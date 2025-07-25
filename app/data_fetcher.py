import requests
import pandas as pd
import json
import numpy as np
from collections import defaultdict
import logging
import time

# Konfigurera logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_and_save_fpl_data(output_path='fpl_data.json', retry_attempts=3, timeout=30):
    """
    Hämtar data från Fantasy Premier League API och sparar den till 'fpl_data.json'.
    Inkluderar förbättrad felhantering, retry-logik och utökad information om nästa match.
    
    Args:
        output_path (str): Sökväg för output-filen
        retry_attempts (int): Antal retry-försök vid nätverksfel
        timeout (int): Timeout för API-anrop i sekunder
    
    Returns:
        dict: Status och information om operationen
    """
    FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
    FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"

    def make_request_with_retry(url, attempts=retry_attempts):
        """Gör API-anrop med retry-logik."""
        for attempt in range(attempts):
            try:
                logger.info(f"Hämtar data från {url} (försök {attempt + 1}/{attempts})")
                response = requests.get(url, verify=False, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout för {url} - försök {attempt + 1}")
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
            except requests.exceptions.RequestException as e:
                logger.warning