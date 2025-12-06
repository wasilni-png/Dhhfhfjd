"""
🚖 بوت النقل الذكي - النسخة المحسنة والمطورة
"""

import os
import logging
import json
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# ============================================================================
# إعدادات أساسية
# ============================================================================

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# الحصول على التوكن من Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN', 8314762629:AAFewIWyTZmANrnkaSyUZHUiDU0NmioJayo')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# تهيئة التطبيق والبوت
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ============================================================================
# فئات ومتغيرات مساعدة
# ============================================================================

class UserState:
    """حالات المستخدم"""
    MAIN_MENU = "main_menu"
    REQUESTING_RIDE = "requesting_ride"
    SETTING_LOCATION = "setting_location"
    WAITING_DRIVER = "waiting_driver"
    IN_RIDE = "in_ride"
    RATE_DRIVER = "rate_driver"

class RideStatus:
    """حالات الرحلة"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    ON_THE_WAY = "on_the_way"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# تخزين مؤقت لحالات المستخدمين
user_states = {}
user_data = {}
ride_requests = {}
active_rides = {}

# ============================================================================
# إدارة قاعدة البيانات
# ============================================================================

class DatabaseManager:
    """مدير قاعدة البيانات"""
    
    def __init__(self):
        self.pool = None
        self.init_pool()
        self.init_tables()
    
    def init_pool(self):
        """تهيئة تجمع الاتصالات"""
        try:
            if DATABASE_URL:
                self.pool = SimpleConnectionPool(1, 10, DATABASE_URL)
            else:
                # استخدام قاعدة بيانات محلية للتطوير
                self.pool = SimpleConnectionPool(
                    1, 10,
                    host="localhost",
                    database="transport_bot",
                    user="postgres",
                    password="postgres"
                )
            logger.info("✅ تم تهيئة تجمع اتصالات قاعدة البيانات")
        except Exception as e:
            logger.error(f"❌ فشل تهيئة قاعدة البيانات: {e}")
            self.pool = None
    
    @contextmanager
    def get_connection(self):
        """الحصول على اتصال من التجمع"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        finally:
            if conn:
                self.pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self):
        """الحصول على مؤشر قاعدة البيانات"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
    
    def init_tables(self):
        """إنشاء الجداول الأساسية"""
        try:
            with self.get_cursor() as cur:
                # جدول المستخدمين
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(50) PRIMARY KEY,
                        username VARCHAR(100),
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        phone VARCHAR(20),
                        role VARCHAR(20),
                        balance DECIMAL(10, 2) DEFAULT 0.0,
                        rating DECIMAL(3, 2) DEFAULT 5.0,
                        total_rides INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # جدول الرحلات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS rides (
                        ride_id VARCHAR(50) PRIMARY KEY,
                        customer_id VARCHAR(50),
                        driver_id VARCHAR(50),
                        pickup_location TEXT,
                        destination TEXT,
                        pickup_lat DECIMAL(10, 6),
                        pickup_lng DECIMAL(10, 6),
                        dest_lat DECIMAL(10, 6),
                        dest_lng DECIMAL(10, 6),
                        status VARCHAR(20),
                        fare DECIMAL(10, 2),
                        distance DECIMAL(10, 2),
                        duration INTEGER,
                        payment_method VARCHAR(20),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        accepted_at TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        cancelled_at TIMESTAMP,
                        customer_rating INTEGER,
                        driver_rating INTEGER,
                        notes TEXT
                    )
                """)
                
                # جدول السائقين النشطين
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_drivers (
                        driver_id VARCHAR(50) PRIMARY KEY,
                        username VARCHAR(100),
                        vehicle_type VARCHAR(50),
                        vehicle_number VARCHAR(50),
                        current_lat DECIMAL(10, 6),
                        current_lng DECIMAL(10, 6),
                        is_available BOOLEAN DEFAULT TRUE,
                        status VARCHAR(50),
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # جدول الدفعات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        payment_id VARCHAR(50) PRIMARY KEY,
                        ride_id VARCHAR(50),
                        user_id VARCHAR(50),
                        amount DECIMAL(10, 2),
                        payment_method VARCHAR(20),
                        status VARCHAR(20),
                        transaction_id VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # إنشاء الفهارس
                cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_customer ON rides(customer_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_driver ON rides(driver_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_active_drivers_available ON active_drivers(is_available)")
                
                logger.info("✅ تم إنشاء/تأكيد الجداول بنجاح")
        except Exception as e:
            logger.error(f"❌ فشل إنشاء الجداول: {e}")
    
    def save_user(self, user_id, username, first_name, last_name="", phone="", role="customer"):
        """حفظ أو تحديث بيانات المستخدم"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, phone, role, last_active)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    phone = EXCLUDED.phone,
                    role = EXCLUDED.role,
                    last_active = CURRENT_TIMESTAMP
                """, (user_id, username, first_name, last_name, phone, role))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ المستخدم: {e}")
            return False
    
    def get_user(self, user_id):
        """الحصول على بيانات مستخدم"""
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات المستخدم: {e}")
            return None
    
    def save_ride(self, ride_data):
        """حفظ رحلة جديدة"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    INSERT INTO rides 
                    (ride_id, customer_id, pickup_location, pickup_lat, pickup_lng, 
                     status, fare, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    ride_data['ride_id'],
                    ride_data['customer_id'],
                    ride_data['pickup_location'],
                    ride_data['pickup_lat'],
                    ride_data['pickup_lng'],
                    RideStatus.PENDING,
                    ride_data.get('fare', 15.0)
                ))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الرحلة: {e}")
            return False
    
    def update_ride_status(self, ride_id, status, driver_id=None):
        """تحديث حالة الرحلة"""
        try:
            with self.get_cursor() as cur:
                query = "UPDATE rides SET status = %s"
                params = [status]
                
                if status == RideStatus.ACCEPTED and driver_id:
                    query += ", driver_id = %s, accepted_at = CURRENT_TIMESTAMP"
                    params.append(driver_id)
                elif status == RideStatus.IN_PROGRESS:
                    query += ", started_at = CURRENT_TIMESTAMP"
                elif status == RideStatus.COMPLETED:
                    query += ", completed_at = CURRENT_TIMESTAMP"
                elif status == RideStatus.CANCELLED:
                    query += ", cancelled_at = CURRENT_TIMESTAMP"
                
                query += " WHERE ride_id = %s"
                params.append(ride_id)
                
                cur.execute(query, params)
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث حالة الرحلة: {e}")
            return False
    
    def get_ride(self, ride_id):
        """الحصول على بيانات رحلة"""
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT * FROM rides WHERE ride_id = %s", (ride_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات الرحلة: {e}")
            return None
    
    def add_active_driver(self, driver_id, username, vehicle_type="سيارة", vehicle_number=""):
        """إضافة سائق نشط"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    INSERT INTO active_drivers (driver_id, username, vehicle_type, vehicle_number, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (driver_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    vehicle_type = EXCLUDED.vehicle_type,
                    vehicle_number = EXCLUDED.vehicle_number,
                    is_available = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                """, (driver_id, username, vehicle_type, vehicle_number))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة سائق نشط: {e}")
            return False
    
    def remove_active_driver(self, driver_id):
        """إزالة سائق من القائمة النشطة"""
        try:
            with self.get_cursor() as cur:
                cur.execute("DELETE FROM active_drivers WHERE driver_id = %s", (driver_id,))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إزالة سائق نشط: {e}")
            return False
    
    def update_driver_location(self, driver_id, lat, lng):
        """تحديث موقع السائق"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    UPDATE active_drivers 
                    SET current_lat = %s, current_lng = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE driver_id = %s
                """, (lat, lng, driver_id))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث موقع السائق: {e}")
            return False
    
    def get_available_drivers(self):
        """الحصول على السائقين المتاحين"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT * FROM active_drivers 
                    WHERE is_available = TRUE
                    ORDER BY updated_at DESC
                    LIMIT 50
                """)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ خطأ في جلب السائقين المتاحين: {e}")
            return []
    
    def get_user_rides(self, user_id, limit=10):
        """الحصول على رحلات المستخدم"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT * FROM rides 
                    WHERE customer_id = %s OR driver_id = %s
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (user_id, user_id, limit))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ خطأ في جلب رحلات المستخدم: {e}")
            return []
    
    def update_user_balance(self, user_id, amount):
        """تحديث رصيد المستخدم"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET balance = balance + %s
                    WHERE user_id = %s
                """, (amount, user_id))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث رصيد المستخدم: {e}")
            return False

