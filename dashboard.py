"""
BIASDESK TERMINAL v2.0
Enterprise-Grade Trading Intelligence Platform
"""

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime, timezone
import json
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import INSTRUMENT, OUTPUT_FOLDER
from data.live_data_provider import get_live_provider, LiveDataProvider
from agents.regime_classifier import RegimeClassifier
from agents.structure_mapper import StructureMapper
from agents.momentum_reader import MomentumReader
from agents.volatility_assessor import VolatilityAssessor
from agents.session_clock import SessionClock
from agents.risk_calculator import RiskCalculator
from agents.recency_check import RecencyCheck
from audit_logger import get_audit_logger
from trade_journal import get_trade_journal
from data.news_scraper import get_news_scraper


app = Flask(__name__)

# Initialize systems
audit_logger = get_audit_logger()
trade_journal = get_trade_journal()

# ============================================================
# SETTINGS CONFIGURATION
# ============================================================

SETTINGS = {
    'general': {
        'instrument': INSTRUMENT,
        'theme': 'dark',
        'auto_refresh': True,
        'refresh_interval': 5,
        'timezone': 'UTC',
        'use_live_data': True  # ADD THIS LINE
    },
    'risk': {
        'risk_per_trade': 1.0,
        'max_daily_loss': 3.0,
        'max_concurrent_positions': 2,
        'account_equity': 10000.00
    },
    'agents': {
        'regime_lookback': 20,
        'structure_lookback': 50,
        'momentum_fast_period': 5,
        'momentum_slow_period': 20,
        'volatility_atr_period': 14,
        'recency_tick_count': 50
    },
    'notifications': {
        'bias_change': True,
        'synthesis_forbidden': True,
        'kill_switch': True,
        'session_change': True
    },
    'display': {
        'show_internals': False,
        'decimal_places': 2,
        'show_timestamps': True
    }
}

def save_settings():
    with open(os.path.join(OUTPUT_FOLDER, 'settings.json'), 'w') as f:
        json.dump(SETTINGS, f, indent=2)

def load_settings():
    global SETTINGS
    settings_file = os.path.join(OUTPUT_FOLDER, 'settings.json')
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            SETTINGS = json.load(f)

load_settings()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_format(value, format_spec=".1f", default=0):
    if value is None:
        value = default
    try:
        return f"{value:{format_spec}}"
    except (TypeError, ValueError):
        return str(default)

def safe_get(dictionary, *keys, default=None):
    result = dictionary
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result if result is not None else default

# ============================================================
# BIAS CALCULATION
# ============================================================

def calculate_bias(regime, momentum, volatility, session):
    regime_state = safe_get(regime, 'output', 'regime', default='UNKNOWN')
    momentum_state = safe_get(momentum, 'output', 'state', default='UNKNOWN')
    volatility_state = safe_get(volatility, 'output', 'volatility_state', default='UNKNOWN')
    session_state = safe_get(session, 'output', 'active_session', default='UNKNOWN')
    
    if regime_state == 'CHAOS':
        return 'DO_NOT_TRADE'
    if volatility_state == 'EXTREME':
        return 'DO_NOT_TRADE'
    if session_state == 'OFF_HOURS':
        return 'DO_NOT_TRADE'
    
    if regime_state == 'TREND_UP':
        if momentum_state in ['ACCELERATING_LONG', 'NEUTRAL']:
            return 'BULLISH_BIAS'
    if regime_state == 'RANGE':
        if momentum_state == 'ACCELERATING_LONG':
            return 'BULLISH_BIAS'
    
    if regime_state == 'TREND_DOWN':
        if momentum_state in ['ACCELERATING_SHORT', 'NEUTRAL']:
            return 'BEARISH_BIAS'
    if regime_state == 'RANGE':
        if momentum_state == 'ACCELERATING_SHORT':
            return 'BEARISH_BIAS'
    
    return 'NEUTRAL'

def check_synthesis_forbidden(regime, momentum, volatility, session, recency):
    reasons = []
    
    regime_state = safe_get(regime, 'output', 'regime', default='UNKNOWN')
    if regime_state == 'CHAOS':
        reasons.append('REGIME_CHAOS')
    
    volatility_state = safe_get(volatility, 'output', 'volatility_state', default='UNKNOWN')
    spread_status = safe_get(volatility, 'output', 'spread_status', default='UNKNOWN')
    if volatility_state == 'EXTREME':
        reasons.append('VOLATILITY_EXTREME')
    if spread_status in ['WIDE', 'EXTREME']:
        reasons.append(f'SPREAD_{spread_status}')
    
    session_state = safe_get(session, 'output', 'active_session', default='UNKNOWN')
    boundary_flag = safe_get(session, 'output', 'boundary_flag', default='NONE')
    if session_state == 'OFF_HOURS':
        reasons.append('SESSION_OFF_HOURS')
    if boundary_flag == 'SESSION_CLOSE_30MIN':
        reasons.append('SESSION_CLOSING')
    
    return len(reasons) > 0, reasons

# ============================================================
# DATA GENERATION
# ============================================================

