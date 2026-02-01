# =============================================================================
# AGENT 2: STRUCTURE MAPPER
# =============================================================================
# This agent analyzes price data and identifies key support/resistance levels.
#
# It answers: "Where are the important price levels?"
#
# Output includes:
#   - Levels ABOVE current price (potential resistance)
#   - Levels BELOW current price (potential support)
#   - Each level tagged as MAJOR or MINOR
#   - Each level has validity: FRESH, USED, or INVALID
#
# Validity meanings:
#   - FRESH: Price has not tested this level in current regime
#   - USED: Price tested level recently; level held
#   - INVALID: Price broke through level; no longer structural
#
# This agent does NOT predict if price will reach levels.
# This agent does NOT suggest trades.
# This agent only reports where levels exist.
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
    STRUCTURE_LOOKBACK_PERIODS,
    STRUCTURE_MIN_DISTANCE_PIPS,
    PIP_SIZE,
    OUTPUT_FOLDER
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def find_swing_highs(candles, left_bars=3, right_bars=3):
    """
    Find swing high points in the price data.
    
    A swing high is a candle whose HIGH is higher than the highs
    of the candles on both sides of it.
    
    Parameters:
    - candles: List of candle dictionaries with 'high'
    - left_bars: How many bars to the left must be lower
    - right_bars: How many bars to the right must be lower
    
    Returns:
    - List of dictionaries with 'price', 'index', 'timestamp'
    """
    swing_highs = []
    
    # We need enough bars on both sides
    for i in range(left_bars, len(candles) - right_bars):
        current_high = candles[i]['high']
        
        # Check if all bars to the left have lower highs
        left_ok = all(
            candles[i - j]['high'] < current_high 
            for j in range(1, left_bars + 1)
        )
        
        # Check if all bars to the right have lower highs
        right_ok = all(
            candles[i + j]['high'] < current_high 
            for j in range(1, right_bars + 1)
        )
        
        if left_ok and right_ok:
            swing_highs.append({
                'price': current_high,
                'index': i,
                'timestamp': candles[i]['timestamp']
            })
    
    return swing_highs


def find_swing_lows(candles, left_bars=3, right_bars=3):
    """
    Find swing low points in the price data.
    
    A swing low is a candle whose LOW is lower than the lows
    of the candles on both sides of it.
    
    Parameters:
    - candles: List of candle dictionaries with 'low'
    - left_bars: How many bars to the left must be higher
    - right_bars: How many bars to the right must be higher
    
    Returns:
    - List of dictionaries with 'price', 'index', 'timestamp'
    """
    swing_lows = []
    
    for i in range(left_bars, len(candles) - right_bars):
        current_low = candles[i]['low']
        
        # Check if all bars to the left have higher lows
        left_ok = all(
            candles[i - j]['low'] > current_low 
            for j in range(1, left_bars + 1)
        )
        
        # Check if all bars to the right have higher lows
        right_ok = all(
            candles[i + j]['low'] > current_low 
            for j in range(1, right_bars + 1)
        )
        
        if left_ok and right_ok:
            swing_lows.append({
                'price': current_low,
                'index': i,
                'timestamp': candles[i]['timestamp']
            })
    
    return swing_lows


def cluster_levels(levels, min_distance):
    """
    Group nearby levels into clusters and return the average.
    
    This prevents having too many levels that are very close together.
    
    Parameters:
    - levels: List of price values
    - min_distance: Minimum distance between levels
    
    Returns:
    - List of clustered level prices
    """
    if not levels:
        return []
    
    # Sort levels
    sorted_levels = sorted(levels)
    
    clusters = []
    current_cluster = [sorted_levels[0]]
    
    for i in range(1, len(sorted_levels)):
        # If this level is close to the current cluster, add it
        if sorted_levels[i] - current_cluster[-1] <= min_distance:
            current_cluster.append(sorted_levels[i])
        else:
            # Save the average of the current cluster
            clusters.append(sum(current_cluster) / len(current_cluster))
            # Start a new cluster
            current_cluster = [sorted_levels[i]]
    
    # Don't forget the last cluster
    clusters.append(sum(current_cluster) / len(current_cluster))
    
    return clusters


