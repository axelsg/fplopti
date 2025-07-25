import pandas as pd
import pulp
import numpy as np
import os
import logging

# Konfigurera logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_fpl_optimizer(
    strategy: str = 'best_15',
    defensive_weight: float = 1.2,
    offensive_weight: float = 1.2,
    differential_factor: float = 0.05,
    min_cheap_players: int = 4
):
    """
    Kör hela optimeringsprocessen med förbättrade strategier och bättre felhantering.
    """
    # --- FPL Regler och konstanter ---
    BUDGET = 100.0
    SQUAD_POSITIONS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    TOTAL_SQUAD_PLAYERS = 15
    MAX_PLAYERS_PER_CLUB = 3
    STARTING_XI_POS_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
    STARTING_XI_POS_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}
    TOTAL_STARTING_XI_PLAYERS = 11
    
    # Förbättrade priströsklar baserat på verklig FPL-data
    CHEAP_PLAYER_THRESHOLDS = {"GKP": 4.0, "DEF": 4.0, "MID": 4.5, "FWD": 4.5}

    try:
        script_dir = os.path.dirname(__file__)
        data_path = os.path.join(script_dir, 'fpl_data.json')
        
        if not os.path.exists(data_path):
            logger.error(f"Datafil saknas: {data_path}")
            return {"error": "Datakällan fpl_data.json hittades inte i app-mappen."}
            
        df = pd.read_json(data_path)
        logger.info(f"Laddade {len(df)} spelare från datafilen")
        
    except Exception as e:
        logger.error(f"Fel vid inläsning av data: {e}")
        return {"error": f"Kunde inte läsa datakällan: {str(e)}"}
    
    # --- Validera och förbered data ---
    if df.empty:
        return {"error": "Ingen spelardata tillgänglig"}
    
    # Kontrollera att alla nödvändiga kolumner finns
    required_columns = ['position', 'expected_points', 'price', 'team', 'name']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return {"error": f"Saknade kolumner i data: {missing_columns}"}
    
    df['position'] = pd.Categorical(df['position'], categories=SQUAD_POSITIONS.keys(), ordered=True)
    df['adjusted_expected_points'] = df['expected_points'].copy()
    
    # Hantera skador och spelstatus
    if 'status' in df.columns:
        df.loc[df['status'].isin(['i', 's']), 'adjusted_expected_points'] = 0
    
    if 'chance_of_playing_this_round' in df.columns:
        df.loc[(df['chance_of_playing_this_round'] < 100) & (~df['status'].isin(['i', 's'])), 'adjusted_expected_points'] *= (df['chance_of_playing_this_round'] / 100.0)
    
    df['adjusted_expected_points'] = df['adjusted_expected_points'].fillna(0)
    
    # Fyll i saknade värden
    df['next_opponent'] = df.get('next_opponent', 'N/A').fillna('N/A')
    df['is_home'] = df.get('is_home', False).fillna(False)
    
    # Validera att vi har tillräckligt med spelare per position
    position_counts = df['position'].value_counts()
    for pos, required_count in SQUAD_POSITIONS.items():
        if position_counts.get(pos, 0) < required_count:
            return {"error": f"Otillräckligt antal spelare för position {pos}: behöver {required_count}, har {position_counts.get(pos, 0)}"}

    try:
        if strategy == 'best_11_cheap_bench':
            return _optimize_best_11_cheap_bench(df, BUDGET, SQUAD_POSITIONS, MAX_PLAYERS_PER_CLUB, 
                                                STARTING_XI_POS_MIN, STARTING_XI_POS_MAX, 
                                                TOTAL_STARTING_XI_PLAYERS, TOTAL_SQUAD_PLAYERS,
                                                CHEAP_PLAYER_THRESHOLDS)
        else:
            return _optimize_traditional_approach(df, strategy, BUDGET, SQUAD_POSITIONS, MAX_PLAYERS_PER_CLUB,
                                                STARTING_XI_POS_MIN, STARTING_XI_POS_MAX,
                                                TOTAL_STARTING_XI_PLAYERS, TOTAL_SQUAD_PLAYERS,
                                                CHEAP_PLAYER_THRESHOLDS, defensive_weight, offensive_weight,
                                                differential_factor, min_cheap_players)
    except Exception as e:
        logger.error(f"Optimeringfel: {e}")
        return {"error": f"Optimeringsfel: {str(e)}"}


