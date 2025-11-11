"""
Telegram LiteShort Bot for Pydroid 3
- Sends shortened links using LiteShort API
- Safe, clean, and handles multiple links
"""

import os
import re
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ----------------- CONFIG -----------------
# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U')

# LiteShort API
LITESHORT_API_TOKEN = os.getenv('LITESHORT_API_TOKEN', '80011abeb528b51241137352d1e54c077760f3ee')
LITESHORT_API_URL = 'https://liteshort.com/member/tools/api'

# ----------------- LOGGING -----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------- URL REGEX -----------------
# Fixed regex for URLs (safe for Python/Pydroid)
URL_RE = re.compile(r'(https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=%]+)')

# ----------------- FUNCTIONS -----------------
def find_urls(text: str):
    """Return list of URLs found in a text"""
    return URL_RE.findall(text or '')

def shorten_with_liteshort(url: str) -> str:
    """Shorten a single URL using LiteShort API"""
    try:
        response = requests.post(
            LITESHORT_API_URL,
            data={'api_token': LITESHORT_API_TOKEN, 'url': url},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success' and 'shortenedUrl' in data:
            return data['shortenedUrl']
        else:
            raise RuntimeError(data.get('message', 'Unknown LiteShort API error'))
    except requests.RequestException as e:
        logger.error('Network error for %s: %s', url, e)
        raise RuntimeError('Network error occurred')
    except Exception as e:
        logger.error('Error shortening %s: %s', url, e)
        raise RuntimeError(str(e))

# ----------------- TELEGRAM HANDLERS -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send me a link and I will shorten it using LiteShort.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any URL starting with http:// or https:// and I will shorten it.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ''
    urls = find_urls(text)
    if not urls:
        await update.message.reply_text("No valid URL found. Please send a proper link.")
        return

    replies = []
    for url in urls:
        try:
            short_url = shorten_with_liteshort(url)
            replies.append(f"{url} -> {short_url}")
        except RuntimeError as e:
            replies.append(f"{url} -> ERROR: {e}")

    await update.message.reply_text("\n".join(replies))

# ----------------- MAIN -----------------
def main():
    if TELEGRAM_BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
        raise RuntimeError("Set your TELEGRAM_BOT_TOKEN environment variable!")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting Telegram LiteShort Bot...")
    app.run_polling()

if __name__ == '__main__':
    main()
