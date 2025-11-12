# filename: shortener_bot.py
# pip install python-telegram-bot==20.7 requests

import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"
ADRION_API_TOKEN = os.getenv("ADRION_API_TOKEN") or "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
ADRION_API_URL = "https://adrinolinks.in/api"

# ---------------- Admin config ----------------
ADMIN_USER_IDS = [7681308594, 8244432792]  # <-- aap aur aapke dost ke Telegram numeric IDs

def is_admin(user_id: int):
    return user_id in ADMIN_USER_IDS
# ---------------------------------------------

def shorten_url(original_url: str):
    try:
        # 1. Try text format
        text_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={requests.utils.quote(original_url)}&format=text"
        resp = requests.get(text_url, timeout=10)
        short_link = resp.text.strip()

        if short_link and short_link.startswith("http"):
            return {"success": True, "short_url": short_link}

        # 2. Try JSON format (backup)
        json_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={requests.utils.quote(original_url)}"
        resp = requests.get(json_url, timeout=10)
        data = resp.json()
        if data.get("status") == "success":
            return {"success": True, "short_url": data.get("shortenedUrl")}
        else:
            return {"success": False, "error": data.get("message", "Unknown error")}

    except Exception as e:
        return {"success": False, "error": str(e)}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me any link, and I’ll shorten it using your AdrinoLinks account!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Sirf admin hi links shorten kar sakte hain.")
        return

    text = update.message.text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("🔗 Shortening your link... ⏳")
        result = shorten_url(text)
        if result["success"]:
            short = result['short_url']

            keyboard = [[InlineKeyboardButton("🌐 Open in Opera", url=short)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ Shortened link:\n{short}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"⚠️ Error: {result['error']}")
    else:
        await update.message.reply_text("Please send a valid link starting with http:// or https://")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 AdrinoLinks Shortener Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
