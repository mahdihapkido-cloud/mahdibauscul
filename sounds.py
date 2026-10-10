"""پخش صداهای رابط کاربری (mp3) روی اتفاق‌های مشخص"""
from pathlib import Path

from PyQt6.QtCore import QUrl

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
except Exception:
    QMediaPlayer = None
    QAudioOutput = None

import config


class SoundManager:
    """
    پخش صداهای کوتاه با کلید (key) از روی config.SOUNDS.
    اگر QtMultimedia در دسترس نباشد یا فایل صدا پیدا نشود، بی‌صدا نادیده می‌گیرد
    (نباید هیچ‌وقت باعث کرش برنامه شود).
    """

    def __init__(self):
        self._player = None
        self._audio_output = None
        if QMediaPlayer is not None:
            try:
                self._player = QMediaPlayer()
                self._audio_output = QAudioOutput()
                self._audio_output.setVolume(1.0)
                self._player.setAudioOutput(self._audio_output)
            except Exception as e:
                print(f"راه‌اندازی پخش صدا ناموفق بود: {e}")
                self._player = None

    def play(self, key):
        if self._player is None:
            return
        path = config.SOUNDS.get(key)
        if not path:
            return
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = Path(__file__).resolve().parent / full_path
        if not full_path.exists():
            return
        try:
            self._player.stop()
            self._player.setSource(QUrl.fromLocalFile(str(full_path.resolve())))
            self._player.play()
        except Exception as e:
            print(f"پخش صدا ({key}) ناموفق بود: {e}")
