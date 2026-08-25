from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient
from integracao_embrace.utils import get_date_from_redcap
from integracao_embrace.mappings.procedures_maps import PROCEDURE_MAPPING
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
    
    site_code = SITE_CODE_MAPPING.get(rc("SITE").strip(), None)
    logger.info("Mapped site: %s ➡ %s", rc("SITE"), site_code)
    
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
    unique_arm_name = config.UNIQUE_ARM_NAME.strip()
    
    if not unique_arm_name:
        raise RuntimeError("UNIQUE_ARM_NAME is not set in the configuration.")
    
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
    
    #8. 
    time.sleep(20)
    visit = polotrial.list_participant_visits(co_participante=co_participante)
    logger.info("Participant visits retrieved: %d, for participant ID: %d", len(visit), co_participante)
    
    unique_visit_name = config.UNIQUE_POLOTRIAL_VISIT_NAME.strip()
    
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
    
    
    
    
    
    #-------------------------------------------------------------------------------------------------------------------------------------------------------------------
    #                                                       _normalize function to normalize text for comparison
    #-------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def _normalize(text: str) -> str:
        
        nfkd = unicodedata.normalize("NFKD", text)
        ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
        return " ".join(ascii_only.lower().split())