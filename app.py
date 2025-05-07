from flask import Flask, request
import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

TOKEN = "7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY"
WEBHOOK_URL = "https://postbot228.vercel.app/webhook"

bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Бот работает!")

# Регистрируем обработчик
application.add_handler(CommandHandler("start", start))

# Устанавливаем вебхук перед первым запросом
@app.before_first_request
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    r = requests.get(url)
    print("Webhook status:", r.json())

# Обработка входящих запросов от Telegram
@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    await application.process_update(update)
    return 'ok'

# Проверка работы сервера
@app.route('/')
def home():
    return 'Бот работает!'

if __name__ == '__main__':
    app.run()
