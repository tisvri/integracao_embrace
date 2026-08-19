from __future__ import annotations
import logging
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class RedcapClient:
    def __init__(
        self,
        api_url: str,
        api_token: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        """Initialize the RedcapClient.

        Args:
            api_url (str): The URL of the REDCap API endpoint.
            api_token (str): The API token for authentication.
            verify_ssl (bool, optional): Whether to verify SSL certificates. Defaults to True.
            timeout (int, optional): The request timeout in seconds. Defaults to 30.
        """
        self.api_url = api_url
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (compatible;redcap-client/1.0)",
            "Accept": "application/json",
        })
    
    def export_record_eav(
        self,
        record_id: str,
        event_name: str,
        *,
        repeat_instance: Optional[str] = None,
        raw_or_label: str = 'label',
        raw_or_label_headers: str = 'label',
    ) -> Dict[str, Any]:
        """Export a REDCap record in EAV format.

        Args:
            record_id (str): The ID of the record to export.
            event_name (str): The name of the event to export.
            repeat_instance (Optional[str], optional): The repeat instance to export. Defaults to None.
            raw_or_label (str, optional): Whether to export raw values or labels. Defaults to 'label'.
            raw_or_label_headers (str, optional): Whether to export raw or label headers. Defaults to 'label'.

        Raises:
            ValueError: If the REDCap response is not in the expected format.

        Returns:
            Dict[str, Any]: The exported record in EAV format.
        """
        payload = {
            "token": self.api_token,
            "content": "record",
            "format": "json",
            "type": "eav",
            "records": [record_id],
            "events": [event_name],
            "exportRepeatingInstruments": "true",
            "rawOrLabel": raw_or_label,
            "rawOrLabelHeaders": raw_or_label_headers,
            "exportCheckboxLabel": "false",
            "returnFormat": "json",
        }
        
        redcap_request = self.session.post(
            self.api_url,
            data = payload,
            timeout = self.timeout
        )
        
        
        #==================================================================================================
        # Temporary DEBUG: log the full response if the request fails, to help with debugging
        #==================================================================================================
        
        
        print("Início debug redcap response")
        logger.info("Debug redcap url: %s", self.api_url)
        logger.info("Debug redcaptoken (First 3 chars): %s...", self.api_token[:3] if self.api_token else "No token provided")
        logger.info("Debug redcap status: %s", redcap_request.status_code)
        logger.info("Debug redcap response (first 30 chars): %s", redcap_request.text[:30] if redcap_request.text else "No response text")
        print("Fim debug redcap response")
        
        #==================================================================================================
        # End of temporary DEBUG logging
        #==================================================================================================
        
        redcap_request.raise_for_status()
        
        data = redcap_request.json()
        if not isinstance(data, list):
            raise ValueError(f"Unexpected redcap response (expected list), got: {type(data)}")
        
        returned_instances = sorted({
            str(entry.get("redcap_repeat_instance", entry.get("repeat_instance")))
            for entry in data
            if entry.get("redcap_repeat_instance", entry.get("repeat_instance")) is not None
        })
        
        logger.info(
            "REDCap: filtering event=%s by repeat_instance=%r; response instances=%s",
            event_name,
            repeat_instance,
            returned_instances,
        )
        
        out: Dict[str, Any] = {}
        matched_entries = 0
        for entry in data:
            entry_repeat_instance = entry.get(
                "redcap_repeat_instance",
                entry.get("repeat_instance")
            )
            if repeat_instance is not None and str(entry_repeat_instance or "") != str(repeat_instance):
                continue
            
            matched_entries += 1
            field_name = entry.get("field_name")
            value = entry.get("value")
            if field_name:
                out[field_name] = value
            
        logger.info(
            "REDCap: exported record %s for event %s, repeat_instance=%r, with %d fields from %d entries",
            record_id,
            event_name,
            repeat_instance,
            len(out),
            matched_entries
        )
        
        return out
        
    def list_event(self)->Any:
        """
        List events from REDCap.
        Returns:
            Any: The list of events from REDCap.
        """
        payload = {
            "token": self.api_token,
            "content": "event",
            "format": "json",
            "returnFormat": "json",
        }
        
        redcap_request = self.session.post(
            self.api_url,
            data = payload,
            timeout = self.timeout
        )
        
        redcap_request.raise_for_status()
        return redcap_request.json()
    