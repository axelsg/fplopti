# ===============================================================
# Fil: main.py
# ===============================================================
from flask import Flask, request, jsonify
from flask_cors import CORS
from optimizer_logic import run_fpl_optimizer

app = Flask(__name__)
CORS(app)

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