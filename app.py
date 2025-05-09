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
        {"state": "idle", "groups": {}, "topics": {}, "post": {}}
    )

def reset_state_but_keep(uid):
    prev = data.get(str(uid), {})
    return {
        "state": "idle",
        "groups": prev.get("groups", {}),
        "topics": prev.get("topics", {}),
        "post": {}
    }

# ========== Хендлеры ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_user_state(uid)
    keyboard = [[InlineKeyboardButton("➕ Добавить группу", callback_data="add_group")]]
    for gid, title in st["groups"].items():
        keyboard.append([InlineKeyboardButton(title, callback_data=f"group:{gid}")])
    await update.message.reply_text(
        "Выберите группу или добавьте новую:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    st = get_user_state(uid)

    # 1) Начало добавления группы
    if query.data == "add_group":
        st["state"] = "waiting_for_mention"
        save_data()
        return await query.edit_message_text(
            "Отметьте меня (@), чтобы я запомнил этот чат как группу."
        )

    # 2) Пользователь нажал кнопку группы → подтягиваем темы из стейта
    if query.data.startswith("group:"):
        gid = int(query.data.split(":",1)[1])
        st = data[str(uid)] = reset_state_but_keep(uid)
        st["groups"][str(gid)] = st["groups"].get(str(gid), "")
        st["selected_group"] = gid
        # Строим кнопки тем из st["topics"]
        keyboard = []
        for tid, name in st["topics"].items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"topic:{tid}")])
        # Добавляем кнопку «Добавить тему» и «Назад»
        keyboard.append([InlineKeyboardButton("🗂 Добавить тему", callback_data="add_topic")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
        save_data()
        return await query.edit_message_text(
            "Выберите тему для поста или добавьте новую:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 3) Добавление темы вручную (по названию и ID)
    if query.data == "add_topic":
        st["state"] = "waiting_for_topic_entry"
        save_data()
        return await query.edit_message_text(
            "Введите название темы и её thread_id через запятую.\n\n"
            "Пример:\n"
            "`Красота и Стиль, 1234567890`",
            parse_mode="Markdown"
        )

    # 4) Выбор темы для создания поста
    if query.data.startswith("topic:"):
        thread_id = query.data.split(":",1)[1]
        st["selected_topic"] = thread_id
        st["state"] = "post_title"
        save_data()
        return await query.edit_message_text(
            "Введите заголовок (или «-» чтобы пропустить):"
        )

    # 5) Назад в меню групп
    if query.data == "back":
        data[str(uid)] = reset_state_but_keep(uid)
        save_data()
        return await start(update, context)

    # 6) Предпросмотр
    if query.data == "preview":
        p = st.get("post", {})
        text = f"*{p.get('title','')}*\n{p.get('text','')}"
        buttons = p.get("buttons", [])
        markup = (
            InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"]) for b in buttons]])
            if buttons else None
        )
        if p.get("media"):
            return await context.bot.send_photo(
                chat_id=uid,
                photo=p["media"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        return await context.bot.send_message(
            chat_id=uid,
            text=text,
            parse_mode="Markdown",
            reply_markup=markup
        )

    # 7) Отправка в выбранную тему
    if query.data == "send":
        p = st.get("post", {})
        gid = st["selected_group"]
        tid = int(st["selected_topic"])
        text = f"*{p.get('title','')}*\n{p.get('text','')}"
        buttons = p.get("buttons", [])
        markup = (
            InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"]) for b in buttons]])
            if buttons else None
        )
        if p.get("media"):
            await context.bot.send_photo(
                chat_id=gid,
                photo=p["media"],
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup,
                message_thread_id=tid
            )
        else:
            await context.bot.send_message(
                chat_id=gid,
                text=text,
                parse_mode="Markdown",
                reply_markup=markup,
                message_thread_id=tid
            )
        await query.edit_message_text("✅ Пост отправлен!")
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

    # Ожидание ввода темы вручную
    if st["state"] == "waiting_for_topic_entry":
        text = update.message.text or ""
        if "," in text:
            name, tid = text.split(",",1)
            name = name.strip()
            tid = tid.strip()
            if tid.isdigit():
                st["topics"][tid] = name
                st["state"] = "idle"
                save_data()
                await update.message.reply_text(f"✅ Тема «{name}» ({tid}) добавлена!")
                # сразу показать меню тем
                return await button_handler(
                    update=Update(
                        update.update_id,
                        callback_query=update.callback_query or None
                    ),  # хитрый коллбек чтобы вызвать button_handler с data="group:<gid>"
                    context=context
                )
        # если неверный формат
        return await update.message.reply_text(
            "Неверный формат. Введите через запятую:\n"
            "Название темы, thread_id"
        )

    # ========== Создание поста ==========
    # Заголовок
    if st["state"] == "post_title":
        txt = update.message.text or ""
        if txt != "-":
            st.setdefault("post", {})["title"] = txt
        st["state"] = "post_text"
        save_data()
        return await update.message.reply_text("Введите основной текст (или «-»):")

    # Текст
    if st["state"] == "post_text":
        txt = update.message.text or ""
        if txt != "-":
            st["post"]["text"] = txt
        st["state"] = "post_media"
        save_data()
        return await update.message.reply_text("Прикрепите фото (или отправьте «-»):")

    # Медиа
    if st["state"] == "post_media":
        if update.message.photo:
            st["post"]["media"] = update.message.photo[-1].file_id
        st["state"] = "post_buttons"
        save_data()
        return await update.message.reply_text("Введите кнопки (текст|URL по строкам) или «-»:")

    # Кнопки
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
            "Выберите действие:",
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
