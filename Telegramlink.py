# filename: shortener_bot.py
# pip install python-telegram-bot==20.7 requests

import os
import requests
import sqlite3
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"
ADRION_API_TOKEN = os.getenv("ADRION_API_TOKEN") or "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
ADRION_API_URL = "https://adrinolinks.in/api"

# ---------------- Admin config ----------------
ADMIN_USER_IDS = [7681308594, 8244432792]  # <-- Add your admin IDs here
def is_admin(user_id: int):
    return user_id in ADMIN_USER_IDS
# ---------------------------------------------

# ---------------- Database Setup ----------------
DB_FILE = "premium_users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS premium (
        user_id INTEGER PRIMARY KEY,
        expiry TIMESTAMP
    )""")
    conn.commit()
    conn.close()

def cleanup_expired_users():
    """Auto-remove expired premium users."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now()
    c.execute("DELETE FROM premium WHERE expiry <= ?", (now,))
    conn.commit()
    conn.close()

def add_premium_user(user_id: int, duration: str):
    """duration = '7D', '1M', '3M', '6M', '1Y'"""
    days_map = {
        "7D": 7,
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365
    }
    days = days_map.get(duration.upper(), 0)
    if days == 0:
        return False, "Invalid duration code!"

    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO premium (user_id, expiry) VALUES (?, ?)", (user_id, expiry_date))
    conn.commit()
    conn.close()
    return True, f"User {user_id} added as premium for {duration} (expires on {expiry_date.strftime('%Y-%m-%d %H:%M:%S')})."

def is_premium_user(user_id: int):
    cleanup_expired_users()  # Auto remove expired users before checking
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT expiry FROM premium WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        expiry = datetime.datetime.fromisoformat(row[0])
        if expiry > datetime.datetime.now():
            return True
    return False
# ------------------------------------------------

def shorten_url(original_url: str):
    try:
        text_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={requests.utils.quote(original_url)}&format=text"
        resp = requests.get(text_url, timeout=10)
        short_link = resp.text.strip()
        if short_link and short_link.startswith("http"):
            return {"success": True, "short_url": short_link}

        json_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={requests.utils.quote(original_url)}"
        resp = requests.get(json_url, timeout=10)
        data = resp.json()
        if data.get("status") == "success":
            return {"success": True, "short_url": data.get("shortenedUrl")}
        else:
            return {"success": False, "error": data.get("message", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------- Bot Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me any link, and I’ll shorten it using AdrinoLinks.\n"
        "Admins can use /premium to add premium users."
    )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Only admin can use this command.")
        return

    if len(context.args) == 0:
        await update.message.reply_text(
            "Usage:\n`/premium <user_id>-<duration>`\nExample: `/premium 1111111111-7D`\n"
            "Durations: 7D | 1M | 3M | 6M | 1Y",
            parse_mode="Markdown"
        )
        return

    try:
        parts = context.args[0].split("-")
        if len(parts) != 2:
            raise ValueError

        target_id = int(parts[0])
        duration = parts[1].upper()
        ok, msg = add_premium_user(target_id, duration)
        await update.message.reply_text("✅ " + msg if ok else "⚠️ " + msg)
    except Exception as e:
        await update.message.reply_text(
            f"❌ Invalid format. Example: `/premium 1111111111-1M`\nError: {e}",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("Please send a valid link starting with http:// or https://")
        return

    # Check if user is premium
    if is_premium_user(user_id):
        await update.message.reply_text(f"🌟 Premium User Detected!\nHere’s your direct link:\n{text}")
        return

    # Otherwise use Adrino shortener
    await update.message.reply_text("🔗 Shortening your link... ⏳")
    result = shorten_url(text)
    if result["success"]:
        short = result['short_url']
        keyboard = [[InlineKeyboardButton("🌐 Open in Browser", url=short)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"✅ Shortened link:\n{short}", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"⚠️ Error: {result['error']}")

# ---------------- Main ----------------
def main():
    init_db()
    cleanup_expired_users()  # Ensure DB clean at start
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 AdrinoLinks Shortener Bot with Premium System is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
