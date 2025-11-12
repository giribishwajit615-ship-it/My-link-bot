# filename: shortener_bot.py
# pip install python-telegram-bot==20.7 requests

import os
import requests
import sqlite3
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"
ADRION_API_TOKEN = os.getenv("ADRION_API_TOKEN") or "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
ADRION_API_URL = "https://adrinolinks.in/api"
ADRION_DOMAIN = "adrinolinks.in"

ADMIN_USER_IDS = [7681308594, 8244432792]  # your admin IDs
DB_FILE = "premium_users.db"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS premium (
        user_id INTEGER PRIMARY KEY,
        expiry TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS links (
        short_url TEXT PRIMARY KEY,
        original_url TEXT
    )""")
    conn.commit()
    conn.close()

def cleanup_expired_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now()
    c.execute("DELETE FROM premium WHERE expiry <= ?", (now,))
    conn.commit()
    conn.close()

def add_premium_user(user_id: int, duration: str):
    days_map = {"7D": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = days_map.get(duration.upper(), 0)
    if days == 0:
        return False, "Invalid duration!"

    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO premium (user_id, expiry) VALUES (?, ?)", (user_id, expiry_date))
    conn.commit()
    conn.close()
    return True, f"User {user_id} added as premium till {expiry_date.strftime('%Y-%m-%d')}"

def is_premium_user(user_id: int):
    cleanup_expired_users()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT expiry FROM premium WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        expiry = datetime.datetime.fromisoformat(row[0])
        return expiry > datetime.datetime.now()
    return False

# ---------------- ADRINO SHORTENER ----------------
def shorten_url(original_url: str):
    try:
        api_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={requests.utils.quote(original_url)}"
        res = requests.get(api_url, timeout=10)
        data = res.json()
        if data.get("status") == "success":
            short = data["shortenedUrl"]
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("REPLACE INTO links (short_url, original_url) VALUES (?, ?)", (short, original_url))
            conn.commit()
            conn.close()
            return {"success": True, "short_url": short}
        return {"success": False, "error": data.get("message", "Adrino API error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_original_from_short(short_url: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT original_url FROM links WHERE short_url=?", (short_url,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me any link to shorten!\n\nAdmins can use:\n"
        "`/premium <user_id>-<duration>`\nDurations: 7D | 1M | 3M | 6M | 1Y",
        parse_mode="Markdown"
    )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Only admin can add premium users.")
        return

    if len(context.args) == 0:
        await update.message.reply_text("Usage: `/premium <user_id>-<duration>`", parse_mode="Markdown")
        return

    try:
        uid, duration = context.args[0].split("-")
        ok, msg = add_premium_user(int(uid), duration)
        await update.message.reply_text("✅ " + msg if ok else "⚠️ " + msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ---------------- MESSAGE HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ✅ CASE 1: If user sends Adrino short link
    if ADRION_DOMAIN in text:
        if is_premium_user(user_id):
            original = get_original_from_short(text)
            if original:
                await update.message.reply_text(f"🌟 Premium Detected!\nDirect link:\n{original}")
            else:
                await update.message.reply_text("⚠️ Link not found or not created by this bot.")
        else:
            await update.message.reply_text(f"🔗 Normal user detected!\nYou’ll see ads:\n{text}")
        return

    # ✅ CASE 2: If user sends any normal link
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("⏳ Shortening link via Adrino...")
        result = shorten_url(text)
        if result["success"]:
            short = result["short_url"]
            keyboard = [[InlineKeyboardButton("🔗 Open Link", url=short)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Shortened link created!\n{short}\n\n📢 Normal users → Ads\n🌟 Premium users → Direct access",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"⚠️ Error: {result['error']}")
    else:
        await update.message.reply_text("Please send a valid URL (http/https).")

# ---------------- MAIN ----------------
def main():
    init_db()
    cleanup_expired_users()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 AdrinoLinks Premium Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
