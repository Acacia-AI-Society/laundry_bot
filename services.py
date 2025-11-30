import datetime
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from pydantic import BaseModel
import config

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
    # Fetch machines for a specific level
    # We explicitly join user data to get display names
    query = supabase.table("machines").select(
        "*, current_user:users!current_user_id(*), last_user:users!last_user_id(*)"
    ).eq("level", level).order("id")
    
    response = query.execute()
    return _parse_machines(response.data)

def get_all_machines() -> List[MachineState]:
    query = supabase.table("machines").select(
        "*, current_user:users!current_user_id(*), last_user:users!last_user_id(*)"
    ).order("level").order("id")
    
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

# --- NEW: FOR RESTORING TIMERS ---
def get_running_machines() -> List[MachineState]:
    """Fetches ONLY machines that are currently marked as Running."""
    query = supabase.table("machines").select(
        "*, current_user:users!current_user_id(*)"
    ).eq("status", "Running")
    
    response = query.execute()
    return _parse_machines(response.data)

def update_machine_status(machine_id: str, status: str, end_time: datetime.datetime, user_id: int):
    # Update machine state
    supabase.table("machines").update({
        "status": status,
        "start_time": datetime.datetime.now().isoformat(),
        "end_time": end_time.isoformat(),
        "current_user_id": user_id,
        "last_user_id": user_id
    }).eq("id", machine_id).execute()

def reset_machine_status(machine_id: str):
    # Used when force stopping or marking as finished
    supabase.table("machines").update({
        "status": "Finished",
        "current_user_id": None # Remove current user ownership (but keep last_user_id implicitly)
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
        # Pydantic parsing
        current_u = UserInfo(**row['current_user']) if row.get('current_user') else None
        last_u = UserInfo(**row['last_user']) if row.get('last_user') else None
        
        # Parse timestamp string from DB to datetime object
        end_dt = None
        if row.get('end_time'):
            end_dt = datetime.datetime.fromisoformat(row['end_time'].replace('Z', '+00:00'))

        status = row['status']
        
        # LAZY EVALUATION: If DB says "Running" but time is up, treat as "Finished"
        # We don't update DB here to save writes, UI just shows it correctly.
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
            last_user=last_u
        )
        results.append(m)
    return results