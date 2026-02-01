# =============================================================================
# MASTER AGENT RUNNER - BIAS-ONLY TRADING DESK
# =============================================================================
# This script runs ALL agents and produces a unified dashboard report.
#
# It does NOT make trading decisions.
# It does NOT suggest trades.
# It only collects and displays agent outputs for human synthesis.
#
# The human reads this dashboard and decides:
#   1. What is the current bias? (BULLISH / BEARISH / NEUTRAL / DO_NOT_TRADE)
#   2. Should I act or stand down?
# =============================================================================

# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------
import json
import os
import sys
from datetime import datetime, timezone

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all agents
from agents.regime_classifier import RegimeClassifier
from agents.structure_mapper import StructureMapper
from agents.momentum_reader import MomentumReader
from agents.volatility_assessor import VolatilityAssessor
from agents.session_clock import SessionClock
from agents.risk_calculator import RiskCalculator
from agents.recency_check import RecencyCheck

# Import fake data generator for testing
from data.fake_data_generator import FakeDataGenerator

# Import settings
from config.settings import OUTPUT_FOLDER, INSTRUMENT

# -----------------------------------------------------------------------------
# BIAS MATRIX LOGIC
# -----------------------------------------------------------------------------
def calculate_bias(regime, momentum, volatility, session):
    """
    Calculate the trading bias based on agent outputs.
    
    This implements the Bias Matrix from the architecture document.
    
    Returns one of:
    - BULLISH_BIAS
    - BEARISH_BIAS
    - NEUTRAL
    - DO_NOT_TRADE
    """
    # First check for DO_NOT_TRADE conditions
    if regime == "CHAOS":
        return "DO_NOT_TRADE"
    
    if volatility == "EXTREME":
        return "DO_NOT_TRADE"
    
    if session in ["OFF_HOURS"]:
        return "DO_NOT_TRADE"
    
    # Check for contradictions (regime vs momentum)
    if regime == "TREND_UP" and momentum == "ACCELERATING_SHORT":
        return "DO_NOT_TRADE"
    
    if regime == "TREND_DOWN" and momentum == "ACCELERATING_LONG":
        return "DO_NOT_TRADE"
    
    if regime == "RANGE" and momentum in ["ACCELERATING_LONG", "ACCELERATING_SHORT"]:
        return "DO_NOT_TRADE"
    
    # Calculate base bias from regime + momentum
    base_bias = "NEUTRAL"
    
    if regime == "TREND_UP":
        if momentum == "ACCELERATING_LONG":
            base_bias = "BULLISH_BIAS"
        elif momentum == "NEUTRAL":
            base_bias = "BULLISH_BIAS_WEAK"
        elif momentum == "DECELERATING":
            base_bias = "NEUTRAL"
    
    elif regime == "TREND_DOWN":
        if momentum == "ACCELERATING_SHORT":
            base_bias = "BEARISH_BIAS"
        elif momentum == "NEUTRAL":
            base_bias = "BEARISH_BIAS_WEAK"
        elif momentum == "DECELERATING":
            base_bias = "NEUTRAL"
    
    elif regime == "RANGE":
        base_bias = "NEUTRAL"
    
    # Modify by volatility
    if volatility == "ELEVATED":
        if base_bias in ["BULLISH_BIAS", "BEARISH_BIAS"]:
            base_bias = "NEUTRAL"
    
    # Modify by session
    if session == "SESSION_CLOSE_30MIN":
        return "DO_NOT_TRADE"
    
    if session == "ASIA" and base_bias in ["BULLISH_BIAS", "BEARISH_BIAS"]:
        base_bias = base_bias + "_WEAK" if "_WEAK" not in base_bias else base_bias
    
    return base_bias


