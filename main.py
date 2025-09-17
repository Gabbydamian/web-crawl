import os
import threading
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from scrapers.jobs_scraper import scrape_jobs

app = Flask(__name__)

# Environment variables
TOKEN = os.getenv("8119359225:AAFkxELes8NS3isQWfhYqYudpnflryx0RdI")
DRAFT_CHAT_ID = int(os.getenv("DRAFT_CHAT_ID", "-1003096593867"))
MAIN_CHAT_ID = int(os.getenv("MAIN_CHAT_ID", "-1002904064919"))

# Bot application setup
if TOKEN:
    application = Application.builder().token(TOKEN).build()
else:
    print("ERROR: TELEGRAM_BOT_TOKEN not found!")
    exit()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot started.")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Posting command received.")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs_data = scrape_jobs()
    if jobs_data:
        response_text = "Found jobs:\n" + "\n".join(jobs_data)
    else:
        response_text = "No jobs found."
    await update.message.reply_text(response_text)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"Selected option: {query.data}")

async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Message received: {update.message.text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("post", post))
application.add_handler(CommandHandler("jobs", jobs))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit))

# Flask endpoints
@app.route('/')
@app.route('/health')
def health():
    return "OK", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.process_update(update)
    return "ok"

# Main function
def main():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()