# إنشاء كائن قاعدة البيانات
db = DatabaseManager()

# ============================================================================
# دوال مساعدة
# ============================================================================

def calculate_fare(distance_km, duration_min):
    """حساب تكلفة الرحلة"""
    base_fare = 5.0  # رسوم البدء
    per_km = 2.0     # سعر الكيلومتر
    per_min = 0.5    # سعر الدقيقة
    
    fare = base_fare + (distance_km * per_km) + (duration_min * per_min)
    return round(fare, 2)

def create_ride_keyboard(user_type="customer"):
    """إنشاء لوحة مفاتيح حسب نوع المستخدم"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if user_type == "customer":
        buttons = [
            types.KeyboardButton('🚖 طلب رحلة جديدة'),
            types.KeyboardButton('📍 إرسال موقعي', request_location=True),
            types.KeyboardButton('📋 رحلاتي السابقة'),
            types.KeyboardButton('💰 رصيدي'),
            types.KeyboardButton('⚙️ الإعدادات'),
            types.KeyboardButton('📞 الدعم')
        ]
    else:  # driver
        buttons = [
            types.KeyboardButton('🟢 بدء العمل'),
            types.KeyboardButton('🔴 إنهاء العمل'),
            types.KeyboardButton('📍 تحديث موقعي', request_location=True),
            types.KeyboardButton('📊 الرحلات المتاحة'),
            types.KeyboardButton('📋 رحلاتي'),
            types.KeyboardButton('💰 أرباحي'),
            types.KeyboardButton('📞 الدعم')
        ]
    
    markup.add(*buttons)
    return markup

def create_inline_ride_buttons(ride_id):
    """إنشاء أزرار داخلية للرحلة"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    
    buttons = [
        InlineKeyboardButton("✅ قبول الرحلة", callback_data=f"accept_{ride_id}"),
        InlineKeyboardButton("❌ رفض الرحلة", callback_data=f"reject_{ride_id}"),
        InlineKeyboardButton("📍 عرض الموقع", callback_data=f"location_{ride_id}"),
        InlineKeyboardButton("📞 التواصل", callback_data=f"contact_{ride_id}")
    ]
    
    markup.add(*buttons)
    return markup

