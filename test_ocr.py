"""
تست OCR باسکول روی یک عکس.
استفاده: python test_ocr.py <مسیر عکس> [x1 y1 x2 y2]
مثال:   python test_ocr.py scale.jpg 0.30 0.14 0.84 0.30
"""
import sys, os, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from seven_segment import decode_seven_segment, _binarize

def test(img_path, roi=None):
    img = cv2.imread(img_path)
    if img is None:
        print(f"❌ عکس پیدا نشد: {img_path}")
        return
    h, w = img.shape[:2]
    print(f"📷 عکس: {w}x{h}")

    if roi:
        x1, y1, x2, y2 = roi
        crop = img[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]
        print(f"✂️  crop: {crop.shape[1]}x{crop.shape[0]}")
    else:
        crop = img
        print("⚠️  ROI نداده شده - کل عکس")

    debug_dir = os.path.dirname(img_path)
    cv2.imwrite(os.path.join(debug_dir, "debug_crop.jpg"), crop)
    binary = _binarize(crop)
    cv2.imwrite(os.path.join(debug_dir, "debug_binary.jpg"), binary)
    print(f"💾 debug_crop.jpg و debug_binary.jpg ذخیره شد")

    for max_dist in [0, 1, 2, 3]:
        result = decode_seven_segment(crop, max_dist=max_dist)
        if result:
            print(f"✅ max_dist={max_dist}: عدد = {result}")
            return result
        else:
            print(f"❌ max_dist={max_dist}: نتیجه‌ای نداشت")
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("استفاده: python test_ocr.py <عکس> [x1 y1 x2 y2]")
        sys.exit(1)
    roi = [float(x) for x in sys.argv[2:6]] if len(sys.argv) == 6 else None
    test(sys.argv[1], roi)
