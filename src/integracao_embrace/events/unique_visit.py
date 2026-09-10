from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient
from integracao_embrace.utils import get_date_from_redcap
from integracao_embrace.mappings.procedures_maps import POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP
from integracao_embrace.mappings.site_code_maps import SITE_CODE_MAPPING
from integracao_embrace.mappings.gender_maps import GENDER_MAPPING
from integracao_embrace.config import config

import logging
import json
import pandas as pd
import time
import unicodedata
import re

logger = logging.getLogger(__name__)

def sync_unique_event(
    *,
    record_id: str,
    event_name: str,
    redcap: RedcapClient,
    polotrial: PoloTrialClient,
    protocol_nickname: str,
) -> None:
    """
    Synchronize a unique event from REDCap to PoloTrial.
    
    Args:
        record_id (str): The REDCap record ID.
        event_name (str): The REDCap event name.
        redcap (RedcapClient): An instance of the RedcapClient to interact with REDCap API.
        polotrial (PoloTrialClient): An instance of the PoloTrialClient to interact with PoloTrial API.
        protocol_nickname (str): The nickname of the protocol in PoloTrial to which the event belongs.
        
    Raises:
        RuntimeError: If any critical step fails, such as missing mappings or failed API calls.
    
    Returns:
        None: The function performs synchronization and does not return any value.
    
    Steps:
        1. Fetch the REDCap payload for the given record and event.
        2. Map gender and site codes using predefined mappings.
        3. Prepare the volunteer payload and check if the volunteer exists in PoloTrial.
        4. If the volunteer does not exist, create a new volunteer in PoloTrial.
        5. Fetch the protocol from PoloTrial using the site code and protocol nickname.
        6. Fetch the arms of the protocol and find the one that matches the unique arm name from the configuration.
        7. Check if the participant already exists in PoloTrial for the given volunteer and protocol. If not, create a new participant.
        8. Fetch the participant's visits from PoloTrial and look for the unique visit by name. Update the visit if necessary.
        9. Synchronize the unique event procedures and link the executor.
        10. Log the completion of the synchronization process.
    """
    
    
    #1. Fetch the REDCap payload for the given record and event
    redcap_payload = redcap.export_record_eav(
        record_id,
        event_name
    )
    
    #2. Helper function to retrieve REDCap field values with fallback
    def rc(
        config_attr: str,
        fallback: str = ""
    ) -> str:
        """
        Retrieve the value of a REDCap field based on the configuration attribute.

        Args:
            config_attr (str): The configuration attribute name.
            fallback (str, optional): The fallback value if the field is not found. Defaults to "".

        Returns:
            str: The value of the REDCap field or the fallback value.
        
        Steps:
            1. Get the field name from the configuration using the provided attribute.
            2. If the field name is not found, return the fallback value.
            3. If the field name is "record_id", return the record_id.
            4. Retrieve the value from the REDCap payload using the field name.
            5. Log the retrieved value for debugging purposes.
        """
        
        
        field_name = getattr(config, config_attr, "")
        if not field_name:
            return fallback
        
        if field_name == "record_id":
            return record_id
        
        value = redcap_payload.get(field_name, "")
        logger.debug("rd(%s) ➡ field_name=%s value=%r", config_attr, field_name, value)
        return str(value) if value else fallback
    
    #3. Map gender and site codes
    gender_code = GENDER_MAPPING.get(rc("GENERO").strip(), None)
    logger.info("Mapped gender: %s ➡ %s", rc("GENERO"), gender_code)
    
    site_code = SITE_CODE_MAPPING.get(rc("CENTRO").strip(), None)
    logger.info("Mapped site: %s ➡ %s", rc("CENTRO"), site_code)
    
    volunteer_payload = {
        "nome": rc("NOME", record_id),
        "iniciais": rc("INICIAIS"),
        'data_nascimento': rc("DATA_NASCIMENTO"),
        'sexo': gender_code,
        'email': rc("EMAIL"),
        'data_inclusao': rc("DATA_INCLUSAO"),
        'centro': site_code,
        'contatos': "11111111111"
    }
    logger.info("Volunteer payload prepared: %s", volunteer_payload)
    
    if not site_code:
        raw_centro = rc("CENTRO")
        raise RuntimeError(f"Site code mapping not found for CENTRO value: {raw_centro!r}. Please check SITE_CODE_MAPPING keys.")
    
    #4. Check if the volunteer already exists in PoloTrial
    existing = polotrial.find_volunteer_by_name(volunteer_payload["nome"])
    if existing:
        co_voluntario = int(existing['id'])
        logger.info("Volunteer %s already exists in PoloTrial with ID: %d", record_id, co_voluntario)
        
        changed_fields = {
            key: value
            for key, value in volunteer_payload.items()
            if str(existing.get(key, "")) != str(value)
        }
        if changed_fields:
            logger.info("Volunteer %s data changed in REDCap, updating in PoloTrial: %s", record_id, changed_fields)
            polotrial.update_volunteer(co_voluntario, volunteer_payload)
    else:
        created = polotrial.create_volunteer(volunteer_payload)
        co_voluntario = int(created['id'])
        logger.info("Volunteer %s created in PoloTrial with ID: %d", record_id, co_voluntario)
    
    #5. Fetch the protocol from PoloTrial using the site code and protocol nickname
    logger.info("DEBUG: Searching protocol %s for site %s", protocol_nickname, site_code)
    protocol = polotrial.get_protocol(
        co_centro=site_code,
        apelido_protocolo = protocol_nickname
    )
    if not protocol:
        raise RuntimeError(f"Protocol with nickname {protocol_nickname} not found for site code {site_code}.")
    co_protocolo = int(protocol['id'])
    logger.info("Protocol found: %s with ID: %d (site=%s)", protocol_nickname, co_protocolo, site_code)
    
    #6. Fetch the arms of the protocol and find the one that matches the unique arm name from the configuration
    arms = polotrial.list_arms(co_protocolo)
    unique_arm_name = config.POLOTRIAL_ARM_NAME.strip()
    
    if not unique_arm_name:
        raise RuntimeError("POLOTRIAL_ARM_NAME is not set in the configuration.")
    
    arm_match = next(
        (
            a for a in arms
            if _normalize(unique_arm_name) in _normalize(a.get('nome', ''))
        ),
        None,
    )
    
    #6.1. Log the arms found and the matching process
    logger.info("DEBUG: Protocol Arm founded for the unique visit: %s", [a.get("nome") for a in arms if _normalize(unique_arm_name) in _normalize(str(a.get("nome", "")))])
    
    if not arm_match:
        raise RuntimeError(f"Arm with name containing '{unique_arm_name}' not found in protocol {protocol_nickname}.")
    
    #6.2. Extract the arm ID from the matched arm
    co_braco = int(arm_match['id'])
    logger.info("Arm matched: %s with ID: %d", arm_match.get("nome"), co_braco)
    
    #7. Check if the participant already exists in PoloTrial for the given volunteer and protocol
    participant = polotrial.find_participant(
        co_voluntario=co_voluntario,
        co_protocolo=co_protocolo
    )
    if participant:
        co_participante = int(participant['id'])
        logger.info("Participant found in PoloTrial with ID: %d", co_participante)
    else:
        
        participant_payload = {
            "co_voluntario": co_voluntario,
            "co_protocolo": co_protocolo,
            "data_inclusao": rc("DATA_INCLUSAO"),
            "id_participante": rc("PARTICIPANT_ID", record_id),
            "numero_de_screening": rc("NOME", record_id),
            "status_participante": "540",
            "co_braco": co_braco,
            "atualizar_agenda": "1",
            "apagar_visitas_pendentes": "0"
        }
        
        logger.info("DEBUG: Sending participant payload to PoloTrial: \n%s", json.dumps(participant_payload, indent=2))
        
        #7.1. Create the participant in PoloTrial
        created = polotrial.create_participant(participant_payload)
        logger.info("DEBUG: Participant created in PoloTrial: \n%s", json.dumps(created, indent=2))
        
        #7.2. Extract the participant ID from the created response
        co_participante = int(created['id'])
        logger.info("Participant created in PoloTrial with ID: %d", co_participante)
    
    #8. Fetch the participant's visits from PoloTrial and look for the unique visit by name
    time.sleep(20)
    visit = polotrial.list_participant_visits(co_participante=co_participante)
    logger.info("Participant visits retrieved: %d, for participant ID: %d", len(visit), co_participante)
    
    unique_visit_name = config.POLOTRIAL_UNIQUE_VISIT_NAME.strip()
    
    unique_visit = next(
        (
            v for v in visit if v.get("nome_tarefa", "") == unique_visit_name
        ),
        None
    )
    logger.info("Looking for unique visit with name: %s among: %s", unique_visit_name, [v.get("nome_tarefa") for v in visit])
    if not unique_visit:
        raise RuntimeError(f"Unique visit with name '{unique_visit_name}' not found for participant ID {co_participante}.")
    
    participant_visit_id = int(unique_visit['id'])
    logger.info("Participant visit found: %s with ID: %d", unique_visit.get("nome_tarefa"), participant_visit_id)
    desired = {
        "data_estimada": rc("DATA_ESTIMADA_VISITA"),
        "data_realizada": rc("DATA_REALIZADA_VISITA"),
        "status": 20
    }
    
    current = polotrial.get_participant_visit(participant_visit_id)
    #
    if str(current.get("data_realizada", ""))[:10] == str(desired["data_realizada"])[:10] and int(current.get("status", -1)) == int(desired["status"]):
        logger.info("Unique visit already up to date (id=%s).", participant_visit_id)
    else:
        polotrial.update_participant_visit(
            participant_visit_id=participant_visit_id,
            payload=desired
        )
        logger.info("Unique visit updated (id=%s) with payload: %s", participant_visit_id, json.dumps(desired, indent=2))
        
    #9. Synchronize the unique event procedures and link the executor
    pvp_df = sync_unique_event_procedures(
        participante_visita_id=participant_visit_id,
        co_protocolo=co_protocolo,
        polotrial=polotrial,
        redcap_payload=redcap_payload
    )
    sync_executor(
        merged_procedures_df=pvp_df,
        volunteer_payload=redcap_payload,
        polotrial=polotrial,
    )
    
    logger.info("Unique visit synchronization completed for record_id=%s, event_name=%s", record_id, event_name)
    
    

    #-------------------------------------------------------------------------------------------------------------------------------------------------------------------
    #                                                      sync_unique_event_procedures function to synchronize procedures
    #-------------------------------------------------------------------------------------------------------------------------------------------------------------------    