def check_synthesis_forbidden(reports):
    """
    Check if synthesis is forbidden based on agent outputs.
    
    Returns a tuple: (is_forbidden, reason)
    """
    regime = reports['regime']['output']['regime']
    volatility = reports['volatility']['output']['state']
    spread = reports['volatility']['output']['spread_status']
    session = reports['session']['output']['active_session']
    boundary = reports['session']['output']['boundary_flag']
    
    # Check forbidden conditions
    if regime == "CHAOS":
        return (True, "REGIME = CHAOS")
    
    if volatility == "EXTREME":
        return (True, "VOLATILITY = EXTREME")
    
    if spread == "WIDE" or spread == "EXTREME":
        return (True, f"SPREAD = {spread}")
    
    if session == "OFF_HOURS":
        return (True, "SESSION = OFF_HOURS")
    
    if boundary == "SESSION_CLOSE_30MIN":
        return (True, "SESSION CLOSING IN 30 MIN")
    
    # Check for contradictions
    momentum = reports['momentum']['output']['state']
    
    if regime == "TREND_UP" and momentum == "ACCELERATING_SHORT":
        return (True, "CONTRADICTION: TREND_UP vs ACCELERATING_SHORT")
    
    if regime == "TREND_DOWN" and momentum == "ACCELERATING_LONG":
        return (True, "CONTRADICTION: TREND_DOWN vs ACCELERATING_LONG")
    
    return (False, None)


