import logging
from pathlib import Path

def setup_logging(log_path: str | None="sync_log.log") -> None:
    
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_path:
        handlers.append(logging.FileHandler(Path(log_path)))
    
    logging.basicConfig(
        level=logging.INFO,
        format = "%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers
    )