def sync_unique_event_procedures(
    *,
    participante_visita_id: int,
    co_protocolo: int,
    polotrial: PoloTrialClient,
    redcap_payload: Dict[str, Any]
) -> pd.DataFrame:
    """
    Synchronize unique event procedures for a participant visit.

    Args:
        participante_visita_id (int): ID of the participant visit.
        co_protocolo (int): Protocol ID.
        polotrial (PoloTrialClient): PoloTrial client instance.
        redcap_payload (Dict[str, Any]): REDCap payload containing procedure data.

    Returns:
        pd.DataFrame: DataFrame containing the synchronized participant visit procedures.
    
    Steps:
        1. Fetch participant visit procedures from PoloTrial.
        2. Convert the raw data to a DataFrame.
        3. Extract procedure names.
        4. Match procedures with REDCap fields.
        5. Log unmatched procedures.
    """
    
    
    #1. Fetch participant visit procedures from PoloTrial
    
    pvp_raw = polotrial.list_participant_visit_procedures(
        co_participante_visita=participante_visita_id,
    )
    
    #2. Convert the raw data to a DataFrame and extract procedure names
    pvp_df = pd.DataFrame(pvp_raw)
    
    #2.1. Extract 'nome_procedimento_estudo' from 'dados_protocolo_procedimento' if it exists, otherwise fetch from /protocolo_procedimento
    if 'dados_protocolo_procedimento' in pvp_df.columns:
        pvp_df['nome_procedimento_estudo'] = pvp_df['dados_protocolo_procedimento'].apply(
            lambda x: x.get('nome_procedimento_estudo') if isinstance(x, dict) else None
        )
    else:
        #2.1.1. If 'dados_protocolo_procedimento' is not found, fetch procedure details from /protocolo_procedimento
        logger.warning("dados_protocolo_procedimento not found in pvp_df columns. Unable to extract 'nome_procedimento_estudo'. Fetching procedure details from /protocolo_procedimento")
        proto_proc = polotrial.list_protocol_procedures(co_protocolo=co_protocolo)
        proto_df = pd.DataFrame(proto_proc)[['id', 'nome_procedimento_estudo']].rename(columns={'id': 'co_protocolo_procedimento'})
        pvp_df = pd.merge(pvp_df, proto_df, on="co_protocolo_procedimento", how="left")
    
    #2.2. Prepare the mapping DataFrame
    #2.2.1. Create a DataFrame from the POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP for easier matching
    mapping_df = pd.DataFrame(POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP)
    
    #2.3. Initialize new columns in pvp_df for REDCap check and date fields, and the matched procedure pattern
    pvp_df['redcap_check_field'] = None
    pvp_df['redcap_date_field'] = None
    pvp_df['procedure_pattern'] = None
    
    #2.4. Match procedures with REDCap fields using regex patterns from the mapping
    matched_count = 0
    unmatched_procedures = []
    
    for idx, row, in pvp_df.iterrows():
        proc_name = str(row.get('nome_procedimento_estudo', '')).strip()
        matched = False
        
        #2.4.1. Iterate through the mapping to find a matching procedure name using regex
        for cfg in POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP:
            pattern = cfg['procedure_name']
            if re.search(pattern, proc_name, re.IGNORECASE):
                pvp_df.at[idx, 'redcap_check_field'] = cfg['redcap_check_field']
                pvp_df.at[idx, 'redcap_date_field'] = cfg['redcap_date_field']
                pvp_df.at[idx, 'procedure_pattern'] = pattern
                matched = True
                matched_count += 1
                break # Stop after the first match
        if not matched:
            unmatched_procedures.append(proc_name)
    
    #2.5. Log the matched and unmatched procedures for debugging purposes
    logger.info('DEBUG: Available procedures in PoloTrial for unique visit: %s', pvp_df['nome_procedimento_estudo'].tolist())
    for idx, row in pvp_df.iterrows():
        check_field = row.get('redcap_check_field')
        date_field = row.get('redcap_date_field')
        
        #2.5.1. Retrieve the values from the REDCap payload for the check and date fields, with a fallback to 'N/A' if not found
        check_value = redcap_payload.get(check_field, 'N/A') if check_field else 'N/A'
        date_value = redcap_payload.get(date_field, 'N/A') if date_field else 'N/A'
        
        logger.info(
            " - ID: %s | Procedure: %s | Appointment date: %s | Check field: %s=%s | Date field: %s=%s",
            row.get('id'),
            row.get('nome_procedimento_estudo'),
            row.get('data_executada'),
            check_field,
            check_value,
            date_field,
            date_value
        )
    logger.info("DEBUG: Procedure mapping summary:")
    logger.info(" 1. Total procedures in PoloTrial for unique visit: %d", len(pvp_df))
    logger.info(" 2. Matched with REDCap mapping: %d", matched_count)
    logger.info(" 3. Unmatched procedures: %d", len(unmatched_procedures))
    
    if unmatched_procedures:
        logger.warning("DEBUG: Unmatched procedures (no mapping found in POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP): %s", unmatched_procedures)
        for proc in unmatched_procedures:
            logger.warning(" - '%s'", proc)
    
    #3. Iterate through the mapping and synchronize procedures with REDCap data
    total_synced = 0
    
    for cfg in POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP:
        pattern = cfg['procedure_name']
        check_field =  cfg['redcap_check_field']
        date_field = cfg['redcap_date_field']
        
        if not (pattern and check_field and date_field):
            logger.warning("Invalid procedure mapping configuration: %s. Skipping...", cfg)
            continue
        
        #3.1. Find the procedure in pvp_df that matches the current pattern and has no execution date
        to_sync = pvp_df[
            pvp_df['nome_procedimento_estudo'].str.contains(pattern, regex=True, na=False, flags=re.IGNORECASE) & (pvp_df['data_executada'].isna() | (pvp_df['data_executada'] == ''))
        ]
        
        if to_sync.empty:
            logger.info("No procedures to sync for pattern: %s", pattern)
            continue
        
        if len(to_sync) > 1:
            logger.warning("Multiple procedures matched pattern %s, using the first one (%s)", pattern, to_sync['nome_procedimento_estudo'].iloc[0])
        
        procedure_id = int(to_sync['id'].iloc[0])
        procedure_name = to_sync['nome_procedimento_estudo'].iloc[0]
        
        #3.2. Retrieve the date from REDCap for the given check and date fields
        redcap_date = get_date_from_redcap(redcap_payload, check_field, date_field)
        if not redcap_date:
            logger.info("No date found in REDCap for procedure %s (check_field=%s, date_field=%s). Skipping sync.", procedure_name, check_field, date_field)
            continue
        
        #3.3. Strip any leading/trailing whitespace from the REDCap date
        redcap_date = str(redcap_date).strip()
        
        #3.4. Parse and validate the REDCap date
        try:
            #3.4.1. Match the date pattern YYYY-MM-DD
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', redcap_date)
            if not date_match:
                raise ValueError(f'Invalid date format for procedure {procedure_name}: {redcap_date}. Expected YYYY-MM-DD.')
            
            formatted_date = date_match.group(1)
            
            #3.4.2. Validate the date format
            datetime.strptime(formatted_date, '%Y-%m-%d')  # Validate date format
        except ValueError as e:
            logger.error("Error parsing date for procedure %s: %s", procedure_name, e)
            continue
        
        #3.5. Update the procedure in PoloTrial with the formatted date
        polotrial.update_participant_visit_procedures(
            procedure_id,
            {"data_executada": formatted_date}
        )
        logger.info("✅ Synced procedure '%s' (ID: %d) with date: %s", procedure_name, procedure_id, formatted_date)
        total_synced += 1
    
    logger.info("Unique visit procedures synchronization completed. Total procedures synced: %d/%d", total_synced, len(POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP))
    
    return pvp_df
    
    
    
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------
#                                                     sync_executor function to link executor to procedure
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

