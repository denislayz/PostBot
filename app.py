import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, Application

# Replace with your bot's token
TOKEN = '7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY'

# Webhook URL for Telegram (this should be your deployed Railway URL)
WEBHOOK_URL = 'https://postbot-production.up.railway.app/webhook'

# Start command function
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Hello, I am your bot!')

# Function to set webhook
def set_webhook(application: Application):
    """Sets the webhook to the Telegram Bot API."""
    application.bot.set_webhook(WEBHOOK_URL)

def main():
    """Start the bot with a webhook and the /start command handler."""
    # Initialize the bot application with your bot token
    application = Application.builder().token(TOKEN).build()

    # Register /start command handler
    application.add_handler(CommandHandler("start", start))

    # Set the webhook URL
    set_webhook(application)

    # Start polling (this is useful if you want to run both webhook and polling, but we'll rely on webhook here)
    application.run_polling()

if __name__ == '__main__':
    main()