def run_all_agents():
    start_time = time.time()
    
    # Use LIVE data from Twelve Data API
    provider = get_live_provider()
    candles = provider.generate_candle_history(num_candles=100, timeframe_minutes=5)
    ticks = provider.get_recent_ticks(count=50)
    quote = provider.get_current_quote()
    current_price = quote.get('mid') or quote.get('price', 0)
    data_source = 'LIVE'
    
    results = {}
    instrument = "XAU/USD"
    
    agent_start = time.time()
    regime_agent = RegimeClassifier()
    results['regime'] = regime_agent.classify(candles)
    audit_logger.log_agent_run('REGIME_CLASSIFIER', safe_get(results['regime'], 'status', default='UNKNOWN'), 
                               safe_get(results['regime'], 'output', default={}), 
                               (time.time() - agent_start) * 1000)
    
    agent_start = time.time()
    structure_agent = StructureMapper()
    results['structure'] = structure_agent.map_structure(candles)
    audit_logger.log_agent_run('STRUCTURE_MAPPER', safe_get(results['structure'], 'status', default='UNKNOWN'),
                               safe_get(results['structure'], 'output', default={}),
                               (time.time() - agent_start) * 1000)
    
    agent_start = time.time()
    momentum_agent = MomentumReader()
    results['momentum'] = momentum_agent.read_momentum(candles)
    audit_logger.log_agent_run('MOMENTUM_READER', safe_get(results['momentum'], 'status', default='UNKNOWN'),
                               safe_get(results['momentum'], 'output', default={}),
                               (time.time() - agent_start) * 1000)
    
    agent_start = time.time()
    volatility_agent = VolatilityAssessor()
    spread = quote.get('spread', 0.30)
    results['volatility'] = volatility_agent.assess(candles, spread)
    audit_logger.log_agent_run(
        'VOLATILITY_ASSESSOR',
        safe_get(results['volatility'], 'status', default='UNKNOWN'),
        safe_get(results['volatility'], 'output', default={}),
        (time.time() - agent_start) * 1000
    )
    
    agent_start = time.time()
    session_agent = SessionClock()
    results['session'] = session_agent.check_session()
    audit_logger.log_agent_run('SESSION_CLOCK', safe_get(results['session'], 'status', default='UNKNOWN'),
                               safe_get(results['session'], 'output', default={}),
                               (time.time() - agent_start) * 1000)
    
    agent_start = time.time()
    risk_agent = RiskCalculator()
    risk_agent.update_state(
        equity=SETTINGS['risk']['account_equity'],
        daily_pnl=-50.0,
        open_positions=0
    )
    results['risk'] = risk_agent.calculate()
    audit_logger.log_agent_run('RISK_CALCULATOR', safe_get(results['risk'], 'status', default='UNKNOWN'),
                               safe_get(results['risk'], 'output', default={}),
                               (time.time() - agent_start) * 1000)
    
    agent_start = time.time()
    recency_agent = RecencyCheck()
    results['recency'] = recency_agent.check(ticks)
    audit_logger.log_agent_run('RECENCY_CHECK', safe_get(results['recency'], 'status', default='UNKNOWN'),
                               safe_get(results['recency'], 'output', default={}),
                               (time.time() - agent_start) * 1000)
    
    bias = calculate_bias(results['regime'], results['momentum'], results['volatility'], results['session'])
    forbidden, forbidden_reasons = check_synthesis_forbidden(results['regime'], results['momentum'], results['volatility'], results['session'], results['recency'])
    
    if forbidden:
        audit_logger.log_synthesis_forbidden(', '.join(forbidden_reasons), {
            'regime': safe_get(results['regime'], 'output', 'regime'),
            'volatility': safe_get(results['volatility'], 'output', 'volatility_state'),
            'spread': safe_get(results['volatility'], 'output', 'spread_status'),
            'session': safe_get(results['session'], 'output', 'active_session')
        })
    
    total_time = (time.time() - start_time) * 1000
    
    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'instrument': instrument,
        'current_price': current_price,
        'spread': quote.get('spread', 0.30),
        'bias': bias,
        'synthesis_forbidden': forbidden,
        'forbidden_reasons': forbidden_reasons,
        'agents': results,
        'execution_time_ms': round(total_time, 2),
        'data_source': data_source  # ADD THIS LINE
    }


# ============================================================
# HTML TEMPLATES
# ============================================================

