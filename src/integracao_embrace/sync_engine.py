from __future__ import annotations

import logging
import re
import pandas as pd
import os
import dotenv

from datetime import datetime
from typing import Any, Dict, List, Optional
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient
from integracao_embrace.mapping.site_code_maps import SITE_CODE_MAPPING
from integracao_embrace.config import config

dotenv.load_dotenv(override=True)
UNIQUE_EVENT = config.UNIQUE_EVENT

logger = logging.getLogger(__name__)

def get_participant_info(
    *,
    record_id: str,
    redcap: RedcapClient,
    polotrial: PoloTrialClient,
    protocol_nickname: str
) -> Dict[str, Any]:
    """
    Given a record_id, fetches the corresponding participant information from PoloTrial and Redcap.
    Returns a dictionary with keys 'co_voluntario', 'co_protocolo', and 'co_participante'.
    
    Args:
        record_id (str): The record ID to look up.
        redcap (RedcapClient): An instance of the RedcapClient to interact with Redcap.
        polotrial (PoloTrialClient): An instance of the PoloTrialClient to interact with PoloTrial.
        protocol_nickname (str): The nickname of the protocol to look up in PoloTrial.
    Returns:
        Dict[str, Any]: A dictionary containing 'co_voluntario', 'co_protocolo', and 'co_participante'.
    """
    #1. Volunteer Lookup in PoloTrial
    volunteer = polotrial.find_volunteer_by_name(record_id)
    if not volunteer:
        raise RuntimeError(f"Volunteer with record_id {record_id} not found in PoloTrial.")
    co_voluntario = int(volunteer['id'])
    
    
    #2. Centro Lookup in Redcap
    unique_event_payload = redcap.export_record_eav(
        record_id=record_id,
        event_name=UNIQUE_EVENT,
    )
    co_centro_raw = str(unique_event_payload.get(config.CENTRO) or '').strip()
    co_centro = SITE_CODE_MAPPING.get(co_centro_raw)
    if not co_centro:
        raise RuntimeError(f"Could not map centro = {co_centro_raw!r} to Polotrial")
    
    #3. Protocol Lookup in PoloTrial
    protocol = polotrial.get_protocol(
        co_centro=co_centro,
        apelido_protocolo=protocol_nickname
    )
    if not protocol:
        raise RuntimeError(f"Could not find protocol with nickname {protocol_nickname!r} for centro {co_centro!r}")
    co_protocolo = int(protocol['id'])
    
    #4. Participant Lookup in PoloTrial
    participant = polotrial.find_participant(
        co_voluntario=co_voluntario,
        co_protocolo=co_protocolo
    )
    if not participant:
        raise RuntimeError(f"Could not find participant for co_voluntario={co_voluntario} and co_protocolo={co_protocolo}")
    co_participante = int(participant['id'])
    
    return {
        'co_voluntario': co_voluntario,
        'co_protocolo': co_protocolo,
        'co_participante': co_participante
    }

def update_visit_status(
    *,
    co_participante: int,
    nome_tarefa: str,
    visit_date: str,
    polotrial: PoloTrialClient
) -> int:
    """
    Update the status of a participant's visit in PoloTrial.

    Args:
        co_participante (int): The ID of the participant in PoloTrial.
        nome_tarefa (str): The name of the visit task.
        visit_date (str): The date of the visit.
        polotrial (PoloTrialClient): An instance of the PoloTrialClient to interact with PoloTrial.

    Raises:
        RuntimeError: If the visit with the specified nome_tarefa is not found for the participant.

    Returns:
        int: The ID of the participant visit in PoloTrial.
    """
    visits = polotrial.list_participant_visits(
        co_participante=co_participante
    )
    visit = next((v for v in visits if v.get("nome_tarefa") == nome_tarefa), None)
    if not visit:
        raise RuntimeError(f"Visit with nome_tarefa={nome_tarefa!r} not found for co_participante={co_participante!r} in PoloTrial.")
    
    participante_visita_id = int(visit['id'])
    
    desired = {
        "data_realizada": visit_date,
        "status": 20
    }
    
    if not visit_date:
        logger.warning("%s: visit_date is empty, skipping update for participant_visit_id=%s", nome_tarefa, participante_visita_id)
        return participante_visita_id
    
    current = polotrial.get_participant_visit(participante_visita_id)
    if(
        str(current.get("data_realizada", ""))[:10] == str(desired["data_realizada"])[:10] and
        int(current.get("status", -1)) == desired["status"]
    ):
        logger.info("%s: No update needed for participant_visit_id=%s", nome_tarefa, participante_visita_id)
    else:
        polotrial.update_participant_visit(participante_visita_id, desired)
        logger.info("%s: Updated participant_visit_id=%s with data_realizada=%s and status=%s", nome_tarefa, participante_visita_id, desired["data_realizada"], desired["status"])
    
    return participante_visita_id

