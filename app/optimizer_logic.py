# app/optimizer_logic.py

import pandas as pd
import pulp

def run_fpl_optimizer():
    """Kör hela optimeringsprocessen och returnerar resultatet."""
    BUDGET = 100.0
    POSITIONS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    TOTAL_PLAYERS = sum(POSITIONS.values())
    MAX_PLAYERS_PER_TEAM = 3

    try:
        df = pd.read_json('fpl_data.json')
    except FileNotFoundError:
        return {"error": "Datakällan fpl_data.json hittades inte. Kör datahämtningen först."}
    
    df['position'] = pd.Categorical(df['position'], categories=POSITIONS.keys())
    teams = df['team'].unique()

    prob = pulp.LpProblem("FPL_Team_Optimization", pulp.LpMaximize)
    player_vars = pulp.LpVariable.dicts("Player", df.index, cat='Binary')
    prob += pulp.lpSum([player_vars[i] * df.loc[i, 'expected_points'] for i in df.index])
    prob += pulp.lpSum([player_vars[i] * df.loc[i, 'price'] for i in df.index]) <= BUDGET
    prob += pulp.lpSum(player_vars) == TOTAL_PLAYERS
    for pos, count in POSITIONS.items():
        prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'position'] == pos]) == count
    for team in teams:
        prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'team'] == team]) <= MAX_PLAYERS_PER_TEAM

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] == 'Optimal':
        selected_indices = [i for i in df.index if player_vars[i].varValue == 1]
        selected_df = df.loc[selected_indices].sort_values(by=['position'])
        result_team = selected_df[['name', 'team', 'position', 'price', 'expected_points']].to_dict(orient='records')
        summary = {
            "total_cost": round(selected_df['price'].sum(), 2),
            "total_expected_points": round(selected_df['expected_points'].sum(), 2)
        }
        return {"optimal_team": result_team, "summary": summary}
    else:
        return {"error": "Kunde inte hitta en optimal lösning."}