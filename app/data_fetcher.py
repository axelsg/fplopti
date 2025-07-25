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
    
    # Headers to mimic a real browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
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

def get_fpl_data_with_session() -> Dict[str, Any]:
    """
    Alternative method using requests session with more browser-like behavior
    """
    cache_file = "fpl_cache.json"
    cache_duration = 3600  # 1 hour in seconds
    
    # Check cache first
    if os.path.exists(cache_file):
        try:
            cache_age = time.time() - os.path.getmtime(cache_file)
            if cache_age < cache_duration:
                with open(cache_file, 'r') as f:
                    print(f"Using cached data (age: {int(cache_age)}s)")
                    return json.load(f)
        except Exception as e:
            print(f"Cache read error: {e}")
    
    print("Fetching fresh FPL data with session...")
    
    # Create session with browser-like behavior
    session = requests.Session()
    
    # Set headers that mimic a real browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    try:
        # First, make a request to the main FPL site to get cookies
        print("Getting FPL homepage for cookies...")
        session.get('https://fantasy.premierleague.com/', timeout=15)
        
        # Small delay to be respectful
        time.sleep(1)
        
        # Now get the API data
        print("Fetching API data...")
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        response = session.get(url, timeout=30)
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
        print(f"Session method failed: {e}")
        # If fresh fetch fails but cache exists, use stale cache
        if os.path.exists(cache_file):
            print("Using stale cache as fallback")
            with open(cache_file, 'r') as f:
                return json.load(f)
        else:
            raise Exception(f"Failed to fetch FPL data: {e}")
    finally:
        session.close()