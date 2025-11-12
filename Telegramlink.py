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

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"
ADRION_API_TOKEN = os.getenv("ADRION_API_TOKEN") or "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
ADRION_API_URL = "https://adrinolinks.in/api"
ADRION_DOMAIN = "adrinolinks.in"

# Put your admin IDs here
ADMIN_USER_IDS = [7681308594, 8244432792]

# Private channel where admin-saved original links will be posted (must be an integer chat id)
# Example: "-1001234567890"
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID")  # set this in environment or None

DB_FILE = "premium_users.db"

# ---------------- Helpers ----------------
def is_admin(user_id: int):
    return user_id in ADMIN_USER_IDS

def now_iso():
    return datetime.datetime.now().isoformat()

def normalize_short_key(url: str):
    """Return canonical short_key from a URL: domain/path without scheme or trailing slash."""
    try:
        p = urlparse(url)
        netloc = p.netloc.lower().replace("www.", "")
        path = p.path.rstrip('/')
        if path == '':
            path = '/'
        return f"{netloc}{path}"
    except Exception:
        return url.strip().lower()

def resolve_redirects(url: str, timeout=10):
    """
    Follow redirects to get the final URL.
    Return the final URL (string). If fails, return original url.
    """
    try:
        # use HEAD first to avoid downloading content, allow redirects
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        final = resp.url
        # if final is empty fallback to GET
        if not final:
            resp2 = requests.get(url, allow_redirects=True, timeout=timeout)
            final = resp2.url
        return final
    except Exception:
        # fallback: try GET (some servers disallow HEAD)
        try:
            resp = requests.get(url, allow_redirects=True, timeout=timeout)
            return resp.url
        except Exception:
            return url

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # premium: expiry stored as ISO string
    c.execute("""CREATE TABLE IF NOT EXISTS premium (
        user_id INTEGER PRIMARY KEY,
        expiry TEXT
    )""")
    # links: store canonical short_key -> original_url, plus who saved & saved_on optionally
    c.execute("""CREATE TABLE IF NOT EXISTS links (
        short_key TEXT PRIMARY KEY,
        original_url TEXT,
        saved_by INTEGER,
        saved_on TEXT
    )""")
    conn.commit()
    conn.close()

def cleanup_expired_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = now_iso()
    c.execute("DELETE FROM premium WHERE expiry <= ?", (now,))
    conn.commit()
    conn.close()

