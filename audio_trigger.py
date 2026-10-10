"""مانیتور سطح صدای میکروفون و تریگر Arduino به‌محض عبور صدا از گیت."""
import threading
import time
import math

try:
    import sounddevice as sd
except Exception:
    sd = None


class AudioGateTrigger:
    def __init__(self, on_trigger=None, threshold=55.0, hold_seconds=2.0, device=None):
        self.on_trigger = on_trigger
        self.threshold = float(threshold)
        self.hold_seconds = 0.0
        self.device = device
        self.level = 0.0
        self.running = False
        self._stream = None
        self._above_since = None
        self._latched = False
        self._lock = threading.Lock()
        self.last_error = ""
        self.last_trigger = None

    def set_device(self, device):
        """انتخاب ورودی میکروفون؛ تغییر ورودی در اجرای بعدی/شروع مجدد اعمال می‌شود."""
        with self._lock:
            self.device = device

    @staticmethod
    def input_devices():
        if sd is None:
            return []
        try:
            devices = sd.query_devices()
            return [(i, d.get("name", f"Input {i}")) for i, d in enumerate(devices) if int(d.get("max_input_channels", 0)) > 0]
        except Exception:
            return []

    def set_threshold(self, value):
        with self._lock:
            self.threshold = max(1.0, min(100.0, float(value)))
            if self.level < self.threshold:
                self._above_since = None
                self._latched = False

    def _callback(self, indata, frames, time_info, status):
        try:
            if status:
                pass
            # RMS -> dBFS -> 0..100, where -60 dBFS=0 and 0 dBFS=100.
            data = indata[:, 0]
            if len(data):
                rms = math.sqrt(sum(float(x) * float(x) for x in data) / len(data))
                db = 20.0 * math.log10(max(rms, 1e-7))
                level = max(0.0, min(100.0, (db + 60.0) / 60.0 * 100.0))
            else:
                level = 0.0

            now = time.monotonic()
            fire = False
            with self._lock:
                self.level = level
                threshold = self.threshold
                if level >= threshold:
                    # بدون تأخیر زمانی: اولین بلاک صوتی که از گیت عبور کند تریگر می‌شود.
                    if not self._latched:
                        self._latched = True
                        self._above_since = now
                        self.last_trigger = time.time()
                        fire = True
                else:
                    self._above_since = None
                    self._latched = False

            if fire and self.on_trigger:
                threading.Thread(target=self.on_trigger, daemon=True).start()
        except Exception as exc:
            self.last_error = str(exc)

    def start(self):
        if self.running:
            return True
        if sd is None:
            self.last_error = "کتابخانه sounddevice نصب نیست"
            return False
        try:
            self._stream = sd.InputStream(
                channels=1,
                samplerate=16000,
                blocksize=800,
                dtype="float32",
                callback=self._callback,
                device=self.device,
            )
            self._stream.start()
            self.running = True
            self.last_error = ""
            return True
        except Exception as exc:
            self.running = False
            self.last_error = str(exc)
            try:
                if self._stream:
                    self._stream.close()
            except Exception:
                pass
            self._stream = None
            return False

    def stop(self):
        self.running = False
        with self._lock:
            self._above_since = None
            self._latched = False
            self.level = 0.0
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None
