# =============================================================================
# AGENT 3: MOMENTUM READER
# =============================================================================
# This agent analyzes price data and measures current momentum.
#
# It answers: "How is price momentum behaving right now?"
#
# Possible outputs:
#   - ACCELERATING_LONG: Price moving up with increasing speed
#   - ACCELERATING_SHORT: Price moving down with increasing speed
#   - DECELERATING: Price movement is slowing down
#   - NEUTRAL: No clear momentum
#
# This agent does NOT predict future momentum.
# This agent does NOT suggest trades.
# This agent only reports the current momentum state.
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
    MOMENTUM_FAST_PERIOD,
    MOMENTUM_SLOW_PERIOD,
    MOMENTUM_ACCELERATION_THRESHOLD,
    OUTPUT_FOLDER
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def calculate_rate_of_change(prices, period):
    """
    Calculate the Rate of Change (ROC) over a period.
    
    ROC measures the percentage change between current price
    and the price 'period' bars ago.
    
    Formula: ((Current - Past) / Past) * 100
    
    Parameters:
    - prices: List of price values
    - period: How many bars to look back
    
    Returns:
    - ROC value as a percentage
    """
    if len(prices) <= period:
        return 0.0
    
    current_price = prices[-1]
    past_price = prices[-(period + 1)]
    
    if past_price == 0:
        return 0.0
    
    roc = ((current_price - past_price) / past_price) * 100
    
    return round(roc, 4)


def calculate_momentum_slope(prices, period):
    """
    Calculate the slope of price movement over a period.
    
    This tells us the average rate of change per bar.
    
    Parameters:
    - prices: List of price values
    - period: How many bars to analyze
    
    Returns:
    - Slope value (positive = up, negative = down)
    """
    if len(prices) < period:
        return 0.0
    
    recent_prices = prices[-period:]
    
    # Simple linear regression slope
    n = len(recent_prices)
    sum_x = sum(range(n))
    sum_y = sum(recent_prices)
    sum_xy = sum(i * p for i, p in enumerate(recent_prices))
    sum_x2 = sum(i * i for i in range(n))
    
    denominator = (n * sum_x2 - sum_x * sum_x)
    if denominator == 0:
        return 0.0
    
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    
    return round(slope, 4)


def calculate_velocity(prices, period):
    """
    Calculate price velocity (rate of movement).
    
    Velocity = total distance moved / time
    
    Parameters:
    - prices: List of price values
    - period: How many bars to analyze
    
    Returns:
    - Velocity value (can be positive or negative)
    """
    if len(prices) < period:
        return 0.0
    
    recent_prices = prices[-period:]
    
    # Total movement over the period
    total_movement = recent_prices[-1] - recent_prices[0]
    
    # Velocity is movement per bar
    velocity = total_movement / period
    
    return round(velocity, 4)


def calculate_acceleration(prices, fast_period, slow_period):
    """
    Calculate momentum acceleration.
    
    Acceleration = Fast velocity - Slow velocity
    
    If acceleration is positive and prices rising = ACCELERATING_LONG
    If acceleration is positive and prices falling = DECELERATING (slowing the fall)
    If acceleration is negative and prices rising = DECELERATING (slowing the rise)
    If acceleration is negative and prices falling = ACCELERATING_SHORT
    
    Parameters:
    - prices: List of price values
    - fast_period: Short lookback for recent momentum
    - slow_period: Longer lookback for baseline momentum
    
    Returns:
    - Acceleration value
    """
    fast_velocity = calculate_velocity(prices, fast_period)
    slow_velocity = calculate_velocity(prices, slow_period)
    
    acceleration = fast_velocity - slow_velocity
    
    return round(acceleration, 4)


def normalize_value(value, baseline):
    """
    Normalize a value relative to a baseline.
    
    This helps us compare momentum across different price levels.
    
    Parameters:
    - value: The value to normalize
    - baseline: The reference value (usually average price)
    
    Returns:
    - Normalized value (typically between -1 and 1 for normal conditions)
    """
    if baseline == 0:
        return 0.0
    
    normalized = value / baseline * 100
    
    return round(normalized, 4)


