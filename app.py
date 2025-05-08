from flask import Flask, request
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder
import asyncio

app = Flask(__name__)

# Токен вашего бота
TOKEN = "7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY"
WEBHOOK_URL = "https://postbot228.vercel.app/webhook"

# Инициализация асинхронного бота
application = ApplicationBuilder().token(TOKEN).build()

# Устанавливаем вебхук
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    response = requests.get(url)
    print(response.json())

@app.route("/webhook", methods=["POST"])
async def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = Update.de_json(json.loads(json_str), application)
    await application.process_update(update)
    return "OK", 200

@app.route('/')
def home():
    return "Бот работает!"

if __name__ == "__main__":
    set_webhook()
    app.run(debug=True, host='0.0.0.0', port=5000)
