"""
🚖 بوت النقل الذكي - نسخة محسنة
"""

import os
import logging
from flask import Flask, request, jsonify
import telebot
from telebot import types

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# الحصول على التوكن
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN غير معين في Environment Variables!")
    logger.error("الرجاء تعيين BOT_TOKEN في Render Dashboard → Environment")
    # يمكنك وضع توكن مؤقت للاختبار (احذفه لاحقاً)
    # BOT_TOKEN = "ضع_التوكن_هنا"
    # لكن الأفضل تعيينه في Environment Variables

app = Flask(__name__)

# محاولة تهيئة البوت
try:
    if BOT_TOKEN:
        bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
        logger.info("✅ تم تهيئة البوت")
    else:
        raise ValueError("BOT_TOKEN غير موجود")
except Exception as e:
    logger.error(f"❌ فشل تهيئة البوت: {e}")
    # إنشاء كائن بوت وهمي للاستمرار
    bot = None

# تخزين بسيط
users = {}
rides = {}

# ============================================================================
# صفحات الويب
# ============================================================================

@app.route('/')
def home():
    status = "🟢 يعمل" if bot else "🔴 متوقف"
    bot_username = "@Dhdhdyduudbot" if bot else "غير متصل"
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🚖 بوت النقل الذكي</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .status {{
                padding: 10px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .status-ok {{ background: #d4edda; color: #155724; }}
            .status-error {{ background: #f8d7da; color: #721c24; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚖 بوت النقل الذكي</h1>
            
            <div class="status {'status-ok' if bot else 'status-error'}">
                <h3>حالة النظام: {status}</h3>
                <p>البوت: {bot_username}</p>
                <p>المستخدمين: {len(users)}</p>
            </div>
            
            <h3>🔧 الإعدادات المطلوبة:</h3>
            <ol>
                <li>تأكد من تعيين <strong>BOT_TOKEN</strong> في Render Environment</li>
                <li>اضغط على "تعيين ويب هوك" بعد التأكد</li>
                <li>اختبر البوت على Telegram</li>
            </ol>
            
            <div style="margin-top: 30px;">
                <a href="/set_webhook" style="padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">
                    ⚙️ تعيين ويب هوك
                </a>
                <a href="/health" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px;">
                    🩺 فحص الصحة
                </a>
            </div>
            
            <div style="margin-top: 30px; padding: 15px; background: #fff3cd; border-radius: 5px;">
                <h4>⚠️ إذا كان البوت لا يعمل:</h4>
                <p>1. تحقق من BOT_TOKEN في Render → Environment</p>
                <p>2. تأكد من صحة التوكن عن طريق زيارة:</p>
                <code>https://api.telegram.org/botYOUR_TOKEN/getMe</code>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook():
    if not bot:
        return '''
        <div style="padding: 50px; text-align: center;">
            <h2 style="color: red;">❌ البوت غير مهيأ</h2>
            <p>الرجاء تعيين BOT_TOKEN في Environment Variables على Render</p>
            <a href="/">العودة للصفحة الرئيسية</a>
        </div>
        ''', 400
    
    try:
        # إزالة الويب هوك القديم
        bot.remove_webhook()
        
        # تعيين ويب هوك جديد
        webhook_url = f"https://{request.host}/webhook"
        result = bot.set_webhook(url=webhook_url)
        
        # اختبار البوت
        bot_info = bot.get_me()
        
        return f'''
        <div style="padding: 50px; text-align: center;">
            <h2 style="color: green;">✅ تم تعيين الويب هوك بنجاح!</h2>
            <p><strong>البوت:</strong> @{bot_info.username}</p>
            <p><strong>الرابط:</strong> {webhook_url}</p>
            <p><strong>النتيجة:</strong> {result}</p>
            <div style="margin-top: 30px;">
                <a href="https://t.me/{bot_info.username}" target="_blank" style="padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px;">
                    💬 افتح البوت على Telegram
                </a>
            </div>
            <div style="margin-top: 20px;">
                <a href="/">العودة للصفحة الرئيسية</a>
            </div>
        </div>
        '''
    except Exception as e:
        return f'''
        <div style="padding: 50px; text-align: center;">
            <h2 style="color: red;">❌ خطأ في تعيين الويب هوك</h2>
            <p>{str(e)}</p>
            <p>الرجاء التأكد من صحة BOT_TOKEN</p>
            <a href="/">العودة للصفحة الرئيسية</a>
        </div>
        ''', 500

@app.route('/health')
def health():
    if not bot:
        return jsonify({
            'status': 'error',
            'message': 'BOT_TOKEN غير معين',
            'instructions': 'اضبط BOT_TOKEN في Environment Variables على Render'
        }), 400
    
    try:
        bot_info = bot.get_me()
        return jsonify({
            'status': 'healthy',
            'bot': {
                'id': bot_info.id,
                'username': bot_info.username,
                'name': bot_info.first_name
            },
            'users_count': len(users),
            'app_url': f"https://{request.host}"
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'suggestion': 'تحقق من BOT_TOKEN في Render Environment'
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    if not bot:
        return 'Bot not initialized', 500
    
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

# ============================================================================
# معالجات البوت (إذا كان البوت مهيأ)
# ============================================================================

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def handle_start(message):
        user_id = str(message.from_user.id)
        users[user_id] = {
            'name': message.from_user.first_name,
            'username': message.from_user.username,
            'joined': True
        }
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('👤 عميل'),
            types.KeyboardButton('🚖 سائق')
        )
        
        bot.send_message(
            message.chat.id,
            f"🎉 أهلاً بك {message.from_user.first_name}!\n\n"
            "🚖 <b>بوت النقل الذكي</b>\n"
            "اختر دورك للبدأ:",
            reply_markup=markup
        )
    
    @bot.message_handler(func=lambda m: m.text in ['👤 عميل', '🚖 سائق'])
    def handle_role(message):
        role = 'عميل' if message.text == '👤 عميل' else 'سائق'
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        if role == 'عميل':
            markup.add('🚖 طلب رحلة', '📍 إرسال موقعي')
            markup.add('📋 رحلاتي', '📞 المساعدة')
        else:
            markup.add('🟢 بدء الخدمة', '🔴 إيقاف الخدمة')
            markup.add('📍 تحديث موقعي', '📊 الرحلات')
        
        bot.send_message(
            message.chat.id,
            f"✅ تم تسجيلك كـ {role}!\n\n"
            "اختر الخدمة المناسبة:",
            reply_markup=markup
        )
    
    @bot.message_handler(func=lambda m: True)
    def handle_all(message):
        bot.reply_to(message, "🤖 البوت يعمل! استخدم /start للقائمة الرئيسية")

# ============================================================================
# التشغيل
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)