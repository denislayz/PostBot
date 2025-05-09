import os
import json
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity
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
            "button_type": None
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
        "button_type": None
    }

# ========== Хендлеры ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    data[uid] = reset_state_but_keep(uid)
    save_data()

    text = "Добро пожаловать! Отправьте сообщение в группу, где упомянете бота. Он запомнит её."
    kb = [[InlineKeyboardButton("🏠 Начать", callback_data="restart")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    st = get_user_state(uid)

    if query.data == "restart":
        data[uid] = reset_state_but_keep(uid)
        save_data()
        text = "Добро пожаловать! Отправьте сообщение в группу, где упомянете бота. Он запомнит её."
        kb = [[InlineKeyboardButton("🏠 Начать", callback_data="restart")]]
        return await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user = msg.from_user
    uid = str(user.id)
    st = get_user_state(uid)

    # ========== Обработка сообщения из группы с упоминанием бота ==========
    if msg.chat.type in ["group", "supergroup"] and msg.entities:
        for ent in msg.entities:
            if ent.type == MessageEntity.MENTION:
                mention = msg.text[ent.offset:ent.offset + ent.length]
                if mention == f"@{context.bot.username}":
                    st["groups"][str(msg.chat.id)] = msg.chat.title or msg.chat.username or str(msg.chat.id)
                    st["selected_group"] = str(msg.chat.id)
                    st["state"] = "awaiting_topic"
                    save_data()

                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"Ты выбрал(а) группу {st['groups'][st['selected_group']]}. Теперь укажи тему в формате: Название, ID"
                    )
                    return

    # ========== Ввод темы вручную ==========
    if st["state"] == "awaiting_topic":
        try:
            name, tid = msg.text.split(",")
            tid = int(tid.strip())
            name = name.strip()
        except:
            return await msg.reply_text("Формат неверен. Используй: Название, ID")

        st["topics"][str(tid)] = name
        st["selected_topic"] = str(tid)
        st["state"] = "awaiting_text"
        save_data()

        return await msg.reply_text(f"Ты выбрал(а) тему {name}. Теперь введи текст поста")

    # ========== Остальная логика (пост, медиа и т.д.) ==========
    if st["state"] == "awaiting_text":
        st["post"]["text"] = msg.text
        st["state"] = "awaiting_media"
        save_data()
        kb = [[InlineKeyboardButton("Пропустить", callback_data="skip_media")]]
        return await msg.reply_text("Теперь отправь фото/видео или нажми 'Пропустить'", reply_markup=InlineKeyboardMarkup(kb))

    if st["state"] == "awaiting_media":
        if msg.photo:
            st["post"]["media"] = {"type": "photo", "file_id": msg.photo[-1].file_id}
        elif msg.video:
            st["post"]["media"] = {"type": "video", "file_id": msg.video.file_id}
        else:
            return await msg.reply_text("Это не фото или видео. Попробуйте снова.")
        st["state"] = "awaiting_buttons"
        save_data()
        return await msg.reply_text("Добавить кнопки?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Реакции", callback_data="btn_react"), InlineKeyboardButton("Ссылки", callback_data="btn_link")],
            [InlineKeyboardButton("Пропустить", callback_data="skip_buttons")]
        ]))

# ========== Инициализация ==========
if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    app.run_polling()