def create_inline_ride_status_buttons(ride_id):
    """إنشاء أزرار حالة الرحلة"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    
    buttons = [
        InlineKeyboardButton("🚗 وصلت للموقع", callback_data=f"arrived_{ride_id}"),
        InlineKeyboardButton("▶️ بدء الرحلة", callback_data=f"start_{ride_id}"),
        InlineKeyboardButton("✅ إنهاء الرحلة", callback_data=f"complete_{ride_id}"),
        InlineKeyboardButton("❌ إلغاء الرحلة", callback_data=f"cancel_{ride_id}")
    ]
    
    markup.add(*buttons)
    return markup

def get_user_state(user_id):
    """الحصول على حالة المستخدم"""
    return user_states.get(str(user_id), UserState.MAIN_MENU)

def set_user_state(user_id, state):
    """تعيين حالة المستخدم"""
    user_states[str(user_id)] = state

def save_user_data(user_id, key, value):
    """حفظ بيانات المستخدم المؤقتة"""
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {}
    user_data[user_id_str][key] = value

def get_user_data(user_id, key, default=None):
    """الحصول على بيانات المستخدم المؤقتة"""
    return user_data.get(str(user_id), {}).get(key, default)

# ============================================================================
# معالجات البوت الرئيسية
# ============================================================================

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """معالجة أمر البدء"""
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = message.from_user.username or ""
    
    logger.info(f"👋 /start من: {first_name} ({user_id})")
    
    # حفظ بيانات المستخدم في قاعدة البيانات
    db.save_user(user_id, username, first_name)
    
    # تعيين الحالة
    set_user_state(user_id, UserState.MAIN_MENU)
    
    # عرض خيارات التسجيل
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👤 عميل'),
        types.KeyboardButton('🚖 سائق'),
        types.KeyboardButton('📞 المساعدة')
    )
    
    welcome_msg = f"""
🎉 <b>مرحباً {first_name} في بوت النقل الذكي!</b>

🚖 <b>خدمة نقل ذكية توفر لك:</b>
• رحلات سريعة وآمنة
• تتبع مباشر للرحلة
• دفع إلكتروني آمن
• تقييمات موثوقة

