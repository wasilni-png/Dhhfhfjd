"""
🚖 بوت النقل الذكي - إصدار Render
تم التطوير خصيصاً ليعمل على Render.com
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import telebot
from telebot import types

# ============================================================================
# إعدادات أساسية لـ Render
# ============================================================================

# إعدادات التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# الحصول على متغيرات البيئة من Render
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN غير معين في متغيرات البيئة!")
    BOT_TOKEN = "8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0"  # توكن احتياطي

PORT = int(os.getenv('PORT', 10000))
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://your-app.onrender.com"

# تهيئة Flask
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'render-telegram-bot-secret-2024')

# تهيئة البوت
try:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
    logger.info("✅ تم تهيئة البوت بنجاح")
except Exception as e:
    logger.error(f"❌ فشل تهيئة البوت: {e}")
    raise

# ============================================================================
# هياكل البيانات
# ============================================================================

# فئات الحالة
class UserRole:
    CUSTOMER = 'customer'
    DRIVER = 'driver'

class RideStatus:
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    ON_WAY = 'on_way'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

# تخزين البيانات (سيتم حفظها في JSON)
users_db_file = 'users.json'
rides_db_file = 'rides.json'

def load_json(file_path):
    """تحميل بيانات من ملف JSON"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"خطأ في تحميل {file_path}: {e}")
        return {}

