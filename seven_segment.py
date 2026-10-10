"""
تشخیص عدد نمایشگر ۷-سگمنتی (مثل نمایشگر دیجیتال باسکول).
OCR معمولی (EasyOCR) روی این فونت خوب کار نمی‌کند؛ اینجا به‌جای «خواندن حروف»
روشن/خاموش بودن هر یک از ۷ قطعه‌ی هر رقم بررسی می‌شود.

      aaa
     f   b
     f   b
      ggg
     e   c
     e   c
      ddd
"""
import cv2
import numpy as np

_PATTERNS = {
    '0': ['abcdef'], '1': ['bc'], '2': ['abdeg'], '3': ['abcdg'],
    '4': ['bcfg'], '5': ['acdfg'], '6': ['acdefg', 'cdefg'],
    '7': ['abc', 'abcf'], '8': ['abcdefg'], '9': ['abcdfg', 'abcfg'],
}
_PATTERN_LIST = [(digit, frozenset(p)) for digit, pats in _PATTERNS.items() for p in pats]

# ناحیه‌ی نمونه‌برداری هر قطعه: (x0, x1, y0, y1) به‌صورت کسری از سلول رقم
_REGIONS = {
    'a': (0.25, 0.75, 0.00, 0.17),
    'b': (0.70, 1.00, 0.15, 0.43),
    'c': (0.70, 1.00, 0.57, 0.85),
    'd': (0.25, 0.75, 0.83, 1.00),
    'e': (0.00, 0.30, 0.57, 0.85),
    'f': (0.00, 0.30, 0.15, 0.43),
    'g': (0.25, 0.75, 0.42, 0.58),
}
_ON_THRESHOLD = 0.40


def _binarize(img):
    """قسمت‌های روشن (LED) = ۲۵۵. برای نمایشگر LCD (رقم تیره روی زمینه روشن) خودکار معکوس می‌شود."""
    if img.ndim == 3:
        v = img.max(axis=2)          # کانال روشنایی؛ برای LED قرمز/آبی/سبز هم جواب می‌دهد
    else:
        v = img
    h, w = v.shape
    scale = 1.0
    if h < 120:
        scale = 120 / h
    elif h > 400:
        scale = 400 / h
    if scale != 1.0:
        v = cv2.resize(v, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    v = cv2.GaussianBlur(v, (3, 3), 0)
    _, binary = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.count_nonzero(binary) > binary.size * 0.5:
        binary = cv2.bitwise_not(binary)
    return _remove_frame(binary)


def _remove_frame(binary):
    """حذف قاب/حاشیه‌ی روشنی که دور نمایشگر افتاده (تکه‌ای که تقریباً کل تصویر را می‌گیرد) و نقطه‌های ریز"""
    h, w = binary.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    out = np.zeros_like(binary)
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        if cw >= 0.9 * w and ch >= 0.9 * h:      # قاب
            continue
        if area < 0.0004 * h * w:                # نقطه‌ی ریز
            continue
        out[labels == i] = 255
    return out


def _runs(mask, min_gap):
    """بازه‌های پشت‌سرهم True در یک آرایه‌ی یک‌بعدی؛ فاصله‌های کوچک‌تر از min_gap ادغام می‌شوند"""
    runs = []
    start = None
    last_true = None
    for i, val in enumerate(mask):
        if val:
            if start is None:
                start = i
            last_true = i
        elif start is not None and i - last_true > min_gap:
            runs.append((start, last_true))
            start = None
    if start is not None:
        runs.append((start, last_true))
    return runs


def _classify_cell(cell):
    """cell: تصویر باینری یک رقم -> (رقم یا '?', فاصله تا نزدیک‌ترین الگو)"""
    h, w = cell.shape
    if w < 0.38 * h:
        return '1', 0

    fractions = {}
    for seg, (x0, x1, y0, y1) in _REGIONS.items():
        region = cell[int(y0 * h):max(int(y1 * h), int(y0 * h) + 1),
                      int(x0 * w):max(int(x1 * w), int(x0 * w) + 1)]
        fractions[seg] = float(np.count_nonzero(region)) / max(region.size, 1)

    on = frozenset(s for s, f in fractions.items() if f >= _ON_THRESHOLD)
    best_digit, best_dist = '?', 99
    for digit, pattern in _PATTERN_LIST:
        dist = len(on ^ pattern)
        if dist < best_dist:
            best_digit, best_dist = digit, dist
    if best_dist > 1:
        return '?', best_dist
    return best_digit, best_dist


def _decode_binary(binary):
    h, w = binary.shape
    col_has = (binary > 0).sum(axis=0) > max(2, 0.02 * h)
    runs = _runs(col_has, min_gap=max(2, int(0.02 * h)))

    infos = []
    for x0, x1 in runs:
        sub = binary[:, x0:x1 + 1]
        rows = np.where((sub > 0).any(axis=1))[0]
        if len(rows) == 0:
            continue
        y0, y1 = rows[0], rows[-1]
        extent = y1 - y0 + 1
        coverage = len(rows) / extent
        infos.append((x0, x1, y0, y1, extent, coverage))
    if not infos:
        return [], 0

    max_extent = max(i[4] for i in infos)
    digits = []
    total_dist = 0
    for x0, x1, y0, y1, extent, coverage in infos:
        # دو نقطه‌ی «:» ، اعشار، متن‌های ریز مثل DST -> رد می‌شوند
        if extent < 0.7 * max_extent or coverage < 0.6:
            continue
        digit, dist = _classify_cell(binary[y0:y1 + 1, x0:x1 + 1])
        digits.append(digit)
        total_dist += dist
    return digits, total_dist


def decode_seven_segment(img, max_dist=0):
    """
    خواندن عدد از تصویر نمایشگر ۷-سگمنتی.
    max_dist=0  : فقط وقتی همه‌ی رقم‌ها دقیقاً با الگوی ۷-سگمنت جور باشند (امن برای حالت خودکار)
    max_dist=1  : کمی تحمل خطا (وقتی مطمئنید نمایشگر ۷-سگمنتی است)
    بازگشت: رشته‌ی رقم‌ها یا None
    """
    if img is None or img.size == 0:
        return None
    binary = _binarize(img)
    h, w = binary.shape

    best = None   # (avg_dist, |k|, digits)
    for k in (0.0, 0.15, -0.15, 0.3, -0.3):        # ارقام کج (ایتالیک) را صاف می‌کند
        if k == 0.0:
            b = binary
        else:
            pad = int(abs(k) * h)
            wide = cv2.copyMakeBorder(binary, 0, 0, pad, pad, cv2.BORDER_CONSTANT, value=0)
            M = np.float32([[1, k, -k * h / 2], [0, 1, 0]])
            b = cv2.warpAffine(wide, M, (wide.shape[1], h), flags=cv2.INTER_NEAREST)
        digits, total = _decode_binary(b)
        if not digits or '?' in digits:
            continue
        avg = total / len(digits)
        cand = (avg, abs(k), ''.join(digits))
        if best is None or cand[:2] < best[:2]:
            best = cand

    if best is None:
        return None
    avg, _, text = best
    if avg * len(text) > max_dist:
        return None
    return text
