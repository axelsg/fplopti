import requests
import json
import os
import time
from typing import Dict, Any

def get_fpl_data() -> Dict[str, Any]:
    """
    Try multiple methods to get FPL data:
    1. Session-based API call (often works better)
    2. Local file fallback
    3. Sample data fallback
    """
    # First try session-based API call
    try:
        return get_fpl_data_with_session()
    except Exception as e:
        print(f"Session-based API call failed: {e}")
        
        # Fall back to local file
        try:
            return get_fpl_data_from_file()
        except Exception as e2:
            print(f"Local file also failed: {e2}")
            
            # Final fallback to sample data
            print("Using sample data as final fallback")
            return get_sample_fpl_data()

def get_fpl_data_with_session() -> Dict[str, Any]:
    """
    Fetch FPL data using requests session with browser-like behavior
    """
    print("Attempting to fetch FPL data using session method...")
    
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
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Referrer': 'https://fantasy.premierleague.com/',
    })
    
    try:
        # First, make a request to the main FPL site to establish session
        print("Establishing session with FPL website...")
        main_response = session.get('https://fantasy.premierleague.com/', timeout=15)
        print(f"Main site response status: {main_response.status_code}")
        
        # Small delay to be respectful
        time.sleep(2)
        
        # Now get the API data
        print("Fetching API data...")
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        response = session.get(url, timeout=30)
        
        print(f"API response status: {response.status_code}")
        response.raise_for_status()
        
        data = response.json()
        
        # Validate data
        if 'elements' in data and 'teams' in data:
            players_count = len(data.get('elements', []))
            teams_count = len(data.get('teams', []))
            print(f"Successfully fetched FPL data: {players_count} players, {teams_count} teams")
            return data
        else:
            raise ValueError("Invalid FPL data structure received")
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("Got 403 Forbidden - FPL is blocking server requests")
            raise Exception("FPL API blocked the request (403 Forbidden)")
        else:
            raise Exception(f"HTTP error {e.response.status_code}: {e}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {e}")
        
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response: {e}")
        
    finally:
        session.close()

def get_fpl_data_from_file() -> Dict[str, Any]:
    """
    Load FPL data from local fpl_data.json file
    """
    print("Attempting to load FPL data from local file...")
    
    # Try different possible locations for the JSON file
    possible_paths = [
        "/opt/render/project/src/fpl_data.json",  # Direct path we know exists
        "fpl_data.json",                          # Same directory as main.py
        "../fpl_data.json",                       # Parent directory
        "./fpl_data.json",                        # Current working directory
        os.path.join(os.path.dirname(__file__), "..", "fpl_data.json"),  # Relative to app folder
    ]
    
    for file_path in possible_paths:
        print(f"Checking: {file_path}")
        try:
            if os.path.exists(file_path):
                print(f"File exists, attempting to read: {file_path}")
                
                # Check if file is readable
                if not os.access(file_path, os.R_OK):
                    print(f"File exists but is not readable: {file_path}")
                    continue
                
                # Get file size
                file_size = os.path.getsize(file_path)
                print(f"File size: {file_size} bytes")
                
                if file_size == 0:
                    print(f"File is empty: {file_path}")
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate that it's FPL data
                if 'elements' in data and 'teams' in data:
                    players_count = len(data.get('elements', []))
                    teams_count = len(data.get('teams', []))
                    print(f"Successfully loaded FPL data from file: {players_count} players, {teams_count} teams")
                    return data
                else:
                    print(f"File {file_path} doesn't contain valid FPL data structure")
                    
            else:
                print(f"File does not exist: {file_path}")
                
        except json.JSONDecodeError as e:
            print(f"JSON decode error in {file_path}: {e}")
        except PermissionError as e:
            print(f"Permission error reading {file_path}: {e}")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    raise FileNotFoundError(f"Could not load fpl_data.json from any location. Tried: {possible_paths}")

