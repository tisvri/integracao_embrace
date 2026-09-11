from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin
import requests

logger= logging.getLogger(__name__)

class PoloTrialClient:
    """
    Client for interaction with Polotrial API.
    
    """
    
    
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
        """Authenticate with the Polotrial API.

        Raises:
            RuntimeError: If authentication fails.
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
        """Make an HTTP request to the Polotrial API.

        Args:
            method (str): HTTP request method (POST, GET or PUT)
            path (str): API endpoint path (e.g., "/voluntarios")
            params (dict, optional): Query parameters for the request. Defaults to None.
            json (dict, optional): JSON payload for the request. Defaults to None.

        Returns:
            requests.Response: The response object from the Polotrial API.
        Raises:
            RuntimeError: If the request fails after retrying authentication.
        """
        
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
            name (str): The name of the volunteer to search for.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Optional[Dict[str, Any]]: The volunteer data if found, otherwise None.
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
        """
        Create a new volunteer in the Polotrial system.

        Args:
            payload (Dict[str, Any]): The volunteer data to create.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The created volunteer data.
        """
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
    
    def update_volunteer(
        self,
        volunteer_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a volunteer.

        Args:
            volunteer_id (int): The ID of the volunteer to update.
            payload (Dict[str, Any]): The data to update the volunteer with.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The updated volunteer data.
        """
        update_volunteer_request = self._requests(
            "PUT",
            f"/voluntarios/{volunteer_id}",
            json = payload
        )
        if update_volunteer_request.status_code != 200:
            raise RuntimeError(f"Error updating volunteer: {update_volunteer_request.status_code} - {update_volunteer_request.text}")
        return update_volunteer_request.json()
    
    def get_protocol(
        self,
        *,
        co_centro: str,
        apelido_protocolo: str
    ) -> Optional[Dict[str, Any]]:
        """Get a protocol from the Polotrial system.

        Args:
            co_centro (str): The center code of the protocol.
            apelido_protocolo (str): The protocol nickname.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Optional[Dict[str, Any]]: The protocol data if found, otherwise None.
        """
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
        """List the arms of a protocol.

        Args:
            co_protocolo (int): The protocol code.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            list[Dict[str, Any]]: The list of arms for the protocol.
        """
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
        """Find a participant in a protocol.

        Args:
            co_voluntario (int): The volunteer code.
            co_protocolo (int): The protocol code.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Optional[Dict[str, Any]]: The participant data if found, otherwise None.
        """
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
        """Get a participant by ID.

        Args:
            participant_id (int): The participant ID.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The participant data.
        """
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
        """Create a new participant.

        Args:
            payload (Dict[str, Any]): The participant data to create.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The created participant data.
        """
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
        """List visits for a participant.

        Args:
            co_participante (int): The participant code.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            list[Dict[str, Any]]: The list of participant visits.
        """
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
    ) -> Dict[str, Any]:
        """Get a participant visit by ID.

        Args:
            participante_visita_id (int): The participant visit ID.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The participant visit data.
        """
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
        """List procedures for a participant visit.

        Args:
            co_participante_visita (int): The participant visit code.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            list[Dict[str, Any]]: The list of participant visit procedures.
        """
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
        """List procedures for a protocol.

        Args:
            co_protocolo (int): The protocol code.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            list[Dict[str, Any]]: The list of protocol procedures.
        """
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
        """Update a participant visit procedure.

        Args:
            procedure_id (int): The procedure ID.
            payload (Dict[str, Any]): The data to update the procedure with.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The updated participant visit procedure.
        """
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
        """Create a participant visit procedure.

        Args:
            payload (Dict[str, Any]): The data for the new participant visit procedure.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The created participant visit procedure.
        """
        procedure_request = self._requests(
            "POST",
            "/participante_visita_procedimento",
            json = payload
        )
        
        if procedure_request.status_code not in (200, 201):
            raise RuntimeError(f"Error creating participant visit procedure: {procedure_request.status_code} - {procedure_request.text}")
        return procedure_request.json()
    
    def find_person_by_name(
        self,
        ds_nome: str
    ) -> Optional[Dict[str, Any]]:
        """Find a person by name.

        Args:
            ds_nome (str): The name of the person.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Optional[Dict[str, Any]]: The person data if found, else None.
        """
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
        """Create a procedure executor.

        Args:
            payload (Dict[str, Any]): The data for the new procedure executor.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The created procedure executor.
        """
        executor_request = self._requests(
            "POST",
            "/participante_visita_procedimento_executor",
            json=payload
        )
        if executor_request.status_code not in (200, 201):
            raise RuntimeError(f"Error creating procedure executor: {executor_request.status_code} - {executor_request.text}")
        return executor_request.json()
    
    def list_procedure_executors(
        self,
        co_participante_visita_procedimento: int
    ) -> list[Dict[str, Any]]:
        """List procedure executors for a participant visit procedure.

        Args:
            co_participante_visita_procedimento (int): The participant visit procedure code.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            list[Dict[str, Any]]: The list of procedure executors.
        """
        executor_request = self._requests(
            "GET",
            "/participante_visita_procedimento_executor",
            params = {
                "co_participante_visita_procedimento": co_participante_visita_procedimento
            }
        )
        if executor_request.status_code != 200:
            raise RuntimeError(f"Error listing procedure executors: {executor_request.status_code} - {executor_request.text}")
        data = executor_request.json()
        return data if isinstance(data, list) else []
    
    def update_participant(
        self,
        participant_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a participant.

        Args:
            participant_id (int): The ID of the participant to update.
            payload (Dict[str, Any]): The data to update the participant with.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The updated participant.
        """
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
        """Create a participant visit.

        Args:
            payload (Dict[str, Any]): The data for the new participant visit.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The created participant visit.
        """
        if not payload.get("data_estimada") and payload.get("data_realizada"):
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
        
        if request.status_code == 500:
            logger.warning("Polotrial returned 500 error when creating visit. Checking if it was created anyway...")
            
            co_participante = payload.get("co_participante")
            nome_tarefa = payload.get("nome_tarefa")
            
            if co_participante and nome_tarefa:
                visits = self.list_participant_visit(
                    co_participante = co_participante
                )
                
                matching_visits = [v for v in visits if v.get("nome_tarefa") == nome_tarefa]
                if matching_visits:
                    latest_visit = max(matching_visits, key=lambda v: v.get("id", 0))
                    logger.info("Visit was created despite 500 error: %s", latest_visit["id"])
                    return latest_visit
        
        raise RuntimeError(f"Error creating participant visit: {request.status_code} - {request.text}")
    
    def update_participant_visit(
        self,
        # participante_visita_id: int, Antigo (com erro)
        participant_visit_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a participant visit.

        Args:
            participant_visit_id (int): The ID of the participant visit to update.
            payload (Dict[str, Any]): The data to update the participant visit with.

        Raises:
            RuntimeError: If the request to the Polotrial API fails.

        Returns:
            Dict[str, Any]: The updated participant visit.
        """
        # request = self._requests(
        #     "PUT",
        #     f"/participante_visita/{participante_visita_id}",
        #     json=payload
        # )
        request = self._requests(
                    "PUT",
                    f"/participante_visita/{participant_visit_id}",
                    json=payload
                )
        if request.status_code != 200:
            raise RuntimeError(f"Error updating participant visit: {request.status_code} - {request.text}")
        return request.json()