from flask import Flask, request, jsonify, json
from flask_cors import CORS
from optimizer_logic import run_fpl_optimizer

app = Flask(__name__)
CORS(app)

# --- NY FELSÖKNINGS-ENDPOINT ---
@app.route('/debug-data')
def debug_data():
    """
    Denna endpoint läser fpl_data.json på servern och returnerar
    datan för den första spelaren. Används för att verifiera att
    filen har uppdaterats korrekt.
    """
    try:
        # Försök att öppna filen från roten av projektet
        with open('fpl_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Returnera bara den första spelaren för att hålla det enkelt
        first_player = data[0] if data else {}
        return jsonify(first_player)
        
    except FileNotFoundError:
        return jsonify({"error": "fpl_data.json hittades inte i projektets rot."})
    except Exception as e:
        return jsonify({"error": str(e)})


# --- DIN BEFINTLIGA OPTIMERINGS-ENDPOINT ---
@app.route('/optimize-team', methods=['POST'])
def optimize_team_endpoint():
    try:
        params = request.get_json()
        if not params:
            params = {}

        kwargs = {}
        if 'strategy' in params and params['strategy'] is not None:
            kwargs['strategy'] = params['strategy']
        
        optional_params = [
            'defensive_weight', 'offensive_weight', 'differential_factor',
            'min_cheap_players', 'cheap_player_price_threshold'
        ]
        
        for param in optional_params:
            if param in params and params[param] is not None:
                try:
                    if 'weight' in param or 'factor' in param or 'threshold' in param:
                        kwargs[param] = float(params[param])
                    elif 'players' in param:
                        kwargs[param] = int(params[param])
                except (ValueError, TypeError):
                    pass

        optimal_team_data = run_fpl_optimizer(**kwargs)
        return jsonify(optimal_team_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
