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
    Fetch FPL data using multiple proxy methods
    """
    print("Attempting to fetch FPL data using proxy methods...")
    
    # Try different approaches
    methods = [
        ("Direct API with session", get_fpl_direct_session),
        ("CORS proxy", get_fpl_via_cors_proxy),
        ("Alternative headers", get_fpl_alternative_headers)
    ]
    
    for method_name, method_func in methods:
        try:
            print(f"Trying {method_name}...")
            data = method_func()
            if data and 'elements' in data:
                players_count = len(data.get('elements', []))
                print(f"Success with {method_name}: {players_count} players")
                return data
        except Exception as e:
            print(f"{method_name} failed: {e}")
            continue
    
    raise Exception("All FPL data fetching methods failed")

def get_fpl_direct_session() -> Dict[str, Any]:
    """Direct session method"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-GB,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    try:
        # Get main page first
        session.get('https://fantasy.premierleague.com/', timeout=10)
        time.sleep(1)
        
        # Get API data
        response = session.get('https://fantasy.premierleague.com/api/bootstrap-static/', timeout=15)
        response.raise_for_status()
        return response.json()
    finally:
        session.close()

def get_fpl_via_cors_proxy() -> Dict[str, Any]:
    """Try using CORS proxy"""
    proxy_urls = [
        "https://api.allorigins.win/get?url=",
        "https://cors-anywhere.herokuapp.com/",
        "https://thingproxy.freeboard.io/fetch/"
    ]
    
    target_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    
    for proxy in proxy_urls:
        try:
            if "allorigins" in proxy:
                full_url = f"{proxy}{requests.utils.quote(target_url)}"
                response = requests.get(full_url, timeout=15)
                response.raise_for_status()
                data = response.json()
                return json.loads(data['contents'])
            else:
                full_url = f"{proxy}{target_url}"
                response = requests.get(full_url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                })
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Proxy {proxy} failed: {e}")
            continue
    
    raise Exception("All proxy methods failed")

