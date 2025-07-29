import telebot
import re
import threading
import time
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = '7994383386:AAHDD7-F3mrv3_RtlZs5dEzPGrChzaRzsm0'
bot = telebot.TeleBot(API_TOKEN)

AUTHORIZED_USER_ID = 7708626625
GROUP_CHAT_ID = -1002830133309

URL_PATTERN = r'(https?://\S+|www\.\S+)'

daily_messages = []
waiting_for_message = False
waiting_for_time = False
temp_message = None
user_pending_time = {}

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        KeyboardButton("➕ إضافة رسالة"),
        KeyboardButton("🗑️ حذف الرسالة")
    )
    return markup

@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        return
    bot.send_message(
        message.chat.id,
        "👋 هلاا شووق نورتي البوت! استخدم الأزرار أدناه.",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_messages(message):
    global waiting_for_time, waiting_for_message, temp_message

    if message.chat.type in ['group', 'supergroup']:
        if re.search(URL_PATTERN, message.text):
            if not is_admin(message.chat.id, message.from_user.id):
                try:
                    bot.delete_message(message.chat.id, message.message_id)
                except:
                    pass
            return

    if message.chat.type == 'private' and message.from_user.id == AUTHORIZED_USER_ID:

        if message.text == "➕ إضافة رسالة":
            waiting_for_message = True
            bot.reply_to(message, "📝 أرسل الرسالة الآن ليتم جدولتها.")
            return

        elif message.text == "🗑️ حذف الرسالة":
            show_scheduled_messages(message.chat.id)
            return

        elif waiting_for_message:
            temp_message = message.text.strip()
            waiting_for_message = False
            waiting_for_time = True
            bot.reply_to(message, "⏰ أرسل الوقت بصيغة 12 ساعة مثل: 2:30")
            return

        elif waiting_for_time:
            try:
                raw_time = message.text.strip()
                datetime.strptime(raw_time, "%I:%M")
                user_pending_time[message.from_user.id] = {
                    "text": raw_time,
                    "message": temp_message
                }
                waiting_for_time = False

                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton("☀️ صباحًا", callback_data="am"),
                    InlineKeyboardButton("🌙 مساءً", callback_data="pm")
                )
                bot.reply_to(message, f"🕓 اختر هل الوقت صباحًا أم مساءً:", reply_markup=markup)

            except ValueError:
                bot.reply_to(message, "❌ صيغة الوقت غير صحيحة. مثل: 2:30")
            return

def show_scheduled_messages(chat_id):
    if not daily_messages:
        bot.send_message(chat_id, "📭 لا توجد رسائل مجدولة حالياً.")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for idx, msg in enumerate(daily_messages):
        short = (msg["message"][:30] + "...") if len(msg["message"]) > 30 else msg["message"]
        btn = InlineKeyboardButton(f"🗑️ حذف: {short} 🕓{msg['time']}", callback_data=f"delete_{idx}")
        markup.add(btn)

    markup.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    bot.send_message(chat_id, "🗂️ اختر الرسالة التي تريد حذفها:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.from_user.id != AUTHORIZED_USER_ID:
        return

    # أجب على الضغط فوراً حتى لا يحدث timeout
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    if call.data.startswith("delete_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(daily_messages):
            deleted = daily_messages.pop(idx)
            bot.edit_message_text(
                f"✅ تم حذف الرسالة المجدولة:\n\n🗑️ {deleted['message']}\n🕓 {deleted['time']}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ رقم غير صالح.")

    elif call.data == "back_main":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "⬅️ رجعت للقائمة الرئيسية.", reply_markup=get_main_keyboard())

    elif call.data in ["am", "pm"]:
        user_id = call.from_user.id
        if user_id not in user_pending_time:
            return

        entry = user_pending_time.pop(user_id)
        hour_12 = entry["text"]
        msg = entry["message"]

        adjusted_time = datetime.strptime(hour_12 + (" AM" if call.data == "am" else " PM"), "%I:%M %p") - timedelta(hours=3)
        hour_24_str = adjusted_time.strftime("%H:%M")

        daily_messages.append({
            "message": msg,
            "time": hour_24_str
        })

        bot.edit_message_text(
            f"✅ تم جدولة الرسالة يوميًا في {hour_12} {'صباحًا' if call.data == 'am' else 'مساءً'}",
            call.message.chat.id,
            call.message.message_id
        )

def schedule_checker():
    while True:
        now = datetime.now().strftime("%H:%M")
        for item in daily_messages:
            if item["time"] == now:
                try:
                    bot.send_message(GROUP_CHAT_ID, item["message"])
                except Exception as e:
                    print(f"❌ خطأ بالإرسال: {e}")
                time.sleep(60)
        time.sleep(1)

threading.Thread(target=schedule_checker, daemon=True).start()
bot.polling()