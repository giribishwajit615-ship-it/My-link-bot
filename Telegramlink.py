import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Telegram bot token (aapko BotFather se milega)
TELEGRAM_BOT_TOKEN = "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"

# AdrionLinks API details
API_TOKEN = "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634"
API_URL = "https://adrinolinks.in/member/tools/api"

# Function to shorten link
def shorten_link(long_url):
    data = {"url": long_url}
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(API_URL, json=data, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        if 'short_url' in result:
            return result['short_url']
        elif 'shortened_url' in result:
            return result['shortened_url']
        else:
            return "Success, but short link not found in response."
    else:
        return f"Error {response.status_code}: {response.text}"

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me a link and I will shorten it for you.")

# Message handler for links
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    long_url = update.message.text
    short_url = shorten_link(long_url)
    await update.message.reply_text(f"Shortened Link:\n{short_url}")

# Main function to run bot
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
