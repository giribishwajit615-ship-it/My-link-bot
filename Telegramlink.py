import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === CONFIG ===
TOKEN = "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"       # BotFather se mila token
ADMIN_ID = 7681308594               # <-- Apna Telegram numeric ID daalo
API_TOKEN = "80011abeb528b51241137352d1e54c077760f3ee"  # Adrinolinks.in ka API token (niche step-1 me milega)

# === Helper ===
def is_admin(user_id):
    return user_id == ADMIN_ID

def shorten_url(long_url):
    """
    Adrinolinks API call — returns shortened URL or error message.
    """
    api_url = "https://adrinolinks.in/api"
    params = {
        "api": API_TOKEN,
        "url": long_url
    }
    try:
        r = requests.get(api_url, params=params, timeout=10)
        data = r.json()
        if data.get("status") == "success":
            return data["shortenedUrl"]
        else:
            return f"⚠️ Error: {data.get('message', 'Unknown error')}"
    except Exception as e:
        return f"❌ API Error: {e}"

# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied! Ye bot sirf admin ke liye hai.")
        return
    await update.message.reply_text("✅ Hello Admin! Mujhe koi URL bhejo, main use short karke dunga.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ye command sirf admin ke liye hai.")
        return
    await update.message.reply_text("Simply ek link bhejo, main usko short kar ke reply kar dunga.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Tumhe is bot ka access nahi hai.")
        return

    text = update.message.text.strip()

    # Check if text looks like a URL
    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("⚠️ Kripya ek valid URL bhejo (http:// ya https:// se shuru).")
        return

    await update.message.reply_text("🔗 Short kar raha hoon, kripya rukho...")
    short_link = shorten_url(text)
    await update.message.reply_text(f"✅ Shortened URL:\n{short_link}")

# === Main ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("✅ Bot started (press Ctrl+C to stop)")
    app.run_polling()

if __name__ == "__main__":
    main()
