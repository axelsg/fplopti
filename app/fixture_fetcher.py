import requests
import json
from pathlib import Path

# Stänger av varningen som visas när verify=False används.
# Detta är valfritt men gör terminalen renare.
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"

def fetch_all_fixtures():
    """
    Hämtar all matchdata (fixtures) från FPL:s officiella API.
    """
    print("Försöker hämta all matchdata från FPL API...")
    try:
        # LÖSNING: verify=False har lagts till för att kringgå SSL-verifieringsfel
        # på företagsnätverk.
        response = requests.get(FIXTURES_URL, verify=False, timeout=10)
        
        response.raise_for_status()
        
        fixtures_data = response.json()
        
        print(f"Hämtade {len(fixtures_data)} matcher framgångsrikt.")
        return fixtures_data
        
    except requests.exceptions.RequestException as e:
        print(f"Ett fel uppstod vid hämtning av matchdata: {e}")
        return None

def save_data_to_json(data, filepath="data/fixtures.json"):
    """
    Sparar en dictionary eller lista till en JSON-fil.
    """
    if not data:
        print("Ingen data att spara.")
        return
        
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data har sparats till {filepath}")
        
    except (IOError, TypeError) as e:
        print(f"Kunde inte spara data till fil: {e}")


if __name__ == '__main__':
    all_fixtures = fetch_all_fixtures()

    if all_fixtures:
        print("\n--- Exempel på första match i listan ---")
        print(json.dumps(all_fixtures[0], indent=2))
        
        save_data_to_json(all_fixtures)