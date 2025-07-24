import pandas as pd
import pulp
import numpy as np

def run_fpl_optimizer(
    strategy: str = 'best_15',
    defensive_weight: float = 1.2, # Vikt för defensiva spelares xP i defensiv strategi
    offensive_weight: float = 1.2, # Vikt för offensiva spelares xP i offensiv strategi
    differential_factor: float = 0.05, # Faktor för differential-strategi (bonus per procentenhet lägre ägarskap)
    min_cheap_players: int = 4, # Minsta antal billiga spelare för "billig bänk" / "enabling"
    cheap_player_price_threshold: float = 5.0 # Maxpris för en "billig" spelare
):
    """
    Kör hela optimeringsprocessen för att hitta det optimala FPL-laget.
    Returnerar den optimala 15-manna truppen, den bästa startelvan (11 spelare),
    bänken, samt val av kapten och vice-kapten.

    Args:
        strategy (str): Vilken optimeringsstrategi som ska användas.
                        Möjliga värden:
                        - 'best_15': Maximera totala xP för 15-manna truppen.
                        - 'best_11_cheap_bench': Maximera xP för startelvan, med fokus på billig bänk.
                        - 'defensive': Prioritera defensiva spelares xP.
                        - 'offensive': Prioritera offensiva spelares xP.
                        - 'enabling': Fokusera på att få in billiga spelare för att möjliggöra dyrare stjärnor.
                        - 'differential': Prioritera spelare med låg ägarskapsprocent.
        defensive_weight (float): Vikt som appliceras på GKP och DEF expected_points
                                  när 'defensive' strategi används.
        offensive_weight (float): Vikt som appliceras på MID och FWD expected_points
                                  när 'offensive' strategi används.
        differential_factor (float): Faktor som bestämmer hur mycket lägre ägarskap
                                     påverkar spelarens värde i 'differential' strategi.
                                     (Bonus = differential_factor * (100 - ownership_percentage))
        min_cheap_players (int): Minsta antal spelare under `cheap_player_price_threshold`
                                 för 'best_11_cheap_bench' och 'enabling' strategier.
        cheap_player_price_threshold (float): Maxpris för en spelare att räknas som "billig".

    Returns:
        dict: En dictionary med det optimala laget, startelvan, bänken och en sammanfattning,
              eller ett felmeddelande om optimeringen misslyckas.
    """

    # --- FPL Regler och konstanter ---
    BUDGET = 100.0  # Miljoner pund för hela truppen
    
    # Positionskrav för den totala 15-manna truppen
    SQUAD_POSITIONS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    TOTAL_SQUAD_PLAYERS = sum(SQUAD_POSITIONS.values()) # Ska vara 15
    MAX_PLAYERS_PER_CLUB = 3 # Max 3 spelare från samma Premier League-klubb

    # Positionskrav för startelvan (11 spelare)
    STARTING_XI_POS_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
    STARTING_XI_POS_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3} 
    TOTAL_STARTING_XI_PLAYERS = 11

    try:
        # Försök att läsa in spelardata från fpl_data.json
        df = pd.read_json('fpl_data.json')
    except FileNotFoundError:
        return {"error": "Datakällan fpl_data.json hittades inte. Kör datahämtningen först via /update-data/ endpointet."}
    
    # Säkerställ att 'position' är en kategorisk typ för konsekvent sortering och filtrering
    df['position'] = pd.Categorical(df['position'], categories=SQUAD_POSITIONS.keys(), ordered=True)

    # --- Förbehandling av spelardata baserat på status och chans att spela ---
    # Justera 'expected_points' baserat på 'status' och 'chance_of_playing_this_round'
    df['adjusted_expected_points'] = df['expected_points'].copy() # Börja med en kopia av original xP

    # Om status är 'i' (injured) eller 's' (suspended), sätt adjusted_expected_points till 0
    df.loc[df['status'].isin(['i', 's']), 'adjusted_expected_points'] = 0

    # Om 'chance_of_playing_this_round' är mindre än 100, skala ner expected_points
    # Endast för spelare som inte redan är uteslutna av 'status'
    df.loc[(df['chance_of_playing_this_round'] < 100) & (~df['status'].isin(['i', 's'])), 'adjusted_expected_points'] = \
        df['adjusted_expected_points'] * (df['chance_of_playing_this_round'] / 100.0)
    
    # Säkerställ att adjusted_expected_points inte är NaN (kan hända om original xP var NaN)
    df['adjusted_expected_points'] = df['adjusted_expected_points'].fillna(0)


    # --- Steg 1: Optimera 15-manna truppen ---
    prob_squad = pulp.LpProblem("FPL_Squad_Optimization", pulp.LpMaximize)
    squad_player_vars = pulp.LpVariable.dicts("SquadPlayer", df.index, cat='Binary')
    
    # --- Målfunktion baserad på strategi (använder nu 'adjusted_expected_points') ---
    if strategy == 'defensive':
        # Prioritera defensiva spelare
        objective_expr = pulp.lpSum([
            squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] * (defensive_weight if df.loc[i, 'position'] in ['DEF', 'GKP'] else 1.0)
            for i in df.index
        ])
    elif strategy == 'offensive':
        # Prioritera offensiva spelare
        objective_expr = pulp.lpSum([
            squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] * (offensive_weight if df.loc[i, 'position'] in ['MID', 'FWD'] else 1.0)
            for i in df.index
        ])
    elif strategy == 'differential':
        # Prioritera spelare med låg ägarskapsprocent
        # Bonusen blir högre ju lägre ägarskap (100 - ownership_percentage)
        # Se till att ownership_percentage är numerisk och inte NaN
        df['ownership_percentage'] = pd.to_numeric(df['ownership_percentage'], errors='coerce').fillna(100) # Fyll NaN med 100 för att inte ge bonus till okänd ägarskap
        objective_expr = pulp.lpSum([
            squad_player_vars[i] * (df.loc[i, 'adjusted_expected_points'] + 
                                    differential_factor * (100 - df.loc[i, 'ownership_percentage']))
            for i in df.index
        ])
    else: # 'best_15', 'best_11_cheap_bench', 'enabling' använder standard xP-maximering för 15-manna truppen
        objective_expr = pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] for i in df.index])

    prob_squad += objective_expr, "Total Expected Points for Squad"
    
    # Begränsningar för 15-manna truppen (gemensamma för alla strategier):
    prob_squad += pulp.lpSum([squad_player_vars[i] * df.loc[i, 'price'] for i in df.index]) <= BUDGET, "Budget Constraint"
    prob_squad += pulp.lpSum(squad_player_vars) == TOTAL_SQUAD_PLAYERS, "Total Players in Squad"
    
    for pos, count in SQUAD_POSITIONS.items():
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'position'] == pos]) == count, f"Squad Position {pos} Count"
    
    for team in df['team'].unique():
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'team'] == team]) <= MAX_PLAYERS_PER_CLUB, f"Max Players from {team}"

    # Specifika begränsningar för "best_11_cheap_bench" och "enabling" strategier
    if strategy in ['best_11_cheap_bench', 'enabling']:
        # Se till att det finns minst 'min_cheap_players' som är under 'cheap_player_price_threshold'
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'price'] <= cheap_player_price_threshold]) >= min_cheap_players, "Min Cheap Players for Bench/Enabling"

    # Lös det första optimeringsproblemet (för 15-manna truppen)
    prob_squad.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob_squad.status] != 'Optimal':
        return {"error": f"Kunde inte hitta en optimal lösning för 15-manna truppen med den valda strategin '{strategy}'. Status: {pulp.LpStatus[prob_squad.status]}"}

    selected_squad_indices = [i for i in df.index if squad_player_vars[i].varValue == 1]
    selected_squad_df = df.loc[selected_squad_indices].copy()
    
    # --- Steg 2: Optimera startelvan (11 spelare) från den valda 15-manna truppen ---
    prob_xi = pulp.LpProblem("FPL_Starting_XI_Optimization", pulp.LpMaximize)
    xi_player_vars = pulp.LpVariable.dicts("XIPlayer", selected_squad_df.index, cat='Binary')

    # Målfunktion för startelvan är alltid att maximera xP (använder 'adjusted_expected_points')
    prob_xi += pulp.lpSum([xi_player_vars[i] * selected_squad_df.loc[i, 'adjusted_expected_points'] for i in selected_squad_df.index]), "Total Expected Points for Starting XI"

    # Begränsningar för startelvan:
    prob_xi += pulp.lpSum(xi_player_vars) == TOTAL_STARTING_XI_PLAYERS, "Total Players in Starting XI"
    
    for pos in SQUAD_POSITIONS.keys():
        prob_xi += pulp.lpSum([xi_player_vars[i] for i in selected_squad_df.index if selected_squad_df.loc[i, 'position'] == pos]) >= STARTING_XI_POS_MIN.get(pos, 0), f"Min XI Position {pos} Count"
        prob_xi += pulp.lpSum([xi_player_vars[i] for i in selected_squad_df.index if selected_squad_df.loc[i, 'position'] == pos]) <= STARTING_XI_POS_MAX.get(pos, SQUAD_POSITIONS[pos]), f"Max XI Position {pos} Count"

    prob_xi.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob_xi.status] != 'Optimal':
        return {"error": f"Kunde inte hitta en optimal lösning för startelvan. Status: {pulp.LpStatus[prob_xi.status]}"}

    starting_xi_indices = [i for i in selected_squad_df.index if xi_player_vars[i].varValue == 1]
    # Sortera efter position och sedan justerade poäng
    starting_xi_df = selected_squad_df.loc[starting_xi_indices].sort_values(by=['position', 'adjusted_expected_points'], ascending=[True, False])

    # --- Steg 3: Optimera bänken och välja Kapten/Vice-kapten ---

    bench_indices = [i for i in selected_squad_df.index if i not in starting_xi_indices]
    bench_df = selected_squad_df.loc[bench_indices].copy()

    # Sortera bänken för auto-subs (utespelare efter justerade xP, målvakt sist)
    bench_gk = bench_df[bench_df['position'] == 'GKP']
    bench_outfield = bench_df[bench_df['position'] != 'GKP']
    
    bench_outfield_sorted = bench_outfield.sort_values(by='adjusted_expected_points', ascending=False)
    
    # Kontrollera och hantera bänkstrukturen
    if len(bench_gk) == 1 and len(bench_outfield) == 3:
        final_bench_df = pd.concat([bench_outfield_sorted, bench_gk])
    else:
        # Fallback om bänkstrukturen är oväntad (bör inte hända om steg 1 och 2 är korrekta)
        print(f"Varning: Bänkstrukturen är oväntad ({len(bench_gk)} GK, {len(bench_outfield)} utespelare). Sorterar om hela bänken.")
        final_bench_df = bench_df.assign(pos_order=bench_df['position'].map({'DEF': 1, 'MID': 2, 'FWD': 3, 'GKP': 4})) \
                               .sort_values(by=['pos_order', 'adjusted_expected_points'], ascending=[True, False]) \
                               .drop(columns='pos_order')
        # Säkerställ att vi får exakt 3 utespelare och 1 GK om det var fel
        bench_outfield_final = final_bench_df[final_bench_df['position'] != 'GKP'].head(3)
        bench_gk_final = final_bench_df[final_bench_df['position'] == 'GKP'].head(1)
        final_bench_df = pd.concat([bench_outfield_final, bench_gk_final])


    # Välj Kapten (C) och Vice-kapten (VC) från startelvan
    # Sortera startelvan efter justerade förväntade poäng (högst först)
    sorted_xi_for_captaincy = starting_xi_df.sort_values(by='adjusted_expected_points', ascending=False)
    
    captain = None
    vice_captain = None
    
    if not sorted_xi_for_captaincy.empty:
        captain = sorted_xi_for_captaincy.iloc[0][['name', 'team', 'position', 'adjusted_expected_points']].to_dict()
        # Ändra nyckeln i dicten till 'expected_points' för konsekvens
        if captain:
            captain['expected_points'] = captain.pop('adjusted_expected_points')

        if len(sorted_xi_for_captaincy) > 1:
            vice_captain = sorted_xi_for_captaincy.iloc[1][['name', 'team', 'position', 'adjusted_expected_points']].to_dict()
            # Ändra nyckeln i dicten till 'expected_points' för konsekvens
            if vice_captain:
                vice_captain['expected_points'] = vice_captain.pop('adjusted_expected_points')

    # --- Förbered resultatobjektet för retur ---
    # Använd 'adjusted_expected_points' för de faktiska poängen i resultatet
    result_squad = selected_squad_df[['name', 'team', 'position', 'price', 'adjusted_expected_points']].to_dict(orient='records')
    # Döp om nyckeln i varje dict för att behålla 'expected_points' som standardnamn
    for player in result_squad:
        player['expected_points'] = player.pop('adjusted_expected_points')

    result_starting_xi = starting_xi_df[['name', 'team', 'position', 'price', 'adjusted_expected_points']].to_dict(orient='records')
    for player in result_starting_xi:
        player['expected_points'] = player.pop('adjusted_expected_points')

    result_bench = final_bench_df[['name', 'team', 'position', 'price', 'adjusted_expected_points']].to_dict(orient='records')
    for player in result_bench:
        player['expected_points'] = player.pop('adjusted_expected_points')


    summary = {
        "squad_total_cost": round(selected_squad_df['price'].sum(), 2),
        "squad_total_expected_points": round(selected_squad_df['adjusted_expected_points'].sum(), 2),
        "xi_total_expected_points": round(starting_xi_df['adjusted_expected_points'].sum(), 2),
        "captain": captain,
        "vice_captain": vice_captain,
        "strategy_used": strategy
    }
    
    return {
        "optimal_squad_15": result_squad,
        "optimal_starting_xi": result_starting_xi,
        "bench": result_bench,
        "summary": summary
    }

