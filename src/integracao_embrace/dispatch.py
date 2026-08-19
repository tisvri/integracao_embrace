from __future__ import annotations

import logging
import os

from integracao_embrace.events.unique_visit import sync_unique_visit
from integracao_embrace.events.status_update import PARTICIPANT_STATUS_EVENT, sync_participant_status_update
from integracao_embrace.visits_catalog import VISITS_CATALOG
from integracao_embrace.polotrial_client import PoloTrialClient
from redcap_client import RedcapClient

import os
import dotenv
from integracao_embrace.config import config

dotenv.load_dotenv(override=True)
UNIQUE_EVENT = config.UNIQUE_EVENT_NAME
PARTICIPANT_STAUS_EVENT = config.PARTICIPANT_STATUS_EVENT_NAME

logger = logging.getLogger(__name__)


def dispatch_event(
    *,
    record_id: str,
    event_name: str,
    redcap: RedcapClient,
    polotrial: PoloTrialClient,
    protocol_nickname: str,
    repeat_instance: str | None=None,
) -> None:
    
    logger.info(
        "Dispatch runtime: pid=%s, module=%s, event_name=%r ",
        os.getpid(),
        __file__,
        event_name,
        
    )
    event_name=event_name.strip()
    
    if event_name == UNIQUE_EVENT:
        logger.info( "Dispatching to unique visit handles: %s", event_name)
        sync_unique_visit(
            record_id=record_id,
            event_name=event_name,
            redcap=redcap,
            polotrial=polotrial,
            protocol_nickname=protocol_nickname,
            repeat_instance=repeat_instance
        )
        return
    
    if event_name==PARTICIPANT_STATUS_EVENT:
        logger.info("Dispatching to participant status update handler: %s", event_name)
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