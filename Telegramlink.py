import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Telegram bot token (BotFather se milega)
TELEGRAM_BOT_TOKEN = "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"

# AdrionLinks API details
API_TOKEN = "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
API_URL = "https://adrinolinks.in/member/tools/api"

# Function to shorten link
def shorten_link(long_url):
    # AdrionLinks API expects GET request with url and token as query params
    params = {
        "url": long_url,
        "token": API_TOKEN
    }
    
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        # Check keys in response (actual API key might be 'short', 'short_url', etc.)
        if 'short' in result:
            return result['short']
        elif 'short_url' in result:
            return result['short_url']
        elif 'url' in result:
            return result['url']
        else:
            return f"Short link not found in response: {result}"
    
    except Exception as e:
        return f"Error: {str(e)}"

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me any link and I will shorten it for you.")

# Message handler for links
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    long_url = update.message.text.strip()
    if not long_url.startswith("http"):
        await update.message.reply_text("Please send a valid URL starting with http or https.")
        return

    await update.message.reply_text("Shortening your link...")
    short_url = shorten_link(long_url)
    await update.message.reply_text(f"Here is your short link:\n{short_url}")

# Main function to run bot
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
