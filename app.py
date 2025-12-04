import os
import sys
import time
import json
import logging
import threading
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template_string

# إعدادات التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# تهيئة Flask
app = Flask(__name__)

# التوكن والحصول عليه من متغيرات البيئة
BOT_TOKEN = os.getenv('BOT_TOKEN', '8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0')
PORT = int(os.getenv('PORT', 10000))

# الحصول على عنوان URL من Render
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else f"https://telegram-bot.onrender.com"
# إعدادات التطبيق
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# ============================================================================
# استيراد مكتبة Telegram Bot
# ============================================================================
try:
    import telebot
    from telebot import types
    from telebot.util import quick_markup
    
    # تهيئة البوت
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
    logger.info("✅ Telebot initialized successfully")
    
except ImportError as e:
    logger.error(f"❌ Failed to import telebot: {e}")
    sys.exit(1)

# ============================================================================
# هياكل البيانات
# ============================================================================

# فئات الحالة
class UserRole:
    CUSTOMER = 'customer'
    DRIVER = 'driver'
    ADMIN = 'admin'

class RideStatus:
    PENDING = 'pending'          # في انتظار السائق
    ACCEPTED = 'accepted'        # قبلها سائق
    ON_WAY = 'on_way'           # السائق في الطريق
    IN_PROGRESS = 'in_progress'  # العميل في السيارة
    COMPLETED = 'completed'      # انتهت
    CANCELLED = 'cancelled'      # ألغيت
    NO_DRIVERS = 'no_drivers'   # لا يوجد سائقين

class PaymentStatus:
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'

# تخزين البيانات (في الإنتاج استخدم قاعدة بيانات)
users = {}              # {user_id: user_data}
rides = {}              # {ride_id: ride_data}
drivers_available = {}  # {driver_id: last_seen}
notifications = {}      # {user_id: [notifications]}
user_states = {}        # {user_id: state_data}
statistics = {
    'total_rides': 0,
    'completed_rides': 0,
    'active_users': 0,
    'active_drivers': 0
}

# ============================================================================
# دوال المساعدة
# ============================================================================

def save_data():
    """حفظ البيانات في ملف (مؤقت للإنتاج الحقيقي استخدم قاعدة بيانات)"""
    try:
        data = {
            'users': users,
            'rides': rides,
            'drivers_available': drivers_available,
            'statistics': statistics
        }
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def load_data():
    """تحميل البيانات من الملف"""
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            users.update(data.get('users', {}))
            rides.update(data.get('rides', {}))
            drivers_available.update(data.get('drivers_available', {}))
            statistics.update(data.get('statistics', {}))
    except FileNotFoundError:
        logger.info("No data file found, starting fresh")
    except Exception as e:
        logger.error(f"Error loading data: {e}")

def generate_ride_id():
    """إنشاء معرف فريد للرحلة"""
    return f"R{int(time.time())}{random.randint(1000, 9999)}"

def generate_user_id():
    """إنشاء معرف فريد للمستخدم"""
    return f"U{int(time.time())}{random.randint(100, 999)}"

def calculate_fare(distance_km, ride_type='economy'):
    """حساب تكلفة الرحلة"""
    base_fares = {
        'economy': 5,
        'comfort': 8,
        'premium': 12,
        'van': 15
    }
    base = base_fares.get(ride_type, 5)
    return round(base + (distance_km * 2), 2)

def format_time(timestamp):
    """تنسيق الوقت"""
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return str(timestamp)

def format_location(lat, lon):
    """تنسيق الموقع"""
    return f"📍 https://maps.google.com/?q={lat},{lon}"

def get_main_menu(user_id):
    """الحصول على القائمة الرئيسية بناءً على دور المستخدم"""
    user = users.get(user_id, {})
    role = user.get('role')
    
    if role == UserRole.CUSTOMER:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('🚖 طلب رحلة جديدة'),
            types.KeyboardButton('📍 إرسال موقعي', request_location=True)
        )
        markup.add(
            types.KeyboardButton('📋 رحلاتي'),
            types.KeyboardButton('💳 محفظتي')
        )
        markup.add(
            types.KeyboardButton('⚙️ إعدادات الحساب'),
            types.KeyboardButton('📞 الدعم')
        )
        return markup
        
    elif role == UserRole.DRIVER:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        if user_id in drivers_available:
            markup.add(types.KeyboardButton('🔴 إيقاف الخدمة'))
        else:
            markup.add(types.KeyboardButton('🟢 بدء الخدمة'))
        markup.add(
            types.KeyboardButton('📊 الرحلات النشطة'),
            types.KeyboardButton('💰 أرباحي')
        )
        markup.add(
            types.KeyboardButton('📋 سجل الرحلات'),
            types.KeyboardButton('⚙️ إعدادات السائق')
        )
        markup.add(types.KeyboardButton('📞 الدعم'))
        return markup
    
    else:
        # قائمة افتراضية
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton('🏠 القائمة الرئيسية'))
        return markup

