import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
import config
import handlers

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# FastAPI
app = FastAPI()
ptb_app = Application.builder().token(config.TOKEN).build() if config.TOKEN else None

def register_handlers(application):
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("register", handlers.register_command))
    application.add_handler(CommandHandler("status", handlers.status_command))
    application.add_handler(CommandHandler("report", handlers.report_command))
    application.add_handler(CommandHandler("stats", handlers.stats_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CallbackQueryHandler(handlers.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_registration_text))

@app.on_event("startup")
async def startup_event():
    if ptb_app:
        register_handlers(ptb_app)
        await ptb_app.initialize()
        await ptb_app.start()
        await handlers.set_bot_commands(ptb_app)
        # --- RESTORE TIMERS FROM DB ---
        await handlers.restore_timers(ptb_app)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not ptb_app: return {"status": "error"}
    req = await request.json()
    update = Update.de_json(req, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}

# --- NEW: HEALTH CHECK ENDPOINT ---
# BetterStack/UptimeRobot will ping this using GET to keep the server awake
@app.get("/")
async def health_check():
    return "OK"

# Local Polling
if __name__ == "__main__":
    if ptb_app:
        print("🚀 Starting Polling Mode...")
        register_handlers(ptb_app)
        
        async def post_init(app):
            await handlers.set_bot_commands(app)
            await handlers.restore_timers(app)
            
        ptb_app.post_init = post_init
        ptb_app.run_polling()