# app/main.py

from fastapi import FastAPI
from .data_fetcher import update_fpl_data
from .optimizer_logic import run_fpl_optimizer

app = FastAPI(
    title="FPL Optimizer API",
    description="Ett API för att optimera ett Fantasy Premier League-lag."
)

# --- Endpoint 1: POST ---
@app.post("/update-data/", summary="Uppdatera FPL-data")
def update_data_endpoint():
    """
    Kör skriptet för att hämta den senaste spelardatan från FPL:s API
    och spara den som fpl_data.json.
    """
    return update_fpl_data()

# --- Endpoint 2: GET ---
@app.get("/optimize-team/", summary="Optimera FPL-lag")
def get_optimal_team():
    """
    Kör optimeraren på den senast hämtade datan och returnerar den bästa truppen.
    """
    return run_fpl_optimizer()