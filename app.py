import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.ext import ApplicationBuilder
from telegram import Bot

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL для webhook
if not TOKEN:
    raise ValueError("Telegram token is not set in environment variables.")
if not WEBHOOK_URL:
    raise ValueError("Webhook URL is not set in environment variables.")

# Список для хранения групп и тем для постинга (пример)
groups_and_topics = {
    'group_1': ['topic_1', 'topic_2'],
    'group_2': ['topic_3', 'topic_4'],
}

# Функция для обработки команды /start
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    await update.message.reply_text(f"Привет, {user.first_name}! Я готов помочь.")

# Функция для обработки сообщений
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    if text.lower() == "/start":
        await start(update, context)
    else:
        await update.message.reply_text(f"Ты написал: {text}")

# Функция для добавления групп и тем
async def add_group_and_topic(update: Update, context: CallbackContext):
    group_name = context.args[0]
    topic_name = context.args[1]
    
    if group_name not in groups_and_topics:
        groups_and_topics[group_name] = []
    groups_and_topics[group_name].append(topic_name)
    
    await update.message.reply_text(f"Группа {group_name} и тема {topic_name} добавлены!")

# Функция для постинга в группы по заданной теме
async def post_to_groups(context: CallbackContext):
    for group, topics in groups_and_topics.items():
        for topic in topics:
            await context.bot.send_message(group, f"Пост на тему: {topic}")

# Основная асинхронная функция для запуска бота
async def main():
    app = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addgroup", add_group_and_topic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Настройка вебхука
    # Замените на свой URL вебхука
    await app.bot.set_webhook(WEBHOOK_URL)

    # Запуск бота с использованием webhook
    await app.run_webhook(
        listen="0.0.0.0",  # слушаем все IP адреса
        port=8443,  # стандартный порт для вебхуков
        url_path=TOKEN  # уникальная часть пути для вашего вебхука
    )

if __name__ == "__main__":
    # Запускаем основной цикл с асинхронным методом main
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(main())  # Запускаем main() как задачу
    loop.run_forever()  # Даем циклу событий работать бесконечно
