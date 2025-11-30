import os
import json
from dotenv import load_dotenv

# Load env from local file or secrets path
if os.path.exists(".env"):
    load_dotenv(".env")
elif os.path.exists("/secrets/.env"):
    load_dotenv("/secrets/.env")

# Telegram Config
TOKEN = os.getenv("TOKEN")
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS", "[]"))

# Supabase Config
SUPABASE_URL = os.getenv("SUPABASE_URL")

# Priority: Try 'SUPABASE_SECRET_KEY' (New name) -> Fallback to 'SUPABASE_KEY' (Old name)
# We use the SECRET key because the Bot needs admin rights to update tables.
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")

if not TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ CRITICAL WARNING: Missing Config Variables.")
    print(f"Token: {'OK' if TOKEN else 'MISSING'}")
    print(f"Supabase URL: {'OK' if SUPABASE_URL else 'MISSING'}")
    print(f"Supabase Key: {'OK' if SUPABASE_KEY else 'MISSING'}")