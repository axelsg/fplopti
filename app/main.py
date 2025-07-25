from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from data_fetcher import get_fpl_data
from optimizer_logic import create_optimal_team

app = FastAPI()

# CORS middleware configuration - THIS IS CRITICAL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins during development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Health check endpoint
@app.get("/")
def health_check():
    return {"status": "ok", "message": "FPL Optimizer API is running"}

class OptimizationRequest(BaseModel):
    strategy: str = "best_15"

@app.post("/optimize-team")
def optimize_team(request: OptimizationRequest):
    try:
        # Validate strategy
        valid_strategies = ["best_15", "best_11_cheap_bench", "defensive", "offensive", "enabling", "differential"]
        if request.strategy not in valid_strategies:
            raise HTTPException(status_code=400, detail=f"Invalid strategy. Choose from: {valid_strategies}")
        
        # Fetch FPL data
        fpl_data = get_fpl_data()
        
        # Create optimal team
        result = create_optimal_team(fpl_data, request.strategy)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        # Return error in the expected format
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