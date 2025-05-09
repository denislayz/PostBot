import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ========== Логирование ==========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== Конфигурация ==========
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_TOKEN не установлена!")

# Файл для хранения состояния (группы, темы, черновики постов)
DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_state(uid):
    return data.setdefault(str(uid), {"state": "idle"})

def reset_user_state(uid):
    data[str(uid)] = {"state": "idle"}
    save_data()

# ========== Хендлеры ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = get_user_state(uid)
    groups = state.get("groups", {})
    if not groups:
        keyboard = [[InlineKeyboardButton("➕ Добавить группу", callback_data="add_group")]]
    else:
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"group:{gid}")]
            for gid, name in groups.items()
        ]
        keyboard.append([InlineKeyboardButton("➕ Добавить группу", callback_data="add_group")])
    await update.message.reply_text(
        "Выберите группу или добавьте новую:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = get_user_state(uid)

    if query.data == "add_group":
        state["state"] = "waiting_for_mention"
        save_data()
        await query.edit_message_text("Отметьте меня (@), я запомню этот чат (группу).")
        return

    if query.data.startswith("group:"):
        gid = query.data.split(":",1)[1]
        state["selected_group"] = gid
        state["state"] = "group_menu"
        save_data()
        await query.edit_message_text(
            "Меню группы:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Сделать пост", callback_data="make_post")],
                [InlineKeyboardButton("🗂 Добавить тему", callback_data="add_topic")],
                [InlineKeyboardButton("❌ Удалить группу", callback_data="remove_group")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]
            ])
        )
        return

    if query.data == "make_post":
        state["state"] = "post_title"
        state["post"] = {}
        save_data()
        await query.edit_message_text("Введите заголовок (или «-» чтобы пропустить):")
        return

    if query.data == "add_topic":
        state["state"] = "topic_name"
        save_data()
        await query.edit_message_text("Введите название темы и thread_id через пробел:")
        return

    if query.data == "remove_group":
        gid = state.get("selected_group")
        if gid:
            state["groups"].pop(gid, None)
        reset_user_state(uid)
        await query.edit_message_text("Группа удалена.")
        await start(update, context)
        return

    if query.data == "back":
        reset_user_state(uid)
        await start(update, context)
        return

    if query.data == "preview":
        post = state["post"]
        media = post.get("media")
        text = f"*{post.get('title','')}*\n{post.get('text','')}"
        buttons = post.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None
        if media:
            await context.bot.send_photo(uid, media, caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
        return

    if query.data == "send":
        gid = state.get("selected_group")
        post = state["post"]
        text = f"*{post.get('title','')}*\n{post.get('text','')}"
        media = post.get("media")
        buttons = post.get("buttons", [])
        kwargs = {"chat_id": gid, "parse_mode":"Markdown"}
        if media:
            await context.bot.send_photo(**kwargs, photo=media, caption=text,
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]))
        else:
            await context.bot.send_message(**kwargs, text=text,
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]))
        await query.edit_message_text("✅ Пост отправлен.")
        reset_user_state(uid)
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = get_user_state(uid)
    # шаг: ожидание упоминания
    if state["state"] == "waiting_for_mention":
        chat = update.effective_chat
        state.setdefault("groups", {})[str(chat.id)] = chat.title or "Группа"
        save_data()
        await update.message.reply_text(f"Добавил группу: {chat.title}")
        reset_user_state(uid)
        return

    # шаг: ввод заголовка
    if state["state"] == "post_title":
        text = update.message.text or ""
        if text != "-":
            state["post"]["title"] = text
        state["state"] = "post_text"
        save_data()
        await update.message.reply_text("Введите текст (или «-»):")
        return

    # шаг: ввод текста
    if state["state"] == "post_text":
        text = update.message.text or ""
        if text != "-":
            state["post"]["text"] = text
        state["state"] = "post_media"
        save_data()
        await update.message.reply_text("Прикрепите фото (или отправьте «-»):")
        return

    # шаг: прикрепление медиа
    if state["state"] == "post_media":
        if update.message.photo:
            state["post"]["media"] = update.message.photo[-1].file_id
        state["state"] = "post_buttons"
        save_data()
        await update.message.reply_text("Введите кнопки (текст|URL в строке), «-» — пропустить:")
        return

    # шаг: ввод кнопок
    if state["state"] == "post_buttons":
        text = update.message.text or ""
        if text != "-":
            buttons=[] 
            for line in text.splitlines():
                if "|" in line:
                    t,u=line.split("|",1)
                    buttons.append({"text":t.strip(),"url":u.strip()})
            state["post"]["buttons"]=buttons
        state["state"]="confirm"
        save_data()
        await update.message.reply_text(
            "Готово. Предпросмотр или отправить?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Предпросмотр",callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить",callback_data="send")],
                [InlineKeyboardButton("❌ Отмена",callback_data="back")]
            ])
        )

# ========== Запуск ==========
if __name__=="__main__":
    # Через asyncio.run polling не конфликтует с loop на Railway
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, message_handler))

    # Запускаем polling
    application.run_polling(poll_interval=3.0)
