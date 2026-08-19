from __future__ import annotations

import logging
import re
import pandas as pd
import os
import dotenv

from datetime import datetime
from typing import Any, Dict, List, Optional
from integracao_embrace.polotrial_client import PoloTrialClient
from integracao_embrace.redcap_client import RedcapClient
from integracao_embrace.mapping.site_code_maps import SITE_CODE_MAPPING
from integracao_embrace.config import config

dotenv.load_dotenv(override=True)

