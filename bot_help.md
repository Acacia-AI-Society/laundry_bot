🧺 *Hostel Laundry Bot V2 - User Guide*

Welcome to the new and improved Laundry Bot! This system helps you track washer/dryer availability, sets timers automatically, and helps you poke (ping) neighbors who forget to collect their clothes.

🚀 *Getting Started (One-Time Setup)*

1. *Start the Bot:* Scan the QR code on any machine OR search for the bot in Telegram and tap Start.
2. *Register:* The bot will ask for your Name, Laundry Level (9 or 17), and House.

🟢 *How to Use*

*1. Start a Wash/Dry Cycle*
• *Method A (Preferred):* Scan the QR code on the machine.
• *Method B:* Send the command /menu and select your machine from the grid.
• *Select Duration:* Choose the cycle time (Timer includes approximated cooldown duration).
• ✅ *Done!* The bot will notify you when 5 minutes are left and when it is Finished.

*2. Check Availability*
Send the command /status to see a live dashboard.
• ✅ Available: Free to use.
• ❌ Running: Currently in use (shows time remaining).
• ⚠️ Finished: Cycle done, but clothes are still inside.

*3. Collecting Laundry (Important!)*
When your laundry is done, the bot will send you a message with a button:
👉 \[✅ I collected my laundry\]

Please click this button after emptying the machine. This resets the status to "Available" for the next person.

🔔 *The "Hogger" Feature (Pinging)*

Is a machine marked as Finished (⚠️) but full of clothes?

1. Select that machine in the /menu.
2. Click 🔔 Ping Owner (Hurry up!).
3. The bot will anonymously message the previous user: "Someone is waiting for your machine!"
4. Cooldown: You can only ping once every few minutes to prevent spam.

⚙️ *Commands Reference*

/menu - Open the machine selection grid.
/status - See list of all running/finished machines.
/start - Register (if you haven't yet).
/reset - Update your Name, Level, or House.
/help - Show this guide.

💡 *Pro-Tips*
• *Wrong Level?* You can switch between Level 9 and Level 17 views directly in the /menu.
• *Conflict?* If a machine is running physically but the bot says "Available", just override it. If the bot says "Running" but it's empty, use the "Force Stop" button (this alerts the previous user).