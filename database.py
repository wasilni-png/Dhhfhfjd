"""
🗄️ قاعدة بيانات PostgreSQL للنقل الذكي
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ============================================================================
# إعدادات اتصال قاعدة البيانات
# ============================================================================

class DatabaseConfig:
    """إعدادات اتصال قاعدة البيانات"""
    
    @staticmethod
    def get_connection_params():
        """الحصول على معاملات الاتصال"""
        if 'DATABASE_URL' in os.environ:
            # على Render، استخدم DATABASE_URL
            return os.environ['DATABASE_URL']
        else:
            # للتنمية المحلية
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': os.getenv('DB_PORT', '5432'),
                'database': os.getenv('DB_NAME', 'transport_db'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'postgres')
            }

# ============================================================================
# فئات النماذج (Models)
# ============================================================================

class UserRole:
    """أدوار المستخدمين"""
    CUSTOMER = 'customer'
    DRIVER = 'driver'
    ADMIN = 'admin'

class RideStatus:
    """حالات الرحلة"""
    PENDING = 'pending'      # في الانتظار
    ACCEPTED = 'accepted'    # مقبولة
    ON_WAY = 'on_way'        # في الطريق
    ARRIVED = 'arrived'      # وصل للموقع
    STARTED = 'started'      # بدأت الرحلة
    COMPLETED = 'completed'  # مكتملة
    CANCELLED = 'cancelled'  # ملغاة

class PaymentStatus:
    """حالات الدفع"""
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class PaymentMethod:
    """طرق الدفع"""
    CASH = 'cash'
    CREDIT_CARD = 'credit_card'
    WALLET = 'wallet'

# ============================================================================
# فئة إدارة قاعدة البيانات
# ============================================================================

class TransportDatabase:
    """فئة إدارة قاعدة البيانات للنقل الذكي"""
    
    def __init__(self):
        """تهيئة الاتصال بقاعدة البيانات"""
        self.connection_pool = None
        self.init_pool()
        self.create_tables()
    
    def init_pool(self):
        """تهيئة تجمع الاتصالات"""
        try:
            conn_params = DatabaseConfig.get_connection_params()
            if isinstance(conn_params, str):
                # إذا كان DATABASE_URL (Render)
                self.connection_pool = SimpleConnectionPool(
                    1, 20, conn_params
                )
            else:
                # للتنمية المحلية
                self.connection_pool = SimpleConnectionPool(
                    1, 20,
                    host=conn_params['host'],
                    port=conn_params['port'],
                    database=conn_params['database'],
                    user=conn_params['user'],
                    password=conn_params['password']
                )
            logger.info("✅ تم تهيئة تجمع اتصالات قاعدة البيانات")
        except Exception as e:
            logger.error(f"❌ فشل تهيئة الاتصال بقاعدة البيانات: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """الحصول على اتصال من التجمع"""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال: {e}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, commit=False):
        """الحصول على مؤشر قاعدة البيانات"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ خطأ في قاعدة البيانات: {e}")
                raise
            finally:
                cursor.close()
    
    def create_tables(self):
        """إنشاء الجداول إذا لم تكن موجودة"""
        try:
            with self.get_cursor(commit=True) as cur:
                # جدول المستخدمين
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id VARCHAR(50) PRIMARY KEY,
                        username VARCHAR(100),
                        full_name VARCHAR(200),
                        phone VARCHAR(20),
                        role VARCHAR(20) DEFAULT 'customer',
                        balance DECIMAL(10,2) DEFAULT 0.00,
                        rating DECIMAL(3,2) DEFAULT 5.00,
                        total_rides INTEGER DEFAULT 0,
                        total_earnings DECIMAL(10,2) DEFAULT 0.00,
                        total_spent DECIMAL(10,2) DEFAULT 0.00,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_verified BOOLEAN DEFAULT FALSE,
                        vehicle_type VARCHAR(50),
                        vehicle_number VARCHAR(50),
                        profile_photo TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # جدول الرحلات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS rides (
                        id VARCHAR(50) PRIMARY KEY,
                        customer_id VARCHAR(50) REFERENCES users(id),
                        customer_name VARCHAR(100),
                        driver_id VARCHAR(50) REFERENCES users(id),
                        driver_name VARCHAR(100),
                        pickup_location JSONB,
                        destination JSONB,
                        pickup_address TEXT,
                        destination_address TEXT,
                        status VARCHAR(20) DEFAULT 'pending',
                        fare DECIMAL(10,2) DEFAULT 0.00,
                        distance DECIMAL(10,2),
                        duration INTEGER,
                        payment_method VARCHAR(50),
                        payment_status VARCHAR(20) DEFAULT 'pending',
                        customer_rating INTEGER,
                        driver_rating INTEGER,
                        customer_comment TEXT,
                        driver_comment TEXT,
                        cancelled_by VARCHAR(50),
                        cancel_reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        accepted_at TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # جدول السائقين النشطين
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_drivers (
                        user_id VARCHAR(50) PRIMARY KEY REFERENCES users(id),
                        username VARCHAR(100),
                        vehicle_type VARCHAR(50),
                        vehicle_number VARCHAR(50),
                        current_location JSONB,
                        is_available BOOLEAN DEFAULT TRUE,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_earnings DECIMAL(10,2) DEFAULT 0.00
                    )
                """)
                
                # جدول الدفعات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) REFERENCES users(id),
                        ride_id VARCHAR(50) REFERENCES rides(id),
                        amount DECIMAL(10,2),
                        payment_method VARCHAR(50),
                        status VARCHAR(20) DEFAULT 'pending',
                        transaction_id VARCHAR(100),
                        transaction_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # جدول التقييمات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ratings (
                        id SERIAL PRIMARY KEY,
                        ride_id VARCHAR(50) REFERENCES rides(id),
                        from_user_id VARCHAR(50) REFERENCES users(id),
                        to_user_id VARCHAR(50) REFERENCES users(id),
                        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                        comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # جدول المحافظ
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS wallet_transactions (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) REFERENCES users(id),
                        type VARCHAR(20), -- deposit, withdrawal, ride_payment, ride_earning, refund
                        amount DECIMAL(10,2),
                        balance_before DECIMAL(10,2),
                        balance_after DECIMAL(10,2),
                        description TEXT,
                        reference_id VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # جدول الإشعارات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) REFERENCES users(id),
                        type VARCHAR(50),
                        title VARCHAR(200),
                        message TEXT,
                        data JSONB,
                        is_read BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # جدول الإحصائيات
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS statistics (
                        date DATE PRIMARY KEY,
                        total_users INTEGER DEFAULT 0,
                        total_drivers INTEGER DEFAULT 0,
                        total_rides INTEGER DEFAULT 0,
                        completed_rides INTEGER DEFAULT 0,
                        cancelled_rides INTEGER DEFAULT 0,
                        total_revenue DECIMAL(10,2) DEFAULT 0.00,
                        average_rating DECIMAL(3,2) DEFAULT 0.00,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # إنشاء الفهارس لتحسين الأداء
                cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_users_rating ON users(rating)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_customer ON rides(customer_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_driver ON rides(driver_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rides_created ON rides(created_at)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_active_drivers_available ON active_drivers(is_available)")
                
                logger.info("✅ تم إنشاء/تأكيد الجداول بنجاح")
                
        except Exception as e:
            logger.error(f"❌ فشل إنشاء الجداول: {e}")
            raise
    
    # ============================================================================
    # دوال المستخدمين
    # ============================================================================
    
    def create_or_update_user(self, user_data: Dict) -> bool:
        """إنشاء أو تحديث مستخدم"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO users 
                    (id, username, full_name, phone, role, balance, rating, 
                     total_rides, created_at, updated_at, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    phone = EXCLUDED.phone,
                    role = EXCLUDED.role,
                    updated_at = EXCLUDED.updated_at,
                    last_seen = EXCLUDED.last_seen
                    RETURNING *
                """, (
                    user_data.get('id'),
                    user_data.get('username'),
                    user_data.get('full_name'),
                    user_data.get('phone'),
                    user_data.get('role'),
                    user_data.get('balance', 0.0),
                    user_data.get('rating', 5.0),
                    user_data.get('total_rides', 0),
                    datetime.now(),
                    datetime.now(),
                    datetime.now()
                ))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء/تحديث المستخدم: {e}")
            return False
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """الحصول على بيانات مستخدم"""
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات المستخدم: {e}")
            return None
    
    def update_user_last_seen(self, user_id: str) -> bool:
        """تحديث وقت آخر ظهور للمستخدم"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("""
                    UPDATE users 
                    SET last_seen = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث آخر ظهور: {e}")
            return False
    
    def update_user_balance(self, user_id: str, amount: float, transaction_type: str) -> bool:
        """تحديث رصيد المستخدم"""
        try:
            with self.get_cursor(commit=True) as cur:
                # الحصول على الرصيد الحالي
                cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
                result = cur.fetchone()
                if not result:
                    return False
                
                current_balance = float(result['balance'])
                new_balance = current_balance + amount
                
                # تحديث الرصيد
                cur.execute("""
                    UPDATE users 
                    SET balance = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_balance, user_id))
                
                # تسجيل المعاملة
                cur.execute("""
                    INSERT INTO wallet_transactions 
                    (user_id, type, amount, balance_before, balance_after, description)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    transaction_type,
                    amount,
                    current_balance,
                    new_balance,
                    f"{transaction_type}: {amount}"
                ))
                
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث الرصيد: {e}")
            return False
    
    # ============================================================================
    # دوال الرحلات
    # ============================================================================
    
    def create_ride(self, ride_data: Dict) -> Optional[str]:
        """إنشاء رحلة جديدة"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO rides 
                    (id, customer_id, customer_name, pickup_location, status, fare, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    ride_data.get('id'),
                    ride_data.get('customer_id'),
                    ride_data.get('customer_name'),
                    Json(ride_data.get('pickup_location', {})),
                    ride_data.get('status', RideStatus.PENDING),
                    ride_data.get('fare', 15.0),
                    datetime.now(),
                    datetime.now()
                ))
                
                result = cur.fetchone()
                return result['id'] if result else None
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الرحلة: {e}")
            return None
    
    def get_ride(self, ride_id: str) -> Optional[Dict]:
        """الحصول على بيانات رحلة"""
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT * FROM rides WHERE id = %s", (ride_id,))
                ride = cur.fetchone()
                return dict(ride) if ride else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات الرحلة: {e}")
            return None
    
    def update_ride_status(self, ride_id: str, status: str, **kwargs) -> bool:
        """تحديث حالة الرحلة"""
        try:
            with self.get_cursor(commit=True) as cur:
                update_fields = []
                values = []
                
                update_fields.append("status = %s")
                values.append(status)
                
                # إضافة حقول إضافية إذا كانت موجودة
                if 'driver_id' in kwargs:
                    update_fields.append("driver_id = %s")
                    values.append(kwargs['driver_id'])
                
                if 'driver_name' in kwargs:
                    update_fields.append("driver_name = %s")
                    values.append(kwargs['driver_name'])
                
                if 'accepted_at' in kwargs and kwargs['accepted_at']:
                    update_fields.append("accepted_at = %s")
                    values.append(kwargs['accepted_at'])
                
                if 'started_at' in kwargs and kwargs['started_at']:
                    update_fields.append("started_at = %s")
                    values.append(kwargs['started_at'])
                
                if 'completed_at' in kwargs and kwargs['completed_at']:
                    update_fields.append("completed_at = %s")
                    values.append(kwargs['completed_at'])
                
                if 'payment_status' in kwargs:
                    update_fields.append("payment_status = %s")
                    values.append(kwargs['payment_status'])
                
                # تحديث وقت التعديل
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                
                # بناء الاستعلام
                values.append(ride_id)
                query = f"""
                    UPDATE rides 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                """
                
                cur.execute(query, values)
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث حالة الرحلة: {e}")
            return False
    
    def get_user_rides(self, user_id: str, limit: int = 10) -> List[Dict]:
        """الحصول على رحلات مستخدم"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT * FROM rides 
                    WHERE customer_id = %s OR driver_id = %s
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (user_id, user_id, limit))
                
                rides = cur.fetchall()
                return [dict(ride) for ride in rides]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب رحلات المستخدم: {e}")
            return []
    
    def get_active_rides(self) -> List[Dict]:
        """الحصول على الرحلات النشطة"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT * FROM rides 
                    WHERE status IN (%s, %s, %s, %s)
                    ORDER BY created_at ASC
                """, (RideStatus.PENDING, RideStatus.ACCEPTED, RideStatus.ON_WAY, RideStatus.STARTED))
                
                rides = cur.fetchall()
                return [dict(ride) for ride in rides]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الرحلات النشطة: {e}")
            return []
    
    def get_pending_rides(self) -> List[Dict]:
        """الحصول على الرحلات في الانتظار"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT * FROM rides 
                    WHERE status = %s
                    ORDER BY created_at ASC
                """, (RideStatus.PENDING,))
                
                rides = cur.fetchall()
                return [dict(ride) for ride in rides]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الرحلات المنتظرة: {e}")
            return []
    
    # ============================================================================
    # دوال السائقين النشطين
    # ============================================================================
    
    def add_active_driver(self, driver_data: Dict) -> bool:
        """إضافة سائق نشط"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO active_drivers 
                    (user_id, username, vehicle_type, vehicle_number, started_at, last_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    vehicle_type = EXCLUDED.vehicle_type,
                    vehicle_number = EXCLUDED.vehicle_number,
                    last_active = EXCLUDED.last_active,
                    is_available = TRUE
                """, (
                    driver_data.get('id'),
                    driver_data.get('username'),
                    driver_data.get('vehicle_type', 'سيارة'),
                    driver_data.get('vehicle_number', ''),
                    datetime.now(),
                    datetime.now()
                ))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة سائق نشط: {e}")
            return False
    
    def remove_active_driver(self, user_id: str) -> bool:
        """إزالة سائق من القائمة النشطة"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM active_drivers WHERE user_id = %s", (user_id,))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في إزالة سائق نشط: {e}")
            return False
    
    def update_driver_location(self, user_id: str, location: Dict) -> bool:
        """تحديث موقع السائق"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("""
                    UPDATE active_drivers 
                    SET current_location = %s, last_active = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (Json(location), user_id))
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث موقع السائق: {e}")
            return False
    
    def get_active_drivers(self, limit: int = 50) -> List[Dict]:
        """الحصول على السائقين النشطين"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT * FROM active_drivers 
                    WHERE is_available = TRUE
                    ORDER BY last_active DESC 
                    LIMIT %s
                """, (limit,))
                
                drivers = cur.fetchall()
                return [dict(driver) for driver in drivers]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب السائقين النشطين: {e}")
            return []
    
    def get_available_drivers(self) -> List[Dict]:
        """الحصول على السائقين المتاحين"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT ad.*, u.rating 
                    FROM active_drivers ad
                    JOIN users u ON ad.user_id = u.id
                    WHERE ad.is_available = TRUE
                    AND u.rating >= 4.0
                    ORDER BY u.rating DESC, ad.last_active DESC
                """)
                
                drivers = cur.fetchall()
                return [dict(driver) for driver in drivers]
        except Exception as e:
            logger.error(f"❌ خطأ في جلب السائقين المتاحين: {e}")
            return []
    
    # ============================================================================
    # دوال الإحصائيات والتقارير
    # ============================================================================
    
    def get_system_stats(self) -> Dict:
        """الحصول على إحصائيات النظام"""
        try:
            with self.get_cursor() as cur:
                stats = {}
                
                # إجمالي المستخدمين
                cur.execute("SELECT COUNT(*) as count FROM users")
                stats['total_users'] = cur.fetchone()['count']
                
                # إجمالي السائقين
                cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'driver'")
                stats['total_drivers'] = cur.fetchone()['count']
                
                # إجمالي العملاء
                cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
                stats['total_customers'] = cur.fetchone()['count']
                
                # إجمالي الرحلات
                cur.execute("SELECT COUNT(*) as count FROM rides")
                stats['total_rides'] = cur.fetchone()['count']
                
                # الرحلات المكتملة
                cur.execute("SELECT COUNT(*) as count FROM rides WHERE status = 'completed'")
                stats['completed_rides'] = cur.fetchone()['count']
                
                # الرحلات النشطة
                cur.execute("""
                    SELECT COUNT(*) as count FROM rides 
                    WHERE status IN ('pending', 'accepted', 'on_way', 'started')
                """)
                stats['active_rides'] = cur.fetchone()['count']
                
                # السائقين النشطين
                cur.execute("SELECT COUNT(*) as count FROM active_drivers")
                stats['active_drivers'] = cur.fetchone()['count']
                
                # إجمالي الإيرادات
                cur.execute("SELECT COALESCE(SUM(fare), 0) as total FROM rides WHERE status = 'completed'")
                stats['total_revenue'] = float(cur.fetchone()['total'])
                
                # متوسط التقييم
                cur.execute("SELECT COALESCE(AVG(rating), 5.0) as avg FROM users WHERE total_rides > 0")
                stats['average_rating'] = float(cur.fetchone()['avg'])
                
                return stats
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {}
    
    def get_today_stats(self) -> Dict:
        """الحصول على إحصائيات اليوم"""
        try:
            with self.get_cursor() as cur:
                today = datetime.now().date()
                stats = {}
                
                # رحلات اليوم
                cur.execute("""
                    SELECT COUNT(*) as count FROM rides 
                    WHERE DATE(created_at) = %s
                """, (today,))
                stats['today_rides'] = cur.fetchone()['count']
                
                # إيرادات اليوم
                cur.execute("""
                    SELECT COALESCE(SUM(fare), 0) as total FROM rides 
                    WHERE status = 'completed' AND DATE(completed_at) = %s
                """, (today,))
                stats['today_revenue'] = float(cur.fetchone()['total'])
                
                # مستخدمين جدد اليوم
                cur.execute("""
                    SELECT COUNT(*) as count FROM users 
                    WHERE DATE(created_at) = %s
                """, (today,))
                stats['new_users_today'] = cur.fetchone()['count']
                
                return stats
        except Exception as e:
            logger.error(f"❌ خطأ في جلب إحصائيات اليوم: {e}")
            return {}
    
    # ============================================================================
    # دوال البحث والاستعلامات
    # ============================================================================
    
    def search_rides(self, filters: Dict, limit: int = 50, offset: int = 0) -> List[Dict]:
        """بحث في الرحلات"""
        try:
            with self.get_cursor() as cur:
                conditions = []
                values = []
                
                # بناء الشروط ديناميكياً
                if 'customer_id' in filters:
                    conditions.append("customer_id = %s")
                    values.append(filters['customer_id'])
                
                if 'driver_id' in filters:
                    conditions.append("driver_id = %s")
                    values.append(filters['driver_id'])
                
                if 'status' in filters:
                    if isinstance(filters['status'], list):
                        placeholders = ','.join(['%s'] * len(filters['status']))
                        conditions.append(f"status IN ({placeholders})")
                        values.extend(filters['status'])
                    else:
                        conditions.append("status = %s")
                        values.append(filters['status'])
                
                if 'start_date' in filters:
                    conditions.append("created_at >= %s")
                    values.append(filters['start_date'])
                
                if 'end_date' in filters:
                    conditions.append("created_at <= %s")
                    values.append(filters['end_date'])
                
                # بناء الاستعلام
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                values.extend([limit, offset])
                
                query = f"""
                    SELECT * FROM rides 
                    WHERE {where_clause}
                    ORDER BY created_at DESC 
                    LIMIT %s OFFSET %s
                """
                
                cur.execute(query, values)
                rides = cur.fetchall()
                return [dict(ride) for ride in rides]
        except Exception as e:
            logger.error(f"❌ خطأ في البحث في الرحلات: {e}")
            return []
    
    def search_users(self, filters: Dict, limit: int = 50, offset: int = 0) -> List[Dict]:
        """بحث في المستخدمين"""
        try:
            with self.get_cursor() as cur:
                conditions = []
                values = []
                
                # بناء الشروط ديناميكياً
                if 'role' in filters:
                    conditions.append("role = %s")
                    values.append(filters['role'])
                
                if 'is_active' in filters:
                    conditions.append("is_active = %s")
                    values.append(filters['is_active'])
                
                if 'min_rating' in filters:
                    conditions.append("rating >= %s")
                    values.append(filters['min_rating'])
                
                if 'search_term' in filters:
                    conditions.append("(username ILIKE %s OR full_name ILIKE %s OR phone ILIKE %s)")
                    search_term = f"%{filters['search_term']}%"
                    values.extend([search_term, search_term, search_term])
                
                # بناء الاستعلام
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                values.extend([limit, offset])
                
                query = f"""
                    SELECT * FROM users 
                    WHERE {where_clause}
                    ORDER BY created_at DESC 
                    LIMIT %s OFFSET %s
                """
                
                cur.execute(query, values)
                users = cur.fetchall()
                return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"❌ خطأ في البحث في المستخدمين: {e}")
            return []
    
    # ============================================================================
    # دوال النسخ الاحتياطي والاستعادة
    # ============================================================================
    
    def backup_database(self) -> Optional[str]:
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        try:
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'users': [],
                'rides': [],
                'active_drivers': []
            }
            
            with self.get_cursor() as cur:
                # نسخ المستخدمين
                cur.execute("SELECT * FROM users")
                backup_data['users'] = [dict(user) for user in cur.fetchall()]
                
                # نسخ الرحلات (آخر 1000 رحلة)
                cur.execute("SELECT * FROM rides ORDER BY created_at DESC LIMIT 1000")
                backup_data['rides'] = [dict(ride) for ride in cur.fetchall()]
                
                # نسخ السائقين النشطين
                cur.execute("SELECT * FROM active_drivers")
                backup_data['active_drivers'] = [dict(driver) for driver in cur.fetchall()]
            
            # حفظ النسخة الاحتياطية في ملف
            backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ تم إنشاء نسخة احتياطية في: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
            return None
    
    # ============================================================================
    # دوول التنظيف والصيانة
    # ============================================================================
    
    def cleanup_old_data(self, days: int = 30) -> Dict:
        """تنظيف البيانات القديمة"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            stats = {
                'deleted_rides': 0,
                'deleted_notifications': 0,
                'archived_users': 0
            }
            
            with self.get_cursor(commit=True) as cur:
                # حذف الإشعارات القديمة
                cur.execute("""
                    DELETE FROM notifications 
                    WHERE created_at < %s AND is_read = TRUE
                """, (cutoff_date,))
                stats['deleted_notifications'] = cur.rowcount
                
                # تعطيل المستخدمين غير النشطين
                cutoff_inactive = datetime.now() - timedelta(days=90)
                cur.execute("""
                    UPDATE users 
                    SET is_active = FALSE 
                    WHERE last_seen < %s AND is_active = TRUE
                """, (cutoff_inactive,))
                stats['archived_users'] = cur.rowcount
            
            logger.info(f"✅ تم تنظيف البيانات القديمة: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف البيانات القديمة: {e}")
            return {}
    
    # ============================================================================
    # دوال التهيئة والتحقق
    # ============================================================================
    
    def check_connection(self) -> bool:
        """فحص اتصال قاعدة البيانات"""
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except:
            return False
    
    def reset_database(self) -> bool:
        """إعادة تعيين قاعدة البيانات (للتنمية فقط)"""
        try:
            with self.get_cursor(commit=True) as cur:
                cur.execute("DROP TABLE IF EXISTS wallet_transactions CASCADE")
                cur.execute("DROP TABLE IF EXISTS ratings CASCADE")
                cur.execute("DROP TABLE IF EXISTS payments CASCADE")
                cur.execute("DROP TABLE IF EXISTS notifications CASCADE")
                cur.execute("DROP TABLE IF EXISTS active_drivers CASCADE")
                cur.execute("DROP TABLE IF EXISTS rides CASCADE")
                cur.execute("DROP TABLE IF EXISTS users CASCADE")
                cur.execute("DROP TABLE IF EXISTS statistics CASCADE")
            
            self.create_tables()
            logger.warning("⚠️ تم إعادة تعيين قاعدة البيانات")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في إعادة تعيين قاعدة البيانات: {e}")
            return False

# إنشاء كائن قاعدة البيانات العالمي
db = TransportDatabase()

# ============================================================================
# دوال المساعدة للتوافق مع الكود القديم
# ============================================================================

def get_main_menu_from_db(user_id: str):
    """الحصول على القائمة الرئيسية من قاعدة البيانات"""
    user = db.get_user(user_id)
    if not user:
        return None
    
    role = user.get('role')
    
    # الحصول على حالة السائق إذا كان سائقاً
    if role == UserRole.DRIVER:
        active_drivers = db.get_active_drivers()
        is_active = any(driver['user_id'] == user_id for driver in active_drivers)
    
    # بناء القائمة (يجب تحويلها إلى تنسيق telebot)
    # هذه مجرد فكرة، ستحتاج للتعديل ليناسب telebot
    return {
        'role': role,
        'balance': user.get('balance', 0),
        'rating': user.get('rating', 5.0),
        'is_driver_active': is_active if role == UserRole.DRIVER else False
    }

def migrate_from_json_to_postgres():
    """هجرة البيانات من JSON إلى PostgreSQL"""
    try:
        # تحميل البيانات القديمة
        users_old = {}
        rides_old = {}
        drivers_old = {}
        
        if os.path.exists('users.json'):
            with open('users.json', 'r', encoding='utf-8') as f:
                users_old = json.load(f)
        
        if os.path.exists('rides.json'):
            with open('rides.json', 'r', encoding='utf-8') as f:
                rides_old = json.load(f)
        
        if os.path.exists('drivers.json'):
            with open('drivers.json', 'r', encoding='utf-8') as f:
                drivers_old = json.load(f)
        
        # هجرة المستخدمين
        for user_id, user_data in users_old.items():
            db.create_or_update_user({
                'id': user_id,
                'username': user_data.get('username', ''),
                'full_name': user_data.get('full_name', ''),
                'phone': user_data.get('phone'),
                'role': user_data.get('role'),
                'balance': user_data.get('balance', 0.0),
                'rating': user_data.get('rating', 5.0),
                'total_rides': user_data.get('total_rides', 0)
            })
        
        # هجرة الرحلات
        for ride_id, ride_data in rides_old.items():
            db.create_ride({
                'id': ride_id,
                'customer_id': ride_data.get('customer_id'),
                'customer_name': ride_data.get('customer_name'),
                'pickup_location': ride_data.get('pickup_location', {}),
                'status': ride_data.get('status', 'pending'),
                'fare': ride_data.get('fare', 15.0),
                'driver_id': ride_data.get('driver_id'),
                'driver_name': ride_data.get('driver_name')
            })
        
        # هجرة السائقين النشطين
        for driver_id, driver_data in drivers_old.items():
            db.add_active_driver({
                'id': driver_id,
                'username': driver_data.get('username', '')
            })
        
        logger.info("✅ تمت هجرة البيانات من JSON إلى PostgreSQL بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ فشل في هجرة البيانات: {e}")
        return False

# ============================================================================
# اختبار قاعدة البيانات
# ============================================================================

if __name__ == "__main__":
    # اختبار الاتصال
    if db.check_connection():
        print("✅ قاعدة البيانات متصلة بنجاح")
        
        # عرض الإحصائيات
        stats = db.get_system_stats()
        print(f"📊 الإحصائيات: {stats}")
        
        # هجرة البيانات إذا كانت موجودة
        migrate_from_json_to_postgres()
    else:
        print("❌ فشل الاتصال بقاعدة البيانات")