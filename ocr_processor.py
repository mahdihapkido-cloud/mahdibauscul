"""
خواندن وزن از نمایشگر باسکول.
  - وزن : بسته به config.WEIGHT_READER
            "easyocr"       -> EasyOCR (پیشنهادی - اعداد فارسی و انگلیسی)
            "yolo"          -> مدل YOLOv8 ترین‌شده برای رقم‌های باسکول
            "seven_segment" -> نمایشگر دیجیتال ۷-سگمنتی (seven_segment.py)
            "plain"         -> اعداد انگلیسی معمولی، بدون ML (simple_digits.py)
سیستم پلاک‌خوان حذف شده است؛ این ماژول فقط وزن می‌خواند.
"""
import config
from pathlib import Path
from seven_segment import decode_seven_segment
from simple_digits import decode_plain_digits
import re

PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
_TO_ENGLISH = {}
for _i, _d in enumerate('۰۱۲۳۴۵۶۷۸۹'):
    _TO_ENGLISH[_d] = str(_i)
for _i, _d in enumerate('٠١٢٣٤٥٦٧٨٩'):
    _TO_ENGLISH[_d] = str(_i)


def to_english_digits(text):
    """تبدیل ارقام فارسی/عربی به انگلیسی"""
    return ''.join(_TO_ENGLISH.get(c, c) for c in text)


def to_persian_digits(text):
    """تبدیل ارقام انگلیسی به فارسی"""
    return ''.join(PERSIAN_DIGITS[int(c)] if '0' <= c <= '9' else c for c in text)


def crop_to_roi(frame, roi):
    """برش تصویر به کادر انتخابی (roi = x1,y1,x2,y2 بین ۰ و ۱) - اگر نبود کل تصویر"""
    if frame is None or not roi:
        return frame
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = roi
    crop = frame[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)]
    return crop if crop.size else frame


