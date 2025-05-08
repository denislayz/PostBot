from flask import Flask, request
import json
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
import asyncio

app = Flask(__name__)

# === НАСТРОЙКИ ===
TOKEN = "7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY"
application = ApplicationBuilder().token(TOKEN).build()

# === ОБРАБОТЧИКИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я работаю через вебхук!")

application.add_handler(CommandHandler("start", start))

# === ГЛАВНАЯ СТРАНИЦА ===
@app.route('/')
def home():
    return "Бот работает!"

# === ВЕБХУК ===
@app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        data = request.get_data().decode('utf-8')
        update = Update.de_json(json.loads(data), application)
        await application.initialize()
        await application.process_update(update)
        return "OK"
    except Exception as e:
        print("Ошибка при обработке обновления:", e)
        return "Ошибка", 500
