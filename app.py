import telebot
from telebot import types
from flask import Flask, request, jsonify
import os
import logging
import time

# تكوين السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تهيئة Flask app
app = Flask(__name__)

# التوكن - قم بتغييره إلى التوكن الخاص بك
BOT_TOKEN = "8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0"  # ضع التوكن هنا
webhook_url = f"{WEBHOOK_URL}/webhook"
        result = bot.set_webhook(url=webhook_url)

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN)

# تخزين البيانات
user_data = {}
rides = {}
ride_requests = []
drivers_available = {}
USER_STATES = {}

class UserRole:
    CUSTOMER = 'customer'
    DRIVER = 'driver'

class RideStatus:
    REQUESTED = 'requested'
    ACCEPTED = 'accepted'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🚖 بوت وسيل للنقل</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
                padding: 20px;
                direction: rtl;
            }
            
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            header {
                text-align: center;
                margin-bottom: 40px;
            }
            
            h1 {
                font-size: 3em;
                margin-bottom: 10px;
                background: linear-gradient(45deg, #fff, #f0f0f0);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            .subtitle {
                font-size: 1.2em;
                opacity: 0.9;
                margin-bottom: 30px;
            }
            
            .status-card {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 30px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .status-card h3 {
                font-size: 1.5em;
                margin-bottom: 15px;
                color: #fff;
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }
            
            .stat-item {
                background: rgba(255, 255, 255, 0.1);
                padding: 15px;
                border-radius: 10px;
                text-align: center;
            }
            
            .stat-value {
                font-size: 1.8em;
                font-weight: bold;
                margin-bottom: 5px;
                color: #4CAF50;
            }
            
            .stat-label {
                font-size: 0.9em;
                opacity: 0.8;
            }
            
            .actions {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 30px;
            }
            
            .btn {
                display: block;
                padding: 15px;
                background: linear-gradient(45deg, #4CAF50, #45a049);
                color: white;
                text-decoration: none;
                border-radius: 10px;
                text-align: center;
                font-weight: bold;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
            }
            
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
                background: linear-gradient(45deg, #45a049, #3d8b40);
            }
            
            .btn-secondary {
                background: linear-gradient(45deg, #2196F3, #1976D2);
            }
            
            .btn-secondary:hover {
                background: linear-gradient(45deg, #1976D2, #1565C0);
            }
            
            .btn-danger {
                background: linear-gradient(45deg, #f44336, #d32f2f);
            }
            
            .btn-danger:hover {
                background: linear-gradient(45deg, #d32f2f, #c62828);
            }
            
            .info {
                background: rgba(255, 255, 255, 0.05);
                padding: 20px;
                border-radius: 10px;
                margin-top: 30px;
                font-size: 0.9em;
                border-right: 4px solid #4CAF50;
            }
            
            .bot-info {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 20px;
                margin-top: 20px;
            }
            
            .bot-avatar {
                width: 80px;
                height: 80px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2em;
            }
            
            .bot-details {
                text-align: right;
            }
            
            footer {
                margin-top: 40px;
                text-align: center;
                opacity: 0.7;
                font-size: 0.9em;
                padding-top: 20px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            @media (max-width: 600px) {
                .container {
                    padding: 20px;
                }
                
                h1 {
                    font-size: 2em;
                }
                
                .stats {
                    grid-template-columns: 1fr;
                }
                
                .actions {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="bot-info">
                    <div class="bot-avatar">🚖</div>
                    <div class="bot-details">
                        <h1>بوت وسيل للنقل</h1>
                        <p class="subtitle">خدمة نقل ذكية - آمنة - سريعة</p>
                    </div>
                </div>
            </header>
            
            <div class="status-card">
                <h3>📊 حالة النظام</h3>
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value">🟢</div>
                        <div class="stat-label">الحالة</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">''' + str(len(user_data)) + '''</div>
                        <div class="stat-label">المستخدمون</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">''' + str(len(drivers_available)) + '''</div>
                        <div class="stat-label">سائقون متاحون</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">''' + str(len([r for r in rides.values() if r['status'] in ['requested', 'accepted']])) + '''</div>
                        <div class="stat-label">رحلات نشطة</div>
                    </div>
                </div>
            </div>
            
            <div class="actions">
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="/health" class="btn btn-secondary">🩺 فحص الصحة</a>
                <a href="/remove_webhook" class="btn btn-danger">🗑️ إزالة ويب هوك</a>
                <a href="https://t.me/''' + (bot.get_me().username if bot.get_me() else 'BotFather') + '''" target="_blank" class="btn btn-secondary">💬 فتح البوت</a>
            </div>
            
            <div class="info">
                <h4>📝 معلومات البوت:</h4>
                <p>• اسم البوت: ''' + (bot.get_me().first_name if bot.get_me() else 'غير متصل') + '''</p>
                <p>• معرف البوت: @''' + (bot.get_me().username if bot.get_me() else 'غير متوفر') + '''</p>
                <p>• رابط الويب هوك: ''' + WEBHOOK_URL + '''/webhook</p>
                <p>• آخر تحديث: ''' + time.strftime("%Y-%m-%d %H:%M:%S") + '''</p>
            </div>
            
            <div class="info">
                <h4>🎯 تعليمات التشغيل:</h4>
                <p>1. تأكد من تعيين التوكن الصحيح في السطر 21</p>
                <p>2. اضغط "تعيين ويب هوك" لتفعيل البوت</p>
                <p>3. افتح البوت في تلجرام وابدأ الاستخدام</p>
                <p>4. راقب حالة النظام من هذه الصفحة</p>
            </div>
            
            <footer>
                <p>© 2024 بوت وسيل للنقل | تم التطوير باستخدام Python + Flask + pyTelegramBotAPI</p>
                <p>PythonAnywhere Hosting | mohammedieke.pythonanywhere.com</p>
            </footer>
        </div>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        webhook_info = bot.get_webhook_info()
        
        return '''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <title>✅ تم تعيين الويب هوك</title>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container {
                    background: rgba(255,255,255,0.1);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 600px;
                    margin: 0 auto;
                }
                .success {
                    font-size: 3em;
                    margin-bottom: 20px;
                }
                .btn {
                    display: inline-block;
                    padding: 10px 20px;
                    background: white;
                    color: #667eea;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>تم تعيين الويب هوك بنجاح!</h1>
                <p><strong>الرابط:</strong> %s</p>
                <p><strong>الحالة:</strong> %s</p>
                <p><strong>آخر خطأ:</strong> %s</p>
                <br>
                <a href="/" class="btn">🏠 العودة للرئيسية</a>
                <a href="https://t.me/%s" target="_blank" class="btn">💬 فتح البوت</a>
            </div>
        </body>
        </html>
        ''' % (
            webhook_info.url,
            'نشط' if webhook_info.url else 'غير نشط',
            webhook_info.last_error_message or 'لا يوجد أخطاء',
            bot.get_me().username if bot.get_me() else 'BotFather'
        )
    except Exception as e:
        return '''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <title>❌ فشل تعيين الويب هوك</title>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
                    color: white;
                }
                .container {
                    background: rgba(255,255,255,0.1);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 600px;
                    margin: 0 auto;
                }
                .error {
                    font-size: 3em;
                    margin-bottom: 20px;
                }
                .btn {
                    display: inline-block;
                    padding: 10px 20px;
                    background: white;
                    color: #ff416c;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌</div>
                <h1>فشل تعيين الويب هوك</h1>
                <p><strong>الخطأ:</strong> %s</p>
                <br>
                <a href="/" class="btn">🏠 العودة للرئيسية</a>
            </div>
        </body>
        </html>
        ''' % str(e)

@app.route('/remove_webhook', methods=['GET'])
def remove_webhook():
    try:
        bot.remove_webhook()
        return '''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <title>✅ تم إزالة الويب هوك</title>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                    color: white;
                }
                .container {
                    background: rgba(255,255,255,0.1);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 600px;
                    margin: 0 auto;
                }
                .success {
                    font-size: 3em;
                    margin-bottom: 20px;
                }
                .btn {
                    display: inline-block;
                    padding: 10px 20px;
                    background: white;
                    color: #4CAF50;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>تم إزالة الويب هوك بنجاح</h1>
                <p>تم إلغاء تفعيل الويب هوك بنجاح.</p>
                <br>
                <a href="/" class="btn">🏠 العودة للرئيسية</a>
                <a href="/set_webhook" class="btn">⚙️ إعادة التعيين</a>
            </div>
        </body>
        </html>
        '''
    except Exception as e:
        return str(e), 500

@app.route('/health')
def health():
    try:
        bot_info = bot.get_me()
        webhook_info = bot.get_webhook_info()
        
        return jsonify({
            'status': 'healthy',
            'bot': {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name
            },
            'webhook': {
                'url': webhook_info.url,
                'has_custom_certificate': webhook_info.has_custom_certificate,
                'pending_update_count': webhook_info.pending_update_count,
                'last_error_date': webhook_info.last_error_date,
                'last_error_message': webhook_info.last_error_message
            },
            'stats': {
                'users': len(user_data),
                'drivers_available': len(drivers_available),
                'active_rides': len([r for r in rides.values() if r['status'] in ['requested', 'accepted']]),
                'total_rides': len(rides)
            },
            'timestamp': time.time(),
            'server_time': time.strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# معالجات البوت الأساسية
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    # حفظ بيانات المستخدم
    if user_id not in user_data:
        user_data[user_id] = {
            'id': user_id,
            'username': username,
            'role': None,
            'phone': None,
            'location': None,
            'joined': time.time()
        }
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('👤 عميل', '🚖 سائق')
    
    bot.send_message(
        message.chat.id,
        f"🚖 *مرحباً {username} في بوت وسيل!*\n\n"
        "خدمة نقل ذكية توفر لك:\n"
        "• 🚗 رحلات سريعة وآمنة\n"
        "• 📍 تتبع مباشر\n"
        "• 💳 دفع إلكتروني\n"
        "• ⭐ تقييمات موثوقة\n\n"
        "*الرجاء اختيار دورك:*",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text in ['👤 عميل', '🚖 سائق'])
def handle_role(message):
    user_id = message.from_user.id
    role = 'customer' if message.text == '👤 عميل' else 'driver'
    
    if user_id in user_data:
        user_data[user_id]['role'] = role
    
    if role == 'customer':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('📍 إرسال موقعي', request_location=True)
        markup.add('🚖 طلب رحلة', '📋 رحلاتي')
        markup.add('⚙️ الإعدادات', '❓ المساعدة')
        
        bot.send_message(
            message.chat.id,
            f"✅ *تم التسجيل كعميل*\n\n"
            "يمكنك الآن:\n"
            "1. إرسال موقعك\n"
            "2. طلب رحلة\n"
            "3. متابعة رحلاتك\n\n"
            "اضغط '📍 إرسال موقعي' للبدء",
            parse_mode='Markdown',
            reply_markup=markup
        )
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('🟢 توفير الخدمة', '🔴 إيقاف الخدمة')
        markup.add('📊 الرحلات النشطة', '📋 سجل الرحلات')
        markup.add('⚙️ إعدادات السائق', '❓ المساعدة')
        
        bot.send_message(
            message.chat.id,
            f"✅ *تم التسجيل كسائق*\n\n"
            "يمكنك الآن:\n"
            "1. تفعيل خدمة الاستقبال\n"
            "2. استقبال طلبات الركوب\n"
            "3. متابعة رحلاتك\n\n"
            "اضغط '🟢 توفير الخدمة' للبدء",
            parse_mode='Markdown',
            reply_markup=markup
        )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🚖 *بوت وسيل - دليل المساعدة*

*للعملاء:*
📍 إرسال موقعي - تحديد موقعك الحالي
🚖 طلب رحلة - طلب رحلة جديدة
📋 رحلاتي - عرض الرحلات السابقة

*للسائقين:*
🟢 توفير الخدمة - تفعيل وضع الاستقبال
🔴 إيقاف الخدمة - إيقاف استقبال الطلبات
📊 الرحلات النشطة - عرض الرحلات الجارية

*أوامر عامة:*
/start - إعادة التشغيل
/help - عرض هذه الرسالة
/cancel - إلغاء العملية الحالية

*الدعم الفني:*
للإبلاغ عن مشاكل أو اقتراحات، راسل الدعم.
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(content_types=['location'])
def handle_location(message):
    user_id = message.from_user.id
    location = message.location
    
    if user_id in user_data:
        user_data[user_id]['location'] = {
            'lat': location.latitude,
            'lon': location.longitude
        }
        
        bot.send_message(
            message.chat.id,
            f"📍 *تم تحديد موقعك بنجاح!*\n\n"
            f"الإحداثيات:\n"
            f"• خط العرض: `{location.latitude}`\n"
            f"• خط الطول: `{location.longitude}`\n\n"
            "يمكنك الآن طلب رحلة.",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة')
def request_ride(message):
    user_id = message.from_user.id
    
    if user_id not in user_data or 'location' not in user_data[user_id]:
        bot.send_message(
            message.chat.id,
            "⚠️ *الرجاء تحديد موقعك أولاً*\n\n"
            "استخدم زر '📍 إرسال موقعي' لتحديد موقعك الحالي.",
            parse_mode='Markdown'
        )
        return
    
    # إنشاء طلب رحلة
    ride_id = len(rides) + 1
    ride = {
        'id': ride_id,
        'customer_id': user_id,
        'customer_name': user_data[user_id]['username'],
        'pickup': user_data[user_id]['location'],
        'destination': None,
        'status': 'requested',
        'created_at': time.time(),
        'driver_id': None,
        'driver_name': None
    }
    
    rides[ride_id] = ride
    ride_requests.append(ride_id)
    
    # البحث عن سائق متاح
    available_driver = None
    for driver_id, is_available in drivers_available.items():
        if is_available:
            available_driver = driver_id
            break
    
    if available_driver:
        # إعلام السائق
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ قبول الرحلة", callback_data=f"accept_{ride_id}"),
            types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_{ride_id}")
        )
        
        bot.send_message(
            available_driver,
            f"🚖 *طلب رحلة جديد #{ride_id}*\n\n"
            f"👤 العميل: {user_data[user_id]['username']}\n"
            f"📍 الموقع: {ride['pickup']['lat']:.4f}, {ride['pickup']['lon']:.4f}\n\n"
            f"⏰ الوقت: {time.strftime('%H:%M:%S')}",
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        bot.send_message(
            message.chat.id,
            f"✅ *تم إرسال طلبك #{ride_id}*\n\n"
            "جاري البحث عن سائق قريب...",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            message.chat.id,
            f"✅ *تم إرسال طلبك #{ride_id}*\n\n"
            "⚠️ لا يوجد سائقين متاحين حالياً.\n"
            "سيتم إعلامك عند توفر سائق.",
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data.startswith('accept_'):
        ride_id = int(data.split('_')[1])
        ride = rides.get(ride_id)
        
        if ride:
            ride['status'] = 'accepted'
            ride['driver_id'] = chat_id
            ride['driver_name'] = user_data.get(chat_id, {}).get('username', 'سائق')
            
            # تحديث حالة السائق
            drivers_available[chat_id] = False
            
            # إعلام العميل
            bot.send_message(
                ride['customer_id'],
                f"✅ *تم قبول رحلتك #{ride_id}*\n\n"
                f"🚖 السائق: {ride['driver_name']}\n"
                f"📞 رقم السائق: سيظهر قريباً\n\n"
                "سيصل السائق إلى موقعك خلال دقائق.",
                parse_mode='Markdown'
            )
            
            # إعلام السائق
            bot.answer_callback_query(call.id, "✅ تم قبول الرحلة")
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"✅ *قبلت الرحلة #{ride_id}*\n\n"
                     f"👤 العميل: {ride['customer_name']}\n"
                     f"📍 توجه إلى موقع العميل",
                parse_mode='Markdown'
            )
    
    elif data.startswith('reject_'):
        ride_id = int(data.split('_')[1])
        bot.answer_callback_query(call.id, "❌ تم رفض الرحلة")
        bot.delete_message(chat_id, call.message.message_id)

# تشغيل التطبيق
if __name__ == '__main__':
    print("🚀 بدء تشغيل بوت وسيل على PythonAnywhere...")
    print(f"🌐 الرابط: {WEBHOOK_URL}")
    print(f"🔗 ويب هوك: {WEBHOOK_URL}/webhook")
    
    try:
        bot_info = bot.get_me()
        print(f"✅ البوت: @{bot_info.username}")
        print(f"👤 الاسم: {bot_info.first_name}")
        
        # تعيين الويب هوك تلقائياً
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        print(f"✅ تم تعيين الويب هوك: {webhook_url}")
        
        # تشغيل Flask (للتجربة المحلية فقط)
        # على PythonAnywhere سيتم تشغيله عبر WSGI
        app.run(debug=True)
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        print("\n🔧 الحلول:")
        print("1. تأكد من صحة التوكن")
        print("2. تحقق من اتصال الإنترنت")
        print(f"3. تأكد من أن البوت موجود على @BotFather")