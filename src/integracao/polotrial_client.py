from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin
import requests

logger= logging.getLogger(__name__)

class PoloTrialClient:
    
    
    def __init__(self, base_url: str, username: str, password: str, timeout: int=30):
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
    
    def _requests(self, method: str, path: str, *, params = None, json = None) -> requests.Response:
        
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
    
    def find_volunteer_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """_summary_

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