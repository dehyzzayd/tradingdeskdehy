"""
LIVE DATA PROVIDER - Twelve Data API
Real-time XAU/USD data for BiasDesk Terminal
"""

import requests
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict

class LiveDataProvider:
    """
    Fetches real XAU/USD data from Twelve Data API
    """
    
    VERSION = "1.0"
    BASE_URL = "https://api.twelvedata.com"
    
    def __init__(self, api_key: str, instrument: str = "XAU/USD"):
        self.api_key = api_key
        self.instrument = instrument
        self.last_quote = None
        self.last_candles = None
        self.request_count = 0
        
    def _make_request(self, endpoint: str, params: dict) -> Optional[dict]:
        """Make API request with error handling"""
        params['apikey'] = self.api_key
        
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = requests.get(url, params=params, timeout=10)
            self.request_count += 1
            
            if response.status_code == 200:
                data = response.json()
                if 'code' in data and data.get('status') == 'error':
                    print(f"API Error: {data.get('message', 'Unknown error')}")
                    return None
                return data
            else:
                print(f"HTTP Error: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print("Request timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def get_current_quote(self) -> dict:
        """
        Get real-time quote for XAU/USD
        Returns: {timestamp, instrument, bid, ask, mid, spread, price}
        """
        params = {
            'symbol': self.instrument,
            'interval': '1min',
            'dp': 2
        }
        
        data = self._make_request('quote', params)
        
        if data and 'close' in data:
            price = float(data.get('close', 0))
            open_price = float(data.get('open', price))
            high = float(data.get('high', price))
            low = float(data.get('low', price))
            
            # Estimate spread (XAU/USD typically 0.20-0.50)
            spread = 0.30
            bid = price - (spread / 2)
            ask = price + (spread / 2)
            
            self.last_quote = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'instrument': self.instrument,
                'bid': round(bid, 2),
                'ask': round(ask, 2),
                'mid': round(price, 2),
                'spread': spread,
                'price': round(price, 2),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'volume': int(data.get('volume', 0)),
                'change': float(data.get('change', 0)),
                'change_percent': float(data.get('percent_change', 0)),
                'source': 'twelvedata',
                'is_market_open': data.get('is_market_open', True)
            }
            return self.last_quote
        
        # Return last known quote or default
        if self.last_quote:
            return self.last_quote
            
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'instrument': self.instrument,
            'bid': 2650.00,
            'ask': 2650.30,
            'mid': 2650.15,
            'spread': 0.30,
            'price': 2650.15,
            'source': 'default',
            'error': 'No data available'
        }
    
    def get_price(self) -> float:
        """Get just the current price"""
        params = {
            'symbol': self.instrument,
            'dp': 2
        }
        
        data = self._make_request('price', params)
        
        if data and 'price' in data:
            return float(data['price'])
        
        return self.last_quote.get('price', 2650.00) if self.last_quote else 2650.00
    
    def generate_candle_history(self, num_candles: int = 100, timeframe_minutes: int = 5) -> List[dict]:
        """
        Get historical candles from Twelve Data
        """
        # Map timeframe to Twelve Data interval
        interval_map = {
            1: '1min',
            5: '5min',
            15: '15min',
            30: '30min',
            60: '1h',
            240: '4h',
            1440: '1day'
        }
        interval = interval_map.get(timeframe_minutes, '5min')
        
        params = {
            'symbol': self.instrument,
            'interval': interval,
            'outputsize': num_candles,
            'dp': 2,
            'order': 'asc'
        }
        
        data = self._make_request('time_series', params)
        
        if data and 'values' in data:
            candles = []
            for item in data['values']:
                candle = {
                    'timestamp': item.get('datetime', ''),
                    'instrument': self.instrument,
                    'timeframe': f'{timeframe_minutes}m',
                    'open': float(item.get('open', 0)),
                    'high': float(item.get('high', 0)),
                    'low': float(item.get('low', 0)),
                    'close': float(item.get('close', 0)),
                    'volume': int(item.get('volume', 0)) if item.get('volume') else 0
                }
                candles.append(candle)
            
            self.last_candles = candles
            return candles
        
        # Return last known candles or empty
        if self.last_candles:
            return self.last_candles
            
        return []
    
    def get_recent_ticks(self, count: int = 50) -> List[dict]:
        """
        Simulate ticks from 1-minute candles
        (Twelve Data free tier doesn't have tick data)
        """
        # Get recent 1-minute candles
        params = {
            'symbol': self.instrument,
            'interval': '1min',
            'outputsize': 10,
            'dp': 2,
            'order': 'desc'
        }
        
        data = self._make_request('time_series', params)
        
        ticks = []
        if data and 'values' in data:
            for candle in data['values'][:5]:
                # Generate synthetic ticks from OHLC
                o = float(candle.get('open', 0))
                h = float(candle.get('high', 0))
                l = float(candle.get('low', 0))
                c = float(candle.get('close', 0))
                
                prices = [o, h, l, c]
                spread = 0.30
                
                for price in prices:
                    tick = {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'bid': round(price - spread/2, 2),
                        'ask': round(price + spread/2, 2),
                        'mid': round(price, 2)
                    }
                    ticks.append(tick)
        
        # Pad to requested count
        while len(ticks) < count:
            if ticks:
                ticks.append(ticks[-1].copy())
            else:
                ticks.append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'bid': 2650.00,
                    'ask': 2650.30,
                    'mid': 2650.15
                })
        
        return ticks[:count]
    
    def test_connection(self) -> dict:
        """Test API connection"""
        quote = self.get_current_quote()
        
        return {
            'status': 'ok' if quote.get('source') == 'twelvedata' else 'error',
            'instrument': self.instrument,
            'price': quote.get('price'),
            'timestamp': quote.get('timestamp'),
            'requests_made': self.request_count,
            'source': quote.get('source'),
            'error': quote.get('error')
        }


