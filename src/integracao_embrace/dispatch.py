from __future__ import annotations

import logging
import os

from integracao_embrace.events.unique_visit import sync_unique_event
from integracao_embrace.events.status_update import sync_participant_status_update
from integracao_embrace.visit_catalog import VISIT_CATALOG
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient

import os
import dotenv
from integracao_embrace.config import config

dotenv.load_dotenv(override=True)
REDCAP_UNIQUE_EVENT = config.REDCAP_UNIQUE_VISIT_NAME
# PARTICIPANT_STATUS_INSTRUMENT é um instrumento dentro do evento da visita única, não um event_name.
PARTICIPANT_STATUS_INSTRUMENT = config.PARTICIPANT_STATUS_INSTRUMENT

logger = logging.getLogger(__name__)


def dispatch_event(
    *,
    record_id: str,
    event_name: str,
    redcap: RedcapClient,
    polotrial: PoloTrialClient,
    protocol_nickname: str,
    instrument: str | None = None,
    repeat_instance: str | None=None,
) -> None:
    """
            Dispatch events to the appropriate handlers.
    
            Args:
                record_id (str): The record ID.
                event_name (str): The name of the event.
                redcap (RedcapClient): The REDCap client instance.
                polotrial (PoloTrialClient): The PoloTrial client instance.
                protocol_nickname (str): The protocol nickname.
                instrument (str | None, optional): The REDCap instrument (form) that triggered the DET. Defaults to None.
                repeat_instance (str | None, optional): The repeat instance. Defaults to None.
        """
    logger.info(
        "Dispatch runtime: pid=%s, module=%s, event_name=%r, instrument=%r",
        os.getpid(),
        __file__,
        event_name,
        instrument,
    )
    event_name=event_name.strip()
    instrument = (instrument or "").strip()
    
    if event_name == REDCAP_UNIQUE_EVENT:
        logger.info( "Dispatching to unique visit handles: %s", event_name)
        sync_unique_event(
            record_id=record_id,
            event_name=event_name,
            redcap=redcap,
            polotrial=polotrial,
            protocol_nickname=protocol_nickname,
        )
        
        if instrument == PARTICIPANT_STATUS_INSTRUMENT:
            logger.info("Dispatching to participant status update handler: instrument=%s", instrument)
            sync_participant_status_update(
                record_id=record_id,
                event_name=event_name,
                redcap=redcap,
                polotrial=polotrial,
                protocol_nickname=protocol_nickname
            )
        return
    
    logger.warning("No handlers implemented for event: %s", event_name)
    raise RuntimeError(f" No handler implemented for event: {event_name}")