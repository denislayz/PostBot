import os
import json
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
import asyncio

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://postbot-production.up.railway.app/webhook"

# Файл с состоянием
DATA_FILE = "data.json"

# Загрузка состояния
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}

def save_data(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f)

def get_user_state(user_id):
    if str(user_id) not in data:
        data[str(user_id)] = {"state": "idle"}
    return data[str(user_id)]

def reset_user_state(user_id):
    data[str(user_id)] = {"state": "idle"}
    save_data(data)

# Обработчик /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    groups = state.get("groups", {})
    if not groups:
        keyboard = [[InlineKeyboardButton("Добавить группу", callback_data="add_group")]]
    else:
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"group:{gid}")]
            for gid, name in groups.items()
        ]
        keyboard.append([InlineKeyboardButton("Добавить группу", callback_data="add_group")])

    await update.message.reply_text(
        "Выберите группу для работы с постами или добавьте новую:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Обработка inline кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    state = get_user_state(user_id)

    if query.data == "add_group":
        state["state"] = "waiting_for_group_mention"
        save_data(data)
        await query.edit_message_text("Пожалуйста, упомяните меня в группе, чтобы я получил её ID.")
        return

    if query.data.startswith("group:"):
        gid = query.data.split(":")[1]
        state["selected_group"] = gid
        state["state"] = "group_menu"
        save_data(data)
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Сделать пост", callback_data="make_post")],
                [InlineKeyboardButton("Добавить тему", callback_data="add_topic")],
                [InlineKeyboardButton("Удалить группу", callback_data="remove_group")],
                [InlineKeyboardButton("Назад", callback_data="back_to_groups")]
            ])
        )

    elif query.data == "make_post":
        state["state"] = "post_title"
        state["post"] = {}
        save_data(data)
        await query.edit_message_text("Введите заголовок поста (или отправьте '-' чтобы пропустить):")

    elif query.data == "add_topic":
        state["state"] = "add_topic"
        save_data(data)
        await query.edit_message_text("Введите название темы и её thread_id через пробел:")

    elif query.data == "remove_group":
        group_id = state.get("selected_group")
        if group_id:
            state["groups"].pop(group_id, None)
        reset_user_state(user_id)
        save_data(data)
        await query.edit_message_text("Группа удалена.")
        await start(update, context)

    elif query.data == "back_to_groups":
        reset_user_state(user_id)
        await start(update, context)

    elif query.data == "preview_post":
        post = state.get("post", {})
        media = post.get("media")
        buttons = post.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None

        if media:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=media, caption=f"*{post.get('title', '')}*\n{post.get('text', '')}", parse_mode='Markdown', reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"*{post.get('title', '')}*\n{post.get('text', '')}", parse_mode='Markdown', reply_markup=markup)

    elif query.data == "send_post":
        group_id = state.get("selected_group")
        post = state.get("post", {})
        thread_id = post.get("thread_id")

        kwargs = {"chat_id": group_id}
        if thread_id:
            kwargs["message_thread_id"] = thread_id

        buttons = post.get("buttons", [])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons]) if buttons else None

        if post.get("media"):
            await context.bot.send_photo(caption=f"*{post.get('title', '')}*\n{post.get('text', '')}", photo=post["media"], parse_mode='Markdown', reply_markup=markup, **kwargs)
        else:
            await context.bot.send_message(text=f"*{post.get('title', '')}*\n{post.get('text', '')}", parse_mode='Markdown', reply_markup=markup, **kwargs)

        await query.edit_message_text("Пост отправлен!")
        reset_user_state(user_id)

# Обработка сообщений
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    state = get_user_state(user_id)
    text = update.message.text
    photo = update.message.photo[-1].file_id if update.message.photo else None

    if state["state"] == "waiting_for_group_mention":
        if update.message.chat.type in ["group", "supergroup"]:
            group_id = str(update.message.chat.id)
            group_name = update.message.chat.title
            state.setdefault("groups", {})[group_id] = group_name
            save_data(data)
            await update.message.reply_text(f"Группа '{group_name}' добавлена.")
        return

    if state["state"] == "post_title":
        if text != "-":
            state["post"]["title"] = text
        state["state"] = "post_text"
        save_data(data)
        await update.message.reply_text("Введите основной текст поста (или '-' чтобы пропустить):")
        return

    if state["state"] == "post_text":
        if text != "-":
            state["post"]["text"] = text
        state["state"] = "post_media"
        save_data(data)
        await update.message.reply_text("Отправьте изображение (или '-' чтобы пропустить):")
        return

    if state["state"] == "post_media":
        if photo:
            state["post"]["media"] = photo
        state["state"] = "post_buttons"
        save_data(data)
        await update.message.reply_text("Введите кнопки (текст и ссылка через |, одна на строку), или '-' чтобы пропустить:")
        return

    if state["state"] == "post_buttons":
        if text != "-":
            buttons = []
            for line in text.strip().splitlines():
                if "|" in line:
                    btext, url = line.split("|", 1)
                    buttons.append({"text": btext.strip(), "url": url.strip()})
            state["post"]["buttons"] = buttons
        state["state"] = "confirm_post"
        save_data(data)
        await update.message.reply_text(
            "Предпросмотр поста:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Предпросмотр", callback_data="preview_post")],
                [InlineKeyboardButton("Отправить", callback_data="send_post")],
                [InlineKeyboardButton("Отменить", callback_data="back_to_groups")]
            ])
        )
        return

    if state["state"] == "add_topic":
        try:
            name, thread_id = text.rsplit(" ", 1)
            state.setdefault("topics", {})[name] = int(thread_id)
            save_data(data)
            await update.message.reply_text(f"Тема '{name}' добавлена.")
            reset_user_state(user_id)
        except:
            await update.message.reply_text("Ошибка. Введите название и thread_id через пробел.")
        return

# Запуск бота
async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))

    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook установлен: {WEBHOOK_URL}")

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    import asyncio
    asyncio.get_event_loop().run_until_complete(main())

