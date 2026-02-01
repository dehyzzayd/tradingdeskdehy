# =============================================================================
# AGENT 7: RECENCY CHECK
# =============================================================================
# This agent analyzes the most recent tick data as a final sanity check.
#
# It answers: "What is happening RIGHT NOW in the last few seconds?"
#
# This is the LAST check before taking action. If this contradicts
# your intended trade direction, you should WAIT.
#
# Outputs:
#   - Tick direction: Count of up ticks vs down ticks
#   - Net movement: Total price change in pips
#   - Spread stability: STABLE, UNSTABLE, or ERRATIC
#   - Velocity trend: INCREASING, STEADY, or DECAYING
#   - Last impulse: Direction and strength of most recent burst
#
# This agent does NOT predict what will happen next.
# This agent only reports what just happened in the last moments.
# =============================================================================

# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------
import json
from datetime import datetime, timezone
import os
import sys

# Add parent folder to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our settings
from config.settings import (
    INSTRUMENT,
    PIP_SIZE,
    RECENCY_TICK_COUNT,
    STALE_DATA_THRESHOLD_SECONDS,
    OUTPUT_FOLDER
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def count_tick_directions(ticks):
    """
    Count how many ticks went up vs down.
    
    Parameters:
    - ticks: List of tick dictionaries with 'mid' price
    
    Returns:
    - Tuple of (up_count, down_count, unchanged_count)
    """
    if len(ticks) < 2:
        return (0, 0, 0)
    
    up_count = 0
    down_count = 0
    unchanged_count = 0
    
    for i in range(1, len(ticks)):
        current = ticks[i].get('mid', 0)
        previous = ticks[i-1].get('mid', 0)
        
        if current > previous:
            up_count += 1
        elif current < previous:
            down_count += 1
        else:
            unchanged_count += 1
    
    return (up_count, down_count, unchanged_count)


def calculate_net_movement(ticks, pip_size):
    """
    Calculate the net price movement across all ticks.
    
    Parameters:
    - ticks: List of tick dictionaries with 'mid' price
    - pip_size: Size of one pip
    
    Returns:
    - Net movement in pips (positive = up, negative = down)
    """
    if len(ticks) < 2:
        return 0.0
    
    first_price = ticks[0].get('mid', 0)
    last_price = ticks[-1].get('mid', 0)
    
    if pip_size == 0:
        return 0.0
    
    movement = (last_price - first_price) / pip_size
    
    return round(movement, 1)


def assess_spread_stability(ticks):
    """
    Assess how stable the spread has been across ticks.
    
    - STABLE: Spread variation < 20%
    - UNSTABLE: Spread variation 20-50%
    - ERRATIC: Spread variation > 50%
    
    Parameters:
    - ticks: List of tick dictionaries with 'spread'
    
    Returns:
    - Stability status string
    """
    if len(ticks) < 2:
        return "STABLE"
    
    spreads = [t.get('spread', 0) for t in ticks]
    spreads = [s for s in spreads if s > 0]  # Filter out zeros
    
    if not spreads:
        return "STABLE"
    
    avg_spread = sum(spreads) / len(spreads)
    
    if avg_spread == 0:
        return "STABLE"
    
    # Calculate variation (max deviation from average)
    max_deviation = max(abs(s - avg_spread) for s in spreads)
    variation_percent = (max_deviation / avg_spread) * 100
    
    if variation_percent < 20:
        return "STABLE"
    elif variation_percent < 50:
        return "UNSTABLE"
    else:
        return "ERRATIC"


def calculate_velocity_trend(ticks, pip_size):
    """
    Determine if price velocity is increasing, steady, or decaying.
    
    Compares velocity in first half vs second half of ticks.
    
    Parameters:
    - ticks: List of tick dictionaries with 'mid' price
    - pip_size: Size of one pip
    
    Returns:
    - Velocity trend string
    """
    if len(ticks) < 10:
        return "STEADY"
    
    half = len(ticks) // 2
    
    # First half velocity
    first_half = ticks[:half]
    if len(first_half) >= 2:
        first_movement = abs(first_half[-1].get('mid', 0) - first_half[0].get('mid', 0))
    else:
        first_movement = 0
    
    # Second half velocity
    second_half = ticks[half:]
    if len(second_half) >= 2:
        second_movement = abs(second_half[-1].get('mid', 0) - second_half[0].get('mid', 0))
    else:
        second_movement = 0
    
    # Compare velocities
    if first_movement == 0:
        if second_movement > 0:
            return "INCREASING"
        else:
            return "STEADY"
    
    ratio = second_movement / first_movement
    
    if ratio > 1.3:
        return "INCREASING"
    elif ratio < 0.7:
        return "DECAYING"
    else:
        return "STEADY"


def find_last_impulse(ticks, pip_size, min_consecutive=3):
    """
    Find the most recent impulse (consecutive moves in same direction).
    
    Parameters:
    - ticks: List of tick dictionaries with 'mid' price
    - pip_size: Size of one pip
    - min_consecutive: Minimum ticks in same direction to count as impulse
    
    Returns:
    - Dictionary with impulse details
    """
    default_result = {
        'direction': 'NONE',
        'strength': 'NONE',
        'ticks_ago': 0,
        'size_pips': 0
    }
    
    if len(ticks) < min_consecutive + 1:
        return default_result
    
    # Look for consecutive moves in same direction
    best_impulse = None
    current_direction = None
    consecutive_count = 0
    impulse_start_idx = 0
    
    for i in range(1, len(ticks)):
        current = ticks[i].get('mid', 0)
        previous = ticks[i-1].get('mid', 0)
        
        if current > previous:
            direction = 'UP'
        elif current < previous:
            direction = 'DOWN'
        else:
            continue  # Skip unchanged
        
        if direction == current_direction:
            consecutive_count += 1
        else:
            # Save previous impulse if it was long enough
            if consecutive_count >= min_consecutive and current_direction:
                start_price = ticks[impulse_start_idx].get('mid', 0)
                end_price = ticks[i-1].get('mid', 0)
                size_pips = abs(end_price - start_price) / pip_size if pip_size > 0 else 0
                
                best_impulse = {
                    'direction': current_direction,
                    'ticks_ago': len(ticks) - i,
                    'size_pips': round(size_pips, 2),
                    'consecutive': consecutive_count
                }
            
            # Start new sequence
            current_direction = direction
            consecutive_count = 1
            impulse_start_idx = i - 1
    
    # Check final sequence
    if consecutive_count >= min_consecutive and current_direction:
        start_price = ticks[impulse_start_idx].get('mid', 0)
        end_price = ticks[-1].get('mid', 0)
        size_pips = abs(end_price - start_price) / pip_size if pip_size > 0 else 0
        
        best_impulse = {
            'direction': current_direction,
            'ticks_ago': 0,
            'size_pips': round(size_pips, 2),
            'consecutive': consecutive_count
        }
    
    if best_impulse is None:
        return default_result
    
    # Determine strength
    if best_impulse['size_pips'] > 1.0:
        strength = 'STRONG'
    elif best_impulse['size_pips'] > 0.5:
        strength = 'MODERATE'
    else:
        strength = 'WEAK'
    
    return {
        'direction': best_impulse['direction'],
        'strength': strength,
        'ticks_ago': best_impulse['ticks_ago'],
        'size_pips': best_impulse['size_pips']
    }


def check_data_freshness(ticks, threshold_seconds):
    """
    Check if the tick data is fresh enough to use.
    
    Parameters:
    - ticks: List of tick dictionaries with 'timestamp'
    - threshold_seconds: Maximum age in seconds
    
    Returns:
    - Tuple of (is_fresh, age_seconds)
    """
    if not ticks:
        return (False, 999)
    
    # Get the most recent tick timestamp
    last_tick = ticks[-1]
    
    if 'timestamp' not in last_tick:
        # No timestamp, assume fresh for testing
        return (True, 0)
    
    # Parse timestamp
    try:
        timestamp_str = last_tick['timestamp']
        # Handle different timestamp formats
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'
        
        tick_time = datetime.fromisoformat(timestamp_str)
        
        # Ensure tick_time is timezone aware
        if tick_time.tzinfo is None:
            tick_time = tick_time.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age = (now - tick_time).total_seconds()
        
        return (age <= threshold_seconds, round(age, 1))
    except Exception as e:
        # If parsing fails, assume fresh for testing
        return (True, 0)


# -----------------------------------------------------------------------------
# MAIN AGENT CLASS
# -----------------------------------------------------------------------------
class RecencyCheck:
    """
    The Recency Check Agent.
    
    This agent analyzes the most recent tick data as a pre-action sanity check.
    """
    
    def __init__(self):
        """
        Initialize the agent.
        """
        self.agent_name = "RECENCY_CHECK"
        self.agent_version = "1.0"
        
        self.instrument = INSTRUMENT
        self.pip_size = PIP_SIZE
        self.tick_count = RECENCY_TICK_COUNT
        self.stale_threshold = STALE_DATA_THRESHOLD_SECONDS
    
    def check(self, ticks, intended_direction=None):
        """
        Perform recency check on tick data.
        
        Parameters:
        - ticks: List of recent tick dictionaries
                 Each tick needs: 'mid', 'spread', 'timestamp'
        - intended_direction: Optional - 'LONG' or 'SHORT' to check alignment
        
        Returns:
        - Dictionary containing the recency report
        """
        analysis_time = datetime.now(timezone.utc).isoformat()
        
        # Check if we have enough ticks
        if len(ticks) < 5:
            return self._create_report(
                analysis_time=analysis_time,
                status="INSUFFICIENT_DATA",
                tick_count=len(ticks),
                intended_direction=intended_direction
            )
        
        # Check data freshness
        is_fresh, data_age = check_data_freshness(ticks, self.stale_threshold)
        
        # Analyze ticks
        up_count, down_count, unchanged = count_tick_directions(ticks)
        net_movement = calculate_net_movement(ticks, self.pip_size)
        spread_stability = assess_spread_stability(ticks)
        velocity_trend = calculate_velocity_trend(ticks, self.pip_size)
        last_impulse = find_last_impulse(ticks, self.pip_size)
        
        # Determine overall tick bias
        total_directional = up_count + down_count
        if total_directional == 0:
            tick_bias = "NEUTRAL"
        elif up_count > down_count * 1.3:
            tick_bias = "BULLISH"
        elif down_count > up_count * 1.3:
            tick_bias = "BEARISH"
        else:
            tick_bias = "NEUTRAL"
        
        # Check alignment with intended direction if provided
        alignment = "N/A"
        if intended_direction:
            if intended_direction == 'LONG':
                if tick_bias == 'BULLISH':
                    alignment = 'ALIGNED'
                elif tick_bias == 'BEARISH':
                    alignment = 'CONTRADICTED'
                else:
                    alignment = 'NEUTRAL'
            elif intended_direction == 'SHORT':
                if tick_bias == 'BEARISH':
                    alignment = 'ALIGNED'
                elif tick_bias == 'BULLISH':
                    alignment = 'CONTRADICTED'
                else:
                    alignment = 'NEUTRAL'
        
        return self._create_report(
            analysis_time=analysis_time,
            status="CHECK_COMPLETE",
            tick_count=len(ticks),
            data_age_seconds=data_age,
            is_fresh=is_fresh,
            up_count=up_count,
            down_count=down_count,
            unchanged_count=unchanged,
            net_movement_pips=net_movement,
            spread_stability=spread_stability,
            velocity_trend=velocity_trend,
            last_impulse=last_impulse,
            tick_bias=tick_bias,
            intended_direction=intended_direction,
            alignment=alignment
        )
    
    def _create_report(self, analysis_time, status, tick_count,
                       data_age_seconds=0, is_fresh=True, up_count=0, 
                       down_count=0, unchanged_count=0, net_movement_pips=0,
                       spread_stability="STABLE", velocity_trend="STEADY",
                       last_impulse=None, tick_bias="NEUTRAL",
                       intended_direction=None, alignment="N/A"):
        """
        Create the standardized report dictionary.
        """
        report = {
            "agent": self.agent_name,
            "version": self.agent_version,
            "timestamp": analysis_time,
            "instrument": self.instrument,
            "status": status,
            "output": {
                "tick_direction": {
                    "up": up_count,
                    "down": down_count,
                    "unchanged": unchanged_count
                },
                "net_movement_pips": net_movement_pips,
                "spread_stability": spread_stability,
                "velocity_trend": velocity_trend,
                "last_impulse": last_impulse if last_impulse else {
                    'direction': 'NONE',
                    'strength': 'NONE',
                    'ticks_ago': 0,
                    'size_pips': 0
                },
                "tick_bias": tick_bias,
                "intended_direction": intended_direction if intended_direction else "NONE",
                "alignment": alignment
            },
            "internals": {
                "ticks_analyzed": tick_count,
                "data_age_seconds": data_age_seconds,
                "is_data_fresh": is_fresh,
                "stale_threshold_seconds": self.stale_threshold
            }
        }
        
        return report
    
    def save_report(self, report, output_folder=None):
        """
        Save the report to a JSON file.
        """
        if output_folder is None:
            output_folder = OUTPUT_FOLDER
        
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_output_path = os.path.join(base_path, output_folder)
        
        if not os.path.exists(full_output_path):
            os.makedirs(full_output_path)
        
        filename = f"recency_check_report.json"
        filepath = os.path.join(full_output_path, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filepath


# -----------------------------------------------------------------------------
# TEST THE AGENT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("TESTING RECENCY CHECK AGENT")
    print("=" * 60)
    
    # Import our fake data generator
    from data.fake_data_generator import FakeDataGenerator
    
    # Create fake tick data
    print("\n1. Generating fake tick data...")
    generator = FakeDataGenerator(instrument="XAU/USD", starting_price=2650.00)
    
    # Generate candles first to move price around, then get ticks
    generator.generate_candle_history(num_candles=10, timeframe_minutes=1)
    
    # Now generate fresh ticks
    ticks = []
    for _ in range(50):
        tick = generator.generate_tick()
        ticks.append(tick)
    
    print(f"   Generated {len(ticks)} ticks")
    
    # Show price range
    prices = [t['mid'] for t in ticks]
    print(f"   Price range: {min(prices):.2f} - {max(prices):.2f}")
    print(f"   First tick: {ticks[0]['mid']:.2f}")
    print(f"   Last tick: {ticks[-1]['mid']:.2f}")
    
    # Create the agent
    print("\n2. Creating Recency Check agent...")
    agent = RecencyCheck()
    print(f"   Agent: {agent.agent_name} v{agent.agent_version}")
    
    # Run check without intended direction
    print("\n3. Running recency check (no direction)...")
    report = agent.check(ticks)
    
    # Display results
    print("\n4. Results:")
    print("-" * 40)
    print(f"   Status: {report['status']}")
    print(f"   Tick Direction: {report['output']['tick_direction']['up']} UP / {report['output']['tick_direction']['down']} DOWN")
    print(f"   Net Movement: {report['output']['net_movement_pips']} pips")
    print(f"   Spread Stability: {report['output']['spread_stability']}")
    print(f"   Velocity Trend: {report['output']['velocity_trend']}")
    print(f"   Tick Bias: {report['output']['tick_bias']}")
    print(f"\n   Last Impulse:")
    impulse = report['output']['last_impulse']
    print(f"      Direction: {impulse['direction']}")
    print(f"      Strength: {impulse['strength']}")
    print(f"      Size: {impulse['size_pips']} pips")
    print(f"      Ticks Ago: {impulse['ticks_ago']}")
    
    # Run check WITH intended direction
    print("\n5. Running recency check (intended LONG)...")
    report_long = agent.check(ticks, intended_direction='LONG')
    print(f"   Tick Bias: {report_long['output']['tick_bias']}")
    print(f"   Intended: {report_long['output']['intended_direction']}")
    print(f"   Alignment: {report_long['output']['alignment']}")
    
    print("\n6. Running recency check (intended SHORT)...")
    report_short = agent.check(ticks, intended_direction='SHORT')
    print(f"   Tick Bias: {report_short['output']['tick_bias']}")
    print(f"   Intended: {report_short['output']['intended_direction']}")
    print(f"   Alignment: {report_short['output']['alignment']}")
    
    # Save report
    print("\n7. Saving report...")
    filepath = agent.save_report(report)
    print(f"   Saved to: {filepath}")
    
    # Show full report
    print("\n8. Full Report (JSON):")
    print("-" * 40)
    print(json.dumps(report, indent=2))
    
    print("\n" + "=" * 60)
    print("RECENCY CHECK TEST COMPLETE")
    print("=" * 60)