📱 <b>اختر دورك للبدء:</b>
    """
    
    bot.send_message(message.chat.id, welcome_msg, reply_markup=markup)
    logger.info(f"✅ تم الترحيب بـ {first_name}")

@bot.message_handler(func=lambda msg: msg.text in ['👤 عميل', '🚖 سائق'])
def handle_role_selection(message):
    """معالجة اختيار الدور"""
    user_id = str(message.from_user.id)
    role_text = message.text
    role = "customer" if role_text == "👤 عميل" else "driver"
    
    logger.info(f"🎭 اختيار دور: {role} من: {user_id}")
    
    # تحديث دور المستخدم في قاعدة البيانات
    db.save_user(user_id, message.from_user.username, 
                message.from_user.first_name, role=role)
    
    # إنشاء القائمة المناسبة
    markup = create_ride_keyboard(role)
    
    role_msg = {
        "customer": "👤 <b>تم تسجيلك كعميل بنجاح!</b>\n\nيمكنك الآن طلب رحلات بسهولة وأمان.",
        "driver": "🚖 <b>تم تسجيلك كسائق بنجاح!</b>\n\nيمكنك الآن بدء العمل واستقبال طلبات الركوب."
    }
    
    bot.send_message(
        message.chat.id,
        role_msg[role] + "\n\n🔧 <b>اختر الخدمة المناسبة:</b>",
        reply_markup=markup
    )
    
    logger.info(f"✅ تم تعيين دور {role} لـ {user_id}")

@bot.message_handler(func=lambda msg: msg.text == '🚖 طلب رحلة جديدة')
def handle_new_ride_request(message):
    """معالجة طلب رحلة جديدة"""
    user_id = str(message.from_user.id)
    
    logger.info(f"🚖 طلب رحلة جديدة من: {user_id}")
    
    # التحقق من أن المستخدم عميل
    user = db.get_user(user_id)
    if not user or user['role'] != 'customer':
        bot.send_message(message.chat.id, "❌ يجب أن تكون مسجلاً كعميل لطلب رحلة.")
        return
    
    set_user_state(user_id, UserState.REQUESTING_RIDE)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton('📍 إرسال موقعي', request_location=True),
        types.KeyboardButton('🏠 استخدام موقع سابق'),
        types.KeyboardButton('رجوع')
    )
    
    bot.send_message(
        message.chat.id,
        "📍 <b>طلب رحلة جديدة</b>\n\n"
        "الرجاء إرسال موقعك الحالي أو استخدام موقع سابق.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == '🟢 بدء العمل')
def handle_driver_start(message):
    """بدء عمل السائق"""
    user_id = str(message.from_user.id)
    
    logger.info(f"🟢 بدء عمل سائق: {user_id}")
    
    # التحقق من أن المستخدم سائق
    user = db.get_user(user_id)
    if not user or user['role'] != 'driver':
        bot.send_message(message.chat.id, "❌ يجب أن تكون مسجلاً كسائق لبدء العمل.")
        return
    
    # إضافة السائق إلى القائمة النشطة
    db.add_active_driver(user_id, user['username'] or user['first_name'])
    
    bot.send_message(
        message.chat.id,
        "✅ <b>تم تفعيل وضع السائق!</b>\n\n"
        "🎯 أنت الآن تستقبل طلبات الركوب تلقائياً.\n"
        "📍 تأكد من تحديث موقعك بانتظام.\n\n"
        "لإيقاف الخدمة، اضغط '🔴 إنهاء العمل'"
    )

@bot.message_handler(func=lambda msg: msg.text == '🔴 إنهاء العمل')
def handle_driver_stop(message):
    """إنهاء عمل السائق"""
    user_id = str(message.from_user.id)
    
    logger.info(f"🔴 إنهاء عمل سائق: {user_id}")
    
    # إزالة السائق من القائمة النشطة
    db.remove_active_driver(user_id)
    
    bot.send_message(
        message.chat.id,
        "🔴 <b>تم إيقاف خدمة الاستقبال</b>\n\n"
        "للعودة لاستقبال الطلبات، اضغط '🟢 بدء العمل'"
    )

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع المرسل"""
    user_id = str(message.from_user.id)
    location = message.location
    user_state = get_user_state(user_id)
    
    logger.info(f"📍 موقع من: {user_id} - {location.latitude}, {location.longitude}")
    
    if user_state == UserState.REQUESTING_RIDE:
        # إنشاء طلب رحلة جديد
        ride_id = f"ride_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        ride_data = {
            'ride_id': ride_id,
            'customer_id': user_id,
            'pickup_location': 'الموقع المرسل',
            'pickup_lat': location.latitude,
            'pickup_lng': location.longitude,
            'fare': 15.0  # سعر افتراضي
        }
        
        # حفظ الرحلة في قاعدة البيانات
        if db.save_ride(ride_data):
            # حفظ بيانات الرحلة مؤقتاً
            save_user_data(user_id, 'current_ride', ride_id)
            save_user_data(user_id, 'pickup_location', {
                'lat': location.latitude,
                'lng': location.longitude
            })
            
            set_user_state(user_id, UserState.WAITING_DRIVER)
            
            # إعلام المستخدم
            bot.send_message(
                message.chat.id,
                "📍 <b>تم استلام موقعك بنجاح!</b>\n\n"
                f"• <b>خط العرض:</b> {location.latitude:.6f}\n"
                f"• <b>خط الطول:</b> {location.longitude:.6f}\n\n"
                "🚖 <b>تم إنشاء طلب رحلة!</b>\n"
                "⏳ جاري البحث عن سائق قريب...",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # البحث عن سائقين متاحين
            available_drivers = db.get_available_drivers()
            
            if available_drivers:
                # إرسال طلب الرحلة للسائقين المتاحين
                for driver in available_drivers:
                    try:
                        # إنشاء أزرار للرد على الطلب
                        markup = create_inline_ride_buttons(ride_id)
                        
                        bot.send_message(
                            driver['driver_id'],
                            f"🚖 <b>طلب رحلة جديد</b>\n\n"
                            f"• <b>العميل:</b> {message.from_user.first_name}\n"
                            f"• <b>المسافة:</b> قريب منك\n"
                            f"• <b>التكلفة:</b> 15 ريال\n\n"
                            f"<b>رقم الرحلة:</b> {ride_id[-8:]}",
                            reply_markup=markup
                        )
                    except Exception as e:
                        logger.error(f"❌ فشل إرسال طلب الرحلة للسائق {driver['driver_id']}: {e}")
                
                logger.info(f"✅ تم إرسال طلب الرحلة {ride_id} لـ {len(available_drivers)} سائق")
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ <b>لا يوجد سائقون متاحون حالياً</b>\n\n"
                    "يرجى المحاولة مرة أخرى لاحقاً.",
                    reply_markup=create_ride_keyboard("customer")
                )
                set_user_state(user_id, UserState.MAIN_MENU)
        else:
            bot.send_message(
                message.chat.id,
                "❌ <b>حدث خطأ في إنشاء الرحلة</b>\n\n"
                "يرجى المحاولة مرة أخرى.",
                reply_markup=create_ride_keyboard("customer")
            )
            set_user_state(user_id, UserState.MAIN_MENU)
    
    elif user_state == UserState.MAIN_MENU:
        # تحديث موقع السائق إذا كان سائقاً
        user = db.get_user(user_id)
        if user and user['role'] == 'driver':
            db.update_driver_location(user_id, location.latitude, location.longitude)
            
            bot.send_message(
                message.chat.id,
                "📍 <b>تم تحديث موقعك بنجاح!</b>\n\n"
                f"• <b>خط العرض:</b> {location.latitude:.6f}\n"
                f"• <b>خط الطول:</b> {location.longitude:.6f}\n\n"
                "✅ <b>تم تحديث موقع السائق</b>",
                reply_markup=create_ride_keyboard("driver")
            )

@bot.message_handler(func=lambda msg: msg.text == '📋 رحلاتي السابقة')
def handle_my_rides(message):
    """عرض رحلات المستخدم السابقة"""
    user_id = str(message.from_user.id)
    
    logger.info(f"📋 طلب رحلات سابقة من: {user_id}")
    
    rides = db.get_user_rides(user_id, limit=5)
    
    if not rides:
        bot.send_message(
            message.chat.id,
            "📭 <b>لا توجد رحلات سابقة</b>",
            reply_markup=create_ride_keyboard("customer")
        )
        return
    
    response = "📋 <b>رحلاتي السابقة</b>\n\n"
    
    for ride in rides:
        status_emoji = {
            'pending': '⏳',
            'accepted': '✅',
            'on_the_way': '🚗',
            'in_progress': '🚖',
            'completed': '🎉',
            'cancelled': '❌'
        }.get(ride['status'], '❓')
        
        created_time = ride['created_at'].strftime('%Y-%m-%d %H:%M') if ride['created_at'] else 'غير معروف'
        
        response += (
            f"{status_emoji} <b>رحلة #{ride['ride_id'][-8:]}</b>\n"
            f"• <b>الحالة:</b> {ride['status']}\n"
            f"• <b>التكلفة:</b> {ride['fare']} ريال\n"
            f"• <b>التاريخ:</b> {created_time}\n"
            f"────────────────────\n"
        )
    
    bot.send_message(
        message.chat.id,
        response,
        reply_markup=create_ride_keyboard("customer")
    )

