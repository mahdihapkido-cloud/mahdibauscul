import sqlite3
import os
from datetime import datetime
from pathlib import Path

# ستون‌های اصلی (ترتیب ثابت - Excel و رابط به این ترتیب وابسته‌اند)
BASE_COLUMNS = ("id, plate_number, empty_weight, empty_time, final_weight, final_time, "
                "product_code, net_weight, receipt_number, status, created_at, completed_at")

# ستون‌های تصویر (به انتهای جدول اضافه می‌شوند)
IMAGE_COLUMNS = ['empty_plate_image', 'empty_scale_image', 'empty_face_image',
                 'final_plate_image', 'final_scale_image']

class WeighingDatabase:
    def __init__(self, db_path="data/weighing.db"):
        self.db_path = db_path
        Path("data").mkdir(exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """ایجاد جداول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول وزن‌گیری‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weighing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT,
                empty_weight REAL,
                empty_time DATETIME,
                final_weight REAL,
                final_time DATETIME,
                product_code TEXT,
                net_weight REAL,
                receipt_number TEXT,
                status TEXT DEFAULT 'waiting',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
        ''')

        # --- رفع باگ قدیمی: receipt_number قبلاً UNIQUE سراسری بود، ولی شماره‌ها هر روز
        # از ۰۰۱ ریست می‌شوند؛ یعنی از روز دوم به بعد اولین ثبت هر روز با شماره‌ی همان
        # روزِ قبل تداخل می‌کرد و خطای "UNIQUE constraint failed" می‌داد. این قسمت اگر
        # چنین محدودیتی را روی دیتابیس قدیمی پیدا کند، جدول را بدون از دست دادن هیچ
        # داده‌ای بازسازی می‌کند تا این محدودیت اشتباه حذف شود.
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='weighing_old'")
        if cursor.fetchone() is None:  # یعنی migration نیمه‌کاره از قبل نمانده
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='weighing'")
            row = cursor.fetchone()
            if row and 'UNIQUE' in row[0] and 'receipt_number' in row[0]:
                cursor.execute('ALTER TABLE weighing RENAME TO weighing_old')
                cursor.execute('''
                    CREATE TABLE weighing (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plate_number TEXT,
                        empty_weight REAL,
                        empty_time DATETIME,
                        final_weight REAL,
                        final_time DATETIME,
                        product_code TEXT,
                        net_weight REAL,
                        receipt_number TEXT,
                        status TEXT DEFAULT 'waiting',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        completed_at DATETIME
                    )
                ''')
                cursor.execute('PRAGMA table_info(weighing_old)')
                old_cols = [r[1] for r in cursor.fetchall()]
                for col in IMAGE_COLUMNS + ['source']:
                    if col in old_cols:
                        extra_type = "TEXT DEFAULT 'customer'" if col == 'source' else 'TEXT'
                        cursor.execute(f'ALTER TABLE weighing ADD COLUMN {col} {extra_type}')
                cols_sql = ', '.join(old_cols)
                cursor.execute(f'INSERT INTO weighing ({cols_sql}) SELECT {cols_sql} FROM weighing_old')
                cursor.execute('DROP TABLE weighing_old')
                conn.commit()
        
        # جدول کد‌های محصول
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول شماره قبض
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS receipt_counter (
                id INTEGER PRIMARY KEY,
                last_number INTEGER DEFAULT 0,
                reset_date DATE DEFAULT CURRENT_DATE
            )
        ''')
        
        # جدول اقلام بار (هر بار‌گیری یک ردیف)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weighing_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weighing_id INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                weight_after REAL NOT NULL,
                quantity REAL NOT NULL,
                plate_image TEXT,
                scale_image TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (weighing_id) REFERENCES weighing(id)
            )
        ''')
        
        # اضافه‌کردن ستون‌های تصویر به دیتابیس‌های قدیمی
        cursor.execute('PRAGMA table_info(weighing)')
        existing = {row[1] for row in cursor.fetchall()}
        for col in IMAGE_COLUMNS:
            if col not in existing:
                cursor.execute(f'ALTER TABLE weighing ADD COLUMN {col} TEXT')
        # ستون منبع: 'customer' = بار مشتری (پیش‌فرض) / 'internal' = بار خودمان (سیستم اتوماسیون)
        if 'source' not in existing:
            cursor.execute("ALTER TABLE weighing ADD COLUMN source TEXT DEFAULT 'customer'")

        # محصولات پیش‌فرض (اولین اجرا)
        cursor.execute('SELECT COUNT(*) FROM products')
        if cursor.fetchone()[0] == 0:
            import config as _config
            for code, name in getattr(_config, 'DEFAULT_PRODUCTS', []):
                cursor.execute('INSERT OR IGNORE INTO products (code, name) VALUES (?, ?)', (code, name))

        conn.commit()
        conn.close()
    
    def _next_receipt_number_locked(self, cursor):
        """
        شماره‌ی قبض بعدی را داخل یک تراکنش قفل‌شده تولید می‌کند (باید cursor از یک
        تراکنش BEGIN IMMEDIATE باشد) تا اگر دو ثبت هم‌زمان انجام شود، هیچ‌وقت یک
        شماره تکراری تولید نشود.
        """
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT reset_date, last_number FROM receipt_counter WHERE id = 1')
        row = cursor.fetchone()
        if row is None:
            cursor.execute('INSERT INTO receipt_counter (id, last_number, reset_date) VALUES (1, 1, ?)', (today,))
            return "001"
        reset_date, last_number = row
        if reset_date != today:
            cursor.execute('UPDATE receipt_counter SET last_number = 1, reset_date = ? WHERE id = 1', (today,))
            return "001"
        new_number = last_number + 1
        cursor.execute('UPDATE receipt_counter SET last_number = ? WHERE id = 1', (new_number,))
        return f"{new_number:03d}"

    def get_next_receipt_number(self):
        """دریافت شماره قبض بعدی (برای استفاده‌ی مستقل/پیش‌نمایش)"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            conn.execute('BEGIN IMMEDIATE')
            cursor = conn.cursor()
            number = self._next_receipt_number_locked(cursor)
            conn.commit()
            return number
        finally:
            conn.close()
    
    def add_empty_weight(self, weight, plate_image=None, face_image=None, source='customer'):
        """ثبت وزن خالی (بدون پلاک)؛ همان‌جا شماره قبض (شماره پرونده) هم تولید می‌شود
        source: 'customer' (بار مشتری) یا 'internal' (بار خودمان - سیستم اتوماسیون)

        تولید شماره قبض و درج رکورد داخل یک تراکنش قفل‌شده انجام می‌شود تا اگر دو
        ثبت هم‌زمان (مثلاً دوبار کلیک سریع) اتفاق بیفتد، خطای شماره‌ی تکراری رخ ندهد؛
        در صورت برخورد نادر به تکراری، خودکار با شماره‌ی بعدی دوباره تلاش می‌کند."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            for attempt in range(5):
                conn.execute('BEGIN IMMEDIATE')
                cursor = conn.cursor()
                receipt_number = self._next_receipt_number_locked(cursor)
                try:
                    cursor.execute('''
                        INSERT INTO weighing (empty_weight, empty_time, status,
                                              empty_plate_image, empty_face_image,
                                              receipt_number, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (weight, datetime.now(), 'waiting', plate_image, face_image,
                          receipt_number, source))
                    conn.commit()
                    return True, "وزن خالی ثبت شد", receipt_number
                except sqlite3.IntegrityError:
                    conn.rollback()
                    continue
            return False, "خطا در تولید شماره قبض یکتا؛ لطفاً دوباره تلاش کنید", None
        finally:
            conn.close()
    
    def get_waiting_record(self, plate_number):
        """پیدا کردن رکورد منتظر"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, empty_weight, empty_time FROM weighing 
            WHERE plate_number = ? AND status = ?
        ''', (plate_number, 'waiting'))
        
        result = cursor.fetchone()
        conn.close()
        return result

    def get_waiting_list(self, source='customer'):
        """لیست همه‌ی ماشین‌هایی که وزن خالی‌شان ثبت شده و منتظر وزن پر هستند
        source: 'customer' یا 'internal' - فقط رکوردهای همان منبع برگردانده می‌شود"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, plate_number, empty_weight, empty_time, receipt_number,
                   empty_plate_image, empty_face_image
            FROM weighing WHERE status = ? AND COALESCE(source, 'customer') = ? ORDER BY empty_time DESC
        ''', ('waiting', source))
        rows = cursor.fetchall()
        conn.close()
        return [
            {'id': r[0], 'plate_number': r[1], 'empty_weight': r[2], 'empty_time': r[3],
             'receipt_number': r[4], 'plate_image': r[5], 'face_image': r[6]}
            for r in rows
        ]


    def get_waiting_by_receipt(self, receipt_number, source='customer'):
        """پیدا کردن رکورد منتظر با شماره قبض/فیش"""
        if receipt_number is None:
            return None
        key = str(receipt_number).strip()
        if not key:
            return None
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, plate_number, empty_weight, empty_time, receipt_number, "
            "empty_plate_image, empty_face_image FROM weighing "
            "WHERE status = ? AND COALESCE(source, 'customer') = ? "
            "AND CAST(receipt_number AS TEXT) = ? "
            "ORDER BY empty_time DESC LIMIT 1",
            ('waiting', source, key),
        )
        r = cursor.fetchone()
        conn.close()
        if not r:
            return None
        return {
            'id': r[0], 'plate_number': r[1], 'empty_weight': r[2], 'empty_time': r[3],
            'receipt_number': r[4], 'plate_image': r[5], 'face_image': r[6],
        }

    def get_waiting_by_id(self, record_id):
        """گرفتن یک رکورد منتظر با شناسه‌ی آن"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, plate_number, empty_weight, empty_time, receipt_number,
                   empty_plate_image, empty_face_image
            FROM weighing WHERE id = ? AND status = ?
        ''', (record_id, 'waiting'))
        r = cursor.fetchone()
        conn.close()
        if not r:
            return None
        return {'id': r[0], 'plate_number': r[1], 'empty_weight': r[2], 'empty_time': r[3],
                'receipt_number': r[4], 'plate_image': r[5], 'face_image': r[6]}
    
    ITEM_COLS = ("i.seq, i.product_code, COALESCE(p.name, i.product_code), "
                 "i.weight_after, i.quantity, i.plate_image, i.scale_image")

    def _fetch_items(self, cursor, record_id):
        cursor.execute(f'''
            SELECT {self.ITEM_COLS} FROM weighing_items i
            LEFT JOIN products p ON p.code = i.product_code
            WHERE i.weighing_id = ? ORDER BY i.seq
        ''', (record_id,))
        return [
            {'seq': r[0], 'code': r[1], 'name': r[2], 'weight_after': r[3],
             'quantity': r[4], 'plate_image': r[5], 'scale_image': r[6]}
            for r in cursor.fetchall()
        ]

    def get_waiting_items(self, plate_number):
        """
        اقلام ثبت‌شده‌ی ماشینی که هنوز فیش نگرفته.
        بازگشت: (empty_weight, [items]) یا None اگر ماشین منتظر نیست
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, empty_weight FROM weighing WHERE plate_number = ? AND status = ?',
                       (plate_number, 'waiting'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        items = self._fetch_items(cursor, row[0])
        conn.close()
        return row[1], items

    def get_waiting_items_by_id(self, record_id):
        """مثل get_waiting_items ولی با شناسه‌ی رکورد (چون پلاک خودکار خوانده نمی‌شود)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, empty_weight FROM weighing WHERE id = ? AND status = ?',
                       (record_id, 'waiting'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        items = self._fetch_items(cursor, row[0])
        conn.close()
        return row[1], items

    def add_load_item(self, plate_number, weight_after, product_code,
                      plate_image=None, scale_image=None):
        """
        ثبت یک بار‌گیری: مقدار بار = وزن فعلی - وزن قبلی
        (وزن قبلی = وزن خالی، یا وزن بعد از بار قبلی)
        بازگشت: (موفق؟، پیام، مقدار بار)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, empty_weight FROM weighing WHERE plate_number = ? AND status = ?',
                       (plate_number, 'waiting'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "رکورد منتظر پیدا نشد؛ ابتدا وزن خالی این پلاک را ثبت کنید", None

        record_id, empty_weight = row
        return self._insert_load_item(conn, cursor, record_id, empty_weight, weight_after,
                                      product_code, plate_image, scale_image)

    def add_load_item_by_id(self, record_id, weight_after, product_code,
                            plate_image=None, scale_image=None):
        """مثل add_load_item ولی با شناسه‌ی رکورد (برای بارهای خودمان - سیستم اتوماسیون)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT empty_weight FROM weighing WHERE id = ? AND status = ?',
                       (record_id, 'waiting'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "رکورد منتظر پیدا نشد", None

        empty_weight = row[0]
        return self._insert_load_item(conn, cursor, record_id, empty_weight, weight_after,
                                      product_code, plate_image, scale_image)

    def _insert_load_item(self, conn, cursor, record_id, empty_weight, weight_after,
                          product_code, plate_image, scale_image):
        cursor.execute('SELECT seq, weight_after FROM weighing_items WHERE weighing_id = ? '
                       'ORDER BY seq DESC LIMIT 1', (record_id,))
        last = cursor.fetchone()
        last_seq, previous_weight = (last[0], last[1]) if last else (0, empty_weight)

        quantity = weight_after - previous_weight
        if quantity <= 0:
            conn.close()
            return False, (f"وزن باید از وزن قبلی ({previous_weight:.1f}) بیشتر باشد "
                           f"(وزن واردشده: {weight_after:.1f})"), None

        cursor.execute('''
            INSERT INTO weighing_items (weighing_id, seq, product_code, weight_after,
                                        quantity, plate_image, scale_image)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (record_id, last_seq + 1, product_code, weight_after, quantity,
              plate_image, scale_image))
        conn.commit()
        conn.close()
        return True, "بار ثبت شد", quantity

    def complete_weighing(self, record_id, final_weight, plate_image=None, scale_image=None):
        """
        پایان کار و صدور فیش برای رکوردی که با شناسه‌ی خودش مشخص شده.
        وزن خالص = وزن پر - وزن خالی. شماره قبض همان است که موقع ثبت وزن خالی تولید شد.
        بازگشت: (موفق؟، شماره قبض/پیام خطا، رکورد)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT empty_weight, receipt_number FROM weighing WHERE id = ? AND status = ?',
                       (record_id, 'waiting'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "رکورد منتظر پیدا نشد", None

        empty_weight, receipt_number = row
        if final_weight <= empty_weight:
            conn.close()
            return False, (f"وزن پر باید از وزن خالی ({empty_weight:.1f}) بیشتر باشد "
                           f"(وزن خوانده‌شده: {final_weight:.1f})"), None

        net_weight = final_weight - empty_weight
        now = datetime.now()

        cursor.execute('''
            UPDATE weighing
            SET final_weight = ?, final_time = ?, net_weight = ?,
                status = ?, completed_at = ?, final_plate_image = ?, final_scale_image = ?
            WHERE id = ?
        ''', (final_weight, now, net_weight, 'completed', now,
              plate_image, scale_image, record_id))
        conn.commit()

        cursor.execute(f'SELECT {BASE_COLUMNS} FROM weighing WHERE id = ?', (record_id,))
        record = cursor.fetchone()
        conn.close()
        return True, receipt_number, record

    def get_internal_stats(self, since=None):
        """آمار سیستم اتوماسیون؛ فقط رکوردهای تکمیل‌شده و اقلام بار خودمان.
        وزن خالی و وزن پرِ ماشین عمداً در خروجی آماری استفاده نمی‌شوند.
        weight_after همان عدد ناخالص ثبت‌شده در لحظه‌ی ثبت هر بار است.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        params = []
        where = "COALESCE(w.source, 'customer') = 'internal' AND w.status = 'completed'"
        if since:
            where += " AND wi.created_at >= ?"
            params.append(since)
        cursor.execute(f"""
            SELECT wi.created_at, wi.product_code, COALESCE(p.name, wi.product_code),
                   wi.weight_after, wi.quantity, wi.weighing_id
            FROM weighing_items wi
            JOIN weighing w ON w.id = wi.weighing_id
            LEFT JOIN products p ON p.code = wi.product_code
            WHERE {where}
            ORDER BY wi.created_at DESC
        """, params)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_products(self):
        """گرفتن تمام محصولات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT code, name FROM products ORDER BY name')
        products = cursor.fetchall()
        conn.close()
        return products
    
    def add_product(self, code, name):
        """اضافه کردن محصول جدید"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO products (code, name) VALUES (?, ?)', 
                          (code, name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def delete_product(self, code):
        """حذف محصول با کد مشخص"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM products WHERE code = ?', (code,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_product(self, old_code, new_code, new_name):
        """ویرایش محصول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE products SET code=?, name=? WHERE code=?',
                           (new_code, new_name, old_code))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_all_records(self):
        """دریافت تمام رکوردها (برای Excel)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f'SELECT {BASE_COLUMNS} FROM weighing ORDER BY completed_at DESC')
        records = cursor.fetchall()
        conn.close()
        return records

    def delete_waiting_record(self, record_id):
        """
        حذف یک ماشینِ در حال انتظار (هنوز فیش نگرفته) از لیست.
        بازگشت: (موفق؟، پیام، دیکشنری مسیر عکس‌های ثبت‌شده‌ی همان رکورد)
        مسیر عکس‌ها را برمی‌گرداند تا در سطح رابط کاربری فایل‌ها هم پاک شوند.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT receipt_number, empty_plate_image, empty_face_image
            FROM weighing WHERE id = ? AND status = ?
        ''', (record_id, 'waiting'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "رکورد منتظر پیدا نشد", {}

        cursor.execute('DELETE FROM weighing WHERE id = ? AND status = ?', (record_id, 'waiting'))
        conn.commit()
        conn.close()

        receipt_number, plate_image, face_image = row
        return True, "حذف شد", {
            'receipt_number': receipt_number,
            'plate_image': plate_image,
            'face_image': face_image,
        }

