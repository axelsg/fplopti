import sys
import os
import uuid
from typing import Dict, Any

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Importer ---
# (Din befintliga, robusta importlogik behålls)
OPTIMIZER_AVAILABLE = False
get_fpl_data = None
create_optimal_team = None

try:
    import data_fetcher
    get_fpl_data = data_fetcher.get_fpl_data
except ImportError:
    from data_fetcher import get_fpl_data

try:
    import optimizer_logic
    create_optimal_team = optimizer_logic.create_optimal_team
    OPTIMIZER_AVAILABLE = True
except ImportError:
    try:
        from optimizer_logic import create_optimal_team
        OPTIMIZER_AVAILABLE = True
    except ImportError:
        print("❌ All import strategies failed for optimizer_logic")

# --- NYHET: Minne för att lagra status på optimeringsjobb ---
# Detta agerar som en enkel databas. I en större applikation kan man använda Redis.
optimization_jobs: Dict[str, Any] = {}

def run_optimization_task(job_id: str, strategy: str):
    """
    Funktion som kör den tunga optimeringen i bakgrunden.
    Uppdaterar `optimization_jobs` med status och resultat.
    """
    print(f"Background task started for job_id: {job_id}")
    optimization_jobs[job_id] = {"status": "processing"}
    try:
        if not get_fpl_data or not OPTIMIZER_AVAILABLE:
            raise Exception("Server error: data fetcher or optimizer not available.")

        print(f"[{job_id}] Fetching FPL data...")
        fpl_data = get_fpl_data()
        if not fpl_data:
            raise Exception("Failed to fetch FPL data")
        
        print(f"[{job_id}] Data fetched, starting optimization...")
        result = create_optimal_team(fpl_data, strategy)
        
        optimization_jobs[job_id] = {"status": "completed", "result": result}
        print(f"✅ Background task finished for job_id: {job_id}")

    except Exception as e:
        print(f"❌ Background task failed for job_id: {job_id}. Error: {e}")
        optimization_jobs[job_id] = {"status": "failed", "error": str(e)}

# --- FastAPI App & CORS-inställningar ---
app = FastAPI(
    title="FPL Optimizer API",
    description="API for optimizing Fantasy Premier League teams",
    version="1.1.0" # Uppdaterad version
)

# Förbättrad CORS - mer specifik och säker
allowed_origins = [
    "https://lovable.dev",
    "https://*.lovable.app", # Wildcard för alla dina preview-URLer
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
@app.get("/")
def health_check():
    """Hälsokontroll-endpoint"""
    return {
        "status": "ok", 
        "message": "FPL Optimizer API is running",
        "optimizer_available": OPTIMIZER_AVAILABLE
    }

class OptimizationRequest(BaseModel):
    strategy: str = "best_15"

# --- UPPDATERADE ENDPOINTS FÖR ASYNKRON HANTERING ---

@app.post("/optimize-team", status_code=202)
def start_optimization(request: OptimizationRequest, background_tasks: BackgroundTasks):
    """
    Startar en optimeringsprocess i bakgrunden. Svarar omedelbart
    med ett unikt jobb-ID som kan användas för att hämta resultatet.
    """
    job_id = str(uuid.uuid4())
    print(f"🚀 Received optimization request with strategy: '{request.strategy}'. Assigning job_id: {job_id}")
    
    valid_strategies = ["best_15", "best_11_cheap_bench", "defensive", "offensive", "enabling", "differential"]
    if request.strategy not in valid_strategies:
        raise HTTPException(status_code=400, detail=f"Invalid strategy. Choose from: {valid_strategies}")

    # Lägg till den tidskrävande funktionen som en bakgrundsuppgift
    background_tasks.add_task(run_optimization_task, job_id, request.strategy)

    return {"job_id": job_id, "status": "accepted", "message": "Optimization started."}

@app.get("/results/{job_id}")
def get_results(job_id: str):
    """
    Hämtar status eller resultat för ett optimeringsjobb.
    Frontend ska anropa denna endpoint upprepade gånger tills status är 'completed' eller 'failed'.
    """
    job = optimization_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    return job

if __name__ == "__main__":
    import uvicorn
    # Port 10000 är standard för Render.com, men 8000 fungerar också lokalt.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)