BASE_CSS = """
:root {
    --bg-primary: #0a0a0a;
    --bg-secondary: #111111;
    --bg-tertiary: #1a1a1a;
    --bg-card: #141414;
    --border-color: #2a2a2a;
    --text-primary: #ffffff;
    --text-secondary: #888888;
    --text-muted: #555555;
    --accent-green: #00d4aa;
    --accent-red: #ff4757;
    --accent-yellow: #ffa502;
    --accent-blue: #3498db;
}
.light-theme {
    --bg-primary: #f5f5f5;
    --bg-secondary: #ffffff;
    --bg-tertiary: #e8e8e8;
    --bg-card: #ffffff;
    --border-color: #d0d0d0;
    --text-primary: #1a1a1a;
    --text-secondary: #666666;
    --text-muted: #999999;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    display: flex;
}
.sidebar {
    width: 220px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    position: fixed;
    height: 100vh;
    z-index: 100;
}
.logo { padding: 24px 20px; border-bottom: 1px solid var(--border-color); }
.logo-text { font-family: 'IBM Plex Mono', monospace; font-size: 14px; font-weight: 600; letter-spacing: 2px; }
.nav-section { padding: 16px 0; }
.nav-section-title { font-size: 10px; font-weight: 600; letter-spacing: 1.5px; color: var(--text-muted); padding: 0 20px; margin-bottom: 8px; }
.nav-item { display: flex; align-items: center; padding: 12px 20px; color: var(--text-secondary); text-decoration: none; font-size: 13px; transition: all 0.15s; border-left: 3px solid transparent; }
.nav-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.nav-item.active { background: var(--bg-tertiary); color: var(--text-primary); border-left-color: var(--accent-green); }
.nav-item-icon { width: 18px; margin-right: 12px; opacity: 0.7; }
.main-content { margin-left: 220px; flex: 1; padding: 24px; min-height: 100vh; }
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border-color); }
.page-title { font-size: 20px; font-weight: 600; }
.page-subtitle { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.top-bar-actions { display: flex; align-items: center; gap: 16px; }
.theme-toggle { background: var(--bg-tertiary); border: 1px solid var(--border-color); color: var(--text-primary); padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.refresh-btn { background: var(--accent-green); color: #000; border: none; padding: 8px 20px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; }
.bias-banner { padding: 16px 24px; border-radius: 4px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }
.bias-bullish { background: rgba(0, 212, 170, 0.1); border: 1px solid var(--accent-green); }
.bias-bearish { background: rgba(255, 71, 87, 0.1); border: 1px solid var(--accent-red); }
.bias-neutral { background: rgba(136, 136, 136, 0.1); border: 1px solid var(--text-secondary); }
.bias-forbidden { background: rgba(255, 165, 2, 0.1); border: 1px solid var(--accent-yellow); }
.bias-text { font-size: 14px; font-weight: 600; }
.bias-reason { font-size: 12px; color: var(--text-secondary); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 4px; padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border-color); }
.card-title { font-size: 11px; font-weight: 600; letter-spacing: 1px; color: var(--text-secondary); }
.card-badge { font-size: 10px; padding: 4px 8px; border-radius: 2px; font-weight: 600; }
.badge-green { background: rgba(0, 212, 170, 0.2); color: var(--accent-green); }
.badge-red { background: rgba(255, 71, 87, 0.2); color: var(--accent-red); }
.badge-yellow { background: rgba(255, 165, 2, 0.2); color: var(--accent-yellow); }
.badge-blue { background: rgba(52, 152, 219, 0.2); color: var(--accent-blue); }
.badge-gray { background: rgba(136, 136, 136, 0.2); color: var(--text-secondary); }
.metric { margin-bottom: 12px; }
.metric-label { font-size: 10px; color: var(--text-muted); letter-spacing: 0.5px; }
.metric-value { font-family: 'IBM Plex Mono', monospace; font-size: 14px; margin-top: 2px; }
.metric-large { font-size: 24px; font-weight: 600; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th { text-align: left; padding: 8px; border-bottom: 1px solid var(--border-color); font-weight: 600; font-size: 10px; letter-spacing: 0.5px; color: var(--text-secondary); }
.data-table td { padding: 8px; border-bottom: 1px solid var(--border-color); font-family: 'IBM Plex Mono', monospace; }
.data-table tr:hover { background: var(--bg-tertiary); }
.settings-section { margin-bottom: 32px; }
.settings-section-title { font-size: 14px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border-color); }
.settings-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border-color); }
.settings-label { font-size: 13px; }
.settings-description { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.settings-input { background: var(--bg-tertiary); border: 1px solid var(--border-color); color: var(--text-primary); padding: 8px 12px; border-radius: 4px; font-size: 13px; width: 120px; text-align: right; }
.settings-toggle { position: relative; width: 44px; height: 24px; background: var(--bg-tertiary); border-radius: 12px; cursor: pointer; border: 1px solid var(--border-color); }
.settings-toggle.active { background: var(--accent-green); border-color: var(--accent-green); }
.settings-toggle::after { content: ''; position: absolute; width: 18px; height: 18px; background: var(--text-primary); border-radius: 50%; top: 2px; left: 2px; transition: transform 0.2s; }
.settings-toggle.active::after { transform: translateX(20px); background: #000; }
.footer { margin-top: auto; padding: 16px 20px; border-top: 1px solid var(--border-color); font-size: 10px; color: var(--text-muted); }
@media (max-width: 1024px) {
    .sidebar { width: 60px; }
    .logo-text, .nav-section-title, .nav-item span { display: none; }
    .nav-item { justify-content: center; padding: 16px; }
    .nav-item-icon { margin: 0; }
    .main-content { margin-left: 60px; }
}
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BiasDesk Terminal</title>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>{{ css|safe }}</style>
</head>
<body class="{{ theme }}">
    <nav class="sidebar">
        <div class="logo"><div class="logo-text">BIASDESK</div></div>
        <div class="nav-section">
            <div class="nav-section-title">ANALYSIS</div>
            <a href="/" class="nav-item {{ 'active' if page == 'dashboard' else '' }}"><span class="nav-item-icon">D</span><span>Dashboard</span></a>
           <a href="/news" class="nav-item {{ 'active' if page == 'news' else '' }}"><span class="nav-item-icon">N</span><span>News</span></a>
           <a href="/structure" class="nav-item {{ 'active' if page == 'structure' else '' }}"><span class="nav-item-icon">S</span><span>Structure</span></a>
            <a href="/momentum" class="nav-item {{ 'active' if page == 'momentum' else '' }}"><span class="nav-item-icon">M</span><span>Momentum</span></a>
            <a href="/volatility" class="nav-item {{ 'active' if page == 'volatility' else '' }}"><span class="nav-item-icon">V</span><span>Volatility</span></a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">RISK</div>
            <a href="/position-sizing" class="nav-item {{ 'active' if page == 'position' else '' }}"><span class="nav-item-icon">P</span><span>Position Sizing</span></a>
            <a href="/trade-log" class="nav-item {{ 'active' if page == 'tradelog' else '' }}"><span class="nav-item-icon">T</span><span>Trade Log</span></a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">SYSTEM</div>
            <a href="/settings" class="nav-item {{ 'active' if page == 'settings' else '' }}"><span class="nav-item-icon">G</span><span>Settings</span></a>
            <a href="/audit" class="nav-item {{ 'active' if page == 'audit' else '' }}"><span class="nav-item-icon">A</span><span>Audit Log</span></a>
        </div>
        <div class="footer"><div>7 AGENTS ACTIVE</div><div style="margin-top: 4px;">v2.0.0</div></div>
    </nav>
    <main class="main-content">{{ content|safe }}</main>
    <script>
        function toggleTheme() {
            document.body.classList.toggle('light-theme');
            const theme = document.body.classList.contains('light-theme') ? 'light' : 'dark';
            fetch('/api/settings/theme', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({theme: theme}) });
        }
        function refreshData() { location.reload(); }
        {% if auto_refresh %}setTimeout(() => location.reload(), {{ refresh_interval * 1000 }});{% endif %}
    </script>
</body>
</html>"""

