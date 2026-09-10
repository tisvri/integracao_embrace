from __future__ import annotations
from typing import Dict, Any, Optional
from integracao_embrace.config import config
import os
import dotenv


#Redcap Unique Event
REDCAP_UNIQUE_EVENT = config.REDCAP_UNIQUE_VISIT_NAME


#Polotrial Unique Event
POLOTRIAL_UNIQUE_EVENT = config.POLOTRIAL_UNIQUE_VISIT_NAME

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
        """
        Visit configuration for a specific visit.

        Args:
            redcap_event_name (str): The REDCap event name.
            polotrial_visit_name (str): The PoloTrial visit name.
            date_field (str): The date field associated with the visit.
            procedures_map (list): The mapping of procedures for the visit.
            executor_config (Optional[Dict[str, Any]], optional): The executor configuration. Defaults to None.
        """
        
        self.redcap_event_name = redcap_event_name
        self.polotrial_visit_name = polotrial_visit_name
        self.date_field = date_field
        self.procedures_map = procedures_map
        self.executor_config = executor_config or {}
        
VISIT_CATALOG = {
    #UNIQUE EVENT
    REDCAP_UNIQUE_EVENT: VisitConfig(
        redcap_event_name = REDCAP_UNIQUE_EVENT,
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