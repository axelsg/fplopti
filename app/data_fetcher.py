# app/data_fetcher.py

import requests
import json
import warnings

FPL_API_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
OUTPUT_FILENAME = "fpl_data.json" # Filen kommer att sparas i rotmappen

def update_fpl_data():
    """Hämtar den senaste FPL-datan och sparar den till en JSON-fil."""
    try:
        print("Startar datahämtning från FPL API...")
        warnings.filterwarnings('ignore', message='Unverified HTTPS request')
        response = requests.get(FPL_API_URL, verify=False)
        response.raise_for_status()
        data = response.json()

        teams_map = {team['id']: team['name'] for team in data['teams']}
        positions_map = {pos['id']: pos['singular_name_short'] for pos in data['element_types']}

        processed_players = []
        for player in data['elements']:
            if player['status'] != 'a':
                continue
            processed_players.append({
                'id': player['id'],
                'name': player['web_name'],
                'team': teams_map[player['team']],
                'position': positions_map[player['element_type']],
                'price': player['now_cost'] / 10.0,
                'expected_points': float(player['ep_next']),
                'total_points': player['total_points'],
            })
        
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(processed_players, f, ensure_ascii=False, indent=4)
        
        print(f"Data sparad! {len(processed_players)} spelare bearbetade.")
        return {"status": "success", "players_processed": len(processed_players)}

    except Exception as e:
        print(f"Ett fel uppstod under datahämtning: {e}")
        return {"status": "error", "message": str(e)}