def send_notification(user_id, message, markup=None):
    """إرسال إشعار للمستخدم"""
    try:
        if markup:
            bot.send_message(user_id, message, reply_markup=markup)
        else:
            bot.send_message(user_id, message)
        return True
    except Exception as e:
        logger.error(f"Failed to send notification to {user_id}: {e}")
        return False

def notify_nearby_drivers(ride):
    """إرسال إشعار للسائقين القريبين"""
    drivers_notified = 0
    
    for driver_id, last_seen in drivers_available.items():
        # تحقق إذا كان السائق نشط (آخر ظهور خلال 5 دقائق)
        if time.time() - last_seen > 300:  # 5 دقائق
            continue
            
        driver = users.get(driver_id, {})
        if driver.get('role') != UserRole.DRIVER:
            continue
            
        # حساب المسافة (في الإنتاج استخدم API خرائط حقيقي)
        distance = random.uniform(0.5, 5.0)  # كيلومتر
        
        if distance <= 10:  # سائق ضمن 10 كيلومتر
            fare = calculate_fare(distance)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "✅ قبول الرحلة",
                    callback_data=f"accept_ride:{ride['id']}"
                ),
                types.InlineKeyboardButton(
                    "❌ رفض",
                    callback_data=f"reject_ride:{ride['id']}"
                )
            )
            
            message = f"""
🚖 <b>طلب رحلة جديد بالقرب منك!</b>

📍 <b>المسافة:</b> {distance:.1f} كم
💰 <b>التكلفة المقدرة:</b> {fare} ريال
👤 <b>العميل:</b> {ride['customer_name']}

⏰ <b>الوقت:</b> {format_time(ride['created_at'])}
            """
            
            if send_notification(driver_id, message, markup):
                drivers_notified += 1
    
    return drivers_notified

def update_ride_status(ride_id, new_status):
    """تحديث حالة الرحلة"""
    if ride_id in rides:
        rides[ride_id]['status'] = new_status
        rides[ride_id]['updated_at'] = time.time()
        
        # إرسال إشعارات للمستخدمين المعنيين
        ride = rides[ride_id]
        
        status_messages = {
            RideStatus.ACCEPTED: "✅ تم قبول رحلتك من قبل السائق",
            RideStatus.ON_WAY: "🚗 السائق في طريقه إليك",
            RideStatus.IN_PROGRESS: "👥 بدأت الرحلة",
            RideStatus.COMPLETED: "🏁 تم إكمال الرحلة بنجاح",
            RideStatus.CANCELLED: "❌ تم إلغاء الرحلة"
        }
        
        if new_status in status_messages:
            # إشعار العميل
            send_notification(
                ride['customer_id'],
                f"{status_messages[new_status]}\nرقم الرحلة: {ride_id}"
            )
            
            # إشعار السائق إذا كان موجوداً
            if 'driver_id' in ride:
                send_notification(
                    ride['driver_id'],
                    f"📢 تم تحديث حالة الرحلة {ride_id} إلى: {new_status}"
                )
        
        save_data()
        return True
    return False

# ============================================================================
# صفحات الويب (لوحة التحكم)
# ============================================================================

