import telebot
import re
import threading
import time
import os
import json
import pytz  # مكتبة ضبط المناطق الزمنية
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# --- إعدادات Flask لمنصة Render ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running with Baghdad Timezone (GMT+3)..."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- إعدادات البوت ---
API_TOKEN = '8374831949:AAGpPk4OZyLFdRYlWkpc-mJ6-ndDRlg0GYE' 
bot = telebot.TeleBot(API_TOKEN)

PASSWORD = "واثق"
GROUP_CHAT_ID = -1001915353634
IRAQ_TZ = pytz.timezone('Asia/Baghdad') # تحديد توقيت العراق

# النماذج (الروابط وأرقام الهواتف)
URL_PATTERN = r'(https?://\S+|www\.\S+)'
PHONE_PATTERN = r'(\+?\d{1,3}[- ]?)?\d{10,13}|(05\d{8})|(\+966\d{9})|(00966\d{9})'

DATA_DIR = "data"
STORAGE_FILE = os.path.join(DATA_DIR, "messages.json")
AUTH_FILE = os.path.join(DATA_DIR, "authorized_users.json")

daily_messages = []
authorized_user_ids = []
user_states = {}

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- دوال إدارة البيانات ---
def load_data():
    global daily_messages, authorized_user_ids
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            try: daily_messages = json.load(f)
            except: daily_messages = []
    
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            try: authorized_user_ids = json.load(f)
            except: authorized_user_ids = []

def save_scheduled_messages():
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(daily_messages, f, ensure_ascii=False, indent=2)

def save_authorized_users():
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(authorized_user_ids, f)

# --- الكيبورد الرئيسي ---
def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("➕ إضافة رسالة"), KeyboardButton("🗑️ حذف الرسالة"))
    return markup

# --- معالجة الرسائل ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    if user_id in authorized_user_ids:
        bot.send_message(message.chat.id, "👋 أهلاً بك! البوت يعمل الآن بتوقيت بغداد.", reply_markup=get_main_keyboard())
    else:
        bot.send_message(message.chat.id, "🔒 عذراً، هذا البوت محمي. الرجاء إرسال كلمة السر للتفعيل:")

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document'])
def handle_messages(message):
    user_id = message.from_user.id

    if message.chat.type in ['group', 'supergroup']:
        if message.content_type == 'text':
            if re.search(URL_PATTERN, message.text) or re.search(PHONE_PATTERN, message.text):
                try:
                    member = bot.get_chat_member(message.chat.id, user_id)
                    if member.status not in ['administrator', 'creator']:
                        bot.delete_message(message.chat.id, message.message_id)
                except: pass
        return

    if message.chat.type == 'private':
        if user_id not in authorized_user_ids:
            if message.text == PASSWORD:
                authorized_user_ids.append(user_id)
                save_authorized_users()
                bot.reply_to(message, "✅ تم التفعيل! البوت يتبع توقيت العراق حالياً.", reply_markup=get_main_keyboard())
            else:
                bot.reply_to(message, "❌ كلمة السر خاطئة.")
            return

        state = user_states.get(user_id, {})

        if message.text == "➕ إضافة رسالة":
            user_states[user_id] = {"waiting_for_message": True}
            bot.reply_to(message, "📝 أرسل الرسالة الآن (نص أو ميديا).")
        
        elif message.text == "🗑️ حذف الرسالة":
            show_scheduled_messages(message.chat.id)
        
        elif state.get("waiting_for_message"):
            user_states[user_id] = {"waiting_for_time": True, "temp_message": message}
            bot.reply_to(message, "⏰ أرسِل الوقــت بتوقيت العراق (مثال: 08:30)")
        
        elif state.get("waiting_for_time"):
            raw_time = message.text.strip()
            try:
                datetime.strptime(raw_time, "%I:%M")
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("☀️ صباحًا", callback_data="am"), 
                           InlineKeyboardButton("🌙 مساءً", callback_data="pm"))
                bot.reply_to(message, "🕓 اختر التوقيت (AM/PM):", reply_markup=markup)
                user_states[user_id]["pending_time"] = raw_time
                user_states[user_id]["waiting_for_time"] = False
            except:
                bot.reply_to(message, "❌ صيغة غير صحيحة. استخدم 02:30 مثلاً.")

