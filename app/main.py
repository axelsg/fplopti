from flask import Flask, request, jsonify
from flask_cors import CORS
# VIKTIGT: Importera rätt funktion från din logik-fil!
from optimizer_logic import run_fpl_optimizer

app = Flask(__name__)
CORS(app)

@app.route('/optimize-team', methods=['POST'])
def optimize_team_endpoint():
    try:
        params = request.get_json()
        if not params:
            params = {}

        # VIKTIGT: Anropa rätt funktion med parametrarna!
        optimal_team_data = run_fpl_optimizer(
            strategy=params.get('strategy', 'best_15'),
            defensive_weight=params.get('defensive_weight'),
            offensive_weight=params.get('offensive_weight'),
            differential_factor=params.get('differential_factor'),
            min_cheap_players=params.get('min_cheap_players'),
            cheap_player_price_threshold=params.get('cheap_player_price_threshold')
        )

        return jsonify(optimal_team_data)

    except Exception as e:
        # Lägg till traceback för enklare felsökning i dina loggar
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)