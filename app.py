import os
import sqlite3
import asyncio

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ================== НАСТРОЙКИ ==================
TOKEN = '7159627672:AAFoa1eN1JUFYaOwO0nqVCFv6AKIol3o_aY'
WEBHOOK_URL = 'https://postbot-production.up.railway.app/webhook'
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')
# ==============================================

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # Таблица пользователей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    )""")
    # Таблица групп
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER,
        user_id  INTEGER,
        title    TEXT,
        PRIMARY KEY (group_id, user_id)
    )""")
    # Таблица тем
    cur.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        topic_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id    INTEGER,
        user_id     INTEGER,
        title       TEXT
    )""")
    # Таблица черновиков постов
    cur.execute("""
    CREATE TABLE IF NOT EXISTS drafts (
        user_id     INTEGER PRIMARY KEY,
        group_id    INTEGER,
        topic_id    INTEGER,
        title       TEXT,
        text        TEXT
    )""")
    # Таблица медиа для черновиков
    cur.execute("""
    CREATE TABLE IF NOT EXISTS media (
        user_id   INTEGER,
        file_id   TEXT
    )""")
    # Таблица кнопок для черновиков
    cur.execute("""
    CREATE TABLE IF NOT EXISTS buttons (
        user_id   INTEGER,
        label     TEXT,
        url       TEXT
    )""")
    con.commit()
    con.close()

# ======== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========
def db_execute(query, params=(), fetch=False):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(query, params)
    if fetch:
        result = cur.fetchall()
    else:
        result = None
    con.commit()
    con.close()
    return result

# ========== HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db_execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
    # Главное меню
    kb = [
        [InlineKeyboardButton("Выбрать группу", callback_data='select_group')],
        [InlineKeyboardButton("Добавить группу", callback_data='add_group')]
    ]
    await update.message.reply_text("Главное меню:", reply_markup=InlineKeyboardMarkup(kb))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # --- Выбрать группу ---
    if data == 'select_group':
        groups = db_execute(
            "SELECT group_id, title FROM groups WHERE user_id=?", (uid,), fetch=True
        )
        if not groups:
            await query.edit_message_text("Нет подключенных групп.")
            return
        kb = [
            [InlineKeyboardButton(title, callback_data=f'grp_{gid}')]
            for gid, title in groups
        ]
        await query.edit_message_text("Выберите группу:", reply_markup=InlineKeyboardMarkup(kb))

    # --- После выбора группы ---
    elif data.startswith('grp_'):
        gid = int(data.split('_')[1])
        # Сохраним выбор в drafts.user_id
        db_execute(
            "INSERT OR REPLACE INTO drafts(user_id, group_id) VALUES(?,?)",
            (uid, gid)
        )
        kb = [
            [InlineKeyboardButton("Сделать пост", callback_data='make_post')],
            [InlineKeyboardButton("Добавить тему", callback_data='add_topic')],
            [InlineKeyboardButton("Удалить группу", callback_data='del_group')]
        ]
        await query.edit_message_text("Группа выбрана:", reply_markup=InlineKeyboardMarkup(kb))

    # --- Добавить группу инструкции ---
    elif data == 'add_group':
        text = (
            "Чтобы добавить группу:\n"
            "1. Добавьте бота в группу и сделайте его админом.\n"
            "2. Отправьте любое сообщение в эту группу.\n"
            "3. Вернитесь и нажмите /start."
        )
        await query.edit_message_text(text)

    # --- Удалить группу ---
    elif data == 'del_group':
        # читаем из drafts таблицы
        rec = db_execute(
            "SELECT group_id FROM drafts WHERE user_id=?", (uid,), fetch=True
        )
        if rec:
            db_execute("DELETE FROM groups WHERE user_id=? AND group_id=?", (uid, rec[0][0]))
            await query.edit_message_text("Группа удалена.")
        else:
            await query.edit_message_text("Ошибка удаления.")

    # --- Сделать пост ---
    elif data == 'make_post':
        # Начинаем черновик
        db_execute(
            "INSERT OR REPLACE INTO drafts(user_id, title, text) VALUES(?,?,?)",
            (uid, '', '')
        )
        await query.edit_message_text("Введите заголовок (или /skip):")

    # --- Добавить тему (thread) ---
    elif data == 'add_topic':
        await query.edit_message_text("Отправьте ID темы (thread_id) и название через пробел:")

    # Можно добавить «Назад» и «Отменить» в каждом меню аналогично


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat = update.message.chat
    text = update.message.text or ''

    # --- Сообщение из группы для регистрации ---
    if chat.type in ['group', 'supergroup']:
        db_execute(
            "INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,)
        )
        db_execute(
            "INSERT OR IGNORE INTO groups(group_id, user_id, title) VALUES(?,?,?)",
            (chat.id, uid, chat.title)
        )
        await update.message.reply_text("Группа зарегистрирована.")
        return

    # --- Работа с черновиком ---
    rec = db_execute(
        "SELECT group_id, title, text FROM drafts WHERE user_id=?", (uid,), fetch=True
    )
    if not rec:
        return

    group_id, title, body = rec[0]

    # Узнаём шаг по title/text в таблице drafts: если title пуст, запрашиваем заголовок
    if title == '':
        if text.startswith('/skip'):
            new_title = ''
        else:
            new_title = text
        db_execute("UPDATE drafts SET title=? WHERE user_id=?", (new_title, uid))
        await update.message.reply_text("Введите основной текст (или /skip):")
        return

    if body == '':
        if text.startswith('/skip'):
            new_body = ''
        else:
            new_body = text
        db_execute("UPDATE drafts SET text=? WHERE user_id=?", (new_body, uid))
        await update.message.reply_text("Отправьте фото (или /done если без медиа):")
        return

    # Медиа
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        db_execute("INSERT INTO media(user_id, file_id) VALUES(?,?)", (uid, file_id))
        await update.message.reply_text("Фото получено. /done когда закончите.")
        return

    # Завершили медиа
    if text.startswith('/done'):
        # Сразу предпросмотр
        await preview_post(update, context)
        return

    # Добавление инлайн-кнопок
    if text.startswith('/button '):
        # формат: /button Label|https://link
        try:
            label, url = text[len('/button '):].split('|', 1)
            db_execute("INSERT INTO buttons(user_id, label, url) VALUES(?,?,?)", (uid, label, url))
            await update.message.reply_text(f"Кнопка '{label}' добавлена.")
        except:
            await update.message.reply_text("Неправильный формат. Используй /button Текст|URL")
        return

    # /preview
    if text.startswith('/preview'):
        await preview_post(update, context)
        return

    # /send
    if text.startswith('/send'):
        await send_post(update, context)
        return


