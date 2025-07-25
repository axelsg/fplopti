import pandas as pd
import pulp
import numpy as np
import os # Importera os-modulen för att hantera filsökvägar

def run_fpl_optimizer(
    strategy: str = 'best_15',
    defensive_weight: float = 1.2,
    offensive_weight: float = 1.2,
    differential_factor: float = 0.05,
    min_cheap_players: int = 4
    # Notera: cheap_player_price_threshold är borttagen
):
    """
    Kör hela optimeringsprocessen och returnerar det optimala laget,
    inklusive information om nästa motståndare.
    Använder nu positionsspecifika prisgränser för "billiga" spelare.
    """

    # --- FPL Regler och konstanter ---
    BUDGET = 100.0
    SQUAD_POSITIONS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    TOTAL_SQUAD_PLAYERS = 15
    MAX_PLAYERS_PER_CLUB = 3
    STARTING_XI_POS_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
    STARTING_XI_POS_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}
    TOTAL_STARTING_XI_PLAYERS = 11

    # NYTT: Positionsspecifika prisgränser för "billiga" spelare
    CHEAP_PLAYER_THRESHOLDS = {
        "GKP": 4.0,
        "DEF": 4.0,
        "MID": 4.5,
        "FWD": 4.5
    }

    try:
        script_dir = os.path.dirname(__file__)
        data_path = os.path.join(script_dir, 'fpl_data.json')
        df = pd.read_json(data_path)
    except FileNotFoundError:
        return {"error": "Datakällan fpl_data.json hittades inte i app-mappen."}
    
    # --- Förbered data ---
    df['position'] = pd.Categorical(df['position'], categories=SQUAD_POSITIONS.keys(), ordered=True)
    df['adjusted_expected_points'] = df['expected_points'].copy()
    df.loc[df['status'].isin(['i', 's']), 'adjusted_expected_points'] = 0
    df.loc[(df['chance_of_playing_this_round'] < 100) & (~df['status'].isin(['i', 's'])), 'adjusted_expected_points'] *= (df['chance_of_playing_this_round'] / 100.0)
    df['adjusted_expected_points'] = df['adjusted_expected_points'].fillna(0)
    
    if 'next_opponent' not in df.columns: df['next_opponent'] = 'N/A'
    if 'is_home' not in df.columns: df['is_home'] = False
    df['next_opponent'] = df['next_opponent'].fillna('N/A')
    df['is_home'] = df['is_home'].fillna(False)

    # --- Steg 1: Optimera 15-manna truppen ---
    prob_squad = pulp.LpProblem("FPL_Squad_Optimization", pulp.LpMaximize)
    squad_player_vars = pulp.LpVariable.dicts("SquadPlayer", df.index, cat='Binary')
    
    if strategy == 'defensive':
        objective_expr = pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] * (defensive_weight if df.loc[i, 'position'] in ['DEF', 'GKP'] else 1.0) for i in df.index])
    elif strategy == 'offensive':
        objective_expr = pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] * (offensive_weight if df.loc[i, 'position'] in ['MID', 'FWD'] else 1.0) for i in df.index])
    elif strategy == 'differential':
        df['ownership_percentage'] = pd.to_numeric(df['ownership_percentage'], errors='coerce').fillna(100)
        objective_expr = pulp.lpSum([squad_player_vars[i] * (df.loc[i, 'adjusted_expected_points'] + differential_factor * (100 - df.loc[i, 'ownership_percentage'])) for i in df.index])
    else:
        objective_expr = pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] for i in df.index])

    prob_squad += objective_expr
    
    prob_squad += pulp.lpSum([squad_player_vars[i] * df.loc[i, 'price'] for i in df.index]) <= BUDGET
    prob_squad += pulp.lpSum(squad_player_vars) == TOTAL_SQUAD_PLAYERS
    for pos, count in SQUAD_POSITIONS.items():
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'position'] == pos]) == count
    for team in df['team'].unique():
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'team'] == team]) <= MAX_PLAYERS_PER_CLUB
    
    # UPPDATERAD LOGIK för "billiga" spelare
    if strategy in ['best_11_cheap_bench', 'enabling']:
        cheap_player_indices = []
        for i in df.index:
            player_pos = df.loc[i, 'position']
            player_price = df.loc[i, 'price']
            threshold = CHEAP_PLAYER_THRESHOLDS.get(player_pos)
            if threshold and player_price <= threshold:
                cheap_player_indices.append(i)
        
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in cheap_player_indices]) >= min_cheap_players, "Min Cheap Players Constraint"

    prob_squad.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob_squad.status] != 'Optimal':
        return {"error": f"Kunde inte hitta en optimal trupp. Status: {pulp.LpStatus[prob_squad.status]}"}

    selected_squad_df = df.loc[[i for i in df.index if squad_player_vars[i].varValue == 1]].copy()
    
    # --- Steg 2: Optimera startelvan ---
    prob_xi = pulp.LpProblem("FPL_Starting_XI_Optimization", pulp.LpMaximize)
    xi_player_vars = pulp.LpVariable.dicts("XIPlayer", selected_squad_df.index, cat='Binary')
    prob_xi += pulp.lpSum([xi_player_vars[i] * selected_squad_df.loc[i, 'adjusted_expected_points'] for i in selected_squad_df.index])
    prob_xi += pulp.lpSum(xi_player_vars) == TOTAL_STARTING_XI_PLAYERS
    for pos in SQUAD_POSITIONS.keys():
        prob_xi += pulp.lpSum([xi_player_vars[i] for i in selected_squad_df.index if selected_squad_df.loc[i, 'position'] == pos]) >= STARTING_XI_POS_MIN.get(pos, 0)
        prob_xi += pulp.lpSum([xi_player_vars[i] for i in selected_squad_df.index if selected_squad_df.loc[i, 'position'] == pos]) <= STARTING_XI_POS_MAX.get(pos, SQUAD_POSITIONS[pos])

    prob_xi.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob_xi.status] != 'Optimal':
        return {"error": f"Kunde inte hitta en optimal startelva. Status: {pulp.LpStatus[prob_xi.status]}"}

    starting_xi_df = selected_squad_df.loc[[i for i in selected_squad_df.index if xi_player_vars[i].varValue == 1]].sort_values(by=['position', 'adjusted_expected_points'], ascending=[True, False])

    # --- Steg 3: Förbered resultat ---
    bench_indices = [i for i in selected_squad_df.index if i not in starting_xi_df.index]
    bench_df = selected_squad_df.loc[bench_indices]
    bench_outfield_sorted = bench_df[bench_df['position'] != 'GKP'].sort_values(by='adjusted_expected_points', ascending=False)
    final_bench_df = pd.concat([bench_outfield_sorted, bench_df[bench_df['position'] == 'GKP']])
    
    sorted_xi_for_captaincy = starting_xi_df.sort_values(by='adjusted_expected_points', ascending=False)
    
    result_columns = ['name', 'team', 'position', 'price', 'adjusted_expected_points', 'next_opponent', 'is_home']
    
    captain, vice_captain = None, None
    if not sorted_xi_for_captaincy.empty:
        captain = sorted_xi_for_captaincy.iloc[0][result_columns].to_dict()
        if len(sorted_xi_for_captaincy) > 1:
            vice_captain = sorted_xi_for_captaincy.iloc[1][result_columns].to_dict()

    def format_player_list(df_to_format):
        player_list = df_to_format[result_columns].to_dict(orient='records')
        for player in player_list:
            player['expected_points'] = player.pop('adjusted_expected_points')
        return player_list

    result_starting_xi = format_player_list(starting_xi_df)
    result_bench = format_player_list(final_bench_df)

    if captain: captain['expected_points'] = captain.pop('adjusted_expected_points')
    if vice_captain: vice_captain['expected_points'] = vice_captain.pop('adjusted_expected_points')

    summary = {
        "squad_total_cost": round(selected_squad_df['price'].sum(), 2),
        "xi_total_expected_points": round(starting_xi_df['adjusted_expected_points'].sum(), 2),
        "strategy_used": strategy, "captain": captain, "vice_captain": vice_captain
    }
    
    return {
        "optimal_starting_xi": result_starting_xi,
        "bench": result_bench,
        "summary": summary
    }