def sync_procedures(
    *,
    participante_visita_id: int,
    co_protocolo: int,
    procedures_map: List[Dict[str, Any]],
    redcap_payload: Dict[str, Any],
    polotrial: PoloTrialClient,
    visit_label: str,
) -> pd.DataFrame:
    """
    Sync procedures between REDCap and PoloTrial for a given participant visit.

    Args:
        participante_visita_id (int): The ID of the participant visit in PoloTrial.
        co_protocolo (int): The protocol ID in PoloTrial.
        procedures_map (List[Dict[str, Any]]): Mapping of procedures between REDCap and PoloTrial.
        redcap_payload (Dict[str, Any]): The REDCap data for the participant visit.
        polotrial (PoloTrialClient): The PoloTrial client instance.
        visit_label (str): The label of the visit for logging purposes.

    Returns:
        pd.DataFrame: The updated participant visit procedures DataFrame.
    """

    #1. Fetch participant visit procedures from PoloTrial
    pvp_raw = polotrial.list_participant_visit_procedures(
        co_participante_visita = participante_visita_id
    )
    #2. Convert the raw data to a DataFrame for easier processing
    pvp_df = pd.DataFrame(pvp_raw)
    
    #2.1. Check if the 'dados_protocolo_procedimento' column exists and extract 'nome_procedimento_estudo'
    if 'dados_protocolo_procedimento' in pvp_df.columns:
        pvp_df['nome_procedimento_estudo'] = pvp_df['dados_protocolo_procedimento'].apply(
            lambda x: x.get('nome_procedimento_estudo') if isinstance(x, dict) else None
        )
    else:
        logger.warning("Column 'dados_protocolo_procedimento' not found in participant_visit_procedures data. 'nome_procedimento_estudo' will not be available.")
        if "co_protocolo_procedimento" not in pvp_df.columns:
            raise RuntimeError(
                f"{visit_label}: Polotrial returned no procedures linked to "
                f"participant visit {participante_visita_id} for protocol {co_protocolo}."
            )
        proto_proc = polotrial.list_protocol_procedures(
            co_protocolo = co_protocolo
        )
        proto_df = pd.DataFrame(proto_proc)[['id', 'nome_procedimento_estudo']].rename(columns={'id': 'co_protocolo_procedimento'})
        pvp_df = pd.merge(pvp_df, proto_df, on='co_protocolo_procedimento', how='left')
    
    # 3. Initialize new columns for mapping results
    pvp_df['redcap_check_field'] = None
    pvp_df['redcap_date_field'] = None
    pvp_df['procedure_pattern'] = None
    
    # 3.1. Initialize counters and lists for matched and unmatched procedures
    matched_count = 0
    unmatched_procedures = []
    
    for idx, row in pvp_df.iterrows():
        proc_name = str(row.get('nome_procedimento_estudo', '')).strip()
        matched = False
        #3.2. Iterate through the procedures_map to find a matching pattern for the procedure name
        for cfd in procedures_map:
            pattern = cfd['pattern']
            if re.search(pattern, proc_name, re.IGNORECASE):
                pvp_df.at[idx, 'redcap_check_field'] = cfd['check_field']
                pvp_df.at[idx, 'redcap_date_field'] = cfd['date_field']
                pvp_df.at[idx, 'procedure_pattern'] = pattern
                matched_count += 1
                matched = True
                break
        if not matched:
            unmatched_procedures.append(proc_name)
            
    # DEBUG: Log the available procedures and their mapping results
    logger.info("DEBUG: Available procedures in visit %s", visit_label)
    for idx, row in pvp_df.iterrows():
        check_field = row.get('redcap_check_field')
        date_field = row.get('redcap_date_field')
        pattern = row.get('procedure_pattern')
        
        
        check_value = redcap_payload.get(check_field, 'N/A') if check_field else 'N/A'
        date_value = redcap_payload.get(date_field, 'N/A') if date_field else 'N/A'
        
        logger.info(
            " - ID: %s | Name: %s | Data exec: %s | Pattern: %s | Check Field: %s (Value: %s) | Date Field: %s (Value: %s)",
            row.get('id'),
            row.get('nome_procedimento_estudo'),
            row.get('data_executada'),
            pattern,
            check_field,
            check_value,
            date_field,
            date_value
        )
    logger.info("DEBUG: Procedure mapping summary for visit %s: %d matched, %d unmatched", visit_label, matched_count, len(unmatched_procedures))
    logger.info(" Total procedures in Polotrial: %s", len(pvp_df))
    logger.info(" Matched procedures: %d", matched_count)
    logger.info(" Unmatched procedures: %d", len(unmatched_procedures))
    
    if unmatched_procedures:
        logger.warning(
            "Unmatched procedures in visit %s: %s",
            visit_label,
            unmatched_procedures
        )
        for proc in unmatched_procedures:
            logger.warning(" - Unmatched procedure: %s", proc)
    
    # 4. Sync procedures based on the mapping and REDCap data
    total_synced = 0 
    for cfg in procedures_map:
        pattern = cfg['procedure_name']
        check_field = cfg['redcap_check_field']
        date_field = cfg['redcap_date_field']
        
        if not (pattern and check_field and date_field):
            logger.warning("%s: incomplete mapping configuration for pattern %r. Skipping.", visit_label, pattern)
            continue
        
        #4.1. Filter the DataFrame to find procedures that match the pattern and have no execution date
        to_sync = pvp_df[
            pvp_df['nome_procedimento_estudo'].str.contains(pattern, regex=True,na=False, flags=re.IGNORECASE) & (pvp_df['data_executada'].isna() | (pvp_df["data_executada"] == ""))
        ]
        
        if to_sync.empty:
            logger.info("No procedures to sync for pattern %s in visit %s", pattern, visit_label)
            continue
        
        if len(to_sync) >1:
            logger.warning("Multiple procedures matched pattern %s, using first: %s", pattern, to_sync.iloc[0]['nome_procedimento_estudo'])
        
        procedure_id = int(to_sync['id'].iloc[0])
        procedure_name = to_sync['nome_procedimento_estudo'].iloc[0]
        
        #4.2. Extract the date from REDCap using the specified check and date fields
        redcap_date = get_date_from_redcap(redcap_payload, check_field, date_field)
        if not redcap_date:
            logger.info("%s: No valid date found in REDCap for procedure %s (pattern %s). Skipping sync for this procedure.", visit_label, procedure_name, pattern)
            continue
        
        #4.3. Clean and validate the extracted date
        redcap_date = str(redcap_date).strip()
        
        #4.4. Validate the date format using regex and datetime
        try:
            date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', redcap_date)
            if not date_match:
                raise ValueError(f"Could not extract date from {redcap_date} for procedure {procedure_name} (pattern {pattern}) in visit {visit_label}")
            
            formatted_date = date_match.group(1)
            datetime.strptime(formatted_date, '%Y-%m-%d')  # Validate date format
        except Exception as e:
            logger.error("%s: Error parsing date %r for procedure %s (pattern %s): %s", visit_label, redcap_date, procedure_name, pattern, str(e))
            continue
        
        #4.5. Update the procedure in PoloTrial with the extracted and validated date
        polotrial.update_participant_visit_procedure(
            procedure_id,
            {"data_executada": formatted_date}
        )
        logger.info("✅ %s: Synced procedure '%s' (pattern %s) with date %s", visit_label, procedure_name, pattern, formatted_date)
        
        total_synced += 1
    
    logger.info("%s: Total procedures synced: %d", visit_label, total_synced)
    
    return pvp_df