def save_json(data, file_path):
    """حفظ بيانات إلى ملف JSON"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ {file_path}: {e}")
        return False

# تحميل البيانات
users = load_json(users_db_file)
rides = load_json(rides_db_file)
active_drivers = load_json('drivers.json')

# إحصائيات النظام
stats = {
    'total_rides': len(rides),
    'completed_rides': sum(1 for r in rides.values() if r.get('status') == RideStatus.COMPLETED),
    'total_users': len(users),
    'active_drivers': len(active_drivers),
    'start_time': time.time()
}

# ============================================================================
# دوال المساعدة
# ============================================================================

def save_all_data():
    """حفظ جميع البيانات"""
    save_json(users, users_db_file)
    save_json(rides, rides_db_file)
    save_json(active_drivers, 'drivers.json')
    logger.debug("💾 تم حفظ البيانات")

def get_main_menu(user_id):
    """الحصول على القائمة الرئيسية"""
    user = users.get(user_id, {})
    role = user.get('role')
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if role == UserRole.CUSTOMER:
        markup.add(
            types.KeyboardButton('🚖 طلب رحلة'),
            types.KeyboardButton('📍 إرسال موقعي', request_location=True)
        )
        markup.add(
            types.KeyboardButton('📋 رحلاتي'),
            types.KeyboardButton('⚙️ إعدادات')
        )
    elif role == UserRole.DRIVER:
        if user_id in active_drivers:
            markup.add(types.KeyboardButton('🔴 إيقاف الخدمة'))
        else:
            markup.add(types.KeyboardButton('🟢 بدء الخدمة'))
        markup.add(
            types.KeyboardButton('📊 الرحلات النشطة'),
            types.KeyboardButton('💰 أرباحي')
        )
    else:
        markup.add(
            types.KeyboardButton('👤 عميل'),
            types.KeyboardButton('🚖 سائق')
        )
    
    markup.add(types.KeyboardButton('📞 المساعدة'))
    return markup

def generate_ride_id():
    """إنشاء معرف فريد للرحلة"""
    return f"R{int(time.time())}{os.urandom(2).hex()}"

# ============================================================================
# صفحات الويب (لـ Render)
# ============================================================================

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🚖 بوت النقل الذكي</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
                padding: 20px;
                text-align: center;
            }
            
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            }
            
            h1 {
                font-size: 2.5em;
                margin-bottom: 20px;
                background: linear-gradient(45deg, #fff, #f0f0f0);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin: 30px 0;
            }
            
            .stat-card {
                background: rgba(255, 255, 255, 0.2);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            
            .stat-value {
                font-size: 2em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px;
                font-weight: bold;
                transition: all 0.3s;
            }
            
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
            
            .info {
                background: rgba(0, 0, 0, 0.1);
                padding: 15px;
                border-radius: 10px;
                margin-top: 30px;
                text-align: right;
            }
            
            @media (max-width: 600px) {
                .container {
                    padding: 20px;
                }
                
                .stats {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚖 بوت النقل الذكي</h1>
            <p>نظام متكامل لإدارة طلبات النقل</p>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value">''' + str(stats['total_users']) + '''</div>
                    <div>👥 المستخدمين</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">''' + str(stats['total_rides']) + '''</div>
                    <div>🚖 الرحلات</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">''' + str(stats['active_drivers']) + '''</div>
                    <div>🚕 السائقين</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">''' + str(stats['completed_rides']) + '''</div>
                    <div>✅ مكتملة</div>
                </div>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="/health" class="btn">🩺 فحص الصحة</a>
                <a href="/admin" class="btn">🛠️ لوحة التحكم</a>
            </div>
            
            <div class="info">
                <h3>📋 معلومات النظام:</h3>
                <p>• المنصة: Render.com</p>
                <p>• الخادم: ''' + str(PORT) + '''</p>
                <p>• العنوان: ''' + WEBHOOK_URL + '''</p>
                <p>• البوت: @''' + (bot.get_me().username if bot.get_me() else "غير متصل") + '''</p>
                <p>• الوقت: ''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '''</p>
            </div>
            
            <div style="margin-top: 30px; font-size: 0.9em; opacity: 0.8;">
                <p>© 2024 بوت النقل الذكي | Render.com | Python + Flask + Telebot</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook_route():
    """تعيين ويب هوك"""
    try:
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = bot.set_webhook(url=webhook_url)
        
        return jsonify({
            'success': True,
            'message': 'تم تعيين الويب هوك بنجاح',
            'webhook_url': webhook_url,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """فحص صحة النظام"""
    try:
        bot_info = bot.get_me()
        bot_status = {
            'id': bot_info.id,
            'username': bot_info.username,
            'first_name': bot_info.first_name
        }
    except:
        bot_status = {'status': 'غير متصل'}
    
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'uptime': time.time() - stats['start_time'],
        'bot': bot_status,
        'stats': stats,
        'webhook': WEBHOOK_URL + '/webhook',
        'python_version': sys.version.split()[0]
    })

@app.route('/admin')
def admin_panel():
    """لوحة التحكم الإدارية"""
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <title>🛠️ لوحة التحكم</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 20px;
                background: #2c3e50;
                color: white;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
            }
            .card {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                margin: 10px 0;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 10px;
                border: 1px solid rgba(255,255,255,0.2);
                text-align: right;
            }
            .btn {
                padding: 8px 16px;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                margin: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛠️ لوحة التحكم الإدارية</h1>
            
            <div class="card">
                <h3>🚀 إجراءات سريعة</h3>
                <button class="btn" onclick="location.reload()">🔄 تحديث</button>
                <button class="btn" onclick="window.location='/set_webhook'">⚙️ إعادة تعيين ويب هوك</button>
                <button class="btn" onclick="window.location='/health'">🩺 فحص الصحة</button>
                <button class="btn" onclick="saveData()">💾 حفظ البيانات</button>
            </div>
            
            <div class="card">
                <h3>📊 إحصائيات النظام</h3>
                <div id="stats"></div>
            </div>
            
            <div class="card">
                <h3>👥 المستخدمين النشطين</h3>
                <div id="users"></div>
            </div>
            
            <div class="card">
                <h3>🚖 الرحلات النشطة</h3>
                <div id="rides"></div>
            </div>
        </div>
        
        <script>
            async function loadStats() {
                const response = await fetch('/health');
                const data = await response.json();
                
                document.getElementById('stats').innerHTML = `
                    <p>👥 المستخدمين: ${data.stats.total_users}</p>
                    <p>🚖 الرحلات: ${data.stats.total_rides}</p>
                    <p>✅ المكتملة: ${data.stats.completed_rides}</p>
                    <p>🚕 السائقين: ${data.stats.active_drivers}</p>
                    <p>⏰ وقت التشغيل: ${Math.floor(data.uptime / 3600)} ساعة</p>
                `;
                
                // تحميل المستخدمين
                const users = ''' + json.dumps(list(users.values())[:10], ensure_ascii=False) + ''';
                let usersHtml = '<table><tr><th>ID</th><th>الاسم</th><th>الدور</th><th>آخر ظهور</th></tr>';
                users.forEach(user => {
                    const time = new Date(user.last_seen * 1000).toLocaleString('ar-SA');
                    usersHtml += `<tr>
                        <td>${user.id.substring(0, 8)}...</td>
                        <td>${user.username}</td>
                        <td>${user.role === 'customer' ? '👤 عميل' : '🚖 سائق'}</td>
                        <td>${time}</td>
                    </tr>`;
                });
                usersHtml += '</table>';
                document.getElementById('users').innerHTML = usersHtml;
                
                // تحميل الرحلات
                const rides = ''' + json.dumps(list(rides.values())[:10], ensure_ascii=False) + ''';
                let ridesHtml = '<table><tr><th>رقم الرحلة</th><th>العميل</th><th>الحالة</th><th>الوقت</th></tr>';
                rides.forEach(ride => {
                    const time = new Date(ride.created_at * 1000).toLocaleString('ar-SA');
                    let status = '';
                    switch(ride.status) {
                        case 'pending': status = '⏳ في الانتظار'; break;
                        case 'accepted': status = '✅ مقبولة'; break;
                        case 'completed': status = '🏁 مكتملة'; break;
                        default: status = ride.status;
                    }
                    ridesHtml += `<tr>
                        <td>${ride.id.substring(0, 8)}...</td>
                        <td>${ride.customer_name}</td>
                        <td>${status}</td>
                        <td>${time}</td>
                    </tr>`;
                });
                ridesHtml += '</table>';
                document.getElementById('rides').innerHTML = ridesHtml;
            }
            
            function saveData() {
                fetch('/api/save_data')
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message);
                    });
            }
            
            // تحميل البيانات عند فتح الصفحة
            loadStats();
            // تحديث كل 30 ثانية
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    '''

@app.route('/api/save_data')
def api_save_data():
    """واجهة لحفظ البيانات"""
    try:
        save_all_data()
        return jsonify({'success': True, 'message': 'تم حفظ البيانات بنجاح'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة نهاية ويب هوك"""
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK', 200
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return 'Error', 500
    return 'Bad Request', 400

