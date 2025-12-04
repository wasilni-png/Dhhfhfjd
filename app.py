import os
import sys
import time
import logging
from flask import Flask, request, jsonify

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# الحصول على التوكن من متغيرات البيئة
BOT_TOKEN = os.getenv('BOT_TOKEN', '8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0')
PORT = int(os.getenv('PORT', 10000))

# الحصول على عنوان URL من Render
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else f"https://telegram-bot.onrender.com"

logger.info(f"🚀 Starting Telegram Bot")
logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}")
logger.info(f"🔑 Token: {BOT_TOKEN[:10]}...")

# محاولة استيراد telebot
try:
    import telebot
    from telebot import types
    
    # تهيئة البوت
    bot = telebot.TeleBot(BOT_TOKEN)
    TELEBOT_AVAILABLE = True
    
    # اختبار البوت
    try:
        bot_info = bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username}")
    except Exception as e:
        logger.warning(f"⚠️ Could not connect to Telegram: {e}")
        
except ImportError as e:
    logger.error(f"❌ Telebot not installed: {e}")
    TELEBOT_AVAILABLE = False
    bot = None
except Exception as e:
    logger.error(f"❌ Bot init failed: {e}")
    TELEBOT_AVAILABLE = False
    bot = None

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Telegram Bot</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
                text-align: center;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
            }
            h1 {
                font-size: 2.5em;
                margin-bottom: 20px;
            }
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
                margin: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Telegram Bot is Running!</h1>
            <p>Your bot is successfully deployed on Render.com</p>
            
            <div style="padding: 20px; background: rgba(255,255,255,0.2); border-radius: 10px; margin: 20px 0;">
                <p><strong>Platform:</strong> Render.com</p>
                <p><strong>Status:</strong> 🟢 Active</p>
                <p><strong>URL:</strong> ''' + WEBHOOK_URL + '''</p>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ Set Webhook</a>
                <a href="/health" class="btn">🩺 Health Check</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook():
    """تعيين ويب هوك - إصدار مصحح"""
    try:
        if not TELEBOT_AVAILABLE:
            return '''
            <div style="text-align: center; padding: 50px; background: #f44336; color: white;">
                <h1>❌ مكتبة telebot غير مثبتة</h1>
                <p>الرجاء تثبيت المكتبات:</p>
                <code>pip install pyTelegramBotAPI</code>
            </div>
            '''
        
        # إزالة الويب هوك القديم
        try:
            bot.remove_webhook()
            time.sleep(1)
        except:
            pass
        
        # تعيين الويب هوك الجديد
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = bot.set_webhook(url=webhook_url)
        
        # محاولة الحصول على معلومات البوت
        bot_info = None
        try:
            bot_info = bot.get_me()
        except Exception as e:
            logger.warning(f"Could not get bot info: {e}")
        
        bot_username = bot_info.username if bot_info else "unknown"
        bot_name = bot_info.first_name if bot_info else "Bot"
        
        # استخدام f-string بدلاً من % formatting
        html = f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <title>✅ تم التعيين</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #4CAF50;
                    color: white;
                }}
                .container {{
                    background: rgba(255,255,255,0.1);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 600px;
                    margin: 0 auto;
                }}
                .btn {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: white;
                    color: #4CAF50;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ تم تعيين الويب هوك بنجاح!</h1>
                <p><strong>الرابط:</strong> {webhook_url}</p>
                <p><strong>البوت:</strong> {bot_name} (@{bot_username})</p>
                <p><strong>النتيجة:</strong> {result}</p>
                <br>
                <a href="https://t.me/{bot_username}" target="_blank" class="btn">💬 فتح البوت</a>
                <a href="/" class="btn">🏠 الرئيسية</a>
            </div>
        </body>
        </html>
        '''
        
        return html
        
    except Exception as e:
        # استخدام f-string هنا أيضاً
        error_html = f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <title>❌ خطأ</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f44336;
                    color: white;
                }}
                .container {{
                    background: rgba(255,255,255,0.1);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 600px;
                    margin: 0 auto;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ فشل تعيين الويب هوك</h1>
                <p><strong>الخطأ:</strong> {str(e)}</p>
                <a href="/" style="color: white;">🏠 العودة للرئيسية</a>
            </div>
        </body>
        </html>
        '''
        return error_html

@app.route('/health')
def health():
    """فحص الصحة"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'platform': 'Render',
        'port': PORT,
        'webhook_url': f"{WEBHOOK_URL}/webhook",
        'telebot_installed': TELEBOT_AVAILABLE,
        'python_version': sys.version.split()[0]
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint"""
    if not TELEBOT_AVAILABLE:
        return 'Telebot not available', 500
    
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK'
        return 'Invalid content type', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

# معالجات البوت الأساسية
if TELEBOT_AVAILABLE and bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        """معالجة أمر /start"""
        try:
            bot.reply_to(
                message,
                "🚀 *Hello! I'm a Telegram Bot*\n\n"
                "I'm successfully running on *Render.com*!\n\n"
                "Send me any message and I'll echo it back!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in welcome handler: {e}")

    @bot.message_handler(func=lambda message: True)
    def echo_all(message):
        """رد على جميع الرسائل"""
        try:
            bot.reply_to(
                message,
                f"📝 You said: `{message.text}`\n\n"
                "✅ Bot is working!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in echo handler: {e}")

# التشغيل المحلي (للتجربة فقط)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)