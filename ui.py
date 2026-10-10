"""
رابط کاربری سیستم توزین خودرو

صفحه اول دو گزینه دارد:
  ۱) ثبت وزن ماشین (وزن خالی + عکس ماشین و صورت راننده)
  ۲) ثبت وزن ماشین‌های بار زده و دریافت فیش

نکته‌ی مهم: پلاک و وزن فقط به‌صورت خودکار از دوربین خوانده می‌شوند و
هیچ کادر ورودی‌ای برای تغییر دستی آن‌ها وجود ندارد. دوربین باسکول هرگز
به‌صورت زنده نمایش داده نمی‌شود؛ فقط نتیجه‌ی متنی OCR آن در کادر وزن دیده می‌شود.
"""
import sys
import json
import time
import threading
import shutil
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta

import cv2
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QComboBox,
                             QLineEdit, QMessageBox, QDialog, QListWidget,
                             QListWidgetItem, QFrame, QStackedWidget,
                             QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QSizePolicy, QScrollArea, QGridLayout, QSlider, QProgressBar, QCheckBox, QSpinBox, QDoubleSpinBox, QFileDialog)
from PyQt6.QtCore import (Qt, QThread, QTimer, QRect, QRectF, QPoint, QPointF, pyqtSignal,
                          QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
                          QSequentialAnimationGroup, QAbstractAnimation)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath, QPen, QColor, QFont, QBrush, QPalette

import config
from database import WeighingDatabase
from sms import send_receipt_sms
from ocr_processor import OCRProcessor, crop_to_roi, to_english_digits, to_persian_digits
from jalali import format_jalali_date, format_jalali_datetime
from receipt import ReceiptGenerator
from sounds import SoundManager
from arduino_controller import ArduinoController


# =====================================================================
#                              ظاهر برنامه
# =====================================================================
STYLE = """
* { font-family: "Vazirmatn", "Segoe UI", "Tahoma", "Arial"; }
QMainWindow { background: #0B1120; }
QDialog { background: #0F172A; }
QWidget { background: #0B1120; }

QLabel { color: #E2E8F0; background: transparent; font-size: 14px; }
QLabel#h1 { font-size: 30px; font-weight: 800; color: #F8FAFC; }
QLabel#h2 { font-size: 22px; font-weight: 700; color: #F1F5F9; }
QLabel#sub { color: #94A3B8; font-size: 14px; }
QLabel#cardTitle { color: #94A3B8; font-size: 13px; font-weight: 600; }
QLabel#unit { color: #94A3B8; font-size: 13px; }
QLabel#op { color: #CBD5E1; font-size: 36px; font-weight: 700; }
QLabel#debug { color: #64748B; font-size: 11px; }
QLabel#preview { background: #1E293B; color: #64748B; border-radius: 14px; font-size: 13px; border: 1px solid #334155; }

QFrame#card { background: #1E293B; border: 1px solid #334155; border-radius: 20px; }

QPushButton { font-size: 15px; font-weight: 600; border-radius: 14px; padding: 12px 26px; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #D97706, stop:1 #F59E0B); color: #0B1120; border: none; }
QPushButton#primary:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B45309, stop:1 #D97706); }
QPushButton#success { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #D97706, stop:1 #F59E0B); color: #0B1120; border: none; }
QPushButton#success:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B45309, stop:1 #D97706); }
QPushButton#primary:disabled, QPushButton#success:disabled { background: #334155; color: #64748B; }
QPushButton#ghost { background: #1E293B; color: #E2E8F0; border: 1px solid #475569; }
QPushButton#ghost:hover { background: #334155; border: 1px solid #64748B; }
QPushButton#glowSuccess { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #D97706, stop:1 #FBBF24);
            color: #0B1120; border: 2px solid #FCD34D; border-radius: 16px; font-size: 18px; font-weight: 700; }
QPushButton#glowSuccess:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B45309, stop:1 #F59E0B); }
QPushButton#glowSuccess:disabled { background: #334155; color: #64748B; border: 2px solid #334155; }

QComboBox { padding: 10px 16px; border: 1px solid #475569; border-radius: 12px;
            background: #1E293B; font-size: 15px; min-height: 24px; color: #F1F5F9; }
QComboBox:hover { border: 1px solid #F59E0B; }
QComboBox::drop-down { border: none; width: 30px; }
QComboBox QAbstractItemView { background: #1E293B; color: #F1F5F9; border: 1px solid #475569;
            selection-background-color: #334155; selection-color: #FBBF24; outline: 0; padding: 4px; }

QLineEdit { padding: 10px 14px; border: 1px solid #475569; border-radius: 12px;
            background: #1E293B; font-size: 14px; color: #F1F5F9; }
QLineEdit:focus { border: 1px solid #F59E0B; }

QTableWidget { border: none; background: transparent; font-size: 14px; color: #E2E8F0; }
QTableWidget::item { padding: 6px; border-bottom: 1px solid #334155; }
QHeaderView::section { background: #1E293B; color: #94A3B8; border: none;
                       padding: 10px; font-weight: 600; font-size: 13px; }
QListWidget { border: 1px solid #334155; border-radius: 12px; background: #1E293B; padding: 6px; font-size: 14px; color: #E2E8F0; }
QListWidget::item { padding: 8px; }
QListWidget::item:selected { background: #334155; color: #FBBF24; }

QFrame#settingsSection { background: #1E293B; border: 1px solid #334155; border-radius: 16px; }
QFrame#cameraCard { background: #0F172A; border: 1px solid #334155; border-radius: 14px; }
QLabel#sectionTitle { color: #F8FAFC; font-size: 16px; font-weight: 800; }
QLabel#fieldLabel { color: #CBD5E1; font-size: 14px; font-weight: 700; }
QLabel#pathLabel { color: #94A3B8; background: #0F172A; border: 1px solid #334155; border-radius: 10px; padding: 9px 12px; }
QScrollArea#settingsScroll, QScrollArea#pageScroll { border: none; background: transparent; }
QScrollBar:vertical { width: 10px; background: transparent; margin: 4px 0 4px 0; }
QScrollBar::handle:vertical { background: #475569; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

QProgressBar { border: none; background: #334155; border-radius: 6px; height: 10px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #D97706, stop:1 #FBBF24); border-radius: 6px; }
QSlider::groove:horizontal { height: 6px; background: #334155; border-radius: 3px; }
QSlider::handle:horizontal { background: #F59E0B; width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; }
QSlider::sub-page:horizontal { background: #D97706; border-radius: 3px; }
"""

BANNER_STYLES = {
    'ok':    ("#1C1917", "#F59E0B", "#FBBF24"),
    'error': ("#1C1017", "#F87171", "#FCA5A5"),
    'warn':  ("#1C1910", "#FBBF24", "#FDE68A"),
    'info':  ("#0F172A", "#38BDF8", "#7DD3FC"),
}

VALUE_COLORS = {'normal': "#F8FAFC", 'empty': "#64748B", 'ok': "#FBBF24", 'error': "#F87171"}


def fmt(v):
    """نمایش عدد: ۱٬۵۰۰ یا — اگر مقدار نبود"""
    if v is None:
        return "—"
    s = f"{float(v):,.1f}"
    return s[:-2] if s.endswith(".0") else s


def add_shadow(widget, blur=32, dy=8, alpha=60):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return eff


def archive_folder_for(receipt_number, source='customer'):
    """پوشه‌ی بایگانیِ یک ماشین (بر اساس شماره قبض) داخل پوشه‌ی images
    source: 'customer' (بار مشتری) یا 'internal' (بار خودمان) - در دو زیرپوشه‌ی جدا بایگانی می‌شوند"""
    return Path(config.IMAGES_DIRECTORY) / "archive" / source / str(receipt_number)


def archive_vehicle_files(receipt_number, plate_image, face_image, pdf_file=None, source='customer'):
    """
    بعد از ثبت نهایی، یک پوشه‌ی جداگانه برای همین ماشین می‌سازد و عکس ماشین،
    عکس راننده (که تا این لحظه فقط به‌صورت bytes داخل دیتابیس بودند و هیچ فایلی
    روی دیسک نداشتند) و فیش مشتری (PDF) را برای بایگانی در آن می‌نویسد.
    آرشیو بارهای مشتری و بارهای خودمان (سیستم اتوماسیون) کاملاً جدا نگه داشته می‌شود.
    این تنها جایی‌ست که تصاویر واقعاً روی دیسک ذخیره می‌شوند.
    plate_image/face_image می‌توانند bytes (حالت جدید) یا مسیر فایل رشته‌ای
    (سازگاری با رکوردهای خیلی قدیمی) باشند.
    """
    if not receipt_number:
        return
    try:
        folder = archive_folder_for(receipt_number, source)
        folder.mkdir(parents=True, exist_ok=True)
        for value, name in ((plate_image, 'car'), (face_image, 'driver')):
            if not value:
                continue
            if isinstance(value, (bytes, bytearray)):
                (folder / f"{name}.jpg").write_bytes(bytes(value))
            elif Path(value).exists():  # سازگاری با رکوردهای قدیمی (مسیر فایل)
                ext = Path(value).suffix or '.jpg'
                shutil.copy2(value, folder / f"{name}{ext}")
        if pdf_file and Path(pdf_file).exists():
            ext = Path(pdf_file).suffix or '.pdf'
            shutil.copy2(pdf_file, folder / f"receipt{ext}")
    except Exception as e:
        print(f"بایگانی فایل‌های ماشین ناموفق بود: {e}")


def delete_files(*paths):
    """چند مسیر فایل را (در صورت وجود) پاک می‌کند؛ خطاها را نادیده می‌گیرد
    (عکس‌های در حال انتظار دیگر فایل نیستند - فقط bytes داخل دیتابیس‌اند و با
    حذف رکورد به‌خودی‌خود از بین می‌روند - این تابع فقط برای مسیرهای رشته‌ای
    قدیمی نگه داشته شده)"""
    for path in paths:
        if not path or not isinstance(path, str):
            continue
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
        except Exception as e:
            print(f"حذف فایل {path} ناموفق بود: {e}")


def pixmap_from_image_value(value):
    """
    مقدار ستون تصویر را به QPixmap تبدیل می‌کند.
    از حالت جدید (bytes ذخیره‌شده در دیتابیس) و مسیر فایل رشته‌ای (رکوردهای خیلی
    قدیمی که هنوز به فایل روی دیسک اشاره می‌کنند) هر دو پشتیبانی می‌کند.
    """
    if not value:
        return None
    if isinstance(value, (bytes, bytearray)):
        pix = QPixmap()
        return pix if pix.loadFromData(bytes(value)) else None
    if isinstance(value, str) and Path(value).exists():
        pix = QPixmap(value)
        return None if pix.isNull() else pix
    return None


def rounded_pixmap(pixmap, size, radius=(0, 0, 0, 0)):
    """
    پیکسمپ را دقیقا به اندازه‌ی size (عرض، ارتفاع) کراپ می‌کند و گوشه‌ها را با
    شعاع دلخواه برای هر گوشه (بالا‌راست، پایین‌راست، پایین‌چپ، بالا‌چپ) گرد می‌کند.
    """
    w, h = size
    scaled = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - w) // 2)
    y = max(0, (scaled.height() - h) // 2)
    cropped = scaled.copy(x, y, w, h)

    tr, br, bl, tl = radius
    result = QPixmap(w, h)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.moveTo(tl, 0)
    path.lineTo(w - tr, 0)
    path.quadTo(w, 0, w, tr)
    path.lineTo(w, h - br)
    path.quadTo(w, h, w - br, h)
    path.lineTo(bl, h)
    path.quadTo(0, h, 0, h - bl)
    path.lineTo(0, tl)
    path.quadTo(0, 0, tl, 0)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return result


# =====================================================================
#                           ابزارهای رابط
# =====================================================================
class ClickableCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._shadow = add_shadow(self, blur=26, dy=10, alpha=30)
        self._base_blur, self._base_dy, self._base_alpha = 26, 10, 30
        self._hover_blur, self._hover_dy, self._hover_alpha = 46, 18, 70
        self._lift_anim = None
        self._press_anim = None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._animate_scale(0.965, 90)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._animate_scale(1.0, 140)
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit()

    def enterEvent(self, event):
        super().enterEvent(event)
        # فقط تغییر جزئی سایه — بدون جابه‌جایی موقعیت (پرش ممنوع)

    def leaveEvent(self, event):
        super().leaveEvent(event)

    def _animate_lift(self, hovered):
        # غیرفعال: پرش کارت هنگام هاور حذف شد
        return

    def _animate_scale(self, factor, duration):
        """جلوه‌ی فشرده‌شدن سبک هنگام کلیک (با کوچک/بزرگ کردن نامحسوس حاشیه)"""
        if self._press_anim is not None:
            try:
                self._press_anim.stop()
            except RuntimeError:
                pass
            self._press_anim = None
        eff = self.graphicsEffect()
        if not isinstance(eff, QGraphicsDropShadowEffect):
            return
        anim = QPropertyAnimation(eff, b"blurRadius", self)
        anim.setDuration(duration)
        anim.setStartValue(eff.blurRadius())
        anim.setEndValue(eff.blurRadius() * factor if factor < 1 else self._base_blur)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._press_anim = anim


def fade_slide_in(widget, delay_ms=0, distance=22, duration=420):
    """ورود نرم و خوشگل یک ویجت: هم‌زمان محو و کمی از پایین بالا می‌آید"""
    # اگر ویجت از قبل سایه (drop shadow) دارد، پارامترهایش را نگه می‌داریم
    # چون setGraphicsEffect جدید، افکت قبلی را واقعا حذف (delete) می‌کند
    # و اگر بعدا self._shadow به همان شیء حذف‌شده اشاره کند، برنامه کرش می‌کند.
    had_shadow = hasattr(widget, '_shadow') and isinstance(
        widget.graphicsEffect(), QGraphicsDropShadowEffect
    )

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)  # این خط، افکت سایه‌ی قبلی را نابود می‌کند

    def start():
        # widget یا effect ممکن است تا این لحظه (بعد از delay_ms) توسط یک
        # refresh() جدید در لیست حذف شده باشند؛ در این صورت به‌سادگی خارج می‌شویم
        try:
            if not widget.isVisible():
                return
        except RuntimeError:
            return  # widget قبلا حذف شده

        try:
            start_pos = widget.pos()
            widget.move(start_pos.x(), start_pos.y() + distance)

            opacity_anim = QPropertyAnimation(effect, b"opacity", widget)
            opacity_anim.setDuration(duration)
            opacity_anim.setStartValue(0.0)
            opacity_anim.setEndValue(1.0)
            opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            pos_anim = QPropertyAnimation(widget, b"pos", widget)
            pos_anim.setDuration(duration)
            pos_anim.setStartValue(widget.pos())
            pos_anim.setEndValue(start_pos)
            pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)

            group = QParallelAnimationGroup(widget)
            group.addAnimation(opacity_anim)
            group.addAnimation(pos_anim)
        except RuntimeError:
            # effect یا widget بین دو بررسی بالا حذف شده - نادیده می‌گیریم
            return

        def _on_finished():
            try:
                if had_shadow:
                    # سایه را از نو می‌سازیم و self._shadow را به‌روز می‌کنیم
                    # تا هیچ ارجاعی به شیء حذف‌شده‌ی قبلی باقی نماند
                    blur = getattr(widget, '_base_blur', 26)
                    dy = getattr(widget, '_base_dy', 10)
                    alpha = getattr(widget, '_base_alpha', 30)
                    widget._shadow = add_shadow(widget, blur=blur, dy=dy, alpha=alpha)
                else:
                    widget.setGraphicsEffect(None)
            except RuntimeError:
                pass  # widget قبل از پایان انیمیشن حذف شده - مشکلی نیست

        group.finished.connect(_on_finished)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        widget._entrance_anim = group

    QTimer.singleShot(delay_ms, start)


class ReadoutCard(QFrame):
    """کارت نمایش فقط‌خواندنی (پلاک، وزن، ...) - هیچ‌وقت قابل ویرایش نیست"""

    def __init__(self, title, unit="", highlight=None):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumWidth(170)
        if highlight:
            bg, border = highlight
            self.setStyleSheet(f"QFrame#card {{ background: {bg}; border: 1px solid {border}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("cardTitle")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_lbl.setWordWrap(True)
        lay.addWidget(self.title_lbl)

        self.value_lbl = QLabel("—")
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.value_lbl)

        self.unit_lbl = QLabel(unit)
        self.unit_lbl.setObjectName("unit")
        self.unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.unit_lbl)
        if not unit:
            self.unit_lbl.hide()

        self.set_value(None)
        add_shadow(self, blur=24, dy=5, alpha=22)

    def set_title(self, text):
        self.title_lbl.setText(text)

    def set_value(self, text, state=None):
        if text is None or text == "":
            text, state = "—", 'empty'
        color = VALUE_COLORS.get(state or 'normal', VALUE_COLORS['normal'])
        self.value_lbl.setText(str(text))
        self.value_lbl.setStyleSheet(
            f"color: {color}; font-size: 32px; font-weight: 700; background: transparent;")



def op_label(sign):
    lbl = QLabel(sign)
    lbl.setObjectName("op")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def make_button(text, kind="primary"):
    btn = QPushButton(text)
    btn.setObjectName(kind)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(52)
    return btn


def make_items_table():
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["#", "محصول", "خالص بار (kg)", "وزن ثبت‌شده (kg)"])
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.setMinimumHeight(150)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return table


