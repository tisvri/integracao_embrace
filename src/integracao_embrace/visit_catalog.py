from __future__ import annotations
from typing import Dict, Any, Optional
from integracao_embrace.config import config
import os
import dotenv


#Redcap Unique Event
UNIQUE_EVENT = config.UNIQUE_EVENT_NAME

#Polotrial Unique Event
POLOTRIAL_UNIQUE_EVENT = config.POLOTRIAL_UNIQUE_EVENT_NAME

# Importing procedure mapping from sync_engine to avoid circular dependency
from integracao_embrace.mappings.procedures_maps import (
    POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP
)

class VisitConfig:
    
    def __init__(
        self, *,
        redcap_event_name: str,
        polotrial_visit_name: str,
        date_field: str,
        procedures_map: list,
        executor_config: Optional[Dict[str, Any]] = None
    ):
        self.redcap_event_name = redcap_event_name
        self.polotrial_visit_name = polotrial_visit_name
        self.date_field = date_field
        self.procedures_map = procedures_map
        self.executor_config = executor_config or {}
        
        VISIT_CATALOG = {
            #UNIQUE EVENT
            UNIQUE_EVENT: VisitConfig(
                redcap_event_name = UNIQUE_EVENT,
                polotrial_visit_name = POLOTRIAL_UNIQUE_EVENT,
                date_field = "idp4",
                procedures_map = POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP,
                executor_config = {
                    'field': 'cm_evolucao_executor',
                    'date_field': 'cm_atendimento_dt',
                    'procedure_pattern': r"^Consulta M[eéEÉ]dica$"
                }
            )
        }