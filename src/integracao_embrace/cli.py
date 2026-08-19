from __future__ import annotations

import argparse
from dotenv import load_dotenv

from integracao_embrace.config  import Settings
from integracao_embrace.dispatch import dispatch_event
from integracao_embrace.logging_conf import setup_logging
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient


def main() -> None:
    
    load_dotenv(override=True)
    setup_logging()
    
    parse = argparse.ArgumentParser()
    parse.add_argument("--record-id", required=True, type=str, help="Redcap Record ID")
    parse.add_argument("--event", required=True, type=str, help="Redcap Unique Event Name")
    args = parse.parse_args()
    
    settings = Settings.from_env()
    
    
    redcap=RedcapClient(settings.redcap_api_url, settings.redcap_api_key)
    polotrial=PoloTrialClient(settings.polotrial_api_url, settings.polotrial_username, settings.polotrial_password)
    
    dispatch_event(
        record_id = args.record_id,
        event_name = args.event,
        redcap=redcap,
        polotrial=polotrial,
        protocol_nickname=settings.protocol_nickname
    )
    
    if __name__ == "__main__":
        main()