def _optimize_best_11_cheap_bench(df, BUDGET, SQUAD_POSITIONS, MAX_PLAYERS_PER_CLUB, 
                                 STARTING_XI_POS_MIN, STARTING_XI_POS_MAX, 
                                 TOTAL_STARTING_XI_PLAYERS, TOTAL_SQUAD_PLAYERS,
                                 CHEAP_PLAYER_THRESHOLDS):
    """
    Förbättrad implementering av best_11_cheap_bench strategin.
    Använder en tvåstegsapproach som är mer robust än den tidigare enstegsmetoden.
    """
    logger.info("Kör best_11_cheap_bench optimering")
    
    # Steg 1: Hitta billigaste möjliga bänkspelare för varje position
    bench_positions = {"GKP": 1, "DEF": 2, "MID": 2, "FWD": 0}  # Typisk bänksammansättning
    
    # Identifiera billigaste spelare per position för bänken
    cheapest_bench_players = []
    remaining_budget = BUDGET
    
    for pos, bench_count in bench_positions.items():
        if bench_count > 0:
            pos_players = df[df['position'] == pos].sort_values('price')
            if len(pos_players) < bench_count:
                return {"error": f"Inte tillräckligt med spelare för bänkposition {pos}"}
            
            for i in range(bench_count):
                cheapest_bench_players.append(pos_players.iloc[i])
                remaining_budget -= pos_players.iloc[i]['price']
    
    # Steg 2: Optimera startelvan med återstående budget
    available_players = df[~df.index.isin([p.name for p in cheapest_bench_players])]
    
    prob = pulp.LpProblem("FPL_Best_11_Optimization", pulp.LpMaximize)
    xi_vars = pulp.LpVariable.dicts("XIPlayer", available_players.index, cat='Binary')
    
    # Objektiv: Maximera poäng för startelvan
    prob += pulp.lpSum([xi_vars[i] * available_players.loc[i, 'adjusted_expected_points'] for i in available_players.index])
    
    # Budgetbegränsning för startelvan
    prob += pulp.lpSum([xi_vars[i] * available_players.loc[i, 'price'] for i in available_players.index]) <= remaining_budget
    
    # Antal spelare i startelvan
    prob += pulp.lpSum(xi_vars) == TOTAL_STARTING_XI_PLAYERS
    
    # Positionsbegränsningar för startelvan
    for pos in SQUAD_POSITIONS.keys():
        pos_players = available_players[available_players['position'] == pos]
        prob += pulp.lpSum([xi_vars[i] for i in pos_players.index]) >= STARTING_XI_POS_MIN.get(pos, 0)
        prob += pulp.lpSum([xi_vars[i] for i in pos_players.index]) <= STARTING_XI_POS_MAX.get(pos, SQUAD_POSITIONS[pos])
    
    # Lagbegränsningar (måste räkna med bänkspelare också)
    for team in df['team'].unique():
        bench_players_from_team = sum(1 for p in cheapest_bench_players if p['team'] == team)
        team_players_available = available_players[available_players['team'] == team]
        prob += pulp.lpSum([xi_vars[i] for i in team_players_available.index]) <= MAX_PLAYERS_PER_CLUB - bench_players_from_team
    
    # Lös problemet
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    
    if pulp.LpStatus[prob.status] != 'Optimal':
        logger.error(f"Optimering misslyckades: {pulp.LpStatus[prob.status]}")
        return {"error": f"Kunde inte hitta en optimal lösning. Status: {pulp.LpStatus[prob.status]}"}
    
    # Extrahera resultat
    starting_xi_indices = [i for i in available_players.index if xi_vars[i].varValue == 1]
    starting_xi_df = available_players.loc[starting_xi_indices]
    
    # Skapa komplett trupp genom att lägga till bänkspelare
    bench_df = pd.DataFrame(cheapest_bench_players)
    squad_df = pd.concat([starting_xi_df, bench_df], ignore_index=True)
    
    return _format_results(starting_xi_df, bench_df, squad_df, 'best_11_cheap_bench')