def determine_level_strength(level_price, all_swing_points, touch_threshold):
    """
    Determine if a level is MAJOR or MINOR based on how many times
    price has reacted at this level.
    
    Parameters:
    - level_price: The price level to check
    - all_swing_points: List of all swing highs and lows
    - touch_threshold: How close price must be to count as a "touch"
    
    Returns:
    - 'MAJOR' if touched 2+ times, 'MINOR' otherwise
    """
    touches = 0
    
    for point in all_swing_points:
        if abs(point['price'] - level_price) <= touch_threshold:
            touches += 1
    
    return 'MAJOR' if touches >= 2 else 'MINOR'


def determine_level_validity(level_price, candles, threshold):
    """
    Determine the validity status of a level.
    
    - FRESH: Price hasn't tested this level recently (last 10 candles)
    - USED: Price tested the level and it held
    - INVALID: Price broke through the level
    
    Parameters:
    - level_price: The price level to check
    - candles: Recent candle data
    - threshold: How close price must be to count as "testing"
    
    Returns:
    - 'FRESH', 'USED', or 'INVALID'
    """
    if len(candles) < 10:
        return 'FRESH'
    
    # Look at the last 10 candles
    recent_candles = candles[-10:]
    
    # Check if price has been near this level
    tested = False
    broken = False
    
    for candle in recent_candles:
        high = candle['high']
        low = candle['low']
        
        # Check if candle touched the level
        if low <= level_price <= high:
            tested = True
            
            # Check if it broke through (closed beyond the level)
            close = candle['close']
            open_price = candle['open']
            
            # If price closed significantly beyond the level, it's broken
            if close > level_price + threshold or close < level_price - threshold:
                broken = True
    
    if broken:
        return 'INVALID'
    elif tested:
        return 'USED'
    else:
        return 'FRESH'


