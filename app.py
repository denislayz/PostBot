import os
import json
import logging
import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ForumTopic
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
    raise ValueError("Переменная окружения TELEGRAM_TOKEN не установлена!")

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
    return data.setdefault(str(uid), {"state": "idle", "groups": {}, "topics": {}})

def reset_state_but_keep(uid):
    prev = data.get(str(uid), {})
    return {"state": "idle", "groups": prev.get("groups", {}), "topics": {}}

# ========== Функция для получения тем форума через HTTP-запрос ==========
def fetch_forum_topics_sync(chat_id: int):
    url = f"https://api.telegram.org/bot{TOKEN}/getForumTopics"
    resp = requests.get(url, params={"chat_id": chat_id})
    resp.raise_for_status()
    result = resp.json().get("result", [])
    # Преобразуем в объекты ForumTopic
    topics = []
    for t in result:
        try:
            topics.append(ForumTopic(**t))
        except TypeError:
            # Если какие-то поля отличаются, берем как минимум id и name
            topics.append(ForumTopic(message_thread_id=t["message_thread_id"], name=t["name"], icon_color=0, icon_custom_emoji_id=None))
    return topics

# ========== Хендлеры ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_user_state(uid)
    kbd = [[InlineKeyboardButton("➕ Добавить группу", callback_data="add_group")]]
    for gid, title in st["groups"].items():
        kbd.append([InlineKeyboardButton(title, callback_data=f"group:{gid}")])
    await update.message.reply_text(
        "Выберите группу или добавьте новую:",
        reply_markup=InlineKeyboardMarkup(kbd)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    st = get_user_state(uid)

    # 1) Начало: добавить группу
    if query.data == "add_group":
        st["state"] = "waiting_for_mention"
        save_data()
        return await query.edit_message_text("Отметьте меня (@), я запомню этот чат как группу.")

    # 2) Пользователь выбрал группу — подтягиваем темы
    if query.data.startswith("group:"):
        gid = int(query.data.split(":",1)[1])
        st = data[str(uid)] = reset_state_but_keep(uid)
        st["groups"][str(gid)] = st["groups"].get(str(gid), "")
        st["selected_group"] = gid

        # Получаем темы через синхронный HTTP
        try:
            topics = fetch_forum_topics_sync(gid)
        except Exception as e:
            logger.error("Не удалось получить темы: %s", e)
            return await query.edit_message_text("❌ Ошибка при получении тем. Убедитесь, что группа — форум.")

        st_topics = {}
        kbd = []
        for t in topics:
            st_topics[str(t.message_thread_id)] = t.name
            kbd.append([InlineKeyboardButton(t.name, callback_data=f"topic:{t.message_thread_id}")])
        st["topics"] = st_topics
        save_data()

        kbd.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
        return await query.edit_message_text(
            "Выберите тему для поста:",
            reply_markup=InlineKeyboardMarkup(kbd)
        )

    # 3) Выбор темы
    if query.data.startswith("topic:"):
        thread_id = int(query.data.split(":",1)[1])
        st["selected_topic"] = thread_id
        st["state"] = "post_title"
        save_data()
        return await query.edit_message_text("Введите заголовок (или «-» чтобы пропустить):")

    # 4) Назад к меню групп
    if query.data == "back":
        data[str(uid)] = reset_state_but_keep(uid)
        save_data()
        return await start(update, context)

    # 5) Предпросмотр
    if query.data == "preview":
        p = st.get("post", {})
        text = f"*{p.get('title','')}*\n{p.get('text','')}"
        buttons = p.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None
        if p.get("media"):
            return await context.bot.send_photo(
                chat_id=uid, photo=p["media"], caption=text,
                parse_mode="Markdown", reply_markup=markup
            )
        return await context.bot.send_message(
            chat_id=uid, text=text,
            parse_mode="Markdown", reply_markup=markup
        )

    # 6) Отправка поста в тему
    if query.data == "send":
        p = st.get("post", {})
        gid = st["selected_group"]
        tid = st["selected_topic"]
        text = f"*{p.get('title','')}*\n{p.get('text','')}"
        buttons = p.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None
        if p.get("media"):
            await context.bot.send_photo(
                chat_id=gid, photo=p["media"], caption=text,
                parse_mode="Markdown", reply_markup=markup,
                message_thread_id=tid
            )
        else:
            await context.bot.send_message(
                chat_id=gid, text=text,
                parse_mode="Markdown", reply_markup=markup,
                message_thread_id=tid
            )
        await query.edit_message_text("✅ Пост отправлен в тему!")
        data[str(uid)] = reset_state_but_keep(uid)
        save_data()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_user_state(uid)

    # Привязка группы по упоминанию
    if st["state"] == "waiting_for_mention" and update.message.chat.type in ["group","supergroup"]:
        chat = update.effective_chat
        st["groups"][str(chat.id)] = chat.title or "Группа"
        st["state"] = "idle"
        save_data()
        await update.message.reply_text(f"✅ Группа «{chat.title}» добавлена.")
        return await start(update, context)

    # Шаги создания поста
    if st["state"] == "post_title":
        txt = update.message.text or ""
        if txt != "-":
            st.setdefault("post", {})["title"] = txt
        st["state"] = "post_text"
        save_data()
        return await update.message.reply_text("Введите текст (или «-»):")

    if st["state"] == "post_text":
        txt = update.message.text or ""
        if txt != "-":
            st["post"]["text"] = txt
        st["state"] = "post_media"
        save_data()
        return await update.message.reply_text("Прикрепите фото или «-»:")

    if st["state"] == "post_media":
        if update.message.photo:
            st["post"]["media"] = update.message.photo[-1].file_id
        st["state"] = "post_buttons"
        save_data()
        return await update.message.reply_text("Введите кнопки (текст|URL в строке) или «-»:")

    if st["state"] == "post_buttons":
        txt = update.message.text or ""
        if txt != "-":
            btns = []
            for line in txt.splitlines():
                if "|" in line:
                    t,u = line.split("|",1)
                    btns.append({"text":t.strip(),"url":u.strip()})
            st["post"]["buttons"] = btns
        st["state"] = "confirm"
        save_data()
        return await update.message.reply_text(
            "Готово: предпросмотр или отправить?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Предпросмотр", callback_data="preview")],
                [InlineKeyboardButton("📨 Отправить", callback_data="send")],
                [InlineKeyboardButton("❌ Отмена", callback_data="back")]
            ])
        )

# ========== Запуск ==========
if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, message_handler))
    application.run_polling(poll_interval=3.0)
