import logging
import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, Dispatcher
from telegram.ext import ContextTypes
from telegram import Bot

# Инициализация FastAPI
app = FastAPI()

# Получение токена бота и URL вебхука из переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Создание экземпляра бота
bot = Bot(TOKEN)

# Логирование для отслеживания ошибок
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Устанавливаем вебхук для бота
bot.set_webhook(url=WEBHOOK_URL)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я ваш бот, как могу помочь?")

# Обработчик вебхука Telegram
@app.post("/")
async def telegram_webhook(req: Request):
    # Получаем данные от Telegram
    data = await req.json()
    logging.info(f"Received update: {data}")

    # Обрабатываем данные с помощью библиотеки python-telegram-bot
    update = Update.de_json(data, bot)
    dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.process_update(update)

    return {"status": "ok"}

