# file: links_shortener_bot.py
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# --- CONFIG ---
TELEGRAM_TOKEN = "8182518309:AAFzn_ybY4nWaOOu3-PFSDQE08SYNy5F41U"
# LITESHORT config - replace with real API details
LITESHORT_API_URL = "https://liteshort.com/member/tools/api"   # <-- replace
LITESHORT_API_KEY = "80011abeb528b51241137352d1e54c077760f3ee"                 # <-- replace

# Author name for telegra.ph page
TELEGRAPH_AUTHOR = "LinksBot"

# Conversation states
COLLECTING = 1

# --- logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- helper: create telegra.ph page with links ---
def create_telegraph_page(title: str, links: list) -> str:
    """
    Create a simple telegra.ph page listing links.
    Returns the telegra.ph URL on success.
    """
    # telegra.ph createPage API expects an array of nodes; simplest approach is to send HTML via "content"
    # But telegraph has a simple createPage endpoint:
    api = "https://api.telegra.ph/createPage"
    # Build simple HTML content: paragraphs with anchor tags
    content_html = ""
    for idx, link in enumerate(links, start=1):
        content_html += f'<p>{idx}. <a href="{link}">{link}</a></p>'
    data = {
        "access_token": "",  # empty => anonymous page
        "title": title,
        "author_name": TELEGRAPH_AUTHOR,
        "content": content_html,
        "return_content": False
    }
    # telegra.ph accepts POST with form fields
    resp = requests.post(api, data=data, timeout=15)
    resp.raise_for_status()
    j = resp.json()
    if not j.get("ok"):
        raise RuntimeError("Telegraph error: " + str(j))
    url = j["result"]["url"]
    return url

# --- helper: shorten with liteshort (placeholder implementation) ---
def shorten_with_liteshort(long_url: str) -> str:
    """
    Shorten a URL using LITESHORT. Replace with real API details.
    This function demonstrates a POST with api_key and url; adjust per actual API.
    """
    # If you have the exact LITESHORT API, update this section to match their docs.
    payload = {
        "api_key": LITESHORT_API_KEY,
        "url": long_url
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(LITESHORT_API_URL, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    j = resp.json()
    # Example expected response: { "success": True, "short_url": "https://liteshort.xyz/abc123" }
    if "short_url" in j:
        return j["short_url"]
    # fallback if API differs:
    if j.get("success") and j.get("short"):
        return j.get("short")
    raise RuntimeError("Liteshort API response unexpected: " + str(j))

# --- Conversation handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salam! /Links command se shuru karein - fir apne links bhejein (ek per line). Jab done ho jaaye, /done bhej dijiye.")

async def links_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['links_buffer'] = []
    await update.message.reply_text("Okay — ab apne links bhejiye. Har link nayi line me. Jab finished ho to /done bhej dijiyega.")
    return COLLECTING

async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Extract URLs from the message (simple split by whitespace)
    parts = text.split()
    links = [p for p in parts if p.startswith("http://") or p.startswith("https://")]
    if not links:
        await update.message.reply_text("Koi valid link nahi mila in that message. Kripya http/https se shuru hone wale links bhejein.")
        return COLLECTING
    context.user_data.setdefault('links_buffer', []).extend(links)
    await update.message.reply_text(f"Added {len(links)} link(s). Total so far: {len(context.user_data['links_buffer'])}. Send more or /done.")
    return COLLECTING

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    links = context.user_data.get('links_buffer', [])
    if not links:
        await update.message.reply_text("Aapne koi link nahi bheja. /Links se phir shuru karein.")
        return ConversationHandler.END
    await update.message.reply_text("Links receive ho gaye. Ab ek single page banake short kar raha hoon...")

    try:
        # Create telegraph page
        title = f"Links from @{update.effective_user.username or update.effective_user.id}"
        page_url = create_telegraph_page(title, links)

        # Shorten using LITESHORT (replace implementation as needed)
        try:
            short = shorten_with_liteshort(page_url)
        except Exception as e:
            # If liteshort fails, fallback to returning the telegra.ph link
            logger.exception("Liteshort failed, returning telegra.ph link")
            await update.message.reply_text(f"Shortening with LITESHORT failed: {e}\nHere's the page link: {page_url}")
            context.user_data['links_buffer'] = []
            return ConversationHandler.END

        await update.message.reply_text(f"Aapka single short link yeh raha:\n{short}")
    except Exception as e:
        logger.exception("Error creating page or shortening")
        await update.message.reply_text(f"Kuch error hua: {e}")

    context.user_data['links_buffer'] = []
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Agar phir se chahen to /Links bhejein.")
    context.user_data['links_buffer'] = []
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('Links', links_cmd)],
        states={
            COLLECTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_links),
                CommandHandler('done', done),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)

    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