def _optimize_traditional_approach(df, strategy, BUDGET, SQUAD_POSITIONS, MAX_PLAYERS_PER_CLUB,
                                  STARTING_XI_POS_MIN, STARTING_XI_POS_MAX,
                                  TOTAL_STARTING_XI_PLAYERS, TOTAL_SQUAD_PLAYERS,
                                  CHEAP_PLAYER_THRESHOLDS, defensive_weight, offensive_weight,
                                  differential_factor, min_cheap_players):
    """
    Traditionell tvåstegsoptimering: först trupp, sedan startelva.
    """
    logger.info(f"Kör {strategy} optimering")
    
    # Steg 1: Optimera trupp
    prob_squad = pulp.LpProblem("FPL_Squad_Optimization", pulp.LpMaximize)
    squad_player_vars = pulp.LpVariable.dicts("SquadPlayer", df.index, cat='Binary')
    
    # Skapa objektivfunktion baserat på strategi
    objective_expr = _create_objective_function(df, squad_player_vars, strategy, 
                                               defensive_weight, offensive_weight, differential_factor)
    prob_squad += objective_expr
    
    # Grundläggande begränsningar
    prob_squad += pulp.lpSum([squad_player_vars[i] * df.loc[i, 'price'] for i in df.index]) <= BUDGET
    prob_squad += pulp.lpSum(squad_player_vars) == TOTAL_SQUAD_PLAYERS
    
    # Positionsbegränsningar
    for pos, count in SQUAD_POSITIONS.items():
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'position'] == pos]) == count
    
    # Lagbegränsningar
    for team in df['team'].unique():
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in df.index if df.loc[i, 'team'] == team]) <= MAX_PLAYERS_PER_CLUB
    
    # Strategispecifika begränsningar
    if strategy == 'enabling':
        cheap_player_indices = [i for i in df.index 
                               if df.loc[i, 'price'] <= CHEAP_PLAYER_THRESHOLDS.get(df.loc[i, 'position'], 99)]
        prob_squad += pulp.lpSum([squad_player_vars[i] for i in cheap_player_indices]) >= min_cheap_players
    
    # Lös truppoptimering
    prob_squad.solve(pulp.PULP_CBC_CMD(msg=0))
    
    if pulp.LpStatus[prob_squad.status] != 'Optimal':
        return {"error": f"Kunde inte hitta en optimal trupp. Status: {pulp.LpStatus[prob_squad.status]}"}
    
    selected_squad_df = df.loc[[i for i in df.index if squad_player_vars[i].varValue == 1]].copy()
    
    # Steg 2: Optimera startelva från vald trupp
    prob_xi = pulp.LpProblem("FPL_Starting_XI_Optimization", pulp.LpMaximize)
    xi_player_vars = pulp.LpVariable.dicts("XIPlayer", selected_squad_df.index, cat='Binary')
    
    prob_xi += pulp.lpSum([xi_player_vars[i] * selected_squad_df.loc[i, 'adjusted_expected_points'] for i in selected_squad_df.index])
    prob_xi += pulp.lpSum(xi_player_vars) == TOTAL_STARTING_XI_PLAYERS
    
    # Positionsbegränsningar för startelva
    for pos in SQUAD_POSITIONS.keys():
        prob_xi += pulp.lpSum([xi_player_vars[i] for i in selected_squad_df.index 
                              if selected_squad_df.loc[i, 'position'] == pos]) >= STARTING_XI_POS_MIN.get(pos, 0)
        prob_xi += pulp.lpSum([xi_player_vars[i] for i in selected_squad_df.index 
                              if selected_squad_df.loc[i, 'position'] == pos]) <= STARTING_XI_POS_MAX.get(pos, SQUAD_POSITIONS[pos])
    
    prob_xi.solve(pulp.PULP_CBC_CMD(msg=0))
    
    if pulp.LpStatus[prob_xi.status] != 'Optimal':
        return {"error": f"Kunde inte hitta en optimal startelva. Status: {pulp.LpStatus[prob_xi.status]}"}
    
    starting_xi_df = selected_squad_df.loc[[i for i in selected_squad_df.index if xi_player_vars[i].varValue == 1]]
    bench_indices = [i for i in selected_squad_df.index if i not in starting_xi_df.index]
    bench_df = selected_squad_df.loc[bench_indices]
    
    return _format_results(starting_xi_df, bench_df, selected_squad_df, strategy)


