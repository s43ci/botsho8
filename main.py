import telebot
import re
import threading
import time
import os
import json
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = '8374831949:AAH-am6HdjEwSkrVPe69y9TlIm16Uwotqdo'
bot = telebot.TeleBot(API_TOKEN)

AUTHORIZED_USER_IDS = [507836119, 7708626625]
GROUP_CHAT_ID = -1001915353634
URL_PATTERN = r'(https?://\S+|www\.\S+)'

DATA_DIR = "data"
STORAGE_FILE = os.path.join(DATA_DIR, "messages.json")

# قائمة الرسائل المجدولة
daily_messages = []

# حالة انتظار كل مستخدم (per-user state)
user_states = {}

# إنشاء مجلد التخزين إذا ما موجود
os.makedirs(DATA_DIR, exist_ok=True)

def load_scheduled_messages():
    global daily_messages
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            try:
                daily_messages = json.load(f)
            except json.JSONDecodeError:
                daily_messages = []

def save_scheduled_messages():
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(daily_messages, f, ensure_ascii=False, indent=2)

def is_admin(chat_id, user_id):
    return user_id in AUTHORIZED_USER_IDS

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        KeyboardButton("➕ إضافة رسالة"),
        KeyboardButton("🗑️ حذف الرسالة")
    )
    return markup

@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id not in AUTHORIZED_USER_IDS:
        return
    bot.send_message(
        message.chat.id,
        "👋 هلاا شووق نورتي البوت! استخدم الأزرار أدناه.",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document'])
def handle_messages(message):
    user_id = message.from_user.id

    # حذف الرسائل التي تحتوي روابط في الجروبات من غير الأدمنز
    if message.chat.type in ['group', 'supergroup']:
    if message.content_type == 'text' and re.search(URL_PATTERN, message.text):
        try:
            chat_member = bot.get_chat_member(message.chat.id, user_id)
            status = chat_member.status
            if status not in ['administrator', 'creator']:
                bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print(f"فشل التحقق من صلاحيات العضو: {e}")
        return

    if message.chat.type == 'private' and user_id in AUTHORIZED_USER_IDS:
        state = user_states.get(user_id, {})

        if message.text == "➕ إضافة رسالة":
            user_states[user_id] = {"waiting_for_message": True}
            bot.reply_to(message, "📝 أرسل الرسالة الآن ليتم جدولتها.")
            return

        elif message.text == "🗑️ حذف الرسالة":
            show_scheduled_messages(message.chat.id)
            return

        # إذا المستخدم يرسل الرسالة التي يريد جدولتها
        if state.get("waiting_for_message"):
            # خزن الرسالة
            user_states[user_id] = {
                "waiting_for_message": False,
                "waiting_for_time": True,
                "temp_message": message
            }
            bot.reply_to(message, "⏰ أرسل الوقت بصيغة 12 ساعة مثل: 2:30")
            return

        # إذا المستخدم يرسل الوقت
        if state.get("waiting_for_time"):
            raw_time = message.text.strip()
            try:
                datetime.strptime(raw_time, "%I:%M")
                user_states[user_id]["waiting_for_time"] = False

                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton("☀️ صباحًا", callback_data="am"),
                    InlineKeyboardButton("🌙 مساءً", callback_data="pm")
                )
                bot.reply_to(message, f"🕓 اختر هل الوقت صباحًا أم مساءً:", reply_markup=markup)

                # حفظ الوقت مؤقتًا
                user_states[user_id]["pending_time"] = raw_time

            except ValueError:
                bot.reply_to(message, "❌ صيغة الوقت غير صحيحة. مثل: 2:30")
            return

def show_scheduled_messages(chat_id):
    if not daily_messages:
        bot.send_message(chat_id, "📭 لا توجد رسائل مجدولة حالياً.")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for idx, msg in enumerate(daily_messages):
        preview = "📷 صورة" if msg["type"] == "photo" else \
                  "🎥 فيديو" if msg["type"] == "video" else \
                  "📄 ملف" if msg["type"] == "document" else \
                  (msg["text"][:30] + "..." if len(msg["text"]) > 30 else msg["text"])
        btn = InlineKeyboardButton(f"🗑️ حذف: {preview} 🕓{msg['time']}", callback_data=f"delete_{idx}")
        markup.add(btn)

    markup.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back_main"))
    bot.send_message(chat_id, "🗂️ اختر الرسالة التي تريد حذفها:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id

    if user_id not in AUTHORIZED_USER_IDS:
        return

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    if call.data.startswith("delete_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(daily_messages):
            deleted = daily_messages.pop(idx)
            save_scheduled_messages()
            bot.edit_message_text(
                f"✅ تم حذف الرسالة المجدولة:\n\n🗑️ {deleted['type']} 🕓 {deleted['time']}",
                call.message.chat.id,
                call.message.message_id
            )

    elif call.data == "back_main":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "⬅️ رجعت للقائمة الرئيسية.", reply_markup=get_main_keyboard())

    elif call.data in ["am", "pm"]:
        state = user_states.get(user_id)
        if not state or "temp_message" not in state or "pending_time" not in state:
            return

        hour_12 = state["pending_time"]
        msg = state["temp_message"]

        adjusted_time = datetime.strptime(hour_12 + (" AM" if call.data == "am" else " PM"), "%I:%M %p") - timedelta(hours=3)
        hour_24_str = adjusted_time.strftime("%H:%M")

        msg_data = {
            "type": msg.content_type,
            "time": hour_24_str
        }

        if msg.content_type == "text":
            msg_data["text"] = msg.text
        elif msg.content_type == "photo":
            msg_data["file_id"] = msg.photo[-1].file_id
            msg_data["caption"] = msg.caption or ""
        elif msg.content_type == "video":
            msg_data["file_id"] = msg.video.file_id
            msg_data["caption"] = msg.caption or ""
        elif msg.content_type == "document":
            msg_data["file_id"] = msg.document.file_id
            msg_data["caption"] = msg.caption or ""

        daily_messages.append(msg_data)
        save_scheduled_messages()

        bot.edit_message_text(
            f"✅ تم جدولة الرسالة يوميًا في {hour_12} {'صباحًا' if call.data == 'am' else 'مساءً'}",
            call.message.chat.id,
            call.message.message_id
        )

        # مسح حالة المستخدم بعد الإضافة
        user_states.pop(user_id, None)

def schedule_checker():
    already_sent_times = set()
    while True:
        now = datetime.now()
        now_str = now.strftime("%H:%M")

        # تنظيف قائمة الإرسال يومياً في بداية اليوم
        if now_str == "00:00":
            already_sent_times.clear()

        if now_str not in already_sent_times:
            for item in daily_messages:
                if item["time"] == now_str:
                    try:
                        if item["type"] == "text":
                            bot.send_message(GROUP_CHAT_ID, item["text"])
                        elif item["type"] == "photo":
                            bot.send_photo(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption", ""))
                        elif item["type"] == "video":
                            bot.send_video(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption", ""))
                        elif item["type"] == "document":
                            bot.send_document(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption", ""))
                    except Exception as e:
                        print(f"❌ خطأ بالإرسال: {e}")
                    time.sleep(1)

            already_sent_times.add(now_str)

        time.sleep(1)

# تحميل الرسائل المجدولة من الملف عند بدء التشغيل
load_scheduled_messages()

# بدء الجدولة بالخلفية
threading.Thread(target=schedule_checker, daemon=True).start()

bot.remove_webhook()

bot.polling()
