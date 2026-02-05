import os
import json
from flask import Flask, request
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

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
# Keyboards
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

    context.user_data.clear()
    await update.message.reply_text("پنل مدیریت:", reply_markup=admin_menu_keyboard())

# ---------------------------
# HANDLER
# ---------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id != ADMIN_ID:
        await update.message.reply_text("دسترسی ندارید.")
        return

    # بررسی وضعیت فعلی
    state = context.user_data.get("state")

    if state == "adding_slogan_text":
        context.user_data["new_slogan"] = text
        context.user_data["state"] = "adding_slogan_score"
        await update.message.reply_text("امتیاز شعار را بفرست:", reply_markup=back_button_keyboard())
        return

    if state == "adding_slogan_score":
        try:
            score = int(text)
            data["slogans"][context.user_data["new_slogan"]] = score
            save_data(data)
            await update.message.reply_text("شعار ذخیره شد ✅", reply_markup=admin_menu_keyboard())
            context.user_data.clear()
        except:
            await update.message.reply_text("عدد نامعتبره.", reply_markup=back_button_keyboard())
        return

    if state == "removing_slogan":
        if text in data["slogans"]:
            del data["slogans"][text]
            save_data(data)
            await update.message.reply_text("حذف شد.", reply_markup=admin_menu_keyboard())
        else:
            await update.message.reply_text("پیدا نشد.", reply_markup=admin_menu_keyboard())
        context.user_data.clear()
        return

    # دکمه‌ها
    if text == "➕ افزودن شعار":
        context.user_data["state"] = "adding_slogan_text"
        await update.message.reply_text("متن شعار را بفرست:", reply_markup=back_button_keyboard())
        return

    if text == "❌ حذف شعار":
        context.user_data["state"] = "removing_slogan"
        await update.message.reply_text("متن شعار جهت حذف:", reply_markup=back_button_keyboard())
        return

    if text == "📄 لیست شعارها":
        if not data["slogans"]:
            await update.message.reply_text("شعاری ثبت نشده.", reply_markup=admin_menu_keyboard())
            return
        msg = "📄 لیست شعارها:\n\n"
        for s, sc in data["slogans"].items():
            msg += f"• {s} → {sc}\n"
        await update.message.reply_text(msg, reply_markup=admin_menu_keyboard())
        return

    if text == "🔙 بازگشت":
        context.user_data.clear()
        await update.message.reply_text("بازگشت به پنل", reply_markup=admin_menu_keyboard())
        return

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

    sorted_users = sorted(data["users"].items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 لیدربورد برترین‌ها:\n\n"
    for idx, (uid, score) in enumerate(sorted_users, start=1):
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, int(uid))
            name = member.user.first_name
        except:
            name = f"User {uid}"
        msg += f"{idx}. {name} — {score} امتیاز\n"
    await update.message.reply_text(msg)

# ---------------------------
# GROUP MESSAGE CHECK
# ---------------------------
async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    uid = str(user.id)

    for slogan, score in data["slogans"].items():
        if slogan in text:
            data["users"][uid] = data["users"].get(uid, 0) + score
            save_data(data)
            await update.message.reply_text(
                f"🎉 تبریک {user.first_name}!\nامتیاز دریافت‌شده: {score}\nجمع امتیاز شما: {data['users'][uid]}"
            )
            break

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
    loop.run_in_executor(None, lambda: asyncio.run(application.process_update(update)))
    return "OK", 200

# ---------------------------
# INIT BOT
# ---------------------------
application = Application.builder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("total_point", total_point))
application.add_handler(CommandHandler("leader_board", leader_board))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, check_messages))

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    async def setup():
        await application.initialize()
        await application.start()
        await application.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")

    loop.run_until_complete(setup())

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
