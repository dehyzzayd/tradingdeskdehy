"""
TRADE JOURNAL - BiasDesk Terminal
Records all trading decisions and outcomes
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import uuid

class TradeJournal:
    """
    Professional trade journaling system.
    Records bias decisions, not actual trades.
    """
    
    VERSION = "1.0"
    
    DECISION_TYPES = {
        'BIAS_LONG': 'Bullish bias identified',
        'BIAS_SHORT': 'Bearish bias identified',
        'STAND_DOWN': 'No trade - conditions unfavorable',
        'FORBIDDEN': 'No trade - synthesis forbidden',
        'OVERRIDE': 'Human override of system'
    }
    
    def __init__(self, journal_folder: str = "outputs"):
        self.journal_folder = Path(journal_folder)
        self.journal_folder.mkdir(parents=True, exist_ok=True)
        self.journal_file = self.journal_folder / "trade_journal.json"
        self._load_journal()
    
    def _load_journal(self):
        """Load existing journal or create new"""
        if self.journal_file.exists():
            with open(self.journal_file, 'r') as f:
                self.journal = json.load(f)
        else:
            self.journal = {
                'version': self.VERSION,
                'created': datetime.now(timezone.utc).isoformat(),
                'entries': [],
                'statistics': {
                    'total_decisions': 0,
                    'bias_long': 0,
                    'bias_short': 0,
                    'stand_down': 0,
                    'forbidden': 0,
                    'override': 0
                }
            }
            self._save_journal()
    
    def _save_journal(self):
        """Persist journal to disk"""
        self.journal['last_updated'] = datetime.now(timezone.utc).isoformat()
        with open(self.journal_file, 'w') as f:
            json.dump(self.journal, f, indent=2)
    
    def record_decision(self, 
                       decision_type: str,
                       instrument: str,
                       agent_states: dict,
                       bias: str,
                       forbidden: bool,
                       forbidden_reason: Optional[str] = None,
                       human_notes: Optional[str] = None) -> dict:
        """
        Record a trading decision.
        """
        entry_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc)
        
        entry = {
            'id': entry_id,
            'timestamp': timestamp.isoformat(),
            'timestamp_unix': timestamp.timestamp(),
            'instrument': instrument,
            'decision_type': decision_type,
            'decision_description': self.DECISION_TYPES.get(decision_type, 'Unknown'),
            'bias': bias,
            'synthesis_forbidden': forbidden,
            'forbidden_reason': forbidden_reason,
            'agent_snapshot': {
                'regime': agent_states.get('regime', {}).get('output', {}).get('regime', 'UNKNOWN'),
                'momentum': agent_states.get('momentum', {}).get('output', {}).get('state', 'UNKNOWN'),
                'volatility': agent_states.get('volatility', {}).get('output', {}).get('volatility_state', 'UNKNOWN'),
                'session': agent_states.get('session', {}).get('output', {}).get('active_session', 'UNKNOWN'),
                'spread_status': agent_states.get('volatility', {}).get('output', {}).get('spread_status', 'UNKNOWN'),
                'tick_bias': agent_states.get('recency', {}).get('output', {}).get('tick_bias', 'UNKNOWN')
            },
            'human_notes': human_notes,
            'outcome': None  # To be filled later if tracking actual trades
        }
        
        self.journal['entries'].append(entry)
        self.journal['statistics']['total_decisions'] += 1
        
        if decision_type == 'BIAS_LONG':
            self.journal['statistics']['bias_long'] += 1
        elif decision_type == 'BIAS_SHORT':
            self.journal['statistics']['bias_short'] += 1
        elif decision_type == 'STAND_DOWN':
            self.journal['statistics']['stand_down'] += 1
        elif decision_type == 'FORBIDDEN':
            self.journal['statistics']['forbidden'] += 1
        elif decision_type == 'OVERRIDE':
            self.journal['statistics']['override'] += 1
        
        self._save_journal()
        return entry
    
    def get_recent_entries(self, count: int = 50) -> List[dict]:
        """Get most recent journal entries"""
        return self.journal['entries'][-count:]
    
    def get_statistics(self) -> dict:
        """Get journal statistics"""
        stats = self.journal['statistics'].copy()
        
        # Calculate percentages
        total = stats['total_decisions']
        if total > 0:
            stats['bias_long_pct'] = round(stats['bias_long'] / total * 100, 1)
            stats['bias_short_pct'] = round(stats['bias_short'] / total * 100, 1)
            stats['stand_down_pct'] = round(stats['stand_down'] / total * 100, 1)
            stats['forbidden_pct'] = round(stats['forbidden'] / total * 100, 1)
            stats['override_pct'] = round(stats['override'] / total * 100, 1)
        else:
            stats['bias_long_pct'] = 0
            stats['bias_short_pct'] = 0
            stats['stand_down_pct'] = 0
            stats['forbidden_pct'] = 0
            stats['override_pct'] = 0
        
        return stats
    
    def get_entries_by_instrument(self, instrument: str) -> List[dict]:
        """Filter entries by instrument"""
        return [e for e in self.journal['entries'] if e['instrument'] == instrument]
    
    def get_entries_by_decision(self, decision_type: str) -> List[dict]:
        """Filter entries by decision type"""
        return [e for e in self.journal['entries'] if e['decision_type'] == decision_type]
    
    def export_csv(self, filepath: Optional[str] = None) -> str:
        """Export journal to CSV format"""
        if filepath is None:
            filepath = self.journal_folder / "trade_journal_export.csv"
        
        import csv
        
        headers = ['id', 'timestamp', 'instrument', 'decision_type', 'bias', 
                  'forbidden', 'regime', 'momentum', 'volatility', 'session', 'notes']
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for entry in self.journal['entries']:
                row = [
                    entry['id'],
                    entry['timestamp'],
                    entry['instrument'],
                    entry['decision_type'],
                    entry['bias'],
                    entry['synthesis_forbidden'],
                    entry['agent_snapshot']['regime'],
                    entry['agent_snapshot']['momentum'],
                    entry['agent_snapshot']['volatility'],
                    entry['agent_snapshot']['session'],
                    entry.get('human_notes', '')
                ]
                writer.writerow(row)
        
        return str(filepath)


# Singleton instance
_trade_journal = None

def get_trade_journal() -> TradeJournal:
    """Get or create trade journal instance"""
    global _trade_journal
    if _trade_journal is None:
        _trade_journal = TradeJournal()
    return _trade_journal


if __name__ == "__main__":
    print("=" * 60)
    print("TESTING TRADE JOURNAL")
    print("=" * 60)
    
    journal = get_trade_journal()
    
    # Record test decisions
    test_states = {
        'regime': {'output': {'regime': 'TREND_UP'}},
        'momentum': {'output': {'state': 'ACCELERATING_LONG'}},
        'volatility': {'output': {'volatility_state': 'NORMAL', 'spread_status': 'ACCEPTABLE'}},
        'session': {'output': {'active_session': 'LONDON'}},
        'recency': {'output': {'tick_bias': 'BULLISH'}}
    }
    
    journal.record_decision(
        decision_type='BIAS_LONG',
        instrument='XAU/USD',
        agent_states=test_states,
        bias='BULLISH_BIAS',
        forbidden=False,
        human_notes='Strong trend alignment'
    )
    
    journal.record_decision(
        decision_type='FORBIDDEN',
        instrument='XAU/USD',
        agent_states=test_states,
        bias='NEUTRAL',
        forbidden=True,
        forbidden_reason='EXTREME_SPREAD'
    )
    
    print(f"\n1. Journal file: {journal.journal_file}")
    
    print("\n2. Recent entries:")
    for entry in journal.get_recent_entries(5):
        print(f"   [{entry['decision_type']}] {entry['instrument']} - {entry['bias']}")
    
    print("\n3. Statistics:")
    stats = journal.get_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 60)
    print("TRADE JOURNAL TEST COMPLETE")
    print("=" * 60)