async def preview_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rec = db_execute("SELECT title, text FROM drafts WHERE user_id=?", (uid,), fetch=True)[0]
    title, body = rec
    medias = db_execute("SELECT file_id FROM media WHERE user_id=?", (uid,), fetch=True)
    buttons = db_execute("SELECT label, url FROM buttons WHERE user_id=?", (uid,), fetch=True)

    # Отправляем медиа
    media_group = [InputMediaPhoto(f[0]) for f in medias]
    if media_group:
        await context.bot.send_media_group(chat_id=uid, media=media_group)

    # Собираем текст
    txt = f"*{title}*\n{body}" if title else body
    # Собираем кнопки
    if buttons:
        kb = [[InlineKeyboardButton(lbl, url=url)] for lbl, url in buttons]
        reply_markup = InlineKeyboardMarkup(kb)
    else:
        reply_markup = None

    await context.bot.send_message(chat_id=uid, text=txt, parse_mode='Markdown', reply_markup=reply_markup)
    await context.bot.send_message(chat_id=uid, text="Для отправки в группу используйте /send")

async def send_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rec = db_execute("SELECT group_id, title, text FROM drafts WHERE user_id=?", (uid,), fetch=True)[0]
    group_id, title, body = rec
    medias = db_execute("SELECT file_id FROM media WHERE user_id=?", (uid,), fetch=True)
    buttons = db_execute("SELECT label, url FROM buttons WHERE user_id=?", (uid,), fetch=True)

    # Отправляем в группу
    mg = [InputMediaPhoto(f[0]) for f in medias]
    if mg:
        await context.bot.send_media_group(chat_id=group_id, media=mg)

    txt = f"*{title}*\n{body}" if title else body
    if buttons:
        kb = [[InlineKeyboardButton(lbl, url=url)] for lbl, url in buttons]
        reply_markup = InlineKeyboardMarkup(kb)
        await context.bot.send_message(chat_id=group_id, text=txt, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=group_id, text=txt, parse_mode='Markdown')

    # Очищаем черновики
    db_execute("DELETE FROM drafts WHERE user_id=?", (uid,))
    db_execute("DELETE FROM media WHERE user_id=?", (uid,))
    db_execute("DELETE FROM buttons WHERE user_id=?", (uid,))
    await context.bot.send_message(chat_id=uid, text="Пост отправлен!")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))
    app.add_handler(CommandHandler("preview", preview_post))
    app.add_handler(CommandHandler("send", send_post))

    # Устанавливаем вебхук
    app.bot.set_webhook(WEBHOOK_URL)

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()
