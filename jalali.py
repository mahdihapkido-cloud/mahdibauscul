# تبدیل تاریخ میلادی به شمسی (بدون نیاز به کتابخانه‌ی خارجی)
from datetime import datetime

_PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(text):
    return str(text).translate(_PERSIAN_DIGITS)


def gregorian_to_jalali(gy, gm, gd):
    """تبدیل تاریخ میلادی (سال، ماه، روز) به شمسی؛ خروجی (jy, jm, jd)"""
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    for i in range(gm2):
        g_day_no += g_days_in_month[i]
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    g_day_no += gd2

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm, jd = 12, j_day_no + 1
    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= j_days_in_month[i]
    return jy, jm, jd


def _parse_dt(value):
    """رشته یا شیء datetime را به datetime تبدیل می‌کند"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).split('.')[0].replace('T', ' ')
    for pattern in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def format_jalali_date(value, persian_digits=True):
    """فقط تاریخ شمسی به‌صورت YYYY/MM/DD (یا با اعداد فارسی)"""
    dt = _parse_dt(value)
    if dt is None:
        return "—"
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    text = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return to_persian_digits(text) if persian_digits else text


def format_jalali_datetime(value, persian_digits=True, with_month_name=False):
    """تاریخ شمسی + ساعت، مثلا ۱۴۰۵/۰۷/۰۱ - ۱۱:۲۰ یا با نام ماه"""
    dt = _parse_dt(value)
    if dt is None:
        return "—"
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    if with_month_name:
        date_part = f"{jd} {_PERSIAN_MONTHS[jm - 1]} {jy}"
    else:
        date_part = f"{jy:04d}/{jm:02d}/{jd:02d}"
    time_part = dt.strftime('%H:%M:%S')
    text = f"{date_part} - {time_part}"
    return to_persian_digits(text) if persian_digits else text