# -----------------------------------------------------------------------------
# DASHBOARD DISPLAY
# -----------------------------------------------------------------------------
def print_dashboard(reports, bias, forbidden_status):
    """
    Print a human-readable dashboard of all agent outputs.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("\n")
    print("=" * 70)
    print("               BIAS-ONLY TRADING DESK DASHBOARD")
    print("=" * 70)
    print(f"  Instrument: {INSTRUMENT}                    Time: {timestamp}")
    print("=" * 70)
    
    # SYNTHESIS STATUS
    is_forbidden, reason = forbidden_status
    if is_forbidden:
        print("\n  ╔═══════════════════════════════════════════════════════════════╗")
        print("  ║              ⛔ SYNTHESIS FORBIDDEN ⛔                        ║")
        print(f"  ║  Reason: {reason:<52} ║")
        print("  ║  ACTION: DO NOT TRADE. Close platform or wait.               ║")
        print("  ╚═══════════════════════════════════════════════════════════════╝")
    else:
        print("\n  ╔═══════════════════════════════════════════════════════════════╗")
        print(f"  ║              BIAS: {bias:<43} ║")
        print("  ╚═══════════════════════════════════════════════════════════════╝")
    
    # REGIME
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ REGIME CLASSIFIER                                               │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    r = reports['regime']['output']
    print(f"  │  State: {r['regime']:<15} Duration: {r['duration_candles']} candles              │")
    print(f"  │  Prior: {r['prior_regime']:<15} Transitions: {r['transitions_24h']}                       │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # STRUCTURE
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ STRUCTURE MAPPER                                                │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    s = reports['structure']['output']
    print(f"  │  Current Price: {s['current_price']:<20}                        │")
    print("  │  Levels ABOVE:                                                  │")
    if s['levels_above']:
        for lvl in s['levels_above'][:2]:  # Show top 2
            print(f"  │    {lvl['price']:<10} [{lvl['strength']:<5}] [{lvl['validity']:<7}] +{lvl['distance_pips']:.0f} pips  │")
    else:
        print("  │    None found                                                  │")
    print("  │  Levels BELOW:                                                  │")
    if s['levels_below']:
        for lvl in s['levels_below'][:2]:  # Show top 2
            print(f"  │    {lvl['price']:<10} [{lvl['strength']:<5}] [{lvl['validity']:<7}] -{lvl['distance_pips']:.0f} pips  │")
    else:
        print("  │    None found                                                  │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # MOMENTUM
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ MOMENTUM READER                                                 │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    m = reports['momentum']['output']
    print(f"  │  State: {m['state']:<20} Duration: {m['state_duration_candles']} candles         │")
    print(f"  │  Prior: {m['prior_state']:<20} Velocity: {m['velocity_normalized']:<10}        │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # VOLATILITY
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ VOLATILITY ASSESSOR                                             │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    v = reports['volatility']['output']
    print(f"  │  State: {v['state']:<12} ATR: {v['atr_current_pips']} pips (baseline: {v['atr_baseline_pips']})    │")
    print(f"  │  Spread: {v['spread_status']:<12} ({v['spread_pips']} pips)                          │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # SESSION
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ SESSION CLOCK                                                   │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    ss = reports['session']['output']
    print(f"  │  Active: {ss['active_session']:<15} Age: {ss['session_age']:<20}   │")
    print(f"  │  Closes In: {ss['time_to_close']:<12} Flag: {ss['boundary_flag']:<20} │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # RISK
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ RISK CALCULATOR                                                 │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    rk = reports['risk']['output']
    print(f"  │  Equity: ${rk['equity']:,.2f}         Risk/Trade: ${rk['risk_per_trade_dollars']:.2f} ({rk['risk_per_trade_percent']}%)  │")
    print(f"  │  Daily P&L: ${rk['daily_pnl']:.2f}        Remaining: ${rk['daily_limit_remaining']:.2f}             │")
    print(f"  │  Can Open: {rk['can_open_new_position']}           Positions: {rk['open_positions']}/{rk['max_concurrent']}                │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # RECENCY CHECK
    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │ RECENCY CHECK (Pre-Action)                                      │")
    print("  ├─────────────────────────────────────────────────────────────────┤")
    rc = reports['recency']['output']
    print(f"  │  Ticks: {rc['tick_direction']['up']} UP / {rc['tick_direction']['down']} DOWN      Net: {rc['net_movement_pips']} pips          │")
    print(f"  │  Bias: {rc['tick_bias']:<12} Spread: {rc['spread_stability']:<12} Velocity: {rc['velocity_trend']:<10}│")
    imp = rc['last_impulse']
    print(f"  │  Last Impulse: {imp['direction']} ({imp['strength']}) {imp['size_pips']} pips, {imp['ticks_ago']} ticks ago      │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    
    # HUMAN ACTION SECTION
    print("\n  ╔═══════════════════════════════════════════════════════════════╗")
    print("  ║                     HUMAN SYNTHESIS REQUIRED                   ║")
    print("  ╠═══════════════════════════════════════════════════════════════╣")
    
    if is_forbidden:
        print("  ║  ⛔ ACTION: STAND DOWN                                         ║")
        print("  ║     Synthesis is forbidden. Do not trade.                     ║")
    elif bias == "DO_NOT_TRADE":
        print("  ║  ⛔ ACTION: STAND DOWN                                         ║")
        print("  ║     Conditions do not support trading.                        ║")
    elif bias == "NEUTRAL":
        print("  ║  ⏸️  ACTION: WAIT                                               ║")
        print("  ║     No directional edge. Do not seek trades.                  ║")
    elif "BULLISH" in bias:
        print("  ║  📈 BIAS: BULLISH                                              ║")
        print("  ║     Conditions lean toward long exposure.                     ║")
        print("  ║     Human may look for long setups if structure supports.    ║")
    elif "BEARISH" in bias:
        print("  ║  📉 BIAS: BEARISH                                              ║")
        print("  ║     Conditions lean toward short exposure.                    ║")
        print("  ║     Human may look for short setups if structure supports.   ║")
    
    print("  ╚═══════════════════════════════════════════════════════════════╝")
    print("\n" + "=" * 70)
    print("  Reports saved to: outputs/")
    print("=" * 70 + "\n")


# -----------------------------------------------------------------------------
# SAVE MASTER REPORT
# -----------------------------------------------------------------------------
def save_master_report(reports, bias, forbidden_status):
    """
    Save all agent reports into a single master JSON file.
    """
    is_forbidden, reason = forbidden_status
    
    master_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instrument": INSTRUMENT,
        "synthesis": {
            "bias": bias,
            "synthesis_forbidden": is_forbidden,
            "forbidden_reason": reason
        },
        "agents": {
            "regime": reports['regime'],
            "structure": reports['structure'],
            "momentum": reports['momentum'],
            "volatility": reports['volatility'],
            "session": reports['session'],
            "risk": reports['risk'],
            "recency": reports['recency']
        }
    }
    
    # Save to outputs folder
    base_path = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_path, OUTPUT_FOLDER)
    
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    filepath = os.path.join(output_path, "master_report.json")
    
    with open(filepath, 'w') as f:
        json.dump(master_report, f, indent=2)
    
    return filepath


# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
def run_all_agents():
    """
    Run all agents and produce the dashboard.
    """
    print("\n" + "=" * 70)
    print("  INITIALIZING BIAS-ONLY TRADING DESK...")
    print("=" * 70)
    
    # Create fake data generator
    print("\n  Generating market data...")
    generator = FakeDataGenerator(instrument="XAU/USD", starting_price=2650.00)
    
    # Generate candle history
    candles = generator.generate_candle_history(num_candles=100, timeframe_minutes=5)
    print(f"  Generated {len(candles)} candles")
    
    # Generate tick data
    for _ in range(60):
        generator.generate_tick()
    ticks = generator.get_recent_ticks(50)
    print(f"  Generated {len(ticks)} ticks")
    
    # Get current spread
    quote = generator.get_current_quote()
    current_spread = quote['spread']
    
    # Initialize reports dictionary
    reports = {}
    
    # Run each agent
    print("\n  Running agents...")
    
    # 1. Regime Classifier
    print("    [1/7] Regime Classifier...")
    regime_agent = RegimeClassifier()
    reports['regime'] = regime_agent.classify(candles)
    regime_agent.save_report(reports['regime'])
    
    # 2. Structure Mapper
    print("    [2/7] Structure Mapper...")
    structure_agent = StructureMapper()
    reports['structure'] = structure_agent.map_structure(candles)
    structure_agent.save_report(reports['structure'])
    
    # 3. Momentum Reader
    print("    [3/7] Momentum Reader...")
    momentum_agent = MomentumReader()
    reports['momentum'] = momentum_agent.read_momentum(candles)
    momentum_agent.save_report(reports['momentum'])
    
    # 4. Volatility Assessor
    print("    [4/7] Volatility Assessor...")
    volatility_agent = VolatilityAssessor()
    reports['volatility'] = volatility_agent.assess(candles, current_spread)
    volatility_agent.save_report(reports['volatility'])
    
    # 5. Session Clock
    print("    [5/7] Session Clock...")
    session_agent = SessionClock()
    reports['session'] = session_agent.check_session()
    session_agent.save_report(reports['session'])
    
    # 6. Risk Calculator
    print("    [6/7] Risk Calculator...")
    risk_agent = RiskCalculator(equity=10000.00, daily_pnl=-50.00, open_positions=0)
    reports['risk'] = risk_agent.calculate(stop_distance_pips=50)
    risk_agent.save_report(reports['risk'])
    
    # 7. Recency Check
    print("    [7/7] Recency Check...")
    recency_agent = RecencyCheck()
    reports['recency'] = recency_agent.check(ticks)
    recency_agent.save_report(reports['recency'])
    
    print("  All agents complete!")
    
    # Calculate bias
    regime = reports['regime']['output']['regime']
    momentum = reports['momentum']['output']['state']
    volatility = reports['volatility']['output']['state']
    session = reports['session']['output']['active_session']
    
    bias = calculate_bias(regime, momentum, volatility, session)
    
    # Check if synthesis is forbidden
    forbidden_status = check_synthesis_forbidden(reports)
    
    # Save master report
    save_master_report(reports, bias, forbidden_status)
    
    # Display dashboard
    print_dashboard(reports, bias, forbidden_status)
    
    return reports, bias, forbidden_status


# -----------------------------------------------------------------------------
# RUN
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    run_all_agents()