# ============================================================
# ROUTES
# ============================================================
@app.route('/news')
def news():
    scraper = get_news_scraper()
    headlines = scraper.get_all_news()
    
    news_rows = ''
    for item in headlines:
        cat_icon = '🥇' if item['category'] == 'GOLD' else '💱'
        title_color = '#ffd700' if item['category'] == 'GOLD' else 'var(--text-primary)'
        news_rows += f'<div style="display:flex;align-items:center;padding:14px 16px;border-bottom:1px solid var(--border-color);"><span style="font-size:16px;margin-right:12px;">{cat_icon}</span><span style="flex:1;font-size:13px;color:{title_color};">{item["title"]}</span><span style="font-size:11px;color:var(--text-muted);margin-left:16px;white-space:nowrap;">{item["source"]} • {item["time"]}</span></div>'
    
    content = f'''
    <div class="top-bar">
        <div><div class="page-title">Market News</div><div class="page-subtitle">Gold & Forex Headlines</div></div>
        <div class="top-bar-actions">
            <span style="background:#00d4aa;color:#000;padding:4px 8px;border-radius:3px;font-size:10px;font-weight:700;">🟢 LIVE</span>
            <button class="theme-toggle" onclick="toggleTheme()">THEME</button>
            <button class="refresh-btn" onclick="refreshData()">REFRESH</button>
        </div>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:4px;">
        {news_rows if news_rows else '<div style="padding:20px;color:var(--text-muted);">Loading news...</div>'}
    </div>
    <div style="margin-top:12px;font-size:11px;color:var(--text-muted);">
        {len(headlines)} headlines • Auto-refresh 5 min • Sources: Google News RSS
    </div>
    '''
    
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='news', content=content, auto_refresh=True, refresh_interval=300)
    
