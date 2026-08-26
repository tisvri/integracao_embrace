from __future__ import annotations
from typing import Any, Dict, Optional
from datetime import datetime
from integracao_embrace.config import config
from integracao_embrace.mappings.site_code_maps import SITE_CODE_MAPPING
from integracao_embrace.mappings.status_maps import STATUS_CODE_MAPPING
from integracao_embrace.utils import get_date_from_redcap
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient

import pandas as pd
import re
import time
import os
import dotenv
import logging
import json

dotenv.load_dotenv(override=True)

logger = logging.getLogger(__name__)

#====================================================================================================
# Constants
#====================================================================================================
REDCAP_UNIQUE_VISIT_NAME = config.REDCAP_UNIQUE_VISIT_NAME
SITE_CODE = config.CENTRO
PARTICIPANT_STATUS = config.PARTICIPANT_STATUS


#====================================================================================================
#
#====================================================================================================

def sync_participant_status_update(
    *,
    record_id: str,
    event_name: str,
    redcap: RedcapClient,
    polotrial: PoloTrialClient,
    protocol_nickname: str
) -> None:
    
    #1
    redcap_payload = redcap.export_record_eav(
        record_id,
        event_name
    )
    logger.info(f"Retrieved REDCap payload for record_id={record_id}, event_name={event_name}: {redcap_payload}")
    
    unique_event_payload = redcap.export_record_eav(
        record_id,
        REDCAP_UNIQUE_VISIT_NAME
    )
    
    #2 
    raw_site_code = str(unique_event_payload.get(SITE_CODE, "")).strip()
    site_code = SITE_CODE_MAPPING.get(raw_site_code)
    if not site_code:
        raise RuntimeError(f"Site code mapping not found for raw_site_code={raw_site_code} (record_id={record_id})")
    
    #3
    volunteer = polotrial.find_volunteer_by_name(record_id)
    if not volunteer:
        raise RuntimeError(f"Volunteer not found in PoloTrial for record_id={record_id}")
    volunteer_code = int(volunteer.get("id"))
    logger.info(f"Found volunteer in PoloTrial: record_id={record_id}, volunteer_code={volunteer_code}")
    
    #4
    protocol = polotrial.get_protocol(
        co_centro=site_code,
        apelido_protocolo=protocol_nickname
    )
    if not protocol:
        raise RuntimeError(f"Protocol not found in PoloTrial for site_code={site_code}, protocol_nickname={protocol_nickname}")
    
    protocol_code = int(protocol['id'])
    logger.info(f"Found protocol in PoloTrial: site_code={site_code}, protocol_nickname={protocol_nickname}, protocol_code={protocol_code}")
    
    #5
    participant = polotrial.find_participant(
        co_voluntario = volunteer_code,
        co_protocolo = protocol_code
    )
    if not participant:
        raise RuntimeError(f"Participant not found in PoloTrial for volunteer_code={volunteer_code}, protocol_code={protocol_code}")
    participant_code = int(participant['id'])
    logger.info(f"Found participant in PoloTrial: volunteer_code={volunteer_code}, protocol_code={protocol_code}, participant_code={participant_code}")
    
    #6
    redcap_status_raw = str(redcap_payload.get(PARTICIPANT_STATUS) or "").strip()
    if not redcap_status_raw:
        logger.info(f"No participant status found in REDCap for record_id={record_id}, event_name={event_name}. Skipping update.")
        return
    polotrial_status_code = STATUS_CODE_MAPPING.get(redcap_status_raw)
    if not polotrial_status_code:
        logger.warning(f"Participant status mapping not found for REDCap status={redcap_status_raw} (record_id={record_id}). Skipping update.")
        return
    logger.info(f"Mapped REDCap status={redcap_status_raw} to PoloTrial status_code={polotrial_status_code} for record_id={record_id}")
    
    #7
    current_participant = polotrial.get_participant(participant_code)
    current_status_code = str(current_participant.get("status_participante", ""))
    
    if current_status_code == polotrial_status_code:
        logger.info(f"Participant status in PoloTrial already matches REDCap status for record_id={record_id}. No update needed.")
        return
    polotrial.update_participant(
        participant_code,
        {
            "status_participante": polotrial_status_code
        }
    )
    logger.info(f"Updated participant status in PoloTrial for record_id={record_id}: {current_status_code} -> {polotrial_status_code}")