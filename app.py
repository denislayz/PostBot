import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext

# Инициализация Flask приложения
app = Flask(__name__)

# Токен твоего бота
TOKEN = '7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY'  # Твой токен

# Устанавливаем логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем приложение Telegram с помощью ApplicationBuilder
application = ApplicationBuilder().token(TOKEN).build()

# Функция для обработки команды /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет, я бот!")

# Устанавливаем обработчик команды /start
application.add_handler(CommandHandler("start", start))

# Вебхук
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    application.process_update(update)
    return 'OK', 200

# Устанавливаем вебхук на Telegram API
def set_webhook():
    url = 'https://postbot228-pujcv9z98-denislayz-gmailcoms-projects.vercel.app/7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY'  # Твой URL на Vercel
    application.bot.set_webhook(url)

# Включаем вебхук при старте приложения
if __name__ == '__main__':
    set_webhook()
    app.run(port=5000)
