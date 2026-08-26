from __future__ import annotations
from typing import Dict, Optional
from integracao_embrace.config import config
import os
import dotenv

dotenv.load_dotenv(override=True)

def load_arm_mapping() -> Dict[str, int]:
    
    raw = config.ARM_MAPPING
    mapping: Dict[str, int] = {}
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        key, val = pair.rsplit(":", 1)
        mapping[key.strip().lower()] = int(val.strip())
    return mapping