@app.route('/')
def dashboard():
    data = run_all_agents()
    
    regime_output = safe_get(data, 'agents', 'regime', 'output', default={})
    momentum_output = safe_get(data, 'agents', 'momentum', 'output', default={})
    volatility_output = safe_get(data, 'agents', 'volatility', 'output', default={})
    session_output = safe_get(data, 'agents', 'session', 'output', default={})
    structure_output = safe_get(data, 'agents', 'structure', 'output', default={})
    risk_output = safe_get(data, 'agents', 'risk', 'output', default={})
    recency_output = safe_get(data, 'agents', 'recency', 'output', default={})
    
    regime_internals = safe_get(regime_output, 'internals', default={})
    momentum_internals = safe_get(momentum_output, 'internals', default={})
    
    regime = safe_get(regime_output, 'regime', default='UNKNOWN')
    regime_badge = 'badge-green' if regime == 'TREND_UP' else 'badge-red' if regime == 'TREND_DOWN' else 'badge-gray'
    
    momentum = safe_get(momentum_output, 'state', default='UNKNOWN')
    momentum_badge = 'badge-green' if 'LONG' in str(momentum) else 'badge-red' if 'SHORT' in str(momentum) else 'badge-gray'
    
    volatility = safe_get(volatility_output, 'volatility_state', default='UNKNOWN')
    volatility_badge = 'badge-green' if volatility in ['LOW', 'NORMAL'] else 'badge-yellow' if volatility == 'ELEVATED' else 'badge-red'
    
    tick_bias = safe_get(recency_output, 'tick_bias', default='UNKNOWN')
    recency_badge = 'badge-green' if tick_bias == 'BULLISH' else 'badge-red' if tick_bias == 'BEARISH' else 'badge-gray'
    
    bias = data['bias']
    if data['synthesis_forbidden']:
        bias_class, bias_text, bias_reason = 'bias-forbidden', 'SYNTHESIS FORBIDDEN', ', '.join(data['forbidden_reasons'])
    elif bias == 'BULLISH_BIAS':
        bias_class, bias_text, bias_reason = 'bias-bullish', 'BULLISH BIAS', 'System state aligned for long positions'
    elif bias == 'BEARISH_BIAS':
        bias_class, bias_text, bias_reason = 'bias-bearish', 'BEARISH BIAS', 'System state aligned for short positions'
    elif bias == 'DO_NOT_TRADE':
        bias_class, bias_text, bias_reason = 'bias-forbidden', 'DO NOT TRADE', 'Conditions not favorable'
    else:
        bias_class, bias_text, bias_reason = 'bias-neutral', 'NEUTRAL', 'No directional bias identified'
    
    levels_above = safe_get(structure_output, 'levels_above', default=[]) or []
    levels_below = safe_get(structure_output, 'levels_below', default=[]) or []
    structure_levels = []
    for level in (levels_above or [])[:3]:
        structure_levels.append({'type': 'RESISTANCE', 'price': safe_format(safe_get(level, 'price', default=0), ".2f"), 'strength': safe_get(level, 'strength', default='UNKNOWN'), 'validity': safe_get(level, 'validity', default='UNKNOWN')})
    for level in (levels_below or [])[:3]:
        structure_levels.append({'type': 'SUPPORT', 'price': safe_format(safe_get(level, 'price', default=0), ".2f"), 'strength': safe_get(level, 'strength', default='UNKNOWN'), 'validity': safe_get(level, 'validity', default='UNKNOWN')})
    
    content = f"""
    <div class="top-bar">
        <div><div class="page-title">{data['instrument']}</div><div class="page-subtitle">Last updated: {data['timestamp'][:19].replace('T', ' ')}</div></div>
        <div class="top-bar-actions">
<span style="font-family: 'IBM Plex Mono'; font-size: 24px; font-weight: 600;">{safe_format(data['current_price'], ".2f")}</span>
            <span style="background: {'#00d4aa' if data.get('data_source') == 'LIVE' else '#ffa502'}; color: #000; padding: 4px 8px; border-radius: 3px; font-size: 10px; font-weight: 700; margin-left: 8px;">{'🟢 LIVE' if data.get('data_source') == 'LIVE' else '🟡 DEMO'}</span>
                        <button class="theme-toggle" onclick="toggleTheme()">THEME</button>
            <button class="refresh-btn" onclick="refreshData()">REFRESH</button>
        </div>
    </div>
    <div class="bias-banner {bias_class}">
        <div><div class="bias-text">{bias_text}</div><div class="bias-reason">{bias_reason}</div></div>
        <div style="font-family: 'IBM Plex Mono'; font-size: 12px;">Execution: {data['execution_time_ms']}ms</div>
    </div>
    <div class="card-grid">
        <div class="card">
            <div class="card-header"><span class="card-title">REGIME</span><span class="card-badge {regime_badge}">{regime}</span></div>
            <div class="metric"><div class="metric-label">Duration</div><div class="metric-value">{safe_get(regime_output, 'duration_candles', default=0)} candles</div></div>
            <div class="metric"><div class="metric-label">Prior State</div><div class="metric-value">{safe_get(regime_output, 'prior_regime', default='N/A')}</div></div>
            <div class="metric"><div class="metric-label">ADX</div><div class="metric-value">{safe_format(safe_get(regime_internals, 'adx', default=0), ".1f")}</div></div>
        </div>
        <div class="card">
            <div class="card-header"><span class="card-title">MOMENTUM</span><span class="card-badge {momentum_badge}">{momentum}</span></div>
            <div class="metric"><div class="metric-label">Velocity</div><div class="metric-value">{safe_format(safe_get(momentum_internals, 'velocity', default=0), ".2f")}</div></div>
            <div class="metric"><div class="metric-label">Acceleration</div><div class="metric-value">{safe_format(safe_get(momentum_internals, 'acceleration', default=0), ".2f")}</div></div>
            <div class="metric"><div class="metric-label">Prior State</div><div class="metric-value">{safe_get(momentum_output, 'prior_state', default='N/A')}</div></div>
        </div>
        <div class="card">
            <div class="card-header"><span class="card-title">VOLATILITY</span><span class="card-badge {volatility_badge}">{volatility}</span></div>
            <div class="metric"><div class="metric-label">ATR Current</div><div class="metric-value">{safe_format(safe_get(volatility_output, 'atr_current_pips', default=0), ".1f")} pips</div></div>
            <div class="metric"><div class="metric-label">Spread Status</div><div class="metric-value">{safe_get(volatility_output, 'spread_status', default='UNKNOWN')}</div></div>
            <div class="metric"><div class="metric-label">Spread</div><div class="metric-value">{safe_format(safe_get(volatility_output, 'spread_pips', default=0), ".1f")} pips</div></div>
        </div>
        <div class="card">
            <div class="card-header"><span class="card-title">SESSION</span><span class="card-badge badge-blue">{safe_get(session_output, 'active_session', default='UNKNOWN')}</span></div>
            <div class="metric"><div class="metric-label">Session Age</div><div class="metric-value">{safe_get(session_output, 'session_age', default='N/A')}</div></div>
            <div class="metric"><div class="metric-label">Time to Close</div><div class="metric-value">{safe_get(session_output, 'time_to_close', default='N/A')}</div></div>
            <div class="metric"><div class="metric-label">Boundary Flag</div><div class="metric-value">{safe_get(session_output, 'boundary_flag', default='NONE')}</div></div>
        </div>
    </div>
    <div class="card-grid">
        <div class="card">
            <div class="card-header"><span class="card-title">STRUCTURE LEVELS</span><span class="card-badge badge-gray">{len(levels_above) + len(levels_below)} LEVELS</span></div>
            <table class="data-table">
                <thead><tr><th>TYPE</th><th>PRICE</th><th>STRENGTH</th><th>VALIDITY</th></tr></thead>
                <tbody>{''.join(f"<tr><td>{l['type']}</td><td>{l['price']}</td><td>{l['strength']}</td><td>{l['validity']}</td></tr>" for l in structure_levels)}</tbody>
            </table>
        </div>
        <div class="card">
            <div class="card-header"><span class="card-title">RISK CALCULATOR</span><span class="card-badge {'badge-green' if safe_get(risk_output, 'can_open_new_position', default=False) else 'badge-red'}">{'ACTIVE' if safe_get(risk_output, 'can_open_new_position', default=False) else 'BLOCKED'}</span></div>
            <div class="metric"><div class="metric-label">Account Equity</div><div class="metric-value metric-large">${safe_format(safe_get(risk_output, 'equity', default=0), ",.2f")}</div></div>
            <div class="metric"><div class="metric-label">Risk Per Trade</div><div class="metric-value">${safe_format(safe_get(risk_output, 'risk_per_trade_dollars', default=0), ".2f")} ({safe_format(safe_get(risk_output, 'risk_per_trade_percent', default=0), ".1f")}%)</div></div>
            <div class="metric"><div class="metric-label">Daily Limit Remaining</div><div class="metric-value">${safe_format(safe_get(risk_output, 'daily_limit_remaining', default=0), ".2f")}</div></div>
        </div>
        <div class="card">
            <div class="card-header"><span class="card-title">RECENCY CHECK</span><span class="card-badge {recency_badge}">{tick_bias}</span></div>
            <div class="metric"><div class="metric-label">Tick Direction</div><div class="metric-value">{safe_get(recency_output, 'ticks_up', default=0)} UP / {safe_get(recency_output, 'ticks_down', default=0)} DOWN</div></div>
            <div class="metric"><div class="metric-label">Net Movement</div><div class="metric-value">{safe_format(safe_get(recency_output, 'net_movement_pips', default=0), ".1f")} pips</div></div>
            <div class="metric"><div class="metric-label">Velocity Trend</div><div class="metric-value">{safe_get(recency_output, 'velocity_trend', default='UNKNOWN')}</div></div>
        </div>
    </div>
    """
    
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='dashboard', content=content, auto_refresh=SETTINGS['general']['auto_refresh'], refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/structure')
def structure():
    data = run_all_agents()
    structure_output = safe_get(data, 'agents', 'structure', 'output', default={})
    levels_above = safe_get(structure_output, 'levels_above', default=[]) or []
    levels_below = safe_get(structure_output, 'levels_below', default=[]) or []
    
    content = f"""
    <div class="top-bar"><div><div class="page-title">Structure Analysis</div><div class="page-subtitle">Key support and resistance levels</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button><button class="refresh-btn" onclick="refreshData()">REFRESH</button></div></div>
    <div class="card-grid">
        <div class="card"><div class="card-header"><span class="card-title">CURRENT PRICE</span></div><div class="metric"><div class="metric-value metric-large">{safe_format(data['current_price'], ".2f")}</div><div class="metric-label">{data['instrument']}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">LEVELS FOUND</span></div><div class="metric"><div class="metric-value metric-large">{len(levels_above) + len(levels_below)}</div><div class="metric-label">{len(levels_above)} Above / {len(levels_below)} Below</div></div></div>
    </div>
    <div class="card" style="margin-top: 16px;"><div class="card-header"><span class="card-title">RESISTANCE LEVELS</span></div>
        <table class="data-table"><thead><tr><th>PRICE</th><th>STRENGTH</th><th>VALIDITY</th></tr></thead>
        <tbody>{''.join(f"<tr><td>{safe_format(safe_get(l, 'price', default=0), '.2f')}</td><td>{safe_get(l, 'strength', default='UNKNOWN')}</td><td>{safe_get(l, 'validity', default='UNKNOWN')}</td></tr>" for l in levels_above)}</tbody></table></div>
    <div class="card" style="margin-top: 16px;"><div class="card-header"><span class="card-title">SUPPORT LEVELS</span></div>
        <table class="data-table"><thead><tr><th>PRICE</th><th>STRENGTH</th><th>VALIDITY</th></tr></thead>
        <tbody>{''.join(f"<tr><td>{safe_format(safe_get(l, 'price', default=0), '.2f')}</td><td>{safe_get(l, 'strength', default='UNKNOWN')}</td><td>{safe_get(l, 'validity', default='UNKNOWN')}</td></tr>" for l in levels_below)}</tbody></table></div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='structure', content=content, auto_refresh=SETTINGS['general']['auto_refresh'], refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/momentum')
def momentum():
    data = run_all_agents()
    momentum_output = safe_get(data, 'agents', 'momentum', 'output', default={})
    internals = safe_get(momentum_output, 'internals', default={})
    state = safe_get(momentum_output, 'state', default='UNKNOWN')
    momentum_badge = 'badge-green' if 'LONG' in str(state) else 'badge-red' if 'SHORT' in str(state) else 'badge-gray'
    
    content = f"""
    <div class="top-bar"><div><div class="page-title">Momentum Analysis</div><div class="page-subtitle">Price velocity and acceleration</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button><button class="refresh-btn" onclick="refreshData()">REFRESH</button></div></div>
    <div class="card-grid">
        <div class="card"><div class="card-header"><span class="card-title">STATE</span><span class="card-badge {momentum_badge}">{state}</span></div>
            <div class="metric"><div class="metric-label">Duration</div><div class="metric-value metric-large">{safe_get(momentum_output, 'state_duration_candles', default=0)} candles</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">VELOCITY</span></div>
            <div class="metric"><div class="metric-value metric-large">{safe_format(safe_get(internals, 'velocity', default=0), ".2f")}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">ACCELERATION</span></div>
            <div class="metric"><div class="metric-value metric-large">{safe_format(safe_get(internals, 'acceleration', default=0), ".2f")}</div></div></div>
    </div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='momentum', content=content, auto_refresh=SETTINGS['general']['auto_refresh'], refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/volatility')