def fill_items_table(table, items):
    table.setRowCount(len(items))
    for row, it in enumerate(items):
        values = [str(it['seq']), it['name'], fmt(it['quantity']), fmt(it['weight_after'])]
        for col, text in enumerate(values):
            cell = QTableWidgetItem(text)
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, col, cell)


def wrap_card(widget_or_layout_builder):
    """یک QFrame کارتی می‌سازد و لایه‌ی عمودی آن را برمی‌گرداند"""
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(10)
    return card, lay


# =====================================================================
#                              دوربین
# =====================================================================
class CameraThread(QThread):
    """Thread برای دوربین - آخرین فریم را نگه می‌دارد تا هنگام ثبت تصویر استفاده شود"""
    frame_signal = pyqtSignal(object)
    error_signal = pyqtSignal(object)

    def __init__(self, camera_id=0):
        super().__init__()
        # camera_id is an integer for USB cameras; a string only for IP/RTSP cameras.
        self.camera_id = camera_id
        self.running = True
        self.last_frame = None
        self._recent = deque(maxlen=6)     # چند تصویر پشت‌سرهم برای رأی‌گیری پلاک
        self._recent_lock = threading.Lock()
        self._last_store = 0.0

    def run(self):
        # IMPORTANT: numeric USB camera IDs must go directly to OpenCV.
        # Network URL handling is used only when the source is explicitly a string.
        if isinstance(self.camera_id, int):
            candidates = [self.camera_id]
        else:
            value = str(self.camera_id).strip()
            if not value:
                self.error_signal.emit(self.camera_id)
                return
            if '://' in value:
                candidates = [value]
            else:
                candidates = [
                    value,
                    f"rtsp://{value}:554/Streaming/Channels/101",
                    f"rtsp://{value}:554/cam/realmonitor?channel=1&subtype=0",
                    f"http://{value}/video",
                    f"http://{value}/mjpeg",
                    f"http://{value}/stream",
                ]

        cap = None
        opened_source = self.camera_id
        for candidate in candidates:
            test = cv2.VideoCapture(candidate)
            if test.isOpened():
                cap = test
                opened_source = candidate
                break
            test.release()
        if cap is None:
            self.error_signal.emit(self.camera_id)
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        while self.running:
            ret, frame = cap.read()
            if ret:
                self.last_frame = frame
                now = time.time()
                if now - self._last_store >= 0.1:
                    self._last_store = now
                    with self._recent_lock:
                        self._recent.append(frame)
                self.frame_signal.emit(frame)
            else:
                self.error_signal.emit(self.camera_id)
                break

        cap.release()

    def get_recent_frames(self):
        with self._recent_lock:
            return [f.copy() for f in self._recent]

    def get_frame(self):
        return None if self.last_frame is None else self.last_frame.copy()

    def stop(self):
        self.running = False


class RoiLabel(QLabel):
    """
    پیش‌نمایش دوربین.
    editable=True (فقط در صفحه‌ی تنظیمات): با ماوس کادر دور اعداد نمایشگر بکشید
    (کلیک راست یا دابل‌کلیک = حذف کادر)
    """
    roi_changed = pyqtSignal(object)   # (x1,y1,x2,y2) بین ۰ و ۱ یا None

    def __init__(self, editable=False):
        super().__init__()
        self.editable = editable
        self.roi = None
        self._start = None
        self._now = None
        if editable:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def set_roi(self, roi):
        self.roi = tuple(roi) if roi else None
        self.update()

    def _pix_rect(self):
        pm = self.pixmap()
        if pm is None or pm.isNull():
            return None
        w, h = pm.width(), pm.height()
        return QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def _clamp(self, pos, rect):
        x = min(max(pos.x(), rect.left()), rect.right())
        y = min(max(pos.y(), rect.top()), rect.bottom())
        return x, y

    def mousePressEvent(self, event):
        if not self.editable:
            return
        rect = self._pix_rect()
        if event.button() == Qt.MouseButton.RightButton:
            self.set_roi(None)
            self.roi_changed.emit(None)
        elif event.button() == Qt.MouseButton.LeftButton and rect is not None:
            self._start = self._clamp(event.position().toPoint(), rect)
            self._now = self._start

    def mouseMoveEvent(self, event):
        if not self.editable:
            return
        rect = self._pix_rect()
        if self._start is not None and rect is not None:
            self._now = self._clamp(event.position().toPoint(), rect)
            self.update()

    def mouseReleaseEvent(self, event):
        if not self.editable:
            return
        rect = self._pix_rect()
        if self._start is not None and rect is not None:
            x1, y1 = self._start
            x2, y2 = self._clamp(event.position().toPoint(), rect)
            self._start = self._now = None
            if abs(x2 - x1) >= 15 and abs(y2 - y1) >= 15:
                nx1 = (min(x1, x2) - rect.left()) / rect.width()
                nx2 = (max(x1, x2) - rect.left()) / rect.width()
                ny1 = (min(y1, y2) - rect.top()) / rect.height()
                ny2 = (max(y1, y2) - rect.top()) / rect.height()
                self.set_roi((nx1, ny1, nx2, ny2))
                self.roi_changed.emit(self.roi)
            self.update()

    def mouseDoubleClickEvent(self, event):
        if not self.editable:
            return
        self.set_roi(None)
        self.roi_changed.emit(None)

    def paintEvent(self, event):
        super().paintEvent(event)
        rect = self._pix_rect()
        if rect is None:
            return
        painter = QPainter(self)
        if self.roi:
            x1, y1, x2, y2 = self.roi
            painter.setPen(QPen(QColor("#00E676"), 2))
            painter.drawRect(QRect(rect.left() + int(x1 * rect.width()),
                                   rect.top() + int(y1 * rect.height()),
                                   int((x2 - x1) * rect.width()),
                                   int((y2 - y1) * rect.height())))
        if self._start is not None and self._now is not None:
            painter.setPen(QPen(QColor("#FFEB3B"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(min(self._start[0], self._now[0]),
                                   min(self._start[1], self._now[1]),
                                   abs(self._now[0] - self._start[0]),
                                   abs(self._now[1] - self._start[1])))
        painter.end()


class OcrWorker(QThread):
    """خواندن وزن باسکول در پس‌زمینه تا برنامه قفل نکند — فقط EasyOCR"""
    done = pyqtSignal(object, str)  # weight, debug_text

    def __init__(self, ocr, scale_frame, scale_thread=None, roi=None, samples=3):
        super().__init__()
        self.ocr = ocr
        self.scale_frame = scale_frame
        self.scale_thread = scale_thread
        self.roi = roi
        # برای EasyOCR تعداد نمونه کم نگه داشته می‌شود تا گیر نکند
        self.samples = max(1, min(int(samples), 3))

    def run(self):
        import time
        from collections import Counter
        weight = None
        try:
            frames = []
            if self.scale_frame is not None:
                frames.append(self.scale_frame)
            if self.scale_thread is not None and self.samples > 1:
                for _ in range(self.samples - 1):
                    time.sleep(0.08)
                    frame = self.scale_thread.get_frame()
                    if frame is not None:
                        frames.append(frame)
            if not frames:
                self.ocr.last_debug['weight'] = "فریم دوربین باسکول در دسترس نیست."
                self.done.emit(None, self.ocr.last_debug.get('weight', ''))
                return

            results = []
            for frame in frames:
                cropped = crop_to_roi(frame, self.roi) if self.roi else frame
                value = self.ocr.read_weight_from_display(cropped)
                if value is not None:
                    results.append(int(value))

            if results:
                counts = Counter(results)
                candidate, votes = counts.most_common(1)[0]
                # با نمونه کم، اکثریت ساده کافی است
                if votes >= max(1, (len(results) + 1) // 2):
                    weight = candidate
                    self.ocr.last_debug['weight'] = (
                        f"وزن: {candidate} | EasyOCR تأیید {votes}/{len(frames)} فریم")
                else:
                    # پرتکرارترین را با هشدار قبول کن تا گیر نکند
                    weight = candidate
                    self.ocr.last_debug['weight'] = (
                        f"وزن: {candidate} (با اطمینان کمتر — {votes}/{len(frames)})")
            else:
                self.ocr.last_debug['weight'] = (
                    "وزن خوانده نشد؛ کادر سبز را فقط دور عدد نمایشگر تنظیم کنید.")
        except Exception as e:
            print(f"خطا در خواندن وزن: {e}")
            self.ocr.last_debug['weight'] = f"خطا در OCR: {e}"
        debug = self.ocr.last_debug.get('weight', '')
        self.done.emit(weight, debug)


# =====================================================================
#                          صفحه‌ی پایه‌ی مراحل
# =====================================================================
class BasePage(QWidget):
    """
    ساختار مشترک: نوار بالا (بازگشت + عنوان)، پیام وضعیت،
    ستون اصلی (سمت راست) و ستون دوربین‌ها (سمت چپ)
    """
    PREVIEW_SIZE = (320, 240)
    CAMERA_TITLES = {'plate': "🚗  دوربین ماشین", 'scale': "⚖️  دوربین باسکول"}

    def __init__(self, win, title, subtitle, previews=('plate', 'scale'), home_key='home'):
        super().__init__()
        self.win = win
        self.home_key = home_key

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(18)
        back = make_button("→  بازگشت", "ghost")
        back.setMinimumHeight(46)
        back.clicked.connect(lambda: win.navigate(self.home_key))
        header.addWidget(back)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("h1")
        s = QLabel(subtitle)
        s.setObjectName("sub")
        titles.addWidget(t)
        titles.addWidget(s)
        header.addLayout(titles, 1)
        root.addLayout(header)

        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.hide()
        root.addWidget(self.banner)

        body = QHBoxLayout()
        body.setSpacing(20)

        # ستون اصلی همیشه اسکرول‌پذیر است تا در نمایشگرهای کوچک هیچ کنترل،
        # دکمه یا پیش‌نمایشی نصفه و بریده نشود.
        self.main_container = QWidget()
        self.main_container.setObjectName("pageContent")
        self.main_col = QVBoxLayout(self.main_container)
        self.main_col.setContentsMargins(2, 2, 8, 8)
        self.main_col.setSpacing(16)
        main_scroll = QScrollArea()
        main_scroll.setObjectName("pageScroll")
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_scroll.setWidget(self.main_container)
        body.addWidget(main_scroll, 1)

        if previews:
            cam_col = QVBoxLayout()
            cam_col.setSpacing(16)
            for role in previews:
                cam_col.addWidget(win.make_preview_card(role, self.CAMERA_TITLES[role],
                                                        size=self.PREVIEW_SIZE))
            cam_col.addStretch()
            body.addLayout(cam_col, 0)
        root.addLayout(body, 1)

        self.debug_label = QLabel("")
        self.debug_label.setObjectName("debug")
        self.debug_label.setWordWrap(True)

    # --- پیام وضعیت ---
    def show_message(self, text, kind='info'):
        bg, fg, border = BANNER_STYLES[kind]
        self.banner.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border};"
            f"border-radius: 14px; padding: 12px 18px; font-size: 14px; font-weight: 600;")
        self.banner.setText(text)
        self.banner.show()

    def hide_message(self):
        self.banner.hide()

    def add_footer(self):
        self.main_col.addWidget(self.debug_label)
        self.main_col.addStretch()

    def on_enter(self):
        self.hide_message()
        self.debug_label.setText("")


# =====================================================================
#                        صفحه ۱: ثبت وزن ماشین
# =====================================================================
class EmptyWeightPage(BasePage):
    CAMERA_TITLES = {**BasePage.CAMERA_TITLES, 'face': "🧑  دوربین صورت راننده"}

    def __init__(self, win, source='customer', home_key='home'):
        super().__init__(win, "ثبت وزن ماشین",
                         "ماشین خالی روی باسکول باشد؛ وزن به‌صورت خودکار خوانده می‌شود",
                         previews=('plate', 'face'), home_key=home_key)
        self.source = source
        self.weight = None
        self.images = {}

        row = QHBoxLayout()
        row.setSpacing(16)
        self.weight_card = ReadoutCard("وزن خالی ماشین", "کیلوگرم")
        row.addWidget(self.weight_card, 1)
        self.main_col.addLayout(row)

        buttons = QHBoxLayout()
        buttons.setSpacing(14)
        self.capture_btn = make_button("📸  خواندن وزن و گرفتن عکس", "primary")
        self.capture_btn.clicked.connect(self.capture)
        self.confirm_btn = make_button("✓  ثبت وزن ماشین", "success")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.confirm)
        buttons.addWidget(self.capture_btn, 1)
        buttons.addWidget(self.confirm_btn, 1)
        self.main_col.addLayout(buttons)
        self.add_footer()

    def on_enter(self):
        super().on_enter()
        self.reset()

    def reset(self):
        self.weight = None
        self.images = {}
        self.weight_card.set_value(None)
        self.confirm_btn.setEnabled(False)

    def capture(self):
        self.capture_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.show_message("در حال خواندن وزن و گرفتن عکس...", 'info')
        if not self.win.run_capture('empty', True, self.on_read, need_face=True):
            self.capture_btn.setEnabled(True)

    def on_read(self, weight, images, debug):
        self.weight, self.images = weight, images
        self.debug_label.setText(debug)
        self.weight_card.set_value(fmt(weight) if weight else None)
        self.capture_btn.setEnabled(True)

        if not weight:
            self.show_message("وزن خوانده نشد — دوباره «خواندن وزن و گرفتن عکس» را بزنید.", 'error')
            return
        self.confirm_btn.setEnabled(True)
        self.show_message("وزن خوانده شد. برای ذخیره «ثبت وزن ماشین» را بزنید.", 'ok')

    def confirm(self):
        if not self.weight:
            return
        self.confirm_btn.setEnabled(False)
        try:
            success, message, receipt_number = self.win.db.add_empty_weight(
                float(self.weight), self.images.get('plate'), self.images.get('face'),
                source=self.source)
        except Exception as e:
            self.confirm_btn.setEnabled(True)
            self.show_message(f"خطای غیرمنتظره در ثبت: {e}", 'error')
            return
        if success:
            self.reset()
            if self.source != 'internal':
                self.win.sounds.play('confirm_empty_weight')
            self.show_message("✓ ماشین شما ثبت شد", 'ok')
            QTimer.singleShot(2000, lambda: self.win.navigate(self.home_key))
        else:
            self.confirm_btn.setEnabled(True)
            self.show_message(message, 'error')


