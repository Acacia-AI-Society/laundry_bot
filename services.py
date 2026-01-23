import datetime
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from pydantic import BaseModel
import pytz
import config

# Singapore timezone for usage tracking
SINGAPORE_TZ = pytz.timezone('Asia/Singapore')

# Initialize Supabase
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

# --- MODELS ---
class UserInfo(BaseModel):
    id: int
    username: str
    first_name: str
    display_name: Optional[str] = None
    level: Optional[str] = None
    house: Optional[str] = None

class MachineState(BaseModel):
    id: str
    type: str
    level: str
    status: str
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    current_user: Optional[UserInfo] = None
    last_user: Optional[UserInfo] = None
    last_ping: Optional[datetime.datetime] = None # Added for persistent cooldown

# --- USER SERVICES ---

def get_user(user_id: int) -> Optional[UserInfo]:
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if response.data:
        return UserInfo(**response.data[0])
    return None

def create_user(user_info: UserInfo):
    data = user_info.dict(exclude_none=True)
    supabase.table("users").upsert(data).execute()

# --- MACHINE SERVICES ---

def get_machines_by_level(level: str) -> List[MachineState]:
    query = supabase.table("machines").select(
        "*, current_user:users!current_user_id(*), last_user:users!last_user_id(*)"
    ).eq("level", level).order("id")
    
    response = query.execute()
    return _parse_machines(response.data)

def get_machine(machine_id: str) -> Optional[MachineState]:
    query = supabase.table("machines").select(
        "*, current_user:users!current_user_id(*), last_user:users!last_user_id(*)"
    ).eq("id", machine_id)
    
    response = query.execute()
    if response.data:
        return _parse_machines(response.data)[0]
    return None

def get_running_machines() -> List[MachineState]:
    """Fetches ONLY machines that are currently marked as Running."""
    query = supabase.table("machines").select(
        "*, current_user:users!current_user_id(*)"
    ).eq("status", "Running")
    
    response = query.execute()
    return _parse_machines(response.data)

def update_machine_status(machine_id: str, status: str, end_time: datetime.datetime, user_id: int, duration_minutes: int = 0):
    # Update machine state
    supabase.table("machines").update({
        "status": status,
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": end_time.isoformat(),
        "current_user_id": user_id,
        "last_user_id": user_id,
        "last_ping": None # Reset ping when new cycle starts
    }).eq("id", machine_id).execute()

    # Log usage event for peak period tracking
    if status == "Running" and duration_minutes > 0:
        level = machine_id.split("_")[0]  # Extract level from machine_id (e.g., "9_washer_1" -> "9")
        try:
            log_usage_event(machine_id, user_id, level, duration_minutes)
        except Exception as e:
            print(f"⚠️ Failed to log usage event: {e}")

def reset_machine_status(machine_id: str):
    # Used when force stopping or marking as finished
    supabase.table("machines").update({
        "status": "Finished",
        "current_user_id": None # Remove current user ownership
    }).eq("id", machine_id).execute()

def make_machine_available(machine_id: str):
    # Used when user collects laundry
    supabase.table("machines").update({
        "status": "Available",
        "current_user_id": None,
        "start_time": None,
        "end_time": None,
        "last_ping": None # Clear ping history
    }).eq("id", machine_id).execute()

def register_ping(machine_id: str):
    # Updates the last_ping timestamp to NOW
    supabase.table("machines").update({
        "last_ping": datetime.datetime.now().isoformat()
    }).eq("id", machine_id).execute()

def log_audit_event(event: str, machine_id: str, victim_id: int, offender_id: int):
    supabase.table("audit_logs").insert({
        "event": event,
        "machine_id": machine_id,
        "victim_id": victim_id,
        "offender_id": offender_id
    }).execute()

# --- HELPER ---
def _parse_machines(data: List[Dict]) -> List[MachineState]:
    results = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for row in data:
        current_u = UserInfo(**row['current_user']) if row.get('current_user') else None
        last_u = UserInfo(**row['last_user']) if row.get('last_user') else None
        
        end_dt = None
        if row.get('end_time'):
            end_dt = datetime.datetime.fromisoformat(row['end_time'].replace('Z', '+00:00'))

        ping_dt = None
        if row.get('last_ping'):
            ping_dt = datetime.datetime.fromisoformat(row['last_ping'].replace('Z', '+00:00'))

        status = row['status']
        if status == 'Running' and end_dt and end_dt < now:
            status = 'Finished'
            
        m = MachineState(
            id=row['id'],
            type=row['type'],
            level=row['level'],
            status=status,
            start_time=row.get('start_time'),
            end_time=end_dt,
            current_user=current_u,
            last_user=last_u,
            last_ping=ping_dt
        )
        results.append(m)
    return results

# --- USAGE EVENT LOGGING (for peak period tracking) ---

def log_usage_event(machine_id: str, user_id: int, level: str, duration_minutes: int):
    """Log a machine start event for peak period analytics."""
    now = datetime.datetime.now(SINGAPORE_TZ)
    supabase.table("machine_usage_events").insert({
        "machine_id": machine_id,
        "user_id": user_id,
        "level": level,
        "duration_minutes": duration_minutes,
        "hour_of_day": now.hour,
        "day_of_week": now.weekday()  # 0=Monday, 6=Sunday
    }).execute()

def get_hourly_usage_data(level: str, days_back: int = 30) -> List[Dict]:
    """Fetch usage events for the past N days for a specific level."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days_back)).isoformat()
    response = supabase.table("machine_usage_events") \
        .select("hour_of_day, day_of_week, machine_id, created_at") \
        .eq("level", level) \
        .gte("created_at", cutoff) \
        .execute()
    return response.data

# --- COMPLAINT SERVICES ---

def can_submit_complaint(user_id: int, machine_id: str) -> bool:
    """Check if user can submit complaint (rate limit: 1 per machine per hour)."""
    one_hour_ago = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    response = supabase.table("complaints") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("machine_id", machine_id) \
        .gte("created_at", one_hour_ago) \
        .execute()
    return len(response.data) == 0

def log_complaint(user_id: int, machine_id: str, reported_status: str):
    """Log a machine discrepancy complaint."""
    supabase.table("complaints").insert({
        "user_id": user_id,
        "machine_id": machine_id,
        "reported_status": reported_status
    }).execute()