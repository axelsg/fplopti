import sys
import os
sys.path.append(os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from data_fetcher import get_fpl_data
from optimizer_logic import create_optimal_team

app = FastAPI(
    title="FPL Optimizer API",
    description="API for optimizing Fantasy Premier League teams",
    version="1.0.0"
)

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
    """Health check endpoint to verify API is running"""
    return {
        "status": "ok", 
        "message": "FPL Optimizer API is running",
        "version": "1.0.0"
    }

# Data endpoint to test FPL data fetching
@app.get("/data-test")
def test_data_fetch():
    """Test endpoint to verify FPL data can be fetched"""
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
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch FPL data: {str(e)}"
        )

class OptimizationRequest(BaseModel):
    strategy: str = "best_15"
    
    class Config:
        schema_extra = {
            "example": {
                "strategy": "best_15"
            }
        }

@app.post("/optimize-team")
def optimize_team(request: OptimizationRequest):
    """
    Optimize FPL team based on selected strategy
    
    Available strategies:
    - best_15: Best overall team
    - best_11_cheap_bench: Strong starting XI with cheap bench
    - defensive: Defense-focused team
    - offensive: Attack-focused team
    - enabling: Balanced team with premium players
    - differential: Team with differential picks
    """
    try:
        # Validate strategy
        valid_strategies = [
            "best_15", 
            "best_11_cheap_bench", 
            "defensive", 
            "offensive", 
            "enabling", 
            "differential"
        ]
        
        if request.strategy not in valid_strategies:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid strategy. Choose from: {valid_strategies}"
            )
        
        # Fetch FPL data
        fpl_data = get_fpl_data()
        if not fpl_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch FPL data"
            )
        
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

# Additional endpoint to get available strategies
@app.get("/strategies")
def get_strategies():
    """Get list of available optimization strategies"""
    return {
        "strategies": [
            {
                "name": "best_15",
                "description": "Best overall team within budget"
            },
            {
                "name": "best_11_cheap_bench",
                "description": "Strong starting XI with cheap bench players"
            },
            {
                "name": "defensive",
                "description": "Defense-focused team strategy"
            },
            {
                "name": "offensive", 
                "description": "Attack-focused team strategy"
            },
            {
                "name": "enabling",
                "description": "Balanced team with premium players"
            },
            {
                "name": "differential",
                "description": "Team with differential/unique picks"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)