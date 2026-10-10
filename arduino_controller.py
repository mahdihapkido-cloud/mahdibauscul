"""ارتباط ساده برنامه با Arduino از طریق Serial.

پروتکل فعلی:
  برنامه -> Arduino: PRESS\n
Arduino پس از اجرای حرکت سروو پاسخ DONE می‌دهد.
"""
import threading
import time

try:
    import serial
except ImportError:
    serial = None


class ArduinoController:
    def __init__(self, port="COM5", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._lock = threading.Lock()
        self._available = False
        self.last_error = ""

    def connect(self):
        if serial is None:
            self.last_error = "کتابخانه pyserial نصب نیست"
            return False
        with self._lock:
            try:
                if self._serial and self._serial.is_open:
                    self._available = True
                    return True
                self._serial = serial.Serial(
                    self.port,
                    self.baudrate,
                    timeout=2,
                    write_timeout=2,
                )
                # باز شدن پورت سریال معمولاً Arduino را ریست می‌کند.
                time.sleep(2.0)
                self._serial.reset_input_buffer()
                self._available = True
                self.last_error = ""
                return True
            except Exception as exc:
                self._available = False
                self.last_error = str(exc)
                try:
                    if self._serial:
                        self._serial.close()
                except Exception:
                    pass
                self._serial = None
                return False

    def press(self):
        """فرمان فشار دادن دکمه را برای Arduino می‌فرستد."""
        if not self.connect():
            return False
        with self._lock:
            try:
                self._serial.write(b"PRESS\n")
                self._serial.flush()
                reply = self._serial.readline().decode("utf-8", errors="ignore").strip()
                if reply == "DONE":
                    self.last_error = ""
                    return True
                # حتی اگر پاسخ DONE به علت timeout نرسید، فرمان ارسال شده است.
                # برای جلوگیری از اجرای دوباره، اینجا موفقیت را فقط با پاسخ تأیید می‌کنیم.
                self.last_error = f"پاسخ Arduino: {reply or 'بدون پاسخ'}"
                return False
            except Exception as exc:
                self._available = False
                self.last_error = str(exc)
                return False

    def close(self):
        with self._lock:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
            self._available = False
