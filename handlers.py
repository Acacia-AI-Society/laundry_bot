import datetime
import logging
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes, Application
from telegram.error import BadRequest
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for server
import matplotlib.pyplot as plt
import numpy as np
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
        BotCommand("start", "Select Machine (Start Laundry)"),
        BotCommand("register", "Register / Update Profile"),
        BotCommand("status", "Check Status"),
        BotCommand("complain", "Report Machine Discrepancy"),
        BotCommand("stats", "View Usage Patterns"),
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

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    args = context.args

    if not db_user:
        # New user - start registration
        context.user_data["registration"] = {"step": "NAME", "pending_machine": args[0] if args else None}
        intro_text = "👋 *Welcome to the Hostel Laundry Bot!*\n\nI am here to help you track washer/dryer availability and set timers.\n\nTo get started, I just need a few details."
        await update.message.reply_text(intro_text, parse_mode="Markdown")
        await update.message.reply_text("*1. What is your Name?* (Please type it below)", parse_mode="Markdown")
        return

    if args:
        await show_machine_control_panel(update, context, args[0])
        return

    # Existing user - start profile update flow
    context.user_data["registration"] = {"step": "NAME", "pending_machine": None}
    await update.message.reply_text(
        "🔄 *Update Profile*\n\nLet's update your details.\n\n*1. What is your Name?* (Please type it below)",
        parse_mode="Markdown"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    if not db_user:
        await update.message.reply_text("⚠️ Please /register first.")
        return
    await send_level_selection_menu(update, context, db_user.level)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    level_to_show = db_user.level if db_user else "9"
    machines = services.get_machines_by_level(level_to_show)
    await send_status_text(update, context, machines, level_to_show)

async def complain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report a machine discrepancy (machine in use but shown as available)."""
    user = update.effective_user
    db_user = services.get_user(user.id)
    if not db_user:
        await update.message.reply_text("⚠️ Please /register first.")
        return
    await send_complain_menu(update, context, db_user.level)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show laundry usage statistics with visualizations."""
    user = update.effective_user
    db_user = services.get_user(user.id)
    if not db_user:
        await update.message.reply_text("⚠️ Please /register first to see stats for your level.")
        return

    level = db_user.level
    await update.message.reply_text(f"📊 Generating laundry statistics for Level {level}...")

    usage_data = services.get_hourly_usage_data(level, days_back=30)

    if len(usage_data) < 10:
        await update.message.reply_text(
            "📊 *Not enough data yet!*\n\n"
            "We need more usage history to generate meaningful stats.\n"
            "Check back in a few days after more people use the bot.",
            parse_mode="Markdown"
        )
        return

    # Generate and send heatmap
    heatmap_buf = generate_heatmap(usage_data, level)
    await update.message.reply_photo(
        photo=heatmap_buf,
        caption=f"🗓️ *Laundry Heatmap - Level {level}*\nDarker = Busier. Find the light spots for free machines!",
        parse_mode="Markdown"
    )

    # Generate and send hourly bar chart
    bar_buf = generate_hourly_bar_chart(usage_data)
    await update.message.reply_photo(
        photo=bar_buf,
        caption="⏰ *Best Times to Do Laundry*\nGreen = Low traffic, Red = Avoid if possible",
        parse_mode="Markdown"
    )

    # Text summary
    hourly_counts = [0] * 24
    for event in usage_data:
        hourly_counts[event["hour_of_day"]] += 1

    total_cycles = len(usage_data)
    busiest_hour = max(range(24), key=lambda h: hourly_counts[h])
    # Find quietest hour between 6am-11pm (reasonable laundry hours)
    quietest_hour = min(range(6, 23), key=lambda h: hourly_counts[h])

    summary = (
        f"📈 *Quick Stats (Last 30 Days) - Level {level}*\n\n"
        f"• Total cycles: {total_cycles}\n"
        f"• Busiest hour: {busiest_hour}:00\n"
        f"• Quietest hour: {quietest_hour}:00\n\n"
        f"💡 *Tip*: Try doing laundry around {quietest_hour}:00 for shorter waits!"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")

# --- GRAPH GENERATION ---
def generate_heatmap(usage_data, level):
    """Generate a heatmap of usage by day and hour."""
    # Initialize 7x24 grid (days x hours)
    heatmap = np.zeros((7, 24))

    for event in usage_data:
        day = event["day_of_week"]
        hour = event["hour_of_day"]
        heatmap[day][hour] += 1

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 5))

    # Only show relevant hours (6am - 11pm)
    heatmap_trimmed = heatmap[:, 6:24]

    # Set vmin and vmax to actual data range for proper color scaling
    vmax = heatmap_trimmed.max()
    im = ax.imshow(heatmap_trimmed, cmap='YlOrRd', aspect='auto', vmin=0, vmax=vmax)

    # Labels
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    hours = [f'{h}:00' for h in range(6, 24)]

    ax.set_xticks(range(len(hours)))
    ax.set_xticklabels(hours, rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(days)))
    ax.set_yticklabels(days)

    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Day of Week')
    ax.set_title(f'Laundry Usage Patterns - Level {level} (Last 30 Days)')

    # Add colorbar with integer ticks
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Number of Cycles Started')

    # Set integer ticks on colorbar
    if vmax > 0:
        tick_values = np.arange(0, vmax + 1, max(1, int(vmax / 5)))
        cbar.set_ticks(tick_values)

    plt.tight_layout()

    # Save to BytesIO
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf

