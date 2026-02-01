# =============================================================================
# AGENT 6: RISK CALCULATOR
# =============================================================================
# This agent calculates position sizing based on account equity and risk rules.
#
# It answers: "How much can I trade safely?"
#
# Outputs:
#   - Current account equity
#   - Risk allowance per trade (in dollars)
#   - Daily P&L status
#   - Remaining daily risk allowance
#   - Position size table for different stop distances
#
# This agent does NOT decide whether to trade.
# This agent does NOT evaluate trade quality.
# This agent only calculates safe position sizes.
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
    ACCOUNT_EQUITY,
    RISK_PER_TRADE,
    MAX_DAILY_LOSS,
    MAX_CONCURRENT_POSITIONS,
    PIP_SIZE,
    OUTPUT_FOLDER
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def calculate_pip_value(instrument, lot_size=1.0):
    """
    Calculate the value of one pip for a given lot size.
    
    For XAU/USD (Gold):
    - 1 standard lot = 100 oz
    - 1 pip (0.01 move) = $1 per standard lot
    
    This is simplified. Real pip values depend on account currency
    and current exchange rates.
    
    Parameters:
    - instrument: The trading instrument
    - lot_size: Position size in lots
    
    Returns:
    - Value of one pip in account currency (USD)
    """
    # For gold (XAU/USD), 1 pip = $0.01 per oz, standard lot = 100 oz
    # So 1 pip = $1 per standard lot
    if "XAU" in instrument:
        pip_value = 1.0 * lot_size  # $1 per pip per lot
    else:
        # For forex pairs, approximate $10 per pip per standard lot
        pip_value = 10.0 * lot_size
    
    return pip_value


def calculate_position_size(risk_amount, stop_distance_pips, pip_value_per_lot):
    """
    Calculate the position size based on risk amount and stop distance.
    
    Formula: Position Size = Risk Amount / (Stop Distance × Pip Value)
    
    Parameters:
    - risk_amount: Maximum amount willing to lose (in account currency)
    - stop_distance_pips: Distance to stop loss in pips
    - pip_value_per_lot: Value of one pip for one standard lot
    
    Returns:
    - Position size in lots
    """
    if stop_distance_pips <= 0 or pip_value_per_lot <= 0:
        return 0.0
    
    # Risk per pip = stop distance × pip value per lot
    # Position size = risk amount / risk per pip
    position_size = risk_amount / (stop_distance_pips * pip_value_per_lot)
    
    # Round to 2 decimal places (standard lot precision)
    return round(position_size, 2)


def calculate_risk_for_position(lot_size, stop_distance_pips, pip_value_per_lot):
    """
    Calculate the dollar risk for a given position and stop.
    
    Parameters:
    - lot_size: Position size in lots
    - stop_distance_pips: Distance to stop loss in pips
    - pip_value_per_lot: Value of one pip for one standard lot
    
    Returns:
    - Risk amount in account currency
    """
    risk = lot_size * stop_distance_pips * pip_value_per_lot
    return round(risk, 2)


