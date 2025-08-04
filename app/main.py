import sys
import os
import uuid
from typing import Dict, Any

# Lägger till nuvarande mapp i Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Importer ---
# Denna robusta importlogik säkerställer att appen kan starta
# även om en modul saknas, och ge tydliga felmeddelanden.
OPTIMIZER_AVAILABLE = False
get_f_data = None
create_optimal_team = None

try:
    import data_fetcher
    get_f_data = data_fetcher.get_fpl_data
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
# Detta agerar som en enkel temporär databas för jobbstatus.
optimization_jobs: Dict[str, Any] = {}

def run_optimization_task(job_id: str, strategy: str):
    """
    Funktion som kör den tunga optimeringen i bakgrunden.
    Uppdaterar `optimization_jobs` med status och resultat.
    """
    print(f"Background task started for job_id: {job_id}")
    optimization_jobs[job_id] = {"status": "processing", "result": None}
    try:
        if not get_f_data or not create_optimal_team or not OPTIMIZER_AVAILABLE:
            raise Exception("Server error: A required module (data_fetcher or optimizer_logic) is not available.")

        print(f"[{job_id}] Fetching FPL data...")
        fpl_data = get_f_data()
        if not fpl_data or 'elements' not in fpl_data:
            raise Exception("Failed to fetch valid FPL data")
        
        print(f"[{job_id}] Data fetched ({len(fpl_data['elements'])} players), starting optimization...")
        result = create_optimal_team(fpl_data, strategy)
        
        optimization_jobs[job_id] = {"status": "completed", "result": result}
        print(f"✅ Background task finished for job_id: {job_id}")

    except Exception as e:
        print(f"❌ Background task failed for job_id: {job_id}. Error: {e}")
        import traceback
        traceback.print_exc()
        optimization_jobs[job_id] = {"status": "failed", "error": str(e)}

# --- FastAPI App & CORS-inställningar ---
app = FastAPI(
    title="FPL Optimizer API",
    description="API for optimizing Fantasy Premier League teams",
    version="1.2.0"
)

# Robust CORS-konfiguration som inkluderar alla dina kända domäner
allowed_origins = [
    "https://lovable.dev",
    "https://*.lovable.app",
    "https://*.vableproject.com", # Från din senaste fel-logg
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"], # Tillåter GET, POST, OPTIONS etc.
    allow_headers=["*"], # Tillåter alla headers
)

# --- VIKTIGT: Säkerställ att inga manuella @app.options-routes finns kvar i filen ---
# CORSMiddleware ovan hanterar detta automatiskt och korrekt.

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

# --- ASYNKRONA ENDPOINTS ---

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
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)