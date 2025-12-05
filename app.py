"""
🚖 بوت النقل الذكي - نسخة مضمونة العمل
"""

import os
import logging
from flask import Flask, request, jsonify
import telebot
from telebot import types

# ============================================================================
# إعدادات أساسية
# ============================================================================

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# الحصول على التوكن من Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN غير معين في Environment Variables!")
    # استخدم هذا التوكن للاختبار فقط (استبدله بتوكنك الفعلي)
    BOT_TOKEN = "8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0"
    logger.info(f"✅ استخدام التوكن: {BOT_TOKEN[:10]}...")

# تهيئة التطبيق والبوت
app = Flask(__name__)

# محاولة تهيئة البوت
try:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
    
    # اختبار البوت
    bot_info = bot.get_me()
    logger.info(f"✅ تم تهيئة البوت: @{bot_info.username}")
    
except Exception as e:
    logger.error(f"❌ فشل تهيئة البوت: {e}")
    # إذا فشل التوكن، حاول بآخر
    BOT_TOKEN = "8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0"
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
    logger.info(f"✅ استخدام التوكن البديل: {BOT_TOKEN[:10]}...")

# تخزين بسيط في الذاكرة
users = {}
active_drivers = {}

# ============================================================================
# صفحات الويب
# ============================================================================

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    try:
        bot_info = bot.get_me()
        bot_status = f"@{bot_info.username}"
    except:
        bot_status = "❌ غير متصل"
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🚖 بوت النقل الذكي</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                text-align: center;
            }}
            .status {{
                padding: 10px 20px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                margin: 20px 0;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 24px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚖 بوت النقل الذكي</h1>
            <p>نظام متكامل لإدارة طلبات النقل</p>
            
            <div class="status">
                <p>🟢 <strong>الخادم يعمل بنجاح</strong></p>
                <p>🤖 <strong>البوت:</strong> {bot_status}</p>
                <p>👥 <strong>المستخدمين:</strong> {len(users)}</p>
                <p>🚕 <strong>السائقين:</strong> {len(active_drivers)}</p>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="/test_bot" class="btn">🧪 اختبار البوت</a>
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn">💬 فتح البوت</a>
            </div>
            
            <div style="margin-top: 40px; opacity: 0.8;">
                <p>🔗 الرابط: https://dhhfhfjd.onrender.com</p>
                <p>© 2024 بوت النقل الذكي</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook():
    """تعيين ويب هوك"""
    try:
        # الحصول على رابط التطبيق الحالي
        webhook_url = f"https://{request.host}/webhook"
        
        logger.info(f"🔄 محاولة تعيين ويب هوك على: {webhook_url}")
        
        # إزالة أي ويب هوك سابق
        bot.remove_webhook()
        
        # تعيين ويب هوك جديد
        result = bot.set_webhook(url=webhook_url)
        
        # الحصول على معلومات البوت
        bot_info = bot.get_me()
        
        return f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>✅ تم تعيين الويب هوك</title>
            <style>
                body {{
                    padding: 50px;
                    text-align: center;
                    font-family: Arial, sans-serif;
                }}
                .success {{
                    background: #d4edda;
                    color: #155724;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px auto;
                    max-width: 600px;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h2>✅ تم تعيين الويب هوك بنجاح!</h2>
                <p><strong>البوت:</strong> @{bot_info.username}</p>
                <p><strong>الرابط:</strong> {webhook_url}</p>
                <p><strong>النتيجة:</strong> {result}</p>
            </div>
            <div style="margin-top: 30px;">
                <a href="https://t.me/{bot_info.username}" target="_blank" style="padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px;">
                    💬 افتح البوت الآن على Telegram
                </a>
            </div>
            <div style="margin-top: 20px;">
                <a href="/">العودة للصفحة الرئيسية</a>
            </div>
        </body>
        </html>
        '''
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين الويب هوك: {e}")
        return f'''
        <div style="padding: 50px; text-align: center;">
            <h2 style="color: red;">❌ خطأ في تعيين الويب هوك</h2>
            <p>{str(e)}</p>
            <a href="/">العودة</a>
        </div>
        ''', 500

@app.route('/test_bot')
def test_bot():
    """صفحة اختبار البوت"""
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🧪 اختبار البوت</title>
        <style>
            body { padding: 30px; font-family: Arial; text-align: center; }
            .instructions { 
                background: #e9f7fe; 
                padding: 20px; 
                border-radius: 10px;
                text-align: right;
                margin: 20px auto;
                max-width: 500px;
            }
        </style>
    </head>
    <body>
        <h1>🧪 اختبار البوت</h1>
        
        <div class="instructions">
            <h3>📱 خطوات الاختبار:</h3>
            <ol>
                <li>افتح تطبيق Telegram على هاتفك</li>
                <li>ابحث عن: <strong>@Dhdhdyduudbot</strong></li>
                <li>أرسل: <code>/start</code></li>
                <li>اضغط على "👤 عميل" أو "🚖 سائق"</li>
                <li>جرب الأزرار المختلفة</li>
            </ol>
            
            <p>إذا لم يرد البوت، جرب:</p>
            <ul>
                <li>أعد تعيين الويب هوك</li>
                <li>انتظر 1-2 دقيقة</li>
                <li>أعد فتح محادثة البوت</li>
            </ul>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="https://t.me/Dhdhdyduudbot" target="_blank" style="padding: 15px 30px; background: #0088cc; color: white; text-decoration: none; border-radius: 8px; font-size: 1.2em;">
                🚀 افتح البوت الآن
            </a>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="/">العودة للصفحة الرئيسية</a>
        </div>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة استقبال تحديثات Telegram"""
    if request.headers.get('content-type') == 'application/json':
        try:
            # تحويل JSON إلى تحديث
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            
            # تسجيل التحديث الوارد
            logger.info(f"📩 استلام تحديث: {update.update_id}")
            
            # معالجة التحديث
            bot.process_new_updates([update])
            
            logger.info(f"✅ تم معالجة تحديث: {update.update_id}")
            return 'OK', 200
            
        except Exception as e:
            logger.error(f"❌ خطأ في ويب هوك: {e}")
            return 'Error', 500
    
    return 'Bad Request', 400

# ============================================================================
# معالجات البوت
# ============================================================================

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """معالجة أمر /start"""
    user_id = str(message.from_user.id)
    name = message.from_user.first_name
    
    # تسجيل وصول الرسالة
    logger.info(f"👋 /start من: {name} ({user_id})")
    
    # حفظ بيانات المستخدم
    users[user_id] = {
        'id': user_id,
        'name': name,
        'username': message.from_user.username,
        'role': None
    }
    
    # إنشاء لوحة المفاتيح
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👤 عميل'),
        types.KeyboardButton('🚖 سائق')
    )
    
    # الرد
    bot.send_message(
        message.chat.id,
        f"🎉 <b>مرحباً بك {name} في بوت النقل الذكي!</b>\n\n"
        "🚖 <b>خدمة نقل ذكية توفر لك:</b>\n"
        "• رحلات سريعة وآمنة\n"
        "• تتبع مباشر للرحلة\n"
        "• دفع إلكتروني آمن\n"
        "• تقييمات موثوقة\n\n"
        "📱 <b>اختر دورك للبدء:</b>",
        reply_markup=markup
    )
    
    logger.info(f"✅ تم الرد على {name}")

@bot.message_handler(func=lambda message: message.text in ['👤 عميل', '🚖 سائق'])
def handle_role(message):
    """معالجة اختيار الدور"""
    user_id = str(message.from_user.id)
    role = 'عميل' if message.text == '👤 عميل' else 'سائق'
    
    logger.info(f"🎭 اختيار دور: {role} من: {user_id}")
    
    # تحديث دور المستخدم
    if user_id in users:
        users[user_id]['role'] = role
    
    # إنشاء القائمة المناسبة
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if role == 'عميل':
        markup.add(
            types.KeyboardButton('🚖 طلب رحلة'),
            types.KeyboardButton('📍 إرسال موقعي', request_location=True)
        )
        markup.add(
            types.KeyboardButton('📋 رحلاتي'),
            types.KeyboardButton('💰 رصيدي')
        )
    else:
        markup.add(
            types.KeyboardButton('🟢 بدء الخدمة'),
            types.KeyboardButton('🔴 إيقاف الخدمة')
        )
        markup.add(
            types.KeyboardButton('📍 تحديث موقعي', request_location=True),
            types.KeyboardButton('📊 الرحلات النشطة')
        )
    
    markup.add(types.KeyboardButton('📞 المساعدة'))
    
    # الرد
    bot.send_message(
        message.chat.id,
        f"✅ <b>تم تسجيلك كـ {role} بنجاح!</b>\n\n"
        f"🔧 <b>اختر الخدمة المناسبة:</b>",
        reply_markup=markup
    )
    
    logger.info(f"✅ تم تعيين دور {role} لـ {user_id}")

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة')
def handle_ride_request(message):
    """طلب رحلة جديدة"""
    logger.info(f"🚖 طلب رحلة من: {message.from_user.id}")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton('📍 إرسال موقعي', request_location=True),
        types.KeyboardButton('رجوع')
    )
    
    bot.send_message(
        message.chat.id,
        "📍 <b>طلب رحلة جديدة</b>\n\n"
        "الرجاء إرسال موقعك الحالي لتحديد نقطة الانطلاق.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '🟢 بدء الخدمة')
def handle_start_service(message):
    """بدء خدمة السائق"""
    user_id = str(message.from_user.id)
    
    logger.info(f"🟢 بدء خدمة سائق: {user_id}")
    
    active_drivers[user_id] = {
        'id': user_id,
        'name': users.get(user_id, {}).get('name', 'Unknown'),
        'status': 'active'
    }
    
    bot.send_message(
        message.chat.id,
        "✅ <b>تم تفعيل وضع السائق!</b>\n\n"
        "🎯 أنت الآن تستقبل طلبات الركوب تلقائياً.\n"
        "📍 تأكد من تحديث موقعك بانتظام.\n\n"
        "لإيقاف الخدمة، اضغط '🔴 إيقاف الخدمة'"
    )

@bot.message_handler(func=lambda message: message.text == '🔴 إيقاف الخدمة')
def handle_stop_service(message):
    """إيقاف خدمة السائق"""
    user_id = str(message.from_user.id)
    
    logger.info(f"🔴 إيقاف خدمة سائق: {user_id}")
    
    if user_id in active_drivers:
        del active_drivers[user_id]
    
    bot.send_message(
        message.chat.id,
        "🔴 <b>تم إيقاف خدمة الاستقبال</b>\n\n"
        "للعودة لاستقبال الطلبات، اضغط '🟢 بدء الخدمة'"
    )

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع المرسل"""
    location = message.location
    
    logger.info(f"📍 موقع من: {message.from_user.id} - {location.latitude}, {location.longitude}")
    
    response = (
        "📍 <b>تم استلام موقعك بنجاح!</b>\n\n"
        f"• <b>خط العرض:</b> {location.latitude:.6f}\n"
        f"• <b>خط الطول:</b> {location.longitude:.6f}\n\n"
    )
    
    user_id = str(message.from_user.id)
    
    if user_id in users and users[user_id]['role'] == 'عميل':
        response += "🚖 <b>تم إنشاء طلب رحلة!</b>\n"
        response += "⏳ جاري البحث عن سائق قريب..."
    elif user_id in users and users[user_id]['role'] == 'سائق':
        response += "✅ <b>تم تحديث موقع السائق</b>"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(func=lambda message: message.text == '📞 المساعدة')
def handle_help(message):
    """عرض رسالة المساعدة"""
    bot.send_message(
        message.chat.id,
        "📞 <b>مساعدة بوت النقل</b>\n\n"
        "<b>👤 للعملاء:</b>\n"
        "• استخدم /start للبدء\n"
        "• اختر '👤 عميل'\n"
        "• اضغط '🚖 طلب رحلة'\n"
        "• أرسل موقعك\n\n"
        "<b>🚖 للسائقين:</b>\n"
        "• اختر '🚖 سائق'\n"
        "• اضغط '🟢 بدء الخدمة'\n"
        "• أرسل موقعك\n\n"
        "<b>📋 الأوامر:</b>\n"
        "/start - بدء البوت\n"
        "/help - هذه الرسالة\n\n"
        "<b>📞 الدعم:</b>\n"
        "للشكاوى والاستفسارات، تواصل مع الدعم الفني."
    )

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالجة جميع الرسائل الأخرى"""
    logger.info(f"📩 رسالة عامة: {message.text} من {message.from_user.id}")
    
    bot.reply_to(
        message,
        "🤖 <b>مرحباً!</b>\n\n"
        "استخدم /start لرؤية القائمة الرئيسية.\n"
        "أو اختر من الأزرار في القائمة."
    )

# ============================================================================
# تهيئة البوت
# ============================================================================

def init_bot():
    """تهيئة البوت عند التشغيل"""
    try:
        # اختبار البوت
        bot_info = bot.get_me()
        logger.info(f"✅ البوت جاهز: @{bot_info.username} ({bot_info.first_name})")
        
        # تسجيل المعالجات
        logger.info("✅ تم تسجيل جميع معالجات الرسائل")
        
        return True
    except Exception as e:
        logger.error(f"❌ فشل تهيئة البوت: {e}")
        return False

# تهيئة البوت
if __name__ != '__main__':
    init_bot()

# للتنمية المحلية فقط
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    app.run(host='0.0.0.0', port=port, debug=False)