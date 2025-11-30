import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes
import services

# --- HELPERS ---
def format_time_delta(end_dt: datetime.datetime):
    if not end_dt: return 0
    now = datetime.datetime.now(datetime.timezone.utc)
    diff = now - end_dt if now > end_dt else end_dt - now
    return int(diff.total_seconds() / 60)

async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Register / Welcome"),
        BotCommand("menu", "Select Machine (Start Laundry)"),
        BotCommand("status", "Check Status"),
        BotCommand("reset", "Update Profile (Re-Onboard)"), # Added Reset
        BotCommand("help", "Show Help")
    ]
    await application.bot.set_my_commands(commands)

# --- COMMANDS ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **Hostel Laundry Bot Help**\n\n"
        "🟢 **/start** - Register/Onboard\n"
        "🔄 **/reset** - Change your Name/Level/House\n"
        "🧺 **/menu** - Select a machine to START\n"
        "📊 **/status** - View machine status (Your Level)\n"
        "❓ **/help** - Show this message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Forces the user back into the registration flow.
    """
    # Initialize registration state
    context.user_data["registration"] = {"step": "NAME", "pending_machine": None}
    
    await update.message.reply_text(
        "🔄 **Update Profile**\n\n"
        "Let's set up your details again.\n\n"
        "**1. What is your Name?** (Please type it below)",
        parse_mode="Markdown"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    args = context.args

    # 1. Not Registered -> Onboarding
    if not db_user:
        context.user_data["registration"] = {"step": "NAME", "pending_machine": args[0] if args else None}
        await update.message.reply_text("👋 **Welcome!**\n\nTo track laundry, I need to know who you are.\n\n**1. What is your Name?**")
        return

    # 2. Registered + Deep Link -> Show Machine
    if args:
        await show_machine_control_panel(update, context, args[0])
        return

    # 3. Registered + No Args -> Welcome
    await update.message.reply_text(
        f"👋 Welcome back, {db_user.display_name} (Level {db_user.level})!\nUse /menu to start laundry.",
        parse_mode="Markdown"
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("⚠️ Please /start to register first.")
        return

    # By default, show ONLY the user's level
    await send_level_selection_menu(update, context, db_user.level)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = services.get_user(user.id)
    
    # If not registered, default to Level 9 view or ask to register
    level_to_show = db_user.level if db_user else "9"
    
    # Handle "Show All" toggle via callback arg or default
    machines = services.get_machines_by_level(level_to_show)
    
    await send_status_text(update, context, machines, level_to_show)

# --- MENUS & UIs ---

async def send_level_selection_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, level: str):
    # Generates grid for specific level
    keyboard = []
    # Washers 1-5
    row1 = [InlineKeyboardButton(f"🧺 W{i}", callback_data=f"sel_{level}_washer_{i}") for i in range(1, 4)]
    row2 = [InlineKeyboardButton(f"🧺 W{i}", callback_data=f"sel_{level}_washer_{i}") for i in range(4, 6)]
    # Dryers 1-4
    row3 = [InlineKeyboardButton(f"🔥 D{i}", callback_data=f"sel_{level}_dryer_{i}") for i in range(1, 3)]
    row4 = [InlineKeyboardButton(f"🔥 D{i}", callback_data=f"sel_{level}_dryer_{i}") for i in range(3, 5)]
    
    keyboard.extend([row1, row2, row3, row4])
    
    # Navigation Buttons to switch levels
    nav_row = [
        InlineKeyboardButton("Lvl 9", callback_data="view_lvl_9"),
        InlineKeyboardButton("Lvl 17", callback_data="view_lvl_17"),
    ]
    keyboard.append(nav_row)

    text = f"👇 **Select Machine (Level {level})**"
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

async def show_machine_control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, machine_id: str):
    machine = services.get_machine(machine_id)
    if not machine:
        await context.bot.send_message(update.effective_chat.id, "❌ Machine not found.")
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    
    # CONFLICT CHECK: Machine is running and time not up
    if machine.status == 'Running' and machine.end_time and machine.end_time > now:
        mins_left = format_time_delta(machine.end_time)
        user_name = machine.current_user.display_name if machine.current_user else "Unknown"
        
        kb = [[InlineKeyboardButton("⚠️ Force Stop & Take Over", callback_data=f"force_{machine_id}")]]
        msg = (f"⚠️ **Conflict!** {machine.type} {machine_id} is running.\n"
               f"👤 User: {user_name}\n⏳ Left: {mins_left}m")
        
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # STANDARD MENU
    kb = []
    if machine.type == "Washer":
        kb = [[InlineKeyboardButton("30 Mins", callback_data=f"set_{machine_id}_30"),
               InlineKeyboardButton("35 Mins", callback_data=f"set_{machine_id}_35")]]
    else:
        kb = [[InlineKeyboardButton("30 Mins", callback_data=f"set_{machine_id}_30"),
               InlineKeyboardButton("1 Hour", callback_data=f"set_{machine_id}_60")]]
    
    prev_msg = ""
    if machine.status == 'Finished' and machine.end_time:
        ago = format_time_delta(machine.end_time)
        prev_user = machine.last_user.display_name if machine.last_user else "Unknown"
        prev_msg = f"\n(Ready {ago}m ago. Last: {prev_user})"

    msg = f"⚙️ **{machine.level} {machine.type} {machine.id.split('_')[-1]}**\n{prev_msg}\nSelect duration:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
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
    
    await update.message.reply_text(f"Hi {reg_data['name']}! Which laundry room level do you primarily use?", reply_markup=InlineKeyboardMarkup(kb))

# --- STATUS LOGIC ---
async def send_status_text(update: Update, context: ContextTypes.DEFAULT_TYPE, machines, level):
    response = f"📊 **Laundry Status (Level {level})**\n\n"
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Separate Washers and Dryers
    washers = [m for m in machines if m.type == 'Washer']
    dryers = [m for m in machines if m.type == 'Dryer']
    
    def format_line(m):
        icon = "🟢"
        status = "Available"
        user_info = ""
        
        if m.status == 'Running':
            left = format_time_delta(m.end_time)
            icon = "🔴"
            status = f"Running ({left}m left)"
            if m.current_user: user_info = f"   └ {m.current_user.display_name}"
            
        elif m.status == 'Finished':
            ago = format_time_delta(m.end_time)
            icon = "🟡"
            status = f"Ready ({ago}m ago)"
            if m.last_user: user_info = f"   └ {m.last_user.display_name}"
            
        return f"{icon} **{m.id}**: {status}\n{user_info}"

    for w in washers: response += format_line(w) + "\n"
    response += "------------------\n"
    for d in dryers: response += format_line(d) + "\n"
    
    # Add "Switch Level View" toggle
    kb = [[InlineKeyboardButton("Switch Level View", callback_data="toggle_status_level")]]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(response, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(response, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- CALLBACK HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    # REGISTRATION
    if data.startswith("reg_lvl_"):
        lvl = data.split("_")[-1]
        context.user_data["registration"]["level"] = lvl
        kb = [[InlineKeyboardButton(h, callback_data=f"reg_house_{h}") for h in ["Zenith", "Nous", "Aeon"]]]
        await query.edit_message_text("Select House:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("reg_house_"):
        house = data.split("_")[-1]
        reg = context.user_data["registration"]
        
        # Save to Supabase
        new_user = services.UserInfo(
            id=user.id, username=user.username or "", first_name=user.first_name or "",
            display_name=reg["name"], level=reg["level"], house=house
        )
        services.create_user(new_user)
        
        await query.edit_message_text("✅ Registered! Type /menu to start.")
        del context.user_data["registration"]
        return

    # LEVEL VIEW SWITCHING
    if data.startswith("view_lvl_"):
        lvl = data.split("_")[-1]
        await send_level_selection_menu(update, context, lvl)
        return
        
    # STATUS VIEW SWITCHING
    if data == "toggle_status_level":
        kb = [[InlineKeyboardButton(l, callback_data=f"status_view_{l}") for l in ["9", "17"]]]
        await query.edit_message_text("Select Level to View:", reply_markup=InlineKeyboardMarkup(kb))
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
        
        await query.edit_message_text(f"✅ Timer started for {mins} mins on {mid}!")
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
            
        services.reset_machine_status(mid)
        await show_machine_control_panel(update, context, mid)
        return