def sync_executor(
    *,
    merged_procedures_df: pd.DataFrame,
    volunteer_payload: Dict[str, Any],
    polotrial: PoloTrialClient
) -> None:
    
    executor_name = str(volunteer_payload.get("cm_evolucao_executor") or "").strip()
    logger.info("Executor name from REDCap: %s", executor_name)
    if not executor_name:
        logger.info("No executor name provided in REDCap payload. Skipping executor synchronization.")
        return
    
    date_held = str(volunteer_payload.get("cm_atendimento_dt") or "").strip()
    if not date_held:
        logger.info("No date held provided in REDCap payload. Skipping executor synchronization.")
        return
    
    medical_appointment = merged_procedures_df[
        merged_procedures_df["nome_procedimento_estudo"]
        .astype(str)
        .str.contains(r"^Consulta\s+[Mm][eéEÉ]dica$", regex=True, na=False)
    ]
    if medical_appointment.empty:
        logger.info("No medical appointment procedure found in the merged procedures DataFrame. Skipping executor synchronization.")
        return
    
    procedure_id = int(medical_appointment['id'].iloc[0])
    if len(medical_appointment) > 1:
        logger.warning("Multiple medical appointment procedures found. Using the first one with ID: %d", procedure_id)
        
    person = polotrial.find_person_by_name(executor_name)
    if not person:
        logger.error("Executor '%s' not found in PoloTrial. Please ensure the executor exists in the system.", executor_name)
        return
    executor_id = int(person['id'])
    
    existing_links = polotrial.list_procedure_executors(procedure_id=procedure_id)
    already_linked = any(int(x.get("executor", -1)) == executor_id for x in existing_links)
    if already_linked:
        logger.info(
            "Executor '%s' (ID: %d) is already linked to procedure ID: %d. No action needed.", 
            executor_name, 
            executor_id, 
            procedure_id
        )
        return
    
    payload = {
        'co_participante_visita_procedimento': procedure_id,
        'executor': executor_id,
        'data_realizada': date_held,
        'data_previsto_pagamento': "",
        'data_pagamento_realizado': "",
        'valor': "",
        'valor_total_procedimento': "",
        'observacoes': ""
    }
    
    created = polotrial.create_procedure_executor(payload)
    logger.info(
        "Unique visit: Executor '%s' (ID: %d) linked to procedure ID: %d with payload: %s. Response: %s",
        executor_name,
        executor_id,
        procedure_id,
        json.dumps(payload, indent=2),
        json.dumps(created, indent=2)
    )
    
    

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------
#                                                       _normalize function to normalize text for comparison
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _normalize(text: str) -> str:
    
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_only.lower().split())