# ============================================================================
# معالجات البوت الأساسية
# ============================================================================

@bot.message_handler(commands=['start', 'menu'])
def start_command(message):
    """بدء البوت"""
    user_id = str(message.from_user.id)
    username = message.from_user.first_name
    
    # إنشاء مستخدم جديد إذا لم يكن موجوداً
    if user_id not in users:
        users[user_id] = {
            'id': user_id,
            'username': username,
            'full_name': f"{message.from_user.first_name} {message.from_user.last_name or ''}",
            'phone': None,
            'role': None,
            'balance': 0.0,
            'rating': 5.0,
            'created_at': time.time(),
            'last_seen': time.time(),
            'total_rides': 0
        }
        stats['total_users'] = len(users)
        save_all_data()
    
    # تحديث وقت آخر ظهور
    users[user_id]['last_seen'] = time.time()
    
    if users[user_id]['role']:
        # إذا كان المستخدم مسجلاً بالفعل
        bot.send_message(
            message.chat.id,
            f"مرحباً بعودتك {username}! 👋\n\n"
            f"دورك: {'👤 عميل' if users[user_id]['role'] == UserRole.CUSTOMER else '🚖 سائق'}\n"
            f"رصيدك: {users[user_id]['balance']} ريال\n"
            f"تقييمك: {users[user_id]['rating']}/5.0\n\n"
            "اختر من القائمة:",
            reply_markup=get_main_menu(user_id)
        )
    else:
        # اختيار الدور للمستخدم الجديد
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('👤 عميل'),
            types.KeyboardButton('🚖 سائق')
        )
        
        bot.send_message(
            message.chat.id,
            f"أهلاً وسهلاً {username}! 👋\n\n"
            "🚖 <b>مرحباً بك في بوت النقل الذكي</b>\n\n"
            "خدمة نقل ذكية توفر لك:\n"
            "• 🚗 رحلات سريعة وآمنة\n"
            "• 📍 تتبع مباشر للرحلة\n"
            "• 💳 دفع إلكتروني آمن\n"
            "• ⭐ تقييمات موثوقة\n\n"
            "الرجاء اختيار دورك للبدء:",
            reply_markup=markup
        )

