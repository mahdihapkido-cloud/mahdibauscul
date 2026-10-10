@echo off
chcp 65001 >nul
echo ========================================
echo    ساخت EXE سیستم توزین خودرو
echo ========================================
echo.

:: فعال‌سازی venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo venv پیدا نشد، از Python عمومی استفاده می‌شود...
)

:: نصب ابزار build
echo در حال نصب PyInstaller...
pip install pyinstaller arabic-reshaper python-bidi --quiet

:: ساخت EXE
echo.
echo در حال build (چند دقیقه طول می‌کشد)...
pyinstaller weighing.spec --clean --noconfirm

:: کپی دیتابیس
if exist "data\weighing.db" (
    if not exist "dist\WeighingSystem\data" mkdir "dist\WeighingSystem\data"
    copy "data\weighing.db" "dist\WeighingSystem\data\weighing.db" >nul
    echo دیتابیس کپی شد.
)

echo.
echo ========================================
if exist "dist\WeighingSystem\WeighingSystem.exe" (
    echo    Build موفق بود!
    echo    فایل: dist\WeighingSystem\WeighingSystem.exe
) else (
    echo    Build ناموفق بود - خطا را بررسی کن
)
echo ========================================
pause
