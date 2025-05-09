import os
import json
import logging
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

DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_state(uid):
    return data.setdefault(str(uid), {"state": "idle", "groups": {}, "topics": {}})

def reset_user_state(uid):
    prev = data.get(str(uid), {})
    groups = prev.get("groups", {})
    topics = prev.get("topics", {})
    data[str(uid)] = {"state": "idle", "groups": groups, "topics": topics}
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
        post = state.get("post", {})
        text = f"*{post.get('title','')}*\n{post.get('text','')}"
        buttons = post.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None
        if post.get("media"):
            await context.bot.send_photo(
                chat_id=uid,
                photo=post["media"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        else:
            await context.bot.send_message(
                chat_id=uid,
                text=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        return

    if query.data == "send":
        post = state.get("post", {})
        gid = state.get("selected_group")
        text = f"*{post.get('title','')}*\n{post.get('text','')}"
        buttons = post.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None
        if post.get("media"):
            await context.bot.send_photo(
                chat_id=gid,
                photo=post["media"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        else:
            await context.bot.send_message(
                chat_id=gid,
                text=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        await query.edit_message_text("✅ Пост отправлен.")
        reset_user_state(uid)
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = get_user_state(uid)

    # Ожидание упоминания в группе
    if state["state"] == "waiting_for_mention":
        chat = update.effective_chat
        st = data.setdefault(str(uid), {})
        gr = st.setdefault("groups", {})
        gr[str(chat.id)] = chat.title or "Группа"
        st["state"] = "idle"
        save_data()
        await update.message.reply_text(f"Группа «{chat.title}» добавлена!")
        await start(update, context)
        return

    # Ввод заголовка
    if state["state"] == "post_title":
        text = update.message.text or ""
        if text != "-":
            state["post"]["title"] = text
        state["state"] = "post_text"
        save_data()
        await update.message.reply_text("Введите текст (или «-» чтобы пропустить):")
        return

    # Ввод текста
    if state["state"] == "post_text":
        text = update.message.text or ""
        if text != "-":
            state["post"]["text"] = text
        state["state"] = "post_media"
        save_data()
        await update.message.reply_text("Прикрепите фото (или отправьте «-»):")
        return

    # Прикрепление медиа
    if state["state"] == "post_media":
        if update.message.photo:
            state["post"]["media"] = update.message.photo[-1].file_id
        state["state"] = "post_buttons"
        save_data()
        await update.message.reply_text("Введите кнопки (текст|URL на строку), «-» — пропустить:")
        return

    # Ввод кнопок
    if state["state"] == "post_buttons":
        text = update.message.text or ""
        if text != "-":
            buttons = []
            for line in text.splitlines():
                if "|" in line:
                    t,u = line.split("|",1)
                    buttons.append({"text":t.strip(),"url":u.strip()})
            state["post"]["buttons"] = buttons
        state["state"] = "confirm"
        save_data()
        await update.message.reply_text(
            "Готово. Хотите предпросмотр или сразу отправить?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить", callback_data="send")],
                [InlineKeyboardButton("❌ Отмена", callback_data="back")]
            ])
        )
        return

# ========== Запуск ==========
if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, message_handler))

    # Запускаем polling
    application.run_polling(poll_interval=3.0)
