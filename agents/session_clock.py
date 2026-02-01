# =============================================================================
# AGENT 5: SESSION CLOCK
# =============================================================================
# This agent tracks trading sessions and time-based conditions.
#
# It answers: "Which trading session is active right now?"
#
# Possible session outputs:
#   - ASIA: Asian/Tokyo session active
#   - LONDON: London/European session active
#   - NEW_YORK: New York/US session active
#   - OVERLAP_LONDON_NY: Both London and New York active (high liquidity)
#   - OFF_HOURS: No major session active
#
# Boundary flags:
#   - NONE: Normal session time
#   - SESSION_OPEN_30MIN: Within 30 minutes of session open
#   - SESSION_CLOSE_30MIN: Within 30 minutes of session close
#   - OVERLAP_ACTIVE: Two sessions overlapping
#
# This agent does NOT suggest which session is best.
# This agent only reports time-based facts.
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
    ASIA_SESSION_START,
    ASIA_SESSION_END,
    LONDON_SESSION_START,
    LONDON_SESSION_END,
    NEW_YORK_SESSION_START,
    NEW_YORK_SESSION_END,
    OUTPUT_FOLDER
)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def is_within_session(current_hour, start_hour, end_hour):
    """
    Check if current hour falls within a session's hours.
    
    Handles sessions that cross midnight (e.g., start=22, end=7).
    
    Parameters:
    - current_hour: Current hour in UTC (0-23)
    - start_hour: Session start hour in UTC
    - end_hour: Session end hour in UTC
    
    Returns:
    - True if within session, False otherwise
    """
    if start_hour < end_hour:
        # Normal session (doesn't cross midnight)
        return start_hour <= current_hour < end_hour
    else:
        # Session crosses midnight
        return current_hour >= start_hour or current_hour < end_hour


def minutes_until_session_end(current_hour, current_minute, end_hour):
    """
    Calculate minutes until session ends.
    
    Parameters:
    - current_hour: Current hour (0-23)
    - current_minute: Current minute (0-59)
    - end_hour: Session end hour
    
    Returns:
    - Minutes until session end
    """
    current_total_minutes = current_hour * 60 + current_minute
    end_total_minutes = end_hour * 60
    
    if end_total_minutes > current_total_minutes:
        return end_total_minutes - current_total_minutes
    else:
        # Session ends tomorrow
        return (24 * 60 - current_total_minutes) + end_total_minutes


def minutes_since_session_start(current_hour, current_minute, start_hour):
    """
    Calculate minutes since session started.
    
    Parameters:
    - current_hour: Current hour (0-23)
    - current_minute: Current minute (0-59)
    - start_hour: Session start hour
    
    Returns:
    - Minutes since session start
    """
    current_total_minutes = current_hour * 60 + current_minute
    start_total_minutes = start_hour * 60
    
    if current_total_minutes >= start_total_minutes:
        return current_total_minutes - start_total_minutes
    else:
        # Session started yesterday
        return (24 * 60 - start_total_minutes) + current_total_minutes


def format_duration(minutes):
    """
    Format minutes as hours and minutes string.
    
    Parameters:
    - minutes: Total minutes
    
    Returns:
    - Formatted string like "2h 30m"
    """
    hours = minutes // 60
    mins = minutes % 60
    
    if hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m"


