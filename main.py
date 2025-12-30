import telebot
import re
import threading
import time
import os
import json
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# --- إعدادات Flask لمنصة Render ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running..."

def run_flask():
    # Render يعطي المنفذ عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- إعدادات البوت ---
API_TOKEN = '8374831949:AAET5CT5Wfn-Xd7Wm2oFWfSWwDBH7t8mSG0' # استبدله بالتوكن الجديد فوراً!
bot = telebot.TeleBot(API_TOKEN)

AUTHORIZED_USER_IDS = [8523041592, 507836119]
GROUP_CHAT_ID = -1001915353634
URL_PATTERN = r'(https?://\S+|www\.\S+)'

DATA_DIR = "data"
STORAGE_FILE = os.path.join(DATA_DIR, "messages.json")

daily_messages = []
user_states = {}

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- دوال إدارة البيانات ---
def load_scheduled_messages():
    global daily_messages
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            try:
                daily_messages = json.load(f)
            except:
                daily_messages = []

def save_scheduled_messages():
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(daily_messages, f, ensure_ascii=False, indent=2)

# --- الكيبورد الرئيسي ---
def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("➕ إضافة رسالة"), KeyboardButton("🗑️ حذف الرسالة"))
    return markup

# --- معالجة الرسائل ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id in AUTHORIZED_USER_IDS:
        bot.send_message(message.chat.id, "👋 أهلاً بك! استخدم الأزرار للتحكم.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document'])
def handle_messages(message):
    user_id = message.from_user.id

    if message.chat.type in ['group', 'supergroup']:
        if message.content_type == 'text' and re.search(URL_PATTERN, message.text):
            try:
                member = bot.get_chat_member(message.chat.id, user_id)
                if member.status not in ['administrator', 'creator']:
                    bot.delete_message(message.chat.id, message.message_id)
            except: pass
            return

    if message.chat.type == 'private' and user_id in AUTHORIZED_USER_IDS:
        state = user_states.get(user_id, {})

        if message.text == "➕ إضافة رسالة":
            user_states[user_id] = {"waiting_for_message": True}
            bot.reply_to(message, "📝 أرسل الرسالة الآن.")
        elif message.text == "🗑️ حذف الرسالة":
            show_scheduled_messages(message.chat.id)
        
        elif state.get("waiting_for_message"):
            user_states[user_id] = {"waiting_for_time": True, "temp_message": message}
            bot.reply_to(message, "⏰ أرسِل الوقــت (مثال: 2:30)")
        
        elif state.get("waiting_for_time"):
            raw_time = message.text.strip()
            try:
                datetime.strptime(raw_time, "%I:%M")
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("☀️ صباحًا", callback_data="am"), 
                           InlineKeyboardButton("🌙 مساءً", callback_data="pm"))
                bot.reply_to(message, "🕓 اختر التوقيت:", reply_markup=markup)
                user_states[user_id]["pending_time"] = raw_time
                user_states[user_id]["waiting_for_time"] = False
            except:
                bot.reply_to(message, "❌ خطأ في الصيغة. استعمل: 2:30")

# --- عرض وحذف الرسائل ---
def show_scheduled_messages(chat_id):
    if not daily_messages:
        bot.send_message(chat_id, "📭 القائمة فارغة.")
        return
    markup = InlineKeyboardMarkup()
    for idx, msg in enumerate(daily_messages):
        preview = msg.get("text", msg["type"])[:20]
        markup.add(InlineKeyboardButton(f"🗑️ {preview} ({msg['time']})", callback_data=f"delete_{idx}"))
    bot.send_message(chat_id, "إختر للحذف:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data.startswith("delete_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(daily_messages):
            daily_messages.pop(idx)
            save_scheduled_messages()
            bot.edit_message_text("✅ تم الحذف!", call.message.chat.id, call.message.message_id)
    
    elif call.data in ["am", "pm"]:
        state = user_states.get(call.from_user.id)
        if state and "pending_time" in state:
            hour_12 = state["pending_time"]
            msg = state["temp_message"]
            adj_time = datetime.strptime(hour_12 + (" AM" if call.data == "am" else " PM"), "%I:%M %p") - timedelta(hours=3)
            
            msg_data = {"type": msg.content_type, "time": adj_time.strftime("%H:%M")}
            if msg.content_type == "text": msg_data["text"] = msg.text
            else:
                msg_data["file_id"] = getattr(msg, msg.content_type)[-1].file_id if msg.content_type == "photo" else getattr(msg, msg.content_type).file_id
                msg_data["caption"] = msg.caption or ""
            
            daily_messages.append(msg_data)
            save_scheduled_messages()
            bot.edit_message_text(f"✅ تمت الجدولة بنجاح في {hour_12}", call.message.chat.id, call.message.message_id)
            user_states.pop(call.from_user.id, None)

# --- الفاحص الدوري (Schedule Checker) ---
def schedule_checker():
    already_sent_times = set()
    while True:
        now_str = datetime.now().strftime("%H:%M")
        if now_str == "00:00": already_sent_times.clear()
        
        if now_str not in already_sent_times:
            for item in daily_messages:
                if item["time"] == now_str:
                    try:
                        if item["type"] == "text": bot.send_message(GROUP_CHAT_ID, item["text"])
                        elif item["type"] == "photo": bot.send_photo(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption", ""))
                        elif item["type"] == "video": bot.send_video(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption", ""))
                        elif item["type"] == "document": bot.send_document(GROUP_CHAT_ID, item["file_id"], caption=item.get("caption", ""))
                    except Exception as e: print(f"Error: {e}")
            already_sent_times.add(now_str)
        time.sleep(30) # فحص كل 30 ثانية لتوفير الموارد

# --- التشغيل النهائي ---
if __name__ == "__main__":
    load_scheduled_messages()
    
    # تشغيل Flask في ثريد منفصل
    threading.Thread(target=run_flask, daemon=True).start()
    
    # تشغيل الفاحص في ثريد منفصل
    threading.Thread(target=schedule_checker, daemon=True).start()
    
    # تشغيل البوت
    print("Bot is starting...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
    