def _create_objective_function(df, squad_player_vars, strategy, defensive_weight, offensive_weight, differential_factor):
    """
    Skapar objektivfunktion baserat på vald strategi.
    """
    if strategy == 'defensive':
        return pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] * 
                          (defensive_weight if df.loc[i, 'position'] in ['DEF', 'GKP'] else 1.0) 
                          for i in df.index])
    elif strategy == 'offensive':
        return pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] * 
                          (offensive_weight if df.loc[i, 'position'] in ['MID', 'FWD'] else 1.0) 
                          for i in df.index])
    elif strategy == 'differential':
        # Säkerställ att ownership_percentage finns och är numerisk
        if 'ownership_percentage' not in df.columns:
            df['ownership_percentage'] = 50.0  # Standardvärde
        df['ownership_percentage'] = pd.to_numeric(df['ownership_percentage'], errors='coerce').fillna(50.0)
        
        return pulp.lpSum([squad_player_vars[i] * 
                          (df.loc[i, 'adjusted_expected_points'] + 
                           differential_factor * (100 - df.loc[i, 'ownership_percentage'])) 
                          for i in df.index])
    else:  # 'best_15' eller annan standardstrategi
        return pulp.lpSum([squad_player_vars[i] * df.loc[i, 'adjusted_expected_points'] for i in df.index])


def _format_results(starting_xi_df, bench_df, squad_df, strategy):
    """
    Formaterar resultaten för API-respons.
    """
    # Sortera startelva efter position och poäng
    starting_xi_df = starting_xi_df.sort_values(by=['position', 'adjusted_expected_points'], ascending=[True, False])
    
    # Sortera bänk: utespelare efter poäng, sedan målvakt
    bench_outfield = bench_df[bench_df['position'] != 'GKP'].sort_values(by='adjusted_expected_points', ascending=False)
    bench_gkp = bench_df[bench_df['position'] == 'GKP']
    final_bench_df = pd.concat([bench_outfield, bench_gkp])
    
    # Bestäm kapten och vice-kapten
    sorted_xi_for_captaincy = starting_xi_df.sort_values(by='adjusted_expected_points', ascending=False)
    
    result_columns = ['name', 'team', 'position', 'price', 'adjusted_expected_points', 'next_opponent', 'is_home']
    
    captain, vice_captain = None, None
    if not sorted_xi_for_captaincy.empty:
        captain_data = sorted_xi_for_captaincy.iloc[0][result_columns].to_dict()
        captain_data['expected_points'] = captain_data.pop('adjusted_expected_points')
        captain = captain_data
        
        if len(sorted_xi_for_captaincy) > 1:
            vice_captain_data = sorted_xi_for_captaincy.iloc[1][result_columns].to_dict()
            vice_captain_data['expected_points'] = vice_captain_data.pop('adjusted_expected_points')
            vice_captain = vice_captain_data

    def format_player_list(df_to_format):
        """Konverterar DataFrame till lista med rätt kolumnnamn."""
        player_list = df_to_format[result_columns].to_dict(orient='records')
        for player in player_list:
            player['expected_points'] = player.pop('adjusted_expected_points')
        return player_list

    result_starting_xi = format_player_list(starting_xi_df)
    result_bench = format_player_list(final_bench_df)

    summary = {
        "squad_total_cost": round(squad_df['price'].sum(), 2),
        "xi_total_expected_points": round(starting_xi_df['adjusted_expected_points'].sum(), 2),
        "bench_total_expected_points": round(final_bench_df['adjusted_expected_points'].sum(), 2),
        "strategy_used": strategy,
        "captain": captain,
        "vice_captain": vice_captain
    }
    
    logger.info(f"Optimering slutförd: {strategy}, Total kostnad: £{summary['squad_total_cost']}M, XI poäng: {summary['xi_total_expected_points']:.2f}")
    
    return {
        "optimal_starting_xi": result_starting_xi,
        "bench": result_bench,
        "summary": summary
    }