def show_scheduled_messages(chat_id):
    if not daily_messages:
        bot.send_message(chat_id, "📭 القائمة فارغة.")
        return
    markup = InlineKeyboardMarkup()
    for idx, msg in enumerate(daily_messages):
        preview = msg.get("text", f"[{msg['type']}]")[:20]
        markup.add(InlineKeyboardButton(f"🗑️ {preview} ({msg['time']})", callback_data=f"delete_{idx}"))
    bot.send_message(chat_id, "إختر للحذف:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    if user_id not in authorized_user_ids: return

    if call.data.startswith("delete_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(daily_messages):
            daily_messages.pop(idx)
            save_scheduled_messages()
            bot.edit_message_text("✅ تم الحذف!", call.message.chat.id, call.message.message_id)
    
    elif call.data in ["am", "pm"]:
        state = user_states.get(user_id)
        if state and "pending_time" in state:
            hour_12 = state["pending_time"]
            msg = state["temp_message"]
            
            # تحويل الوقت لصيغة 24 ساعة للتخزين
            adj_time = datetime.strptime(hour_12 + (" AM" if call.data == "am" else " PM"), "%I:%M %p")
            time_24 = adj_time.strftime("%H:%M")
            
            msg_data = {"type": msg.content_type, "time": time_24, "original_user": user_id}
            
            if msg.content_type == "text": 
                msg_data["text"] = msg.text
            else:
                # جلب الـ file_id للميديا
                if msg.content_type == "photo":
                    msg_data["file_id"] = msg.photo[-1].file_id
                elif msg.content_type == "video":
                    msg_data["file_id"] = msg.video.file_id
                elif msg.content_type == "document":
                    msg_data["file_id"] = msg.document.file_id
                msg_data["caption"] = msg.caption or ""
            
            daily_messages.append(msg_data)
            save_scheduled_messages()
            bot.edit_message_text(f"✅ تمت الجدولة بتوقيت العراق: {hour_12} {call.data}", call.message.chat.id, call.message.message_id)
            user_states.pop(user_id, None)

# --- الفاحص الدوري (معدل ليعمل بتوقيت بغداد) ---
def schedule_checker():
    already_sent_times = set()
    while True:
        # جلب الوقت الحالي في بغداد
        now_iraq = datetime.now(IRAQ_TZ)
        now_str = now_iraq.strftime("%H:%M")
        
        # تصفير السجل عند منتصف الليل بتوقيت العراق
        if now_str == "00:00": 
            already_sent_times.clear()
        
        if now_str not in already_sent_times:
            for item in daily_messages:
                if item["time"] == now_str:
                    try:
                        if item["type"] == "text":
                            bot.send_message(GROUP_CHAT_ID, item["text"])
                        else:
                            # استخدام copy_message لإرسال الميديا مع وصفها
                            bot.copy_message(
                                chat_id=GROUP_CHAT_ID,
                                from_chat_id=item.get("original_user", authorized_user_ids[0]),
                                message_id=None, # لا نحتاجه عند استخدام file_id في بعض النسخ، لكن هنا نستخدم copy_message الصحيحة
                                caption=item.get("caption", ""),
                                # ملاحظة: في النسخ الحديثة يفضل استخدام send_photo/video مع file_id
                            )
                            # كطريقة بديلة أكثر ضماناً للميديا:
                            if item["type"] == "photo":
                                bot.send_photo(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption"))
                            elif item["type"] == "video":
                                bot.send_video(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption"))
                    except Exception as e:
                        print(f"Send Error: {e}")
            
            already_sent_times.add(now_str)
        time.sleep(30)

# --- التشغيل ---
if __name__ == "__main__":
    load_data()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=schedule_checker, daemon=True).start()
    print("Bot is starting with Iraq Timezone...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