# -----------------------------------------------------------------------------
# MAIN AGENT CLASS
# -----------------------------------------------------------------------------
class StructureMapper:
    """
    The Structure Mapper Agent.
    
    This agent takes candle data and identifies key price levels.
    """
    
    def __init__(self):
        """
        Initialize the agent.
        """
        self.agent_name = "STRUCTURE_MAPPER"
        self.agent_version = "1.0"
        
        self.instrument = INSTRUMENT
        self.lookback = STRUCTURE_LOOKBACK_PERIODS
        self.min_distance_pips = STRUCTURE_MIN_DISTANCE_PIPS
        self.pip_size = PIP_SIZE
    
    def map_structure(self, candles):
        """
        Analyze candles and identify structural levels.
        
        Parameters:
        - candles: List of candle dictionaries (oldest first)
                   Each candle needs: 'high', 'low', 'close', 'open', 'timestamp'
        
        Returns:
        - Dictionary containing the structure report
        """
        analysis_time = datetime.now(timezone.utc).isoformat()
        
        # Check if we have enough data
        if len(candles) < 10:
            return self._create_report(
                levels_above=[],
                levels_below=[],
                current_price=0,
                analysis_time=analysis_time,
                status="INSUFFICIENT_DATA",
                candle_count=len(candles)
            )
        
        # Get current price (close of most recent candle)
        current_price = candles[-1]['close']
        
        # Find swing points
        swing_highs = find_swing_highs(candles, left_bars=3, right_bars=3)
        swing_lows = find_swing_lows(candles, left_bars=3, right_bars=3)
        
        # Combine all swing points for strength calculation
        all_swings = swing_highs + swing_lows
        
        # Extract just the prices
        high_prices = [sh['price'] for sh in swing_highs]
        low_prices = [sl['price'] for sl in swing_lows]
        all_level_prices = high_prices + low_prices
        
        # Cluster nearby levels
        min_distance = self.min_distance_pips * self.pip_size
        clustered_levels = cluster_levels(all_level_prices, min_distance)
        
        # Separate into above and below current price
        levels_above = sorted([l for l in clustered_levels if l > current_price])
        levels_below = sorted([l for l in clustered_levels if l < current_price], reverse=True)
        
        # Take only the nearest 3 levels in each direction
        levels_above = levels_above[:3]
        levels_below = levels_below[:3]
        
        # Add strength and validity to each level
        touch_threshold = self.min_distance_pips * self.pip_size
        
        levels_above_detailed = []
        for price in levels_above:
            strength = determine_level_strength(price, all_swings, touch_threshold)
            validity = determine_level_validity(price, candles, touch_threshold)
            distance_pips = round((price - current_price) / self.pip_size, 1)
            
            levels_above_detailed.append({
                'price': round(price, 2),
                'strength': strength,
                'validity': validity,
                'distance_pips': distance_pips
            })
        
        levels_below_detailed = []
        for price in levels_below:
            strength = determine_level_strength(price, all_swings, touch_threshold)
            validity = determine_level_validity(price, candles, touch_threshold)
            distance_pips = round((current_price - price) / self.pip_size, 1)
            
            levels_below_detailed.append({
                'price': round(price, 2),
                'strength': strength,
                'validity': validity,
                'distance_pips': distance_pips
            })
        
        return self._create_report(
            levels_above=levels_above_detailed,
            levels_below=levels_below_detailed,
            current_price=round(current_price, 2),
            analysis_time=analysis_time,
            status="ANALYSIS_COMPLETE",
            candle_count=len(candles),
            swing_highs_found=len(swing_highs),
            swing_lows_found=len(swing_lows)
        )
    
    def _create_report(self, levels_above, levels_below, current_price, 
                       analysis_time, status, candle_count,
                       swing_highs_found=0, swing_lows_found=0):
        """
        Create the standardized report dictionary.
        """
        # Calculate nearest level distances
        nearest_above = levels_above[0]['distance_pips'] if levels_above else None
        nearest_below = levels_below[0]['distance_pips'] if levels_below else None
        
        report = {
            "agent": self.agent_name,
            "version": self.agent_version,
            "timestamp": analysis_time,
            "instrument": self.instrument,
            "status": status,
            "output": {
                "current_price": current_price,
                "levels_above": levels_above,
                "levels_below": levels_below,
                "nearest_above_pips": nearest_above,
                "nearest_below_pips": nearest_below
            },
            "internals": {
                "candles_analyzed": candle_count,
                "swing_highs_found": swing_highs_found,
                "swing_lows_found": swing_lows_found,
                "min_distance_pips": self.min_distance_pips
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
        
        filename = f"structure_mapper_report.json"
        filepath = os.path.join(full_output_path, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filepath


# -----------------------------------------------------------------------------
# TEST THE AGENT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("TESTING STRUCTURE MAPPER AGENT")
    print("=" * 60)
    
    # Import our fake data generator
    from data.fake_data_generator import FakeDataGenerator
    
    # Create fake data (more candles for better structure detection)
    print("\n1. Generating fake candle data...")
    generator = FakeDataGenerator(instrument="XAU/USD", starting_price=2650.00)
    candles = generator.generate_candle_history(num_candles=100, timeframe_minutes=5)
    print(f"   Generated {len(candles)} candles")
    print(f"   Price range: {min(c['low'] for c in candles):.2f} - {max(c['high'] for c in candles):.2f}")
    
    # Create the agent
    print("\n2. Creating Structure Mapper agent...")
    agent = StructureMapper()
    print(f"   Agent: {agent.agent_name} v{agent.agent_version}")
    
    # Run mapping
    print("\n3. Mapping structure...")
    report = agent.map_structure(candles)
    
    # Display results
    print("\n4. Results:")
    print("-" * 40)
    print(f"   Current Price: {report['output']['current_price']}")
    print(f"\n   LEVELS ABOVE (Resistance):")
    if report['output']['levels_above']:
        for level in report['output']['levels_above']:
            print(f"      {level['price']} [{level['strength']}] [{level['validity']}] (+{level['distance_pips']} pips)")
    else:
        print("      None found")
    
    print(f"\n   LEVELS BELOW (Support):")
    if report['output']['levels_below']:
        for level in report['output']['levels_below']:
            print(f"      {level['price']} [{level['strength']}] [{level['validity']}] (-{level['distance_pips']} pips)")
    else:
        print("      None found")
    
    print("-" * 40)
    print(f"   Swing Highs Found: {report['internals']['swing_highs_found']}")
    print(f"   Swing Lows Found: {report['internals']['swing_lows_found']}")
    
    # Save report
    print("\n5. Saving report...")
    filepath = agent.save_report(report)
    print(f"   Saved to: {filepath}")
    
    # Show full report
    print("\n6. Full Report (JSON):")
    print("-" * 40)
    print(json.dumps(report, indent=2))
    
    print("\n" + "=" * 60)
    print("STRUCTURE MAPPER TEST COMPLETE")
    print("=" * 60)
