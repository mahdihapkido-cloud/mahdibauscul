"""
خواندن اعداد انگلیسی معمولی (نه ۷-سگمنتی) بدون هیچ مدل یادگیری ماشین.

روش کار (فقط OpenCV + NumPy + Pillow):
  ۱) سیاه‌وسفید کردن تصویر (Otsu) و تشخیص خودکار «رقم روشن روی زمینه تیره» یا برعکس
  ۲) پیدا کردن هر رقم با Connected Components (رقم‌های چسبیده به هم جدا می‌شوند)
  ۳) هر رقم به اندازه‌ی ثابت تبدیل می‌شود و با «قالب‌های» ۰ تا ۹ مقایسه می‌شود
     (Template Matching - قالب‌ها همان لحظه با فونت‌های خود سیستم و فونت‌های OpenCV
     ساخته می‌شوند، نه از روی داده‌ی آموزشی)
  ۴) تعداد «حفره‌ها» (مثلاً ۸ دو حفره دارد، ۰ و ۶ و ۹ یکی) به‌عنوان امتیاز کمکی

بازگشت: decode_plain_digits(img) -> (رشته‌ی ارقام یا None، اطمینان ۰..۱)
"""
import glob
import os

import cv2
import numpy as np

CELL_W, CELL_H = 24, 36          # اندازه‌ی استاندارد هر رقم برای مقایسه
MIN_SCORE = 0.45                 # کمتر از این = رقم نامعتبر (نویز)
SHIFT_SCORE_BONUS = 0.12         # امتیاز/جریمه‌ی تعداد حفره‌ها
EXPECTED_HOLES = {'0': {1}, '1': {0}, '2': {0}, '3': {0}, '4': {0, 1},
                  '5': {0}, '6': {1}, '7': {0}, '8': {2}, '9': {1}}

_FONT_FILES = [
    # ویندوز
    "arialbd.ttf", "arial.ttf", "tahomabd.ttf", "tahoma.ttf", "verdanab.ttf",
    "verdana.ttf", "segoeuib.ttf", "calibrib.ttf", "consolab.ttf", "trebucbd.ttf",
    # لینوکس / مک
    "DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "LiberationSans-Bold.ttf",
    "LiberationSans-Regular.ttf", "FreeSansBold.ttf", "Arial Bold.ttf",
    "Arial.ttf", "Helvetica.ttc",
]


