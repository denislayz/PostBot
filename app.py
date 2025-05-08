from flask import Flask, request
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder

app = Flask(__name__)

# Токен вашего бота
TOKEN = "7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY"
WEBHOOK_URL = "https://postbot228.vercel.app/webhook"

# Инициализация бота
application = ApplicationBuilder().token(TOKEN).build()

# Устанавливаем вебхук
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    response = requests.get(url)
    print(f"Webhook setup response: {response.json()}")  # Добавим больше информации

# Этот маршрут будет обрабатывать запросы от Telegram
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Логируем данные, чтобы понимать, что приходит в запросе
        print("Received data:", request.get_data().decode("UTF-8"))
        
        json_str = request.get_data().decode("UTF-8")
        update = Update.de_json(json.loads(json_str), application)
        application.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"Error processing update: {e}")
        return "Internal Server Error", 500

# Главная страница
@app.route('/')
def home():
    return "Бот работает!"

if __name__ == "__main__":
    set_webhook()  # Устанавливаем вебхук
    app.run(debug=True, host='0.0.0.0', port=5000)  # Запускаем Flask сервер