@bot.message_handler(func=lambda msg: msg.text == '💰 رصيدي')
def handle_balance(message):
    """عرض رصيد المستخدم"""
    user_id = str(message.from_user.id)
    
    user = db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ يجب البدء باستخدام /start أولاً.")
        return
    
    bot.send_message(
        message.chat.id,
        f"💰 <b>رصيدك الحالي:</b> {user.get('balance', 0)} ريال\n\n"
        f"📊 <b>إحصائياتك:</b>\n"
        f"• عدد الرحلات: {user.get('total_rides', 0)}\n"
        f"• تقييمك: {user.get('rating', 5.0)} ⭐",
        reply_markup=create_ride_keyboard("customer")
    )

@bot.message_handler(func=lambda msg: msg.text == '📊 الرحلات المتاحة')
def handle_available_rides(message):
    """عرض الرحلات المتاحة للسائقين"""
    user_id = str(message.from_user.id)
    
    # التحقق من أن المستخدم سائق
    user = db.get_user(user_id)
    if not user or user['role'] != 'driver':
        bot.send_message(message.chat.id, "❌ يجب أن تكون سائقاً لعرض الرحلات المتاحة.")
        return
    
    # الحصول على الرحلات المنتظرة
    # في النسخة الحقيقية، سيكون هناك استعلام خاص
    # هنا نستخدم مثال بسيط
    
    bot.send_message(
        message.chat.id,
        "📊 <b>الرحلات المتاحة حالياً</b>\n\n"
        "🔍 جاري البحث عن رحلات بالقرب منك...\n\n"
        "تأكد من تفعيل وضع '🟢 بدء العمل' وتحديث موقعك.",
        reply_markup=create_ride_keyboard("driver")
    )

@bot.message_handler(func=lambda msg: msg.text == '📞 الدعم' or msg.text == '📞 المساعدة')
def handle_support(message):
    """عرض معلومات الدعم"""
    support_msg = """
📞 <b>مركز المساعدة والدعم</b>

<b>👤 للعملاء:</b>
• استخدم /start للبدء
• اختر '👤 عميل'
• اضغط '🚖 طلب رحلة جديدة'
• أرسل موقعك

<b>🚖 للسائقين:</b>
• اختر '🚖 سائق'
• اضغط '🟢 بدء العمل'
• أرسل موقعك

<b>📋 الأوامر:</b>
/start - بدء البوت
/help - هذه الرسالة

<b>📞 الدعم الفني:</b>
للشكاوى والاستفسارات، تواصل مع:
@support_username
أو راسلنا على:
support@example.com

<b>⏰ ساعات العمل:</b>
24/7
"""
    
    bot.send_message(
        message.chat.id,
        support_msg,
        reply_markup=create_ride_keyboard("customer")
    )

@bot.message_handler(func=lambda msg: msg.text == 'رجوع')
def handle_back(message):
    """العودة للقائمة الرئيسية"""
    user_id = str(message.from_user.id)
    
    user = db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ يجب البدء باستخدام /start أولاً.")
        return
    
    role = user['role']
    set_user_state(user_id, UserState.MAIN_MENU)
    
    markup = create_ride_keyboard(role)
    
    bot.send_message(
        message.chat.id,
        "🔙 <b>تم العودة للقائمة الرئيسية</b>",
        reply_markup=markup
    )

