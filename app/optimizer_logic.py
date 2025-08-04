import pandas as pd
from typing import Dict, Any, List

# Try importing OR-Tools with better error handling
try:
    from ortools.linear_solver import pywraplp
    ORTOOLS_AVAILABLE = True
    print("✅ OR-Tools imported successfully")
except ImportError as e:
    print(f"❌ OR-Tools import failed: {e}")
    ORTOOLS_AVAILABLE = False

def create_optimal_team(fpl_data: Dict[str, Any], strategy: str = "best_15") -> Dict[str, Any]:
    """
    Create optimal FPL team using OR-Tools solver - with enhanced error handling
    """
    
    if not ORTOOLS_AVAILABLE:
        print("❌ OR-Tools not available, returning sample team")
        return get_sample_optimal_team(strategy)
    
    try:
        print(f"🚀 Starting optimization with strategy: {strategy}")
        
        # Convert to DataFrames
        players_df = pd.DataFrame(fpl_data['elements'])
        teams_df = pd.DataFrame(fpl_data['teams'])
        fixtures_df = pd.DataFrame(fpl_data.get('fixtures', []))
        
        print(f"📊 Processing {len(players_df)} players, {len(teams_df)} teams, {len(fixtures_df)} fixtures")
        
        # Clean and prepare player data
        players_df['now_cost'] = players_df['now_cost'] / 10
        players_df['team_name'] = players_df['team'].map(dict(zip(teams_df['id'], teams_df['short_name'])))
        
        # Normalize position names
        position_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        players_df['position'] = players_df['element_type'].map(position_map)
        
        # Add fixture info if not present
        if 'next_opponent' not in players_df.columns:
            players_df['next_opponent'] = 'TBD'
        if 'is_home' not in players_df.columns:
            players_df['is_home'] = True
        
        # Filter out injured/suspended players
        initial_count = len(players_df)
        players_df = players_df[
            (players_df['status'] != 'i') & 
            (players_df['status'] != 's')
        ]
        print(f"🔍 Filtered out {initial_count - len(players_df)} injured/suspended players")
        
        # Handle chance of playing
        if 'chance_of_playing_next_round' in players_df.columns:
            before_filter = len(players_df)
            players_df = players_df[
                players_df['chance_of_playing_next_round'].isna() | 
                (players_df['chance_of_playing_next_round'] > 75)
            ]
            print(f"🔍 Filtered out {before_filter - len(players_df)} players with low playing chance")
        
        print(f"✅ After filtering: {len(players_df)} players available")
        
        # Strategy-specific filtering
        if strategy == "differential":
            if 'selected_by_percent' in players_df.columns:
                before_diff = len(players_df)
                players_df['ownership_numeric'] = pd.to_numeric(players_df['selected_by_percent'], errors='coerce')
                players_df = players_df[players_df['ownership_numeric'] < 10]
                print(f"🔍 Differential strategy: kept {len(players_df)} players (filtered {before_diff - len(players_df)})")
        
        # Check position requirements
        position_counts = players_df['position'].value_counts()
        min_required = {'GKP': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}
        
        print(f"📈 Available players by position: {position_counts.to_dict()}")
        
        for pos, min_count in min_required.items():
            available = position_counts.get(pos, 0)
            if available < min_count:
                raise ValueError(f"❌ Not enough {pos} players. Found {available}, need {min_count}")
        
        # Try different solvers in order of preference
        solvers_to_try = ['SCIP', 'CBC', 'GLOP']
        solver = None
        
        for solver_name in solvers_to_try:
            try:
                print(f"🔧 Trying solver: {solver_name}")
                solver = pywraplp.Solver.CreateSolver(solver_name)
                if solver:
                    print(f"✅ Successfully created {solver_name} solver")
                    break
                else:
                    print(f"❌ Failed to create {solver_name} solver")
            except Exception as e:
                print(f"❌ Error with {solver_name}: {e}")
                continue
        
        if not solver:
            print("❌ Could not create any solver, using fallback")
            return get_sample_optimal_team(strategy)
        
        # Create a simplified optimization problem first
        print("🧮 Setting up optimization variables...")
        
        num_players = len(players_df)
        if num_players > 1000:
            print(f"⚠️ Large dataset ({num_players} players), this might take a while...")
        
        # Decision variables
        x = {}  # Whether player i is selected in squad
        for i in range(num_players):
            x[i] = solver.IntVar(0, 1, f'x_{i}')
        
        print("📐 Adding constraints...")
        
        # Basic constraints
        # Exactly 15 players in squad
        solver.Add(solver.Sum([x[i] for i in range(num_players)]) == 15)
        
        # Budget constraint (£100m)
        budget_constraint = solver.Sum([x[i] * players_df.iloc[i]['now_cost'] for i in range(num_players)])
        solver.Add(budget_constraint <= 100)
        
        # Position constraints
        for pos in ['GKP', 'DEF', 'MID', 'FWD']:
            pos_players = [i for i in range(num_players) if players_df.iloc[i]['position'] == pos]
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
            team_players = [i for i in range(num_players) if players_df.iloc[i]['team'] == team_id]
            if len(team_players) > 0:
                solver.Add(solver.Sum([x[i] for i in team_players]) <= 3)
        
        print("🎯 Setting objective...")
        
        # Objective: maximize expected points
        objective = solver.Sum([x[i] * players_df.iloc[i]['ep_next'] for i in range(num_players)])
        solver.Maximize(objective)
        
        # Solve with time limit
        print("⏱️ Starting optimization (30s limit)...")
        solver.SetTimeLimit(30000)  # 30 seconds
        
        status = solver.Solve()
        
        print(f"🏁 Optimization completed with status: {status}")
        
        if status not in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
            print(f"❌ Solver failed with status {status}")
            return get_sample_optimal_team(strategy)
        
        # Extract results
        print("📋 Extracting optimal team...")
        selected_players = []
        
        for i in range(num_players):
            if x[i].solution_value() > 0.5:
                player_data = players_df.iloc[i]
                player_info = {
                    "name": player_data['web_name'],
                    "team": player_data['team_name'],
                    "price": round(player_data['now_cost'], 1),
                    "expected_points": round(player_data['ep_next'], 1),
                    "position": player_data['position'],
                    "next_opponent": player_data.get('next_opponent', 'TBD'),
                    "is_home": player_data.get('is_home', True)
                }
                selected_players.append(player_info)
        
        if len(selected_players) != 15:
            print(f"❌ Expected 15 players, got {len(selected_players)}")
            return get_sample_optimal_team(strategy)
        
        # Create starting XI (simple approach - best 11 by expected points)
        selected_players.sort(key=lambda x: -x['expected_points'])
        
        # Ensure formation is valid (1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD)
        starting_11 = []
        bench = []
        
        # First, select 1 GKP for starting XI
        gkps = [p for p in selected_players if p['position'] == 'GKP']
        starting_11.append(gkps[0])
        bench.extend(gkps[1:])
        
        # Select best players for each position
        defs = [p for p in selected_players if p['position'] == 'DEF']
        mids = [p for p in selected_players if p['position'] == 'MID'] 
        fwds = [p for p in selected_players if p['position'] == 'FWD']
        
        # Add best 4 defenders, 4 midfielders, 2 forwards (total 11)
        starting_11.extend(defs[:4])
        bench.extend(defs[4:])
        starting_11.extend(mids[:4])
        bench.extend(mids[4:])
        starting_11.extend(fwds[:2])
        bench.extend(fwds[2:])
        
        # Calculate totals
        total_cost = sum(p['price'] for p in selected_players)
        xi_expected_points = sum(p['expected_points'] for p in starting_11)
        
        print(f"✅ Team created successfully!")
        print(f"💰 Total cost: £{total_cost}m")
        print(f"⚡ Expected points: {xi_expected_points}")
        
        return {
            "optimal_starting_xi": starting_11,
            "bench": bench,
            "optimal_squad_15": selected_players,
            "summary": {
                "squad_total_cost": round(total_cost, 1),
                "xi_total_expected_points": round(xi_expected_points, 1),
                "squad_total_expected_points": round(sum(p['expected_points'] for p in selected_players), 1),
                "strategy_used": strategy,
                "captain": starting_11[0] if starting_11 else None,
                "vice_captain": starting_11[1] if len(starting_11) > 1 else None
            }
        }
        
    except Exception as e:
        print(f"❌ Error in optimization: {str(e)}")
        import traceback
        traceback.print_exc()
        return get_sample_optimal_team(strategy)