# ------------------------------------------------------------------ قالب‌ها
def _glyph_mask(canvas):
    """تصویر خاکستری یک رقم (سفید روی سیاه) -> ماسک بریده‌شده به کادر رقم"""
    _, m = cv2.threshold(canvas, 100, 255, cv2.THRESH_BINARY)
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        return None
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _render_pil(font_file, digit, size=160):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(font_file, size)
    img = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(img).text((size // 2, size // 4), digit, fill=255, font=font)
    return _glyph_mask(np.array(img))


def _render_hershey(face, thickness, digit, size=160):
    canvas = np.zeros((size * 2, size * 2), np.uint8)
    scale = size / 22.0
    cv2.putText(canvas, digit, (size // 2, int(size * 1.4)), face, scale, 255,
                thickness, cv2.LINE_AA)
    return _glyph_mask(canvas)


def _stroke_variants(mask):
    """همان رقم با ضخامت‌های مختلف (نازک، معمولی، ضخیم، خیلی ضخیم)"""
    out = [mask]
    h = mask.shape[0]
    for delta in (-0.05, 0.05, 0.10):        # نسبت به ارتفاع رقم
        k = max(1, int(abs(delta) * h))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
        m = cv2.erode(mask, kernel) if delta < 0 else cv2.dilate(mask, kernel)
        if m.any():
            out.append(cv2.copyMakeBorder(m, 0, 0, 0, 0, cv2.BORDER_CONSTANT))
    return out


def _normalize_cell(mask):
    """ماسک رقم -> بردار نرمال‌شده‌ی ثابت برای همبستگی"""
    small = cv2.resize(mask, (CELL_W, CELL_H), interpolation=cv2.INTER_AREA)
    v = small.astype(np.float32).ravel() / 255.0
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else None


def _count_holes(mask):
    """تعداد حفره‌های داخل رقم (مثلاً ۸ -> ۲)"""
    h, w = mask.shape
    scale = 64.0 / h
    m = cv2.resize(mask, (max(8, int(w * scale)), 64), interpolation=cv2.INTER_AREA)
    m = cv2.copyMakeBorder((m > 127).astype(np.uint8) * 255, 2, 2, 2, 2,
                           cv2.BORDER_CONSTANT, value=0)
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return 0
    area_total = m.shape[0] * m.shape[1]
    holes = 0
    for c, hh in zip(cnts, hier[0]):
        if hh[3] != -1 and cv2.contourArea(c) > 0.004 * area_total:
            holes += 1
    return holes


def _synthetic_ones():
    out = []
    for stem in (18, 30):
        for flag in (False, True):
            for base in (False, True):
                c = np.zeros((160, 120), np.uint8)
                x = 60 - stem // 2
                cv2.rectangle(c, (x, 10), (x + stem, 150), 255, -1)
                if flag:
                    cv2.line(c, (x + stem // 2, 12), (x - 22, 46), 255, max(12, stem // 2))
                if base:
                    cv2.rectangle(c, (x - 26, 138), (x + stem + 26, 150), 255, -1)
                m = _glyph_mask(c)
                if m is not None:
                    out.append(m)
    return out


_TEMPLATES = None     # {digit: [(vector, aspect), ...]}


def _build_templates(extra_fonts=None, only_fonts=None):
    templates = {str(d): [] for d in range(10)}

    def add(digit, mask):
        if mask is None or mask.size == 0:
            return
        for m in _stroke_variants(mask):
            vec = _normalize_cell(m)
            if vec is not None:
                templates[digit].append((vec, m.shape[1] / m.shape[0]))

    font_files = []
    if only_fonts is None:
        for name in _FONT_FILES + list(extra_fonts or []):
            font_files.append(name)
        for pattern in ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            font_files += glob.glob(pattern)
    else:
        font_files = list(only_fonts)

    used = 0
    seen = set()
    for f in font_files:
        if f in seen:
            continue
        seen.add(f)
        try:
            masks = {str(d): _render_pil(f, str(d)) for d in range(10)}
        except Exception:
            continue
        if any(m is None for m in masks.values()):
            continue
        for d, m in masks.items():
            add(d, m)
        used += 1

    # چند شکل ۱ ساختگی (ساقه، ساقه + پرچم، ساقه + پرچم + پایه) تا ۱ با هر فونتی خوانده شود
    for mask in _synthetic_ones():
        add('1', mask)

    # فونت‌های OpenCV همیشه هست (حتی اگر هیچ فونت سیستمی پیدا نشود)
    for face in (cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX):
        for thick in (6, 12):
            for d in range(10):
                add(str(d), _render_hershey(face, thick, str(d)))
    return templates


def _get_templates():
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = _build_templates()
    return _TEMPLATES


# ------------------------------------------------------------------ پردازش تصویر
def _binarize(img):
    """رقم‌ها = ۲۵۵ (سفید) روی زمینه‌ی ۰؛ قطبیت (روشن/تیره) خودکار تشخیص داده می‌شود"""
    if img.ndim == 3:
        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    h, w = gray.shape
    longest = max(h, w)
    if longest > 700:
        s = 700.0 / longest
        gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    elif h < 120:
        s = 120.0 / h
        gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # زمینه معمولاً حاشیه‌ی تصویر است؛ اگر روشن بود برعکس می‌کنیم
    b = max(2, min(binary.shape) // 40)
    ring = np.concatenate([binary[:b].ravel(), binary[-b:].ravel(),
                           binary[:, :b].ravel(), binary[:, -b:].ravel()])
    ring_frac = float(np.count_nonzero(ring)) / ring.size
    if ring_frac > 0.75:
        binary = cv2.bitwise_not(binary)
    elif ring_frac >= 0.25:                        # مبهم -> رقم‌ها را «کم‌تر» فرض می‌کنیم
        if np.count_nonzero(binary) > binary.size * 0.5:
            binary = cv2.bitwise_not(binary)
    return binary


def _find_glyphs(binary):
    """لیست ماسک هر رقم به ترتیب چپ به راست"""
    H, W = binary.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w >= 0.9 * W and h >= 0.9 * H:            # قاب دور نمایشگر
            continue
        if area < 0.0004 * H * W or h < 0.06 * H:    # نقطه‌ی ریز / نویز
            continue
        comps.append([x, y, x + w, y + h, [i]])
    if not comps:
        return []
    top_h = max(c[3] - c[1] for c in comps)
    comps = [c for c in comps if (c[3] - c[1]) >= 0.3 * top_h]   # متن ریز/لوگو

    # قطعه‌های یک رقم که بالا و پایین هم افتاده‌اند (مثلاً فونت استنسیل) ادغام می‌شوند
    comps.sort(key=lambda c: c[0])
    merged = []
    for c in comps:
        if merged:
            m = merged[-1]
            overlap = min(m[2], c[2]) - max(m[0], c[0])
            v_gap = max(m[1], c[1]) - min(m[3], c[3])          # فاصله‌ی عمودی دو قطعه
            if overlap > 0.6 * min(m[2] - m[0], c[2] - c[0]) and v_gap < 0.3 * top_h:
                m[0], m[1] = min(m[0], c[0]), min(m[1], c[1])
                m[2], m[3] = max(m[2], c[2]), max(m[3], c[3])
                m[4] += c[4]
                continue
        merged.append(c)

    max_h = max(m[3] - m[1] for m in merged)
    glyphs = []
    for x0, y0, x1, y1, ids in merged:
        if (y1 - y0) < 0.55 * max_h:                 # نقطه‌ی اعشار، ':' ، متن ریز
            continue
        sub = np.isin(labels[y0:y1, x0:x1], ids).astype(np.uint8) * 255
        glyphs.append(sub)
    return glyphs


def _classify(mask):
    """-> (رقم، امتیاز ۰..۱)"""
    h, w = mask.shape
    aspect = w / h
    vec = _normalize_cell(mask)
    if vec is None:
        return '?', 0.0
    holes = _count_holes(mask)
    best_digit, best_score = '?', -9.0
    for digit, items in _get_templates().items():
        s = max(float(np.dot(vec, t)) for t, _a in items)
        if holes in EXPECTED_HOLES[digit]:
            s += SHIFT_SCORE_BONUS
        else:
            s -= SHIFT_SCORE_BONUS
        if aspect < 0.50:                            # رقم باریک = ۱
            s += 0.30 if digit == '1' else -0.30
        if s > best_score:
            best_digit, best_score = digit, s
    return best_digit, best_score


def _split_wide(mask, k):
    """رقم‌های چسبیده را در کم‌ترین ضخامت عمودی به k قسمت تقسیم می‌کند"""
    h, w = mask.shape
    proj = (mask > 0).sum(axis=0)
    cuts = [0]
    for j in range(1, k):
        center = int(j * w / k)
        lo, hi = max(cuts[-1] + 2, center - w // (3 * k)), min(w - 2, center + w // (3 * k))
        if hi <= lo:
            cuts.append(center)
        else:
            cuts.append(lo + int(np.argmin(proj[lo:hi + 1])))
    cuts.append(w)
    parts = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        p = mask[:, a:b]
        ys, xs = np.where(p > 0)
        if len(xs) > 0:
            parts.append(p[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return parts


def decode_plain_digits(img):
    """
    خواندن اعداد انگلیسی از تصویر (بدون یادگیری ماشین).
    بازگشت: (رشته‌ی ارقام یا None، اطمینان بین ۰ و ۱)
    """
    if img is None or img.size == 0:
        return None, 0.0
    binary = _binarize(img)
    glyphs = _find_glyphs(binary)
    if not glyphs:
        return None, 0.0

    digits, scores = [], []
    for g in glyphs:
        h, w = g.shape
        digit, score = _classify(g)
        if w / h > 0.95:                              # شاید دو رقم چسبیده باشند
            k = max(2, int(round((w / h) / 0.62)))
            parts = _split_wide(g, k)
            if len(parts) >= 2:
                res = [_classify(p) for p in parts]
                avg = sum(s for _d, s in res) / len(res)
                if avg > score + 0.02:
                    digits += [d for d, _s in res]
                    scores += [s for _d, s in res]
                    continue
        digits.append(digit)
        scores.append(score)

    if not digits or min(scores) < MIN_SCORE or '?' in digits:
        return None, 0.0
    conf = float(max(0.0, min(1.0, np.mean(scores))))
    return ''.join(digits), conf
