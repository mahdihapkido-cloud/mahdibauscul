"""
ارسال پیامک با سرویس کاوه‌نگار
فقط برای سیستم اتوماسیون (بارهای خودمان) — موقع صدور فیش نهایی

نصب:
    pip install kavenegar

استفاده در ui.py:
    from sms import send_receipt_sms
    send_receipt_sms(receipt_number, net_weight, items, plate_number)
"""

import threading
from datetime import datetime

try:
    from kavenegar import KavenegarAPI, APIException, HTTPException
    HAS_KAVENEGAR = True
except ImportError:
    HAS_KAVENEGAR = False

import config

def _get_settings():
    """تنظیمات را لحظه‌ی ارسال از config می‌خوند — نه موقع import"""
    return {
        'api_key': getattr(config, 'KAVENEGAR_API_KEY', 'YOUR-API-KEY-HERE'),
        'phone':   getattr(config, 'MANAGER_PHONE',     '09120000000'),
        'sender':  getattr(config, 'SMS_SENDER',        '1000596446'),
    }


def _build_message(receipt_number, net_weight, items, plate_number=None):
    """متن پیامک را می‌سازد"""
    now = datetime.now().strftime('%H:%M')

    lines = [
        f"🏭 {config.COMPANY_NAME}",
        f"📋 فیش: {receipt_number} | ⏰ {now}",
    ]

    if plate_number:
        lines.append(f"🚛 پلاک: {plate_number}")

    lines.append(f"⚖️ جمع بار: {net_weight:,.0f} کیلوگرم")

    if items:
        lines.append("─────────────")
        for it in items:
            lines.append(f"• {it['name']}: {it['quantity']:,.0f} kg")

    return "\n".join(lines)


def send_receipt_sms(receipt_number, net_weight, items,
                     plate_number=None, on_success=None, on_error=None):
    """
    پیامک فیش نهایی را در یک thread جداگانه ارسال می‌کند تا UI قفل نشود.

    پارامترها:
        receipt_number : شماره فیش (مثلاً '001')
        net_weight     : جمع وزن خالص (کیلوگرم)
        items          : لیست اقلام [{'name': str, 'quantity': float}, ...]
        plate_number   : پلاک ماشین (اختیاری)
        on_success     : تابع callback بدون پارامتر — در thread اصلی فراخوانی نمی‌شود
        on_error       : تابع callback با یک پارامتر str (پیام خطا)
    """
    if not HAS_KAVENEGAR:
        msg = "کتابخانه kavenegar نصب نیست:\n  pip install kavenegar"
        print(f"[SMS] {msg}")
        if on_error:
            on_error(msg)
        return

    cfg = _get_settings()

    if cfg['api_key'] == 'YOUR-API-KEY-HERE':
        msg = "کلید API کاوه‌نگار تنظیم نشده.\nدر config.py مقدار KAVENEGAR_API_KEY را وارد کنید."
        print(f"[SMS] {msg}")
        if on_error:
            on_error(msg)
        return

    text = _build_message(receipt_number, net_weight, items, plate_number)

    def _send():
        try:
            api = KavenegarAPI(cfg['api_key'])
            params = {
                'sender': cfg['sender'],
                'receptor': cfg['phone'],
                'message': text,
            }
            response = api.sms_send(params)
            print(f"[SMS] ارسال موفق — messageid: {response[0]['messageid']}")
            if on_success:
                on_success()
        except APIException as e:
            msg = f"خطای API کاوه‌نگار: {e}"
            print(f"[SMS] {msg}")
            if on_error:
                on_error(msg)
        except HTTPException as e:
            msg = f"خطای اتصال کاوه‌نگار: {e}"
            print(f"[SMS] {msg}")
            if on_error:
                on_error(msg)
        except Exception as e:
            msg = f"خطای ناشناخته پیامک: {e}"
            print(f"[SMS] {msg}")
            if on_error:
                on_error(msg)

    t = threading.Thread(target=_send, daemon=True)
    t.start()