class OCRProcessor:
    def __init__(self):
        self.last_debug = {'weight': ''}
        self._yolo_model = None
        self._yolo_loaded = False
        self._easyocr_reader = None
        self._easyocr_loaded = False

    def _load_easyocr(self):
        """لود EasyOCR (فقط en برای سرعت بیشتر روی ارقام نمایشگر)."""
        if self._easyocr_loaded:
            return self._easyocr_reader is not None
        self._easyocr_loaded = True
        try:
            import easyocr
            # فقط en: سریع‌تر و برای رقم‌های نمایشگر کافی است
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            print("[EasyOCR] مدل با موفقیت لود شد")
            return True
        except Exception as e:
            self.last_debug['weight'] = f"خطا در لود EasyOCR: {e}"
            print(f"[EasyOCR] خطا در لود: {e}")
            self._easyocr_reader = None
            return False

    def preload(self):
        """پیش‌بارگذاری مدل در پس‌زمینه تا اولین کلیک گیر نکند."""
        try:
            self._load_easyocr()
        except Exception as e:
            print(f"[EasyOCR] preload: {e}")

    def _read_weight_easyocr(self, frame):
        """خواندن وزن با EasyOCR — سریع، حداکثر ۲ نسخه تصویر."""
        if frame is None:
            self.last_debug['weight'] = "وزن: فریم خالی"
            return None
        if not self._load_easyocr():
            return None
        try:
            import cv2

            # فقط دو نسخه: اصلی بزرگ‌شده + آستانه‌گذاری
            h, w = frame.shape[:2]
            if max(h, w) < 200:
                img = cv2.resize(frame, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
            else:
                img = cv2.resize(frame, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            _, th = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            candidates = []
            for variant in (enhanced, th, cv2.bitwise_not(th)):
                results = self._easyocr_reader.readtext(
                    variant,
                    allowlist='0123456789',
                    detail=1,
                    paragraph=False,
                )
                for (_bbox, text, conf) in results:
                    if conf < 0.2:
                        continue
                    cleaned = re.sub(r'[^\d]', '', to_english_digits(text))
                    if cleaned and cleaned.isdigit() and 1 <= len(cleaned) <= getattr(config, 'WEIGHT_MAX_DIGITS', 6):
                        candidates.append((int(cleaned), float(conf), cleaned))
                # اگر با اطمینان خوب پیدا شد، زود تمام کن
                if candidates and max(c[1] for c in candidates) >= 0.55:
                    break

            if not candidates:
                self.last_debug['weight'] = (
                    "وزن: EasyOCR هیچ رقمی پیدا نکرد - کادر سبز را دقیق دور عدد بکشید"
                )
                return None

            candidates.sort(key=lambda x: (-x[1], -len(x[2])))
            best_val, best_conf, _ = candidates[0]
            self.last_debug['weight'] = f"وزن: {best_val} (EasyOCR conf={best_conf:.2f})"
            return best_val
        except Exception as e:
            print(f"خطا در EasyOCR: {e}")
            self.last_debug['weight'] = f"وزن: خطا EasyOCR ({e})"
            return None

    def _load_yolo(self):
        """لود تنبل مدل YOLOv8 فقط وقتی واقعاً نیاز باشد."""
        if self._yolo_loaded:
            return self._yolo_model is not None

        self._yolo_loaded = True
        model_path = Path(getattr(config, 'YOLO_MODEL_PATH', 'models/scale_yolo.pt'))
        if not model_path.is_absolute():
            # نسبت به پوشه‌ی پروژه (کنار main.py)
            base = Path(__file__).resolve().parent
            model_path = base / model_path

        if not model_path.exists():
            self.last_debug['weight'] = (
                f"فایل مدل YOLO پیدا نشد: {model_path}\n"
                "فایل .pt را داخل پوشه‌ی models بگذارید."
            )
            print(f"[YOLO] مدل پیدا نشد: {model_path}")
            return False

        try:
            from ultralytics import YOLO
            self._yolo_model = YOLO(str(model_path))
            print(f"[YOLO] مدل با موفقیت لود شد: {model_path}")
            return True
        except Exception as e:
            self.last_debug['weight'] = f"خطا در لود مدل YOLO: {e}"
            print(f"[YOLO] خطا در لود: {e}")
            self._yolo_model = None
            return False

    def read_weight_from_display(self, frame):
        """
        خواندن عدد نمایشگر باسکول.
        بهتر است فقط ناحیه‌ی عدد (کادر سبز) به این تابع داده شود.
        بازگشت: عدد (int) یا None وقتی خوانش قابل اتکا نیست.
        """
        # فقط EasyOCR — مدل‌های آموزش‌دیده (YOLO و غیره) استفاده نمی‌شوند
        return self._read_weight_easyocr(frame)

        # کدهای زیر دیگر اجرا نمی‌شوند (نگه داشته شده برای سازگاری)
        reader = getattr(config, 'WEIGHT_READER', 'easyocr')
        if reader == 'yolo':
            return self._read_weight_yolo(frame)
        if reader == 'plain':
            return self._read_weight_plain(frame)
        # seven_segment
        try:
            digits, approx = None, False
            for max_dist in (0, 1):
                digits = decode_seven_segment(frame, max_dist=max_dist)
                if digits:
                    approx = max_dist > 0
                    break

            if not digits:
                self.last_debug['weight'] = (
                    "وزن: هیچ رقمی دیده نشد - کادر سبز را فقط دور اعداد "
                    "نمایشگر بکشید و نور روی نمایشگر را بررسی کنید"
                )
                return None

            if len(digits) > config.WEIGHT_MAX_DIGITS:
                self.last_debug['weight'] = (
                    f"رد شد: تعداد رقم‌ها بیشتر از {config.WEIGHT_MAX_DIGITS} است؛ "
                    "کادر OCR را تنظیم کنید."
                )
                return None

            self.last_debug['weight'] = (
                f"وزن: {int(digits)}"
                + (" (تقریبی - لطفاً با نمایشگر مقایسه کنید)" if approx else "")
            )
            if not digits.isdigit():
                self.last_debug['weight'] = "رد شد: خروجی OCR فقط باید شامل رقم باشد."
                return None
            return int(digits)
        except Exception as e:
            print(f"خطا در خواندن وزن: {e}")
            self.last_debug['weight'] = f"وزن: خطا ({e})"
            return None

    def _read_weight_yolo(self, frame):
        """
        خواندن وزن با مدل YOLOv8.
        - رقم‌ها از چپ به راست
        - صفرهای اول حذف می‌شوند
        - چند پیش‌پردازش امتحان می‌شود و بهترین نتیجه انتخاب می‌شود
        """
        if frame is None:
            self.last_debug['weight'] = "وزن: فریم خالی"
            return None

        if not self._load_yolo():
            return None

        try:
            import cv2
            import numpy as np

            conf_threshold = float(getattr(config, 'YOLO_CONF_THRESHOLD', 0.15))
            iou_threshold = float(getattr(config, 'YOLO_IOU_THRESHOLD', 0.45))

            # ---- ساخت چند نسخه پیش‌پردازش‌شده ----
            variants = []

            # 1) تصویر اصلی
            variants.append(('orig', frame))

            # 2) بزرگ‌نمایی
            up = cv2.resize(frame, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
            variants.append(('up', up))

            # 3) بزرگ‌نمایی + Otsu معکوس (برای رقم‌های آبی روی زمینه تیره خیلی مؤثر است)
            gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
            _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            inv = cv2.cvtColor(cv2.bitwise_not(th), cv2.COLOR_GRAY2BGR)
            variants.append(('otsu_inv', inv))

            # 4) Otsu عادی
            otsu = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
            variants.append(('otsu', otsu))

            def decode_one(img, tag):
                results = self._yolo_model.predict(
                    source=img, conf=conf_threshold, iou=iou_threshold, verbose=False
                )
                if not results:
                    return None
                result = results[0]
                boxes = result.boxes
                if boxes is None or len(boxes) == 0:
                    return None

                names = result.names
                raw = []
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = str(names.get(cls_id, '')).strip().lower()
                    if name not in '0123456789':
                        continue
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    h = max(1.0, y2 - y1)
                    w = max(1.0, x2 - x1)
                    aspect = w / h
                    # فقط ۷ خیلی باریک → ۱
                    if name == '7' and aspect < 0.32:
                        name = '1'
                    raw.append((cx, cy, name, conf, h))

                if not raw:
                    return None

                # انتخاب ردیف اصلی
                raw.sort(key=lambda t: t[1])
                rows = []
                for det in raw:
                    placed = False
                    for row in rows:
                        ref_cy = sum(d[1] for d in row) / len(row)
                        ref_h = sum(d[4] for d in row) / len(row)
                        if abs(det[1] - ref_cy) < ref_h * 0.55:
                            row.append(det)
                            placed = True
                            break
                    if not placed:
                        rows.append([det])

                best_row = max(rows, key=lambda row: (len(row), sum(d[3] for d in row) / len(row)))
                best_row.sort(key=lambda t: t[0])

                # ادغام نزدیک‌ها
                cleaned = []
                for det in best_row:
                    if cleaned and abs(det[0] - cleaned[-1][0]) < max(10.0, cleaned[-1][4] * 0.35):
                        if det[3] > cleaned[-1][3]:
                            cleaned[-1] = det
                    else:
                        cleaned.append(det)

                digits_str = ''.join(d[2] for d in cleaned)
                if not digits_str or not digits_str.isdigit():
                    return None
                if len(digits_str) > config.WEIGHT_MAX_DIGITS:
                    return None

                avg_conf = sum(d[3] for d in cleaned) / len(cleaned)
                return {
                    'tag': tag,
                    'raw': digits_str,
                    'weight': int(digits_str),  # صفرهای اول حذف می‌شوند
                    'avg_conf': avg_conf,
                    'n': len(cleaned),
                }

            candidates = []
            for tag, im in variants:
                hit = decode_one(im, tag)
                if hit:
                    candidates.append(hit)

            if not candidates:
                self.last_debug['weight'] = (
                    "وزن: هیچ رقمی دیده نشد - کادر سبز را فقط دور اعداد "
                    "نمایشگر بکشید و نور را بررسی کنید"
                )
                return None

            # امتیاز: تعداد رقم معقول (۳ تا ۶) + اطمینان بالا
            # ترجیح به نتیجه‌ای که صفرهای پیشرو داشته باشد (علامت نمایشگر واقعی)
            def score(c):
                bonus = 0.0
                if 3 <= c['n'] <= 6:
                    bonus += 1.0
                if c['raw'].startswith('0') and c['n'] >= 4:
                    bonus += 0.5  # شبیه نمایشگر ۶ رقمی
                if c['tag'] == 'otsu_inv':
                    bonus += 0.3  # این پیش‌پردازش روی این باسکول بهتر جواب داده
                return bonus + c['avg_conf']

            best = max(candidates, key=score)

            conf_pct = best['avg_conf'] * 100
            note = ""
            if best['avg_conf'] < 0.45:
                note = " (اطمینان پایین - با نمایشگر مقایسه کنید)"

            self.last_debug['weight'] = (
                f"وزن: {best['weight']}  |  YOLO/{best['tag']}  |  "
                f"خام={best['raw']}  |  اطمینان {conf_pct:.0f}%{note}"
            )
            return best['weight']

        except Exception as e:
            print(f"خطا در خواندن وزن با YOLO: {e}")
            self.last_debug['weight'] = f"وزن: خطا YOLO ({e})"
            return None

    def _read_weight_plain(self, frame):
        """خواندن عدد انگلیسی معمولی (نه ۷-سگمنتی) با پردازش تصویر کلاسیک، بدون ML"""
        try:
            digits, conf = decode_plain_digits(frame)
            if not digits:
                self.last_debug['weight'] = (
                    "وزن: هیچ رقمی دیده نشد - کادر سبز را فقط دور اعداد "
                    "بکشید و مطمئن شوید عدد واضح و بدون بازتاب است"
                )
                return None
            if len(digits) > config.WEIGHT_MAX_DIGITS:
                digits = digits[-config.WEIGHT_MAX_DIGITS:]
                conf = min(conf, 0.5)
            self.last_debug['weight'] = (
                f"وزن: {int(digits)} (اطمینان {conf * 100:.0f}%)"
                + (" - تقریبی؛ لطفاً با نمایشگر مقایسه کنید" if conf < 0.65 else "")
            )
            return int(digits)
        except Exception as e:
            print(f"خطا در خواندن وزن: {e}")
            self.last_debug['weight'] = f"وزن: خطا ({e})"
            return None
