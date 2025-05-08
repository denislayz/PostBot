import logging
from flask import Flask, request
from telegram import Bot
from telegram.ext import Dispatcher, CommandHandler
import os

# Настройки
TOKEN = os.getenv('7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY')  # Токен Telegram-бота
WEBHOOK_URL = os.getenv('postbot-production.up.railway.app')  # URL для вебхука

# Инициализация Flask-приложения
app = Flask(__name__)

# Инициализация бота
bot = Bot(TOKEN)

# Функция обработки команды /start
def start(update, context):
    update.message.reply_text('Привет! Я твой бот. Напиши /help для получения справки.')

# Создаем диспетчер для обработки сообщений
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))

# Настройка вебхука для получения данных
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = bot.get_updates(json_str)
    dispatcher.process_update(update)
    return "ok", 200

# Установка вебхука на сервер Telegram
def set_webhook():
    bot.set_webhook(WEBHOOK_URL + '/webhook')

# Запуск сервера Flask
if __name__ == '__main__':
    set_webhook()  # Устанавливаем вебхук при запуске
    app.run(debug=True, host='0.0.0.0', port=5000)
