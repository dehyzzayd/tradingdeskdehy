"""
VOLATILITY ASSESSOR AGENT v2.0
Proper ATR calculation and volatility assessment
"""

from datetime import datetime, timezone

class VolatilityAssessor:
    def __init__(self):
        self.agent_name = "VOLATILITY_ASSESSOR"
        self.agent_version = "2.0.0"
        self.instrument = "XAU/USD"
        self.pip_size = 0.01  # For XAU/USD
        
        # Thresholds for XAU/USD (in pips)
        self.low_threshold = 100  # Below 100 pips = low volatility
        self.normal_threshold = 300  # 100-300 pips = normal
        self.elevated_threshold = 500  # 300-500 pips = elevated
        # Above 500 = extreme
        
        # Spread thresholds (in pips)
        self.spread_acceptable = 0.50
        self.spread_wide = 1.00
    
    def calculate_atr(self, candles, period=14):
        """Calculate Average True Range"""
        if len(candles) < period + 1:
            return 0
        
        tr_list = []
        
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            close_prev = candles[i-1]['close']
            
            # True Range = max of:
            # 1. Current High - Current Low
            # 2. |Current High - Previous Close|
            # 3. |Current Low - Previous Close|
            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return sum(tr_list) / len(tr_list) if tr_list else 0
        
        # Wilder's smoothed ATR
        atr = sum(tr_list[:period]) / period
        
        for i in range(period, len(tr_list)):
            atr = ((atr * (period - 1)) + tr_list[i]) / period
        
        return atr
    
    def calculate_baseline_atr(self, candles, period=14, lookback=50):
        """Calculate baseline ATR from historical data"""
        if len(candles) < lookback:
            return self.calculate_atr(candles, period)
        
        # Use older candles for baseline
        baseline_candles = candles[:-lookback] if len(candles) > lookback * 2 else candles[:lookback]
        return self.calculate_atr(baseline_candles, period)
    
    def assess(self, candles, spread=None):
        """Assess current volatility state"""
        start_time = datetime.now(timezone.utc)
        
        if not candles or len(candles) < 2:
            return {
                'status': 'ERROR',
                'output': {
                    'volatility_state': 'UNKNOWN',
                    'atr_current_pips': 0,
                    'atr_baseline_pips': 0,
                    'spread_pips': 0,
                    'spread_status': 'UNKNOWN'
                }
            }
        
        # Calculate current ATR
        atr_current = self.calculate_atr(candles, 14)
        atr_current_pips = atr_current / self.pip_size
        
        # Calculate baseline ATR for comparison
        atr_baseline = self.calculate_baseline_atr(candles, 14, 50)
        atr_baseline_pips = atr_baseline / self.pip_size
        
        # Determine volatility state
        if atr_current_pips < self.low_threshold:
            volatility_state = 'LOW'
        elif atr_current_pips < self.normal_threshold:
            volatility_state = 'NORMAL'
        elif atr_current_pips < self.elevated_threshold:
            volatility_state = 'ELEVATED'
        else:
            volatility_state = 'EXTREME'
        
        # Also check relative to baseline
        if atr_baseline > 0:
            ratio = atr_current / atr_baseline
            if ratio > 2.0 and volatility_state != 'EXTREME':
                volatility_state = 'ELEVATED'  # Upgrade if 2x normal
            if ratio > 3.0:
                volatility_state = 'EXTREME'  # Upgrade if 3x normal
        
        # Assess spread
        spread_pips = spread if spread is not None else 0.30  # Default spread estimate
        
        if spread_pips <= self.spread_acceptable:
            spread_status = 'ACCEPTABLE'
        elif spread_pips <= self.spread_wide:
            spread_status = 'WIDE'
        else:
            spread_status = 'EXTREME'
        
        return {
            'status': 'OK',
            'output': {
                'volatility_state': volatility_state,
                'atr_current_pips': round(atr_current_pips, 2),
                'atr_baseline_pips': round(atr_baseline_pips, 2),
                'atr_ratio': round(atr_current / atr_baseline, 2) if atr_baseline > 0 else 1.0,
                'spread_pips': round(spread_pips, 2),
                'spread_status': spread_status,
                'internals': {
                    'atr_raw': round(atr_current, 4),
                    'atr_baseline_raw': round(atr_baseline, 4),
                    'period': 14
                }
            }
        }
    
    def save_report(self, result):
        pass
