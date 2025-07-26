import pandas as pd
from ortools.linear_solver import pywraplp
from typing import Dict, Any, List

def create_optimal_team(fpl_data: Dict[str, Any], strategy: str = "best_15") -> Dict[str, Any]:
    """
    Create optimal FPL team using OR-Tools solver - Fixed for missing fixtures
    """
    
    try:
        # Convert to DataFrames
        players_df = pd.DataFrame(fpl_data['elements'])
        teams_df = pd.DataFrame(fpl_data['teams'])
        fixtures_df = pd.DataFrame(fpl_data.get('fixtures', []))
        
        print(f"Processing {len(players_df)} players, {len(teams_df)} teams, {len(fixtures_df)} fixtures")
        
        # Clean and prepare player data
        players_df['now_cost'] = players_df['now_cost'] / 10
        players_df['team_name'] = players_df['team'].map(dict(zip(teams_df['id'], teams_df['short_name'])))
        
        # Normalize position names
        position_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        players_df['position'] = players_df['element_type'].map(position_map)
        
        # Get next fixture for each team (safer version)
        def get_next_fixture(team_id):
            try:
                if len(fixtures_df) == 0:
                    # No fixtures available, return default
                    return 'TBD', True
                
                upcoming = fixtures_df[
                    ((fixtures_df['team_h'] == team_id) | (fixtures_df['team_a'] == team_id)) &
                    (fixtures_df.get('finished', True) == False)
                ]
                
                if len(upcoming) > 0:
                    upcoming = upcoming.sort_values('event') if 'event' in upcoming.columns else upcoming
                    fixture = upcoming.iloc[0]
                    is_home = fixture.get('team_h', team_id) == team_id
                    opponent_id = fixture.get('team_a', 1) if is_home else fixture.get('team_h', 1)
                    
                    # Find opponent name
                    opponent_row = teams_df[teams_df['id'] == opponent_id]
                    opponent_name = opponent_row['short_name'].values[0] if len(opponent_row) > 0 else 'TBD'
                    return opponent_name, is_home
                return 'TBD', True
            except Exception as e:
                print(f"Error getting fixture for team {team_id}: {e}")
                return 'TBD', True
        
        # Add fixture info safely
        fixture_info = players_df['team'].apply(get_next_fixture)
        players_df['next_opponent'] = [info[0] for info in fixture_info]
        players_df['is_home'] = [info[1] for info in fixture_info]
        
        # Filter out injured/suspended players
        players_df = players_df[
            (players_df['status'] != 'i') & 
            (players_df['status'] != 's')
        ]
        
        # Handle chance of playing (might not exist in custom data)
        if 'chance_of_playing_next_round' in players_df.columns:
            players_df = players_df[
                players_df['chance_of_playing_next_round'].isna() | 
                (players_df['chance_of_playing_next_round'] > 75)
            ]
        
        print(f"After filtering: {len(players_df)} players available")
        
        # Select players based on strategy
        if strategy == "differential":
            # Only include players owned by less than 10%
            if 'selected_by_percent' in players_df.columns:
                players_df['ownership_numeric'] = pd.to_numeric(players_df['selected_by_percent'], errors='coerce')
                players_df = players_df[players_df['ownership_numeric'] < 10]
        
        # Ensure we have enough players for each position
        position_counts = players_df['position'].value_counts()
        min_required = {'GKP': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}
        
        print(f"Available players by position: {position_counts.to_dict()}")
        
        for pos, min_count in min_required.items():
            available = position_counts.get(pos, 0)
            if available < min_count:
                raise ValueError(f"Not enough {pos} players available after filtering. Found {available}, need {min_count}")
        
        # Create optimization solver
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            raise Exception("Could not create solver")
        
        # Decision variables
        num_players = len(players_df)
        x = {}  # Whether player i is selected in squad
        for i in range(num_players):
            x[i] = solver.IntVar(0, 1, f'player_{i}')
        
        # Starting XI and captain variables
        captain = {}
        vice_captain = {}
        starting_xi = {}
        for i in range(num_players):
            captain[i] = solver.IntVar(0, 1, f'captain_{i}')
            vice_captain[i] = solver.IntVar(0, 1, f'vice_captain_{i}')
            starting_xi[i] = solver.IntVar(0, 1, f'starting_xi_{i}')
        
        # Constraints
        
        # Exactly 15 players in squad
        solver.Add(solver.Sum([x[i] for i in range(num_players)]) == 15)
        
        # Budget constraint (£100m)
        solver.Add(
            solver.Sum([x[i] * players_df.iloc[i]['now_cost'] for i in range(num_players)]) <= 100
        )
        
        # Position constraints for squad
        for pos in ['GKP', 'DEF', 'MID', 'FWD']:
            pos_players = players_df[players_df['position'] == pos].index
            if pos == 'GKP':
                solver.Add(solver.Sum([x[i] for i in pos_players]) == 2)
            elif pos == 'DEF':
                solver.Add(solver.Sum([x[i] for i in pos_players]) == 5)
            elif pos == 'MID':
                solver.Add(solver.Sum([x[i] for i in pos_players]) == 5)
            elif pos == 'FWD':
                solver.Add(solver.Sum([x[i] for i in pos_players]) == 3)
        
        # Max 3 players per team
        for team_id in players_df['team'].unique():
            team_players = players_df[players_df['team'] == team_id].index
            solver.Add(solver.Sum([x[i] for i in team_players]) <= 3)
        
        # Starting XI constraints
        solver.Add(solver.Sum([starting_xi[i] for i in range(num_players)]) == 11)
        
        # Starting XI must be from selected squad
        for i in range(num_players):
            solver.Add(starting_xi[i] <= x[i])
        
        # Formation constraints for starting XI
        gkp_indices = players_df[players_df['position'] == 'GKP'].index
        def_indices = players_df[players_df['position'] == 'DEF'].index
        mid_indices = players_df[players_df['position'] == 'MID'].index
        fwd_indices = players_df[players_df['position'] == 'FWD'].index
        
        # Exactly 1 GKP in starting XI
        solver.Add(solver.Sum([starting_xi[i] for i in gkp_indices]) == 1)
        
        # 3-5 defenders
        solver.Add(solver.Sum([starting_xi[i] for i in def_indices]) >= 3)
        solver.Add(solver.Sum([starting_xi[i] for i in def_indices]) <= 5)
        
        # 2-5 midfielders  
        solver.Add(solver.Sum([starting_xi[i] for i in mid_indices]) >= 2)
        solver.Add(solver.Sum([starting_xi[i] for i in mid_indices]) <= 5)
        
        # 1-3 forwards
        solver.Add(solver.Sum([starting_xi[i] for i in fwd_indices]) >= 1)
        solver.Add(solver.Sum([starting_xi[i] for i in fwd_indices]) <= 3)
        
        # Captain constraints
        solver.Add(solver.Sum([captain[i] for i in range(num_players)]) == 1)
        solver.Add(solver.Sum([vice_captain[i] for i in range(num_players)]) == 1)
        
        # Captain and vice must be in starting XI
        for i in range(num_players):
            solver.Add(captain[i] <= starting_xi[i])
            solver.Add(vice_captain[i] <= starting_xi[i])
            solver.Add(captain[i] + vice_captain[i] <= 1)  # Can't be both
        
        # Strategy-specific adjustments
        if strategy == "defensive":
            position_weights = {'GKP': 1.5, 'DEF': 1.3, 'MID': 1.0, 'FWD': 0.9}
        elif strategy == "offensive":
            position_weights = {'GKP': 0.9, 'DEF': 0.9, 'MID': 1.1, 'FWD': 1.3}
        else:
            position_weights = {'GKP': 1.0, 'DEF': 1.0, 'MID': 1.0, 'FWD': 1.0}
        
        # Add constraint for cheap bench in best_11_cheap_bench strategy
        if strategy == "best_11_cheap_bench":
            # Create bench indicator variables
            bench = {}
            for i in range(num_players):
                bench[i] = solver.IntVar(0, 1, f'bench_{i}')
                # Player is on bench if selected but not in starting XI
                solver.Add(bench[i] == x[i] - starting_xi[i])
            
            # Limit total bench cost to encourage cheap bench
            max_bench_cost = 18.0  # 4 players at average 4.5m each
            solver.Add(
                solver.Sum([bench[i] * players_df.iloc[i]['now_cost'] for i in range(num_players)]) <= max_bench_cost
            )
        
        # Objective function based on strategy
        if strategy == "best_11_cheap_bench":
            # For best_11_cheap_bench: Focus entirely on maximizing starting XI quality
            objective = solver.Sum([
                starting_xi[i] * players_df.iloc[i]['ep_next'] * 
                position_weights.get(players_df.iloc[i]['position'], 1.0)
                for i in range(num_players)
            ])
        elif strategy == "enabling":
            # Balance points with budget efficiency
            objective = solver.Sum([
                x[i] * (players_df.iloc[i]['ep_next'] - 0.5 * players_df.iloc[i]['now_cost'])
                for i in range(num_players)
            ])
        else:
            # Standard: maximize total expected points of squad
            objective = solver.Sum([
                x[i] * players_df.iloc[i]['ep_next'] * 
                position_weights.get(players_df.iloc[i]['position'], 1.0)
                for i in range(num_players)
            ])
        
        solver.Maximize(objective)
        
        # Solve with time limit
        solver.SetTimeLimit(30000)  # 30 seconds
        print("Starting optimization...")
        status = solver.Solve()
        
        if status not in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
            raise Exception(f"Solver could not find a solution. Status: {status}")
        
        print(f"Optimization completed with status: {status}")
        
        # Extract results
        selected_players = []
        captain_player = None
        
        for i in range(num_players):
            if x[i].solution_value() > 0.5:
                player_data = players_df.iloc[i]
                player_info = {
                    "name": player_data['web_name'],
                    "team": player_data['team_name'],
                    "price": round(player_data['now_cost'], 1),
                    "expected_points": round(player_data['ep_next'], 1),
                    "position": player_data['position'],
                    "next_opponent": player_data['next_opponent'],
                    "is_home": player_data['is_home'],
                    "is_starting": starting_xi[i].solution_value() > 0.5
                }
                selected_players.append(player_info)
                
                if captain[i].solution_value() > 0.5:
                    captain_player = player_info.copy()
        
        # Separate starting XI and bench
        starting_11 = [p for p in selected_players if p['is_starting']]
        bench = [p for p in selected_players if not p['is_starting']]
        
        # Sort by position and points
        position_order = {'GKP': 0, 'DEF': 1, 'MID': 2, 'FWD': 3}
        starting_11.sort(key=lambda x: (position_order.get(x['position'], 4), -x['expected_points']))
        bench.sort(key=lambda x: -x['expected_points'])
        
        # Calculate totals
        total_cost = sum(p['price'] for p in selected_players)
        xi_expected_points = sum(p['expected_points'] for p in starting_11)
        
        # Remove is_starting flag from output
        for player in starting_11 + bench:
            player.pop('is_starting', None)
        
        # Also include the full squad for compatibility
        optimal_squad_15 = starting_11 + bench
        
        print(f"Successfully created team: {len(starting_11)} starters, {len(bench)} bench")
        print(f"Total cost: £{total_cost}m, Expected points: {xi_expected_points}")
        
        return {
            "optimal_starting_xi": starting_11,
            "bench": bench,
            "optimal_squad_15": optimal_squad_15,
            "summary": {
                "squad_total_cost": round(total_cost, 1),
                "xi_total_expected_points": round(xi_expected_points, 1),
                "squad_total_expected_points": round(sum(p['expected_points'] for p in optimal_squad_15), 1),
                "strategy_used": strategy,
                "captain": captain_player,
                "vice_captain": starting_11[1] if len(starting_11) > 1 else None
            }
        }
        
    except Exception as e:
        print(f"Error in create_optimal_team: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Error creating optimal team: {str(e)}")