def volatility():
    data = run_all_agents()
    volatility_output = safe_get(data, 'agents', 'volatility', 'output', default={})
    state = safe_get(volatility_output, 'volatility_state', default='UNKNOWN')
    volatility_badge = 'badge-green' if state in ['LOW', 'NORMAL'] else 'badge-yellow' if state == 'ELEVATED' else 'badge-red'
    spread_status = safe_get(volatility_output, 'spread_status', default='UNKNOWN')
    spread_badge = 'badge-green' if spread_status == 'ACCEPTABLE' else 'badge-yellow' if spread_status == 'WIDE' else 'badge-red'
    
    content = f"""
    <div class="top-bar"><div><div class="page-title">Volatility Analysis</div><div class="page-subtitle">Market volatility assessment</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button><button class="refresh-btn" onclick="refreshData()">REFRESH</button></div></div>
    <div class="card-grid">
        <div class="card"><div class="card-header"><span class="card-title">VOLATILITY STATE</span><span class="card-badge {volatility_badge}">{state}</span></div>
            <div class="metric"><div class="metric-value metric-large">{state}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">SPREAD STATUS</span><span class="card-badge {spread_badge}">{spread_status}</span></div>
            <div class="metric"><div class="metric-value metric-large">{safe_format(safe_get(volatility_output, 'spread_pips', default=0), ".1f")} pips</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">ATR</span></div>
            <div class="metric"><div class="metric-label">Current</div><div class="metric-value">{safe_format(safe_get(volatility_output, 'atr_current_pips', default=0), ".1f")} pips</div></div>
            <div class="metric"><div class="metric-label">Baseline</div><div class="metric-value">{safe_format(safe_get(volatility_output, 'atr_baseline_pips', default=0), ".1f")} pips</div></div></div>
    </div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='volatility', content=content, auto_refresh=SETTINGS['general']['auto_refresh'], refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/position-sizing')
def position_sizing():
    data = run_all_agents()
    risk_output = safe_get(data, 'agents', 'risk', 'output', default={})
    position_table = safe_get(risk_output, 'position_size_table', default=[]) or []
    
    content = f"""
    <div class="top-bar"><div><div class="page-title">Position Sizing</div><div class="page-subtitle">Risk-based calculator</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button><button class="refresh-btn" onclick="refreshData()">REFRESH</button></div></div>
    <div class="card-grid">
        <div class="card"><div class="card-header"><span class="card-title">ACCOUNT</span></div>
            <div class="metric"><div class="metric-label">Equity</div><div class="metric-value metric-large">${safe_format(safe_get(risk_output, 'equity', default=0), ",.2f")}</div></div>
            <div class="metric"><div class="metric-label">Risk Per Trade</div><div class="metric-value">${safe_format(safe_get(risk_output, 'risk_per_trade_dollars', default=0), ".2f")}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">DAILY LIMITS</span></div>
            <div class="metric"><div class="metric-label">Remaining</div><div class="metric-value metric-large">${safe_format(safe_get(risk_output, 'daily_limit_remaining', default=0), ".2f")}</div></div></div>
    </div>
    <div class="card" style="margin-top: 16px;"><div class="card-header"><span class="card-title">POSITION SIZE TABLE</span></div>
        <table class="data-table"><thead><tr><th>STOP (PIPS)</th><th>LOT SIZE</th><th>RISK ($)</th></tr></thead>
        <tbody>{''.join(f"<tr><td>{r.get('stop_pips', 0)}</td><td>{r.get('lot_size', 0)}</td><td>${r.get('risk_dollars', 0)}</td></tr>" for r in position_table)}</tbody></table></div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='position', content=content, auto_refresh=SETTINGS['general']['auto_refresh'], refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/trade-log')
