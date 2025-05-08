from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = "7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY"
WEBHOOK_URL = "https://your-render-url.onrender.com"

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    data = {"url": WEBHOOK_URL}
    response = requests.post(url, data=data)
    print("Webhook setup:", response.text)

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        send_message(chat_id, f"Ты написал: {text}")
    return "OK"

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=10000)