# =====================================================================
#              صفحه ۲: ماشین‌های بار زده (لیست در انتظار)
# =====================================================================
class PendingCard(ClickableCard):
    """کارت ماشین در انتظار — طراحی مدرن با عکس، badge شیشه‌ای و افکت هاور"""

    CARD_SIZE = 260
    RADIUS = 22
    delete_requested = pyqtSignal(dict)

    def __init__(self, record):
        super().__init__()
        self.record = record
        self._photo_pixmaps = []   # list of (QPixmap, emoji)
        self._photo_index = 0
        self._dot_btns = []

        self.setObjectName("pendingCard")
        self.setFixedSize(self.CARD_SIZE, self.CARD_SIZE + 52)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "QFrame#pendingCard {"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "    stop:0 #1E293B, stop:1 #0F172A);"
            "  border: 1.5px solid #334155;"
            f"  border-radius: {self.RADIUS}px;"
            "}"
            "QFrame#pendingCard:hover {"
            "  border: 2px solid #F59E0B;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "    stop:0 #1E293B, stop:1 #1A2332);"
            "}")
        self._base_blur, self._hover_blur = 28, 48
        self._base_dy, self._hover_dy = 8, 16
        self._base_alpha, self._hover_alpha = 40, 80
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(0, 8)
        self._shadow.setColor(QColor(0, 0, 0, 70))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ══════════════ بخش عکس ══════════════
        photo_container = QWidget()
        photo_h = self.CARD_SIZE - 8
        photo_container.setFixedSize(self.CARD_SIZE, photo_h)
        photo_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.photo = QLabel(photo_container)
        self.photo.setFixedSize(self.CARD_SIZE, photo_h)
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 #1E293B, stop:1 #0F172A);"
            f" color:#64748B; font-size: 28px;"
            f" border-top-left-radius:{self.RADIUS}px;"
            f" border-top-right-radius:{self.RADIUS}px;")

        for key, emoji in (('face_image', '👤'), ('plate_image', '🚗')):
            pm = pixmap_from_image_value(record.get(key))
            if pm is not None:
                self._photo_pixmaps.append((pm, emoji))

        if self._photo_pixmaps:
            self._show_photo(0)
        else:
            self.photo.setText("📷\nبدون عکس")

        # ── badge شماره قبض (بالا-راست) ──
        receipt_num = record.get('receipt_number') or '—'
        badge_receipt = QLabel(f"  🧾  {receipt_num}  ", photo_container)
        badge_receipt.setStyleSheet(
            "QLabel { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 rgba(180,83,9,0.92), stop:1 rgba(245,158,11,0.92));"
            " color: #0B1120;"
            " font-size: 12px; font-weight: 800;"
            " border-radius: 11px;"
            " border: 1px solid #FBBF24;"
            " padding: 4px 10px; }")
        badge_receipt.adjustSize()
        badge_receipt.move(10, 12)
        badge_receipt.raise_()

        # ── badge تاریخ (پایین، وسط) ──
        when = record.get('empty_time') or ""
        date_str = format_jalali_datetime(when) if when else "—"
        badge_date = QLabel(f"  🕐  {date_str}  ", photo_container)
        badge_date.setStyleSheet(
            "QLabel { background: rgba(15,23,42,0.88); color: #CBD5E1;"
            " font-size: 11px; font-weight: 600;"
            " border-radius: 10px;"
            " border: 1px solid #334155;"
            " padding: 4px 10px; }")
        badge_date.adjustSize()
        bw = badge_date.width()
        badge_date.move((self.CARD_SIZE - bw) // 2, photo_h - 38)
        badge_date.raise_()

        # ── دکمه‌های انتخاب عکس (فقط اگر دو عکس داریم) ──
        if len(self._photo_pixmaps) > 1:
            dot_container = QWidget(photo_container)
            dot_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            dot_lay = QHBoxLayout(dot_container)
            dot_lay.setContentsMargins(0, 0, 0, 0)
            dot_lay.setSpacing(6)

            for i, (_, emoji) in enumerate(self._photo_pixmaps):
                dot = QPushButton(emoji, dot_container)
                dot.setFixedSize(38, 30)
                dot.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_dot(dot, i == 0)
                dot.clicked.connect(lambda _, idx=i: self._on_dot_click(idx))
                dot_lay.addWidget(dot)
                self._dot_btns.append(dot)

            dot_container.adjustSize()
            dw = dot_container.width()
            dot_container.move(self.CARD_SIZE - dw - 10, 10)
            dot_container.raise_()

        # ── دکمه حذف ──
        self.delete_btn = QPushButton("✕", photo_container)
        self.delete_btn.setFixedSize(30, 30)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setStyleSheet(
            "QPushButton { background: rgba(15,23,42,0.75); color: #F87171;"
            " border: 1.5px solid #EF4444; border-radius: 15px;"
            " font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background: rgba(239,68,68,0.25);"
            " border: 1.5px solid #FCA5A5; color: #FCA5A5; }")
        self.delete_btn.move(self.CARD_SIZE - 40, photo_h - 40)
        self.delete_btn.setToolTip("حذف این ماشین از لیست")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.record))
        self.delete_btn.raise_()

        lay.addWidget(photo_container)

        # ══════════════ نوار پایین ══════════════
        footer = QFrame()
        footer.setFixedHeight(52)
        footer.setStyleSheet(
            f"QFrame {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 #1E293B, stop:1 #0F172A);"
            f"  border-top: 1px solid #334155;"
            f"  border-bottom-left-radius: {self.RADIUS}px;"
            f"  border-bottom-right-radius: {self.RADIUS}px;"
            f"}}")
        foot_lay = QHBoxLayout(footer)
        foot_lay.setContentsMargins(16, 10, 16, 10)
        foot_lay.setSpacing(8)

        plate_text = record.get('plate') or '—'
        plate_lbl = QLabel(f"🚗  {plate_text}")
        plate_lbl.setStyleSheet(
            "color: #E2E8F0; font-size: 13px; font-weight: 700; background: transparent;")
        foot_lay.addWidget(plate_lbl)
        foot_lay.addStretch()

        cta = QLabel("انتخاب  ←")
        cta.setStyleSheet(
            "color: #F59E0B; font-size: 13px; font-weight: 800; background: transparent;")
        foot_lay.addWidget(cta)
        lay.addWidget(footer)

    def _style_dot(self, btn, active):
        if active:
            btn.setStyleSheet(
                "QPushButton { background: rgba(245,158,11,0.95); color: #0B1120;"
                " border-radius: 8px; font-size: 15px; border: none; font-weight: 700; }")
        else:
            btn.setStyleSheet(
                "QPushButton { background: rgba(15,23,42,0.85); color: #94A3B8;"
                " border-radius: 8px; font-size: 15px;"
                " border: 1px solid #334155; }")

    def _show_photo(self, index):
        self._photo_index = index
        pm, _ = self._photo_pixmaps[index]
        photo_h = self.CARD_SIZE - 8
        self.photo.setPixmap(rounded_pixmap(
            pm, (self.CARD_SIZE, photo_h),
            radius=(self.RADIUS, self.RADIUS, 0, 0)))

    def _on_dot_click(self, index):
        self._show_photo(index)
        for i, btn in enumerate(self._dot_btns):
            self._style_dot(btn, i == index)



class VirtualNumpadDialog(QDialog):
    """کیبورد مجازی عددی برای ورود شماره فیش"""
    def __init__(self, parent=None, title="شماره فیش", initial=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(420, 560)
        self._value = str(initial or "")
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0F172A, stop:0.5 #1E293B, stop:1 #0F172A);
            }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 24)
        root.setSpacing(14)

        lbl = QLabel("شماره فیش خود را وارد کنید")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #F8FAFC; background: transparent;")
        root.addWidget(lbl)

        self.display = QLabel(self._value or "—")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setMinimumHeight(64)
        self.display.setStyleSheet(
            "font-size: 36px; font-weight: 900; color: #FBBF24; background: #0B1120;"
            " border: 2px solid #F59E0B; border-radius: 16px; padding: 8px;")
        root.addWidget(self.display)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        keys = ['1','2','3','4','5','6','7','8','9','C','0','⌫']
        for i, key in enumerate(keys):
            btn = QPushButton(key)
            btn.setFixedSize(100, 70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if key.isdigit():
                btn.setStyleSheet("""
                    QPushButton {
                        background: #1E293B; color: #F8FAFC; border: 1px solid #334155;
                        border-radius: 16px; font-size: 26px; font-weight: 800;
                    }
                    QPushButton:hover { border: 1px solid #F59E0B; background: #334155; }
                    QPushButton:pressed { background: #F59E0B; color: #0B1120; }
                """)
                btn.clicked.connect(lambda _, k=key: self._press(k))
            elif key == 'C':
                btn.setStyleSheet("""
                    QPushButton { background: transparent; color: #94A3B8; border: none;
                        font-size: 18px; font-weight: 700; }
                    QPushButton:hover { color: #F87171; }
                """)
                btn.clicked.connect(self._clear)
            else:
                btn.setStyleSheet("""
                    QPushButton { background: transparent; color: #94A3B8; border: none;
                        font-size: 22px; font-weight: 700; }
                    QPushButton:hover { color: #FBBF24; }
                """)
                btn.clicked.connect(self._backspace)
            grid.addWidget(btn, i // 3, i % 3)
        root.addLayout(grid)
        root.addStretch()

        row = QHBoxLayout()
        cancel = QPushButton("انصراف")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setMinimumHeight(52)
        cancel.setStyleSheet("""
            QPushButton { background: transparent; color: #94A3B8; border: 1px solid #475569;
                border-radius: 14px; font-size: 15px; font-weight: 700; padding: 8px 18px; }
            QPushButton:hover { background: rgba(255,255,255,0.06); color: #E2E8F0; }
        """)
        cancel.clicked.connect(self.reject)
        ok = QPushButton("✓  تأیید")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setMinimumHeight(52)
        ok.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B45309, stop:1 #F59E0B);
                color: #0B1120; border: none; border-radius: 14px;
                font-size: 17px; font-weight: 900; padding: 8px 22px;
            }
            QPushButton:hover { background: #FBBF24; }
        """)
        ok.clicked.connect(self._confirm)
        row.addWidget(cancel, 1)
        row.addWidget(ok, 2)
        root.addLayout(row)

    def _refresh(self):
        self.display.setText(self._value if self._value else "—")

    def _press(self, d):
        if len(self._value) >= 12:
            return
        self._value += d
        self._refresh()

    def _backspace(self):
        self._value = self._value[:-1]
        self._refresh()

    def _clear(self):
        self._value = ""
        self._refresh()

    def _confirm(self):
        if not self._value.strip():
            return
        self.accept()

    def value(self):
        return self._value.strip()


class PendingListPage(BasePage):
    def __init__(self, win, source='customer', home_key='home', on_select=None,
                title="ثبت وزن ماشین‌های بار زده",
                subtitle="ماشینی را که وزن خالی‌اش قبلا ثبت شده انتخاب کنید"):
        super().__init__(win, title, subtitle, previews=(), home_key=home_key)
        self.source = source
        # on_select(record_id): اگر ندهید، پیش‌فرض رفتار مشتری (فیش) اجرا می‌شود
        self.on_select = on_select or (lambda record_id: win.open_finish_detail(record_id, self.source))

        # ===== جستجوی شماره فیش =====
        search_card = QFrame()
        search_card.setObjectName("receiptSearchCard")
        search_card.setStyleSheet("""
            QFrame#receiptSearchCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1E293B, stop:1 #0F172A);
                border: 2px solid #F59E0B;
                border-radius: 22px;
            }
        """)
        search_card.setMinimumHeight(110)
        sl = QHBoxLayout(search_card)
        sl.setContentsMargins(22, 16, 22, 16)
        sl.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        st = QLabel("شماره فیش خود را وارد کنید")
        st.setStyleSheet("font-size: 20px; font-weight: 900; color: #F8FAFC; background: transparent;")
        ss = QLabel("با زدن روی کادر، کیبورد مجازی باز می‌شود")
        ss.setStyleSheet("font-size: 13px; color: #94A3B8; background: transparent;")
        text_col.addWidget(st)
        text_col.addWidget(ss)
        sl.addLayout(text_col, 1)

        self.receipt_display = QPushButton("—  شماره فیش  —")
        self.receipt_display.setCursor(Qt.CursorShape.PointingHandCursor)
        self.receipt_display.setMinimumSize(220, 64)
        self.receipt_display.setStyleSheet("""
            QPushButton {
                background: #0B1120; color: #FBBF24;
                border: 2px solid #F59E0B; border-radius: 16px;
                font-size: 24px; font-weight: 900; padding: 8px 18px;
            }
            QPushButton:hover { background: #1E293B; border-color: #FBBF24; }
        """)
        self.receipt_display.clicked.connect(self.open_receipt_numpad)
        sl.addWidget(self.receipt_display)

        go_btn = QPushButton("✓  تأیید")
        go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        go_btn.setMinimumSize(140, 64)
        go_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #B45309, stop:1 #F59E0B);
                color: #0B1120; border: none; border-radius: 16px;
                font-size: 18px; font-weight: 900;
            }
            QPushButton:hover { background: #FBBF24; }
        """)
        go_btn.clicked.connect(self.submit_receipt_search)
        sl.addWidget(go_btn)
        self.main_col.addWidget(search_card)
        self._receipt_value = ""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        inner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.grid = QGridLayout(inner)
        self.grid.setSpacing(20)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(inner)
        self.main_col.addWidget(scroll, 1)

        self.empty_hint = QLabel("در حال حاضر هیچ ماشینی در انتظار وزن پر نیست.")
        self.empty_hint.setObjectName("sub")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_col.addWidget(self.empty_hint)

    def on_enter(self):
        super().on_enter()
        self.refresh()

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        records = self.win.db.get_waiting_list(source=self.source)
        self.empty_hint.setVisible(not records)

        cols = 4
        for i, record in enumerate(records):
            card = PendingCard(record)
            card.clicked.connect(lambda r=record: self.on_select(r['id']))
            card.delete_requested.connect(self.on_delete_requested)
            self.grid.addWidget(card, i // cols, i % cols)
            fade_slide_in(card, delay_ms=40 * i, distance=26, duration=380)


    def open_receipt_numpad(self):
        dlg = VirtualNumpadDialog(self, title="ورود شماره فیش", initial=self._receipt_value)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._receipt_value = dlg.value()
            self.receipt_display.setText(self._receipt_value)
            self.submit_receipt_search()

    def submit_receipt_search(self):
        num = (self._receipt_value or "").strip()
        if not num:
            # اگر هنوز عددی انتخاب نشده، کیبورد را باز کن
            self.open_receipt_numpad()
            return
        record = self.win.db.get_waiting_by_receipt(num, source=self.source)
        if not record:
            QMessageBox.warning(
                self, "پیدا نشد",
                f"فیش شماره «{num}» در لیست انتظار پیدا نشد.\n"
                "شماره را دوباره بررسی کنید.")
            return
        self.on_select(record['id'])

    def on_delete_requested(self, record):
        reply = QMessageBox.question(
            self, "حذف ماشین",
            f"آیا از حذف کامل این ماشین (قبض {record.get('receipt_number') or '—'}) مطمئن هستید؟\n"
            "عکس‌های ثبت‌شده‌ی آن هم برای همیشه پاک می‌شوند.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        success, message, images = self.win.db.delete_waiting_record(record['id'])
        if not success:
            QMessageBox.warning(self, "خطا", message)
            return

        delete_files(images.get('plate_image'), images.get('face_image'))
        # اگر پوشه‌ی بایگانی‌ای هم برای این شماره قبض ساخته شده بود پاک شود
        folder = archive_folder_for(images.get('receipt_number'), self.source)
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)

        self.refresh()


# =====================================================================
#          صفحه ۳: ثبت وزن پر و صدور فیش برای یک ماشین مشخص
# =====================================================================
class FinishDetailPage(BasePage):
    def __init__(self, win, source='customer', home_key='home'):
        super().__init__(win, "ثبت وزن پر و دریافت فیش", "", previews=(), home_key=home_key)
        self.source = source
        self.record = None
        self.final_weight = None
        self.final_images = {}
        self._photo_pixmaps = []
        self._photo_index = 0

        row = QHBoxLayout()
        row.setSpacing(20)

        photos_card = QFrame()
        photos_card.setObjectName("photoCard")
        photos_card.setFixedWidth(260)
        photos_card.setStyleSheet(
            "QFrame#photoCard { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 22px; }")
        photos_lay = QVBoxLayout(photos_card)
        photos_lay.setContentsMargins(0, 0, 0, 0)
        photos_lay.setSpacing(0)

        self.photo_label = QLabel()
        self.photo_label.setFixedSize(260, 260)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #EEF2FF, stop:1 #F3E8FF); "
            "color:#8B5CF6; font-size: 13px; border-top-left-radius:22px; border-top-right-radius:22px;")
        photos_lay.addWidget(self.photo_label)

        caption = QFrame()
        caption.setObjectName("photoCaption")
        caption.setStyleSheet(
            "QFrame#photoCaption { background: #FFFFFF; "
            "border-bottom-left-radius:22px; border-bottom-right-radius:22px; }")
        cap_lay = QVBoxLayout(caption)
        cap_lay.setContentsMargins(14, 12, 14, 14)
        cap_lay.setSpacing(3)
        self.ticket_lbl = QLabel("")
        self.ticket_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ticket_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color:#1F2937; background:transparent;")
        cap_lay.addWidget(self.ticket_lbl)
        self.date_lbl = QLabel("")
        self.date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_lbl.setWordWrap(True)
        self.date_lbl.setStyleSheet("font-size: 12px; color:#64748B; background:transparent;")
        cap_lay.addWidget(self.date_lbl)
        photos_lay.addWidget(caption)

        add_shadow(photos_card, blur=28, dy=10, alpha=28)
        row.addWidget(photos_card, 0)

        right = QVBoxLayout()
        right.setSpacing(14)
        eq = QHBoxLayout()
        eq.setSpacing(14)
        self.final_card = ReadoutCard("وزن پر ماشین", "کیلوگرم")
        self.empty_card = ReadoutCard("وزن خالی ماشین", "کیلوگرم")
        self.net_card = ReadoutCard("خالص بار", "کیلوگرم",
                                    highlight=("#F0FDF4", "#BBF7D0"))
        eq.addWidget(self.final_card, 1)
        eq.addWidget(op_label("−"))
        eq.addWidget(self.empty_card, 1)
        eq.addWidget(op_label("="))
        eq.addWidget(self.net_card, 1)
        right.addLayout(eq)

        self.capture_btn = make_button("📸  خواندن وزن پر از باسکول", "primary")
        self.capture_btn.clicked.connect(self.capture)
        right.addWidget(self.capture_btn)

        self.issue_btn = QPushButton("✓  ثبت و دریافت فیش")
        self.issue_btn.setObjectName("glowSuccess")
        self.issue_btn.setMinimumHeight(58)
        self.issue_btn.setEnabled(False)
        self.issue_btn.clicked.connect(self.issue)
        add_shadow(self.issue_btn, blur=30, dy=0, alpha=140)
        right.addWidget(self.issue_btn)

        right.addWidget(self.debug_label)
        right.addStretch()
        row.addLayout(right, 1)

        self.main_col.addLayout(row, 1)

    def open_record(self, record_id):
        self.record = self.win.db.get_waiting_by_id(record_id)
        self.final_weight = None
        self.final_images = {}
        self.hide_message()
        self.debug_label.setText("")
        self.refresh()

    def refresh(self):
        if not self.record:
            return
        self.ticket_lbl.setText(f"🧾  قبض {self.record['receipt_number'] or '—'}")
        when = self.record.get('empty_time') or ""
        self.date_lbl.setText(f"ورود: {format_jalali_datetime(when)}" if when else "—")

        self._photo_pixmaps = []
        for key in ('face_image', 'plate_image'):
            candidate = pixmap_from_image_value(self.record.get(key))
            if candidate is not None:
                self._photo_pixmaps.append(candidate)
        self._photo_index = 0

        if self._photo_pixmaps:
            self.photo_label.setPixmap(rounded_pixmap(
                self._photo_pixmaps[0], (260, 260), radius=(22, 22, 0, 0)))
        else:
            self.photo_label.setPixmap(QPixmap())
            self.photo_label.setText("📷\nبدون عکس")

        # جلوه‌ی محو-ظاهر شدن نرم هر بار که عکس عوض می‌شود
        fx = QGraphicsOpacityEffect(self.photo_label)
        fx.setOpacity(0.0)
        self.photo_label.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", self.photo_label)
        anim.setDuration(360)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self.photo_label.setGraphicsEffect(None))
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._photo_anim = anim

        self.empty_card.set_value(fmt(self.record['empty_weight']))
        self.final_card.set_value(fmt(self.final_weight) if self.final_weight else None)
        if self.final_weight:
            net = float(self.final_weight) - float(self.record['empty_weight'])
            self.net_card.set_value(fmt(net), 'ok' if net > 0 else 'error')
        else:
            self.net_card.set_value(None)
        self.issue_btn.setEnabled(self.final_weight is not None)

    def _toggle_photo(self, event):
        """با کلیک روی عکس، بین عکس صورت و عکس ماشین جابجا می‌شود"""
        if not self._photo_pixmaps:
            return
        self._photo_index = (self._photo_index + 1) % len(self._photo_pixmaps)
        self.photo_label.setPixmap(rounded_pixmap(
            self._photo_pixmaps[self._photo_index], (260, 260), radius=(22, 22, 0, 0)))

    def capture(self):
        self.capture_btn.setEnabled(False)
        self.issue_btn.setEnabled(False)
        self.show_message("در حال خواندن وزن از باسکول...", 'info')
        if not self.win.run_capture('final', True, self.on_read, save=True,
                                    need_vehicle=False, need_face=False):
            self.capture_btn.setEnabled(True)

    def on_read(self, weight, images, debug):
        self.debug_label.setText(debug)
        self.capture_btn.setEnabled(True)
        if not weight:
            self.show_message("وزن خوانده نشد — دوباره «خواندن وزن پر از باسکول» را بزنید.", 'error')
            return
        if float(weight) <= float(self.record['empty_weight']):
            self.show_message("وزن پر باید از وزن خالی بیشتر باشد؛ دوباره تلاش کنید.", 'error')
            return
        self.final_weight = weight
        self.final_images = images
        self.refresh()
        self.show_message("وزن پر خوانده شد. برای صدور فیش «ثبت و دریافت فیش» را بزنید.", 'ok')

    def issue(self):
        if not self.record or self.final_weight is None:
            return
        success, receipt_number, record = self.win.db.complete_weighing(
            self.record['id'], float(self.final_weight),
            self.final_images.get('plate'), self.final_images.get('scale'))
        if not success:
            self.show_message(receipt_number, 'error')
            return

        self.win.sounds.play('issue_receipt')

        empty_weight, final_weight, net_weight = record[2], record[4], record[7]
        empty_time, final_time = record[3], record[5]
        receipt_data = {
            'receipt_number': receipt_number,
            'empty_weight': empty_weight,
            'final_weight': final_weight,
            'net_weight': net_weight,
            'entry_time': empty_time,
            'exit_time': final_time,
        }
        pdf_file = self.win.receipt_gen.generate_pdf(receipt_data)
        if config.PRINT_DIRECTLY:
            self.win.receipt_gen.print_receipt(pdf_file)

        archive_vehicle_files(
            receipt_number,
            self.record.get('plate_image'),
            self.record.get('face_image'),
            pdf_file,
            source=self.source,
        )

        self.show_message(f"✓ فیش {receipt_number} صادر و چاپ شد.", 'ok')
        QTimer.singleShot(2000, lambda: self.win.navigate(self.home_key))


