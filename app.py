import os
import json
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
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
            "reaction_clicks": {}
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
        "reaction_clicks": {}
    }

# ========== Хендлеры ========== 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data[str(uid)] = reset_state_but_keep(uid)
    save_data()
    kb = [[InlineKeyboardButton("➕ Добавить группу", switch_inline_query="add_group")]]
    await update.message.reply_text(
        "Выберите группу для публикации:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    st = get_user_state(uid)

    if query.data == "restart":
        data[str(uid)] = reset_state_but_keep(uid)
        save_data()
        return await query.edit_message_text("🔄 Перезапуск...", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ Добавить группу", switch_inline_query="add_group")]]
        ))

    if query.data == "choose_group":
        st["state"] = "choose_group"
        save_data()
        return await query.edit_message_text("Выберите группу:")

    if query.data == "skip_caption":
        st["post"]["caption"] = ""
        st["state"] = "choose_buttons"
        save_data()
        return await query.edit_message_text("Выберите тип кнопок:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😊 Реакции", callback_data="btn_react")],
                [InlineKeyboardButton("🔗 Ссылки", callback_data="btn_link")],
                [InlineKeyboardButton("Пропустить", callback_data="skip_buttons")]
            ])
        )

    if query.data == "btn_react":
        st["state"] = "post_react_1"
        save_data()
        return await query.edit_message_text("Введите эмоджи для первой реакции:")

    if query.data == "skip_buttons":
        st["state"] = "confirm"
        save_data()
        return await query.edit_message_text("Кнопки пропущены. Готово к публикации.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить", callback_data="send")],
                [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
            ])
        )

    if query.data == "btn_link":
        st["state"] = "add_link_text"
        save_data()
        return await query.edit_message_text("Введите текст кнопки:")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return  # Игнорировать сообщения не в ЛС

    uid = update.effective_user.id
    st = get_user_state(uid)

    if st["state"] == "choose_group":
        st["selected_group"] = update.message.text.strip()
        st["state"] = "choose_topic"
        save_data()
        return await update.message.reply_text(f"Ты выбрал(а) группу: {st['selected_group']}\nТеперь укажи тему (в формате: Название,ID)")

    if st["state"] == "choose_topic":
        try:
            title, tid = update.message.text.split(",", 1)
            tid = int(tid.strip())
            st["selected_topic"] = {"title": title.strip(), "id": tid}
            st["state"] = "add_media"
            save_data()
            return await update.message.reply_text(f"Ты выбрал(а) тему: {title.strip()}\nТеперь отправь фото или видео:")
        except Exception:
            return await update.message.reply_text("Ошибка формата. Введите в виде: Название,ID")

    if st["state"] == "add_media":
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            st["post"]["media"] = {"type": "photo", "file_id": file_id}
        elif update.message.video:
            file_id = update.message.video.file_id
            st["post"]["media"] = {"type": "video", "file_id": file_id}
        else:
            return await update.message.reply_text("Отправьте фото или видео.")
        st["state"] = "add_caption"
        save_data()
        kb = [[InlineKeyboardButton("Пропустить", callback_data="skip_caption")]]
        return await update.message.reply_text("Теперь добавьте подпись к посту:", reply_markup=InlineKeyboardMarkup(kb))

    if st["state"] == "add_caption":
        st["post"]["caption"] = update.message.text
        st["state"] = "choose_buttons"
        save_data()
        return await update.message.reply_text("Выберите тип кнопок:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😊 Реакции", callback_data="btn_react")],
                [InlineKeyboardButton("🔗 Ссылки", callback_data="btn_link")],
                [InlineKeyboardButton("Пропустить", callback_data="skip_buttons")]
            ])
        )

    if st["state"] == "post_react_1":
        st["reactions"]["r1"] = update.message.text.strip()
        st["state"] = "post_react_2"
        save_data()
        return await update.message.reply_text("Введите эмоджи для второй реакции:")

    if st["state"] == "post_react_2":
        st["reactions"]["r2"] = update.message.text.strip()
        st["state"] = "confirm"
        save_data()
        return await update.message.reply_text("Реакции добавлены. Выберите действие:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить", callback_data="send")],
                [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
            ])
        )

    if st["state"] == "add_link_text":
        st["post"]["btn_text"] = update.message.text
        st["state"] = "add_link_url"
        save_data()
        return await update.message.reply_text("Теперь введите URL кнопки:")

    if st["state"] == "add_link_url":
        st["post"]["btn_url"] = update.message.text
        st["state"] = "confirm"
        save_data()
        return await update.message.reply_text("Ссылка добавлена. Выберите действие:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить", callback_data="send")],
                [InlineKeyboardButton("🏠 Начать", callback_data="restart")]
            ])
        )

# ========== Инициализация ==========
if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    app.run_polling()
