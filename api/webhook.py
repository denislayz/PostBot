import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Секретный ключ для валидации запросов. Можно использовать любое уникальное значение.
SECRET = "super-secret-key-123456"  # Это ключ для проверки, его можно поменять

# Токен вашего Telegram-бота. Заменим на твой реальный токен.
TELEGRAM_TOKEN = "7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY"  # Заменено на твой токен

# URL для твоего вебхука на Vercel
WEBHOOK_URL = "https://postbot228.vercel.app/api/webhook"  # Замените на реальный URL (текущий пример!)

# Установка вебхука
def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    response = requests.post(url, data={"url": WEBHOOK_URL})
    print(response.text)

# Обработка запросов, приходящих на вебхук
@app.route("/api/webhook", methods=["POST"])
def handle_webhook():
    if request.method == "POST":
        data = request.json
        if validate_signature(data):
            # Обработка данных, например, ответ на сообщение
            process_update(data)
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"error": "Invalid signature"}), 403

def validate_signature(data):
    # В данном примере мы проверяем, что данные содержат правильный секретный ключ
    # В реальном приложении можно добавлять дополнительные проверки для повышения безопасности
    return data.get("secret") == SECRET

def process_update(data):
    # Тут вы обрабатываете полученные данные
    print("Received update:", json.dumps(data, indent=4))

if __name__ == "__main__":
    set_webhook()
    app.run(debug=True, host='0.0.0.0', port=5000)
