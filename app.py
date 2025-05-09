import os
import json
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
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
            "reactions": {}
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
        "reactions": {}
    }

# ========== Хендлеры ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Кнопка "начать" всегда доступна
    keyboard = [[InlineKeyboardButton("🏠 Начать", callback_data="restart")]]
    uid = None
    if update.message:
        uid = update.effective_user.id
        send = update.message.reply_text
    else:
        uid = update.callback_query.from_user.id
        def send(text, **kwargs):
            return context.bot.send_message(chat_id=uid, text=text, **kwargs)

    st = get_user_state(uid)
    # Рисуем группы ниже
    keyboard.append([InlineKeyboardButton("➕ Добавить группу", callback_data="add_group")])
    for gid, title in st["groups"].items():
        keyboard.append([InlineKeyboardButton(title, callback_data=f"group:{gid}")])

    await send(
        "Выберите группу или добавьте новую:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    st = get_user_state(uid)

    # Общий restart
    if query.data == "restart":
        data[str(uid)] = reset_state_but_keep(uid)
        save_data()
        return await start(update, context)

    # Добавить группу
    if query.data == "add_group":
        st["state"] = "waiting_for_mention"
        save_data()
        return await query.edit_message_text(
            "Отметьте меня (@) в группе для подключения."
        )

    # Выбор группы
    if query.data.startswith("group:"):
        gid = int(query.data.split("<",1)[0].split(":")[1])
        group_name = st["groups"].get(str(gid), "группа")
        st = data[str(uid)] = reset_state_but_keep(uid)
        st["groups"][str(gid)] = group_name
        st["selected_group"] = gid
        save_data()
        # Сообщение подтверждения
        await query.edit_message_text(f"Ты выбрал(а) группу {group_name}")
        # Отрисовать темы
        keyboard = [[InlineKeyboardButton("🏠 Начать", callback_data="restart")]]
        keyboard.append([InlineKeyboardButton("🗂 Добавить тему", callback_data="add_topic")])
        for tid, name in st["topics"].items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"topic:{tid}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="restart")])
        return await context.bot.send_message(
            chat_id=uid,
            text="Выберите тему:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Добавить тему вручную
    if query.data == "add_topic":
        st["state"] = "waiting_for_topic_entry"
        save_data()
        return await query.edit_message_text(
            "Введите тему и thread_id через запятую, например: Красота, 123456"
        )

    # Выбор темы
    if query.data.startswith("topic:"):
        tid = query.data.split(":")[1]
        topic_name = st["topics"].get(tid)
        st["selected_topic"] = tid
        st["state"] = "post_title"
        save_data()
        return await query.edit_message_text(f"Ты выбрал(а) тему {topic_name}\nВведите заголовок:")

    # Пропустить
    if query.data == "skip":
        # логика пропуска похожа на ввод '-', просто устанавливаем и движемся дальше
        cur = st["state"]
        st["post"][cur.split("_")[1]] = None
        # смена состояния
        if cur == "post_title": st["state"] = "post_text"
        elif cur == "post_text": st["state"] = "post_media"
        elif cur == "post_media": st["state"] = "post_buttons"
        save_data()
        return await context.bot.send_message(chat_id=uid, text="Шаг пропущен. Продолжайте.")

    # Предпросмотр и отправка, реакции / ссылки выбираем по состоянию
    if query.data == "choose_buttons":
        st["state"] = "choose_button_type"
        save_data()
        kb = [[InlineKeyboardButton("👍 Реакции", callback_data="btn_react")],
              [InlineKeyboardButton("🔗 Ссылки", callback_data="btn_link")],
              [InlineKeyboardButton("❌ Пропустить", callback_data="skip")]]
        return await query.edit_message_text(
            "Выберите тип кнопок:", reply_markup=InlineKeyboardMarkup(kb)
        )
    # Далее полноценный код обработки реакций и ссылок...

# Аналогично доработать message_handler, добавив inline skip кнопку на каждый шаг, генерацию кнопки меню

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    app.run_polling()
