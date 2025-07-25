import json
import os
from typing import Dict, Any

def get_fpl_data() -> Dict[str, Any]:
    """
    Load FPL data from local fpl_data.json file
    """
    # Try different possible locations for the JSON file
    possible_paths = [
        "fpl_data.json",                    # Same directory as main.py
        "../fpl_data.json",                 # Parent directory
        "/opt/render/project/src/fpl_data.json",  # Render root
        os.path.join(os.path.dirname(__file__), "..", "fpl_data.json"),  # Relative to app folder
    ]
    
    print("Looking for fpl_data.json file...")
    
    for file_path in possible_paths:
        print(f"Checking: {file_path}")
        if os.path.exists(file_path):
            try:
                print(f"Found fpl_data.json at: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate that it's FPL data
                if 'elements' in data and 'teams' in data:
                    players_count = len(data.get('elements', []))
                    teams_count = len(data.get('teams', []))
                    print(f"Loaded FPL data: {players_count} players, {teams_count} teams")
                    return data
                else:
                    print(f"File {file_path} doesn't contain valid FPL data structure")
                    
            except json.JSONDecodeError as e:
                print(f"JSON decode error in {file_path}: {e}")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    # If no file found, show debug info
    print("=== DEBUG: File system info ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"__file__ location: {__file__ if '__file__' in globals() else 'Not available'}")
    print(f"Directory of this file: {os.path.dirname(__file__) if '__file__' in globals() else 'Not available'}")
    
    # List files in current directory
    try:
        current_files = os.listdir('.')
        print(f"Files in current directory: {current_files}")
    except Exception as e:
        print(f"Can't list current directory: {e}")
    
    # List files in parent directory
    try:
        parent_files = os.listdir('..')
        print(f"Files in parent directory: {parent_files}")
    except Exception as e:
        print(f"Can't list parent directory: {e}")
    
    raise FileNotFoundError(
        "Could not find fpl_data.json file. "
        "Please ensure the file is uploaded to your repository. "
        f"Searched in: {possible_paths}"
    )

# Backup function using sample data if file not found
def get_sample_fpl_data() -> Dict[str, Any]:
    """
    Return minimal sample FPL data structure for testing
    """
    return {
        "elements": [
            {
                "id": 1,
                "web_name": "Sample Player 1",
                "element_type": 1,
                "team": 1,
                "now_cost": 45,
                "ep_next": 5.2,
                "status": "a",
                "selected_by_percent": "15.0",
                "chance_of_playing_next_round": 100
            },
            {
                "id": 2, 
                "web_name": "Sample Player 2",
                "element_type": 2,
                "team": 2,
                "now_cost": 50,
                "ep_next": 4.8,
                "status": "a",
                "selected_by_percent": "8.5",
                "chance_of_playing_next_round": 100
            }
        ],
        "teams": [
            {"id": 1, "name": "Sample Team 1", "short_name": "SAM1"},
            {"id": 2, "name": "Sample Team 2", "short_name": "SAM2"}
        ],
        "element_types": [
            {"id": 1, "singular_name": "Goalkeeper"},
            {"id": 2, "singular_name": "Defender"}
        ],
        "fixtures": []
    }

# Function that tries real data first, then falls back to sample
def get_fpl_data_with_fallback() -> Dict[str, Any]:
    """
    Try to get real FPL data, fall back to sample data if not available
    """
    try:
        return get_fpl_data()
    except FileNotFoundError:
        print("Real FPL data not found, using sample data for testing")
        return get_sample_fpl_data()