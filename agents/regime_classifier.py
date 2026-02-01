"""
REGIME CLASSIFIER AGENT v2.0
Proper ADX calculation for trend strength
"""

from datetime import datetime, timezone

class RegimeClassifier:
    def __init__(self):
        self.agent_name = "REGIME_CLASSIFIER"
        self.agent_version = "2.0.0"
        self.instrument = "XAU/USD"
        self.lookback = 14  # Standard ADX period
        self.adx_threshold = 25  # Above 25 = strong trend
    
    def calculate_adx(self, candles, period=14):
        """Calculate ADX using Wilder's smoothing method"""
        if len(candles) < period + 1:
            return 0, 0, 0  # ADX, +DI, -DI
        
        # Calculate True Range, +DM, -DM
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []
        
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            close_prev = candles[i-1]['close']
            high_prev = candles[i-1]['high']
            low_prev = candles[i-1]['low']
            
            # True Range
            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            tr_list.append(tr)
            
            # Directional Movement
            up_move = high - high_prev
            down_move = low_prev - low
            
            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        if len(tr_list) < period:
            return 0, 0, 0
        
        # Wilder's smoothing for first value (sum of first period values)
        smoothed_tr = sum(tr_list[:period])
        smoothed_plus_dm = sum(plus_dm_list[:period])
        smoothed_minus_dm = sum(minus_dm_list[:period])
        
        dx_list = []
        
        # Calculate smoothed values and DX
        for i in range(period, len(tr_list)):
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_list[i]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm_list[i]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm_list[i]
            
            if smoothed_tr > 0:
                plus_di = 100 * smoothed_plus_dm / smoothed_tr
                minus_di = 100 * smoothed_minus_dm / smoothed_tr
            else:
                plus_di = 0
                minus_di = 0
            
            di_sum = plus_di + minus_di
            if di_sum > 0:
                dx = 100 * abs(plus_di - minus_di) / di_sum
            else:
                dx = 0
            
            dx_list.append((dx, plus_di, minus_di))
        
        if len(dx_list) < period:
            if dx_list:
                return dx_list[-1]
            return 0, 0, 0
        
        # ADX is smoothed average of DX
        adx = sum(d[0] for d in dx_list[-period:]) / period
        last_plus_di = dx_list[-1][1]
        last_minus_di = dx_list[-1][2]
        
        return adx, last_plus_di, last_minus_di
    
    def classify(self, candles):
        """Classify market regime based on ADX and directional indicators"""
        start_time = datetime.now(timezone.utc)
        
        if not candles or len(candles) < self.lookback + 1:
            return {
                'status': 'ERROR',
                'output': {
                    'regime': 'UNKNOWN',
                    'duration_candles': 0,
                    'prior_regime': 'UNKNOWN',
                    'internals': {'adx': 0, 'plus_di': 0, 'minus_di': 0}
                }
            }
        
        adx, plus_di, minus_di = self.calculate_adx(candles, self.lookback)
        
        # Determine regime
        if adx < 20:
            regime = 'RANGE'  # Weak/no trend
        elif adx >= 20 and adx < 25:
            # Borderline - check direction
            if plus_di > minus_di:
                regime = 'TREND_UP'
            elif minus_di > plus_di:
                regime = 'TREND_DOWN'
            else:
                regime = 'RANGE'
        elif adx >= 25 and adx < 50:
            # Strong trend
            if plus_di > minus_di:
                regime = 'TREND_UP'
            else:
                regime = 'TREND_DOWN'
        else:  # adx >= 50
            # Very strong trend or potential chaos
            if abs(plus_di - minus_di) < 10:
                regime = 'CHAOS'  # High volatility, no clear direction
            elif plus_di > minus_di:
                regime = 'TREND_UP'
            else:
                regime = 'TREND_DOWN'
        
        # Calculate trend duration (simplified)
        duration = min(int(adx / 5), 20) if adx > 20 else 1
        
        return {
            'status': 'OK',
            'output': {
                'regime': regime,
                'duration_candles': duration,
                'prior_regime': 'RANGE',
                'trend_strength': 'STRONG' if adx >= 25 else 'WEAK' if adx >= 15 else 'NONE',
                'internals': {
                    'adx': round(adx, 2),
                    'plus_di': round(plus_di, 2),
                    'minus_di': round(minus_di, 2)
                }
            }
        }
    
    def save_report(self, result):
        pass
