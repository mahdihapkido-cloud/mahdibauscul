# 📦 راهنمای نصب سیستم توزین

---

## 🪟 ویندوز

### مرحله 1: نصب Python

1. به [python.org](https://www.python.org) برو
2. **Python 3.10+** دانلود کن
3. فایل را اجرا کن و **"Add Python to PATH"** را تیک بزن
4. **Install** را بزن

### مرحله 2: نصب git (اختیاری):

```bash
# یا دانلود از git-scm.com
```

### مرحله 3: دانلود پروژه:

```bash
git clone <url>
cd weighing_system
```

### مرحله 4: ایجاد محیط مجازی:

```bash
python -m venv venv
venv\Scripts\activate
```

### مرحله 5: نصب کتابخانه‌ها:

```bash
pip install -r requirements.txt
```

### مرحله 6: اجرای برنامه:

```bash
python main.py
```

---

## 🐧 لینوکس (Ubuntu/Debian)

### مرحله 1: بروزرسانی سیستم:

```bash
sudo apt update
sudo apt upgrade -y
```

### مرحله 2: نصب Python و کتابخانه‌های مورد نیاز:

```bash
sudo apt install python3 python3-pip python3-venv -y
```

### مرحله 3: نصب کتابخانه‌های OpenCV:

```bash
sudo apt install python3-opencv -y
```

### مرحله 4: دانلود پروژه:

```bash
git clone <url>
cd weighing_system
```

### مرحله 5: ایجاد محیط مجازی:

```bash
python3 -m venv venv
source venv/bin/activate
```

### مرحله 6: نصب کتابخانه‌ها:

```bash
pip install -r requirements.txt
```

### مرحله 7: اجرای برنامه:

```bash
python3 main.py
```

---

## 🍎 macOS

### مرحله 1: نصب Homebrew (اگر ندارد):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### مرحله 2: نصب Python:

```bash
brew install python3
```

### مرحله 3: دانلود پروژه:

```bash
git clone <url>
cd weighing_system
```

### مرحله 4: ایجاد محیط مجازی:

```bash
python3 -m venv venv
source venv/bin/activate
```

### مرحله 5: نصب کتابخانه‌ها:

```bash
pip install -r requirements.txt
```

### مرحله 6: اجرای برنامه:

```bash
python3 main.py
```

---

## 🐳 نصب با Docker (پیشنهادی برای سرور)

### مرحله 1: نصب Docker:

[دانلود Docker](https://www.docker.com/get-started)

### مرحله 2: Dockerfile:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### مرحله 3: بناء و اجرا:

```bash
docker build -t weighing-system .
docker run -it --device /dev/video0 weighing-system
```

---

## ✅ تست نصب

برای اطمینان از صحیح بودن نصب:

```bash
python -c "import cv2; print('OpenCV OK')"
python -c "import easyocr; print('EasyOCR OK')"
python -c "import PyQt6; print('PyQt6 OK')"
python -c "import openpyxl; print('openpyxl OK')"
python -c "import reportlab; print('ReportLab OK')"
```

اگر خطای **ModuleNotFoundError** بگی، کتابخانه نصب نشده است.

---

## 🔧 تنظیم دوربین

### Windows:
```python
# Device Manager → Cameras بررسی کن
cap = cv2.VideoCapture(0)  # یا 1, 2, ...
```

### Linux:
```bash
ls /dev/video*
```

### macOS:
```bash
# System Settings → Privacy & Security → Camera
```

---

## 🖨️ تنظیم پرینتر

### Windows:
```
Settings → Devices → Printers & Scanners
```

### Linux:
```bash
lpstat -p  # نمایش پرینترها
```

### macOS:
```
System Preferences → Printers & Scanners
```

---

## 🆘 حل مشکلات

### خطا: "No module named 'cv2'":
```bash
pip install opencv-python --upgrade
```

### خطا: "QXcbConnection: Could not connect to display":
```bash
# روی لینوکس بدون GUI
export DISPLAY=:0
```

### خطا: دوربین کار نمی‌کند:
```bash
# بررسی دوربین
python -c "import cv2; cap=cv2.VideoCapture(0); print(cap.isOpened())"
```

### خطا: حافظه کافی نیست (EasyOCR):
```bash
# نصب نسخه کم‌حجم
pip install easyocr --no-cache-dir
```

---

## 📊 شرایط سیستم

| سیستم | نسخه | توصیه |
|------|------|------|
| Python | 3.8+ | 3.10+ بهتر است |
| RAM | 4GB حداقل | 8GB توصیه می‌شود |
| CPU | Dual-core | Quad-core بهتر است |
| دوربین | USB یا داخلی | 1080p توصیه می‌شود |
| پرینتر | USB | thermal پرینتر بهتر است |

---

## 🚀 اجرای برنامه به صورت خودکار

### Windows:
```
Start → Run → shell:startup
# فایل shortcut بساز اینجا
```

### Linux:
```bash
sudo nano /etc/systemd/system/weighing.service
```

```ini
[Unit]
Description=Weighing System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/weighing_system
ExecStart=/usr/bin/python3 /home/pi/weighing_system/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable weighing
sudo systemctl start weighing
```

---

## 📞 پشتیبانی نصب

اگر مشکل داری:

1. **Google کن** (بیشتر مشکلات حل شده)
2. **Stack Overflow** جستجو کن
3. **Issue** باز کن روی GitHub

---

**نسخه**: 1.0  
**آخرین بروزرسانی**: 1403/06/19