# ============================================================================
# معالجات الاستدعاء (Inline Buttons)
# ============================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """معالجة استدعاء الأزرار"""
    user_id = str(call.from_user.id)
    callback_data = call.data
    
    logger.info(f"🔘 ضغط زر: {callback_data} من: {user_id}")
    
    if callback_data.startswith('accept_'):
        # قبول الرحلة
        ride_id = callback_data.split('_')[1]
        ride = db.get_ride(ride_id)
        
        if ride and ride['status'] == RideStatus.PENDING:
            # تحديث حالة الرحلة
            db.update_ride_status(ride_id, RideStatus.ACCEPTED, user_id)
            
            # إعلام السائق
            bot.answer_callback_query(call.id, "✅ تم قبول الرحلة!")
            bot.edit_message_text(
                f"✅ <b>لقد قبلت الرحلة #{ride_id[-8:]}</b>\n\n"
                f"• <b>العميل:</b> {ride['customer_id'][:8]}...\n"
                f"• <b>التكلفة:</b> {ride['fare']} ريال\n\n"
                f"🚗 توجه الآن إلى موقع العميل.",
                call.message.chat.id,
                call.message.message_id
            )
            
            # إرسال أزرار حالة الرحلة للسائق
            markup = create_inline_ride_status_buttons(ride_id)
            bot.send_message(
                user_id,
                f"🟢 <b>تم قبول الرحلة #{ride_id[-8:]}</b>\n\n"
                f"استخدم الأزرار أدناه لتحديث حالة الرحلة:",
                reply_markup=markup
            )
            
            # إعلام العميل
            try:
                bot.send_message(
                    ride['customer_id'],
                    f"✅ <b>تم العثور على سائق!</b>\n\n"
                    f"🎉 تهانينا! سائقنا في طريقه إليك الآن.\n"
                    f"• <b>رقم الرحلة:</b> {ride_id[-8:]}\n"
                    f"• <b>التكلفة:</b> {ride['fare']} ريال\n\n"
                    f"⏳ الرجاء الانتظار، السائق في الطريق..."
                )
            except Exception as e:
                logger.error(f"❌ فشل إعلام العميل: {e}")
    
    elif callback_data.startswith('reject_'):
        # رفض الرحلة
        ride_id = callback_data.split('_')[1]
        
        bot.answer_callback_query(call.id, "❌ تم رفض الرحلة")
        bot.edit_message_text(
            f"❌ <b>تم رفض الرحلة #{ride_id[-8:]}</b>",
            call.message.chat.id,
            call.message.message_id
        )
    
    elif callback_data.startswith('arrived_'):
        # وصول السائق للموقع
        ride_id = callback_data.split('_')[1]
        ride = db.get_ride(ride_id)
        
        if ride and ride['driver_id'] == user_id:
            bot.answer_callback_query(call.id, "📍 تم تحديث الحالة: وصلت للموقع")
            
            # إعلام العميل
            try:
                bot.send_message(
                    ride['customer_id'],
                    f"📍 <b>السائق وصل إلى موقعك!</b>\n\n"
                    f"🚗 السائق في انتظارك الآن.\n"
                    f"• <b>رقم الرحلة:</b> {ride_id[-8:]}\n\n"
                    f"⏳ الرجاء التوجه إلى موقع السائق."
                )
            except Exception as e:
                logger.error(f"❌ فشل إعلام العميل: {e}")
    
    elif callback_data.startswith('start_'):
        # بدء الرحلة
        ride_id = callback_data.split('_')[1]
        ride = db.get_ride(ride_id)
        
        if ride and ride['driver_id'] == user_id:
            db.update_ride_status(ride_id, RideStatus.IN_PROGRESS)
            
            bot.answer_callback_query(call.id, "▶️ تم بدء الرحلة")
            
            # إعلام العميل
            try:
                bot.send_message(
                    ride['customer_id'],
                    f"▶️ <b>بدأت الرحلة!</b>\n\n"
                    f"🚖 الرحلة قد بدأت الآن.\n"
                    f"• <b>رقم الرحلة:</b> {ride_id[-8:]}\n"
                    f"• <b>وجهتك:</b> {ride.get('destination', 'غير محددة')}\n\n"
                    f"🚗 استمتع برحلتك!"
                )
            except Exception as e:
                logger.error(f"❌ فشل إعلام العميل: {e}")
    
    elif callback_data.startswith('complete_'):
        # إنهاء الرحلة
        ride_id = callback_data.split('_')[1]
        ride = db.get_ride(ride_id)
        
        if ride and ride['driver_id'] == user_id:
            db.update_ride_status(ride_id, RideStatus.COMPLETED)
            
            bot.answer_callback_query(call.id, "✅ تم إنهاء الرحلة")
            
            # إعلام العميل
            try:
                bot.send_message(
                    ride['customer_id'],
                    f"✅ <b>تم إنهاء الرحلة!</b>\n\n"
                    f"🎉 وصلت إلى وجهتك بنجاح.\n"
                    f"• <b>رقم الرحلة:</b> {ride_id[-8:]}\n"
                    f"• <b>التكلفة:</b> {ride['fare']} ريال\n\n"
                    f"⭐ الرجاء تقييم السائق من خلال الدعم الفني."
                )
            except Exception as e:
                logger.error(f"❌ فشل إعلام العميل: {e}")
    
    elif callback_data.startswith('cancel_'):
        # إلغاء الرحلة
        ride_id = callback_data.split('_')[1]
        ride = db.get_ride(ride_id)
        
        if ride:
            db.update_ride_status(ride_id, RideStatus.CANCELLED)
            
            bot.answer_callback_query(call.id, "❌ تم إلغاء الرحلة")
            
            # إعلام العميل إذا كان السائق هو من ألغى
            if ride['customer_id'] and ride['driver_id'] == user_id:
                try:
                    bot.send_message(
                        ride['customer_id'],
                        f"❌ <b>تم إلغاء الرحلة!</b>\n\n"
                        f"تم إلغاء الرحلة #{ride_id[-8:]} من قبل السائق.\n"
                        f"• <b>التكلفة:</b> {ride['fare']} ريال\n\n"
                        f"🔁 يمكنك طلب رحلة جديدة."
                    )
                except Exception as e:
                    logger.error(f"❌ فشل إعلام العميل: {e}")

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
    
    # الحصول على إحصائيات من قاعدة البيانات
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) as total_users FROM users")
            total_users = cur.fetchone()['total_users']
            
            cur.execute("SELECT COUNT(*) as total_drivers FROM users WHERE role = 'driver'")
            total_drivers = cur.fetchone()['total_drivers']
            
            cur.execute("SELECT COUNT(*) as total_rides FROM rides")
            total_rides = cur.fetchone()['total_rides']
            
            cur.execute("SELECT COUNT(*) as active_drivers FROM active_drivers WHERE is_available = TRUE")
            active_drivers = cur.fetchone()['active_drivers']
    except:
        total_users = 0
        total_drivers = 0
        total_rides = 0
        active_drivers = 0
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🚖 بوت النقل الذكي</title>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                text-align: center;
                backdrop-filter: blur(10px);
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .stat-card {{
                background: rgba(255, 255, 255, 0.15);
                padding: 20px;
                border-radius: 12px;
                text-align: center;
            }}
            .stat-number {{
                font-size: 2.5em;
                font-weight: bold;
                margin: 10px 0;
            }}
            .btn {{
                display: inline-block;
                padding: 15px 30px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 10px;
                margin: 10px;
                font-weight: bold;
                transition: transform 0.3s;
            }}
            .btn:hover {{
                transform: translateY(-3px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }}
            .logo {{
                font-size: 3em;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🚖</div>
            <h1>بوت النقل الذكي</h1>
            <p>نظام متكامل لإدارة طلبات النقل</p>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div>👥 المستخدمين</div>
                    <div class="stat-number">{total_users}</div>
                </div>
                <div class="stat-card">
                    <div>🚖 السائقين</div>
                    <div class="stat-number">{total_drivers}</div>
                </div>
                <div class="stat-card">
                    <div>📊 الرحلات</div>
                    <div class="stat-number">{total_rides}</div>
                </div>
                <div class="stat-card">
                    <div>🟢 النشطين</div>
                    <div class="stat-number">{active_drivers}</div>
                </div>
            </div>
            
            <div style="margin: 40px 0;">
                <p>🤖 <strong>حالة البوت:</strong> {bot_status}</p>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="/test_bot" class="btn">🧪 اختبار البوت</a>
                <a href="/dashboard" class="btn">📊 لوحة التحكم</a>
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn">💬 فتح البوت</a>
            </div>
            
            <div style="margin-top: 40px; opacity: 0.8;">
                <p>🔗 الرابط: https://dhhfhfjd.onrender.com</p>
                <p>© 2024 بوت النقل الذكي - جميع الحقوق محفوظة</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    """لوحة التحكم"""
    try:
        with db.get_cursor() as cur:
            # إحصائيات الرحلات
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    COALESCE(SUM(fare), 0) as total_revenue
                FROM rides
            """)
            ride_stats = cur.fetchone()
            
            # آخر الرحلات
            cur.execute("SELECT * FROM rides ORDER BY created_at DESC LIMIT 10")
            recent_rides = cur.fetchall()
            
            # السائقين النشطين
            cur.execute("SELECT * FROM active_drivers WHERE is_available = TRUE ORDER BY updated_at DESC")
            active_drivers = cur.fetchall()
            
    except Exception as e:
        logger.error(f"❌ خطأ في جلب بيانات لوحة التحكم: {e}")
        ride_stats = {}
        recent_rides = []
        active_drivers = []
    
    rides_html = ""
    for ride in recent_rides:
        rides_html += f"""
        <tr>
            <td>{ride['ride_id'][-8:]}</td>
            <td>{ride['customer_id'][:8]}...</td>
            <td>{ride.get('driver_id', '')[:8] if ride.get('driver_id') else 'غير معين'}</td>
            <td>{ride['status']}</td>
            <td>{ride['fare']}</td>
            <td>{ride['created_at'].strftime('%Y-%m-%d %H:%M') if ride['created_at'] else ''}</td>
        </tr>
        """
    
    drivers_html = ""
    for driver in active_drivers:
        drivers_html += f"""
        <tr>
            <td>{driver['driver_id'][:8]}...</td>
            <td>{driver['username'] or driver['driver_id'][:8]}</td>
            <td>{driver['vehicle_type']}</td>
            <td>{'🟢' if driver['is_available'] else '🔴'}</td>
            <td>{driver['updated_at'].strftime('%Y-%m-%d %H:%M') if driver['updated_at'] else ''}</td>
        </tr>
        """
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>📊 لوحة التحكم</title>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #f5f5f5;
                color: #333;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 30px;
            }}
            .stats-cards {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .card {{
                background: white;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            .card h3 {{
                margin-top: 0;
                color: #667eea;
            }}
            .stat-number {{
                font-size: 2.5em;
                font-weight: bold;
                color: #764ba2;
                margin: 10px 0;
            }}
            table {{
                width: 100%;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            th, td {{
                padding: 15px;
                text-align: right;
                border-bottom: 1px solid #eee;
            }}
            th {{
                background: #667eea;
                color: white;
            }}
            tr:hover {{
                background: #f9f9f9;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 لوحة التحكم - بوت النقل الذكي</h1>
                <p>إحصائيات ومراقبة النظام</p>
            </div>
            
            <div class="stats-cards">
                <div class="card">
                    <h3>إجمالي الرحلات</h3>
                    <div class="stat-number">{ride_stats.get('total', 0)}</div>
                </div>
                <div class="card">
                    <h3>الرحلات المكتملة</h3>
                    <div class="stat-number">{ride_stats.get('completed', 0)}</div>
                </div>
                <div class="card">
                    <h3>الإيرادات</h3>
                    <div class="stat-number">{ride_stats.get('total_revenue', 0):.2f} ريال</div>
                </div>
                <div class="card">
                    <h3>السائقين النشطين</h3>
                    <div class="stat-number">{len(active_drivers)}</div>
                </div>
            </div>
            
            <div style="margin-bottom: 30px;">
                <a href="/" class="btn">🏠 الرئيسية</a>
                <a href="/set_webhook" class="btn">⚙️ تحديث الويب هوك</a>
            </div>
            
            <h2>🚖 آخر الرحلات</h2>
            <table>
                <thead>
                    <tr>
                        <th>رقم الرحلة</th>
                        <th>العميل</th>
                        <th>السائق</th>
                        <th>الحالة</th>
                        <th>التكلفة</th>
                        <th>التاريخ</th>
                    </tr>
                </thead>
                <tbody>
                    {rides_html}
                </tbody>
            </table>
            
            <h2 style="margin-top: 40px;">🚗 السائقين النشطين</h2>
            <table>
                <thead>
                    <tr>
                        <th>رقم السائق</th>
                        <th>اسم المستخدم</th>
                        <th>نوع المركبة</th>
                        <th>الحالة</th>
                        <th>آخر تحديث</th>
                    </tr>
                </thead>
                <tbody>
                    {drivers_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook():
    """تعيين ويب هوك"""
    try:
        webhook_url = f"https://{request.host}/webhook"
        
        logger.info(f"🔄 محاولة تعيين ويب هوك على: {webhook_url}")
        
        bot.remove_webhook()
        time.sleep(1)
        result = bot.set_webhook(url=webhook_url)
        
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
            body { padding: 30px; font-family: Arial; text-align: center; background: #f5f5f5; }
            .instructions { 
                background: white; 
                padding: 30px; 
                border-radius: 15px;
                text-align: right;
                margin: 20px auto;
                max-width: 600px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .steps {{
                counter-reset: step-counter;
                padding-right: 0;
            }}
            .steps li {{
                list-style: none;
                margin-bottom: 20px;
                position: relative;
                padding-right: 40px;
            }}
            .steps li:before {{
                content: counter(step-counter);
                counter-increment: step-counter;
                position: absolute;
                right: 0;
                top: 0;
                background: #667eea;
                color: white;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <h1>🧪 اختبار البوت</h1>
        
        <div class="instructions">
            <h3>📱 خطوات اختبار البوت:</h3>
            <ol class="steps">
                <li>افتح تطبيق Telegram على هاتفك</li>
                <li>ابحث عن: <strong>@Dhdhdyduudbot</strong></li>
                <li>أرسل: <code>/start</code></li>
                <li>اضغط على "👤 عميل" أو "🚖 سائق"</li>
                <li>جرب الأزرار المختلفة</li>
                <li>اختبر طلب رحلة جديدة</li>
            </ol>
            
            <p style="color: #666; margin-top: 30px;">
                ⚠️ إذا لم يرد البوت، جرب:
                <ul style="color: #666;">
                    <li>أعد تعيين الويب هوك من الصفحة الرئيسية</li>
                    <li>انتظر 1-2 دقيقة</li>
                    <li>أعد فتح محادثة البوت</li>
                </ul>
            </p>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="https://t.me/Dhdhdyduudbot" target="_blank" style="padding: 15px 30px; background: #0088cc; color: white; text-decoration: none; border-radius: 8px; font-size: 1.2em; display: inline-block;">
                🚀 افتح البوت الآن
            </a>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="/" style="color: #667eea; text-decoration: none;">← العودة للصفحة الرئيسية</a>
        </div>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة استقبال تحديثات Telegram"""
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            
            logger.info(f"📩 استلام تحديث: {update.update_id}")
            
            bot.process_new_updates([update])
            
            logger.info(f"✅ تم معالجة تحديث: {update.update_id}")
            return 'OK', 200
            
        except Exception as e:
            logger.error(f"❌ خطأ في ويب هوك: {e}")
            return 'Error', 500
    
    return 'Bad Request', 400

@app.route('/health')
def health_check():
    """فحص صحة التطبيق"""
    try:
        # فحص اتصال قاعدة البيانات
        with db.get_cursor() as cur:
            cur.execute("SELECT 1")
        
        # فحص حالة البوت
        bot_info = bot.get_me()
        
        return jsonify({
            'status': 'healthy',
            'bot': bot_info.username,
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# وظائف الصيانة
# ============================================================================

def cleanup_old_data():
    """تنظيف البيانات القديمة"""
    try:
        with db.get_cursor() as cur:
            # حذف الرحلات الأقدم من 30 يوم
            cur.execute("""
                DELETE FROM rides 
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
                AND status IN ('completed', 'cancelled')
            """)
            
            # حذف السائقين غير النشطين
            cur.execute("""
                DELETE FROM active_drivers 
                WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
            """)
            
            logger.info("🧹 تم تنظيف البيانات القديمة")
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف البيانات: {e}")

# ============================================================================
# التهيئة والتشغيل
# ============================================================================

def init_bot():
    """تهيئة البوت"""
    try:
        # اختبار البوت
        bot_info = bot.get_me()
        logger.info(f"✅ البوت جاهز: @{bot_info.username} ({bot_info.first_name})")
        
        # تعيين ويب هوك تلقائياً
        try:
            webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}/webhook"
            if webhook_url.startswith("https://"):
                bot.remove_webhook()
                time.sleep(1)
                bot.set_webhook(url=webhook_url)
                logger.info(f"🌐 تم تعيين ويب هوك تلقائياً على: {webhook_url}")
        except:
            pass
        
        # تنظيف البيانات القديمة
        cleanup_old_data()
        
        return True
    except Exception as e:
        logger.error(f"❌ فشل تهيئة البوت: {e}")
        return False

# استيراد time للتأخير
import time

# تهيئة البوت
if __name__ != '__main__':
    init_bot()

# تشغيل التطبيق
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    app.run(host='0.0.0.0', port=port, debug=False)