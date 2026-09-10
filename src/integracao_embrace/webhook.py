from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import BackgroundTasks, FastAPI, Form, Response, status
from dotenv import load_dotenv
from integracao_embrace.config import Settings
from integracao_embrace.dispatch import dispatch_event
from integracao_embrace.logging_conf import setup_logging
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient
from datetime import datetime

import logging
import time

#1. Logging
logger = logging.getLogger(__name__)

#2. Global Objects (initialized in lifespan of the app)

_settings: Settings | None = None
_redcap: RedcapClient | None = None
_polotrial: PoloTrialClient | None = None


#3. Context Manager for Lifespan of the App
@asynccontextmanager
async def lifespan(app: FastAPI):
    
    global _settings, _redcap, _polotrial
    
    #3.1. Load Environment Variables
    load_dotenv(override=True)
    setup_logging()
    
    _settings = Settings.from_env()
    _redcap = RedcapClient(_settings.redcap_api_url, _settings.redcap_api_key)
    _polotrial = PoloTrialClient(
        _settings.polotrial_api_url,
        _settings.polotrial_username,
        _settings.polotrial_password
    )
    logger.info("Webhook initialized for protocol %s", _settings.protocol_nickname)
    yield # Control is returned to the FastAPI app, and will resume here on shutdown
    logger.info("Shutting down webhooks for protocol %s", _settings.protocol_nickname)

#4. FastAPI App Initialization
app = FastAPI(
    title = "Embrace integration - REDCap DET <-> PoloTrial webhook",
    version = "0.0.1",
    lifespan=lifespan
)

#5. Health check endpoint
@app.get("/embrace_det_health")
async def heatlth(response: Response):
    """
    Health check endpoint for the Embrace Webhook service.
    Returns a JSON response with the status of the service and its dependencies.
    
    Args:
        response (Response): The FastAPI response object.

    Returns:
        dict: A JSON response with the status of the service and its dependencies.
        
    Steps:
        1. Check the status of the external API (PoloTrial).
        2. Set the response status code based on the external API status.
        3. Return a JSON response with the overall status, version, description, and checks for dependencies.
    """
    
    external_api_status = "warn"
    if external_api_status == 'fail':
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        general_status = "fail"
    elif external_api_status == 'warn':
        response.status_code = status.HTTP_200_OK
        general_status = "warn"
    else:
        response.status_code = status.HTTP_200_OK
        general_status = "ok"
    return {
        "status": general_status,
        "version": "0.0.1",
        'description': 'Health check for the Embrace Webhook service',
        "checks": {
            "database": [
                {
                    'componentType': 'datastore',
                    'status': 'pass',
                    'time': datetime.now().isoformat(),
                }
            ],
            "external_api": [
                {
                    'componentType': 'http',
                    'status': external_api_status,
                    'time': datetime.now().isoformat(),
                }
            ]
        }
    }


#6. Endpoint to receive webhook events from REDCap DET
@app.post("/redcap-embrace-det", status_code=status.HTTP_200_OK)
async def redcap_embrace_det(
    
    background_tasks: BackgroundTasks,
    
    # data sended by redcap (x-www-form-urlencoded)
    project_id: str = Form(...),
    username: str = Form(default=""),
    instrument: str = Form(default=""),
    record: str = Form(...),
    redcap_event_name: str = Form(default=""),
    redcap_data_acess_group: str = Form(default=""),
    redcap_repeat_instance: Optional[str] = Form(default=None),
    redcap_repeat_instrument: Optional[str] = Form(default=None),
    redcap_url: str=Form(default=""),
    project_url: str=Form(default="") 
):
    """
    Endpoint to receive webhook events from REDCap DET.
    
    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks manager.
        project_id (str): The ID of the REDCap project.
        username (str): The username of the user who triggered the event.
        instrument (str): The instrument associated with the event.
        record (str): The record ID associated with the event.
        redcap_event_name (str): The name of the REDCap event.
        redcap_data_acess_group (str): The data access group associated with the event.
        redcap_repeat_instance (Optional[str]): The repeat instance associated with the event, if any.
        redcap_repeat_instrument (Optional[str]): The repeat instrument associated with the event, if any.
        redcap_url (str): The URL of the REDCap instance.
        project_url (str): The URL of the REDCap project.
    
    Returns:
        dict: A JSON response indicating the status of the webhook event processing.
        
    Steps:
        1. Validate required fields (redcap_event_name and record).
        2. Log the received webhook event details.
        3. Schedule a background task to process the event using the _run_sync function.
    4. Return a success response indicating that the webhook event has been received and processing has been scheduled.
    """
    #6.1. basic filter
    if not redcap_event_name or not record:
        logger.warning(
            "DET ignored due to missing required fields: redcap_event_name=%s, record=%s",
            redcap_event_name, 
            record
        )
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Missing required fields: redcap_event_name and record are required.")
    
    logger.info(
        "Received webhook from REDCap DET: project_id=%s, username=%s, instrument=%s, record=%s, redcap_event_name=%s, redcap_data_acess_group=%s, redcap_repeat_instance=%s, redcap_repeat_instrument=%s, redcap_url=%s, project_url=%s",
        project_id,
        username,
        instrument,
        record,
        redcap_event_name,
        redcap_data_acess_group,
        redcap_repeat_instance,
        redcap_repeat_instrument,
        redcap_url,
        project_url
    )
    
    #6.2. Schedule a heavy task to process the event in the background
    background_tasks.add_task(
        _run_sync,
        record_id=record,
        event_name=redcap_event_name,
        instrument=instrument,
        repeat_instance = redcap_repeat_instance,
    )
    
    return {'status': 'success', 'message': 'Webhook event received and processing scheduled.'}

#7. Background worker function to process the webhook event
def _run_sync(
    *,
    record_id: str,
    event_name: str,
    instrument: str = "",
    repeat_instance: str | None = None
) -> None:
    """Background worker function to process the webhook event.
    Args:
        record_id (str): The record ID associated with the event.
        event_name (str): The name of the REDCap event.
        instrument (str): The REDCap instrument (form) that triggered the DET.
        repeat_instance (Optional[str]): The repeat instance associated with the event, if any.
    
    Raises:
        AssertionError: If the global clients (_redcap, _polotrial, _settings) are not initialized.
        Exception: If an error occurs during event dispatching.
    
    Steps:
        1. Assert that the global clients (_redcap, _polotrial, _settings) are initialized.
        2. Attempt to dispatch the event using the dispatch_event function.
        3. Log the success or failure of the event dispatching.
        4. If an exception occurs, log the error details.
        
    """
    
    assert _redcap is not None and _polotrial is not None and _settings is not None
    
    try:
        dispatch_event(
            record_id=record_id,
            event_name=event_name,
            redcap=_redcap,
            polotrial=_polotrial,
            protocol_nickname=_settings.protocol_nickname,
            instrument=instrument,
            repeat_instance=repeat_instance
        )
        logger.info("Successfully dispatched event: record_id=%s, event_name=%s, repeat_instance=%s", record_id, event_name, repeat_instance)
    except Exception as e:
        logger.exception("Error dispatching event: record_id=%s, event_name=%s, repeat_instance=%s, error=%s", record_id, event_name, repeat_instance, str(e))
    