def generate_hourly_bar_chart(usage_data):
    """Generate bar chart showing busiest hours."""
    hourly_counts = [0] * 24
    for event in usage_data:
        hourly_counts[event["hour_of_day"]] += 1

    fig, ax = plt.subplots(figsize=(10, 4))

    hours = range(24)

    # Color based on percentile
    if max(hourly_counts) > 0:
        p33 = np.percentile([c for c in hourly_counts if c > 0], 33) if any(hourly_counts) else 1
        p66 = np.percentile([c for c in hourly_counts if c > 0], 66) if any(hourly_counts) else 2
        colors = ['#2ecc71' if c <= p33 else '#f1c40f' if c <= p66 else '#e74c3c' for c in hourly_counts]
    else:
        colors = ['#2ecc71'] * 24

    ax.bar(hours, hourly_counts, color=colors)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Total Cycles Started')
    ax.set_title('Laundry Activity by Hour (Last 30 Days)')
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f'{h}:00' for h in range(0, 24, 2)])

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='Low (Best Time)'),
        Patch(facecolor='#f1c40f', label='Medium'),
        Patch(facecolor='#e74c3c', label='High (Busiest)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf

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

async def send_complain_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, level: str):
    """Show machine grid for reporting discrepancies."""
    machines = services.get_machines_by_level(level)
    status_map = {m.id: m.status for m in machines}

    def get_btn_text(type_short, type_key, index):
        mid = f"{level}_{type_key}_{index}"
        status = status_map.get(mid, "Available")
        if status == "Running": return f"❌ {type_short}{index}"
        elif status == "Finished": return f"⚠️ {type_short}{index}"
        else: return f"✅ {type_short}{index}"

    keyboard = []
    row1 = [InlineKeyboardButton(get_btn_text("W", "washer", i), callback_data=f"complain_sel_{level}_washer_{i}") for i in range(1, 4)]
    row2 = [InlineKeyboardButton(get_btn_text("W", "washer", i), callback_data=f"complain_sel_{level}_washer_{i}") for i in range(4, 6)]
    row3 = [InlineKeyboardButton(get_btn_text("D", "dryer", i), callback_data=f"complain_sel_{level}_dryer_{i}") for i in range(1, 3)]
    row4 = [InlineKeyboardButton(get_btn_text("D", "dryer", i), callback_data=f"complain_sel_{level}_dryer_{i}") for i in range(3, 5)]
    keyboard.extend([row1, row2, row3, row4])

    # Switch level button
    other_level = "17" if level == "9" else "9"
    nav_row = [InlineKeyboardButton(f"🔄 Switch to Level {other_level}", callback_data=f"complain_lvl_{other_level}")]
    keyboard.append(nav_row)

    text = (f"⚠️ *Report Machine Discrepancy (Level {level})*\n\n"
            f"Select the machine that is IN USE but shown as available/finished.\n\n"
            f"✅ Available  ❌ Running  ⚠️ Finished")
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
        current_user = update.effective_user

        # Check if the viewer is the owner of the machine
        if machine.current_user and machine.current_user.id == current_user.id:
            # OWNER viewing their own running machine
            kb = [
                [InlineKeyboardButton("⏹️ Stop My Laundry", callback_data=f"stop_own_{machine_id}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"view_lvl_{machine.level}")]
            ]
            msg = (f"⏳ *Your Laundry is Running*\n"
                   f"🧺 Machine: {display_name}\n⏱️ Time Left: {mins_left}m")
        else:
            # NON-OWNER viewing someone else's running machine
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
        await safe_edit_message(query.message, "✅ Registered! Type /start to begin.")
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
        services.update_machine_status(mid, "Running", end_time, user.id, duration_minutes=mins)
        
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

    # STOP OWN LAUNDRY - Show confirmation
    if data.startswith("stop_own_"):
        mid = data.replace("stop_own_", "")
        machine = services.get_machine(mid)

        # Safety check: verify user is the owner
        if not machine.current_user or machine.current_user.id != user.id:
            await safe_edit_message(query.message, "❌ You are not the owner of this machine.")
            return

        text = "⚠️ *Are you sure you want to stop your laundry?*\n\nThis will cancel your timer immediately."
        kb = [
            [InlineKeyboardButton("✅ Yes, Stop Now", callback_data=f"confirm_stop_{mid}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"sel_{mid}")]
        ]
        await safe_edit_message(query.message, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    # CONFIRM STOP - Execute the stop
    if data.startswith("confirm_stop_"):
        mid = data.replace("confirm_stop_", "")
        machine = services.get_machine(mid)

        # Safety check again
        if not machine.current_user or machine.current_user.id != user.id:
            await safe_edit_message(query.message, "❌ You are not the owner of this machine.")
            return

        # Save level before clearing machine data
        level = machine.level

        # Cancel scheduled alarms
        if context.job_queue:
            for job in context.job_queue.get_jobs_by_name(f"done_{mid}"):
                job.schedule_removal()
            for job in context.job_queue.get_jobs_by_name(f"5min_{mid}"):
                job.schedule_removal()

        # Make machine available (user is taking clothes out now)
        services.make_machine_available(mid)

        # Show success and return to machine selection menu
        await query.answer("✅ Laundry stopped successfully!")
        await send_level_selection_menu(update, context, level)
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

    # --- COMPLAIN HANDLERS ---
    # Switch level in complain menu
    if data.startswith("complain_lvl_"):
        level = data.replace("complain_lvl_", "")
        await send_complain_menu(update, context, level)
        return

    # Select machine to report
    if data.startswith("complain_sel_"):
        mid = data.replace("complain_sel_", "")
        machine = services.get_machine(mid)
        display_name = format_machine_name(mid)

        # Check rate limit
        if not services.can_submit_complaint(user.id, mid):
            await query.answer("⏳ You already reported this machine recently. Please wait.", show_alert=True)
            return

        # Show confirmation screen
        level = mid.split("_")[0]
        status_text = machine.status if machine else "Unknown"
        text = (f"⚠️ *Confirm Report*\n\n"
                f"Machine: *{display_name}*\n"
                f"Current Status: \\[{status_text}\\]\n\n"
                f"Are you sure this machine is actually IN USE by someone not using the bot?")
        kb = [
            [InlineKeyboardButton("✅ Confirm Report", callback_data=f"complain_confirm_{mid}")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"complain_back_{level}")]
        ]
        await safe_edit_message(query.message, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    # Confirm and submit complaint
    if data.startswith("complain_confirm_"):
        mid = data.replace("complain_confirm_", "")
        machine = services.get_machine(mid)
        display_name = format_machine_name(mid)

        # Double-check rate limit
        if not services.can_submit_complaint(user.id, mid):
            await query.answer("⏳ You already reported this machine recently.", show_alert=True)
            return

        # Log the complaint
        reported_status = machine.status if machine else "Unknown"
        services.log_complaint(user.id, mid, reported_status)

        await safe_edit_message(
            query.message,
            f"✅ *Thank you for reporting!*\n\n"
            f"We've logged that *{display_name}* shows as [{reported_status}] but is actually in use.\n\n"
            f"This helps us track bot adoption. 📊"
        )
        return

    # Go back to complain menu
    if data.startswith("complain_back_"):
        level = data.replace("complain_back_", "")
        await send_complain_menu(update, context, level)
        return