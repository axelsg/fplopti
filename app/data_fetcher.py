import requests
import json
import os
import time
from typing import Dict, Any

def get_fpl_data() -> Dict[str, Any]:
    """
    Fetch FPL data with caching to avoid hitting the API too frequently
    """
    cache_file = "fpl_cache.json"
    cache_duration = 3600  # 1 hour in seconds
    
    # Check if cache exists and is fresh
    if os.path.exists(cache_file):
        try:
            cache_age = time.time() - os.path.getmtime(cache_file)
            if cache_age < cache_duration:
                with open(cache_file, 'r') as f:
                    print(f"Using cached data (age: {int(cache_age)}s)")
                    return json.load(f)
        except Exception as e:
            print(f"Cache read error: {e}")
    
    # Fetch fresh data
    print("Fetching fresh FPL data...")
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Save to cache
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            print("Data cached successfully")
        except Exception as e:
            print(f"Cache write error: {e}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        # If fresh fetch fails but cache exists, use stale cache
        if os.path.exists(cache_file):
            print(f"Fetch failed ({e}), using stale cache")
            with open(cache_file, 'r') as f:
                return json.load(f)
        else:
            raise Exception(f"Failed to fetch FPL data: {e}")