# Your API Key
TWELVE_DATA_API_KEY = "43fca686d8234f7b89c8a5e879e1ce28"

# Create global instance
_live_provider = None

def get_live_provider() -> LiveDataProvider:
    """Get or create live data provider instance"""
    global _live_provider
    if _live_provider is None:
        _live_provider = LiveDataProvider(
            api_key=TWELVE_DATA_API_KEY,
            instrument="XAU/USD"
        )
    return _live_provider


if __name__ == "__main__":
    print("=" * 60)
    print("TESTING TWELVE DATA CONNECTION")
    print("=" * 60)
    
    provider = get_live_provider()
    
    print("\n1. Testing connection...")
    result = provider.test_connection()
    print(f"   Status: {result['status']}")
    print(f"   Instrument: {result['instrument']}")
    print(f"   Price: {result['price']}")
    print(f"   Source: {result['source']}")
    
    print("\n2. Getting current quote...")
    quote = provider.get_current_quote()
    print(f"   Bid: {quote['bid']}")
    print(f"   Ask: {quote['ask']}")
    print(f"   Mid: {quote['mid']}")
    print(f"   Spread: {quote['spread']}")
    
    print("\n3. Getting historical candles...")
    candles = provider.generate_candle_history(num_candles=5, timeframe_minutes=5)
    print(f"   Retrieved {len(candles)} candles")
    if candles:
        print(f"   Latest: O={candles[-1]['open']} H={candles[-1]['high']} L={candles[-1]['low']} C={candles[-1]['close']}")
    
    print("\n4. Getting ticks...")
    ticks = provider.get_recent_ticks(count=10)
    print(f"   Retrieved {len(ticks)} ticks")
    if ticks:
        print(f"   Latest tick: Bid={ticks[-1]['bid']} Ask={ticks[-1]['ask']}")
    
    print("\n" + "=" * 60)
    print(f"Total API requests: {provider.request_count}")
    print("TEST COMPLETE")
    print("=" * 60)