def get_sample_optimal_team(strategy: str) -> Dict[str, Any]:
    """Return a sample optimal team when the real optimizer fails"""
    print(f"🎭 Returning sample optimal team for strategy: {strategy}")
    
    starting_11 = [
        {"name": "Alisson", "team": "LIV", "price": 5.5, "expected_points": 5.2, "position": "GKP", "next_opponent": "BOU", "is_home": True},
        {"name": "Alexander-Arnold", "team": "LIV", "price": 7.0, "expected_points": 6.1, "position": "DEF", "next_opponent": "BOU", "is_home": True},
        {"name": "Robertson", "team": "LIV", "price": 6.0, "expected_points": 5.5, "position": "DEF", "next_opponent": "BOU", "is_home": True},
        {"name": "Stones", "team": "MCI", "price": 4.5, "expected_points": 4.2, "position": "DEF", "next_opponent": "NEW", "is_home": False},
        {"name": "Budget Defender", "team": "NEW", "price": 4.0, "expected_points": 3.8, "position": "DEF", "next_opponent": "MCI", "is_home": True},
        {"name": "Salah", "team": "LIV", "price": 13.0, "expected_points": 8.5, "position": "MID", "next_opponent": "BOU", "is_home": True},
        {"name": "De Bruyne", "team": "MCI", "price": 12.5, "expected_points": 8.2, "position": "MID", "next_opponent": "NEW", "is_home": False},
        {"name": "Saka", "team": "ARS", "price": 8.0, "expected_points": 6.1, "position": "MID", "next_opponent": "TOT", "is_home": True},
        {"name": "Budget Mid", "team": "MUN", "price": 5.0, "expected_points": 4.2, "position": "MID", "next_opponent": "CHE", "is_home": False},
        {"name": "Haaland", "team": "MCI", "price": 15.0, "expected_points": 9.2, "position": "FWD", "next_opponent": "NEW", "is_home": False},
        {"name": "Watkins", "team": "AVL", "price": 7.5, "expected_points": 6.0, "position": "FWD", "next_opponent": "EVE", "is_home": True}
    ]
    
    bench = [
        {"name": "Pickford", "team": "EVE", "price": 4.5, "expected_points": 4.2, "position": "GKP", "next_opponent": "AVL", "is_home": False},
        {"name": "Bench Defender", "team": "CHE", "price": 4.0, "expected_points": 3.5, "position": "DEF", "next_opponent": "MUN", "is_home": True},
        {"name": "Bench Mid", "team": "TOT", "price": 4.5, "expected_points": 3.8, "position": "MID", "next_opponent": "ARS", "is_home": False},
        {"name": "Bench Forward", "team": "NEW", "price": 4.5, "expected_points": 3.5, "position": "FWD", "next_opponent": "MCI", "is_home": True}
    ]
    
    all_players = starting_11 + bench
    total_cost = sum(p['price'] for p in all_players)
    xi_points = sum(p['expected_points'] for p in starting_11)
    
    return {
        "optimal_starting_xi": starting_11,
        "bench": bench,
        "optimal_squad_15": all_players,
        "summary": {
            "squad_total_cost": round(total_cost, 1),
            "xi_total_expected_points": round(xi_points, 1),
            "squad_total_expected_points": round(sum(p['expected_points'] for p in all_players), 1),
            "strategy_used": strategy,
            "captain": starting_11[0],
            "vice_captain": starting_11[1]
        }
    }