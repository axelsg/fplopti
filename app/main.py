from flask import Flask, request, jsonify
from flask_cors import CORS
from optimizer_logic import run_fpl_optimizer
import logging
import traceback
import os

# Konfigurera logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Konfigurera Flask för produktion
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

@app.route('/health', methods=['GET'])
def health_check():
    """Enkel hälsokontroll för monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "FPL Optimizer API",
        "version": "1.0"
    })

@app.route('/optimize-team', methods=['POST'])
def optimize_team_endpoint():
    """
    Huvud-endpoint för teamoptimering med förbättrad felhantering och validering.
    """
    try:
        # Hämta och validera request data
        params = request.get_json()
        if params is None:
            params = {}
        
        # Logga inkommande request (utan känslig data)
        logger.info(f"Optimering begärd med strategi: {params.get('strategy', 'best_15')}")
        
        # Bygg kwargs för optimizer med validering
        kwargs = {}
        
        # Strategi (required)
        strategy = params.get('strategy', 'best_15')
        valid_strategies = ['best_15', 'best_11_cheap_bench', 'defensive', 'offensive', 'enabling', 'differential']
        if strategy not in valid_strategies:
            return jsonify({
                "error": f"Invalid strategy '{strategy}'. Valid options: {', '.join(valid_strategies)}"
            }), 400
        kwargs['strategy'] = strategy
        
        # Numeriska parametrar med validering
        numeric_params = {
            'defensive_weight': {'min': 1.0, 'max': 3.0, 'default': 1.2},
            'offensive_weight': {'min': 1.0, 'max': 3.0, 'default': 1.2},
            'differential_factor': {'min': 0.0, 'max': 0.2, 'default': 0.05}
        }
        
        for param, config in numeric_params.items():
            if param in params and params[param] is not None:
                try:
                    value = float(params[param])
                    if config['min'] <= value <= config['max']:
                        kwargs[param] = value
                    else:
                        logger.warning(f"Parameter {param} utanför giltigt intervall: {value}")
                except (ValueError, TypeError):
                    logger.warning(f"Ogiltigt värde för {param}: {params[param]}")
        
        # Integer parametrar
        if 'min_cheap_players' in params and params['min_cheap_players'] is not None:
            try:
                value = int(params['min_cheap_players'])
                if 1 <= value <= 8:  # Rimligt intervall
                    kwargs['min_cheap_players'] = value
                else:
                    logger.warning(f"min_cheap_players utanför giltigt intervall: {value}")
            except (ValueError, TypeError):
                logger.warning(f"Ogiltigt värde för min_cheap_players: {params['min_cheap_players']}")
        
        # Kör optimering
        logger.info(f"Startar optimering med parametrar: {kwargs}")
        optimal_team_data = run_fpl_optimizer(**kwargs)
        
        # Kontrollera om det blev fel
        if 'error' in optimal_team_data:
            logger.error(f"Optimeringsfel: {optimal_team_data['error']}")
            return jsonify(optimal_team_data), 500
        
        # Validera svar
        if not _validate_response(optimal_team_data):
            logger.error("Ogiltigt svar från optimizer")
            return jsonify({"error": "Intern fel - ogiltigt svar från optimizer"}), 500
        
        logger.info("Optimering slutförd framgångsrikt")
        return jsonify(optimal_team_data)
        
    except Exception as e:
        # Logga fullständig stacktrace för debugging
        logger.error(f"Oväntat fel i optimize_team_endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Returnera användarvänligt felmeddelande
        return jsonify({
            "error": "Ett oväntat fel uppstod. Vänligen försök igen senare.",
            "details": str(e) if app.debug else None
        }), 500

def _validate_response(response_data):
    """
    Validerar att svaret från optimizern har rätt struktur.
    """
    try:
        required_keys = ['optimal_starting_xi', 'bench', 'summary']
        if not all(key in response_data for key in required_keys):
            return False
        
        # Kontrollera att vi har rätt antal spelare
        if len(response_data['optimal_starting_xi']) != 11:
            logger.error(f"Felaktigt antal spelare i startelva: {len(response_data['optimal_starting_xi'])}")
            return False
        
        if len(response_data['bench']) != 4:
            logger.error(f"Felaktigt antal spelare på bänk: {len(response_data['bench'])}")
            return False
        
        # Kontrollera att summary har nödvändiga fält
        summary_required = ['squad_total_cost', 'xi_total_expected_points', 'strategy_used']
        if not all(key in response_data['summary'] for key in summary_required):
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Fel vid validering av svar: {e}")
        return False

@app.errorhandler(404)
def not_found(error):
    """Hantera 404-fel."""
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": ["/optimize-team", "/health"]
    }), 404

@app.errorhandler(500)
def internal_server_error(error):
    """Hantera 500-fel."""
    logger.error(f"Intern serverfel: {error}")
    return jsonify({
        "error": "Internal server error",
        "message": "Something went wrong on our end. Please try again later."
    }), 500

if __name__ == '__main__':
    # Kontrollera att datafilen finns
    data_path = os.path.join(os.path.dirname(__file__), 'fpl_data.json')
    if not os.path.exists(data_path):
        logger.warning(f"Datafil saknas: {data_path}")
        logger.warning("Kör data_fetcher.py för att hämta senaste data")
    
    # Bestäm port och debug-läge baserat på miljö
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Startar FPL Optimizer API på port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)