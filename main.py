import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from scrapers.jobs_scraper import scrape_jobs

# Get environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DRAFT_CHAT_ID = int(os.getenv("DRAFT_CHAT_ID", "-1001234567890"))
MAIN_CHAT_ID = int(os.getenv("MAIN_CHAT_ID", "-1009876543210"))

logging.basicConfig(level=logging.INFO)

# ... rest of your existing code ...

def main():
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not found!")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("jobs", jobs))  # Add this line
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit))
    
    # Use webhook for Railway (better than polling)
    PORT = int(os.environ.get("PORT", 8000))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost')}"
    )

if __name__ == "__main__":
    main()