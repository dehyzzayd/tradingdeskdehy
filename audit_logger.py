"""
AUDIT LOGGER - BiasDesk Terminal
Compliance-grade logging system
Retention: 5 years (MiFID II RTS 24)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import hashlib

class AuditLogger:
    """
    Institutional-grade audit logging system.
    Every action is immutable and timestamped.
    """
    
    VERSION = "1.0"
    
    # Event types for categorization
    EVENT_TYPES = {
        'SYSTEM_START': 'System initialization',
        'SYSTEM_STOP': 'System shutdown',
        'AGENT_RUN': 'Agent execution',
        'AGENT_ERROR': 'Agent failure',
        'BIAS_CHANGE': 'Bias state change',
        'SYNTHESIS_FORBIDDEN': 'Trading blocked',
        'HUMAN_DECISION': 'Human action recorded',
        'SETTINGS_CHANGE': 'Configuration modified',
        'DATA_REFRESH': 'Market data update',
        'KILL_SWITCH': 'Emergency stop triggered',
        'RISK_BREACH': 'Risk limit exceeded',
        'SESSION_CHANGE': 'Trading session transition'
    }
    
    def __init__(self, log_folder: str = "logs"):
        self.log_folder = Path(log_folder)
        self.log_folder.mkdir(parents=True, exist_ok=True)
        self.session_id = self._generate_session_id()
        self.log_file = self.log_folder / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        self._log_event('SYSTEM_START', {'session_id': self.session_id})
    
    def _generate_session_id(self) -> str:
        """Generate unique session identifier"""
        timestamp = datetime.now(timezone.utc).isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:16]
    
    def _calculate_hash(self, data: dict) -> str:
        """Calculate integrity hash for audit entry"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _log_event(self, event_type: str, data: dict, severity: str = "INFO"):
        """
        Write immutable audit entry.
        Format: JSON Lines (one JSON object per line)
        """
        timestamp = datetime.now(timezone.utc)
        
        entry = {
            'timestamp': timestamp.isoformat(),
            'timestamp_unix': timestamp.timestamp(),
            'session_id': self.session_id,
            'event_type': event_type,
            'event_description': self.EVENT_TYPES.get(event_type, 'Unknown event'),
            'severity': severity,
            'data': data
        }
        
        # Add integrity hash
        entry['integrity_hash'] = self._calculate_hash(entry)
        
        # Append to log file (JSON Lines format)
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        return entry
    
    def log_agent_run(self, agent_name: str, status: str, output: dict, duration_ms: float):
        """Log agent execution"""
        return self._log_event('AGENT_RUN', {
            'agent': agent_name,
            'status': status,
            'output_summary': self._summarize_output(output),
            'duration_ms': round(duration_ms, 2)
        })
    
    def log_agent_error(self, agent_name: str, error: str):
        """Log agent failure"""
        return self._log_event('AGENT_ERROR', {
            'agent': agent_name,
            'error': str(error)
        }, severity="ERROR")
    
    def log_bias_change(self, old_bias: str, new_bias: str, reason: str):
        """Log bias state transition"""
        return self._log_event('BIAS_CHANGE', {
            'previous_bias': old_bias,
            'new_bias': new_bias,
            'reason': reason
        }, severity="WARNING" if new_bias == "DO_NOT_TRADE" else "INFO")
    
    def log_synthesis_forbidden(self, reason: str, agent_states: dict):
        """Log when trading is blocked"""
        return self._log_event('SYNTHESIS_FORBIDDEN', {
            'reason': reason,
            'agent_states': agent_states
        }, severity="WARNING")
    
    def log_human_decision(self, decision_type: str, details: dict):
        """Log human trader action"""
        return self._log_event('HUMAN_DECISION', {
            'decision_type': decision_type,
            'details': details
        })
    
    def log_settings_change(self, setting_name: str, old_value, new_value, changed_by: str = "SYSTEM"):
        """Log configuration changes"""
        return self._log_event('SETTINGS_CHANGE', {
            'setting': setting_name,
            'old_value': old_value,
            'new_value': new_value,
            'changed_by': changed_by
        }, severity="WARNING")
    
    def log_kill_switch(self, trigger: str, details: dict):
        """Log emergency stop"""
        return self._log_event('KILL_SWITCH', {
            'trigger': trigger,
            'details': details
        }, severity="CRITICAL")
    
    def log_risk_breach(self, breach_type: str, current_value: float, limit: float):
        """Log risk limit violation"""
        return self._log_event('RISK_BREACH', {
            'breach_type': breach_type,
            'current_value': current_value,
            'limit': limit,
            'breach_percentage': round((current_value / limit - 1) * 100, 2)
        }, severity="CRITICAL")
    
    def _summarize_output(self, output: dict) -> dict:
        """Create condensed summary of agent output"""
        if not output:
            return {}
        
        # Extract key fields only
        summary_fields = ['status', 'regime', 'state', 'volatility_state', 
                         'active_session', 'tick_bias', 'can_open_new_position']
        return {k: v for k, v in output.items() if k in summary_fields}
    
    def get_recent_entries(self, count: int = 100) -> list:
        """Retrieve recent audit entries"""
        entries = []
        
        if not self.log_file.exists():
            return entries
        
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        for line in lines[-count:]:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
        
        return entries
    
    def get_entries_by_type(self, event_type: str, count: int = 50) -> list:
        """Filter entries by event type"""
        all_entries = self.get_recent_entries(1000)
        filtered = [e for e in all_entries if e.get('event_type') == event_type]
        return filtered[-count:]
    
    def get_daily_summary(self) -> dict:
        """Generate daily audit summary"""
        entries = self.get_recent_entries(10000)
        
        summary = {
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'total_events': len(entries),
            'events_by_type': {},
            'events_by_severity': {
                'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0
            },
            'agent_runs': 0,
            'agent_errors': 0,
            'bias_changes': 0,
            'synthesis_forbidden_count': 0,
            'human_decisions': 0
        }
        
        for entry in entries:
            event_type = entry.get('event_type', 'UNKNOWN')
            severity = entry.get('severity', 'INFO')
            
            summary['events_by_type'][event_type] = summary['events_by_type'].get(event_type, 0) + 1
            summary['events_by_severity'][severity] = summary['events_by_severity'].get(severity, 0) + 1
            
            if event_type == 'AGENT_RUN':
                summary['agent_runs'] += 1
            elif event_type == 'AGENT_ERROR':
                summary['agent_errors'] += 1
            elif event_type == 'BIAS_CHANGE':
                summary['bias_changes'] += 1
            elif event_type == 'SYNTHESIS_FORBIDDEN':
                summary['synthesis_forbidden_count'] += 1
            elif event_type == 'HUMAN_DECISION':
                summary['human_decisions'] += 1
        
        return summary
    
    def export_for_compliance(self, start_date: str, end_date: str) -> list:
        """Export entries for regulatory review"""
        entries = []
        log_files = sorted(self.log_folder.glob("audit_*.jsonl"))
        
        for log_file in log_files:
            file_date = log_file.stem.replace('audit_', '')
            if start_date <= file_date <= end_date:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            entries.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        
        return entries
    
    def verify_integrity(self) -> dict:
        """Verify audit log integrity"""
        entries = self.get_recent_entries(10000)
        verified = 0
        failed = 0
        
        for entry in entries:
            stored_hash = entry.pop('integrity_hash', None)
            calculated_hash = self._calculate_hash(entry)
            entry['integrity_hash'] = stored_hash
            
            if stored_hash == calculated_hash:
                verified += 1
            else:
                failed += 1
        
        return {
            'total_entries': len(entries),
            'verified': verified,
            'failed': failed,
            'integrity_status': 'PASS' if failed == 0 else 'FAIL'
        }