# =====================================================================
#                          صفحه‌ی تنظیمات دوربین
# =====================================================================
class CameraSettingsPage(BasePage):
    """صفحه تنظیمات دوربین با چیدمان واکنش‌گرا و قابل اسکرول.

    هر دوربین داخل کارت مستقل قرار دارد تا کنترل‌ها، آدرس IP و پیش‌نمایش
    در اندازه‌های مختلف پنجره به‌هم نریزند. هیچ منطق اتصال دوربین در این
    کلاس تغییر نکرده و فقط لایه رابط کاربری مرتب شده است.
    """
    def __init__(self, win):
        super().__init__(win, "تنظیمات دوربین",
                         "انتخاب دوربین‌ها، آدرس IP و ناحیه خواندن نمایشگر باسکول",
                         previews=(), home_key='home')
        # home_key به صورت پویا از open_settings تنظیم می‌شود

        # BasePage برای صفحات عملیاتی مناسب است؛ تنظیمات دوربین فضای بیشتری
        # لازم دارد، بنابراین محتوای اصلی را داخل اسکرول قرار می‌دهیم.
        self.main_col.setContentsMargins(0, 0, 0, 0)
        self.main_col.setSpacing(14)

        intro = QFrame()
        intro.setObjectName("settingsSection")
        il = QVBoxLayout(intro)
        il.setContentsMargins(18, 16, 18, 16)
        il.setSpacing(6)
        title = QLabel("تنظیمات اتصال دوربین‌ها")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        hint = QLabel(
            "برای دوربین USB شماره دوربین را انتخاب کنید. برای دوربین شبکه، «IP دوربین» را انتخاب کنید، "
            "آدرس IP یا RTSP/HTTP را وارد کنید و سپس اتصال را بزنید."
        )
        hint.setObjectName("sub")
        hint.setWordWrap(True)
        il.addWidget(hint)
        self.main_col.addWidget(intro)

        cameras = QFrame()
        cameras.setObjectName("settingsSection")
        cl = QVBoxLayout(cameras)
        cl.setContentsMargins(18, 16, 18, 18)
        cl.setSpacing(14)
        ct = QLabel("دوربین‌ها")
        ct.setObjectName("sectionTitle")
        cl.addWidget(ct)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        self._camera_column(grid, 0, 0, 'plate', "🚗  دوربین ماشین", editable=True)
        self._camera_column(grid, 0, 1, 'scale', "⚖️  دوربین باسکول", editable=True)
        self._camera_column(grid, 1, 0, 'face', "🧑  دوربین صورت راننده", editable=False)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        cl.addLayout(grid)
        self.main_col.addWidget(cameras)
        self.main_col.addStretch(1)

    def _camera_column(self, grid, row, col, role, title, editable=True):
        card = QFrame()
        card.setObjectName("cameraCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 15, 16, 16)
        lay.setSpacing(9)

        cap = QLabel(title)
        cap.setObjectName("cardTitle")
        cap.setStyleSheet("font-size: 15px; font-weight: 800; color: #E2E8F0;")
        lay.addWidget(cap)

        combo = QComboBox()
        combo.setMinimumHeight(42)
        for i, cid in enumerate(config.AVAILABLE_CAMERAS):
            combo.addItem(f"دوربین {i + 1}  (شماره {cid})", cid)
        combo.addItem("IP دوربین", "ip")
        current = self.win.camera_id(role)
        if self.win.camera_mode(role) == 'ip':
            self.win.set_combo_value(combo, 'ip')
        else:
            self.win.set_combo_value(combo, current)
        combo.currentIndexChanged.connect(lambda _, r=role: self.win.on_camera_selection_changed(r))
        lay.addWidget(combo)
        # نگه‌داشتن کامبوها با نام‌های قدیمی برای سازگاری با منطق انتخاب دوربین
        setattr(self, f'{role}_combo', combo)

        url = QLineEdit()
        url.setMinimumHeight(42)
        url.setPlaceholderText("IP یا آدرس RTSP / HTTP دوربین")
        url.setText(self.win.camera_url(role))
        url.setVisible(self.win.camera_mode(role) == 'ip')
        lay.addWidget(url)
        setattr(self, f'{role}_url', url)

        connect_btn = QPushButton("🔌  اتصال به دوربین")
        connect_btn.setObjectName("primary")
        connect_btn.setMinimumHeight(42)
        connect_btn.setVisible(self.win.camera_mode(role) == 'ip')
        connect_btn.clicked.connect(lambda _, r=role: self.win.apply_camera_url(r))
        lay.addWidget(connect_btn)
        setattr(self, f'{role}_connect', connect_btn)

        preview = self.win.make_preview_view(role, editable=editable, size=(420, 236))
        preview.setMinimumSize(320, 180)
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(preview, 0, Qt.AlignmentFlag.AlignCenter)

        if editable:
            note = QLabel("برای تعیین ناحیه OCR روی تصویر کادر بکشید؛ دوبار کلیک برای حذف کادر")
            note.setObjectName("sub")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note.setWordWrap(True)
            lay.addWidget(note)

        grid.addWidget(card, row, col)
        add_shadow(card, blur=22, dy=4, alpha=18)
        return combo

    def update_ip_controls(self, role):
        is_ip = self.win.camera_mode(role) == 'ip'
        getattr(self, f'{role}_url').setVisible(is_ip)
        getattr(self, f'{role}_connect').setVisible(is_ip)

    def _choose_background(self):
        self.win.choose_background()
        self.bg_label.setText(self.win.background_path or "پس‌زمینه پیش‌فرض روشن")

    def _clear_background(self):
        self.win.clear_background()
        self.bg_label.setText("پس‌زمینه پیش‌فرض روشن")


# =====================================================================
#                          مدیریت محصولات
# =====================================================================
class WeightPricingPage(QWidget):
    """مدیریت تعرفه بر اساس بازه وزن خودرو؛ تنظیمات در settings.json ذخیره می‌شود."""
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 32, 48, 28)
        root.setSpacing(14)

        header = QHBoxLayout()
        back = make_button("→  بازگشت", "ghost")
        back.clicked.connect(lambda: win.navigate('automation_home'))
        header.addWidget(back); header.addStretch()
        root.addLayout(header)

        title = QLabel("تعرفه وزن ماشین‌ها")
        title.setObjectName('h1'); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        sub = QLabel("برای هر بازه وزن، مبلغ موردنظر را تعریف کنید. واحد وزن: کیلوگرم و مبلغ: تومان")
        sub.setObjectName('sub'); sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub); root.addSpacing(8)

        card, lay = wrap_card(None)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["از وزن (kg)", "تا وزن (kg)", "هزینه (تومان)", "عملیات"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)

        buttons = QHBoxLayout()
        add = make_button("＋ افزودن بازه", "primary"); add.clicked.connect(self.add_row)
        save = make_button("💾 ذخیره", "success"); save.clicked.connect(self.save)
        buttons.addStretch(); buttons.addWidget(add); buttons.addWidget(save)
        lay.addLayout(buttons)
        root.addWidget(card, 1)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for row in self.win.weight_pricing:
            self._append_row(row)

    def _append_row(self, row):
        r = self.table.rowCount(); self.table.insertRow(r)
        vals = [f"{int(row['min_weight']):,}", f"{int(row['max_weight']):,}", f"{int(row['price']):,}"]
        for c, v in enumerate(vals):
            item = QTableWidgetItem(v); item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(r,c,item)
        box = QWidget(); bl = QHBoxLayout(box); bl.setContentsMargins(4,2,4,2); bl.setSpacing(4)
        edit = QPushButton("ویرایش"); edit.setObjectName('ghost'); edit.setMinimumHeight(34)
        delete = QPushButton("حذف"); delete.setObjectName('ghost'); delete.setMinimumHeight(34)
        edit.clicked.connect(lambda _, rr=r: self.edit_row(rr))
        delete.clicked.connect(lambda _, rr=r: self.delete_row(rr))
        bl.addWidget(edit); bl.addWidget(delete); self.table.setCellWidget(r,3,box)

    def _row_dialog(self, row=None):
        dlg = QDialog(self); dlg.setWindowTitle("تعریف تعرفه وزن")
        lay = QVBoxLayout(dlg); form = QGridLayout(); form.setSpacing(10)
        minw=QSpinBox(); minw.setRange(0, 999999999); minw.setSuffix(' کیلوگرم')
        maxw=QSpinBox(); maxw.setRange(0, 999999999); maxw.setSuffix(' کیلوگرم')
        price=QSpinBox(); price.setRange(0, 2147483); price.setSuffix(' هزار تومان')
        if row: minw.setValue(int(row['min_weight'])); maxw.setValue(int(row['max_weight'])); price.setValue(int(round(row['price']/1000)))
        form.addWidget(QLabel('از وزن:'),0,0); form.addWidget(minw,0,1)
        form.addWidget(QLabel('تا وزن:'),1,0); form.addWidget(maxw,1,1)
        form.addWidget(QLabel('هزینه:'),2,0); form.addWidget(price,2,1)
        help_lbl=QLabel('مثال: ۱۲۲ یعنی ۱۲۲٬۰۰۰ تومان'); help_lbl.setObjectName('sub'); form.addWidget(help_lbl,3,1)
        lay.addLayout(form)
        btns=QHBoxLayout(); ok=make_button('ثبت','primary'); cancel=make_button('انصراف','ghost')
        ok.clicked.connect(dlg.accept); cancel.clicked.connect(dlg.reject); btns.addStretch(); btns.addWidget(ok); btns.addWidget(cancel); lay.addLayout(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted: return None
        if maxw.value() <= minw.value():
            QMessageBox.warning(self,'بازه نامعتبر','وزن «تا» باید بزرگ‌تر از وزن «از» باشد.'); return None
        return {'min_weight':int(minw.value()),'max_weight':int(maxw.value()),'price':int(price.value()) * 1000}

    def add_row(self):
        row=self._row_dialog()
        if row:
            if any(row['min_weight'] < r['max_weight'] and row['max_weight'] > r['min_weight'] for r in self.win.weight_pricing):
                QMessageBox.warning(self, 'بازه تکراری', 'این بازه با یکی از تعرفه‌های موجود هم‌پوشانی دارد.')
                return
            self.win.weight_pricing.append(row)
            self.win.weight_pricing.sort(key=lambda r: r['min_weight'])
            self.win.save_general_settings(); self.refresh()

    def edit_row(self, index):
        if index >= len(self.win.weight_pricing): return
        row=self._row_dialog(self.win.weight_pricing[index])
        if row:
            others = self.win.weight_pricing[:index] + self.win.weight_pricing[index+1:]
            if any(row['min_weight'] < r['max_weight'] and row['max_weight'] > r['min_weight'] for r in others):
                QMessageBox.warning(self, 'بازه تکراری', 'این بازه با یکی از تعرفه‌های موجود هم‌پوشانی دارد.')
                return
            self.win.weight_pricing[index]=row
            self.win.weight_pricing.sort(key=lambda r: r['min_weight'])
            self.win.save_general_settings(); self.refresh()

    def delete_row(self, index):
        if index >= len(self.win.weight_pricing): return
        if QMessageBox.question(self,'حذف تعرفه','این بازه حذف شود؟') == QMessageBox.StandardButton.Yes:
            self.win.weight_pricing.pop(index); self.win.save_general_settings(); self.refresh()

    def save(self):
        self.win.save_general_settings()
        QMessageBox.information(self,'ذخیره شد','تعرفه‌های وزن با موفقیت ذخیره شدند.')

# =====================================================================
#           انتخاب محصول (برای هر بار در بخش «اضافه کردن بار»)
# =====================================================================
PRODUCT_COLORS = ["#8B5CF6", "#0EA5E9", "#8B5CF6", "#F59E0B", "#EF4444",
                  "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1"]


class ProductPickerDialog(QDialog):
    """گرید زیبای دکمه‌های محصول (حداکثر ۲۰ تا) برای انتخاب نوع باری که تازه توزین شده"""

    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.setWindowTitle("انتخاب محصول")
        self.setModal(True)
        self.setMinimumSize(560, 460)
        self.selected_code = None
        self.setStyleSheet("QDialog { background: #0F172A; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(14)

        title = QLabel("این بار مربوط به کدام محصول است؟")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 19px; font-weight: 700; color: #1F2937;")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(14)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        cols = 4
        for i, (code, name) in enumerate(products[:20]):
            accent = PRODUCT_COLORS[i % len(PRODUCT_COLORS)]
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumSize(112, 88)
            btn.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #1F2937; font-size: 15px; "
                f"font-weight: 700; border: 2px solid {accent}55; border-radius: 18px; padding: 8px; }}"
                f"QPushButton:hover {{ background: {accent}18; border: 2px solid {accent}; }}"
                f"QPushButton:pressed {{ background: {accent}30; }}")
            btn.clicked.connect(lambda _, c=code: self._choose(c))
            grid.addWidget(btn, i // cols, i % cols)

        if not products:
            empty = QLabel("هیچ محصولی تعریف نشده است.")
            empty.setObjectName("sub")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(empty, 0, 0)

        cancel = make_button("انصراف", "ghost")
        cancel.clicked.connect(self.reject)
        root.addWidget(cancel)

    def _choose(self, code):
        self.selected_code = code
        self.accept()


# =====================================================================
#                    مدیریت لیست محصولات (فقط در اتوماسیون)
# =====================================================================
class ProductManagePage(BasePage):
    """صفحه‌ی مدیریت کدهای محصول: اضافه، ویرایش، حذف"""

    def __init__(self, win, home_key='automation_home'):
        super().__init__(win, "مدیریت محصولات",
                         "کدهای محصول را اضافه، ویرایش یا حذف کنید",
                         previews=(), home_key=home_key)

        # ---- فرم افزودن / ویرایش ----
        form_card, form_lay = wrap_card(None)
        form_row = QHBoxLayout()
        form_row.setSpacing(10)

        self.lbl_form = QLabel("➕  افزودن محصول جدید")
        self.lbl_form.setObjectName("h2")
        form_lay.addWidget(self.lbl_form)

        self.inp_code = QLineEdit()
        self.inp_code.setPlaceholderText("کد محصول  (مثلاً: BRR001)")
        self.inp_code.setMinimumHeight(42)
        self.inp_code.setStyleSheet("font-size:15px; padding: 4px 10px;")

        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("نام محصول  (مثلاً: برنج)")
        self.inp_name.setMinimumHeight(42)
        self.inp_name.setStyleSheet("font-size:15px; padding: 4px 10px;")

        self.btn_save = make_button("✓  ذخیره", "primary")
        self.btn_save.setMinimumHeight(42)
        self.btn_save.clicked.connect(self._save)

        self.btn_clear = make_button("✕  لغو", "ghost")
        self.btn_clear.setMinimumHeight(42)
        self.btn_clear.clicked.connect(self._clear_form)

        form_row.addWidget(self.inp_code, 2)
        form_row.addWidget(self.inp_name, 3)
        form_row.addWidget(self.btn_save, 1)
        form_row.addWidget(self.btn_clear, 1)
        form_lay.addLayout(form_row)
        add_shadow(form_card, blur=16, dy=4, alpha=18)
        self.main_col.addWidget(form_card)

        # ---- جدول محصولات ----
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["کد محصول", "نام محصول", "عملیات"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(340)
        self.table.setStyleSheet(
            "QTableWidget { font-size:15px; } "
            "QHeaderView::section { font-size:14px; font-weight:700; padding:6px; }"
        )
        self.main_col.addWidget(self.table, 1)

        self._editing_code = None   # کد در حال ویرایش
        self.add_footer()

    def on_enter(self):
        self._refresh_table()

    def _refresh_table(self):
        products = self.win.db.get_products()
        self.table.setRowCount(0)
        for code, name in products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(code))
            self.table.setItem(row, 1, QTableWidgetItem(name))

            btn_row = QWidget()
            btn_lay = QHBoxLayout(btn_row)
            btn_lay.setContentsMargins(4, 2, 4, 2)
            btn_lay.setSpacing(6)

            btn_edit = QPushButton("✏️ ویرایش")
            btn_edit.setStyleSheet(
                "QPushButton{background:#EFF6FF;color:#1D4ED8;border:1px solid #93C5FD;"
                "border-radius:8px;padding:4px 10px;font-size:13px;}"
                "QPushButton:hover{background:#DBEAFE;}")
            btn_edit.clicked.connect(lambda _, c=code, n=name: self._start_edit(c, n))

            btn_del = QPushButton("🗑 حذف")
            btn_del.setStyleSheet(
                "QPushButton{background:#FEF2F2;color:#F87171;border:1px solid #FCA5A5;"
                "border-radius:8px;padding:4px 10px;font-size:13px;}"
                "QPushButton:hover{background:#FEE2E2;}")
            btn_del.clicked.connect(lambda _, c=code, n=name: self._delete(c, n))

            btn_lay.addWidget(btn_edit)
            btn_lay.addWidget(btn_del)
            self.table.setCellWidget(row, 2, btn_row)
            self.table.setRowHeight(row, 46)

    def _start_edit(self, code, name):
        self._editing_code = code
        self.inp_code.setText(code)
        self.inp_name.setText(name)
        self.lbl_form.setText(f"✏️  ویرایش محصول:  {name}")
        self.btn_save.setText("✓  بروزرسانی")

    def _clear_form(self):
        self._editing_code = None
        self.inp_code.clear()
        self.inp_name.clear()
        self.lbl_form.setText("➕  افزودن محصول جدید")
        self.btn_save.setText("✓  ذخیره")
        self.hide_message()

    def _save(self):
        code = self.inp_code.text().strip()
        name = self.inp_name.text().strip()
        if not code or not name:
            self.show_message("کد محصول و نام الزامی است.", 'error')
            return

        if self._editing_code:
            ok = self.win.db.update_product(self._editing_code, code, name)
            if ok:
                self.show_message(f"محصول «{name}» بروزرسانی شد.", 'ok')
                self._clear_form()
                self._refresh_table()
            else:
                self.show_message("ویرایش ناموفق — کد تکراری یا خطای دیگر.", 'error')
        else:
            ok = self.win.db.add_product(code, name)
            if ok:
                self.show_message(f"محصول «{name}» اضافه شد.", 'ok')
                self._clear_form()
                self._refresh_table()
            else:
                self.show_message(f"کد «{code}» قبلاً وجود دارد.", 'error')

    def _delete(self, code, name):
        reply = QMessageBox.question(
            self, "حذف محصول",
            f"آیا از حذف محصول «{name}» (کد: {code}) مطمئن هستید؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok = self.win.db.delete_product(code)
        if ok:
            self.show_message(f"محصول «{name}» حذف شد.", 'ok')
            self._refresh_table()
        else:
            self.show_message("حذف ناموفق.", 'error')


# =====================================================================
#         سیستم اتوماسیون: ثبت ماشین + اضافه کردن بار (بارهای خودمان)
# =====================================================================
class LoadModeDialog(QDialog):
    """انتخاب حالت بارگیری: یک بار یا چند بار ترکیبی"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("نوع بارگیری")
        self.setModal(True)
        self.setFixedSize(520, 300)
        self.single_mode = True
        self.setStyleSheet("QDialog { background: #0F172A; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(18)

        title = QLabel("نوع بارگیری را انتخاب کنید")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:19px; font-weight:700; color:#1F2937;")
        lay.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(18)

        btn_single = QPushButton("⚖️  یک بار\n(وزن خالص نمایش داده می‌شود)")
        btn_single.setMinimumHeight(90)
        btn_single.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#1F2937;font-size:15px;font-weight:700;"
            "border:2px solid #8B5CF655;border-radius:18px;padding:10px;}"
            "QPushButton:hover{background:#F0FDF4;border:2px solid #8B5CF6;}")
        btn_single.clicked.connect(lambda: self._choose(True))

        btn_multi = QPushButton("🔀  چند بار ترکیبی\n(بارها یکی‌یکی ثبت می‌شوند)")
        btn_multi.setMinimumHeight(90)
        btn_multi.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#1F2937;font-size:15px;font-weight:700;"
            "border:2px solid #8B5CF655;border-radius:18px;padding:10px;}"
            "QPushButton:hover{background:#EEF2FF;border:2px solid #8B5CF6;}")
        btn_multi.clicked.connect(lambda: self._choose(False))

        btn_row.addWidget(btn_single)
        btn_row.addWidget(btn_multi)
        lay.addLayout(btn_row)

        cancel = make_button("انصراف", "ghost")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)

    def _choose(self, single):
        self.single_mode = single
        self.accept()


class SingleLoadConfirmDialog(QDialog):
    """نمایش وزن خالص و انتخاب کد محصول برای حالت یک بار"""

    def __init__(self, net_weight, products, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تأیید بار و انتخاب محصول")
        self.setModal(True)
        self.setMinimumSize(560, 520)
        self.selected_code = None
        self.setStyleSheet("QDialog { background: #0F172A; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(16)

        title = QLabel("وزن خالص بار")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:17px;font-weight:700;color:#334155;")
        lay.addWidget(title)

        net_card = QFrame()
        net_card.setStyleSheet(
            "QFrame{background:#F0FDF4;border:2px solid #BBF7D0;border-radius:18px;padding:10px;}")
        net_lay = QVBoxLayout(net_card)
        lbl_net = QLabel(f"{fmt(net_weight)} کیلوگرم")
        lbl_net.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_net.setStyleSheet("font-size:36px;font-weight:900;color:#A78BFA;")
        net_lay.addWidget(lbl_net)
        lay.addWidget(net_card)

        sep = QLabel("محصول این بار را انتخاب کنید:")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("font-size:16px;font-weight:600;color:#1F2937;margin-top:4px;")
        lay.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(12)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        cols = 4
        for i, (code, name) in enumerate(products[:20]):
            accent = PRODUCT_COLORS[i % len(PRODUCT_COLORS)]
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumSize(112, 80)
            btn.setStyleSheet(
                f"QPushButton{{background:#FFFFFF;color:#1F2937;font-size:14px;"
                f"font-weight:700;border:2px solid {accent}55;border-radius:16px;padding:6px;}}"
                f"QPushButton:hover{{background:{accent}18;border:2px solid {accent};}}"
                f"QPushButton:pressed{{background:{accent}30;}}")
            btn.clicked.connect(lambda _, c=code: self._choose(c))
            grid.addWidget(btn, i // cols, i % cols)

        if not products:
            empty = QLabel("هیچ محصولی تعریف نشده است.")
            empty.setObjectName("sub")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(empty, 0, 0)

        cancel = make_button("انصراف", "ghost")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)

    def _choose(self, code):
        self.selected_code = code
        self.accept()


class AddLoadPage(BasePage):
    """
    صفحه‌ی «اضافه کردن بار» برای یک ماشین مشخص از بارهای خودمان:
    ماشین از قبل با «ثبت وزن ماشین خالی» ثبت شده؛ اینجا هر بار که روی باسکول رفت
    وزن خوانده می‌شود و محصول آن از یک لیست انتخاب می‌شود -> یک قلم بار ثبت می‌گردد.
    در پایان «پایان و ثبت نهایی» پرونده را می‌بندد. همه‌ی این رکوردها با source='internal'
    ذخیره می‌شوند و کاملاً از بارهای مشتری جدا هستند.
    """
    SOURCE = 'internal'

    def __init__(self, win, home_key='pending_auto'):
        super().__init__(win, "اضافه کردن بار",
                         "هر بار روی باسکول رفت وزن را بخوانید و محصول آن را انتخاب کنید",
                         previews=(), home_key=home_key)
        self.record = None      # {'id', 'empty_weight', 'receipt_number'}
        self.last_weight = None
        self.items = []

        # --- ردیف بالا: عکس صورت + اطلاعات ماشین ---
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # عکس صورت راننده (کلیک‌پذیر → نمایش عکس ماشین)
        self.face_thumb = QLabel()
        self.face_thumb.setFixedSize(90, 90)
        self.face_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.face_thumb.setToolTip("کلیک کنید تا عکس ماشین را ببینید")
        self.face_thumb.setStyleSheet(
            "QLabel { background: #EEF2FF; border: 2px solid #8B5CF6; border-radius: 14px; "
            "color: #8B5CF6; font-size: 11px; }"
            "QLabel:hover { border: 2px solid #6366F1; background: #F3E8FF; }")
        self.face_thumb.mousePressEvent = lambda e: self._show_plate_image()
        top_row.addWidget(self.face_thumb)

        # اطلاعات ماشین (شماره قبض + کارت‌های وزن)
        info_col = QVBoxLayout()
        info_col.setSpacing(8)
        self.ticket_lbl = QLabel("")
        self.ticket_lbl.setObjectName("h2")
        self.ticket_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_col.addWidget(self.ticket_lbl)

        status_row = QHBoxLayout()
        status_row.setSpacing(16)
        self.empty_card = ReadoutCard("وزن خالی ماشین", "کیلوگرم")
        self.last_card = ReadoutCard("آخرین وزن باسکول", "کیلوگرم")
        self.net_card = ReadoutCard("جمع بار تاکنون", "کیلوگرم", highlight=("#F0FDF4", "#BBF7D0"))
        status_row.addWidget(self.empty_card, 1)
        status_row.addWidget(self.last_card, 1)
        status_row.addWidget(self.net_card, 1)
        info_col.addLayout(status_row)
        top_row.addLayout(info_col, 1)
        self.main_col.addLayout(top_row)

        active_row = QHBoxLayout()
        active_row.setSpacing(14)
        self.add_btn = make_button("⚖️  خواندن وزن و افزودن بار", "primary")
        self.add_btn.clicked.connect(self.read_and_add)
        self.finish_btn = QPushButton("✓  پایان و ثبت نهایی")
        self.finish_btn.setObjectName("glowSuccess")
        self.finish_btn.setMinimumHeight(52)
        self.finish_btn.clicked.connect(self.finish)
        self.cancel_btn = make_button("✕  انصراف از این ماشین", "ghost")
        self.cancel_btn.clicked.connect(self.cancel_vehicle)
        active_row.addWidget(self.add_btn, 2)
        active_row.addWidget(self.finish_btn, 2)
        active_row.addWidget(self.cancel_btn, 1)
        self.main_col.addLayout(active_row)

        self.items_table = make_items_table()
        self.main_col.addWidget(self.items_table, 1)

        self.add_footer()

        # --- thumbnail ثابت عکس ماشین، گوشه پایین چپ (overlay روی صفحه) ---
        self._car_thumb_widget = QWidget(self)
        self._car_thumb_widget.setFixedSize(160, 110)
        self._car_thumb_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._car_thumb_widget.raise_()

        thumb_lay = QVBoxLayout(self._car_thumb_widget)
        thumb_lay.setContentsMargins(0, 0, 0, 0)
        thumb_lay.setSpacing(0)

        self._car_thumb_lbl = QLabel()
        self._car_thumb_lbl.setFixedSize(160, 110)
        self._car_thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._car_thumb_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._car_thumb_lbl.setToolTip("کلیک کنید تا عکس ماشین بزرگ شود")
        self._car_thumb_lbl.setStyleSheet(
            "QLabel { background: #F8FAFC; border: 2px solid #334155; border-radius: 12px; "
            "color: #B9ACC9; font-size: 11px; }"
            "QLabel:hover { border: 2px solid #6366F1; }")
        self._car_thumb_lbl.mousePressEvent = lambda e: self._show_plate_image()
        thumb_lay.addWidget(self._car_thumb_lbl)

        self._car_thumb_widget.setVisible(False)

    def open_record(self, record_id):
        """این صفحه از لیست «اضافه کردن بار» با شناسه‌ی یک ماشینِ منتظر باز می‌شود"""
        waiting = self.win.db.get_waiting_by_id(record_id)
        if not waiting:
            self.record = None
            return
        self.record = {'id': waiting['id'], 'empty_weight': float(waiting['empty_weight']),
                       'receipt_number': waiting['receipt_number'],
                       'plate_image': waiting.get('plate_image'), 'face_image': waiting.get('face_image')}
        _, self.items = self.win.db.get_waiting_items_by_id(record_id)
        self.last_weight = self.items[-1]['weight_after'] if self.items else self.record['empty_weight']
        self.hide_message()
        self.debug_label.setText("")
        self.refresh()

    def refresh(self):
        if not self.record:
            return
        self.ticket_lbl.setText(f"🧾  پرونده {self.record['receipt_number'] or '—'}")
        self.empty_card.set_value(fmt(self.record['empty_weight']))
        self.last_card.set_value(fmt(self.last_weight))
        self.net_card.set_value(fmt(self.last_weight - self.record['empty_weight']),
                                'ok' if self.items else None)
        fill_items_table(self.items_table, self.items)
        self.finish_btn.setEnabled(len(self.items) > 0)

        # نمایش عکس صورت راننده در thumbnail بالا
        face_pix = pixmap_from_image_value(self.record.get('face_image'))
        if face_pix:
            self.face_thumb.setPixmap(
                rounded_pixmap(face_pix, (90, 90), radius=(14, 14, 14, 14)))
            self.face_thumb.setText("")
        else:
            self.face_thumb.setPixmap(QPixmap())
            self.face_thumb.setText("📷\nراننده")

        # نمایش thumbnail ثابت عکس ماشین در گوشه پایین چپ
        plate_pix = pixmap_from_image_value(self.record.get('plate_image'))
        if plate_pix:
            thumb_scaled = plate_pix.scaled(
                156, 106,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self._car_thumb_lbl.setPixmap(thumb_scaled)
            self._car_thumb_lbl.setText("")
            self._car_thumb_widget.setVisible(True)
            self._position_car_thumb()
        else:
            self._car_thumb_lbl.setPixmap(QPixmap())
            self._car_thumb_lbl.setText("🚗\nعکس ماشین")
            self._car_thumb_widget.setVisible(True)
            self._position_car_thumb()

    def _position_car_thumb(self):
        """thumbnail را گوشه پایین چپ قرار می‌دهد"""
        if hasattr(self, '_car_thumb_widget'):
            margin = 16
            x = margin
            y = self.height() - self._car_thumb_widget.height() - margin
            self._car_thumb_widget.move(x, y)
            self._car_thumb_widget.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_car_thumb()

    def _show_plate_image(self):
        """کلیک روی thumbnail یا عکس مشتری → نمایش بزرگ عکس ماشین در dialog"""
        if not self.record:
            return
        plate_pix = pixmap_from_image_value(self.record.get('plate_image'))
        if not plate_pix:
            return
        dlg = QDialog(self.win)
        dlg.setWindowTitle("عکس ماشین")
        dlg.setModal(True)
        dlg.setStyleSheet("QDialog { background: #F8FAFC; }")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        screen = QApplication.primaryScreen().availableGeometry()
        max_w = int(screen.width() * 0.88)
        max_h = int(screen.height() * 0.82)
        scaled = plate_pix.scaled(max_w, max_h,
                                  Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        lbl = QLabel()
        lbl.setPixmap(scaled)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        close_btn = make_button("✕  بستن", "ghost")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dlg.exec()

    # ---------------- افزودن بار ----------------
    def read_and_add(self):
        if not self.record:
            return
        # ابتدا بپرسیم یک بار است یا چند بار ترکیبی
        mode_dlg = LoadModeDialog(self.win)
        if mode_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._single_load_mode = mode_dlg.single_mode

        self.add_btn.setEnabled(False)
        self.finish_btn.setEnabled(False)
        self.show_message("در حال خواندن وزن از باسکول...", 'info')
        if not self.win.run_capture('internal_load', True, self.on_load_read,
                                    need_vehicle=False, need_face=False):
            self.add_btn.setEnabled(True)

    def on_load_read(self, weight, images, debug):
        self.debug_label.setText(debug)
        self.add_btn.setEnabled(True)
        if not weight:
            self.show_message("وزن خوانده نشد — دوباره «خواندن وزن و افزودن بار» را بزنید.", 'error')
            self.finish_btn.setEnabled(len(self.items) > 0)
            return
        if float(weight) <= self.last_weight:
            self.show_message(f"وزن باید از وزن قبلی ({fmt(self.last_weight)}) بیشتر باشد.", 'error')
            self.finish_btn.setEnabled(len(self.items) > 0)
            return

        gross_weight = float(weight)
        net_weight = gross_weight - self.record['empty_weight']

        if getattr(self, '_single_load_mode', True):
            # ---- یک بار: وزن خالص نشان بده + انتخاب محصول، بعد همین صفحه بمونه ----
            dlg = SingleLoadConfirmDialog(net_weight, self.win.db.get_products(), self.win)
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_code:
                self.finish_btn.setEnabled(len(self.items) > 0)
                return
            success, message, quantity = self.win.db.add_load_item_by_id(
                self.record['id'], gross_weight, dlg.selected_code,
                images.get('plate'), images.get('scale'))
            if not success:
                self.show_message(message, 'error')
                self.finish_btn.setEnabled(len(self.items) > 0)
                return
            self.last_weight = gross_weight
            _, self.items = self.win.db.get_waiting_items_by_id(self.record['id'])
            self.refresh()
            self.show_message(f"✓ بار «{fmt(quantity)} کیلوگرم» ثبت شد.", 'ok')
            # طبق درخواست: بعد از ثبت هر وزن، دو ثانیه بعد به صفحه سیستم اتوماسیون برگرد.
            QTimer.singleShot(2000, lambda: self.win.navigate('automation_home'))

        else:
            # ---- چند بار ترکیبی: محصول انتخاب کنه، ثبت بشه، برگرده صفحه اتوماسیون ----
            dlg = ProductPickerDialog(self.win.db.get_products(), self.win)
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_code:
                self.finish_btn.setEnabled(len(self.items) > 0)
                return
            success, message, quantity = self.win.db.add_load_item_by_id(
                self.record['id'], gross_weight, dlg.selected_code,
                images.get('plate'), images.get('scale'))
            if not success:
                self.show_message(message, 'error')
                self.finish_btn.setEnabled(len(self.items) > 0)
                return
            self.last_weight = gross_weight
            _, self.items = self.win.db.get_waiting_items_by_id(self.record['id'])
            self.show_message(f"✓ بار «{fmt(quantity)} کیلوگرم» ثبت شد.", 'ok')
            QTimer.singleShot(2000, lambda: self.win.navigate('automation_home'))

    # ---------------- پایان کار (دستی) ----------------
    def finish(self):
        if not self.record or not self.items:
            return
        success, receipt_number, record = self.win.db.complete_weighing(
            self.record['id'], self.last_weight)
        if not success:
            self.show_message(receipt_number, 'error')
            return

        empty_weight, final_weight, net_weight = record[2], record[4], record[7]
        empty_time, final_time = record[3], record[5]
        receipt_data = {
            'receipt_number': receipt_number,
            'empty_weight': empty_weight,
            'final_weight': final_weight,
            'net_weight': net_weight,
            'entry_time': empty_time,
            'exit_time': final_time,
            'items': [{'name': it['name'], 'quantity': it['quantity']} for it in self.items],
        }
        pdf_file = self.win.receipt_gen.generate_internal_pdf(receipt_data)
        if config.PRINT_DIRECTLY:
            self.win.receipt_gen.print_receipt(pdf_file)

        # پوشه‌ی بایگانیِ جداگانه برای همین ماشین (بارهای خودمان): عکس ماشین + عکس راننده + فیش PDF
        archive_vehicle_files(receipt_number, self.record.get('plate_image'),
                              self.record.get('face_image'), pdf_file, source=self.SOURCE)

        # ── ارسال پیامک به مدیر ──
        send_receipt_sms(
            receipt_number = receipt_number,
            net_weight     = net_weight,
            items          = self.items,
            plate_number   = self.record.get('receipt_number'),   # شماره پرونده در پیامک
            on_error       = lambda e: print(f"[SMS خطا] {e}"),
        )

        # فقط بعد از ثبت نهایی موفقِ اتوماسیون، به Arduino فرمان بده.
        # این کار در یک Thread انجام می‌شود تا رابط کاربری معطل Serial نشود.
        def trigger_arduino():
            ok = self.win.arduino.press()
            if ok:
                print("[Arduino] فرمان PRESS با موفقیت اجرا شد.")
            else:
                err = self.win.arduino.last_error or ""
                if "FileNotFoundError" in err or "could not open port" in err:
                    print("[Arduino] پورت سریال پیدا نشد — Arduino وصل نیست یا COM اشتباه است.")
                else:
                    print(f"[Arduino خطا] {err}")

        threading.Thread(target=trigger_arduino, daemon=True).start()

        self.show_message(f"✓ پرونده {receipt_number} با {len(self.items)} قلم بار ثبت و فیش صادر شد.", 'ok')
        QTimer.singleShot(1600, lambda: self.win.navigate('automation_home'))

    def cancel_vehicle(self):
        if not self.record:
            return
        reply = QMessageBox.question(
            self, "انصراف", "آیا از انصراف کامل این ماشین مطمئن هستید؟ بارهای ثبت‌شده‌ی آن پاک می‌شوند.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.win.db.delete_waiting_record(self.record['id'])
        self.win.navigate(self.home_key)


# =====================================================================
#                             صفحه‌ی اول
# =====================================================================
class PinDot(QLabel):
    """یک دایره‌ی کوچک نشان‌دهنده‌ی وضعیت یک رقم رمز (خالی / پر شده)"""

    def __init__(self):
        super().__init__()
        self.setFixedSize(22, 22)
        self.set_filled(False)

    def set_filled(self, filled):
        if filled:
            self.setStyleSheet(
                "background: #FBBF24; border-radius: 11px; border: 2px solid #F59E0B;")
        else:
            self.setStyleSheet(
                "background: transparent; border-radius: 11px; "
                "border: 2px solid rgba(165,180,252,0.55);")


class PinDialog(QDialog):
    """
    دیالوگ ورود رمز برای سیستم اتوماسیون - تم لاکچری طلایی/مشکی، کیبورد عددی.
    رمز صحیح: 1111
    """
    CORRECT_PIN = "1111"
    PIN_LENGTH = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ورود به سیستم اتوماسیون")
        self.setModal(True)
        self.setFixedSize(420, 680)
        self.entered = ""

        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0F172A, stop:0.4 #1E1B4B, stop:0.7 #312E81, stop:1 #0F172A);
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 36)
        root.setSpacing(14)

        icon = QLabel("🔐")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 48px; background: transparent;")
        root.addWidget(icon)

        title = QLabel("سیستم اتوماسیون")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #F8FAFC; background: transparent;"
            " letter-spacing: 0.5px;")
        root.addWidget(title)

        sub = QLabel("رمز عبور را وارد کنید")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 14px; color: #A5B4FC; background: transparent;")
        root.addWidget(sub)

        root.addSpacing(10)

        dots_row = QHBoxLayout()
        dots_row.setSpacing(18)
        dots_row.addStretch()
        self.dots = [PinDot() for _ in range(self.PIN_LENGTH)]
        for d in self.dots:
            dots_row.addWidget(d)
        dots_row.addStretch()
        root.addLayout(dots_row)

        self.error_lbl = QLabel("")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FCA5A5; background: transparent;")
        self.error_lbl.setFixedHeight(20)
        root.addWidget(self.error_lbl)

        root.addSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(22)
        keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'C', '0', '⌫']
        for i, key in enumerate(keys):
            btn = QPushButton(key)
            btn.setFixedSize(88, 72)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if key.isdigit():
                btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                            stop:0 rgba(255,255,255,0.14), stop:1 rgba(255,255,255,0.06));
                        color: #F8FAFC;
                        border: 1px solid rgba(165,180,252,0.35);
                        border-radius: 20px;
                        font-size: 24px; font-weight: 700;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                            stop:0 rgba(251,191,36,0.35), stop:1 rgba(245,158,11,0.2));
                        border: 1px solid #FBBF24;
                        color: #FEF3C7;
                    }
                    QPushButton:pressed {
                        background: rgba(251,191,36,0.45);
                    }
                """)
                btn.clicked.connect(lambda _, k=key: self.press_digit(k))
            elif key == 'C':
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent; color: #A5B4FC;
                        border: none; font-size: 15px; font-weight: 700;
                    }
                    QPushButton:hover { color: #FBBF24; }
                """)
                btn.clicked.connect(self.clear_pin)
            else:  # ⌫
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent; color: #A5B4FC;
                        border: none; font-size: 22px; font-weight: 700;
                    }
                    QPushButton:hover { color: #FBBF24; }
                """)
                btn.clicked.connect(self.backspace)
            grid.addWidget(btn, i // 3, i % 3)
        root.addLayout(grid)

        root.addStretch()
        cancel = QPushButton("انصراف")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet("""
            QPushButton {
                background: transparent; color: #94A3B8;
                border: 1px solid rgba(148,163,184,0.4); border-radius: 14px;
                padding: 12px; font-size: 14px; font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.06);
                color: #E2E8F0;
                border: 1px solid rgba(148,163,184,0.6);
            }
        """)
        cancel.clicked.connect(self.reject)
        root.addWidget(cancel)

    def press_digit(self, digit):
        if len(self.entered) >= self.PIN_LENGTH:
            return
        self.entered += digit
        self._refresh_dots()
        if len(self.entered) == self.PIN_LENGTH:
            QTimer.singleShot(140, self._check_pin)

    def backspace(self):
        self.entered = self.entered[:-1]
        self.error_lbl.setText("")
        self._refresh_dots()

    def clear_pin(self):
        self.entered = ""
        self.error_lbl.setText("")
        self._refresh_dots()

    def _refresh_dots(self):
        for i, d in enumerate(self.dots):
            d.set_filled(i < len(self.entered))

    def _check_pin(self):
        if self.entered == self.CORRECT_PIN:
            self.accept()
        else:
            self.error_lbl.setText("رمز اشتباه است")
            self.entered = ""
            self._refresh_dots()
            self._shake()

    def _shake(self):
        anim = QPropertyAnimation(self, b"pos", self)
        pos = self.pos()
        anim.setDuration(300)
        anim.setKeyValueAt(0.0, pos)
        anim.setKeyValueAt(0.2, QPoint(pos.x() - 10, pos.y()))
        anim.setKeyValueAt(0.4, QPoint(pos.x() + 10, pos.y()))
        anim.setKeyValueAt(0.6, QPoint(pos.x() - 8, pos.y()))
        anim.setKeyValueAt(0.8, QPoint(pos.x() + 8, pos.y()))
        anim.setKeyValueAt(1.0, pos)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._shake_anim = anim


class AutomationStatsPage(QWidget):
    """آمار اتوماسیون با تم دارک بنفش؛ نمایش مجموع وزن ناخالص و خالص هر محصول."""
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("automationStatsPage")
        self.setStyleSheet("""
            QWidget#automationStatsPage { background: #0B1120; }
            QLabel { background: transparent; color: #E2E8F0; }
            QFrame#statsShell {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 28px;
            }
            QFrame#periodCard {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 24px;
            }
            QLabel#statsTitle { color: #F8FAFC; font-size: 29px; font-weight: 900; }
            QLabel#statsSub { color: #94A3B8; font-size: 12px; }
            QLabel#periodCaption { color: #FBBF24; font-size: 12px; font-weight: 800; }
            QLabel#periodTitle { color: #F8FAFC; font-size: 23px; font-weight: 900; }
            QLabel#periodInfo { color: #94A3B8; font-size: 12px; }
            QComboBox#statsPeriod {
                background: #0F172A;
                color: #F1F5F9;
                border: 1px solid #F59E0B;
                border-radius: 15px;
                padding: 12px 16px;
                font-size: 15px;
                font-weight: 800;
                min-height: 25px;
            }
            QComboBox#statsPeriod:hover { border: 1px solid #FBBF24; background: #1E293B; }
            QComboBox#statsPeriod::drop-down { border: none; width: 34px; }
            QComboBox#statsPeriod QAbstractItemView {
                background: #1E293B;
                color: #F1F5F9;
                border: 1px solid #F59E0B;
                selection-background-color: #B45309;
                selection-color: #FFFFFF;
                padding: 7px;
            }
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #0F172A; width: 8px; border-radius: 4px; margin: 4px;
            }
            QScrollBar::handle:vertical { background: #475569; border-radius: 4px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 26, 34, 26)
        root.setSpacing(16)

        header = QHBoxLayout()
        back = make_button("→  بازگشت", "ghost")
        back.setMinimumHeight(42)
        back.clicked.connect(lambda: win.navigate('automation_home'))
        header.addWidget(back)
        header.addStretch()
        title_box = QVBoxLayout()
        title = QLabel("آمار فروش اتوماسیون")
        title.setObjectName("statsTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        title_box.addWidget(title)
        sub = QLabel("گزارش وزن‌های ثبت‌شده به تفکیک محصول")
        sub.setObjectName("statsSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignRight)
        title_box.addWidget(sub)
        header.addLayout(title_box)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setDirection(QHBoxLayout.Direction.LeftToRight)
        content.setSpacing(18)

        # سمت چپ: محصولات و دو مقدار ناخالص/خالص
        products_card = QFrame()
        products_card.setObjectName("statsShell")
        pl = QVBoxLayout(products_card)
        pl.setContentsMargins(22, 20, 22, 20)
        pl.setSpacing(12)

        ph = QHBoxLayout()
        ph.setDirection(QHBoxLayout.Direction.RightToLeft)
        ptitle = QLabel("محصولات")
        ptitle.setStyleSheet("font-size:21px; font-weight:900; color:#F8FAFC;")
        ph.addWidget(ptitle)
        ph.addStretch()
        self.product_subtitle = QLabel("مرتب‌شده بر اساس وزن ناخالص")
        self.product_subtitle.setStyleSheet("font-size:12px; color:#94A3B8;")
        ph.addWidget(self.product_subtitle)
        pl.addLayout(ph)

        # هدر ستون‌ها
        cols = QHBoxLayout()
        cols.setContentsMargins(14, 0, 14, 0)
        cols.addWidget(QLabel("محصول"), 1)
        gross_h = QLabel("ناخالص (کیلوگرم)")
        gross_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gross_h.setStyleSheet("color:#FBBF24; font-size:11px; font-weight:800;")
        cols.addWidget(gross_h, 0)
        net_h = QLabel("خالص (کیلوگرم)")
        net_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        net_h.setStyleSheet("color:#94A3B8; font-size:11px; font-weight:800;")
        cols.addWidget(net_h, 0)
        # استایل محصول هدر
        cols.itemAt(0).widget().setStyleSheet("color:#94A3B8; font-size:11px; font-weight:800;")
        pl.addLayout(cols)

        self.products_scroll = QScrollArea()
        self.products_scroll.setWidgetResizable(True)
        self.products_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.products_container = QWidget()
        self.products_container.setStyleSheet("background:transparent;")
        self.products_layout = QVBoxLayout(self.products_container)
        self.products_layout.setContentsMargins(2, 2, 8, 2)
        self.products_layout.setSpacing(9)
        self.products_scroll.setWidget(self.products_container)
        pl.addWidget(self.products_scroll, 1)
        content.addWidget(products_card, 1)

        # سمت راست: انتخاب بازه
        period_card = QFrame()
        period_card.setObjectName("periodCard")
        period_card.setFixedWidth(300)
        rl = QVBoxLayout(period_card)
        rl.setContentsMargins(22, 24, 22, 24)
        rl.setSpacing(14)

        caption = QLabel("بازه آمار:")
        caption.setObjectName("periodCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        rl.addWidget(caption)

        period_title = QLabel("انتخاب بازه")
        period_title.setObjectName("periodTitle")
        period_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        rl.addWidget(period_title)

        self.period = QComboBox()
        self.period.setObjectName("statsPeriod")
        options = (
            ("امروز", "today"),
            ("این هفته", "week"),
            ("هفته قبل", "prev_week"),
            ("۲ هفته قبل", "prev_2_week"),
            ("این ماه", "month"),
            ("۳۰ روز اخیر", "30days"),
            ("همه سوابق", "all"),
        )
        for text, key in options:
            self.period.addItem(text, key)
        self.period.currentIndexChanged.connect(self.refresh)
        rl.addWidget(self.period)

        hint = QLabel("وزن ناخالص = عدد ثبت‌شده روی باسکول\nوزن خالص = مقدار واقعی بار ثبت‌شده")
        hint.setObjectName("periodInfo")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        hint.setWordWrap(True)
        rl.addWidget(hint)
        rl.addStretch()

        self.period_info = QLabel("")
        self.period_info.setObjectName("periodInfo")
        self.period_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.period_info.setWordWrap(True)
        rl.addWidget(self.period_info)
        content.addWidget(period_card, 0)

        root.addLayout(content, 1)
        self.refresh()

    def on_enter(self):
        self.refresh()

    def _fmt_weight(self, value):
        return to_persian_digits(fmt(value))

    def _week_start(self, d):
        return d - timedelta(days=(d.weekday() - 5) % 7)

    def _date(self, value):
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.strptime(str(value).split('.')[0], '%Y-%m-%d %H:%M:%S').date()
        except Exception:
            try:
                return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
            except Exception:
                return None

    def _clear_products(self):
        while self.products_layout.count():
            item = self.products_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_product_row(self, name, gross, net, rank):
        row = QFrame()
        row.setObjectName("productRow")
        row.setStyleSheet("""
            QFrame#productRow { background:#0F172A; border:1px solid #334155; border-radius:16px; }
            QFrame#productRow:hover { background:#1E293B; border:1px solid #F59E0B; }
        """)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        number = QLabel(to_persian_digits(str(rank)))
        number.setFixedSize(30, 30)
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setStyleSheet(
            "background:#B45309; color:#FEF3C7; border-radius:15px;"
            " font-size:12px; font-weight:900; border:none;")
        lay.addWidget(number)

        pname = QLabel(to_persian_digits(str(name)))
        pname.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pname.setStyleSheet("font-size:16px; font-weight:800; color:#F1F5F9; border:none;")
        lay.addWidget(pname, 1)

        gross_lbl = QLabel(f"{self._fmt_weight(gross)}")
        gross_lbl.setMinimumWidth(115)
        gross_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gross_lbl.setStyleSheet("font-size:18px; font-weight:950; color:#FBBF24; border:none;")
        lay.addWidget(gross_lbl)

        net_lbl = QLabel(f"{self._fmt_weight(net)}")
        net_lbl.setMinimumWidth(115)
        net_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        net_lbl.setStyleSheet("font-size:17px; font-weight:900; color:#94A3B8; border:none;")
        lay.addWidget(net_lbl)

        self.products_layout.addWidget(row)

    def refresh(self):
        now = datetime.now()
        today = now.date()
        week_start = self._week_start(today)
        rows_all = self.win.db.get_internal_stats()
        key = self.period.currentData()

        if key == 'today':
            start, end, label = today, today, "امروز"
        elif key == 'week':
            start, end, label = week_start, today, "این هفته"
        elif key == 'prev_week':
            end = week_start - timedelta(days=1)
            start = end - timedelta(days=6)
            label = "هفته قبل"
        elif key == 'prev_2_week':
            end = week_start - timedelta(days=8)
            start = end - timedelta(days=6)
            label = "۲ هفته قبل"
        elif key == 'month':
            start, end, label = today.replace(day=1), today, "این ماه"
        elif key == '30days':
            start, end, label = today - timedelta(days=29), today, "۳۰ روز اخیر"
        else:
            start, end, label = None, today, "همه سوابق"

        if start is None:
            filtered = rows_all
            self.period_info.setText(f"{to_persian_digits(str(len(filtered)))} ثبت بار در کل سوابق")
        else:
            filtered = [r for r in rows_all if self._date(r[0]) and start <= self._date(r[0]) <= end]
            self.period_info.setText(
                f"{label}\n"
                f"{format_jalali_date(start)} تا {format_jalali_date(end)}\n"
                f"{to_persian_digits(str(len(filtered)))} ثبت بار"
            )

        # برای هر محصول هم مجموع وزن ناخالص ثبت‌شده و هم مجموع وزن خالص بار محاسبه می‌شود.
        products = {}
        for r in filtered:
            name = r[2] or r[1] or "بدون نام"
            item = products.setdefault(name, {"gross": 0.0, "net": 0.0})
            item["gross"] += float(r[3] or 0)
            item["net"] += float(r[4] or 0)

        self._clear_products()
        if not products:
            empty = QLabel("در این بازه هنوز باری ثبت نشده است")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#64748B; font-size:15px; padding:40px;")
            self.products_layout.addWidget(empty)
        else:
            ordered = sorted(products.items(), key=lambda x: x[1]["gross"], reverse=True)
            for rank, (name, values) in enumerate(ordered, 1):
                self._add_product_row(name, values["gross"], values["net"], rank)
        self.products_layout.addStretch()


class AutomationHomePage(QWidget):
    """صفحه سیستم اتوماسیون (بارهای داخلی)."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 32, 48, 28)
        root.setSpacing(8)

        header = QHBoxLayout()
        back = make_button("→  بازگشت", "ghost")
        back.setMinimumHeight(44)
        back.clicked.connect(lambda: win.navigate('home'))
        header.addWidget(back)
        header.addStretch()
        root.addLayout(header)

        title = QLabel("سیستم اتوماسیون")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 34px; font-weight: 800; color: #FCA5A5;")
        sub = QLabel("ثبت وزن بارهای داخلی شرکت")
        sub.setObjectName("sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #94A3B8;")
        root.addWidget(title)
        root.addWidget(sub)
        root.addSpacing(18)

        cards = QHBoxLayout()
        cards.setSpacing(18)
        cards.addWidget(HomePage._card(self, "۱", "🚛", "ثبت وزن ماشین خالی",
                                       "وزن خالی ماشین به‌صورت خودکار از باسکول خوانده و ثبت می‌شود",
                                       "#F87171", lambda: win.navigate('empty_auto')))
        cards.addWidget(HomePage._card(self, "۲", "➕", "اضافه کردن بار",
                                       "ماشینی که قبلاً خالی ثبت شده را انتخاب کنید و بارهایش را اضافه کنید",
                                       "#F87171", lambda: win.navigate('pending_auto')))
        cards.addWidget(HomePage._card(self, "۳", "📦", "مدیریت محصولات",
                                       "کدهای محصول را اضافه، ویرایش یا حذف کنید",
                                       "#8B5CF6", lambda: win.navigate('product_manage')))
        root.addLayout(cards)
        root.addSpacing(14)

        tools = QHBoxLayout(); tools.setSpacing(10)
        cam = make_button("⚙️  تنظیمات دوربین", "ghost"); cam.setMinimumHeight(44)
        cam.clicked.connect(lambda: win.open_settings(return_key='automation_home'))
        stats = make_button("📊  مشاهده آمار", "ghost"); stats.setMinimumHeight(44); stats.clicked.connect(lambda: win.navigate('automation_stats'))
        pricing = make_button("💰  وزن ماشین‌ها / تعرفه", "ghost"); pricing.setMinimumHeight(44); pricing.clicked.connect(lambda: win.navigate('weight_pricing'))
        tools.addStretch(); tools.addWidget(cam); tools.addWidget(pricing); tools.addWidget(stats); tools.addStretch(); root.addLayout(tools)


class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 28, 48, 28)
        root.setSpacing(8)

        # ساعت وسط بالا — قالب ساعت، محتوا کاملاً وسط‌چین
        self.clock_frame = QFrame()
        self.clock_frame.setObjectName("homeClock")
        self.clock_frame.setFixedHeight(78)
        self.clock_frame.setMinimumWidth(280)
        self.clock_frame.setStyleSheet(
            "QFrame#homeClock {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #0F172A, stop:0.5 #1E293B, stop:1 #0F172A);"
            "  border: 2px solid #F59E0B;"
            "  border-radius: 39px;"
            "}")
        clock_lay = QVBoxLayout(self.clock_frame)
        clock_lay.setContentsMargins(24, 8, 24, 8)
        clock_lay.setSpacing(0)
        clock_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        time_row = QHBoxLayout()
        time_row.setSpacing(10)
        time_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_icon = QLabel("🕐")
        self.clock_icon.setStyleSheet("font-size: 26px; background: transparent;")
        self.clock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_time = QLabel("—")
        self.clock_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_time.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #FBBF24; background: transparent;"
            " letter-spacing: 2px;")
        time_row.addWidget(self.clock_icon)
        time_row.addWidget(self.clock_time)
        clock_lay.addLayout(time_row)

        self.clock_date = QLabel("—")
        self.clock_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_date.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #94A3B8; background: transparent;")
        clock_lay.addWidget(self.clock_date)

        clock_row = QHBoxLayout()
        clock_row.addStretch()
        clock_row.addWidget(self.clock_frame)
        clock_row.addStretch()
        root.addLayout(clock_row)
        root.addSpacing(10)

        title = QLabel("باسکول 50 تنی همت")
        title.setObjectName("h1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 36px; font-weight: 800; color: #F8FAFC; letter-spacing: -0.5px;")
        sub = QLabel("یکی از گزینه‌های زیر را انتخاب کنید")
        sub.setObjectName("sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #94A3B8; font-size: 15px;")
        root.addWidget(title)
        root.addWidget(sub)
        root.addSpacing(24)
        root.addStretch(1)

        # دو کارت بزرگ بالا
        top_cards = QHBoxLayout()
        top_cards.setSpacing(24)
        top_cards.addWidget(self._card(
            "۱", "🚛", "ثبت وزن ماشین",
            "وزن خالی ماشین، پلاک، عکس ماشین و عکس صورت راننده خودکار ثبت می‌شود",
            "#F59E0B", lambda: win.navigate('empty')))
        top_cards.addWidget(self._card(
            "۲", "🧾", "ثبت وزن ماشین‌های بار زده",
            "ماشین را از لیست انتخاب کنید، وزن پر خوانده می‌شود و فیش صادر می‌شود",
            "#38BDF8", lambda: win.navigate('pending')))
        root.addLayout(top_cards)
        root.addSpacing(16)

        # سیستم اتوماسیون کوچک زیر دو گزینه
        auto_row = QHBoxLayout()
        auto_row.addStretch()
        auto_row.addWidget(self._automation_card(win))
        auto_row.addStretch()
        root.addLayout(auto_row)
        root.addStretch(2)

        self._refresh_home_clock()
        self._home_clock_timer = QTimer(self)
        self._home_clock_timer.timeout.connect(self._refresh_home_clock)
        self._home_clock_timer.start(1000)

    def _refresh_home_clock(self):
        now = datetime.now()
        # ساعت به سبک ۱۲/۲۴ با اعداد فارسی
        h, m, s = now.hour, now.minute, now.second
        time_str = f"{h:02d}:{m:02d}:{s:02d}"
        try:
            from jalali import to_persian_digits, format_jalali_date
            time_str = to_persian_digits(time_str)
            date_str = format_jalali_date(now)
        except Exception:
            date_str = now.strftime("%Y/%m/%d")
        self.clock_time.setText(time_str)
        self.clock_date.setText(date_str)


    def _card(self, number, icon, title, text, accent, on_click, badge=None):
        card = ClickableCard()
        card.setObjectName("homeCard")
        card.setMinimumHeight(300)
        card.setStyleSheet(
            "QFrame#homeCard { background: #1E293B; border: 1px solid #334155; border-radius: 28px; }"
            f"QFrame#homeCard:hover {{ border: 2px solid {accent}; background: #1E293B; }}")
        card._base_blur, card._hover_blur = 48, 72
        card._base_dy, card._hover_dy = 14, 24
        card._base_alpha, card._hover_alpha = 50, 100
        card._shadow.setBlurRadius(48)
        card._shadow.setOffset(0, 14)
        card._shadow.setColor(QColor(0, 0, 0, 80))
        card.clicked.connect(on_click)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 26, 28, 26)
        lay.setSpacing(10)

        top = QHBoxLayout()
        num = QLabel(number)
        num.setFixedSize(40, 40)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(f"background: {accent}; color: #0B1120; border-radius: 20px;"
                          f"font-size: 17px; font-weight: 800;")
        top.addWidget(num)
        top.addStretch()
        if badge:
            tag = QLabel(badge)
            tag.setStyleSheet("background: #422006; color: #FBBF24; border-radius: 10px;"
                              "padding: 4px 12px; font-size: 12px; font-weight: 700;")
            top.addWidget(tag)
        lay.addLayout(top)

        lay.addStretch()
        ic = QLabel(icon)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size: 60px; background: transparent;")
        lay.addWidget(ic)

        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setWordWrap(True)
        t.setStyleSheet("font-size: 20px; font-weight: 800; color: #F8FAFC; background: transparent;")
        lay.addWidget(t)

        d = QLabel(text)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setWordWrap(True)
        d.setStyleSheet("font-size: 13px; color: #94A3B8; background: transparent;")
        lay.addWidget(d)
        lay.addStretch()

        go = QLabel("ادامه  ←")
        go.setAlignment(Qt.AlignmentFlag.AlignCenter)
        go.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {accent}; background: transparent;")
        lay.addWidget(go)
        return card

    def _automation_card(self, win):
        """کارت کوچک سیستم اتوماسیون — زرد، زیر دو گزینه بزرگ"""
        card = ClickableCard()
        card.setObjectName("autoCard")
        card.setMinimumHeight(88)
        card.setMaximumHeight(100)
        card.setMinimumWidth(360)
        card.setMaximumWidth(480)
        card.setStyleSheet(
            "QFrame#autoCard {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #B45309, stop:0.5 #F59E0B, stop:1 #FBBF24);"
            "  border: 2px solid #FDE68A; border-radius: 20px;"
            "}"
            "QFrame#autoCard:hover { border: 2px solid #FEF3C7; }")
        card._base_blur, card._hover_blur = 32, 48
        card._base_dy, card._hover_dy = 8, 14
        card._base_alpha, card._hover_alpha = 50, 90
        card._shadow.setBlurRadius(32)
        card._shadow.setOffset(0, 8)
        card._shadow.setColor(QColor(180, 83, 9, 80))
        card.clicked.connect(lambda: self.open_automation(win))

        lay = QHBoxLayout(card)
        lay.setContentsMargins(22, 12, 22, 12)
        lay.setSpacing(14)

        ic = QLabel("🔒")
        ic.setStyleSheet("font-size: 28px; background: transparent;")
        lay.addWidget(ic)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        t = QLabel("سیستم اتوماسیون")
        t.setStyleSheet(
            "font-size: 17px; font-weight: 800; color: #0B1120; background: transparent;")
        d = QLabel("دسترسی محدود — ورود با رمز")
        d.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #422006; background: transparent;")
        text_col.addWidget(t)
        text_col.addWidget(d)
        lay.addLayout(text_col, 1)

        go = QLabel("ورود ←")
        go.setStyleSheet(
            "font-size: 14px; font-weight: 800; color: #0B1120; background: transparent;")
        lay.addWidget(go)
        return card

    def open_automation(self, win):
        dialog = PinDialog(win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            win.navigate('automation_home')


# =====================================================================
#                          مدیریت محصولات
# =====================================================================


# =====================================================================
#                            پنجره‌ی اصلی
# =====================================================================
class WeighingSystemUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = WeighingDatabase()
        self.ocr = OCRProcessor()
        self.receipt_gen = ReceiptGenerator()
        self.sounds = SoundManager()
        # پیش‌بارگذاری EasyOCR در پس‌زمینه تا اولین «خواندن وزن» گیر نکند
        import threading
        threading.Thread(target=self.ocr.preload, daemon=True).start()
        # Arduino برای سیستم اتوماسیون؛ COM5 و 9600 طبق تست انجام‌شده
        self.arduino = ArduinoController(port="COM5", baudrate=9600)

        self.ocr_worker = None
        self.plate_thread = None
        self.scale_thread = None
        self.face_thread = None
        self.views = {'plate': [], 'scale': [], 'face': []}   # همه‌ی پیش‌نمایش‌های هر دوربین
        self._anim = None

        self.rois = {}   # {camera_source: (x1,y1,x2,y2)}
        self.camera_urls = {'plate': '', 'scale': '', 'face': ''}
        self.camera_modes = {'plate': 'usb', 'scale': 'usb', 'face': 'usb'}
        self.background_path = ''
        self.weight_pricing = []
        self.load_general_settings()
        self.plate_camera_id, self.scale_camera_id, self.face_camera_id = self.load_camera_settings()

        self.init_ui()
        self.apply_background()
        self.restart_cameras()

    # ---------------------- ساخت رابط ----------------------
    def init_ui(self):
        self.setWindowTitle("باسکول 50 تنی همت")
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(STYLE)

        self.stack = QStackedWidget()
        self.stack.setObjectName('appStack')
        self.setCentralWidget(self.stack)

        self.empty_page = EmptyWeightPage(self)
        self.pending_page = PendingListPage(self)
        self.finish_detail_page = FinishDetailPage(self)
        self.settings_page = CameraSettingsPage(self)
        self.automation_stats_page = AutomationStatsPage(self)

        # صفحات «سیستم اتوماسیون» (بارهای خودمان - source='internal')؛ کاملاً جدا از بارهای مشتری
        self.empty_page_auto = EmptyWeightPage(self, source='internal', home_key='automation_home')
        self.add_load_page = AddLoadPage(self, home_key='pending_auto')
        self.pending_page_auto = PendingListPage(
            self, source='internal', home_key='automation_home',
            on_select=self.open_add_load_detail,
            title="اضافه کردن بار",
            subtitle="ماشینی را که قبلاً خالی ثبت شده انتخاب کنید")
        self.product_manage_page = ProductManagePage(self, home_key='automation_home')
        self.weight_pricing_page = WeightPricingPage(self)

        self.pages = {
            'home': HomePage(self),
            'empty': self.empty_page,
            'pending': self.pending_page,
            'detail': self.finish_detail_page,
            'settings': self.settings_page,
            'automation_stats': self.automation_stats_page,
            'automation_home': AutomationHomePage(self),
            'empty_auto': self.empty_page_auto,
            'pending_auto': self.pending_page_auto,
            'add_load_detail': self.add_load_page,
            'product_manage': self.product_manage_page,
            'weight_pricing': self.weight_pricing_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.pages['home'])

        # کلید میانبر F5 → ورود مستقیم به سیستم اتوماسیون بدون رمز
        from PyQt6.QtGui import QShortcut, QKeySequence
        self._f5_shortcut = QShortcut(QKeySequence("F5"), self)
        self._f5_shortcut.activated.connect(lambda: self.navigate('automation_home'))

        # F11 → تمام‌صفحه / خروج از تمام‌صفحه
        self._fullscreen = False
        self._f11_shortcut = QShortcut(QKeySequence("F11"), self)
        self._f11_shortcut.activated.connect(self.toggle_fullscreen)
        # شروع در حالت تمام‌صفحه
        QTimer.singleShot(0, self.enter_fullscreen)

        # ویجت ساعت فشرده برای صفحات داخلی (در صفحه اصلی ساعت بزرگ وسط است)
        self._clock_label = QLabel(self)
        self._clock_label.setStyleSheet(
            "QLabel {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #0F172A, stop:1 #1E293B);"
            "  color: #FBBF24;"
            "  border: 2px solid #F59E0B;"
            "  border-radius: 20px;"
            "  padding: 8px 18px;"
            "  font-size: 14px;"
            "  font-weight: 700;"
            "}")
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_clock()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

    def _update_clock(self):
        now = datetime.now()
        h, m, s = now.hour, now.minute, now.second
        time_str = f"{h:02d}:{m:02d}:{s:02d}"
        try:
            from jalali import to_persian_digits, format_jalali_date
            time_str = to_persian_digits(time_str)
            date_str = format_jalali_date(now)
        except Exception:
            date_str = now.strftime("%Y/%m/%d")
        self._clock_label.setText(f"🕐  {time_str}   ·   {date_str}")
        self._clock_label.adjustSize()
        # در صفحه اصلی پنهان (ساعت بزرگ وسط هست)، در بقیه صفحات گوشه
        on_home = self.stack.currentWidget() is self.pages.get('home')
        self._clock_label.setVisible(not on_home)
        if not on_home:
            self._clock_label.move(16, 12)
            self._clock_label.raise_()


    def enter_fullscreen(self):
        self._fullscreen = True
        self.showFullScreen()

    def exit_fullscreen(self):
        self._fullscreen = False
        self.showNormal()
        self.showMaximized()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def open_settings(self, return_key='home'):
        """باز کردن تنظیمات دوربین و تعیین صفحه بازگشت"""
        self.settings_page.home_key = return_key
        self.navigate('settings')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_clock_label') and self._clock_label.isVisible():
            self._clock_label.move(16, 12)
            self._clock_label.raise_()

    # صداهایی که با ورود به هر صفحه (بر اساس کلید ناوبری) پخش می‌شوند
    # توجه: بخش «سیستم اتوماسیون» (بارهای خودمان) کاملاً بی‌صداست؛ راهنمای صوتی فقط
    # برای صفحات مشتری (empty/pending) پخش می‌شود.
    NAV_SOUNDS = {
        'empty': 'open_empty_weight_page',
        'pending': 'open_waiting_list',
    }

    def open_finish_detail(self, record_id, source='customer'):
        self.sounds.play('open_vehicle_profile')
        self.finish_detail_page.open_record(record_id)
        self.navigate('detail')

    def open_add_load_detail(self, record_id):
        self.add_load_page.open_record(record_id)
        self.navigate('add_load_detail')

    def _read_settings(self):
        path = Path(config.SETTINGS_FILE)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"خواندن تنظیمات ناموفق: {e}")
            return {}

    def _write_settings(self, data):
        try:
            Path(config.SETTINGS_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"ذخیره تنظیمات ناموفق: {e}")

    def load_general_settings(self):
        data = self._read_settings()
        self.background_path = ''
        raw = data.get('weight_pricing') or []
        cleaned = []
        for row in raw:
            try:
                mn = float(row.get('min_weight', 0)); mx = float(row.get('max_weight', 0)); price = int(row.get('price', 0))
                if mx > mn and price >= 0:
                    cleaned.append({'min_weight': mn, 'max_weight': mx, 'price': price})
            except Exception:
                continue
        self.weight_pricing = cleaned

    def save_general_settings(self):
        data = self._read_settings()
        data['weight_pricing'] = self.weight_pricing
        self._write_settings(data)

    def choose_background(self):
        # قابلیت پس‌زمینه سفارشی عمداً غیرفعال شده.
        self.background_path = ''
        self.save_general_settings()
        self.apply_background()

    def clear_background(self):
        self.background_path = ''
        self.save_general_settings()
        self.apply_background()

    def apply_background(self):
        if hasattr(self, 'stack'):
            self.stack.setStyleSheet("QStackedWidget#appStack { background: transparent; }")

    def get_price_for_weight(self, weight_kg):
        """برگرداندن تعرفه ثبت‌شده برای وزن به کیلوگرم؛ مبلغ به تومان است."""
        try:
            weight = float(weight_kg)
        except Exception:
            return None
        for row in sorted(self.weight_pricing, key=lambda r: r['min_weight']):
            if row['min_weight'] <= weight <= row['max_weight']:
                return int(row['price'])
        return None

    def navigate(self, key):
        """رفتن به صفحه با انیمیشن نرم (محو شدن)"""
        sound_key = self.NAV_SOUNDS.get(key)
        if sound_key:
            self.sounds.play(sound_key)
        page = self.pages[key]
        if hasattr(page, 'on_enter'):
            page.on_enter()
        self.stack.setCurrentWidget(page)

        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda p=page: p.setGraphicsEffect(None))
        anim.start()
        self._anim = anim

        # ساعت گوشه فقط در صفحات داخلی؛ در صفحه اصلی ساعت بزرگ وسط هست
        if hasattr(self, '_clock_label'):
            self._clock_label.setVisible(key != 'home')
            if key != 'home':
                self._clock_label.raise_()

    def make_preview_view(self, role, editable=False, size=(320, 240)):
        view = RoiLabel(editable)
        view.setObjectName("preview")
        view.setFixedSize(*size)
        view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        view.setText("در حال اتصال...")
        view.set_roi(self.rois.get(self.camera_source(role)))
        if editable:
            view.roi_changed.connect(lambda roi, r=role: self.on_roi_changed(r, roi))
        self.views[role].append(view)
        return view

    def make_preview_card(self, role, title, size=(320, 240)):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)
        cap = QLabel(title)
        cap.setObjectName("cardTitle")
        lay.addWidget(cap)
        lay.addWidget(self.make_preview_view(role, False, size))
        add_shadow(card, blur=24, dy=5, alpha=22)
        return card

    def camera_id(self, role):
        if role == 'plate':
            return self.plate_camera_id
        if role == 'face':
            return self.face_camera_id
        return self.scale_camera_id

    # ---------------------- تنظیم دوربین‌ها ----------------------
    def camera_mode(self, role):
        return self.camera_modes.get(role, 'usb')

    def camera_url(self, role):
        return self.camera_urls.get(role, '').strip()

    def camera_source(self, role):
        if self.camera_mode(role) == 'ip' and self.camera_url(role):
            return self.camera_url(role)
        return self.camera_id(role)

    def load_camera_settings(self):
        plate_id = config.PLATE_CAMERA_ID
        scale_id = config.SCALE_CAMERA_ID
        face_id = config.FACE_CAMERA_ID
        try:
            path = Path(config.SETTINGS_FILE)
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                p = data.get('plate_camera')
                s = data.get('scale_camera')
                f = data.get('face_camera')
                for role in ('plate', 'scale', 'face'):
                    self.camera_urls[role] = str(data.get(f'{role}_camera_url') or '').strip()
                    self.camera_modes[role] = 'ip' if data.get(f'{role}_camera_mode') == 'ip' and self.camera_urls[role] else 'usb'

                # هر دوربین را جدا اعتبارسنجی می‌کنیم؛ نبودن/نامعتبربودن یکی
                # (مثلا دوربین صورت که وصل نیست) نباید تنظیمات معتبر بقیه را
                # نادیده بگیرد و به مقدار پیش‌فرض برگرداند.
                if p in config.AVAILABLE_CAMERAS:
                    plate_id = p
                if s in config.AVAILABLE_CAMERAS:
                    scale_id = s
                if f in config.AVAILABLE_CAMERAS:
                    face_id = f

                # فقط اگر دو دوربینِ اصلی (ماشین/باسکول) با هم تداخل داشته باشند
                # به پیش‌فرض برمی‌گردیم؛ چون این دو همیشه باید فعال باشند.
                if plate_id == scale_id:
                    plate_id = config.PLATE_CAMERA_ID
                    scale_id = config.SCALE_CAMERA_ID

                for cid, roi in (data.get('rois') or {}).items():
                    if roi and len(roi) == 4:
                        self.rois[int(cid)] = tuple(roi)
        except Exception as e:
            print(f"خواندن تنظیمات ناموفق: {e}")
        return plate_id, scale_id, face_id

    def save_camera_settings(self):
        data = self._read_settings()
        data.update({'plate_camera': self.plate_camera_id,
                     'scale_camera': self.scale_camera_id,
                     'face_camera': self.face_camera_id,
                     'plate_camera_url': self.camera_urls.get('plate', ''),
                     'scale_camera_url': self.camera_urls.get('scale', ''),
                     'face_camera_url': self.camera_urls.get('face', ''),
                     'plate_camera_mode': self.camera_modes.get('plate', 'usb'),
                     'scale_camera_mode': self.camera_modes.get('scale', 'usb'),
                     'face_camera_mode': self.camera_modes.get('face', 'usb'),
                     'rois': {str(k): list(v) for k, v in self.rois.items()}})
        self._write_settings(data)

    @staticmethod
    def set_combo_value(combo, value):
        combo.blockSignals(True)
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def on_camera_selection_changed(self, role):
        """USB behaves exactly like the original app; IP selection only reveals the IP controls."""
        combos = {'plate': self.settings_page.plate_combo,
                  'scale': self.settings_page.scale_combo,
                  'face': self.settings_page.face_combo}
        selected = combos[role].currentData()

        if selected == 'ip':
            self.camera_modes[role] = 'ip'
            self.save_camera_settings()
            self.settings_page.update_ip_controls(role)
            return

        current = {'plate': self.plate_camera_id, 'scale': self.scale_camera_id,
                   'face': self.face_camera_id}
        old_value = current[role]
        new_value = selected
        for other_role, other_combo in combos.items():
            if other_role != role and self.camera_mode(other_role) != 'ip' and current[other_role] == new_value:
                current[other_role] = old_value
                self.set_combo_value(other_combo, old_value)
        current[role] = new_value
        self.plate_camera_id = current['plate']
        self.scale_camera_id = current['scale']
        self.face_camera_id = current['face']
        self.camera_modes[role] = 'usb'
        self.save_camera_settings()
        self.settings_page.update_ip_controls(role)
        self.restart_cameras()

    def apply_camera_url(self, role):
        fields = {'plate': self.settings_page.plate_url,
                  'scale': self.settings_page.scale_url,
                  'face': self.settings_page.face_url}
        value = fields[role].text().strip()
        if not value:
            QMessageBox.warning(self, "آدرس دوربین", "IP یا آدرس استریم دوربین را وارد کنید.")
            return
        self.camera_urls[role] = value
        self.camera_modes[role] = 'ip'
        self.save_camera_settings()
        self.restart_cameras()

    def on_roi_changed(self, role, roi):
        cam_id = self.camera_source(role)
        if roi:
            self.rois[cam_id] = tuple(roi)
        else:
            self.rois.pop(cam_id, None)
        for view in self.views[role]:
            view.set_roi(roi)
        self.save_camera_settings()

    def stop_cameras(self):
        for thread in (self.plate_thread, self.scale_thread, self.face_thread):
            if thread is not None:
                thread.stop()
                thread.wait(3000)
        self.plate_thread = None
        self.scale_thread = None
        self.face_thread = None

    def restart_cameras(self):
        self.stop_cameras()
        for role in ('plate', 'scale', 'face'):
            for view in self.views[role]:
                view.setText("در حال اتصال...")
                view.set_roi(self.rois.get(self.camera_source(role)))

        self.plate_thread = CameraThread(self.camera_source('plate'))
        self.plate_thread.frame_signal.connect(lambda f: self.on_frame('plate', f))
        self.plate_thread.error_signal.connect(lambda cid: self.on_camera_error('plate', cid))
        self.plate_thread.start()

        self.scale_thread = CameraThread(self.camera_source('scale'))
        self.scale_thread.frame_signal.connect(lambda f: self.on_frame('scale', f))
        self.scale_thread.error_signal.connect(lambda cid: self.on_camera_error('scale', cid))
        self.scale_thread.start()

        self.face_thread = CameraThread(self.camera_source('face'))
        self.face_thread.frame_signal.connect(lambda f: self.on_frame('face', f))
        self.face_thread.error_signal.connect(lambda cid: self.on_camera_error('face', cid))
        self.face_thread.start()

    def on_camera_error(self, role, cid):
        for view in self.views[role]:
            view.setText(f"دوربین {cid} باز نشد")

    def on_frame(self, role, frame):
        visible = [v for v in self.views[role] if v.isVisible()]
        if not visible:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        for view in visible:
            view.setPixmap(pixmap.scaled(view.width(), view.height(),
                                         Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))

    # ---------------------- ثبت تصویر + خواندن خودکار ----------------------
    def save_images(self, stage, vehicle_frame, scale_frame, face_frame=None):
        """
        فریم‌ها را به‌صورت JPEG در حافظه (bytes) درمی‌آورد - هیچ فایلی روی دیسک
        ساخته نمی‌شود. این عکس‌ها فقط داخل دیتابیس نگه داشته می‌شوند و تنها زمانی
        که کار یک ماشین تمام و آرشیو می‌شود، به فایل واقعی تبدیل می‌شوند (در
        archive_vehicle_files) تا پوشه‌ی images الکی پر نشود.
        """
        result = {'plate': None, 'scale': None, 'face': None}
        for key, frame in (('plate', vehicle_frame), ('scale', scale_frame), ('face', face_frame)):
            if frame is None:
                continue
            ok, buf = cv2.imencode('.jpg', frame)
            if ok:
                result[key] = buf.tobytes()
        return result

    def save_debug_crops(self, stage, scale_crop):
        """فقط برای دیباگ - پیش‌فرض خاموش است تا چیزی روی دیسک ذخیره نشود (config.SAVE_DEBUG_CROPS)"""
        if scale_crop is None or not getattr(config, 'SAVE_DEBUG_CROPS', False):
            return
        Path(config.IMAGES_DIRECTORY).mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        cv2.imwrite(str(Path(config.IMAGES_DIRECTORY) / f"{stamp}_{stage}_scale_roi.jpg"), scale_crop)

    def run_capture(self, stage, need_weight, on_done, save=True, need_vehicle=True, need_face=False):
        """
        خواندن خودکار وزن (دوربین باسکول) و در صورت نیاز گرفتن عکس از دوربین ماشین
        و/یا دوربین صورت راننده (بدون OCR - فقط ذخیره می‌شوند).
        نتیجه فقط از طریق on_done(weight, images, debug) به صفحه می‌رسد.
        اگر شروع نشد False برمی‌گرداند.
        """
        if self.ocr_worker is not None and self.ocr_worker.isRunning():
            return False

        vehicle_frame, scale_frame, face_frame = None, None, None
        if need_vehicle:
            vehicle_frame = self.plate_thread.get_frame() if self.plate_thread else None
            if vehicle_frame is None:
                QMessageBox.warning(self, "خطا", "تصویری از دوربین ماشین دریافت نشد!")
                return False
        if need_weight:
            scale_frame = self.scale_thread.get_frame() if self.scale_thread else None
            if scale_frame is None:
                QMessageBox.warning(self, "خطا", "تصویری از دوربین باسکول دریافت نشد!")
                return False
        if need_face:
            face_frame = self.face_thread.get_frame() if self.face_thread else None

        images = self.save_images(stage, vehicle_frame, scale_frame, face_frame) if save else {}

        # اگر کادر سبز کشیده شده باشد فقط همان ناحیه خوانده می‌شود
        scale_roi = self.rois.get(self.camera_source('scale'))
        scale_input = crop_to_roi(scale_frame, scale_roi) if need_weight else None
        if save:
            self.save_debug_crops(stage, scale_input if (need_weight and scale_roi) else None)

        self.ocr_worker = OcrWorker(
            self.ocr, scale_frame if need_weight else None,
            scale_thread=self.scale_thread if need_weight else None,
            roi=scale_roi if need_weight else None,
            samples=2,  # EasyOCR کند است؛ ۲ نمونه کافی و سریع‌تر است
        )

        def finished(weight, debug):
            on_done(weight, images, debug)

        self.ocr_worker.done.connect(finished)
        self.ocr_worker.start()
        return True

    # ---------------------- بستن برنامه ----------------------
    def closeEvent(self, event):
        self.arduino.close()
        self.stop_cameras()
        if self.ocr_worker is not None and self.ocr_worker.isRunning():
            self.ocr_worker.wait(10000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    window = WeighingSystemUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