# -----------------------------------------------------------------------------
# MAIN AGENT CLASS
# -----------------------------------------------------------------------------
class SessionClock:
    """
    The Session Clock Agent.
    
    This agent reports which trading session is currently active.
    """
    
    def __init__(self):
        """
        Initialize the agent.
        """
        self.agent_name = "SESSION_CLOCK"
        self.agent_version = "1.0"
        
        self.instrument = INSTRUMENT
        
        # Session times (in UTC)
        self.sessions = {
            'ASIA': {
                'start': ASIA_SESSION_START,
                'end': ASIA_SESSION_END,
                'name': 'ASIA'
            },
            'LONDON': {
                'start': LONDON_SESSION_START,
                'end': LONDON_SESSION_END,
                'name': 'LONDON'
            },
            'NEW_YORK': {
                'start': NEW_YORK_SESSION_START,
                'end': NEW_YORK_SESSION_END,
                'name': 'NEW_YORK'
            }
        }
    
    def check_session(self, timestamp=None):
        """
        Determine the current trading session.
        
        Parameters:
        - timestamp: Optional datetime object. Uses current UTC time if not provided.
        
        Returns:
        - Dictionary containing the session report
        """
        # Use provided timestamp or current UTC time
        if timestamp is None:
            now = datetime.now(timezone.utc)
        else:
            now = timestamp
        
        analysis_time = now.isoformat()
        current_hour = now.hour
        current_minute = now.minute
        
        # Check which sessions are active
        asia_active = is_within_session(
            current_hour, 
            self.sessions['ASIA']['start'],
            self.sessions['ASIA']['end']
        )
        
        london_active = is_within_session(
            current_hour,
            self.sessions['LONDON']['start'],
            self.sessions['LONDON']['end']
        )
        
        new_york_active = is_within_session(
            current_hour,
            self.sessions['NEW_YORK']['start'],
            self.sessions['NEW_YORK']['end']
        )
        
        # Determine primary session
        active_session = self._determine_active_session(
            asia_active, london_active, new_york_active
        )
        
        # Calculate session age and time to close
        session_age_minutes = 0
        minutes_to_close = 0
        
        if active_session == 'ASIA':
            session_age_minutes = minutes_since_session_start(
                current_hour, current_minute, self.sessions['ASIA']['start']
            )
            minutes_to_close = minutes_until_session_end(
                current_hour, current_minute, self.sessions['ASIA']['end']
            )
        elif active_session == 'LONDON':
            session_age_minutes = minutes_since_session_start(
                current_hour, current_minute, self.sessions['LONDON']['start']
            )
            minutes_to_close = minutes_until_session_end(
                current_hour, current_minute, self.sessions['LONDON']['end']
            )
        elif active_session == 'NEW_YORK':
            session_age_minutes = minutes_since_session_start(
                current_hour, current_minute, self.sessions['NEW_YORK']['start']
            )
            minutes_to_close = minutes_until_session_end(
                current_hour, current_minute, self.sessions['NEW_YORK']['end']
            )
        elif active_session == 'OVERLAP_LONDON_NY':
            # For overlap, use London's timing as primary
            session_age_minutes = minutes_since_session_start(
                current_hour, current_minute, self.sessions['NEW_YORK']['start']
            )
            minutes_to_close = minutes_until_session_end(
                current_hour, current_minute, self.sessions['LONDON']['end']
            )
        
        # Determine boundary flag
        boundary_flag = self._determine_boundary_flag(
            active_session, session_age_minutes, minutes_to_close,
            london_active, new_york_active
        )
        
        # Calculate next session transition
        next_transition = self._get_next_transition(
            current_hour, current_minute, active_session
        )
        
        return self._create_report(
            active_session=active_session,
            analysis_time=analysis_time,
            current_hour=current_hour,
            current_minute=current_minute,
            session_age_minutes=session_age_minutes,
            minutes_to_close=minutes_to_close,
            boundary_flag=boundary_flag,
            next_transition=next_transition,
            asia_active=asia_active,
            london_active=london_active,
            new_york_active=new_york_active
        )
    
    def _determine_active_session(self, asia, london, new_york):
        """
        Determine the primary active session.
        
        Priority: Overlap > Individual sessions > Off hours
        """
        # Check for London/NY overlap (highest liquidity)
        if london and new_york:
            return 'OVERLAP_LONDON_NY'
        
        # Check individual sessions (priority: London > NY > Asia)
        if london:
            return 'LONDON'
        if new_york:
            return 'NEW_YORK'
        if asia:
            return 'ASIA'
        
        return 'OFF_HOURS'
    
    def _determine_boundary_flag(self, session, age_minutes, minutes_to_close,
                                  london_active, new_york_active):
        """
        Determine if we're near a session boundary.
        """
        # Check for overlap
        if london_active and new_york_active:
            return 'OVERLAP_ACTIVE'
        
        # Check if session just opened (within 30 minutes)
        if age_minutes <= 30 and session != 'OFF_HOURS':
            return 'SESSION_OPEN_30MIN'
        
        # Check if session closing soon (within 30 minutes)
        if minutes_to_close <= 30 and session != 'OFF_HOURS':
            return 'SESSION_CLOSE_30MIN'
        
        return 'NONE'
    
    def _get_next_transition(self, current_hour, current_minute, current_session):
        """
        Calculate when the next session transition will occur.
        """
        # Simplified: just show what's coming next
        if current_session == 'OFF_HOURS':
            return {'session': 'ASIA', 'in': 'Soon'}
        elif current_session == 'ASIA':
            return {'session': 'LONDON', 'in': 'After Asia close'}
        elif current_session == 'LONDON':
            return {'session': 'OVERLAP_LONDON_NY', 'in': 'When NY opens'}
        elif current_session == 'OVERLAP_LONDON_NY':
            return {'session': 'NEW_YORK', 'in': 'After London close'}
        elif current_session == 'NEW_YORK':
            return {'session': 'OFF_HOURS', 'in': 'After NY close'}
        
        return {'session': 'UNKNOWN', 'in': 'UNKNOWN'}
    
    def _create_report(self, active_session, analysis_time, current_hour,
                       current_minute, session_age_minutes, minutes_to_close,
                       boundary_flag, next_transition, asia_active,
                       london_active, new_york_active):
        """
        Create the standardized report dictionary.
        """
        report = {
            "agent": self.agent_name,
            "version": self.agent_version,
            "timestamp": analysis_time,
            "instrument": self.instrument,
            "status": "TIME_CHECK_COMPLETE",
            "output": {
                "active_session": active_session,
                "session_age": format_duration(session_age_minutes),
                "time_to_close": format_duration(minutes_to_close),
                "boundary_flag": boundary_flag,
                "next_transition": next_transition
            },
            "internals": {
                "current_hour_utc": current_hour,
                "current_minute": current_minute,
                "asia_active": asia_active,
                "london_active": london_active,
                "new_york_active": new_york_active,
                "session_age_minutes": session_age_minutes,
                "minutes_to_close": minutes_to_close
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
        
        filename = f"session_clock_report.json"
        filepath = os.path.join(full_output_path, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filepath


# -----------------------------------------------------------------------------
# TEST THE AGENT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("TESTING SESSION CLOCK AGENT")
    print("=" * 60)
    
    # Create the agent
    print("\n1. Creating Session Clock agent...")
    agent = SessionClock()
    print(f"   Agent: {agent.agent_name} v{agent.agent_version}")
    
    # Show session times
    print("\n2. Session Schedule (UTC):")
    print(f"   ASIA:     {agent.sessions['ASIA']['start']:02d}:00 - {agent.sessions['ASIA']['end']:02d}:00")
    print(f"   LONDON:   {agent.sessions['LONDON']['start']:02d}:00 - {agent.sessions['LONDON']['end']:02d}:00")
    print(f"   NEW_YORK: {agent.sessions['NEW_YORK']['start']:02d}:00 - {agent.sessions['NEW_YORK']['end']:02d}:00")
    
    # Check current session
    print("\n3. Checking current session...")
    report = agent.check_session()
    
    # Display results
    print("\n4. Results:")
    print("-" * 40)
    print(f"   ACTIVE SESSION: {report['output']['active_session']}")
    print(f"   Session Age: {report['output']['session_age']}")
    print(f"   Time to Close: {report['output']['time_to_close']}")
    print(f"   Boundary Flag: {report['output']['boundary_flag']}")
    print(f"   Next: {report['output']['next_transition']['session']} ({report['output']['next_transition']['in']})")
    print("-" * 40)
    print(f"   Current Time (UTC): {report['internals']['current_hour_utc']:02d}:{report['internals']['current_minute']:02d}")
    print(f"   Asia Active: {report['internals']['asia_active']}")
    print(f"   London Active: {report['internals']['london_active']}")
    print(f"   New York Active: {report['internals']['new_york_active']}")
    
    # Save report
    print("\n5. Saving report...")
    filepath = agent.save_report(report)
    print(f"   Saved to: {filepath}")
    
    # Show full report
    print("\n6. Full Report (JSON):")
    print("-" * 40)
    print(json.dumps(report, indent=2))
    
    # Test different times
    print("\n7. Testing different times:")
    print("-" * 40)
    
    test_times = [
        (3, 0, "03:00 UTC - Should be ASIA"),
        (8, 30, "08:30 UTC - Should be LONDON"),
        (14, 0, "14:00 UTC - Should be OVERLAP"),
        (18, 0, "18:00 UTC - Should be NEW_YORK"),
        (23, 0, "23:00 UTC - Should be OFF_HOURS"),
    ]
    
    for hour, minute, description in test_times:
        test_time = datetime(2026, 1, 26, hour, minute, tzinfo=timezone.utc)
        test_report = agent.check_session(test_time)
        print(f"   {description}")
        print(f"      → {test_report['output']['active_session']} ({test_report['output']['boundary_flag']})")
    
    print("\n" + "=" * 60)
    print("SESSION CLOCK TEST COMPLETE")
    print("=" * 60)
