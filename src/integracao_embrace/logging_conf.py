import logging
from pathlib import Path

def setup_logging(log_path: str | None="sync_log.log") -> None:
    """
        Setup logging configuration.

        Args:
            log_path (str | None, optional): Path to the log file. Defaults to "sync_log.log".
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_path:
        handlers.append(logging.FileHandler(Path(log_path)))
    
    logging.basicConfig(
        level=logging.INFO,
        format = "%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers
    )