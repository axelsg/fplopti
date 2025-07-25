import requests
import pandas as pd
import json
import numpy as np
from collections import defaultdict

def fetch_and_save_fpl_data():
    """
    Hämtar data från Fantasy Premier League API och sparar den till 'fpl_data.json'.
    Inkluderar nu utökad information om nästa match för varje spelare.
    """
    FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
    FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"

    # KORRIGERING: Lade till ett kolon ':' i slutet av try-raden.
    try:
        # Steg 1: Hämta grundläggande data (spelare, lag, events)
        bootstrap_response = requests.get(FPL_BOOTSTRAP_URL, verify=False)
        bootstrap_response.raise_for_status()
        bootstrap_data = bootstrap_response.json()

        # Steg 2: Hämta matchdata (fixtures)
        fixtures_response = requests.get(FPL_FIXTURES_URL, verify=False)
        fixtures_response.raise_for_status()
        fixtures_data = fixtures_response.json()

    except requests.exceptions.RequestException as e:
        print(f"Fel vid hämtning av FPL-data: {e}")
        return {"error": f"Kunde inte hämta data från FPL API: {e}"}

    # Bearbeta grundläggande data
    elements = pd.DataFrame(bootstrap_data['elements'])
    element_types = pd.DataFrame(bootstrap_data['element_types'])
    teams = pd.DataFrame(bootstrap_data['teams'])
    
    # **KORRIGERING: Hämta 'events' som en lista, inte en DataFrame.**
    events_list = bootstrap_data.get('events', [])

    # --- NY LOGIK: Hitta nästa omgång och bearbeta matcher ---

    # Hitta nästa gameweek ID
    next_gameweek_id = None
    # **KORRIGERING: Loopa över den korrekta listan.**
    for event in events_list:
        if event.get('is_next'):
            next_gameweek_id = event.get('id')
            break
    
    # Skapa mappning från lag-ID till kortnamn (t.ex. 1 -> 'ARS')
    team_id_to_short_name_map = dict(zip(teams['id'], teams['short_name']))

    # Skapa en mappning för varje lags nästa match
    next_fixtures_map = defaultdict(dict)
    if next_gameweek_id:
        for fixture in fixtures_data:
            if fixture.get('event') == next_gameweek_id:
                home_team_id = fixture.get('team_h')
                away_team_id = fixture.get('team_a')
                
                next_fixtures_map[home_team_id] = {
                    'opponent_short_name': team_id_to_short_name_map.get(away_team_id, 'N/A'),
                    'is_home': True
                }
                next_fixtures_map[away_team_id] = {
                    'opponent_short_name': team_id_to_short_name_map.get(home_team_id, 'N/A'),
                    'is_home': False
                }

    # Lägg till den nya informationen i huvud-DataFrame för spelare
    elements['next_opponent'] = elements['team'].apply(
        lambda team_id: next_fixtures_map.get(team_id, {}).get('opponent_short_name', 'BLANK')
    )
    elements['is_home'] = elements['team'].apply(
        lambda team_id: next_fixtures_map.get(team_id, {}).get('is_home', False)
    )

    # --- BEFINTLIG LOGIK: Bearbeta resten av spelardatan ---

    pos_map = dict(zip(element_types['id'], element_types['singular_name_short']))
    elements['position'] = elements['element_type'].map(pos_map)

    team_map = dict(zip(teams['id'], teams['name']))
    elements['team'] = elements['team'].map(team_map)

    elements['price'] = elements['now_cost'] / 10.0

    processed_df = elements[[
        'id', 'first_name', 'second_name', 'web_name', 'team', 'position', 'price',
        'selected_by_percent', 'form', 'total_points', 'points_per_game',
        'value_form', 'goals_scored', 'assists', 'clean_sheets',
        'goals_conceded', 'saves', 'bonus', 'ict_index', 'status',
        'chance_of_playing_this_round', 'news', 'cost_change_event',
        'cost_change_start', 'transfers_in_event', 'transfers_out_event',
        'ep_this', 'ep_next',
        'next_opponent', 'is_home'
    ]].copy()

    processed_df['name'] = processed_df['web_name']
    processed_df.rename(columns={'selected_by_percent': 'ownership_percentage'}, inplace=True)
    
    if 'ep_next' in processed_df.columns and not processed_df['ep_next'].isnull().all():
        processed_df['expected_points'] = pd.to_numeric(processed_df['ep_next'], errors='coerce').fillna(0)
    elif 'ep_this' in processed_df.columns and not processed_df['ep_this'].isnull().all():
        processed_df['expected_points'] = pd.to_numeric(processed_df['ep_this'], errors='coerce').fillna(0)
    else:
        processed_df['expected_points'] = 0.0

    processed_df['chance_of_playing_this_round'] = pd.to_numeric(
        processed_df['chance_of_playing_this_round'], errors='coerce'
    ).fillna(100).astype(int)

    processed_df.drop(columns=['ep_this', 'ep_next'], errors='ignore', inplace=True)

    output_path = 'fpl_data.json'
    processed_df.to_json(output_path, orient='records', indent=4)

    print(f"FPL-data hämtad och sparad till '{output_path}' med {len(processed_df)} spelare.")
    return {"message": f"FPL-data hämtad och sparad till '{output_path}'.", "player_count": len(processed_df)}

if __name__ == '__main__':
    fetch_and_save_fpl_data()
