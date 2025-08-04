import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Try multiple import strategies
OPTIMIZER_AVAILABLE = False
get_fpl_data = None
create_optimal_team = None

# Import data_fetcher
try:
    print("Attempting to import data_fetcher...")
    import data_fetcher
    get_fpl_data = data_fetcher.get_fpl_data
    print("✅ data_fetcher imported successfully")
except ImportError as e:
    print(f"❌ data_fetcher import failed: {e}")
    try:
        from data_fetcher import get_fpl_data
        print("✅ data_fetcher imported with 'from' syntax")
    except ImportError as e2:
        print(f"❌ data_fetcher 'from' import also failed: {e2}")
        raise

# Import optimizer_logic with multiple strategies
print("Attempting to import optimizer_logic...")

# Strategy 1: Import module then get function
try:
    import optimizer_logic
    create_optimal_team = optimizer_logic.create_optimal_team
    OPTIMIZER_AVAILABLE = True
    print("✅ optimizer_logic imported successfully (strategy 1)")
except ImportError as e:
    print(f"❌ Strategy 1 failed: {e}")
    
    # Strategy 2: Direct function import
    try:
        from optimizer_logic import create_optimal_team
        OPTIMIZER_AVAILABLE = True
        print("✅ optimizer_logic imported successfully (strategy 2)")
    except ImportError as e2:
        print(f"❌ Strategy 2 failed: {e2}")
        
        # Strategy 3: With explicit path
        try:
            sys.path.append(os.path.join(current_dir, '.'))
            from optimizer_logic import create_optimal_team
            OPTIMIZER_AVAILABLE = True
            print("✅ optimizer_logic imported successfully (strategy 3)")
        except ImportError as e3:
            print(f"❌ Strategy 3 failed: {e3}")
            print("❌ All import strategies failed for optimizer_logic")

# Fallback function if optimizer not available
if not OPTIMIZER_AVAILABLE:
    def create_optimal_team(fpl_data, strategy="best_15"):
        return {
            "error": "Optimizer not available - check OR-Tools installation",
            "optimal_starting_xi": [],
            "bench": [],
            "summary": {
                "squad_total_cost": 0,
                "xi_total_expected_points": 0,
                "strategy_used": strategy
            }
        }

app = FastAPI(
    title="FPL Optimizer API",
    description="API for optimizing Fantasy Premier League teams",
    version="1.0.0"
)

# Enhanced CORS middleware - Allow specific Lovable domains
allowed_origins = [
    "https://lovable.dev",
    "https://id-preview--862ad416-c6a6-400e-b5a6-27a17a5b8983.lovable.app",
    "https://id-preview--862ad416-8983.lovable.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]

# Add wildcard for any Lovable preview URLs
lovable_pattern = "https://*.lovable.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=False,  # Set to False when using allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add a preflight handler for OPTIONS requests
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return {"message": "OK"}

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok", 
        "message": "FPL Optimizer API is running",
        "optimizer_available": OPTIMIZER_AVAILABLE,
        "version": "1.0.0",
        "cors": "enabled"
    }

@app.get("/debug")
def debug_info():
    """Debug endpoint to check imports and file system"""
    try:
        import ortools
        ortools_available = True
        ortools_version = getattr(ortools, '__version__', 'unknown')
    except ImportError:
        ortools_available = False
        ortools_version = None
    
    return {
        "current_directory": os.getcwd(),
        "file_directory": os.path.dirname(__file__),
        "files_in_current": os.listdir('.') if os.path.exists('.') else [],
        "files_in_app": os.listdir('.') if os.path.exists('.') else [],
        "optimizer_available": OPTIMIZER_AVAILABLE,
        "ortools_available": ortools_available,
        "ortools_version": ortools_version,
        "python_path": sys.path[:5],  # First 5 entries
        "data_fetcher_available": get_fpl_data is not None,
        "cors_origins": allowed_origins
    }

@app.get("/data-test")
def test_data_fetch():
    """Test FPL data fetching"""
    if not get_fpl_data:
        raise HTTPException(status_code=500, detail="data_fetcher not available")
    
    try:
        fpl_data = get_fpl_data()
        players_count = len(fpl_data.get('elements', []))
        teams_count = len(fpl_data.get('teams', []))
        
        return {
            "status": "success",
            "message": "FPL data fetched successfully",
            "players_count": players_count,
            "teams_count": teams_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch FPL data: {str(e)}")

class OptimizationRequest(BaseModel):
    strategy: str = "best_15"

@app.post("/optimize-team")
def optimize_team(request: OptimizationRequest):
    """Optimize FPL team"""
    print(f"🚀 Received optimization request: {request.strategy}")
    
    try:
        # Validate strategy
        valid_strategies = ["best_15", "best_11_cheap_bench", "defensive", "offensive", "enabling", "differential"]
        if request.strategy not in valid_strategies:
            raise HTTPException(status_code=400, detail=f"Invalid strategy. Choose from: {valid_strategies}")
        
        # Check if optimizer is available
        if not OPTIMIZER_AVAILABLE:
            print("❌ Optimizer not available, returning error response")
            return {
                "error": "Optimizer logic not available - check OR-Tools installation and deployment",
                "optimal_starting_xi": [],
                "bench": [],
                "summary": {
                    "squad_total_cost": 0,
                    "xi_total_expected_points": 0,
                    "strategy_used": request.strategy
                }
            }
        
        # Fetch FPL data
        if not get_fpl_data:
            raise HTTPException(status_code=500, detail="data_fetcher not available")
            
        print("📊 Fetching FPL data...")
        fpl_data = get_fpl_data()
        if not fpl_data:
            raise HTTPException(status_code=500, detail="Failed to fetch FPL data")
        
        print(f"✅ FPL data fetched: {len(fpl_data.get('elements', []))} players")
        
        # Create optimal team
        print("🤖 Creating optimal team...")
        result = create_optimal_team(fpl_data, request.strategy)
        
        print("✅ Optimization completed successfully")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in optimize_team: {str(e)}")
        return {
            "error": str(e),
            "optimal_starting_xi": [],
            "bench": [],
            "summary": {
                "squad_total_cost": 0,
                "xi_total_expected_points": 0,
                "strategy_used": request.strategy
            }
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)