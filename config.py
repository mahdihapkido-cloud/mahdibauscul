# ⚙️ تنظیمات سیستم توزین

# ===== دوربین =====
CAMERA_ID = 0  # (قدیمی - دیگر استفاده نمی‌شود)
AVAILABLE_CAMERAS = [0, 1, 2]   # شماره دوربین‌هایی که در لیست انتخاب نمایش داده می‌شود
PLATE_CAMERA_ID = 0          # پیش‌فرض: دوربین ماشین
SCALE_CAMERA_ID = 1          # پیش‌فرض: دوربین باسکول (هرگز به صورت زنده نمایش داده نمی‌شود)
FACE_CAMERA_ID = 2           # پیش‌فرض: دوربین صورت (بالای مانیتور)
SETTINGS_FILE = "settings.json"   # انتخاب شما اینجا ذخیره می‌شود
IMAGES_DIRECTORY = "images"       # فقط برای آرشیو نهایی استفاده می‌شود (پوشه‌ی archive)؛
                                   # عکس‌های خام حین کار روی دیسک ذخیره نمی‌شوند
SAVE_DEBUG_CROPS = False          # اگر True شود، تصویر کراپ‌شده‌ی ناحیه‌ی عدد باسکول هم برای دیباگ ذخیره می‌شود
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# ===== OCR =====
OCR_LANGUAGES = ['fa', 'en']  # فارسی و انگلیسی
OCR_CONFIDENCE_THRESHOLD = 0.3  # حداقل اطمینان
WEIGHT_MAX_DIGITS = 6           # حداکثر تعداد رقم وزن (بیشتر از این رد می‌شود)

# روش خواندن وزن از دوربین باسکول:
#   "easyocr"       = EasyOCR (پیشنهادی - اعداد فارسی و انگلیسی)
#   "yolo"          = مدل YOLOv8 ترین‌شده (models/scale_yolo.pt)
#   "plain"         = اعداد انگلیسی معمولی (بدون ML) - simple_digits.py
#   "seven_segment" = نمایشگر دیجیتال ۷-سگمنتی - seven_segment.py
WEIGHT_READER = "easyocr"

# مسیر مدل YOLOv8 (نسبت به پوشه‌ی پروژه یا مسیر کامل)
YOLO_MODEL_PATH = "models/scale_yolo.pt"
YOLO_CONF_THRESHOLD = 0.15      # حداقل اطمینان تشخیص هر رقم
YOLO_IOU_THRESHOLD = 0.45       # آستانه NMS

ALLOW_APPROX_WEIGHT = True

# ===== پایگاه داده =====
DB_PATH = "data/weighing.db"

# ===== فیش =====
RECEIPT_START_NUMBER = 1
RECEIPT_DECIMAL_PLACES = 1  # رقم اعشار برای وزن
PRINT_DIRECTLY = True  # چاپ مستقیم بدون پرسیدن
RECEIPT_PAGE_SIZE = "A5"
COMPANY_NAME = "باسکول ۵۰ تنی همت"
COMPANY_ADDRESS = "آدرس: آمل – دابودشت – خیابان دریا – مجتمع حیدری"

# ===== محصولات پیش‌فرض =====
DEFAULT_PRODUCTS = [
    ('BRR001', 'برنج'),
    ('PRN001', 'پرنج'),
    ('GLR001', 'گلاب'),
    ('OIL001', 'روغن'),
    ('SYP001', 'سیب'),
    ('ORG001', 'پرتقال'),
]

# ===== رابط کاربری =====
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
FONT_SIZE = 12
FONT_FAMILY = "Arial"

# ===== صادرات =====
EXPORT_DIRECTORY = "exports"
RECEIPT_DIRECTORY = "receipts"

# ===== پیامک کاوه‌نگار =====
KAVENEGAR_API_KEY = "47666B426270695265335239716D42722F47702F7066376459447A4650325846726778373961456E3375413D"   # ← کلید API خود را اینجا بگذارید
MANAGER_PHONE     = "09232856241"          # ← شماره موبایل مدیر
SMS_SENDER        = "0018018949161"           # ← خط ارسال کاوه‌نگار

# ===== دیگر =====
LANGUAGE = 'fa'  # فارسی
AUTO_OCR_DELAY = 2  # ثانیه برای OCR خودکار

# ===== صداها =====
SOUNDS_DIRECTORY = "sounds"
SOUNDS = {
    # صفحه اول -> ورود به صفحه‌ی «ثبت وزن ماشین»
    'open_empty_weight_page': f"{SOUNDS_DIRECTORY}/open_empty_weight_page.mp3",
    # داخل صفحه‌ی «ثبت وزن ماشین» -> زدن دکمه‌ی «ثبت وزن ماشین»
    'confirm_empty_weight': f"{SOUNDS_DIRECTORY}/confirm_empty_weight.mp3",
    # صفحه اول -> ورود به صفحه‌ی «ماشین‌های بار زده» (لیست در انتظار)
    'open_waiting_list': f"{SOUNDS_DIRECTORY}/open_waiting_list.mp3",
    # ورود به پروفایل هر ماشین (باز کردن جزئیات یک ماشین از لیست)
    'open_vehicle_profile': f"{SOUNDS_DIRECTORY}/open_vehicle_profile.mp3",
    # زدن دکمه‌ی «ثبت و دریافت فیش»
    'issue_receipt': f"{SOUNDS_DIRECTORY}/issue_receipt.mp3",
}

