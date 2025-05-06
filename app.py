from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Создаем FastAPI-приложение
app = FastAPI()

# Простой маршрут для проверки, что приложение работает
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <head>
            <title>Telegram Bot Hosting</title>
        </head>
        <body>
            <h1>Привет! Бот успешно работает на Vercel.</h1>
            <p>Здесь можно разместить документацию или интерфейс.</p>
        </body>
    </html>
    """
