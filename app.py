import os
import json
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
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
    raise ValueError("TELEGRAM_TOKEN не установлена!")

DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_state(uid):
    return data.setdefault(
        str(uid),
        {
            "state": "idle",
            "groups": {},
            "topics": {},
            "post": {},
            "selected_group": None,
            "selected_topic": None,
            "reactions": {},
            "button_type": None,
            "users_reacted": set()
        }
    )

def reset_state_but_keep(uid):
    prev = data.get(str(uid), {})
    return {
        "state": "idle",
        "groups": prev.get("groups", {}),
        "topics": prev.get("topics", {}),
        "post": {},
        "selected_group": None,
        "selected_topic": None,
        "reactions": {},
        "button_type": None,
        "users_reacted": set()
    }

# ========== Хендлеры ========== (пример с минимальным button_handler)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data[str(uid)] = reset_state_but_keep(uid)
    save_data()
    kb = [[InlineKeyboardButton("Добавить группу", callback_data="add_group")]]
    await update.message.reply_text("Привет! Выберите группу:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    st = get_user_state(uid)
    cb = query.data

    if cb == "add_group":
        st["state"] = "await_group"
        save_data()
        await query.message.reply_text("Пришлите ссылку на группу или перешлите сообщение из неё.")
        return

    if cb == "btn_react":
        st["state"] = "post_react_1"
        st["button_type"] = "react"
        save_data()
        await query.message.reply_text("Пришлите эмоджи для первой реакции")
        return

    if cb == "btn_link":
        st["state"] = "post_link"
        st["button_type"] = "link"
        save_data()
        await query.message.reply_text("Пришлите текст и ссылку в формате 'Текст, URL'")
        return

    if cb == "skip_buttons":
        st["state"] = "confirm"
        st["button_type"] = None
        save_data()
        kb = [
            [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
            [InlineKeyboardButton("📨 Отправить", callback_data="send")],
            [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
        ]
        await query.message.reply_text("Кнопки пропущены. Готово к отправке:", reply_markup=InlineKeyboardMarkup(kb))
        return

    # реакция кнопка 2
    if st["state"] == "post_react_2" and cb == "continue_react":
        st["state"] = "confirm"
        save_data()
        kb = [
            [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
            [InlineKeyboardButton("📨 Отправить", callback_data="send")],
            [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
        ]
        await query.message.reply_text("Реакции добавлены.", reply_markup=InlineKeyboardMarkup(kb))
        return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_user_state(uid)

    if st["state"] == "await_group":
        group_link = update.message.text
        st["groups"][group_link] = {}
        st["selected_group"] = group_link
        st["state"] = "await_topic"
        save_data()
        await update.message.reply_text(f"Ты выбрал(а) группу {group_link}\nТеперь укажи тему в формате 'Название, ID'")
        return

    if st["state"] == "await_topic":
        try:
            name, tid = update.message.text.split(",")
            st["topics"][tid.strip()] = name.strip()
            st["selected_topic"] = tid.strip()
            st["state"] = "await_post_text"
            save_data()
            await update.message.reply_text(f"Ты выбрал(а) тему {name.strip()}\nТеперь введи текст поста")
        except ValueError:
            await update.message.reply_text("Формат неверный. Пример: Новости, 123")
        return

    if st["state"] == "await_post_text":
        st["post"]["text"] = update.message.text
        st["state"] = "await_post_media"
        save_data()
        await update.message.reply_text("Теперь отправь медиа (или нажми 'Пропустить')")
        return

    if st["state"] == "await_post_media":
        if update.message.photo:
            st["post"]["media"] = update.message.photo[-1].file_id
        st["state"] = "await_button_type"
        save_data()
        kb = [
            [InlineKeyboardButton("Добавить реакции", callback_data="btn_react")],
            [InlineKeyboardButton("Добавить ссылку", callback_data="btn_link")],
            [InlineKeyboardButton("Пропустить", callback_data="skip_buttons")]
        ]
        await update.message.reply_text("Добавим кнопки?", reply_markup=InlineKeyboardMarkup(kb))
        return

    if st["state"] == "post_react_1":
        em1 = update.message.text.strip()
        st["reactions"]["r1"] = em1
        st["state"] = "post_react_2"
        save_data()
        await update.message.reply_text("Теперь второе эмоджи")
        return

    if st["state"] == "post_react_2":
        em2 = update.message.text.strip()
        st["reactions"]["r2"] = em2
        st["state"] = "confirm"
        save_data()
        kb = [
            [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
            [InlineKeyboardButton("📨 Отправить", callback_data="send")],
            [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
        ]
        await update.message.reply_text("Реакции добавлены.", reply_markup=InlineKeyboardMarkup(kb))
        return

    if st["state"] == "post_link":
        try:
            text, url = update.message.text.split(",")
            st["post"]["link"] = {"text": text.strip(), "url": url.strip()}
            st["state"] = "confirm"
            save_data()
            kb = [
                [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить", callback_data="send")],
                [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
            ]
            await update.message.reply_text("Ссылка добавлена.", reply_markup=InlineKeyboardMarkup(kb))
        except ValueError:
            await update.message.reply_text("Формат неверный. Пример: Подробнее, https://example.com")
        return

# ========== Инициализация ==========

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    app.run_polling()