def get_date_from_redcap(
    payload: Dict[str, Any],
    check_field: str,
    date_field: str
) -> Optional[str]:
    """
    Extracts the date from the REDCap payload based on the provided check and date fields.
    
    Args:
        payload (Dict[str, Any]): The REDCap data for the participant visit.
        check_field (str): The REDCap field that indicates whether the procedure was done.
        date_field (str): The REDCap field that contains the date of the procedure.

    Returns:
        Optional[str]: The extracted date as a string, or None if not available or not done.
    """
    if date_field in payload and payload.get(date_field):
        check_value = str(payload.get(check_field, "")).strip().lower()
        
        if check_field != date_field and check_value in {""}:
            logger.warning(
                "Date exist (%s) but check field %s indicates not done (Value = %r). Skipping",
                date_field,
                check_field, 
                check_value
            )
            return None
        return str(payload[date_field]).strip()
    return None

def sync_executor(
    *,
    merged_procedures_df: pd.DataFrame,
    redcap_payload: Dict[str, Any],
    executor_field: str,
    executor_date_field: str,
    procedure_pattern: str,
    polotrial: PoloTrialClient,
    visit_label: str
) -> None:
    """
    Syncs the executor information for a given procedure based on the REDCap payload.

    Args:
        merged_procedures_df (pd.DataFrame): The merged procedures DataFrame.
        redcap_payload (Dict[str, Any]): The REDCap data for the participant visit.
        executor_field (str): The REDCap field that contains the executor's name.
        executor_date_field (str): The REDCap field that contains the date the procedure was performed.
        procedure_pattern (str): The regex pattern to match the procedure name.
        polotrial (PoloTrialClient): The PoloTrial client instance.
        visit_label (str): The label for the visit, used in logging.

    Returns:
        None
    """
    #1. Extract executor name and date from REDCap payload
    executor_name = str(redcap_payload.get(executor_field, "")).strip()
    if not executor_name:
        logger.warning("%s: Executor name is missing for procedure pattern %s", visit_label, procedure_pattern)
        return
    
    #2. Extract the date the procedure was performed from REDCap payload
    data_realizada = str(redcap_payload.get(executor_date_field, "")).strip()
    if not data_realizada:
        logger.warning("%s: Executor date is missing for procedure pattern %s", visit_label, procedure_pattern)
        return
    
    #3. Find the procedure in the merged DataFrame that matches the given pattern
    proc = merged_procedures_df[
        merged_procedures_df["nome_procedimento_estudo"].astype(str).str.contains(procedure_pattern, regex=True, na=False, flags=re.IGNORECASE)
    ]
    
    if proc.empty:
        logger.warning("%s: No procedure found for pattern %s to sync executor", visit_label, procedure_pattern)
        return
    
    #4. Get the procedure ID and log a warning if multiple procedures match the pattern
    procedure_id = int(proc['id'].iloc[0])
    if len(proc) > 1:
        logger.warning("%s: Multiple procedures found for pattern %s, using first: %s", visit_label, procedure_pattern, proc.iloc[0]['nome_procedimento_estudo'])
    executor_id = int(polotrial.get_person_by_name(executor_name)['id'])  # Assuming polotrial has a method to get person by name
    
    #5. Check if the executor is already linked to the procedure
    existeing_links = polotrial.list_procedure_executors(procedure_id)
    already_linked = any(int(x.get("executor", -1)) == executor_id for x in existeing_links)
    if already_linked:
        logger.info("%s: Executor %r (id=%s) already linked to procedure id=%s. Skipping...", visit_label, executor_name, executor_id, procedure_id)
        return
    
    payload = {
        "co_participante_visita_procedimento": procedure_id,
        "executor": executor_id,
        "data_realizada": data_realizada,
        "data_previsto_pagamento": "",
        "data_realizada_pagamento": "",
        "valor": "",
        "valor_total_procedimento": "",
        "observacoes": ""
    }
    
    created = polotrial.create_procedure_executor(payload)
    logger.info("%s: Executor %r (id=%s) linked to procedure id=%s with data_realizada=%s. Created executor link: %s", visit_label, executor_name, executor_id, procedure_id, data_realizada, created)