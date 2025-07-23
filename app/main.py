# app/main.py

from fastapi import FastAPI
# NY IMPORT: Importera CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware

# Importera funktionerna från våra andra moduler
from .data_fetcher import update_fpl_data
from .optimizer_logic import run_fpl_optimizer

app = FastAPI(
    title="FPL Optimizer API",
    description="Ett API för att optimera ett Fantasy Premier League-lag."
)

# === NY KOD: Lägg till CORS Middleware ===
# Definiera en lista över de domäner som får anropa detta API
origins = [
    "*"  # Detta tillåter ALLA domäner. För ett hobbyprojekt är detta okej.
    # För en mer säker app skulle du specificera din Lovable-URL här, t.ex:
    # "https://dinsida.lovable.com",
    # "https://www.dindomän.ai"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Tillåt alla metoder (GET, POST, etc.)
    allow_headers=["*"], # Tillåt alla headers
)
# ======================================

@app.post("/update-data/", summary="Uppdatera FPL-data")
def update_data_endpoint():
    """
    Kör skriptet för att hämta den senaste spelardatan från FPL:s API
    och spara den som fpl_data.json.
    """
    return update_fpl_data()

@app.get("/optimize-team/", summary="Optimera FPL-lag")
def get_optimal_team():
    """
    Kör optimeraren på den senast hämtade datan och returnerar den bästa truppen.
    """
    return run_fpl_optimizer()