def get_fpl_alternative_headers() -> Dict[str, Any]:
    """Try with different headers"""
    headers_list = [
        {
            'User-Agent': 'FPL-Bot/1.0',
            'Accept': 'application/json',
        },
        {
            'User-Agent': 'curl/7.68.0',
            'Accept': '*/*',
        },
        {
            'User-Agent': 'Python-requests/2.28.0',
            'Accept': 'application/json',
        }
    ]
    
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    
    for headers in headers_list:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Headers {headers['User-Agent']} failed: {e}")
            continue
    
    raise Exception("All header methods failed")

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
                
                # Debug: Show what's actually in the file
                print(f"File loaded successfully. Type: {type(data)}")
                
                if isinstance(data, list):
                    print(f"Data is a list with {len(data)} items")
                    if len(data) > 0:
                        print(f"First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not a dict'}")
                        
                    # Convert your format to FPL API format
                    print("Converting custom format to FPL API format...")
                    
                    # Extract unique teams
                    teams = []
                    team_names = set()
                    team_id_map = {}
                    
                    for i, player in enumerate(data):
                        team_name = player.get('team', 'Unknown')
                        if team_name not in team_names:
                            team_id = len(teams) + 1
                            teams.append({
                                "id": team_id,
                                "name": team_name,
                                "short_name": team_name[:3].upper()
                            })
                            team_names.add(team_name)
                            team_id_map[team_name] = team_id
                    
                    # Position mapping
                    position_map = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
                    
                    # Convert players to FPL format
                    elements = []
                    for player in data:
                        elements.append({
                            "id": player.get("id", 0),
                            "web_name": player.get("web_name", player.get("name", "Unknown")),
                            "first_name": player.get("first_name", ""),
                            "second_name": player.get("second_name", ""),
                            "element_type": position_map.get(player.get("position", "MID"), 3),
                            "team": team_id_map.get(player.get("team", "Unknown"), 1),
                            "now_cost": int(float(player.get("price", 5.0)) * 10),  # Convert to FPL format (£5.5 -> 55)
                            "ep_next": float(player.get("expected_points", 0)),
                            "total_points": player.get("total_points", 0),
                            "status": player.get("status", "a"),
                            "selected_by_percent": player.get("ownership_percentage", "0"),
                            "chance_of_playing_next_round": player.get("chance_of_playing_this_round", 100),
                            "form": player.get("form", "0.0"),
                            "points_per_game": player.get("points_per_game", "0.0"),
                            "goals_scored": player.get("goals_scored", 0),
                            "assists": player.get("assists", 0),
                            "clean_sheets": player.get("clean_sheets", 0),
                            "goals_conceded": player.get("goals_conceded", 0),
                            "saves": player.get("saves", 0),
                            "bonus": player.get("bonus", 0)
                        })
                    
                    # Create FPL API format
                    normalized_data = {
                        "elements": elements,
                        "teams": teams,
                        "element_types": [
                            {"id": 1, "singular_name": "Goalkeeper"},
                            {"id": 2, "singular_name": "Defender"},
                            {"id": 3, "singular_name": "Midfielder"}, 
                            {"id": 4, "singular_name": "Forward"}
                        ],
                        "fixtures": data.get("fixtures", [])
                    
                    # Add some dummy fixtures if none exist (needed for optimizer)
                    if not normalized_data["fixtures"]:
                        normalized_data["fixtures"] = [
                            {"id": i+1, "team_h": (i % len(teams)) + 1, "team_a": ((i+1) % len(teams)) + 1, 
                             "event": 1, "finished": False}
                            for i in range(min(10, len(teams)//2))  # Create some dummy fixtures
                        ]
                    }
                    
                    players_count = len(elements)
                    teams_count = len(teams)
                    print(f"Successfully converted to FPL format: {players_count} players, {teams_count} teams")
                    return normalized_data
                    
                elif isinstance(data, dict):
                    print(f"Data structure details:")
                    for key in data.keys():
                        if isinstance(data[key], list):
                            print(f"  {key}: list with {len(data[key])} items")
                        else:
                            print(f"  {key}: {type(data[key])}")
                
                    # Validate that it's FPL data - be more flexible
                    if 'elements' in data or 'players' in data:
                        # Handle different possible formats
                        players = data.get('elements', data.get('players', []))
                        teams = data.get('teams', [])
                        
                        if players and teams:
                            players_count = len(players)
                            teams_count = len(teams)
                            print(f"Successfully loaded FPL data from file: {players_count} players, {teams_count} teams")
                            
                            # Normalize format if needed
                            normalized_data = {
                                'elements': players,
                                'teams': teams,
                                'element_types': data.get('element_types', [
                                    {"id": 1, "singular_name": "Goalkeeper"},
                                    {"id": 2, "singular_name": "Defender"}, 
                                    {"id": 3, "singular_name": "Midfielder"},
                                    {"id": 4, "singular_name": "Forward"}
                                ]),
                                'fixtures': data.get('fixtures', [])
                            }
                            return normalized_data
                        else:
                            print(f"File has dict structure but missing player/team data")
                    else:
                        print(f"File {file_path} doesn't contain valid FPL data structure")
                        print(f"Available keys: {list(data.keys())}")
                else:
                    print(f"Data is type: {type(data)}")
                    
                    
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
            # Goalkeepers (budget options)
            {"id": 1, "web_name": "Alisson", "element_type": 1, "team": 1, "now_cost": 55, "ep_next": 5.2, "status": "a", "selected_by_percent": "15.0", "chance_of_playing_next_round": 100},
            {"id": 2, "web_name": "Pickford", "element_type": 1, "team": 2, "now_cost": 45, "ep_next": 4.2, "status": "a", "selected_by_percent": "8.5", "chance_of_playing_next_round": 100},
            
            # Defenders (mix of premium and budget)
            {"id": 3, "web_name": "Alexander-Arnold", "element_type": 2, "team": 1, "now_cost": 70, "ep_next": 6.1, "status": "a", "selected_by_percent": "22.0", "chance_of_playing_next_round": 100},
            {"id": 4, "web_name": "Robertson", "element_type": 2, "team": 1, "now_cost": 60, "ep_next": 5.5, "status": "a", "selected_by_percent": "18.0", "chance_of_playing_next_round": 100},
            {"id": 5, "web_name": "Stones", "element_type": 2, "team": 3, "now_cost": 45, "ep_next": 4.2, "status": "a", "selected_by_percent": "12.0", "chance_of_playing_next_round": 100},
            {"id": 6, "web_name": "Budget Defender 1", "element_type": 2, "team": 4, "now_cost": 40, "ep_next": 3.8, "status": "a", "selected_by_percent": "16.0", "chance_of_playing_next_round": 100},
            {"id": 7, "web_name": "Budget Defender 2", "element_type": 2, "team": 5, "now_cost": 40, "ep_next": 3.5, "status": "a", "selected_by_percent": "9.0", "chance_of_playing_next_round": 100},
            
            # Midfielders (mix of premium and budget)
            {"id": 8, "web_name": "Salah", "element_type": 3, "team": 1, "now_cost": 130, "ep_next": 8.5, "status": "a", "selected_by_percent": "45.0", "chance_of_playing_next_round": 100},
            {"id": 9, "web_name": "De Bruyne", "element_type": 3, "team": 3, "now_cost": 125, "ep_next": 8.2, "status": "a", "selected_by_percent": "38.0", "chance_of_playing_next_round": 100},
            {"id": 10, "web_name": "Saka", "element_type": 3, "team": 7, "now_cost": 80, "ep_next": 6.1, "status": "a", "selected_by_percent": "28.0", "chance_of_playing_next_round": 100},
            {"id": 11, "web_name": "Budget Mid 1", "element_type": 3, "team": 6, "now_cost": 50, "ep_next": 4.2, "status": "a", "selected_by_percent": "15.0", "chance_of_playing_next_round": 100},
            {"id": 12, "web_name": "Budget Mid 2", "element_type": 3, "team": 8, "now_cost": 45, "ep_next": 3.8, "status": "a", "selected_by_percent": "12.0", "chance_of_playing_next_round": 100},
            
            # Forwards (mix of premium and budget)
            {"id": 13, "web_name": "Haaland", "element_type": 4, "team": 3, "now_cost": 150, "ep_next": 9.2, "status": "a", "selected_by_percent": "55.0", "chance_of_playing_next_round": 100},
            {"id": 14, "web_name": "Watkins", "element_type": 4, "team": 9, "now_cost": 75, "ep_next": 6.0, "status": "a", "selected_by_percent": "20.0", "chance_of_playing_next_round": 100},
            {"id": 15, "web_name": "Budget Forward", "element_type": 4, "team": 4, "now_cost": 45, "ep_next": 3.5, "status": "a", "selected_by_percent": "8.0", "chance_of_playing_next_round": 100},
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