import requests
import pandas as pd
import json
import numpy as np

def fetch_and_save_fpl_data():
    """
    Hämtar data från Fantasy Premier League API och sparar den till 'fpl_data.json'.
    Inkluderar utökade parametrar för mer detaljerad optimering och visning.
    """
    FPL_API_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

    try:
        # Lade till verify=False för att kringgå SSL-certifikatverifieringsfel.
        # VARNING: Detta rekommenderas INTE för produktionsmiljöer då det kan vara en säkerhetsrisk.
        # Det bör endast användas för lokal utveckling/testning om du stöter på SSL-problem.
        response = requests.get(FPL_API_URL, verify=False)
        response.raise_for_status()  # Kasta ett fel för dåliga statuskoder (4xx eller 5xx)
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Fel vid hämtning av FPL-data: {e}")
        return {"error": f"Kunde inte hämta data från FPL API: {e}"}

    # Extrahera element (spelare), elementtyper (positioner) och lag
    elements = pd.DataFrame(data['elements'])
    element_types = pd.DataFrame(data['element_types'])
    teams = pd.DataFrame(data['teams'])

    # Mappa positioner (element_type_id till namn)
    pos_map = dict(zip(element_types['id'], element_types['singular_name_short']))
    elements['position'] = elements['element_type'].map(pos_map)

    # Mappa lag (team_id till namn)
    team_map = dict(zip(teams['id'], teams['name']))
    elements['team'] = elements['team'].map(team_map)

    # Välj och döp om relevanta kolumner för din fpl_data.json
    # Konvertera priser från pence till miljoner pund (t.ex. 45 -> 4.5)
    # FPL API ger pris i 10-delar av pund, så 45 betyder 4.5m.
    elements['price'] = elements['now_cost'] / 10.0

    # Välj de datapunkter som är relevanta för din optimerare och hemsida
    # Lägger till de nya fält som diskuterats:
    processed_df = elements[[
        'id', 'first_name', 'second_name', 'web_name', 'team', 'position', 'price',
        'selected_by_percent', # Används för 'ownership_percentage'
        'form',
        'total_points',
        'points_per_game',
        'value_form',
        'goals_scored',
        'assists',
        'clean_sheets',
        'goals_conceded',
        'saves',
        'bonus',
        'ict_index',
        'status', # Skadestatus (t.ex. 'a', 'd', 'i', 's')
        'chance_of_playing_this_round', # Procentuell chans att spela nästa omgång
        'news', # Kort nyhetsmeddelande om spelaren (t.ex. skada)
        'cost_change_event', # Prisförändring under aktuell omgång
        'cost_change_start', # Prisförändring sedan säsongsstart
        'transfers_in_event', # Antal in-transfers aktuell omgång
        'transfers_out_event', # Antal ut-transfers aktuell omgång
        'ep_this', # FPL:s egna förväntade poäng för denna omgång (kan användas som 'expected_points')
        'ep_next' # FPL:s egna förväntade poäng för nästa omgång (kan användas som 'expected_points')
    ]].copy()

    # Skapa 'name' kolumn från 'web_name' för enkelhetens skull
    processed_df['name'] = processed_df['web_name']

    # Döp om 'selected_by_percent' till 'ownership_percentage' för att matcha optimeringskoden
    processed_df.rename(columns={'selected_by_percent': 'ownership_percentage'}, inplace=True)
    
    # Döp om 'ep_this' eller 'ep_next' till 'expected_points'
    # Prioriterar 'ep_next' om den finns, annars 'ep_this'
    if 'ep_next' in processed_df.columns and not processed_df['ep_next'].isnull().all():
        processed_df['expected_points'] = processed_df['ep_next']
    elif 'ep_this' in processed_df.columns and not processed_df['ep_this'].isnull().all():
        processed_df['expected_points'] = processed_df['ep_this']
    else:
        # Fallback om varken ep_this eller ep_next finns eller är tomma
        print("Varning: 'ep_this' eller 'ep_next' saknas eller är tomma. 'expected_points' kommer att vara NaN.")
        processed_df['expected_points'] = np.nan # Sätt till NaN om ingen data finns

    # Hantera saknade 'chance_of_playing_this_round' värden (kan vara None i API)
    # Konvertera till numerisk typ först, fyll sedan i NaN, och konvertera till int.
    processed_df['chance_of_playing_this_round'] = pd.to_numeric(
        processed_df['chance_of_playing_this_round'], errors='coerce'
    ).fillna(100).astype(int)

    # Ta bort temporära 'ep_this' och 'ep_next' om de inte är den primära 'expected_points'
    processed_df.drop(columns=['ep_this', 'ep_next'], errors='ignore', inplace=True)

    # Spara den bearbetade datan till en JSON-fil
    output_path = 'fpl_data.json'
    processed_df.to_json(output_path, orient='records', indent=4)

    print(f"FPL-data hämtad och sparad till '{output_path}' med {len(processed_df)} spelare.")
    return {"message": f"FPL-data hämtad och sparad till '{output_path}'.", "player_count": len(processed_df)}

# Exempel på hur du kan anropa funktionen:
if __name__ == '__main__':
    fetch_and_save_fpl_data()
