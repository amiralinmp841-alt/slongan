import os
import json
from flask import Flask, request
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes,
    filters, ConversationHandler
)
import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ---------------------------
# ENV
# ---------------------------
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ---------------------------
# Load / Save storage
# ---------------------------
def load_data():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"slogans": {}, "users": {}}

def save_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ---------------------------
# States
# ---------------------------
ADD_SLOGAN_TEXT, ADD_SLOGAN_SCORE, REMOVE_SLOGAN = range(3)

# ---------------------------
# Keyboard
# ---------------------------
def admin_menu_keyboard():
    keyboard = [
        [KeyboardButton("➕ افزودن شعار"), KeyboardButton("❌ حذف شعار")],
        [KeyboardButton("📄 لیست شعارها"), KeyboardButton("🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_button_keyboard():
    keyboard = [[KeyboardButton("🔙 بازگشت")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------------------------
# START
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("سلام! ربات فعاله 👋")
        return

    await update.message.reply_text(
        "پنل مدیریت:",
        reply_markup=admin_menu_keyboard()
    )

# ---------------------------
# BUTTON HANDLER
# ---------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("دسترسی ندارید.")
        return ConversationHandler.END

    if text == "➕ افزودن شعار":
        await update.message.reply_text("متن شعار را بفرست:", reply_markup=back_button_keyboard())
        return ADD_SLOGAN_TEXT

    if text == "❌ حذف شعار":
        await update.message.reply_text("متن شعار جهت حذف:", reply_markup=back_button_keyboard())
        return REMOVE_SLOGAN

    if text == "📄 لیست شعارها":
        if not data["slogans"]:
            await update.message.reply_text("شعاری ثبت نشده.", reply_markup=admin_menu_keyboard())
            return ConversationHandler.END

        msg = "📄 لیست شعارها:\n\n"
        for s, sc in data["slogans"].items():
            msg += f"• {s} → {sc}\n"

        await update.message.reply_text(msg, reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    if text == "🔙 بازگشت":
        await update.message.reply_text("بازگشت به پنل", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

# ---------------------------
# ADD SLOGAN
# ---------------------------
async def add_slogan_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["slogan"] = update.message.text
    await update.message.reply_text("امتیاز شعار را بفرست:", reply_markup=back_button_keyboard())
    return ADD_SLOGAN_SCORE

async def add_slogan_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        score = int(update.message.text)
    except:
        await update.message.reply_text("عدد نامعتبره.", reply_markup=back_button_keyboard())
        return ADD_SLOGAN_SCORE

    data["slogans"][context.user_data["slogan"]] = score
    save_data(data)

    await update.message.reply_text("شعار ذخیره شد ✅", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END

# ---------------------------
# REMOVE
# ---------------------------
async def remove_slogan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slogan = update.message.text
    if slogan in data["slogans"]:
        del data["slogans"][slogan]
        save_data(data)
        await update.message.reply_text("حذف شد.", reply_markup=admin_menu_keyboard())
    else:
        await update.message.reply_text("پیدا نشد.", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END

# ---------------------------
# GROUP MESSAGE CHECK
# ---------------------------
async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id = str(user.id)

    for slogan, score in data["slogans"].items():
        if slogan in text:
            data["users"][user_id] = data["users"].get(user_id, 0) + score
            save_data(data)

            await update.message.reply_text(
                f"🎉 تبریک {user.first_name}!\n"
                f"امتیاز دریافت‌شده: {score}\n"
                f"جمع امتیاز شما: {data['users'][user_id]}"
            )
            break

# ---------------------------
# TOTAL POINT
# ---------------------------
async def total_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    total = data["users"].get(user_id, 0)
    await update.message.reply_text(f"📊 جمع امتیاز شما: {total}")

# ---------------------------
# LEADER BOARD
# ---------------------------
async def leader_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["users"]:
        await update.message.reply_text("هنوز امتیازی ثبت نشده.")
        return

    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    msg = "🏆 لیدربورد برترین‌ها:\n\n"

    for idx, (user_id, score) in enumerate(sorted_users, start=1):
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, int(user_id))
            name = member.user.first_name
        except:
            name = f"User {user_id}"

        msg += f"{idx}. {name} — {score} امتیاز\n"

    await update.message.reply_text(msg)

# ---------------------------
# FLASK APP
# ---------------------------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    data_json = request.get_json(force=True)
    update = Update.de_json(data_json, application.bot)
    
    # مستقیم با loop.run_in_executor اجرا کن
    loop.run_in_executor(None, lambda: asyncio.run(application.process_update(update)))
    
    return "OK", 200

# ---------------------------
# INIT BOT
# ---------------------------
application = Application.builder().token(TOKEN).build()

conv = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler)],
    states={
        ADD_SLOGAN_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_slogan_text)],
        ADD_SLOGAN_SCORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_slogan_score)],
        REMOVE_SLOGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_slogan)],
    },
    fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler)],
    per_message=True
)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("total_point", total_point))
application.add_handler(CommandHandler("leader_board", leader_board))
application.add_handler(conv)
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_messages))

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    async def setup():
        await application.initialize()
        await application.start()
        await application.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")

    loop.run_until_complete(setup())

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