@app.route('/')
def dashboard():
    """لوحة التحكم الرئيسية"""
    template = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🚖 لوحة تحكم بوت النقل</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            
            header {
                background: white;
                border-radius: 15px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                text-align: center;
            }
            
            h1 {
                color: #667eea;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .stat-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                transition: transform 0.3s;
            }
            
            .stat-card:hover {
                transform: translateY(-5px);
            }
            
            .stat-value {
                font-size: 2.5em;
                font-weight: bold;
                color: #4CAF50;
                margin: 10px 0;
            }
            
            .stat-label {
                color: #666;
                font-size: 1.1em;
            }
            
            .section {
                background: white;
                border-radius: 15px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            
            .section-title {
                color: #667eea;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #f0f0f0;
            }
            
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: #4CAF50;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                margin: 5px;
                transition: background 0.3s;
            }
            
            .btn:hover {
                background: #45a049;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            
            th, td {
                padding: 15px;
                text-align: right;
                border-bottom: 1px solid #eee;
            }
            
            th {
                background: #f8f9fa;
                color: #667eea;
                font-weight: bold;
            }
            
            .status-badge {
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: bold;
            }
            
            .status-pending { background: #fff3cd; color: #856404; }
            .status-accepted { background: #d4edda; color: #155724; }
            .status-completed { background: #d1ecf1; color: #0c5460; }
            .status-cancelled { background: #f8d7da; color: #721c24; }
            
            .ride-actions {
                display: flex;
                gap: 10px;
            }
            
            .action-btn {
                padding: 5px 10px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 0.9em;
            }
            
            .action-view { background: #007bff; color: white; }
            .action-cancel { background: #dc3545; color: white; }
            
            footer {
                text-align: center;
                margin-top: 40px;
                color: white;
                opacity: 0.8;
            }
            
            @media (max-width: 768px) {
                .stats-grid {
                    grid-template-columns: 1fr;
                }
                
                th, td {
                    padding: 10px;
                    font-size: 0.9em;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🚖 لوحة تحكم بوت النقل</h1>
                <p>نظام إدارة طلبات النقل - الإصدار 2.0</p>
            </header>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{{ stats.total_rides }}</div>
                    <div class="stat-label">إجمالي الرحلات</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ stats.completed_rides }}</div>
                    <div class="stat-label">رحلات مكتملة</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ stats.active_users }}</div>
                    <div class="stat-label">مستخدمين نشطين</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ stats.active_drivers }}</div>
                    <div class="stat-label">سائقين نشطين</div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">🎯 إحصائيات النظام</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                    <div>
                        <h3>👥 المستخدمين</h3>
                        <p>إجمالي المسجلين: {{ total_users }}</p>
                        <p>العملاء: {{ customers_count }}</p>
                        <p>السائقين: {{ drivers_count }}</p>
                    </div>
                    <div>
                        <h3>🚖 الرحلات</h3>
                        <p>نشطة الآن: {{ active_rides_count }}</p>
                        <p>في انتظار: {{ pending_rides_count }}</p>
                        <p>مكتملة اليوم: {{ today_completed }}</p>
                    </div>
                    <div>
                        <h3>💰 المالية</h3>
                        <p>إجمالي الإيرادات: {{ total_revenue }} ر.س</p>
                        <p>متوسط الرحلة: {{ avg_fare }} ر.س</p>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">📋 الرحلات النشطة</h2>
                <table>
                    <thead>
                        <tr>
                            <th>رقم الرحلة</th>
                            <th>العميل</th>
                            <th>السائق</th>
                            <th>الحالة</th>
                            <th>التكلفة</th>
                            <th>الوقت</th>
                            <th>الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for ride in active_rides %}
                        <tr>
                            <td>{{ ride.id[:8] }}...</td>
                            <td>{{ ride.customer_name }}</td>
                            <td>{{ ride.driver_name if ride.driver_name else 'لا يوجد' }}</td>
                            <td>
                                <span class="status-badge status-{{ ride.status }}">
                                    {{ ride.status }}
                                </span>
                            </td>
                            <td>{{ ride.fare if ride.fare else 'غير محدد' }} ر.س</td>
                            <td>{{ ride.time_ago }}</td>
                            <td>
                                <div class="ride-actions">
                                    <button class="action-btn action-view">عرض</button>
                                    <button class="action-btn action-cancel">إلغاء</button>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2 class="section-title">⚙️ الإجراءات السريعة</h2>
                <div>
                    <a href="/health" class="btn">🩺 فحص الصحة</a>
                    <a href="/users" class="btn">👥 إدارة المستخدمين</a>
                    <a href="/rides" class="btn">🚖 إدارة الرحلات</a>
                    <a href="/settings" class="btn">⚙️ الإعدادات</a>
                    <a href="/logs" class="btn">📋 السجلات</a>
                </div>
            </div>
            
            <footer>
                <p>© 2024 بوت النقل الذكي | الإصدار 2.0 | تم التطوير بـ Python + Flask</p>
                <p>آخر تحديث: {{ current_time }}</p>
            </footer>
        </div>
        
        <script>
            // تحديث الإحصائيات كل 30 ثانية
            function updateStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.querySelectorAll('.stat-value')[0].textContent = data.total_rides;
                        document.querySelectorAll('.stat-value')[1].textContent = data.completed_rides;
                        document.querySelectorAll('.stat-value')[2].textContent = data.active_users;
                        document.querySelectorAll('.stat-value')[3].textContent = data.active_drivers;
                    });
            }
            
            // تحديث كل 30 ثانية
            setInterval(updateStats, 30000);
            
            // تحديث وقت الرحلات
            function updateRideTimes() {
                document.querySelectorAll('.time-ago').forEach(el => {
                    const timestamp = el.dataset.timestamp;
                    const timeAgo = getTimeAgo(timestamp);
                    el.textContent = timeAgo;
                });
            }
            
            function getTimeAgo(timestamp) {
                const seconds = Math.floor((new Date() - new Date(timestamp * 1000)) / 1000);
                if (seconds < 60) return 'الآن';
                const minutes = Math.floor(seconds / 60);
                if (minutes < 60) return `قبل ${minutes} دقيقة`;
                const hours = Math.floor(minutes / 60);
                if (hours < 24) return `قبل ${hours} ساعة`;
                const days = Math.floor(hours / 24);
                return `قبل ${days} يوم`;
            }
        </script>
    </body>
    </html>
    '''
    
    # جمع البيانات للإحصائيات
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # حساب الإحصائيات
    total_users = len(users)
    customers_count = sum(1 for u in users.values() if u.get('role') == UserRole.CUSTOMER)
    drivers_count = sum(1 for u in users.values() if u.get('role') == UserRole.DRIVER)
    
    # الرحلات النشطة
    active_rides = []
    for ride_id, ride in rides.items():
        if ride['status'] in [RideStatus.PENDING, RideStatus.ACCEPTED, RideStatus.ON_WAY, RideStatus.IN_PROGRESS]:
            time_ago = datetime.fromtimestamp(ride['created_at']).strftime('%H:%M')
            active_rides.append({
                'id': ride_id,
                'customer_name': ride['customer_name'],
                'driver_name': ride.get('driver_name', ''),
                'status': ride['status'],
                'fare': ride.get('fare'),
                'time_ago': time_ago
            })
    
    # الإحصائيات الأخرى
    active_rides_count = len(active_rides)
    pending_rides_count = sum(1 for r in rides.values() if r['status'] == RideStatus.PENDING)
    today_completed = sum(1 for r in rides.values() if r['status'] == RideStatus.COMPLETED and 
                          datetime.fromtimestamp(r.get('completed_at', 0)).date() == datetime.now().date())
    
    # حساب الإيرادات
    total_revenue = sum(r.get('fare', 0) for r in rides.values() if r['status'] == RideStatus.COMPLETED)
    avg_fare = round(total_revenue / max(1, statistics['completed_rides']), 2)
    
    # تحديث إحصائيات النظام
    statistics['active_users'] = sum(1 for u in users.values() if time.time() - u.get('last_seen', 0) < 3600)
    statistics['active_drivers'] = len([d for d in drivers_available if time.time() - drivers_available[d] < 300])
    
    return render_template_string(template,
        stats=statistics,
        total_users=total_users,
        customers_count=customers_count,
        drivers_count=drivers_count,
        active_rides=active_rides,
        active_rides_count=active_rides_count,
        pending_rides_count=pending_rides_count,
        today_completed=today_completed,
        total_revenue=total_revenue,
        avg_fare=avg_fare,
        current_time=current_time
    )

@app.route('/health')
def health_check():
    """فحص صحة النظام"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '2.0',
        'stats': statistics,
        'users_count': len(users),
        'rides_count': len(rides),
        'active_drivers': len(drivers_available),
        'uptime': time.time() - app_start_time
    })

@app.route('/api/stats')
def api_stats():
    """واجهة برمجة التطبيقات للإحصائيات"""
    return jsonify(statistics)

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة نهاية ويب هوك"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ============================================================================
# معالجات البوت الأساسية
# ============================================================================

@app.before_first_request
def initialize():
    """تهيئة التطبيق"""
    global app_start_time
    app_start_time = time.time()
    load_data()
    logger.info("Application initialized successfully")

@bot.message_handler(commands=['start', 'menu'])
def start_command(message):
    """معالج أمر /start"""
    user_id = str(message.from_user.id)
    username = message.from_user.first_name
    
    # إنشاء المستخدم إذا لم يكن موجوداً
    if user_id not in users:
        users[user_id] = {
            'id': user_id,
            'username': username,
            'full_name': f"{message.from_user.first_name} {message.from_user.last_name or ''}",
            'phone': None,
            'role': None,
            'balance': 0.0,
            'rating': 5.0,
            'total_rides': 0,
            'created_at': time.time(),
            'last_seen': time.time(),
            'settings': {
                'notifications': True,
                'language': 'ar',
                'payment_method': 'cash'
            }
        }
        save_data()
    
    # تحديث آخر ظهور
    users[user_id]['last_seen'] = time.time()
    
    # التحقق إذا كان المستخدم مسجلاً بالفعل
    if users[user_id]['role']:
        bot.send_message(
            message.chat.id,
            f"مرحباً بعودتك {username}! 👋\n\n"
            f"دورك: {'👤 عميل' if users[user_id]['role'] == UserRole.CUSTOMER else '🚖 سائق'}\n\n"
            "اختر من القائمة أدناه:",
            reply_markup=get_main_menu(user_id)
        )
    else:
        # عرض اختيار الدور
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('👤 عميل'),
            types.KeyboardButton('🚖 سائق')
        )
        
        bot.send_message(
            message.chat.id,
            f"أهلاً وسهلاً {username}! 👋\n\n"
            "🚖 <b>مرحباً بك في بوت النقل الذكي</b>\n\n"
            "خدمتنا توفر لك:\n"
            "• 🚗 رحلات سريعة وآمنة\n"
            "• 📍 تتبع مباشر للرحلة\n"
            "• 💳 دفع إلكتروني آمن\n"
            "• ⭐ تقييمات موثوقة\n\n"
            "الرجاء اختيار دورك للبدء:",
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: message.text in ['👤 عميل', '🚖 سائق'])
def handle_role_selection(message):
    """معالجة اختيار الدور"""
    user_id = str(message.from_user.id)
    selected_role = UserRole.CUSTOMER if message.text == '👤 عميل' else UserRole.DRIVER
    
    if user_id in users:
        users[user_id]['role'] = selected_role
        users[user_id]['last_seen'] = time.time()
        save_data()
        
        if selected_role == UserRole.CUSTOMER:
            response = (
                "✅ <b>تم التسجيل كعميل بنجاح!</b>\n\n"
                "🎉 يمكنك الآن:\n"
                "• 🚖 طلب رحلة جديدة\n"
                "• 📍 إرسال موقعك\n"
                "• 💳 شحن رصيدك\n"
                "• 📋 متابعة رحلاتك\n\n"
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
    else:
        bot.send_message(message.chat.id, "الرجاء استخدام /start أولاً")

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة جديدة')
def request_new_ride(message):
    """طلب رحلة جديدة"""
    user_id = str(message.from_user.id)
    
    if user_id not in users or users[user_id]['role'] != UserRole.CUSTOMER:
        bot.send_message(message.chat.id, "الرجاء التسجيل كعميل أولاً")
        return
    
    # حفظ حالة المستخدم
    user_states[user_id] = {
        'action': 'request_ride',
        'step': 'waiting_for_location'
    }
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('📍 إرسال موقعي', request_location=True))
    markup.add(types.KeyboardButton('❌ إلغاء'))
    
    bot.send_message(
        message.chat.id,
        "📍 <b>طلب رحلة جديدة</b>\n\n"
        "الرجاء إرسال موقعك الحالي للبدء:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '🟢 بدء الخدمة')
def start_driver_service(message):
    """بدء خدمة السائق"""
    user_id = str(message.from_user.id)
    
    if user_id not in users or users[user_id]['role'] != UserRole.DRIVER:
        bot.send_message(message.chat.id, "الرجاء التسجيل كسائق أولاً")
        return
    
    drivers_available[user_id] = time.time()
    users[user_id]['last_seen'] = time.time()
    save_data()
    
    bot.send_message(
        message.chat.id,
        "✅ <b>تم تفعيل وضع السائق بنجاح!</b>\n\n"
        "🎯 أنت الآن تستقبل طلبات الركوب.\n"
        "📱 سيتم إعلامك بطلبات جديدة تلقائياً.\n\n"
        "لإيقاف الخدمة، اضغط '🔴 إيقاف الخدمة'",
        reply_markup=get_main_menu(user_id)
    )

@bot.message_handler(func=lambda message: message.text == '🔴 إيقاف الخدمة')
def stop_driver_service(message):
    """إيقاف خدمة السائق"""
    user_id = str(message.from_user.id)
    
    if user_id in drivers_available:
        del drivers_available[user_id]
        save_data()
    
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
    
    if user_id in user_states and user_states[user_id]['action'] == 'request_ride':
        # حفظ موقع العميل
        users[user_id]['last_location'] = {
            'lat': location.latitude,
            'lon': location.longitude,
            'timestamp': time.time()
        }
        
        # إنشاء رحلة جديدة
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
            'fare': None,
            'driver_id': None,
            'driver_name': None,
            'created_at': time.time(),
            'updated_at': time.time(),
            'ride_type': 'economy',
            'payment_status': PaymentStatus.PENDING,
            'notes': ''
        }
        
        # تحديث الإحصائيات
        statistics['total_rides'] += 1
        save_data()
        
        # إرسال إشعار للسائقين القريبين
        drivers_notified = notify_nearby_drivers(rides[ride_id])
        
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
            rides[ride_id]['status'] = RideStatus.NO_DRIVERS
        
        # تنظيف حالة المستخدم
        del user_states[user_id]
        
        bot.send_message(
            message.chat.id,
            response,
            reply_markup=get_main_menu(user_id)
        )
    else:
        # تحديث موقع المستخدم العام
        if user_id in users:
            users[user_id]['last_location'] = {
                'lat': location.latitude,
                'lon': location.longitude,
                'timestamp': time.time()
            }
            save_data()
            
            bot.send_message(
                message.chat.id,
                f"📍 <b>تم تحديث موقعك</b>\n\n"
                f"الإحداثيات: {location.latitude:.4f}, {location.longitude:.4f}",
                reply_markup=get_main_menu(user_id)
            )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """معالجة استعلامات الرد"""
    user_id = str(call.from_user.id)
    data = call.data
    
    try:
        if data.startswith('accept_ride:'):
            # قبول الرحلة
            ride_id = data.split(':')[1]
            
            if ride_id in rides and rides[ride_id]['status'] == RideStatus.PENDING:
                # تحديث الرحلة
                rides[ride_id]['status'] = RideStatus.ACCEPTED
                rides[ride_id]['driver_id'] = user_id
                rides[ride_id]['driver_name'] = users[user_id]['username']
                rides[ride_id]['updated_at'] = time.time()
                
                # حساب التكلفة
                if rides[ride_id]['fare'] is None:
                    distance = random.uniform(1, 10)
                    rides[ride_id]['fare'] = calculate_fare(distance)
                
                # إشعار العميل
                customer_id = rides[ride_id]['customer_id']
                send_notification(
                    customer_id,
                    f"✅ <b>تم قبول رحلتك!</b>\n\n"
                    f"🚖 <b>السائق:</b> {users[user_id]['username']}\n"
                    f"💰 <b>التكلفة:</b> {rides[ride_id]['fare']} ريال\n"
                    f"📍 <b>رقم الرحلة:</b> {ride_id}\n\n"
                    "سيصل السائق إلى موقعك خلال دقائق ⏰"
                )
                
                # إشعار السائق
                pickup = rides[ride_id]['pickup_location']
                bot.answer_callback_query(call.id, "✅ تم قبول الرحلة")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🚗 بدء الرحلة", callback_data=f"start_ride:{ride_id}"),
                    types.InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_ride:{ride_id}")
                )
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=(
                        f"✅ <b>قبلت الرحلة بنجاح!</b>\n\n"
                        f"👤 <b>العميل:</b> {rides[ride_id]['customer_name']}\n"
                        f"📍 <b>موقع العميل:</b>\n"
                        f"• خط العرض: {pickup['lat']:.4f}\n"
                        f"• خط الطول: {pickup['lon']:.4f}\n"
                        f"💰 <b>التكلفة:</b> {rides[ride_id]['fare']} ريال\n\n"
                        f"⏰ <b>الوقت:</b> {format_time(time.time())}"
                    ),
                    reply_markup=markup
                )
                
                save_data()
                
        elif data.startswith('start_ride:'):
            # بدء الرحلة
            ride_id = data.split(':')[1]
            
            if ride_id in rides and rides[ride_id]['driver_id'] == user_id:
                rides[ride_id]['status'] = RideStatus.ON_WAY
                rides[ride_id]['updated_at'] = time.time()
                
                # إشعار العميل
                customer_id = rides[ride_id]['customer_id']
                send_notification(
                    customer_id,
                    f"🚗 <b>السائق في طريقه إليك!</b>\n\n"
                    f"📍 <b>رقم الرحلة:</b> {ride_id}\n"
                    "استعد للرحلة، سيصل السائق قريباً ⏰"
                )
                
                bot.answer_callback_query(call.id, "🚗 بدأت الرحلة")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=call.message.text + "\n\n✅ بدأت الرحلة"
                )
                
                save_data()
                
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ، حاول مرة أخرى")

@bot.message_handler(func=lambda message: message.text == '📋 رحلاتي')
def show_my_rides(message):
    """عرض رحلات المستخدم"""
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        bot.send_message(message.chat.id, "الرجاء التسجيل أولاً")
        return
    
    user_rides = []
    for ride_id, ride in rides.items():
        if ride['customer_id'] == user_id or ride.get('driver_id') == user_id:
            user_rides.append({
                'id': ride_id,
                'status': ride['status'],
                'fare': ride.get('fare'),
                'created_at': ride['created_at'],
                'role': 'customer' if ride['customer_id'] == user_id else 'driver'
            })
    
    if not user_rides:
        bot.send_message(message.chat.id, "📭 لا توجد رحلات سابقة")
        return
    
    # ترتيب الرحلات من الأحدث إلى الأقدم
    user_rides.sort(key=lambda x: x['created_at'], reverse=True)
    
    response = "📋 <b>رحلاتك السابقة</b>\n\n"
    for i, ride in enumerate(user_rides[:10], 1):  # عرض آخر 10 رحلات
        status_icons = {
            RideStatus.PENDING: '⏳',
            RideStatus.ACCEPTED: '✅',
            RideStatus.ON_WAY: '🚗',
            RideStatus.IN_PROGRESS: '👥',
            RideStatus.COMPLETED: '🏁',
            RideStatus.CANCELLED: '❌'
        }
        
        icon = status_icons.get(ride['status'], '📝')
        role = '👤' if ride['role'] == 'customer' else '🚖'
        fare = f"💰 {ride['fare']} ر.س" if ride['fare'] else ""
        time_str = format_time(ride['created_at'])
        
        response += f"{i}. {icon} {role} <b>{ride['id'][:8]}...</b>\n"
        response += f"   📍 {ride['status']} {fare}\n"
        response += f"   ⏰ {time_str}\n\n"
    
    bot.send_message(message.chat.id, response)

# ============================================================================
# معالجات أخرى
# ============================================================================

@bot.message_handler(func=lambda message: message.text == '⚙️ إعدادات الحساب')
def account_settings(message):
    """إعدادات الحساب"""
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        bot.send_message(message.chat.id, "الرجاء التسجيل أولاً")
        return
    
    user = users[user_id]
    role_icon = '👤' if user['role'] == UserRole.CUSTOMER else '🚖'
    role_text = 'عميل' if user['role'] == UserRole.CUSTOMER else 'سائق'
    
    response = (
        f"⚙️ <b>إعدادات حسابك</b>\n\n"
        f"{role_icon} <b>الدور:</b> {role_text}\n"
        f"👤 <b>الاسم:</b> {user['username']}\n"
        f"📱 <b>رقم الهاتف:</b> {user['phone'] or 'غير محدد'}\n"
        f"💰 <b>الرصيد:</b> {user['balance']} ريال\n"
        f"⭐ <b>التقييم:</b> {user['rating']}/5.0\n"
        f"🚖 <b>الرحلات:</b> {user.get('total_rides', 0)}\n\n"
        f"📅 <b>تاريخ التسجيل:</b> {format_time(user['created_at'])}\n"
        f"🕒 <b>آخر ظهور:</b> {format_time(user['last_seen'])}"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📱 تغيير الهاتف", callback_data="change_phone"),
        types.InlineKeyboardButton("🔔 الإشعارات", callback_data="notifications")
    )
    
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '💳 محفظتي')
def wallet_info(message):
    """معلومات المحفظة"""
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        bot.send_message(message.chat.id, "الرجاء التسجيل أولاً")
        return
    
    user = users[user_id]
    
    response = (
        f"💳 <b>محفظتك المالية</b>\n\n"
        f"💰 <b>الرصيد الحالي:</b> {user['balance']} ريال\n"
        f"📊 <b>إجمالي الرحلات:</b> {user.get('total_rides', 0)}\n"
        f"💵 <b>إجمالي المصروفات:</b> {user.get('total_spent', 0)} ريال\n\n"
        f"📅 <b>آخر تحديث:</b> {format_time(time.time())}"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💰 شحن الرصيد", callback_data="charge_wallet"),
        types.InlineKeyboardButton("📋 كشف الحساب", callback_data="transaction_history")
    )
    
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📞 الدعم')
def support_info(message):
    """معلومات الدعم"""
    response = (
        "📞 <b>الدعم الفني والمساعدة</b>\n\n"
        "🕒 <b>ساعات العمل:</b> 24/7\n"
        "📱 <b>واتساب:</b> +966500000000\n"
        "📧 <b>البريد:</b> support@transport-bot.com\n\n"
        "📍 <b>للشكاوى والاقتراحات:</b>\n"
        "• مشاكل في الحساب\n"
        "• استرجاع مدفوعات\n"
        "• اقتراحات تحسين\n"
        "• تقارير أخطاء\n\n"
        "⏰ <b>وقت الرد:</b> خلال 24 ساعة"
    )
    
    bot.send_message(message.chat.id, response)

# ============================================================================
# أوامر الإدارة
# ============================================================================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """لوحة التحكم الإدارية"""
    user_id = str(message.from_user.id)
    
    if user_id not in ADMIN_IDS and user_id not in ['YOUR_ADMIN_ID']:  # ضع معرفك هنا
        bot.send_message(message.chat.id, "⛔ غير مصرح لك بالوصول")
        return
    
    response = (
        "🛠️ <b>لوحة التحكم الإدارية</b>\n\n"
        f"👥 <b>إجمالي المستخدمين:</b> {len(users)}\n"
        f"🚖 <b>إجمالي الرحلات:</b> {len(rides)}\n"
        f"💰 <b>إجمالي الإيرادات:</b> {sum(r.get('fare', 0) for r in rides.values() if r['status'] == RideStatus.COMPLETED)} ريال\n\n"
        f"📊 <b>إحصائيات النظام:</b>\n"
        f"• الرحلات النشطة: {sum(1 for r in rides.values() if r['status'] in [RideStatus.PENDING, RideStatus.ACCEPTED, RideStatus.ON_WAY])}\n"
        f"• السائقين المتاحين: {len(drivers_available)}\n"
        f"• العملاء النشطين: {sum(1 for u in users.values() if u['role'] == UserRole.CUSTOMER and time.time() - u['last_seen'] < 3600)}\n\n"
        f"🕒 <b>وقت التشغيل:</b> {int((time.time() - app_start_time) / 3600)} ساعة"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📊 إحصائيات كاملة", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")
    )
    markup.add(
        types.InlineKeyboardButton("🚖 إدارة الرحلات", callback_data="admin_rides"),
        types.InlineKeyboardButton("💰 التقارير المالية", callback_data="admin_finance")
    )
    
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """عرض إحصائيات البوت"""
    response = (
        "📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 <b>المستخدمين:</b> {len(users)}\n"
        f"🚖 <b>الرحلات:</b> {len(rides)}\n"
        f"✅ <b>مكتملة:</b> {sum(1 for r in rides.values() if r['status'] == RideStatus.COMPLETED)}\n"
        f"⏳ <b>نشطة:</b> {sum(1 for r in rides.values() if r['status'] in [RideStatus.PENDING, RideStatus.ACCEPTED, RideStatus.ON_WAY])}\n\n"
        f"💰 <b>إجمالي الإيرادات:</b> {sum(r.get('fare', 0) for r in rides.values() if r['status'] == RideStatus.COMPLETED)} ريال\n"
        f"⭐ <b>متوسط التقييم:</b> {sum(u.get('rating', 5) for u in users.values()) / max(1, len(users)):.1f}/5.0\n\n"
        f"🕒 <b>وقت التشغيل:</b> {int((time.time() - app_start_time) / 3600)} ساعة"
    )
    
    bot.send_message(message.chat.id, response)

# ============================================================================
# وظائف الخلفية
# ============================================================================

def cleanup_inactive_users():
    """تنظيف المستخدمين غير النشطين"""
    while True:
        try:
            current_time = time.time()
            users_to_remove = []
            
            for user_id, user in users.items():
                # حذف المستخدمين غير النشطين لأكثر من 30 يوم
                if current_time - user.get('last_seen', 0) > 2592000:  # 30 يوم
                    users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                # حذف من قائمة السائقين النشطين
                if user_id in drivers_available:
                    del drivers_available[user_id]
                # حذف المستخدم
                del users[user_id]
            
            if users_to_remove:
                logger.info(f"Cleaned up {len(users_to_remove)} inactive users")
                save_data()
            
            time.sleep(3600)  # تشغيل كل ساعة
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            time.sleep(300)

def check_stuck_rides():
    """فحص الرحلات العالقة"""
    while True:
        try:
            current_time = time.time()
            
            for ride_id, ride in rides.items():
                # إذا كانت الرحلة معلقة لأكثر من 30 دقيقة
                if ride['status'] == RideStatus.PENDING and current_time - ride['created_at'] > 1800:
                    # محاولة إعادة إرسال الإشعارات
                    drivers_notified = notify_nearby_drivers(ride)
                    
                    if drivers_notified == 0:
                        rides[ride_id]['status'] = RideStatus.NO_DRIVERS
                        # إشعار العميل
                        send_notification(
                            ride['customer_id'],
                            f"⚠️ <b>انتهت مدة البحث عن سائق</b>\n\n"
                            f"رقم الرحلة: {ride_id}\n"
                            "لم نتمكن من العثور على سائق متاح.\n"
                            "الرجاء المحاولة مرة أخرى لاحقاً."
                        )
            
            save_data()
            time.sleep(300)  # تشغيل كل 5 دقائق
            
        except Exception as e:
            logger.error(f"Error checking stuck rides: {e}")
            time.sleep(60)

# ============================================================================
# نقطة التشغيل الرئيسية
# ============================================================================

if __name__ == '__main__':
    # تحميل البيانات
    load_data()
    
    # بدء خيوط الخلفية
    cleanup_thread = threading.Thread(target=cleanup_inactive_users, daemon=True)
    stuck_rides_thread = threading.Thread(target=check_stuck_rides, daemon=True)
    
    cleanup_thread.start()
    stuck_rides_thread.start()
    
    logger.info("🚀 Starting Telegram Transport Bot v2.0")
    logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}/webhook")
    logger.info(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    
    # تعيين ويب هوك
    try:
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook set: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")
    
    # تشغيل Flask (للتجربة المحلية)
    # في Render سيتم تشغيله عبر gunicorn
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)