def add_premium_user(user_id: int, duration: str):
    days_map = {"7D": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = days_map.get(duration.upper(), 0)
    if days == 0:
        return False, "❌ Invalid duration code! Use 7D/1M/3M/6M/1Y."
    expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO premium (user_id, expiry) VALUES (?, ?)", (user_id, expiry))
    conn.commit()
    conn.close()
    readable = datetime.datetime.fromisoformat(expiry).strftime('%Y-%m-%d %H:%M:%S')
    return True, f"✅ User {user_id} premium till {readable}"

def remove_premium_user(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM premium WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_premium_user(user_id: int):
    cleanup_expired_users()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT expiry FROM premium WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            expiry = datetime.datetime.fromisoformat(row[0])
            return expiry > datetime.datetime.now()
        except Exception:
            return False
    return False

def save_link_mapping(short_key: str, original_url: str, saved_by: int = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "REPLACE INTO links (short_key, original_url, saved_by, saved_on) VALUES (?, ?, ?, ?)",
        (short_key, original_url, saved_by, now_iso())
    )
    conn.commit()
    conn.close()

def get_original_from_short_key(short_key: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT original_url FROM links WHERE short_key=?", (short_key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ---------------- ADRINO SHORTENER ----------------
def shorten_via_adrino(original_url: str):
    """
    Call Adrino API to create a short link. Return dict {success, short_url or error}.
    """
    try:
        api_url = f"{ADRION_API_URL}?api={ADRION_API_TOKEN}&url={quote(original_url)}&format=json"
        resp = requests.get(api_url, timeout=12)
        data = resp.json()
        if data.get("status") == "success":
            short = data.get("shortenedUrl")
            return {"success": True, "short_url": short}
        else:
            return {"success": False, "error": data.get("message", "Adrino API error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------- BOT COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me any http/https link to shorten.\n\n"
        "Admin-only: send links to save them in your private channel + DB.\n\n"
        "Admin commands:\n"
        "/premium <user_id>-<duration>  (7D|1M|3M|6M|1Y)\n"
        "/remove <user_id>\n"
        "/listpremium\n\nUser:\n"
        "/info  (check your premium status)"
    )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user.id
    if not is_admin(caller):
        await update.message.reply_text("❌ Only admin can add premium.")
        return
    if len(context.args) == 0:
        await update.message.reply_text("Usage: `/premium <user_id>-<duration>`", parse_mode="Markdown")
        return
    try:
        target, duration = context.args[0].split("-")
        ok, msg = add_premium_user(int(target), duration)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user.id
    if not is_admin(caller):
        await update.message.reply_text("❌ Only admin can remove.")
        return
    if len(context.args) == 0:
        await update.message.reply_text("Usage: `/remove <user_id>`", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
        remove_premium_user(uid)
        await update.message.reply_text(f"✅ Removed {uid} from premium.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def listpremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user.id
    if not is_admin(caller):
        await update.message.reply_text("❌ Only admin can view list.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, expiry FROM premium ORDER BY expiry DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No active premium users.")
        return
    text = "🌟 Active premium users:\n\n"
    for uid, expiry in rows:
        text += f"`{uid}` → `{expiry}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_premium_user(uid):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT expiry FROM premium WHERE user_id=?", (uid,))
        row = c.fetchone()
        conn.close()
        await update.message.reply_text(f"🌟 You are premium till:\n`{row[0]}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ You are not a premium user.")

# ---------------- MESSAGE HANDLING ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    user_id = sender.id
    text = update.message.text.strip()

    # validate url quickly
    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("Please send a valid URL starting with http:// or https://")
        return

    # If it's an Adrino domain link (someone clicked/posted short link)
    parsed = urlparse(text)
    if ADRION_DOMAIN in parsed.netloc.lower():
        # Resolve redirects to canonical adrino short if needed
        final = resolve_redirects(text)
        short_key = normalize_short_key(final)
        # If premium user -> return original if we have mapping
        if is_premium_user(user_id):
            original = get_original_from_short_key(short_key)
            if original:
                await update.message.reply_text(f"🌟 Premium detected — direct file:\n{original}")
                return
            else:
                await update.message.reply_text(
                    "⚠️ Short link not found in DB. If this link was created by this bot earlier, try sending the original link again (admin can re-save)."
                )
                return
        else:
            # Normal user -> show short (ads)
            keyboard = [[InlineKeyboardButton("🌐 Open (Adrino)", url=text)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🔗 Here is the Adrino short link (ads may appear):",
                reply_markup=reply_markup
            )
            return

    # Otherwise: normal original link posted.
    # If sender is admin: shorten, save mapping, AND post to private channel
    await update.message.reply_text("⏳ Generating short link via Adrino...")
    res = shorten_via_adrino(text)
    if not res["success"]:
        await update.message.reply_text(f"⚠️ Error creating short link: {res.get('error')}")
        return

    short_url = res["short_url"]
    # Resolve final (in case adrino returns redirecting short variants) and canonicalize
    final = resolve_redirects(short_url)
    short_key = normalize_short_key(final)

    # Save mapping in DB (short_key -> original)
    save_link_mapping(short_key, text, saved_by=user_id)

    # Post/save to private channel if admin and PRIVATE_CHANNEL_ID set
    if is_admin(user_id) and PRIVATE_CHANNEL_ID:
        try:
            private_id = int(PRIVATE_CHANNEL_ID)
            msg = (
                f"🔒 *Saved by Admin:* `{user_id}`\n\n"
                f"*Original:* {text}\n"
                f"*Short (Adrino):* {short_url}\n"
                f"*Canonical key:* `{short_key}`\n"
            )
            await context.bot.send_message(chat_id=private_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            # don't fail if private post fails; inform admin
            await update.message.reply_text(f"⚠️ Could not post to private channel: {e}")

    # Reply to user with created short link
    keyboard = [[InlineKeyboardButton("🌐 Open Link", url=short_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"✅ Short link created:\n{short_url}\n\n📢 Normal users will see ads. Premium users who click this short link will get direct access.",
        reply_markup=reply_markup
    )

# ---------------- MAIN ----------------
def main():
    init_db()
    cleanup_expired_users()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("listpremium", listpremium_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Adrino Premium Bypass + Private-archive Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