# -----------------------------------------------------------------------------
# MAIN AGENT CLASS
# -----------------------------------------------------------------------------
class MomentumReader:
    """
    The Momentum Reader Agent.
    
    This agent takes candle data and outputs the current momentum state.
    """
    
    def __init__(self):
        """
        Initialize the agent.
        """
        self.agent_name = "MOMENTUM_READER"
        self.agent_version = "1.0"
        
        self.instrument = INSTRUMENT
        self.fast_period = MOMENTUM_FAST_PERIOD
        self.slow_period = MOMENTUM_SLOW_PERIOD
        self.acceleration_threshold = MOMENTUM_ACCELERATION_THRESHOLD
    
    def read_momentum(self, candles):
        """
        Analyze candles and determine current momentum state.
        
        Parameters:
        - candles: List of candle dictionaries (oldest first)
                   Each candle needs: 'close', 'timestamp'
        
        Returns:
        - Dictionary containing the momentum report
        """
        analysis_time = datetime.now(timezone.utc).isoformat()
        
        # Check if we have enough data
        if len(candles) < self.slow_period + 5:
            return self._create_report(
                state="NEUTRAL",
                analysis_time=analysis_time,
                status="INSUFFICIENT_DATA",
                candle_count=len(candles)
            )
        
        # Extract close prices
        closes = [c['close'] for c in candles]
        
        # Calculate momentum indicators
        fast_roc = calculate_rate_of_change(closes, self.fast_period)
        slow_roc = calculate_rate_of_change(closes, self.slow_period)
        
        fast_velocity = calculate_velocity(closes, self.fast_period)
        slow_velocity = calculate_velocity(closes, self.slow_period)
        
        acceleration = calculate_acceleration(closes, self.fast_period, self.slow_period)
        
        slope = calculate_momentum_slope(closes, self.fast_period)
        
        # Normalize velocity for easier interpretation
        avg_price = sum(closes[-self.slow_period:]) / self.slow_period
        normalized_velocity = normalize_value(fast_velocity, avg_price)
        
        # Determine momentum state
        state = self._determine_state(
            fast_roc=fast_roc,
            slow_roc=slow_roc,
            acceleration=acceleration,
            velocity=fast_velocity
        )
        
        # Determine prior state (look at older data)
        prior_state = self._get_prior_state(closes)
        
        # Calculate state duration (simplified)
        state_duration = self._estimate_state_duration(closes, state)
        
        return self._create_report(
            state=state,
            analysis_time=analysis_time,
            status="ANALYSIS_COMPLETE",
            candle_count=len(candles),
            fast_roc=fast_roc,
            slow_roc=slow_roc,
            velocity=fast_velocity,
            normalized_velocity=normalized_velocity,
            acceleration=acceleration,
            slope=slope,
            prior_state=prior_state,
            state_duration=state_duration
        )
    
    def _determine_state(self, fast_roc, slow_roc, acceleration, velocity):
        """
        Determine the momentum state based on calculated values.
        
        Logic:
        1. If velocity near zero and acceleration near zero = NEUTRAL
        2. If velocity positive and acceleration positive = ACCELERATING_LONG
        3. If velocity negative and acceleration negative = ACCELERATING_SHORT
        4. If acceleration opposes velocity direction = DECELERATING
        """
        # Define thresholds
        velocity_threshold = 0.05  # Minimum velocity to not be neutral
        accel_threshold = self.acceleration_threshold
        
        # Check for neutral (low velocity and low acceleration)
        if abs(velocity) < velocity_threshold and abs(acceleration) < accel_threshold:
            return "NEUTRAL"
        
        # Check direction based on velocity
        going_up = velocity > 0
        going_down = velocity < 0
        
        # Check acceleration direction
        accelerating = acceleration > accel_threshold
        decelerating_accel = acceleration < -accel_threshold
        
        # Determine state
        if going_up:
            if accelerating:
                return "ACCELERATING_LONG"
            elif decelerating_accel:
                return "DECELERATING"
            else:
                # Mild momentum up
                return "NEUTRAL"
        elif going_down:
            if decelerating_accel:
                return "ACCELERATING_SHORT"
            elif accelerating:
                return "DECELERATING"
            else:
                # Mild momentum down
                return "NEUTRAL"
        else:
            return "NEUTRAL"
    
    def _get_prior_state(self, closes):
        """
        Determine what momentum state was before current.
        """
        if len(closes) < self.slow_period + 10:
            return "UNKNOWN"
        
        # Look at older data (exclude recent candles)
        older_closes = closes[:-5]
        
        fast_roc = calculate_rate_of_change(older_closes, self.fast_period)
        slow_roc = calculate_rate_of_change(older_closes, self.slow_period)
        acceleration = calculate_acceleration(older_closes, self.fast_period, self.slow_period)
        velocity = calculate_velocity(older_closes, self.fast_period)
        
        return self._determine_state(fast_roc, slow_roc, acceleration, velocity)
    
    def _estimate_state_duration(self, closes, current_state):
        """
        Estimate how many candles we've been in current state.
        """
        if len(closes) < self.slow_period + 5:
            return 1
        
        duration = 0
        
        # Check progressively older data
        for i in range(1, min(50, len(closes) - self.slow_period)):
            subset = closes[:-i]
            if len(subset) < self.slow_period + 5:
                break
            
            fast_roc = calculate_rate_of_change(subset, self.fast_period)
            slow_roc = calculate_rate_of_change(subset, self.slow_period)
            acceleration = calculate_acceleration(subset, self.fast_period, self.slow_period)
            velocity = calculate_velocity(subset, self.fast_period)
            
            state = self._determine_state(fast_roc, slow_roc, acceleration, velocity)
            
            if state == current_state:
                duration += 1
            else:
                break
        
        return max(duration, 1)
    
    def _create_report(self, state, analysis_time, status, candle_count,
                       fast_roc=0, slow_roc=0, velocity=0, normalized_velocity=0,
                       acceleration=0, slope=0, prior_state="UNKNOWN", state_duration=0):
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
                "state": state,
                "prior_state": prior_state,
                "state_duration_candles": state_duration,
                "velocity_normalized": normalized_velocity
            },
            "internals": {
                "fast_roc": fast_roc,
                "slow_roc": slow_roc,
                "velocity": velocity,
                "acceleration": acceleration,
                "slope": slope,
                "candles_analyzed": candle_count,
                "fast_period": self.fast_period,
                "slow_period": self.slow_period
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
        
        filename = f"momentum_reader_report.json"
        filepath = os.path.join(full_output_path, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filepath


# -----------------------------------------------------------------------------
# TEST THE AGENT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("TESTING MOMENTUM READER AGENT")
    print("=" * 60)
    
    # Import our fake data generator
    from data.fake_data_generator import FakeDataGenerator
    
    # Create fake data
    print("\n1. Generating fake candle data...")
    generator = FakeDataGenerator(instrument="XAU/USD", starting_price=2650.00)
    candles = generator.generate_candle_history(num_candles=50, timeframe_minutes=1)
    print(f"   Generated {len(candles)} candles")
    
    # Show price movement
    first_close = candles[0]['close']
    last_close = candles[-1]['close']
    change = last_close - first_close
    print(f"   Price moved: {first_close:.2f} → {last_close:.2f} ({change:+.2f})")
    
    # Create the agent
    print("\n2. Creating Momentum Reader agent...")
    agent = MomentumReader()
    print(f"   Agent: {agent.agent_name} v{agent.agent_version}")
    
    # Run analysis
    print("\n3. Reading momentum...")
    report = agent.read_momentum(candles)
    
    # Display results
    print("\n4. Results:")
    print("-" * 40)
    print(f"   STATE: {report['output']['state']}")
    print(f"   Prior State: {report['output']['prior_state']}")
    print(f"   Duration: {report['output']['state_duration_candles']} candles")
    print(f"   Velocity (normalized): {report['output']['velocity_normalized']}")
    print("-" * 40)
    print(f"   Fast ROC: {report['internals']['fast_roc']}%")
    print(f"   Slow ROC: {report['internals']['slow_roc']}%")
    print(f"   Acceleration: {report['internals']['acceleration']}")
    print(f"   Slope: {report['internals']['slope']}")
    
    # Save report
    print("\n5. Saving report...")
    filepath = agent.save_report(report)
    print(f"   Saved to: {filepath}")
    
    # Show full report
    print("\n6. Full Report (JSON):")
    print("-" * 40)
    print(json.dumps(report, indent=2))
    
    print("\n" + "=" * 60)
    print("MOMENTUM READER TEST COMPLETE")
    print("=" * 60)