def get_sample_fpl_data() -> Dict[str, Any]:
    """
    Return sample FPL data structure for testing
    """
    print("Using sample FPL data for testing...")
    return {
        "elements": [
            # Goalkeepers
            {"id": 1, "web_name": "Alisson", "element_type": 1, "team": 1, "now_cost": 55, "ep_next": 5.2, "status": "a", "selected_by_percent": "15.0", "chance_of_playing_next_round": 100},
            {"id": 2, "web_name": "Pickford", "element_type": 1, "team": 2, "now_cost": 50, "ep_next": 4.8, "status": "a", "selected_by_percent": "8.5", "chance_of_playing_next_round": 100},
            
            # Defenders  
            {"id": 3, "web_name": "Alexander-Arnold", "element_type": 2, "team": 1, "now_cost": 70, "ep_next": 6.1, "status": "a", "selected_by_percent": "22.0", "chance_of_playing_next_round": 100},
            {"id": 4, "web_name": "Robertson", "element_type": 2, "team": 1, "now_cost": 60, "ep_next": 5.5, "status": "a", "selected_by_percent": "18.0", "chance_of_playing_next_round": 100},
            {"id": 5, "web_name": "Stones", "element_type": 2, "team": 3, "now_cost": 55, "ep_next": 4.9, "status": "a", "selected_by_percent": "12.0", "chance_of_playing_next_round": 100},
            {"id": 6, "web_name": "Trippier", "element_type": 2, "team": 4, "now_cost": 58, "ep_next": 5.2, "status": "a", "selected_by_percent": "16.0", "chance_of_playing_next_round": 100},
            {"id": 7, "web_name": "Chilwell", "element_type": 2, "team": 5, "now_cost": 52, "ep_next": 4.7, "status": "a", "selected_by_percent": "9.0", "chance_of_playing_next_round": 100},
            
            # Midfielders
            {"id": 8, "web_name": "Salah", "element_type": 3, "team": 1, "now_cost": 130, "ep_next": 8.5, "status": "a", "selected_by_percent": "45.0", "chance_of_playing_next_round": 100},
            {"id": 9, "web_name": "De Bruyne", "element_type": 3, "team": 3, "now_cost": 125, "ep_next": 8.2, "status": "a", "selected_by_percent": "38.0", "chance_of_playing_next_round": 100},
            {"id": 10, "web_name": "Bruno Fernandes", "element_type": 3, "team": 6, "now_cost": 110, "ep_next": 7.8, "status": "a", "selected_by_percent": "32.0", "chance_of_playing_next_round": 100},
            {"id": 11, "web_name": "Saka", "element_type": 3, "team": 7, "now_cost": 95, "ep_next": 7.1, "status": "a", "selected_by_percent": "28.0", "chance_of_playing_next_round": 100},
            {"id": 12, "web_name": "Rice", "element_type": 3, "team": 7, "now_cost": 65, "ep_next": 5.2, "status": "a", "selected_by_percent": "15.0", "chance_of_playing_next_round": 100},
            
            # Forwards
            {"id": 13, "web_name": "Haaland", "element_type": 4, "team": 3, "now_cost": 150, "ep_next": 9.2, "status": "a", "selected_by_percent": "55.0", "chance_of_playing_next_round": 100},
            {"id": 14, "web_name": "Kane", "element_type": 4, "team": 8, "now_cost": 125, "ep_next": 8.1, "status": "a", "selected_by_percent": "35.0", "chance_of_playing_next_round": 100},
            {"id": 15, "web_name": "Watkins", "element_type": 4, "team": 9, "now_cost": 85, "ep_next": 6.5, "status": "a", "selected_by_percent": "20.0", "chance_of_playing_next_round": 100},
        ],
        "teams": [
            {"id": 1, "name": "Liverpool", "short_name": "LIV"},
            {"id": 2, "name": "Everton", "short_name": "EVE"},
            {"id": 3, "name": "Manchester City", "short_name": "MCI"},
            {"id": 4, "name": "Newcastle United", "short_name": "NEW"},
            {"id": 5, "name": "Chelsea", "short_name": "CHE"},
            {"id": 6, "name": "Manchester United", "short_name": "MUN"},
            {"id": 7, "name": "Arsenal", "short_name": "ARS"},
            {"id": 8, "name": "Tottenham Hotspur", "short_name": "TOT"},
            {"id": 9, "name": "Aston Villa", "short_name": "AVL"}
        ],
        "element_types": [
            {"id": 1, "singular_name": "Goalkeeper"},
            {"id": 2, "singular_name": "Defender"},
            {"id": 3, "singular_name": "Midfielder"},
            {"id": 4, "singular_name": "Forward"}
        ],
        "fixtures": [
            {"id": 1, "team_h": 1, "team_a": 2, "event": 1, "finished": False},
            {"id": 2, "team_h": 3, "team_a": 4, "event": 1, "finished": False}
        ]
    }

# Main function that tries all methods
def get_fpl_data_with_fallback() -> Dict[str, Any]:
    """
    Try to get real FPL data, fall back to sample data if not available
    """
    return get_fpl_data()