def trade_log():
    journal = get_trade_journal()
    stats = journal.get_statistics()
    entries = journal.get_recent_entries(20)
    
    content = f"""
    <div class="top-bar"><div><div class="page-title">Trade Log</div><div class="page-subtitle">Decision history</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button><button class="refresh-btn" onclick="refreshData()">REFRESH</button></div></div>
    <div class="card-grid">
        <div class="card"><div class="card-header"><span class="card-title">TOTAL DECISIONS</span></div><div class="metric"><div class="metric-value metric-large">{safe_get(stats, 'total_decisions', default=0)}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">BIAS LONG</span></div><div class="metric"><div class="metric-value metric-large">{safe_get(stats, 'bias_long', default=0)}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">BIAS SHORT</span></div><div class="metric"><div class="metric-value metric-large">{safe_get(stats, 'bias_short', default=0)}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">STAND DOWN</span></div><div class="metric"><div class="metric-value metric-large">{safe_get(stats, 'stand_down', default=0)}</div></div></div>
    </div>
    <div class="card" style="margin-top: 16px;"><div class="card-header"><span class="card-title">RECENT DECISIONS</span></div>
        <table class="data-table"><thead><tr><th>TIME</th><th>DECISION</th><th>BIAS</th></tr></thead>
        <tbody>{''.join(f"<tr><td>{e['timestamp'][:19]}</td><td>{e['decision_type']}</td><td>{e['bias']}</td></tr>" for e in reversed(entries))}</tbody></table></div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='tradelog', content=content, auto_refresh=False, refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/settings')
def settings():
    content = f"""
    <div class="top-bar"><div><div class="page-title">Settings</div><div class="page-subtitle">System configuration</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button></div></div>
    <div class="card">
        <div class="settings-section"><div class="settings-section-title">GENERAL</div>
            <div class="settings-row"><div><div class="settings-label">Instrument</div></div><input type="text" class="settings-input" value="{SETTINGS['general']['instrument']}" disabled></div>
            <div class="settings-row"><div><div class="settings-label">Refresh Interval</div></div><input type="number" class="settings-input" value="{SETTINGS['general']['refresh_interval']}"></div>
        </div>
        <div class="settings-section"><div class="settings-section-title">RISK MANAGEMENT</div>
            <div class="settings-row"><div><div class="settings-label">Account Equity</div></div><input type="number" class="settings-input" value="{SETTINGS['risk']['account_equity']}"></div>
            <div class="settings-row"><div><div class="settings-label">Risk Per Trade (%)</div></div><input type="number" class="settings-input" value="{SETTINGS['risk']['risk_per_trade']}"></div>
            <div class="settings-row"><div><div class="settings-label">Max Daily Loss (%)</div></div><input type="number" class="settings-input" value="{SETTINGS['risk']['max_daily_loss']}"></div>
        </div>
    </div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='settings', content=content, auto_refresh=False, refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/audit')
