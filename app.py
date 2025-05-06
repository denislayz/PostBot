from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler
import requests

app = Flask(__name__)

TOKEN = '7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY'  # Ваш токен бота
WEBHOOK_URL = 'https://postbot228-a2a6cog9r-denislayz-gmailcoms-projects.vercel.app/7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY'  # Ваш URL с верселя

# Создаем приложение для бота
application = Application.builder().token(TOKEN).build()

# Команда для старта
async def start(update: Update, context):
    await update.message.reply_text('Привет! Я твой бот.')

# Регистрируем команду /start
application.add_handler(CommandHandler('start', start))

@app.route(f'/{TOKEN}', methods=['POST'])  # Настройка маршрута для вебхука
def webhook():
    try:
        # Получаем обновление от Telegram
        update = Update.de_json(request.get_json(), application.bot)
        application.process_update(update)
        return 'OK', 200
    except Exception as e:
        print(f"Error: {e}")
        return 'Internal Server Error', 500


if __name__ == '__main__':
    # Устанавливаем вебхук для Telegram
    webhook_set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    response = requests.get(webhook_set_url)
    print(f"Webhook response: {response.text}")

    # Запускаем Flask сервер
    app.run(debug=True, host='0.0.0.0', port=8080)
