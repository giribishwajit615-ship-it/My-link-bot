# filename: shortener_bot.py
# pip install python-telegram-bot==20.7 requests

import os
import requests
import sqlite3
import datetime
from urllib.parse import urlparse, quote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"
ADRION_API_TOKEN = os.getenv("ADRION_API_TOKEN") or "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
ADRION_API_URL = "https://adrinolinks.in/api"
ADRION_DOMAIN = "adrinolinks.in"  # your shortener domain (used for detection)

# ---------------- Admin config ----------------
ADMIN_USER_IDS = [7681308594, 8244432792]  # Add your admin IDs
def is_admin(user_id: int):
    return user_id in ADMIN_USER_IDS
# ---------------------------------------------

# ---------------- Database Setup ----------------
DB_FILE = "premium_users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # premium table: expiry stored as ISO string
    c.execute("""CREATE TABLE IF NOT EXISTS premium (
        user_id INTEGER PRIMARY KEY,
        expiry TEXT
    )""")
    # links table: store canonical short_key (netloc+path) as primary key
    c.execute("""CREATE TABLE IF NOT EXISTS links (
        short_key TEXT PRIMARY KEY,
        original_url TEXT
    )""")
    conn.commit()
    conn.close()

def now_iso():
    return datetime.datetime.now().isoformat()

def cleanup_expired_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = now_iso()
    # expiry stored as ISO string, compare lexicographically works for ISO format
    c.execute("DELETE FROM premium WHERE expiry <= ?", (now,))
    conn.commit()
    conn.close()

def add_premium_user(user_id: int, duration: str):
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

    expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO premium (user_id, expiry) VALUES (?, ?)", (user_id, expiry_date))
    conn.commit()
    conn.close()
    readable = datetime.datetime.fromisoformat(expiry_date).strftime('%Y-%m-%d %H:%M:%S')
    return True, f"User {user_id} added as premium for {duration} (expires on {readable})."

def is_premium_user(user_id: int):
    cleanup_expired_users()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT expiry FROM premium WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            expiry = datetime.datetime.fromisoformat(row[0])
            return expiry > datetime.datetime.now()
        except Exception:
            return False
    return False

# ---------------- Helpers for canonical short key ----------------
def make_short_key(url: str):
    """
    Convert a URL to canonical short_key = netloc + path (without trailing slash)
    Example: https://adrinolinks.in/Abc -> adrinoslinks.in/Abc
    """
    try:
        p = urlparse(url)
        netloc = p.netloc.lower()
        path = p.path.rstrip('/')
        if path == '':
            path = '/'
        return netloc + path
    except Exception:
        return url.strip().lower()

# ---------------- Adrino Shortener ----------------
def shorten_url(original_url: str):
    try:
        api_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={quote(original_url)}&format=json"
        response = requests.get(api_url, timeout=12)
        data = response.json()
        if data.get("status") == "success":
            short = data.get("shortenedUrl")
            if not short:
                return {"success": False, "error": "No shortenedUrl in response."}

            short_key = make_short_key(short)
            # save mapping (short_key -> original_url)
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("REPLACE INTO links (short_key, original_url) VALUES (?, ?)", (short_key, original_url))
            conn.commit()
            conn.close()

            return {"success": True, "short_url": short}
        else:
            return {"success": False, "error": data.get("message", "Adrino API error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_original_from_short(short_url: str):
    short_key = make_short_key(short_url)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT original_url FROM links WHERE short_key = ?", (short_key,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

# ---------------- Bot Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send any http/https link to shorten.\n"
        "Admins: /premium <user_id>-<duration> (7D | 1M | 3M | 6M | 1Y)"
    )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Only admin can use this command.")
        return

    if len(context.args) == 0:
        await update.message.reply_text(
            "Usage:\n`/premium <user_id>-<duration>`\nExample: `/premium 1111111111-7D`",
            parse_mode="Markdown"
        )
        return

    try:
        parts = context.args[0].split("-")
        if len(parts) != 2:
            raise ValueError("Wrong format")
        target_id = int(parts[0])
        duration = parts[1].upper()
        ok, msg = add_premium_user(target_id, duration)
        await update.message.reply_text("✅ " + msg if ok else "⚠️ " + msg)
    except Exception as e:
        await update.message.reply_text(
            f"❌ Invalid format. Example: `/premium 1111111111-1M`\nError: {e}",
            parse_mode="Markdown"
        )

# Optional: allow admin to list premium users (helpful for debug)
async def list_premiums(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Only admin can use this.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, expiry FROM premium")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No premium users.")
        return
    lines = []
    for u, e in rows:
        try:
            readable = datetime.datetime.fromisoformat(e).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            readable = e
        lines.append(f"{u} — expires: {readable}")
    await update.message.reply_text("Premium users:\n" + "\n".join(lines))

# ---------------- Message Handling ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("Please send a valid URL starting with http:// or https://")
        return

    # If user sent an Adrino short link (domain match), decide based on premium
    parsed = urlparse(text)
    if ADRION_DOMAIN in parsed.netloc.lower():
        # It's an Adrino short link
        if is_premium_user(user_id):
            original = get_original_from_short(text)
            if original:
                await update.message.reply_text(f"🌟 Premium Detected! Direct link:\n{original}")
                return
            else:
                # If mapping not found, try to attempt resolving via Adrino API (best-effort)
                await update.message.reply_text(
                    "⚠️ Short link not found in DB. If this link was created by this bot earlier, mapping should exist.\n"
                    "Ask the creator/admin to re-generate the short link through this bot."
                )
                return
        else:
            # Normal user just open short link (ads)
            keyboard = [[InlineKeyboardButton("🌐 Open Link", url=text)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🔗 Here is the short link (ads may appear):\n{text}",
                reply_markup=reply_markup
            )
            return

    # Otherwise: user sent an original file link — create Adrino short link and save mapping
    await update.message.reply_text("🔗 Generating Adrino short link... ⏳")
    result = shorten_url(text)
    if result["success"]:
        short = result["short_url"]
        keyboard = [[InlineKeyboardButton("🌐 Open Link", url=short)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"✅ Shortened link:\n{short}\n\n📢 Normal users will see ads. Premium users who click this short link will get direct access.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(f"⚠️ Error: {result['error']}")

# ---------------- Main ----------------
def main():
    init_db()
    cleanup_expired_users()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium_command))
    # optional admin helper
    app.add_handler(CommandHandler("listprem", list_premiums))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 AdrinoLinks Premium Bypass Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
