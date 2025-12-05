"""
🚖 بوت النقل الذكي - نسخة متوافقة مع Render
"""

import os
import logging
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================================================
# إعدادات أساسية
# ============================================================================

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# الحصول على التوكن
BOT_TOKEN = os.environ.get('BOT_TOKEN', 8425005126:AAExDibH8mxVpITuhA98AFfNcUo9Rgdd98A')

# تهيئة التطبيق والبوت
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ============================================================================
# قاعدة البيانات (SQLite)
# ============================================================================

class Database:
    """فئة إدارة قاعدة البيانات باستخدام SQLite"""
    
    def __init__(self, db_path='transport.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """الحصول على اتصال قاعدة البيانات"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """تهيئة قاعدة البيانات وإنشاء الجداول"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # جدول المستخدمين
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        phone TEXT,
                        role TEXT DEFAULT 'customer',
                        balance REAL DEFAULT 0.0,
                        rating REAL DEFAULT 5.0,
                        total_rides INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # جدول الرحلات
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rides (
                        ride_id TEXT PRIMARY KEY,
                        customer_id TEXT,
                        driver_id TEXT,
                        pickup_location TEXT,
                        destination TEXT,
                        pickup_lat REAL,
                        pickup_lng REAL,
                        dest_lat REAL,
                        dest_lng REAL,
                        status TEXT DEFAULT 'pending',
                        fare REAL DEFAULT 15.0,
                        distance REAL,
                        duration INTEGER,
                        payment_method TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        accepted_at TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        cancelled_at TIMESTAMP,
                        customer_rating INTEGER,
                        driver_rating INTEGER,
                        notes TEXT
                    )
                ''')
                
                # جدول السائقين النشطين
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS active_drivers (
                        driver_id TEXT PRIMARY KEY,
                        username TEXT,
                        vehicle_type TEXT DEFAULT 'سيارة',
                        vehicle_number TEXT,
                        current_lat REAL,
                        current_lng REAL,
                        is_available BOOLEAN DEFAULT 1,
                        status TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
                
        except Exception as e:
            logger.error(f"❌ فشل تهيئة قاعدة البيانات: {e}")
    
    def save_user(self, user_id, username, first_name, last_name="", phone="", role="customer"):
        """حفظ أو تحديث بيانات المستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, last_name, phone, role, last_active)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, username, first_name, last_name, phone, role))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ المستخدم: {e}")
            return False
    
    def get_user(self, user_id):
        """الحصول على بيانات مستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات المستخدم: {e}")
            return None
    
    def save_ride(self, ride_data):
        """حفظ رحلة جديدة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO rides 
                    (ride_id, customer_id, pickup_location, pickup_lat, pickup_lng, 
                     status, fare, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    ride_data.get('ride_id'),
                    ride_data.get('customer_id'),
                    ride_data.get('pickup_location'),
                    ride_data.get('pickup_lat'),
                    ride_data.get('pickup_lng'),
                    'pending',
                    ride_data.get('fare', 15.0)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الرحلة: {e}")
            return False
    
    def update_ride_status(self, ride_id, status, driver_id=None):
        """تحديث حالة الرحلة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if status == 'accepted' and driver_id:
                    cursor.execute('''
                        UPDATE rides 
                        SET status = ?, driver_id = ?, accepted_at = CURRENT_TIMESTAMP
                        WHERE ride_id = ?
                    ''', (status, driver_id, ride_id))
                elif status == 'in_progress':
                    cursor.execute('''
                        UPDATE rides 
                        SET status = ?, started_at = CURRENT_TIMESTAMP
                        WHERE ride_id = ?
                    ''', (status, ride_id))
                elif status == 'completed':
                    cursor.execute('''
                        UPDATE rides 
                        SET status = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE ride_id = ?
                    ''', (status, ride_id))
                elif status == 'cancelled':
                    cursor.execute('''
                        UPDATE rides 
                        SET status = ?, cancelled_at = CURRENT_TIMESTAMP
                        WHERE ride_id = ?
                    ''', (status, ride_id))
                else:
                    cursor.execute('''
                        UPDATE rides SET status = ? WHERE ride_id = ?
                    ''', (status, ride_id))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث حالة الرحلة: {e}")
            return False
    
    def get_ride(self, ride_id):
        """الحصول على بيانات رحلة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM rides WHERE ride_id = ?', (ride_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات الرحلة: {e}")
            return None
    
    def add_active_driver(self, driver_id, username, vehicle_type="سيارة", vehicle_number=""):
        """إضافة سائق نشط"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO active_drivers 
                    (driver_id, username, vehicle_type, vehicle_number, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (driver_id, username, vehicle_type, vehicle_number))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة سائق نشط: {e}")
            return False
    
    def remove_active_driver(self, driver_id):
        """إزالة سائق من القائمة النشطة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM active_drivers WHERE driver_id = ?', (driver_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إزالة سائق نشط: {e}")
            return False
    
    def update_driver_location(self, driver_id, lat, lng):
        """تحديث موقع السائق"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE active_drivers 
                    SET current_lat = ?, current_lng = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE driver_id = ?
                ''', (lat, lng, driver_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث موقع السائق: {e}")
            return False
    
    def get_available_drivers(self):
        """الحصول على السائقين المتاحين"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM active_drivers 
                    WHERE is_available = 1
                    ORDER BY updated_at DESC
                    LIMIT 50
                ''')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب السائقين المتاحين: {e}")
            return []
    
    def get_user_rides(self, user_id, limit=10):
        """الحصول على رحلات المستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM rides 
                    WHERE customer_id = ? OR driver_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (user_id, user_id, limit))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب رحلات المستخدم: {e}")
            return []
    
    def update_user_balance(self, user_id, amount):
        """تحديث رصيد المستخدم"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET balance = balance + ?
                    WHERE user_id = ?
                ''', (amount, user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث رصيد المستخدم: {e}")
            return False
    
    def get_stats(self):
        """الحصول على إحصائيات النظام"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                stats = {}
                
                cursor.execute('SELECT COUNT(*) as count FROM users')
                stats['total_users'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = "driver"')
                stats['total_drivers'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) as count FROM rides')
                stats['total_rides'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) as count FROM active_drivers WHERE is_available = 1')
                stats['active_drivers'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COALESCE(SUM(fare), 0) as total FROM rides WHERE status = "completed"')
                stats['total_revenue'] = cursor.fetchone()[0]
                
                return stats
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {}

# إنشاء كائن قاعدة البيانات
db = Database()

# ============================================================================
# دوال مساعدة
# ============================================================================

def create_ride_keyboard(user_type="customer"):
    """إنشاء لوحة مفاتيح حسب نوع المستخدم"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if user_type == "customer":
        buttons = [
            types.KeyboardButton('🚖 طلب رحلة جديدة'),
            types.KeyboardButton('📍 إرسال موقعي', request_location=True),
            types.KeyboardButton('📋 رحلاتي السابقة'),
            types.KeyboardButton('💰 رصيدي'),
            types.KeyboardButton('📞 الدعم')
        ]
    else:  # driver
        buttons = [
            types.KeyboardButton('🟢 بدء العمل'),
            types.KeyboardButton('🔴 إنهاء العمل'),
            types.KeyboardButton('📍 تحديث موقعي', request_location=True),
            types.KeyboardButton('📋 رحلاتي'),
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
        InlineKeyboardButton("❌ رفض الرحلة", callback_data=f"reject_{ride_id}")
    ]
    
    markup.add(*buttons)
    return markup

# ============================================================================
# معالجات البوت
# ============================================================================

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """معالجة أمر البدء"""
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = message.from_user.username or ""
    
    logger.info(f"👋 /start من: {first_name} ({user_id})")
    
    # حفظ بيانات المستخدم
    db.save_user(user_id, username, first_name)
    
    # عرض خيارات التسجيل
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👤 عميل'),
        types.KeyboardButton('🚖 سائق')
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

@bot.message_handler(func=lambda msg: msg.text in ['👤 عميل', '🚖 سائق'])
def handle_role_selection(message):
    """معالجة اختيار الدور"""
    user_id = str(message.from_user.id)
    role_text = message.text
    role = "customer" if role_text == "👤 عميل" else "driver"
    
    logger.info(f"🎭 اختيار دور: {role} من: {user_id}")
    
    # تحديث دور المستخدم
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
    
    logger.info(f"📍 موقع من: {user_id} - {location.latitude}, {location.longitude}")
    
    user = db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ يجب البدء باستخدام /start أولاً.")
        return
    
    if user['role'] == 'customer':
        # إنشاء طلب رحلة جديد
        ride_id = f"ride_{user_id}_{int(datetime.now().timestamp())}"
        
        ride_data = {
            'ride_id': ride_id,
            'customer_id': user_id,
            'pickup_location': 'الموقع المرسل',
            'pickup_lat': location.latitude,
            'pickup_lng': location.longitude
        }
        
        # حفظ الرحلة
        if db.save_ride(ride_data):
            # إعلام المستخدم
            bot.send_message(
                message.chat.id,
                "📍 <b>تم استلام موقعك بنجاح!</b>\n\n"
                f"• <b>خط العرض:</b> {location.latitude:.6f}\n"
                f"• <b>خط الطول:</b> {location.longitude:.6f}\n\n"
                "🚖 <b>تم إنشاء طلب رحلة!</b>\n"
                "⏳ جاري البحث عن سائق قريب...",
                reply_markup=create_ride_keyboard("customer")
            )
            
            # البحث عن سائقين متاحين
            available_drivers = db.get_available_drivers()
            
            if available_drivers:
                # إرسال طلب الرحلة للسائقين المتاحين
                for driver in available_drivers:
                    try:
                        markup = create_inline_ride_buttons(ride_id)
                        
                        bot.send_message(
                            driver['driver_id'],
                            f"🚖 <b>طلب رحلة جديد</b>\n\n"
                            f"• <b>العميل:</b> {message.from_user.first_name}\n"
                            f"• <b>التكلفة:</b> 15 ريال\n\n"
                            f"<b>رقم الرحلة:</b> {ride_id[-8:]}",
                            reply_markup=markup
                        )
                    except Exception as e:
                        logger.error(f"❌ فشل إرسال طلب الرحلة للسائق {driver['driver_id']}: {e}")
                
                logger.info(f"✅ تم إرسال طلب الرحلة لـ {len(available_drivers)} سائق")
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ <b>لا يوجد سائقون متاحون حالياً</b>\n\n"
                    "يرجى المحاولة مرة أخرى لاحقاً.",
                    reply_markup=create_ride_keyboard("customer")
                )
        else:
            bot.send_message(
                message.chat.id,
                "❌ <b>حدث خطأ في إنشاء الرحلة</b>\n\n"
                "يرجى المحاولة مرة أخرى.",
                reply_markup=create_ride_keyboard("customer")
            )
    
    elif user['role'] == 'driver':
        # تحديث موقع السائق
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
            'in_progress': '🚗',
            'completed': '🎉',
            'cancelled': '❌'
        }.get(ride['status'], '❓')
        
        response += (
            f"{status_emoji} <b>رحلة #{ride['ride_id'][-8:]}</b>\n"
            f"• <b>الحالة:</b> {ride['status']}\n"
            f"• <b>التكلفة:</b> {ride['fare']} ريال\n\n"
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

@bot.message_handler(func=lambda msg: msg.text == '📞 الدعم')
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
للشكاوى والاستفسارات، تواصل مع الدعم.
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
    markup = create_ride_keyboard(role)
    
    bot.send_message(
        message.chat.id,
        "🔙 <b>تم العودة للقائمة الرئيسية</b>",
        reply_markup=markup
    )

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
        
        if ride and ride['status'] == 'pending':
            # تحديث حالة الرحلة
            db.update_ride_status(ride_id, 'accepted', user_id)
            
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
    
    # الحصول على إحصائيات
    stats = db.get_stats()
    
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
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                text-align: center;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin: 30px 0;
            }}
            .stat-card {{
                background: rgba(255, 255, 255, 0.15);
                padding: 15px;
                border-radius: 10px;
            }}
            .stat-number {{
                font-size: 2em;
                font-weight: bold;
                margin: 10px 0;
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
            
            <div style="margin: 20px 0;">
                <p>🤖 <strong>حالة البوت:</strong> {bot_status}</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div>👥 المستخدمين</div>
                    <div class="stat-number">{stats.get('total_users', 0)}</div>
                </div>
                <div class="stat-card">
                    <div>🚖 السائقين</div>
                    <div class="stat-number">{stats.get('total_drivers', 0)}</div>
                </div>
                <div class="stat-card">
                    <div>📊 الرحلات</div>
                    <div class="stat-number">{stats.get('total_rides', 0)}</div>
                </div>
                <div class="stat-card">
                    <div>🟢 النشطين</div>
                    <div class="stat-number">{stats.get('active_drivers', 0)}</div>
                </div>
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
        webhook_url = f"https://{request.host}/webhook"
        
        logger.info(f"🔄 محاولة تعيين ويب هوك على: {webhook_url}")
        
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        
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
            </div>
            <div style="margin-top: 30px;">
                <a href="https://t.me/{bot_info.username}" target="_blank" style="padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px;">
                    💬 افتح البوت الآن
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
        bot_info = bot.get_me()
        return jsonify({
            'status': 'healthy',
            'bot': bot_info.username,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# التشغيل الرئيسي
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    app.run(host='0.0.0.0', port=port, debug=False)