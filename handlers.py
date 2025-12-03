import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes, Application
from telegram.error import BadRequest
import services

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- HELPERS ---
def format_time_delta(end_dt: datetime.datetime):
    if not end_dt: return 0
    now = datetime.datetime.now(datetime.timezone.utc)
    diff = now - end_dt if now > end_dt else end_dt - now
    return int(diff.total_seconds() / 60)

def format_machine_name(mid: str):
    """Converts '17_dryer_1' to 'Lvl17 Dryer 1' for display."""
    try:
        parts = mid.split('_') 
        if len(parts) >= 3:
            level = parts[0]
            mtype = parts[1].capitalize()
            idx = parts[2]
            return f"Lvl{level} {mtype} {idx}"
        return mid
    except:
        return mid

def escape_md(text: str) -> str:
    """Helper to escape Markdown special chars."""
    if not text: return ""
    escaped = str(text).replace("\\", "\\\\")
    return escaped.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

async def safe_edit_message(message, text, reply_markup=None, parse_mode="Markdown"):
    """Safely edits a message, ignoring 'Message is not modified' errors."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass # Ignore legitimate no-op edits
        else:
            raise e # Raise other real errors

async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Register / Welcome"),
        BotCommand("menu", "Select Machine (Start Laundry)"),
        BotCommand("status", "Check Status"),
        BotCommand("reset", "Update Profile (Re-Onboard)"),
        BotCommand("help", "Show Help")
    ]
    await application.bot.set_my_commands(commands)

# --- NOTIFICATION JOBS ---
async def alarm_5min(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    mid = job.data.get('mid')
    display_name = format_machine_name(mid)
    try:
        print(f"⏰ Executing 5-min alarm for {mid}")
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text=f"⏳ *5 Minutes Left!*\nYour laundry in *{display_name}* is almost ready.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Failed to send 5-min alarm: {e}")

async def alarm_done(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    mid = job.data.get('mid')
    display_name = format_machine_name(mid)
    try:
        print(f"✅ Executing DONE alarm for {mid}")
        kb = [[InlineKeyboardButton("✅ I collected my laundry", callback_data=f"collect_{mid}")]]
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text=f"✅ *Laundry Done!*\nYour machine *{display_name}* is finished.\nPlease collect it immediately!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    except Exception as e:
        logger.error(f"❌ Failed to send DONE alarm: {e}")

# --- RESTORE TIMERS ---
async def restore_timers(application: Application):
    print("🔄 Hydrating Timers from Supabase...")
    if not application.job_queue:
        print("❌ CRITICAL: Job Queue is NOT available. Notifications will fail.")
        return

    try:
        running_machines = services.get_running_machines()
    except Exception as e:
        print(f"❌ Database Error during hydration: {e}")
        return

    count = 0
    now = datetime.datetime.now(datetime.timezone.utc)
    
    print(f"📄 Found {len(running_machines)} machines marked as 'Running' in DB.")

    for m in running_machines:
        if not m.end_time or not m.current_user: continue
        
        delay = (m.end_time - now).total_seconds()
        user_id = m.current_user.id
        mid = m.id
        
        if delay > 0:
            application.job_queue.run_once(alarm_done, delay, chat_id=user_id, data={"mid": mid}, name=f"done_{mid}")
            if delay > 300:
                application.job_queue.run_once(alarm_5min, delay - 300, chat_id=user_id, data={"mid": mid}, name=f"5min_{mid}")
            count += 1
        else:
            application.job_queue.run_once(alarm_done, 1, chat_id=user_id, data={"mid": mid}, name=f"done_{mid}")
            count += 1
            
    print(f"✅ Successfully restored {count} active timers.")

# --- COMMANDS ---
try:
    with open("bot_help.md", "r", encoding="utf-8") as f:
        HELP_TEXT = f.read()
except FileNotFoundError:
    HELP_TEXT = "Help file not found."

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["registration"] = {"step": "NAME", "pending_machine": None}
    await update.message.reply_text(
        "🔄 *Update Profile*\n\nLet's set up your details again.\n\n*1. What is your Name?* (Please type it below)",
        parse_mode="Markdown"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    args = context.args

    if not db_user:
        context.user_data["registration"] = {"step": "NAME", "pending_machine": args[0] if args else None}
        intro_text = "👋 *Welcome to the Hostel Laundry Bot!*\n\nI am here to help you track washer/dryer availability and set timers.\n\nTo get started, I just need a few details."
        await update.message.reply_text(intro_text, parse_mode="Markdown")
        await update.message.reply_text("*1. What is your Name?* (Please type it below)", parse_mode="Markdown")
        return

    if args:
        await show_machine_control_panel(update, context, args[0])
        return

    welcome_name = escape_md(db_user.display_name)
    await update.message.reply_text(
        f"👋 Welcome back, {welcome_name} (Level {db_user.level})!\nUse /menu to start laundry.",
        parse_mode="Markdown"
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    if not db_user:
        await update.message.reply_text("⚠️ Please /start to register first.")
        return
    await send_level_selection_menu(update, context, db_user.level)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    level_to_show = db_user.level if db_user else "9"
    machines = services.get_machines_by_level(level_to_show)
    await send_status_text(update, context, machines, level_to_show)

# --- MENUS ---
async def send_level_selection_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, level: str):
    machines = services.get_machines_by_level(level)
    status_map = {m.id: m.status for m in machines}

    def get_btn_text(type_short, type_key, index):
        mid = f"{level}_{type_key}_{index}"
        status = status_map.get(mid, "Available")
        if status == "Running": return f"❌ {type_short}{index}" 
        elif status == "Finished": return f"⚠️ {type_short}{index}" 
        else: return f"✅ {type_short}{index}" 

    keyboard = []
    row1 = [InlineKeyboardButton(get_btn_text("W", "washer", i), callback_data=f"sel_{level}_washer_{i}") for i in range(1, 4)]
    row2 = [InlineKeyboardButton(get_btn_text("W", "washer", i), callback_data=f"sel_{level}_washer_{i}") for i in range(4, 6)]
    row3 = [InlineKeyboardButton(get_btn_text("D", "dryer", i), callback_data=f"sel_{level}_dryer_{i}") for i in range(1, 3)]
    row4 = [InlineKeyboardButton(get_btn_text("D", "dryer", i), callback_data=f"sel_{level}_dryer_{i}") for i in range(3, 5)]
    keyboard.extend([row1, row2, row3, row4])
    
    nav_row = [
        InlineKeyboardButton("Lvl 9", callback_data="view_lvl_9"),
        InlineKeyboardButton("Lvl 17", callback_data="view_lvl_17"),
    ]
    keyboard.append(nav_row)

    text = f"👇 *Select Machine (Level {level})*\n\n✅ Available  ❌ Running  ⚠️ Finished"
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await safe_edit_message(update.callback_query.message, text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

async def show_machine_control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, machine_id: str, ping_status=None):
    machine = services.get_machine(machine_id)
    if not machine:
        await context.bot.send_message(update.effective_chat.id, "❌ Machine not found.")
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    display_name = format_machine_name(machine.id)
    
    if machine.status == 'Running' and machine.end_time and machine.end_time > now:
        mins_left = format_time_delta(machine.end_time)
        user_name = escape_md(machine.current_user.display_name if machine.current_user else "Unknown")
        
        kb = [
            [InlineKeyboardButton("⚠️ Force Stop & Take Over", callback_data=f"force_{machine_id}")],
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"view_lvl_{machine.level}")]
        ]
        msg = (f"⚠️ *Conflict!* {display_name} is running.\n"
               f"👤 User: {user_name}\n⏳ Left: {mins_left}m")
        
        if update.callback_query:
            await safe_edit_message(update.callback_query.message, msg, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    kb = []
    if machine.type == "Washer":
        kb = [[InlineKeyboardButton("33 Mins", callback_data=f"set_{machine_id}_33"),
               InlineKeyboardButton("39 Mins", callback_data=f"set_{machine_id}_39")]]
    else:
        kb = [[InlineKeyboardButton("35 Mins", callback_data=f"set_{machine_id}_35"),
               InlineKeyboardButton("70 Mins", callback_data=f"set_{machine_id}_70")]]
    
    prev_msg = ""
    if machine.status == 'Finished':
        if machine.end_time:
            ago = format_time_delta(machine.end_time)
            prev_user_raw = machine.last_user.display_name if machine.last_user else "Unknown"
            prev_user = escape_md(prev_user_raw)
            prev_msg = f"\n(Ready {ago}m ago. Last: {prev_user})"
            
            if machine.last_user:
                last_time = machine.last_ping
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                
                ping_btn_text = "🔔 Ping Owner (Hurry up!)"
                callback = f"ping_{machine_id}"
                
                if last_time and (now_utc - last_time).total_seconds() < 200:
                    remaining = 200 - int((now_utc - last_time).total_seconds())
                    ping_btn_text = f"⏳ Wait {remaining}s to Ping"
                    callback = "ignore_ping" 
                    
                kb.append([InlineKeyboardButton(ping_btn_text, callback_data=callback)])
        
        user = update.effective_user
        if machine.last_user and machine.last_user.id == user.id:
            kb.append([InlineKeyboardButton("✅ I collected my laundry", callback_data=f"collect_{machine_id}")])

    kb.append([InlineKeyboardButton("🔙 Cancel", callback_data=f"view_lvl_{machine.level}")])

    msg = f"⚙️ *{display_name}*\n{prev_msg}\nSelect duration:"
    
    if ping_status:
        msg += f"\n\n{ping_status}"

    if update.callback_query:
        await safe_edit_message(update.callback_query.message, msg, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- REGISTRATION LOGIC ---
async def handle_registration_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg_data = context.user_data.get("registration")
    if not reg_data or reg_data["step"] != "NAME": return

    reg_data["name"] = update.message.text.strip()
    reg_data["step"] = "LEVEL"
    
    kb = [[InlineKeyboardButton("Level 9", callback_data="reg_lvl_9"),
           InlineKeyboardButton("Level 17", callback_data="reg_lvl_17")]]
    
    name_clean = escape_md(reg_data['name'])
    await update.message.reply_text(f"Hi {name_clean}! Which laundry room level do you use?", reply_markup=InlineKeyboardMarkup(kb))

# --- STATUS LOGIC ---
async def send_status_text(update: Update, context: ContextTypes.DEFAULT_TYPE, machines, level):
    response = f"📊 *Laundry Status (Level {level})*\n\n"
    washers = [m for m in machines if m.type == 'Washer']
    dryers = [m for m in machines if m.type == 'Dryer']
    
    def format_line(m):
        icon = "✅"
        status = "Available"
        user_info = ""
        name = format_machine_name(m.id)
        
        if m.status == 'Running':
            left = format_time_delta(m.end_time)
            icon = "❌"
            status = f"Running ({left}m left)"
            if m.current_user: 
                clean_name = escape_md(m.current_user.display_name)
                user_info = f"   └ {clean_name}"
            
        elif m.status == 'Finished':
            ago = format_time_delta(m.end_time)
            icon = "⚠️"
            status = f"Ready ({ago}m ago)"
            if m.last_user: 
                clean_name = escape_md(m.last_user.display_name)
                user_info = f"   └ {clean_name}"
            
        return f"{icon} *{name}*: {status}\n{user_info}"

    for w in washers: response += format_line(w) + "\n"
    response += "------------------\n"
    for d in dryers: response += format_line(d) + "\n"
    
    kb = [[InlineKeyboardButton("Switch Level View", callback_data="toggle_status_level")]]
    
    if update.callback_query:
        await safe_edit_message(update.callback_query.message, response, reply_markup=InlineKeyboardMarkup(kb))
    elif update.message:
        await update.message.reply_text(response, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if data == "ignore_ping":
        await query.answer("⏳ Please wait for the cooldown.", show_alert=True)
        return

    # REGISTRATION
    if data.startswith("reg_lvl_"):
        lvl = data.split("_")[-1]
        context.user_data["registration"]["level"] = lvl
        keyboard = [
            [InlineKeyboardButton("Zenith", callback_data="reg_house_Zenith"),
             InlineKeyboardButton("Nous", callback_data="reg_house_Nous"),
             InlineKeyboardButton("Aeon", callback_data="reg_house_Aeon")]
        ]
        await safe_edit_message(query.message, "Select House:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("reg_house_"):
        house = data.split("_")[-1]
        reg = context.user_data["registration"]
        new_user = services.UserInfo(
            id=user.id, username=user.username or "", first_name=user.first_name or "",
            display_name=reg["name"], level=reg["level"], house=house
        )
        services.create_user(new_user)
        await safe_edit_message(query.message, "✅ Registered! Type /menu to start.")
        del context.user_data["registration"]
        return

    # VIEWS
    if data.startswith("view_lvl_"):
        await send_level_selection_menu(update, context, data.split("_")[-1])
        return
    if data == "toggle_status_level":
        kb = [[InlineKeyboardButton(l, callback_data=f"status_view_{l}") for l in ["9", "17"]]]
        # Use safe_edit_message to catch "Message Not Modified" here
        await safe_edit_message(query.message, "Select Level to View:", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("status_view_"):
        lvl = data.split("_")[-1]
        machines = services.get_machines_by_level(lvl)
        await send_status_text(update, context, machines, lvl)
        return

    # MACHINE SELECTION
    if data.startswith("sel_"):
        mid = data.replace("sel_", "")
        await show_machine_control_panel(update, context, mid)
        return

    # SET TIMER
    if data.startswith("set_"):
        parts = data.rsplit("_", 1)
        mid = parts[0].replace("set_", "")
        mins = int(parts[1])
        end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=mins)
        services.update_machine_status(mid, "Running", end_time, user.id)
        
        if context.job_queue:
            print(f"🕒 Scheduling {mins}m timer for {mid}")
            context.job_queue.run_once(alarm_done, mins * 60, chat_id=user.id, data={"mid": mid}, name=f"done_{mid}")
            if mins > 5:
                context.job_queue.run_once(alarm_5min, (mins - 5) * 60, chat_id=user.id, data={"mid": mid}, name=f"5min_{mid}")
        else:
            print("❌ CRITICAL: No JobQueue found in context! Notifications will FAIL.")

        await safe_edit_message(query.message, f"✅ Timer started for {mins} mins on {mid}!\nI'll notify you when it's done.")
        return

    # FORCE STOP
    if data.startswith("force_"):
        mid = data.replace("force_", "")
        machine = services.get_machine(mid)
        if machine.current_user:
            services.log_audit_event("FORCE_STOP", mid, machine.current_user.id, user.id)
            try:
                await context.bot.send_message(machine.current_user.id, f"🚨 Your machine {mid} was stopped by {user.first_name}.")
            except: pass
            
            if context.job_queue:
                for job in context.job_queue.get_jobs_by_name(f"done_{mid}"): job.schedule_removal()
                for job in context.job_queue.get_jobs_by_name(f"5min_{mid}"): job.schedule_removal()

        services.reset_machine_status(mid)
        await show_machine_control_panel(update, context, mid)
        return

    # PING OWNER
    if data.startswith("ping_"):
        mid = data.replace("ping_", "")
        display_name = format_machine_name(mid)
        
        machine = services.get_machine(mid)
        last_time = machine.last_ping
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        if last_time and (now_utc - last_time).total_seconds() < 200:
            remaining = 200 - int((now_utc - last_time).total_seconds())
            await query.answer(f"⏳ Cooldown! Wait {remaining}s.", show_alert=True)
            return
            
        ping_msg = "✅ Ping Sent!"
        if machine.last_user:
            try:
                await context.bot.send_message(
                    chat_id=machine.last_user.id,
                    text=f"🔔 *PING!*\nSomeone is waiting for *{display_name}*. Please collect your laundry immediately!"
                )
                await query.answer("🔔 Ping sent!", show_alert=True)
                
                services.register_ping(mid)
                
                u = machine.last_user
                handle = escape_md(f" (@{u.username})") if u.username else ""
                clean_name = escape_md(u.display_name)
                clean_house = escape_md(u.house)
                ping_msg = f"✅ Ping sent to *{clean_name}* ({clean_house}){handle}!"
                
            except:
                ping_msg = "❌ Failed to Ping (User Blocked Bot)"
                await query.answer("❌ Could not reach user.", show_alert=True)
        else:
             await query.answer("❌ No user history.", show_alert=True)
        
        await show_machine_control_panel(update, context, mid, ping_status=ping_msg)
        return

    # COLLECT (I'M DONE)
    if data.startswith("collect_"):
        mid = data.replace("collect_", "")
        services.make_machine_available(mid)
        await safe_edit_message(query.message, f"✅ Machine {mid} marked as Available.\nThank you for collecting your laundry!")
        return