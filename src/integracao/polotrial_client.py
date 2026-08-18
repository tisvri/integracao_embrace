from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin
import requests

logger= logging.getLogger(__name__)

class PoloTrialClient:
    
    
    def __init__(
        self, 
        base_url: str, 
        username: str, 
        password: str, 
        timeout: int=30
        ):
        """
        Client for interaction with Polotrial API

        Args:
            base_url (str): Poltrial API url
            username (str): Polotrial API username
            password (str): Polotrial API password
            timeout (int, optional): defalt timeout to 30 seconds.
        """
        self.base_url=base_url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session=requests.Session()
        self._authed = False
    
    def _login(self) -> None:
        """_summary_

        Raises:
            RuntimeError: _description_
        """
        
        session_url = urljoin(self.base_url, "sessions")
        print(session_url)
        payload = {
            "nome": self.username,
            "password": self.password
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        polotrial_request=self.session.post(session_url, json= payload, headers=headers, timeout=self.timeout)
        if not self.session.cookies.get("userId"):
            raise RuntimeError("Polotrial login failed: userId cookie not found")
        
        self._authed = True
        logger.info("Polotrial: authentication succsssful")
    
    def _requests(
        self, 
        method: str, 
        path: str, 
        *, 
        params = None, 
        json = None
    ) -> requests.Response:
        
        if not self._authed:
            self._login()
            
        url = urljoin(self.base_url, path.lstrip("/"))
        polotrial_response = self.session.request(method, url, params = params, json = json, timeout = self.timeout)
        
        if polotrial_response.status_code in (401, 403):
            logger.warning("Polotrial: auth failed (%s). Retrying login onde...", polotrial_response.status_code)
            self._authed=False
            self._login()
            polotrial_response = self.session.request(method, url, params = params, json = json, timeout = self.timeout)
        
        return polotrial_response
    
    # -----------------------------------------------------------------------------------
    # Integration methods
    # -----------------------------------------------------------------------------------
    
    def find_volunteer_by_name(
        self, 
        name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Search in Polotrial /voluntario endpoint for a volunteer in name field.

        Args:
            name (str): _description_

        Raises:
            RuntimeError: _description_

        Returns:
            Optional[Dict[str, Any]]: _description_
        """
        volunteer_request = self._requests(
            "GET",
            "/voluntarios",
            params={"nome": name}
        )
        if volunteer_request.status_code != 200:
            raise RuntimeError (f"Error querying volunteer: {volunteer_request.status_code} - {volunteer_request.text}")
        data = volunteer_request.json()
        return data[0] if isinstance(data, list) and data else None
    
    def create_volunteer(
        self, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        volunteer_request = self._requests(
            "POST",
            "/voluntarios",
            json = payload
        )
        
        if volunteer_request.status_code in (200, 201):
            return volunteer_request.json()
        
        
        if volunteer_request.status_code == 500:
            logger.warning("Polotrial returned 500 when creating volunteer. Checking if it was created anyway...")
            
            existing = self.find_volunteer_by_name(payload["nome"])
            if existing:
                logger.info("Volunteer was created dispite 500 error. %s", existing["id"])
                return existing
        
        raise RuntimeError(f"Error creating volunteer: {volunteer_request.status_code} - {volunteer_request.text}")
    
    def get_protocol(
        self,
        *,
        co_centro: str,
        apelido_protocolo: str
    ) -> Optional[Dict[str, Any]]:
        
        protocol_request = self._requests(
            "GET",
            "/protocolo",
            params = {
                "co_centro": co_centro,
                "apelido_protocolo": apelido_protocolo
            }
        )
        if protocol_request.status_code != 200:
            raise RuntimeError(f"Error querying protocol: {protocol_request.status_code} - {protocol_request.text}")
        data = protocol_request.json()
        return data[0] if isinstance(data, list) and data else None
    
    def list_arms(
        self,
        co_protocolo: int
    ) -> list[Dict[str, Any]]:
        
        arm_request = self._requests(
            "GET",
            "/braco",
            params = {
                "co_protocolo": str(co_protocolo)
            }
        )
        print(f"arms list: {arm_request}")
        
        if arm_request.status_code == 200:
            data = arm_request.json()
            return data if isinstance(data, list) else []
        
        raise RuntimeError(f"Error fetching arms: {arm_request.status_code} - {arm_request.text}")
    
    def find_participant(
        self,
        *,
        co_voluntario: int,
        co_protocolo: int
    ) -> Optional[Dict[str, Any]]:
        
        participant_request = self._requests(
            "GET",
            "/participantes",
            params = {
                "co_voluntario": str(co_voluntario),
                "co_protocolo": str(co_protocolo)
            }
        )
        if participant_request.status_code != 200:
            raise RuntimeError(f"Error querying participant: {participant_request.status_code} - {participant_request.text}")
        data = participant_request.json()
        return data[0] if isinstance(data, list) and data else None
    
    def get_participant(
        self,
        participant_id: int
    ) -> Dict[str, Any]:
        
        participant_request = self._requests(
            "GET",
            f"/participantes/{participant_id}"
        )
        if participant_request.status_code != 200:
            raise RuntimeError(f"Error fetching participant: {participant_request.status_code} - {participant_request.text}")
        return participant_request.json()
    
    def create_participant(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        participant_request = self._requests(
            "POST",
            "/participantes",
            json = payload
        )
        
        if participant_request.status_code in (200, 201):
            return participant_request.json()
        
        if participant_request.status_code == 500:
            logger.warning("Polotrial returned 500 when creating participant. Checking if it was created anyway...")
            
            co_voluntario = payload.get("co_voluntario")
            co_protocolo = payload.get("co_protocolo")
            
            if co_voluntario and co_protocolo:
                existing = self.find_participant(
                    co_voluntario = co_voluntario,
                    co_protocolo = co_protocolo
                )
                if existing:
                    logger.info("Participant was created despite 500 error. %s", existing["id"])
                    return existing
                
            raise RuntimeError(f"Error creating participant: {participant_request.status_code} - {participant_request.text}")
        
    def list_participant_visits(
        self,
        *,
        co_participante: int
    ) -> list[Dict[str, Any]]:
        
        visit_request = self._requests(
            "GET",
            "/participante_visita",
            params={
                "co_participante": co_participante
            }
        )
        
        if visit_request.status_code != 200:
            raise RuntimeError(f"Error fetching participant visits: {visit_request.status_code} - {visit_request.text}")
        data = visit_request.json()
        return data if isinstance (data, list) else []
    
    def get_participant_visit(
        self,
        participante_visita_id: int
    ) -> Dict[str,Any]:
        
        visit_request = self._requests(
            "GET",
            f"/participante_visita/{participante_visita_id}"
        )
        if visit_request.status_code != 200:
            raise RuntimeError(f"Error fetching participant visit: {visit_request.status_code} - {visit_request.text}")
        return visit_request.json()
        
    
    def list_participant_visit_procedures(
        self, *,
        co_participante_visita: int
    ) -> list[Dict[str, Any]]:
        
        procedures_request = self._requests(
            "GET",
            "/participante_visita_procedimento",
            params={
                "co_participante_visita": co_participante_visita,
                "nested": "true"
            }
        )
        
        if procedures_request.status_code != 200:
            raise RuntimeError(f"Error fetching participant visit procedures: {procedures_request.status_code} - {procedures_request.text}")
        data = procedures_request.json()
        return data if isinstance(data, list) else []
    
    def list_protocol_procedures (
        self, *,
        co_protocolo: int
    ) -> list[Dict[str, Any]]:
        
        procedures_request = self._requests(
            "GET",
            "/protocolo_procedimento",
            params={
                "co_protocolo": co_protocolo
            }
        )
        
        if procedures_request.status_code != 200:
            raise RuntimeError(f"Error fetching protocol procedures: {procedures_request.status_code} - {procedures_request.text}")
        data = procedures_request.json()
        return data if isinstance(data, list) else []
    
    def update_participant_visit_procedures(
        self,
        procedure_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        procedure_request = self._requests(
            "PUT",
            f"/participante_visita_procedimento/{procedure_id}",
            json = payload
        )
        
        if procedure_request.status_code != 200:
            raise RuntimeError(f"Error updating participant visit procedure: {procedure_request.status_code} - {procedure_request.text}")
        return procedure_request.json()
    
    def create_participant_visit_procedure(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        procedure_request = self._requests(
            "POST",
            "/participante_visita_procedimento",
            json = payload
        )
        
        if procedure_request.status_code != 200:
            raise RuntimeError(f"Error creating participant visit procedure: {procedure_request.status_code} - {procedure_request.text}")
        return procedure_request.json()
    
    def find_person_by_name(
        self,
        ds_nome: str
    ) -> Optional[Dict[str, Any]]:
        
        person_request = self._requests(
            "GET",
            "/pessoas",
            params = {
                "ds_nome": ds_nome
            }
        )
        
        if person_request.status_code != 200:
            raise RuntimeError(f"Error fetching person by name: {person_request.status_code} - {person_request.text}")
        data = person_request.json()
        return data[0] if isinstance(data, list) and data else None
    
    def create_procedure_executor (
        self, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        executor_request = self._requests(
            "POST",
            "/participante_visita_procedimento_executor",
            json=payload
        )
        if executor_request.status_code != 200:
            raise RuntimeError(f"Error creating procedure executor: {executor_request.status_code} - {executor_request.text}")
        return executor_request.json()
    
    def list_procedure_executors(
        self,
        co_participante_visita_procedimento: int
    ) -> list[Dict[str, Any]]:
        
        executor_request = self._requests(
            "GET",
            "/participante_visita_procedimento_executor",
            params = {
                "co_participante_visita_procedimento": co_participante_visita_procedimento
            }
        )
        if executor_request.status_code != 200:
            raise RuntimeError(f"Error listing procedure executors: {executor_request.status_code} - {executor_request.text}")
        data = executor_requests.json()
        return data if isinstance(data, list) else []
    
    def update_participant(
        self,
        participant_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        update_participant_request = self._requests(
            "PUT",
            f"/participantes/{participant_id}",
            json = payload
        )
        if update_participant_request.status_code != 200:
            raise RuntimeError(f"Error updating participant: {update_participant_request.status_code} - {update_participant_request.text}")
        return update_participant_request.json()
    
    def create_participant_visit(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        if not payload.get("data_estimada") and payload("data_realizada"):
            payload = {
                **payload,
                "data_estimada": payload["data_realizada"],
            }
        
        logger.info(
            "Polotrial: creating participant visit co_participante=%s, nome_tarefa=%s, data_estimada=%s, data_realizada=%s, status=%s",
            payload.get("co_participante"),
            payload.get("nome_tarefa"),
            payload.get("data_estimada"),
            payload.get("data_realizada"),
            payload.get("status")
        )
        
        request = self._requests(
            "POST",
            "/participante_visita",
            json = payload
        )
        
        if request.status_code in (200, 201):
            return request.json()
        
        if request.satus_code == 500:
            logger.warning("Polotrial returned 500 error when creating visit. Cheking if it was created anyway...")
            
            co_participante = payload.get("co_participante")
            nome_tarefa = payload.get("nome_tarefa")
            
            if co_participante and nome_tarefa:
                visits = self.list_participant_visit(
                    co_participante = co_participante
                )
                
                matching_visits = [v for v in visits if v.get("nome_tarefa") == nome_tarefa]
                if matching_visits:
                    latest_visit = max(matching_visits, key=lambda v: v.get("id", 0))
                    logger.info("Visit was created despite 500 erro: %s", latest_visit["id"])
                    return latest_visit
        
        raise RuntimeError(f"Error creating participant visit: {request.status_code} - {request.text}")
    
    def update_participant_visit(
        self,
        participante_visita_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        request = self._requests(
            "PUT",
            f"/participante_visita/{participante_visita_id}",
            json=payload
        )
        if request.status_code != 200:
            raise RuntimeError(f"Error updating participant visit: {request.status_code} - {request.text}")
        return request.json()