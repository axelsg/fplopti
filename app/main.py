import sys
import os
import uuid
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Samma robusta importlogik som tidigare ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

OPTIMIZER_AVAILABLE = False
get_fpl_data = None
create_optimal_team = None

try:
    import data_fetcher
    get_fpl_data = data_fetcher.get_fpl_data
    print("✅ data_fetcher imported successfully")
except ImportError as e:
    print(f"❌ data_fetcher import failed: {e}")

try:
    import optimizer_logic
    create_optimal_team = optimizer_logic.create_optimal_team
    OPTIMIZER_AVAILABLE = optimizer_logic.ORTOOLS_AVAILABLE
    print("✅ optimizer_logic imported successfully")
except ImportError as e:
    print(f"❌ optimizer_logic import failed: {e}")

# --- Minne för att lagra status på optimeringsjobb ---
optimization_jobs: Dict[str, Any] = {}

def run_optimization_task(job_id: str, strategy: str):
    print(f"Background task started for job_id: {job_id}")
    optimization_jobs[job_id] = {"status": "processing", "result": None}
    try:
        if not get_fpl_data or not create_optimal_team or not OPTIMIZER_AVAILABLE:
            raise Exception("Server error: A required module is not available.")
        
        fpl_data = get_fpl_data()
        if not fpl_data or 'elements' not in fpl_data:
            raise Exception("Failed to fetch valid FPL data")
        
        result = create_optimal_team(fpl_data, strategy)
        optimization_jobs[job_id] = {"status": "completed", "result": result}
        print(f"✅ Background task finished for job_id: {job_id}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        optimization_jobs[job_id] = {"status": "failed", "error": str(e)}

# --- FastAPI App & CORS-inställningar ---
app = FastAPI(
    title="FPL Optimizer API",
    description="API for optimizing Fantasy Premier League teams",
    version="1.4.1_VERIFICATION"  # NYTT VERSIONNUMMER FÖR ATT VERIFIERA
)

allowed_origins = [
    "https://lovable.dev",
    "https://*.lovable.app",
    "https://*.vableproject.com",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---

# VERIFIERINGS-ENDPOINT
@app.get("/version")
def get_version():
    """Returnerar den nuvarande versionen av appen för att verifiera deployment."""
    return {"version": "1.4.1_VERIFICATION", "message": "Deployment is live and correct."}

@app.get("/")
def health_check():
    return {
        "status": "ok", 
        "message": "FPL Optimizer API is running",
        "optimizer_available": OPTIMIZER_AVAILABLE
    }

class OptimizationRequest(BaseModel):
    strategy: str = "best_15"

# Manuell OPTIONS-hanterare
@app.options("/optimize-team")
async def options_optimize_team():
    response = Response()
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.post("/optimize-team", status_code=202)
def start_optimization(request: OptimizationRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    print(f"🚀 Received optimization request with strategy: '{request.strategy}'. Assigning job_id: {job_id}")
    
    valid_strategies = ["best_15", "best_11_cheap_bench", "defensive", "offensive", "enabling", "differential"]
    if request.strategy not in valid_strategies:
        raise HTTPException(status_code=400, detail=f"Invalid strategy. Choose from: {valid_strategies}")

    background_tasks.add_task(run_optimization_task, job_id, request.strategy)
    return {"job_id": job_id, "status": "accepted", "message": "Optimization started."}

@app.get("/results/{job_id}")
def get_results(job_id: str):
    job = optimization_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return job

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)