from typing import Any, Dict, Optional
import logging
from integracao_embrace.redcap_client import RedcapClient


logger = logging.getLogger(__name__)

def get_initials_from_name(full_name: str) -> str:
    """Extract initials from a full name.

    Args:
        full_name (str): The full name (e.g., "Luana Batista Fernandes").

    Returns:
        str: The initials in uppercase (e.g., "LBF"), or "" if full_name is empty.
    """
    tokens = full_name.strip().split()
    return "".join(token[0].upper() for token in tokens if token)

def get_date_from_redcap(
    redcap_payload: Dict[str, Any],
    check_field: str,
    date_field: str,
    
) -> Optional[str]:
    """Get a date from a REDCap payload if certain conditions are met.

    Args:
        redcap_payload (Dict[str, Any]): The REDCap payload containing the data.
        check_field (str): The field to check for a specific value.
        date_field (str): The field containing the date to retrieve.
    
    Returns:
        Optional[str]: The date as a string if conditions are met, otherwise None.
    """
    if date_field in redcap_payload and redcap_payload.get(date_field):
        check_value = str(redcap_payload.get(check_field, "")).strip().lower()
        if check_field != date_field and check_value in ("", "not done"):
            logger.warning(
                "Date exists (%s) but check field %s indicates not done (value = %r). Skipping...",
                date_field,
                check_field,
                check_value
            )
            return None
        return str(redcap_payload[date_field]).strip()
    return None