@bot.message_handler(func=lambda msg: msg.text in ['👤 عميل', '🚖 سائق'])
def handle_role(message):
    """معالجة اختيار الدور"""
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        bot.send_message(message.chat.id, "الرجاء استخدام /start أولاً")
        return
    
    role = UserRole.CUSTOMER if message.text == '👤 عميل' else UserRole.DRIVER
    users[user_id]['role'] = role
    users[user_id]['last_seen'] = time.time()
    
    # حفظ البيانات
    save_all_data()
    
    if role == UserRole.CUSTOMER:
        response = (
            "✅ <b>تم التسجيل كعميل بنجاح!</b>\n\n"
            "🎉 يمكنك الآن:\n"
            "• 🚖 طلب رحلة جديدة\n"
            "• 📍 إرسال موقعك الحالي\n"
            "• 📋 متابعة رحلاتك\n"
            "• ⚙️ تعديل إعداداتك\n\n"
            "استخدم القائمة أدناه للبدء 👇"
        )
    else:
        response = (
            "✅ <b>تم التسجيل كسائق بنجاح!</b>\n\n"
            "🎉 يمكنك الآن:\n"
            "• 🟢 بدء استقبال الطلبات\n"
            "• 📊 عرض الرحلات النشطة\n"
            "• 💰 متابعة أرباحك\n"
            "• ⭐ تحسين تقييمك\n\n"
            "استخدم القائمة أدناه للبدء 👇"
        )
    
    bot.send_message(
        message.chat.id,
        response,
        reply_markup=get_main_menu(user_id)
    )

