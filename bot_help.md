🧺 *Hostel Laundry Bot - User Guide*

Welcome to the Laundry Bot! This system helps you track washer/dryer availability, sets timers automatically, and helps you notify neighbors who forget to collect their clothes.

🚀 *Getting Started (One-Time Setup)*

1. *Register:* Send /register to the bot.
2. *Enter Details:* The bot will ask for your Name, Laundry Level (9 or 17), and House.

🟢 *How to Use*

*1. Start a Wash/Dry Cycle*
• Send /start and select your machine from the grid.
• Select Duration: Choose the cycle time (Timer includes approximated cooldown duration).
• Done! The bot will notify you when 5 minutes are left and when it is Finished.

*2. Check Availability*
Send /status to see a live dashboard.
• ✅ Available: Free to use.
• ❌ Running: Currently in use (shows time remaining).
• ⚠️ Finished: Cycle done, but clothes from previous user might still be inside.

*3. Stop Your Laundry Early*
If you need to cancel your timer:
• Send /start and select your running machine.
• Click "⏹️ Stop My Laundry".
• Confirm by clicking "Yes, Stop Now".

*4. Collecting Laundry (Important!)*
When your laundry is done, the bot will send you a message with a button:
👉 \[✅ I collected my laundry]

Please click this button after emptying the machine. This resets the status to "Available" for the next person.

🔔 *The "Hogger" Feature (Pinging)*

Is a machine marked as Finished (⚠️) but full of clothes?

1. Select that machine in /start.
2. Click 🔔 Ping Owner (Hurry up!).
3. The bot will message the previous user: "Someone is waiting for your machine!"
4. After pinging, you'll see the owner's name and Telegram handle (if available).
5. Cooldown: You can only ping once every 200 seconds to prevent spam.
6. If they still don't collect, you can directly message or call them using the Telegram handle provided.

⚙️ *Commands Reference*

/start - Open the machine selection grid.
/status - See list of all running/finished machines.
/register - Register or update your profile (Name, Level, House).
/help - Show this guide.

💡 *Pro-Tips*
• *Wrong Level?* You can switch between Level 9 and Level 17 views directly in /start.
• *Conflict?* If a machine is running physically but the bot says "Available", just override it. If the bot says "Running" but it's empty, use the "Force Stop" button (this alerts the previous user).
• *Wrong Machine?* If you selected the wrong machine, use "⏹️ Stop My Laundry" to cancel and start over.
