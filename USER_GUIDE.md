# Laundry Bot User Guide

A complete guide for residents using the Laundry Bot to manage washing machines and dryers at Level 9 and Level 17.

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [Using the Bot](#using-the-bot)
3. [Understanding Machine Status](#understanding-machine-status)
4. [Timer Durations](#timer-durations)
5. [Notifications](#notifications)
6. [Troubleshooting & Edge Cases](#troubleshooting--edge-cases)
7. [FAQ for Authorities](#faq-for-authorities)

---

## Getting Started

### Step 1: Find the Bot
Search for the Laundry Bot on Telegram or scan the QR code posted in the laundry room.

### Step 2: Register Your Account
1. Send `/register` to the bot
2. Enter your **name** when prompted
3. Select your **laundry level** (Level 9 or Level 17)
4. Select your **house** (Zenith, Nous, or Aeon)
5. You'll see: "Registered! Type /start to begin."

That's it! You're ready to use the bot.

---

## Using the Bot

### Available Commands

| Command | What It Does |
|---------|--------------|
| `/register` | Register as a new user (first time only) |
| `/start` | Open the machine selection panel |
| `/status` | View live status of all machines at your level |
| `/reset` | Update your profile (name, level, house) |
| `/help` | Display the help guide |

### Starting a Laundry Cycle

1. **Send `/start`** to the bot
2. **Select a machine** from the grid (e.g., W1, W2, D1, D2)
   - W = Washer
   - D = Dryer
3. **Choose your timer duration**
   - Washers: 33 minutes or 39 minutes
   - Dryers: 35 minutes or 70 minutes
4. The timer starts immediately. You'll receive notifications when it's almost done and when it's finished.

### Stopping Your Laundry Early

If you need to stop your laundry before the timer ends:
1. Send `/start` and select the machine you're using
2. Click **"Stop My Laundry"**
3. Confirm by clicking **"Yes, Stop Now"**
4. The machine will be freed immediately

### Collecting Your Laundry

1. When you receive the "Laundry Done!" notification, go collect your laundry
2. Click the **"I collected my laundry"** button in the message
3. The machine will be marked as Available for the next person

### Checking Machine Status

Send `/status` to see all machines at your registered level:
- Which machines are available
- Which machines are running (and time remaining)
- Which machines are finished (waiting for collection)

---

## Understanding Machine Status

| Icon | Status | Meaning |
|------|--------|---------|
| ✅ | Available | Machine is free to use |
| ❌ | Running | Someone is using it (shows time remaining) |
| ⚠️ | Finished | Cycle complete, waiting for pickup |

---

## Timer Durations

### Washers
- **33 minutes** - Standard wash cycle
- **39 minutes** - Extended wash cycle

### Dryers
- **35 minutes** - Quick dry
- **70 minutes** - Full dry cycle

*Note: These durations include a small buffer time for machine cooldown.*

---

## Notifications

The bot will send you automatic notifications:

| Notification | When | Action Required |
|--------------|------|-----------------|
| 5 Minutes Left | 5 minutes before your cycle ends | Prepare to collect your laundry |
| Laundry Done | When your cycle is complete | Go collect and press "I collected my laundry" |
| PING! | Someone is waiting for your machine | Collect your laundry immediately |
| Force Stop Alert | Someone has taken over your machine | Your cycle was ended by another user |

---

## Troubleshooting & Edge Cases

### "I can't use /start or /status"
**Solution:** You need to register first. Send `/register` and complete the registration process.

### "I accidentally selected the wrong machine or duration"
**Solution:**
1. Send `/start` and select the machine you started by mistake
2. Click "Stop My Laundry"
3. Confirm by clicking "Yes, Stop Now"
4. The machine will be freed and you can start over on the correct machine

### "The machine says it's running but no one is there"
**Solution:** Select the machine from `/start`. You'll see a "Force Stop & Take Over" button. Use this to claim the machine. Note: The previous user will be notified.

### "Someone isn't collecting their finished laundry"
**Solution:**
1. Select the machine from `/start`
2. Click "Ping Owner (Hurry up!)"
3. The owner will receive a notification asking them to collect immediately
4. After pinging, you'll see the owner's name and Telegram handle (if available)
5. If they still don't collect after an extended period, you can directly message or call them using their Telegram handle

### "I can't ping the owner"
**Possible reasons:**
- **Cooldown active:** You must wait 200 seconds (about 3 minutes) between pings on the same machine. Try again later.
- **User blocked the bot:** The ping will fail. Please contact your house heads for assistance.

### "I pressed the button but nothing happened"
**Solution:** This is normal if you press the same button multiple times quickly. The bot prevents duplicate actions. Wait a moment and try again if needed.

### "I didn't receive my notification"
**Possible reasons:**
- You may have muted the bot in Telegram
- Check your Telegram notification settings
- Ensure you haven't blocked the bot

### "I want to change my registered level or house"
**Solution:** Send `/reset` to update your profile information.

### "Someone force-stopped my machine"
This means another user needed the machine and took over. You'll receive a notification when this happens. Please collect your laundry promptly to avoid this situation.

### "The bot is not responding"
**Solution:**
1. Wait a few seconds and try again
2. Check your internet connection
3. If the issue persists, the server may be undergoing maintenance

---

## FAQ for Authorities

### Privacy & Data Collection

**Q: What personal data does the bot collect?**

A: The bot collects minimal data necessary for operation:
- **Name** (as entered by the user during registration)
- **House name** (Zenith, Nous, or Aeon)
- **Telegram ID** (automatically provided by Telegram, used to send notifications)

No phone numbers, emails, or other personal identifiers are collected.

---

**Q: Why is the Telegram ID collected?**

A: The Telegram ID is required for the bot to send direct messages to users (notifications about their laundry cycle). Without it, the bot cannot function.

---

**Q: Who has access to the user data?**

A: Only the **Acacia AI Society project team** has access to the backend services:
- Database (Supabase)
- Server (Render)
- Logs (BetterStack)

All secret keys and passwords are securely managed and restricted to authorized team members only.

---

**Q: Is the data encrypted?**

A:
- **In transit:** Yes, all communications use HTTPS/TLS encryption
- **At rest:** Supabase provides encryption at rest for all database storage
- **Telegram:** All messages are encrypted by Telegram's infrastructure

---

**Q: How long is user data retained?**

A: User data is retained for as long as the user remains registered with the bot. Users can request data deletion by contacting the Acacia AI Society team.

---

**Q: What happens when someone force-stops another user's machine?**

A: Force-stop events are logged in an **audit log** that records:
- The user who performed the force-stop
- The user whose cycle was interrupted
- The timestamp of the event

This creates accountability and allows administrators to address any misuse.

---

**Q: Is there any analytics or tracking beyond laundry usage?**

A: No. The bot does not track:
- User behavior patterns
- Usage frequency
- Location data
- Any data beyond what's needed for laundry management

---

**Q: Can users delete their data?**

A: Yes. Users can contact the Acacia AI Society team to request complete deletion of their data from the system.

---

**Q: How is the system monitored?**

A:
- **BetterStack** is used for log monitoring and uptime checks
- Logs capture system events and errors for debugging
- No personal conversation data is logged

---

**Q: Who built this bot?**

A: The Laundry Bot was developed by the **Acacia AI Society** as a community project to improve laundry room management for residents.

---

**Q: What if there's a security concern or vulnerability?**

A: Please report any security concerns to the Acacia AI Society team immediately. We take security seriously and will address issues promptly.

---

**Q: Is this bot compliant with data protection regulations?**

A: The bot is designed with privacy in mind:
- Minimal data collection (only what's necessary)
- Clear purpose for each data point
- Secure storage with reputable providers
- No sharing of data with third parties
- Users can request data deletion

---

### Technical Infrastructure

| Component | Provider | Purpose |
|-----------|----------|---------|
| Bot Server | Render | Hosts the bot application |
| Database | Supabase | Stores user and machine data |
| Monitoring | BetterStack | Logs and uptime monitoring |
| Messaging | Telegram | User interface and notifications |

All providers are industry-standard, reputable services with strong security practices.

---

## Support

For questions, issues, or feedback about the Laundry Bot, please contact the **Acacia AI Society** team.

---

*Last updated: January 2026*