# -----------------------------------------------------------------------------
# MAIN AGENT CLASS
# -----------------------------------------------------------------------------
class RiskCalculator:
    """
    The Risk Calculator Agent.
    
    This agent calculates position sizes based on account and risk parameters.
    """
    
    def __init__(self, equity=None, daily_pnl=0.0, open_positions=0):
        """
        Initialize the agent.
        
        Parameters:
        - equity: Current account equity (uses config default if not provided)
        - daily_pnl: Today's realized + unrealized P&L
        - open_positions: Number of currently open positions
        """
        self.agent_name = "RISK_CALCULATOR"
        self.agent_version = "1.0"
        
        self.instrument = INSTRUMENT
        self.pip_size = PIP_SIZE
        
        # Account parameters
        self.equity = equity if equity is not None else ACCOUNT_EQUITY
        self.risk_per_trade = RISK_PER_TRADE
        self.max_daily_loss = MAX_DAILY_LOSS
        self.max_concurrent = MAX_CONCURRENT_POSITIONS
        
        # Current state
        self.daily_pnl = daily_pnl
        self.open_positions = open_positions
        
        # Calculate pip value for this instrument
        self.pip_value_per_lot = calculate_pip_value(self.instrument, lot_size=1.0)
    
    def calculate(self, stop_distance_pips=None):
        """
        Calculate risk parameters and position sizes.
        
        Parameters:
        - stop_distance_pips: Optional specific stop distance to calculate for
        
        Returns:
        - Dictionary containing the risk report
        """
        analysis_time = datetime.now(timezone.utc).isoformat()
        
        # Calculate risk amounts
        risk_per_trade_dollars = self.equity * self.risk_per_trade
        max_daily_loss_dollars = self.equity * self.max_daily_loss
        daily_limit_remaining = max_daily_loss_dollars + self.daily_pnl  # daily_pnl is negative if losing
        
        # Check if daily limit is breached
        daily_limit_breached = daily_limit_remaining <= 0
        
        # Check if max positions reached
        can_open_new = self.open_positions < self.max_concurrent
        
        # Calculate position sizes for common stop distances
        stop_distances = [20, 30, 50, 100, 150, 200]
        
        # If specific stop provided, add it to the list
        if stop_distance_pips and stop_distance_pips not in stop_distances:
            stop_distances.append(stop_distance_pips)
            stop_distances.sort()
        
        # Build position size table
        position_size_table = []
        for stop in stop_distances:
            lot_size = calculate_position_size(
                risk_per_trade_dollars, 
                stop, 
                self.pip_value_per_lot
            )
            actual_risk = calculate_risk_for_position(
                lot_size, 
                stop, 
                self.pip_value_per_lot
            )
            
            position_size_table.append({
                'stop_pips': stop,
                'lot_size': lot_size,
                'risk_dollars': actual_risk,
                'risk_percent': round((actual_risk / self.equity) * 100, 2)
            })
        
        # Get specific calculation if stop provided
        specific_calculation = None
        if stop_distance_pips:
            lot_size = calculate_position_size(
                risk_per_trade_dollars,
                stop_distance_pips,
                self.pip_value_per_lot
            )
            specific_calculation = {
                'stop_pips': stop_distance_pips,
                'lot_size': lot_size,
                'risk_dollars': calculate_risk_for_position(
                    lot_size, stop_distance_pips, self.pip_value_per_lot
                )
            }
        
        return self._create_report(
            analysis_time=analysis_time,
            risk_per_trade_dollars=round(risk_per_trade_dollars, 2),
            max_daily_loss_dollars=round(max_daily_loss_dollars, 2),
            daily_limit_remaining=round(daily_limit_remaining, 2),
            daily_limit_breached=daily_limit_breached,
            can_open_new=can_open_new,
            position_size_table=position_size_table,
            specific_calculation=specific_calculation
        )
    
    def _create_report(self, analysis_time, risk_per_trade_dollars,
                       max_daily_loss_dollars, daily_limit_remaining,
                       daily_limit_breached, can_open_new,
                       position_size_table, specific_calculation):
        """
        Create the standardized report dictionary.
        """
        report = {
            "agent": self.agent_name,
            "version": self.agent_version,
            "timestamp": analysis_time,
            "instrument": self.instrument,
            "status": "CALCULATION_COMPLETE",
            "output": {
                "equity": self.equity,
                "risk_per_trade_dollars": risk_per_trade_dollars,
                "risk_per_trade_percent": self.risk_per_trade * 100,
                "daily_pnl": self.daily_pnl,
                "daily_limit_remaining": daily_limit_remaining,
                "daily_limit_breached": daily_limit_breached,
                "open_positions": self.open_positions,
                "max_concurrent": self.max_concurrent,
                "can_open_new_position": can_open_new,
                "position_size_table": position_size_table
            },
            "internals": {
                "max_daily_loss_dollars": max_daily_loss_dollars,
                "max_daily_loss_percent": self.max_daily_loss * 100,
                "pip_value_per_lot": self.pip_value_per_lot,
                "pip_size": self.pip_size
            }
        }
        
        # Add specific calculation if provided
        if specific_calculation:
            report["output"]["specific_calculation"] = specific_calculation
        
        return report
    
    def update_state(self, equity=None, daily_pnl=None, open_positions=None):
        """
        Update the calculator's state with new values.
        
        Parameters:
        - equity: New account equity
        - daily_pnl: New daily P&L
        - open_positions: New open position count
        """
        if equity is not None:
            self.equity = equity
        if daily_pnl is not None:
            self.daily_pnl = daily_pnl
        if open_positions is not None:
            self.open_positions = open_positions
    
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
        
        filename = f"risk_calculator_report.json"
        filepath = os.path.join(full_output_path, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filepath


# -----------------------------------------------------------------------------
# TEST THE AGENT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("TESTING RISK CALCULATOR AGENT")
    print("=" * 60)
    
    # Create the agent with default settings
    print("\n1. Creating Risk Calculator agent...")
    agent = RiskCalculator(
        equity=10000.00,      # $10,000 account
        daily_pnl=-50.00,     # Lost $50 today
        open_positions=0       # No open positions
    )
    print(f"   Agent: {agent.agent_name} v{agent.agent_version}")
    print(f"   Equity: ${agent.equity:,.2f}")
    print(f"   Daily P&L: ${agent.daily_pnl:,.2f}")
    
    # Run calculation
    print("\n2. Calculating risk parameters...")
    report = agent.calculate(stop_distance_pips=50)  # Calculate for 50 pip stop
    
    # Display results
    print("\n3. Results:")
    print("-" * 40)
    print(f"   Account Equity: ${report['output']['equity']:,.2f}")
    print(f"   Risk Per Trade: ${report['output']['risk_per_trade_dollars']:.2f} ({report['output']['risk_per_trade_percent']}%)")
    print(f"   Daily P&L: ${report['output']['daily_pnl']:.2f}")
    print(f"   Daily Limit Remaining: ${report['output']['daily_limit_remaining']:.2f}")
    print(f"   Daily Limit Breached: {report['output']['daily_limit_breached']}")
    print(f"   Can Open New Position: {report['output']['can_open_new_position']}")
    
    print("\n4. Position Size Table:")
    print("-" * 40)
    print(f"   {'Stop (pips)':<12} {'Lot Size':<10} {'Risk ($)':<10} {'Risk (%)':<10}")
    print(f"   {'-'*12} {'-'*10} {'-'*10} {'-'*10}")
    for row in report['output']['position_size_table']:
        print(f"   {row['stop_pips']:<12} {row['lot_size']:<10} {row['risk_dollars']:<10} {row['risk_percent']:<10}")
    
    # Show specific calculation
    if 'specific_calculation' in report['output']:
        calc = report['output']['specific_calculation']
        print(f"\n5. Specific Calculation (50 pip stop):")
        print("-" * 40)
        print(f"   Stop Distance: {calc['stop_pips']} pips")
        print(f"   Position Size: {calc['lot_size']} lots")
        print(f"   Risk Amount: ${calc['risk_dollars']:.2f}")
    
    # Test with daily limit breached
    print("\n6. Testing with daily limit breached...")
    agent.update_state(daily_pnl=-350.00)  # Lost $350 (more than 3% of $10k)
    report_breached = agent.calculate()
    print(f"   Daily P&L: ${report_breached['output']['daily_pnl']:.2f}")
    print(f"   Daily Limit Remaining: ${report_breached['output']['daily_limit_remaining']:.2f}")
    print(f"   Daily Limit Breached: {report_breached['output']['daily_limit_breached']}")
    
    # Reset and save report
    agent.update_state(daily_pnl=-50.00)
    report = agent.calculate(stop_distance_pips=50)
    
    print("\n7. Saving report...")
    filepath = agent.save_report(report)
    print(f"   Saved to: {filepath}")
    
    # Show full report
    print("\n8. Full Report (JSON):")
    print("-" * 40)
    print(json.dumps(report, indent=2))
    
    print("\n" + "=" * 60)
    print("RISK CALCULATOR TEST COMPLETE")
    print("=" * 60)
