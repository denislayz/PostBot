from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
import os
import logging

TOKEN = os.getenv("BOT_TOKEN")  # Токен бота берём из переменной окружения

bot = Bot(token=TOKEN)
app = FastAPI()

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Обработка команды /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Бот подключен через webhook и работает на Vercel.")

@app.post("/")
async def telegram_webhook(req: Request):
    # Получаем обновление от Telegram
    data = await req.json()  # Преобразуем тело запроса в JSON
    logging.info(f"Received update: {data}")  # Логируем данные для отладки
    
    # Создаем объект обновления
    update = Update.de_json(data, bot)
    
    # Создаем обработчик команд
    dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
    dispatcher.add_handler(CommandHandler("start", start))  # Обрабатываем команду /start
    
    # Обрабатываем обновление
    dispatcher.process_update(update)
    
    return {"status": "ok"}