@bot.message_handler(func=lambda msg: msg.text == '🚖 طلب رحلة')
def request_ride(message):
    """طلب رحلة جديدة"""
    user_id = str(message.from_user.id)
    
    if user_id not in users or users[user_id]['role'] != UserRole.CUSTOMER:
        bot.send_message(message.chat.id, "الرجاء التسجيل كعميل أولاً")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('📍 إرسال موقعي', request_location=True))
    markup.add('❌ إلغاء')
    
    bot.send_message(
        message.chat.id,
        "📍 <b>طلب رحلة جديدة</b>\n\n"
        "الرجاء إرسال موقعك الحالي للبدء:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == '🟢 بدء الخدمة')
def start_driver_service(message):
    """بدء خدمة السائق"""
    user_id = str(message.from_user.id)
    
    if user_id not in users or users[user_id]['role'] != UserRole.DRIVER:
        bot.send_message(message.chat.id, "الرجاء التسجيل كسائق أولاً")
        return
    
    active_drivers[user_id] = {
        'id': user_id,
        'username': users[user_id]['username'],
        'started_at': time.time(),
        'last_active': time.time()
    }
    
    users[user_id]['last_seen'] = time.time()
    save_all_data()
    
    bot.send_message(
        message.chat.id,
        "✅ <b>تم تفعيل وضع السائق بنجاح!</b>\n\n"
        "🎯 أنت الآن تستقبل طلبات الركوب.\n"
        "📱 سيتم إعلامك بطلبات جديدة تلقائياً.\n\n"
        "لإيقاف الخدمة، اضغط '🔴 إوقف الخدمة'",
        reply_markup=get_main_menu(user_id)
    )

@bot.message_handler(func=lambda msg: msg.text == '🔴 إيقاف الخدمة')
def stop_driver_service(message):
    """إيقاف خدمة السائق"""
    user_id = str(message.from_user.id)
    
    if user_id in active_drivers:
        del active_drivers[user_id]
        save_all_data()
    
    bot.send_message(
        message.chat.id,
        "🔴 <b>تم إيقاف خدمة الاستقبال</b>\n\n"
        "للعودة لاستقبال الطلبات، اضغط '🟢 بدء الخدمة'",
        reply_markup=get_main_menu(user_id)
    )

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع المرسل"""
    user_id = str(message.from_user.id)
    location = message.location
    
    if user_id in users:
        # تحديث موقع المستخدم
        users[user_id]['last_location'] = {
            'lat': location.latitude,
            'lon': location.longitude,
            'timestamp': time.time()
        }
        
        if users[user_id]['role'] == UserRole.CUSTOMER:
            # إنشاء رحلة جديدة للعميل
            ride_id = generate_ride_id()
            rides[ride_id] = {
                'id': ride_id,
                'customer_id': user_id,
                'customer_name': users[user_id]['username'],
                'pickup_location': {
                    'lat': location.latitude,
                    'lon': location.longitude
                },
                'destination': None,
                'status': RideStatus.PENDING,
                'fare': 15.0,  # تكلفة افتراضية
                'driver_id': None,
                'driver_name': None,
                'created_at': time.time(),
                'updated_at': time.time()
            }
            
            stats['total_rides'] = len(rides)
            save_all_data()
            
            # إشعار السائقين المتاحين
            drivers_notified = 0
            for driver_id, driver in active_drivers.items():
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton(
                            "✅ قبول الرحلة",
                            callback_data=f"accept_ride:{ride_id}"
                        )
                    )
                    
                    bot.send_message(
                        driver_id,
                        f"🚖 <b>طلب رحلة جديد!</b>\n\n"
                        f"👤 العميل: {users[user_id]['username']}\n"
                        f"📍 الموقع: {location.latitude:.4f}, {location.longitude:.4f}\n"
                        f"💰 التكلفة: 15.0 ريال\n\n"
                        f"⏰ الوقت: {datetime.now().strftime('%H:%M')}",
                        reply_markup=markup
                    )
                    drivers_notified += 1
                except:
                    continue
            
            # إعلام العميل
            if drivers_notified > 0:
                response = (
                    f"✅ <b>تم إرسال طلبك بنجاح!</b>\n\n"
                    f"📝 <b>رقم الرحلة:</b> {ride_id}\n"
                    f"📍 <b>موقعك:</b> {location.latitude:.4f}, {location.longitude:.4f}\n"
                    f"👥 <b>تم إرسال الطلب لـ {drivers_notified} سائق</b>\n\n"
                    "⏳ جاري البحث عن سائق قريب..."
                )
            else:
                response = (
                    f"⚠️ <b>تم إرسال طلبك</b>\n\n"
                    f"📝 <b>رقم الرحلة:</b> {ride_id}\n"
                    "🔍 <b>لا يوجد سائقين متاحين حالياً</b>\n\n"
                    "سيتم إعلامك عند توفر سائق"
                )
            
            bot.send_message(
                message.chat.id,
                response,
                reply_markup=get_main_menu(user_id)
            )
        else:
            # للسائق: فقط تحديث الموقع
            bot.send_message(
                message.chat.id,
                f"📍 <b>تم تحديث موقعك</b>\n\n"
                f"الإحداثيات: {location.latitude:.4f}, {location.longitude:.4f}",
                reply_markup=get_main_menu(user_id)
            )
    else:
        bot.send_message(message.chat.id, "الرجاء استخدام /start أولاً")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """معالجة استعلامات الرد"""
    try:
        data = call.data
        
        if data.startswith('accept_ride:'):
            ride_id = data.split(':')[1]
            driver_id = str(call.from_user.id)
            
            if ride_id in rides and rides[ride_id]['status'] == RideStatus.PENDING:
                # قبول الرحلة
                rides[ride_id]['status'] = RideStatus.ACCEPTED
                rides[ride_id]['driver_id'] = driver_id
                rides[ride_id]['driver_name'] = users[driver_id]['username']
                rides[ride_id]['updated_at'] = time.time()
                
                # إشعار العميل
                customer_id = rides[ride_id]['customer_id']
                bot.send_message(
                    customer_id,
                    f"✅ <b>تم قبول رحلتك!</b>\n\n"
                    f"🚖 <b>السائق:</b> {users[driver_id]['username']}\n"
                    f"💰 <b>التكلفة:</b> {rides[ride_id]['fare']} ريال\n"
                    f"📍 <b>رقم الرحلة:</b> {ride_id}\n\n"
                    "سيصل السائق إلى موقعك خلال دقائق ⏰"
                )
                
                # إشعار السائق
                bot.answer_callback_query(call.id, "✅ تم قبول الرحلة")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=call.message.text + "\n\n✅ تم قبول الرحلة!"
                )
                
                save_all_data()
                
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ")

@bot.message_handler(func=lambda msg: msg.text == '📋 رحلاتي')
def show_rides(message):
    """عرض رحلات المستخدم"""
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        bot.send_message(message.chat.id, "الرجاء التسجيل أولاً")
        return
    
    user_rides = []
    for ride_id, ride in rides.items():
        if ride['customer_id'] == user_id or ride.get('driver_id') == user_id:
            user_rides.append(ride)
    
    if not user_rides:
        bot.send_message(message.chat.id, "📭 لا توجد رحلات سابقة")
        return
    
    # ترتيب من الأحدث
    user_rides.sort(key=lambda x: x['created_at'], reverse=True)
    
    response = "📋 <b>رحلاتك السابقة</b>\n\n"
    for i, ride in enumerate(user_rides[:5], 1):
        status_icons = {
            RideStatus.PENDING: '⏳',
            RideStatus.ACCEPTED: '✅',
            RideStatus.COMPLETED: '🏁',
            RideStatus.CANCELLED: '❌'
        }
        
        icon = status_icons.get(ride['status'], '📝')
        time_str = datetime.fromtimestamp(ride['created_at']).strftime('%H:%M')
        
        response += f"{i}. {icon} <b>{ride['id'][:8]}...</b>\n"
        response += f"   📍 {ride['status']}\n"
        response += f"   💰 {ride.get('fare', 0)} ريال\n"
        response += f"   ⏰ {time_str}\n\n"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(func=lambda msg: msg.text == '📞 المساعدة')
def show_help(message):
    """عرض رسالة المساعدة"""
    help_text = """
📞 <b>مساعدة بوت النقل</b>

<b>👤 للعملاء:</b>
• استخدم /start للبدء
• اختر "👤 عميل" للتسجيل
• اضغط "🚖 طلب رحلة" لطلب سيارة
• أرسل موقعك عند الطلب

<b>🚖 للسائقين:</b>
• اختر "🚖 سائق" للتسجيل
• اضغط "🟢 بدء الخدمة" للاستقبال
• اضغط "🔴 إيقاف الخدمة" للتوقف

<b>📋 الأوامر:</b>
/start - بدء البوت
/menu - عرض القائمة
/help - هذه الرسالة

<b>📞 الدعم:</b>
للشكاوى والاستفسارات، راسل الدعم الفني.
"""
    
    bot.send_message(message.chat.id, help_text)

# ============================================================================
# التشغيل الرئيسي
# ============================================================================

def initialize_bot():
    """تهيئة البوت عند التشغيل"""
    logger.info("🚀 بدء تشغيل بوت النقل على Render...")
    logger.info(f"🌐 الويب هوك: {WEBHOOK_URL}")
    logger.info(f"🔑 التوكن: {BOT_TOKEN[:10]}...")
    logger.info(f"🚪 البورت: {PORT}")
    
    try:
        bot_info = bot.get_me()
        logger.info(f"✅ البوت: @{bot_info.username}")
        
        # تعيين ويب هوك
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ تم تعيين الويب هوك: {webhook_url}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة البوت: {e}")

# تهيئة البوت عند الاستيراد
initialize_bot()

# نقطة دخول التطبيق (للتشغيل المحلي)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)