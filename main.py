import os
import json
import asyncio
from flask import Flask, request
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# -------------------------------------------------
# Async loop (FIXED)
# -------------------------------------------------
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# -------------------------------------------------
# Persian digit converter
# -------------------------------------------------
def normalize_digits(text: str) -> str:
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    english = "0123456789"

    table = str.maketrans(
        persian + arabic,
        english + english
    )
    return text.translate(table)


# -------------------------------------------------
# Load / Save storage (SAFE)
# -------------------------------------------------
def load_data():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            d = json.load(f)
            d.setdefault("slogans", {})
            d.setdefault("users", {})
            return d
    except:
        return {"slogans": {}, "users": {}}


def save_data(d):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


data = load_data()

# -------------------------------------------------
# Keyboards
# -------------------------------------------------
def admin_menu_keyboard():
    keyboard = [
        [KeyboardButton("➕ افزودن شعار"), KeyboardButton("❌ حذف شعار")],
        [KeyboardButton("📄 لیست شعارها"), KeyboardButton("🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def back_button_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 بازگشت")]], resize_keyboard=True)


# -------------------------------------------------
# START
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("سلام! ربات فعاله 👋")
        return

    context.user_data.clear()
    await update.message.reply_text("پنل مدیریت:", reply_markup=admin_menu_keyboard())


# -------------------------------------------------
# ADMIN HANDLER (PRIVATE ONLY — FIXED)
# -------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id != ADMIN_ID:
        return

    state = context.user_data.get("state")

    # BACK
    if text == "🔙 بازگشت":
        context.user_data.clear()
        await update.message.reply_text("بازگشت به پنل", reply_markup=admin_menu_keyboard())
        return

    # ---------------- add slogan text
    if state == "adding_slogan_text":
        if not text:
            await update.message.reply_text("متن خالیه دوباره بفرست")
            return

        context.user_data["new_slogan"] = text
        context.user_data["state"] = "adding_slogan_score"
        await update.message.reply_text("امتیاز شعار را بفرست:", reply_markup=back_button_keyboard())
        return

    # ---------------- add slogan score
    if state == "adding_slogan_score":
        try:
            text = normalize_digits(text)
            score = int(text)

            data["slogans"][context.user_data["new_slogan"]] = score
            save_data(data)

            context.user_data.clear()
            await update.message.reply_text("شعار ذخیره شد ✅", reply_markup=admin_menu_keyboard())
        except:
            await update.message.reply_text("❌ عدد معتبر نیست", reply_markup=back_button_keyboard())
        return

    # ---------------- remove slogan
    if state == "removing_slogan":
        if text in data["slogans"]:
            del data["slogans"][text]
            save_data(data)
            await update.message.reply_text("حذف شد ✅", reply_markup=admin_menu_keyboard())
        else:
            await update.message.reply_text("پیدا نشد ❌", reply_markup=admin_menu_keyboard())
        context.user_data.clear()
        return

    # ------------------------------------------------ buttons
    if text == "➕ افزودن شعار":
        context.user_data["state"] = "adding_slogan_text"
        await update.message.reply_text("متن شعار را بفرست:", reply_markup=back_button_keyboard())

    elif text == "❌ حذف شعار":
        context.user_data["state"] = "removing_slogan"
        await update.message.reply_text("متن شعار جهت حذف:", reply_markup=back_button_keyboard())

    elif text == "📄 لیست شعارها":
        if not data["slogans"]:
            await update.message.reply_text("شعاری ثبت نشده.", reply_markup=admin_menu_keyboard())
            return

        msg = "📄 لیست شعارها:\n\n"
        for s, sc in data["slogans"].items():
            msg += f"• {s} → {sc}\n"

        await update.message.reply_text(msg, reply_markup=admin_menu_keyboard())


# -------------------------------------------------
# GROUP CHECK (SEPARATED — FIXED)
# -------------------------------------------------
async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    user = update.effective_user
    uid = str(user.id)

    for slogan, score in data["slogans"].items():
        if slogan in text:
            data["users"][uid] = data["users"].get(uid, 0) + score
            save_data(data)

            await update.message.reply_text(
                f"🎉 تبریک {user.first_name}!\n"
                f"امتیاز: {score}\n"
                f"جمع کل: {data['users'][uid]}"
            )
            break


# -------------------------------------------------
# COMMANDS
# -------------------------------------------------
async def total_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    total = data["users"].get(uid, 0)
    await update.message.reply_text(f"📊 جمع امتیاز شما: {total}")


async def leader_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["users"]:
        await update.message.reply_text("هنوز امتیازی ثبت نشده.")
        return

    sorted_users = sorted(data["users"].items(), key=lambda x: x[1], reverse=True)[:10]

    msg = "🏆 لیدربورد:\n\n"
    for i, (uid, score) in enumerate(sorted_users, 1):
        msg += f"{i}. {uid} — {score}\n"

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
    loop.run_in_executor(None, lambda: asyncio.run(application.process_update(update)))
    return "OK", 200200


# -------------------------------------------------
# INIT BOT
# -------------------------------------------------
application = Application.builder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("total_point", total_point))
application.add_handler(CommandHandler("leader_board", leader_board))

# PRIVATE admin
application.add_handler(
    MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message)
)

# GROUP scoring
application.add_handler(
    MessageHandler(filters.TEXT & filters.ChatType.GROUPS, check_messages)
)


# -------------------------------------------------
# START
# -------------------------------------------------
if __name__ == "__main__":

    async def setup():
        await application.initialize()
        await application.start()
        await application.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")

    loop.run_until_complete(setup())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