def audit():
    logger = get_audit_logger()
    summary = logger.get_daily_summary()
    integrity = logger.verify_integrity()
    entries = logger.get_recent_entries(20)
    
    content = f"""
    <div class="top-bar"><div><div class="page-title">Audit Log</div><div class="page-subtitle">System activity records</div></div>
        <div class="top-bar-actions"><button class="theme-toggle" onclick="toggleTheme()">THEME</button><button class="refresh-btn" onclick="refreshData()">REFRESH</button></div></div>
    <div class="card-grid">
        <div class="card"><div class="card-header"><span class="card-title">TODAY'S EVENTS</span></div><div class="metric"><div class="metric-value metric-large">{safe_get(summary, 'total_events', default=0)}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">AGENT RUNS</span></div><div class="metric"><div class="metric-value metric-large">{safe_get(summary, 'agent_runs', default=0)}</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">INTEGRITY</span><span class="card-badge {'badge-green' if safe_get(integrity, 'integrity_status', default='UNKNOWN') == 'PASS' else 'badge-red'}">{safe_get(integrity, 'integrity_status', default='UNKNOWN')}</span></div>
            <div class="metric"><div class="metric-value">{safe_get(integrity, 'verified', default=0)} / {safe_get(integrity, 'total_entries', default=0)}</div></div></div>
    </div>
    <div class="card" style="margin-top: 16px;"><div class="card-header"><span class="card-title">RECENT EVENTS</span></div>
        <table class="data-table"><thead><tr><th>TIME</th><th>EVENT</th><th>SEVERITY</th></tr></thead>
        <tbody>{''.join(f"<tr><td>{e['timestamp'][11:19] if len(e.get('timestamp', '')) > 19 else 'N/A'}</td><td>{e.get('event_type', 'UNKNOWN')}</td><td>{e.get('severity', 'INFO')}</td></tr>" for e in reversed(entries[-10:]))}</tbody></table></div>
    <div class="card" style="margin-top: 16px;"><div class="card-header"><span class="card-title">COMPLIANCE</span></div>
        <div class="metric"><div class="metric-label">Session ID</div><div class="metric-value">{logger.session_id}</div></div>
        <div class="metric"><div class="metric-label">Log File</div><div class="metric-value">{logger.log_file}</div></div>
        <div class="metric"><div class="metric-label">Retention</div><div class="metric-value">5 Years (MiFID II)</div></div></div>
    """
    return render_template_string(DASHBOARD_HTML, css=BASE_CSS, theme='light-theme' if SETTINGS['general']['theme'] == 'light' else '', page='audit', content=content, auto_refresh=False, refresh_interval=SETTINGS['general']['refresh_interval'])

@app.route('/api/data')
def api_data():
    return jsonify(run_all_agents())

@app.route('/api/settings/theme', methods=['POST'])
def update_theme():
    data = request.get_json()
    theme = data.get('theme', 'dark')
    SETTINGS['general']['theme'] = theme
    save_settings()
    return jsonify({'status': 'ok', 'theme': theme})

if __name__ == '__main__':
    print("=" * 60)
    print("BIASDESK TERMINAL v2.0")
    print("=" * 60)
    print(f"Instrument: {INSTRUMENT}")
    print(f"Audit Log: {audit_logger.log_file}")
    print("\nStarting server...")
    print("Open: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