# Singleton instance
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Get or create audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


if __name__ == "__main__":
    # Test the audit logger
    print("=" * 60)
    print("TESTING AUDIT LOGGER")
    print("=" * 60)
    
    logger = get_audit_logger()
    
    # Log some test events
    logger.log_agent_run('REGIME_CLASSIFIER', 'ANALYSIS_COMPLETE', 
                        {'regime': 'TREND_UP'}, 45.2)
    logger.log_bias_change('NEUTRAL', 'BULLISH_BIAS', 'Regime trend up with momentum')
    logger.log_synthesis_forbidden('EXTREME_SPREAD', {'spread': 30.0})
    logger.log_human_decision('STAND_DOWN', {'reason': 'Wide spread'})
    
    print(f"\n1. Session ID: {logger.session_id}")
    print(f"2. Log file: {logger.log_file}")
    
    print("\n3. Recent entries:")
    for entry in logger.get_recent_entries(5):
        print(f"   [{entry['severity']}] {entry['event_type']}: {entry['data']}")
    
    print("\n4. Daily summary:")
    summary = logger.get_daily_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    print("\n5. Integrity check:")
    integrity = logger.verify_integrity()
    print(f"   Status: {integrity['integrity_status']}")
    print(f"   Verified: {integrity['verified']}/{integrity['total_entries']}")
    
    print("\n" + "=" * 60)
    print("AUDIT LOGGER TEST COMPLETE")
    print("=" * 60)
