from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, ContextTypes
import os
import logging

TOKEN = os.getenv("BOT_TOKEN")  # Токен бота берём из переменной окружения

bot = Bot(token=TOKEN)
app = FastAPI()

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Обработка команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Бот подключен через webhook и работает на Vercel.")

@app.post("/")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Привет! Бот успешно работает на Vercel."}
