from reportlab.lib.pagesizes import A5
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime
from pathlib import Path
import os
import subprocess
import platform

import config
from jalali import format_jalali_datetime

# برای نمایش درست فارسی در PDF (pip install arabic-reshaper python-bidi)
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None

# فونت فارسی: فایل TTF را در پوشه fonts/ کنار برنامه بگذارید (مثلا Vazirmatn-Regular.ttf)
FONT_CANDIDATES = [
    "fonts/Vazirmatn-Regular.ttf",
    "fonts/Vazirmatn.ttf",
    "fonts/Vazir.ttf",
    "fonts/vazirmatn-regular.ttf",
    "fonts/vazir.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def register_persian_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('FaFont', path))
                return 'FaFont'
            except Exception:
                continue
    print("هشدار: فونت فارسی پیدا نشد؛ فایل TTF را در پوشه fonts/ بگذارید")
    return 'Helvetica'


def fa(text):
    """آماده‌سازی متن فارسی برای PDF (اتصال حروف + راست‌به‌چپ)"""
    text = str(text)
    if arabic_reshaper is not None:
        return get_display(arabic_reshaper.reshape(text))
    return text


def _fmt_dt(value):
    """datetime/رشته را به تاریخ شمسی + ساعت خوانا تبدیل می‌کند"""
    if not value:
        return "—"
    return format_jalali_datetime(value)


class ReceiptGenerator:
    def __init__(self):
        Path(config.RECEIPT_DIRECTORY).mkdir(exist_ok=True)
        self.font = register_persian_font()

    def generate_pdf(self, data):
        """
        تولید فیش PDF سایز A5
        data = {
            'receipt_number': '001',
            'plate_number': '۱۲۳۴۵۶۷',
            'empty_weight': 1500,
            'final_weight': 1700,
            'net_weight': 200,
            'entry_time': ساعت ورود (وزن خالی),
            'exit_time': ساعت خروج (وزن پر),
        }
        """
        filename = f"{config.RECEIPT_DIRECTORY}/receipt_{data['receipt_number']}.pdf"

        doc = SimpleDocTemplate(filename, pagesize=A5,
                                rightMargin=1 * cm, leftMargin=1 * cm,
                                topMargin=1 * cm, bottomMargin=1 * cm)
        elements = []

        header_style = ParagraphStyle('Header', fontName=self.font, fontSize=17,
                                      alignment=1, leading=22, textColor=colors.HexColor('#111827'))
        sub_style = ParagraphStyle('Sub', fontName=self.font, fontSize=10,
                                   alignment=1, leading=14, textColor=colors.HexColor('#6B7280'))
        footer_style = ParagraphStyle('Footer', fontName=self.font, fontSize=9,
                                      alignment=1, leading=13, textColor=colors.HexColor('#4B5563'))
        cell_label = ParagraphStyle('CellLabel', fontName=self.font, fontSize=10,
                                    alignment=1, leading=14, textColor=colors.HexColor('#6B7280'))
        cell_value = ParagraphStyle('CellValue', fontName=self.font, fontSize=13,
                                    alignment=1, leading=17, textColor=colors.HexColor('#111827'))

        # --- بالای صفحه: نام باسکول ---
        elements.append(Paragraph(fa(config.COMPANY_NAME), header_style))
        elements.append(Spacer(1, 0.15 * cm))
        elements.append(Paragraph(fa(f"شماره قبض: {data['receipt_number']}"), sub_style))
        elements.append(Spacer(1, 0.5 * cm))

        # --- جدول آمار وسط صفحه ---
        def cell(label, value):
            return [Paragraph(fa(label), cell_label), Paragraph(fa(value), cell_value)]

        rows = [
            cell("وزن پر", f"{data['final_weight']:.1f} کیلوگرم") +
            cell("وزن خالی", f"{data['empty_weight']:.1f} کیلوگرم"),
            cell("خالص بار", f"{data['net_weight']:.1f} کیلوگرم") +
            cell("شماره قبض", str(data['receipt_number'])),
            cell("ساعت ورود", _fmt_dt(data.get('entry_time'))) +
            cell("ساعت خروج", _fmt_dt(data.get('exit_time'))),
        ]
        # هر ردیف بالا شامل ۲ برچسب و ۲ مقدار است -> باید به صورت جدولی جدا مرتب شود
        table_data = []
        for r in rows:
            table_data.append([r[0], r[2]])
            table_data.append([r[1], r[3]])

        table = Table(table_data, colWidths=[6 * cm, 6 * cm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.25 * cm),
            ('TOPPADDING', (0, 0), (-1, -1), 0.15 * cm),
            ('LINEBELOW', (0, 1), (-1, 1), 0.6, colors.HexColor('#D9DEEA')),
            ('LINEBELOW', (0, 3), (-1, 3), 0.6, colors.HexColor('#D9DEEA')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#D9DEEA')),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.7 * cm))

        # --- پایین صفحه: آدرس ---
        elements.append(Paragraph(fa(config.COMPANY_ADDRESS), footer_style))
        elements.append(Paragraph(fa("تلفن: ۰۱۱۴۳۱۱۶۱۰۲"), footer_style))
        print_time = format_jalali_datetime(datetime.now())
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(Paragraph(fa(f"زمان چاپ: {print_time}"), footer_style))

        doc.build(elements)
        return filename

    def generate_internal_pdf(self, data):
        """
        تولید رسید PDF برای بارهای خودمان (سیستم اتوماسیون) - شامل ریز اقلام بار.
        data = {
            'receipt_number': '001',
            'empty_weight': 1500, 'final_weight': 1700, 'net_weight': 200,
            'entry_time': ..., 'exit_time': ...,
            'items': [{'name': 'برنج', 'quantity': 120}, ...],
        }
        فایل‌ها در زیرپوشه‌ی جداگانه‌ی internal/ ذخیره می‌شوند تا از رسیدهای مشتری جدا باشند.
        """
        out_dir = Path(config.RECEIPT_DIRECTORY) / "internal"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = str(out_dir / f"receipt_internal_{data['receipt_number']}.pdf")

        doc = SimpleDocTemplate(filename, pagesize=A5,
                                rightMargin=1 * cm, leftMargin=1 * cm,
                                topMargin=1 * cm, bottomMargin=1 * cm)
        elements = []

        header_style = ParagraphStyle('Header', fontName=self.font, fontSize=17,
                                      alignment=1, leading=22, textColor=colors.HexColor('#111827'))
        sub_style = ParagraphStyle('Sub', fontName=self.font, fontSize=10,
                                   alignment=1, leading=14, textColor=colors.HexColor('#6B7280'))
        footer_style = ParagraphStyle('Footer', fontName=self.font, fontSize=9,
                                      alignment=1, leading=13, textColor=colors.HexColor('#4B5563'))
        cell_label = ParagraphStyle('CellLabel', fontName=self.font, fontSize=10,
                                    alignment=1, leading=14, textColor=colors.HexColor('#6B7280'))
        cell_value = ParagraphStyle('CellValue', fontName=self.font, fontSize=13,
                                    alignment=1, leading=17, textColor=colors.HexColor('#111827'))
        item_head = ParagraphStyle('ItemHead', fontName=self.font, fontSize=10,
                                   alignment=1, leading=14, textColor=colors.HexColor('#4B5563'))
        item_cell = ParagraphStyle('ItemCell', fontName=self.font, fontSize=11,
                                   alignment=1, leading=15, textColor=colors.HexColor('#111827'))

        elements.append(Paragraph(fa(config.COMPANY_NAME), header_style))
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(Paragraph(fa(f"شماره قبض: {data['receipt_number']}"), sub_style))
        elements.append(Spacer(1, 0.5 * cm))

        def cell(label, value):
            return [Paragraph(fa(label), cell_label), Paragraph(fa(value), cell_value)]

        rows = [
            cell("وزن پر", f"{data['final_weight']:.1f} کیلوگرم") +
            cell("وزن خالی", f"{data['empty_weight']:.1f} کیلوگرم"),
            cell("خالص بار", f"{data['net_weight']:.1f} کیلوگرم") +
            cell("شماره قبض", str(data['receipt_number'])),
            cell("ساعت ورود", _fmt_dt(data.get('entry_time'))) +
            cell("ساعت خروج", _fmt_dt(data.get('exit_time'))),
        ]
        table_data = []
        for r in rows:
            table_data.append([r[0], r[2]])
            table_data.append([r[1], r[3]])

        table = Table(table_data, colWidths=[6 * cm, 6 * cm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.25 * cm),
            ('TOPPADDING', (0, 0), (-1, -1), 0.15 * cm),
            ('LINEBELOW', (0, 1), (-1, 1), 0.6, colors.HexColor('#D9DEEA')),
            ('LINEBELOW', (0, 3), (-1, 3), 0.6, colors.HexColor('#D9DEEA')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#D9DEEA')),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.5 * cm))

        # --- ریز اقلام بار ---
        items = data.get('items') or []
        if items:
            item_rows = [[Paragraph(fa("ردیف"), item_head), Paragraph(fa("محصول"), item_head),
                         Paragraph(fa("خالص (kg)"), item_head)]]
            for i, it in enumerate(items, start=1):
                item_rows.append([Paragraph(fa(str(i)), item_cell),
                                  Paragraph(fa(it['name']), item_cell),
                                  Paragraph(fa(f"{it['quantity']:.1f}"), item_cell)])
            item_table = Table(item_rows, colWidths=[2 * cm, 6 * cm, 4 * cm])
            item_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0.2 * cm),
                ('TOPPADDING', (0, 0), (-1, -1), 0.2 * cm),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F5FA')),
                ('LINEBELOW', (0, 0), (-1, 0), 0.6, colors.HexColor('#D9DEEA')),
                ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#D9DEEA')),
                ('LINEBELOW', (0, 1), (-1, -2), 0.4, colors.HexColor('#EEF0F6')),
            ]))
            elements.append(item_table)
            elements.append(Spacer(1, 0.5 * cm))

        elements.append(Paragraph(fa(config.COMPANY_ADDRESS), footer_style))
        elements.append(Paragraph(fa("تلفن: ۰۱۱-۴۳۱۱۶۱۰۲"), footer_style))
        print_time = format_jalali_datetime(datetime.now())
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(Paragraph(fa(f"زمان چاپ: {print_time}"), footer_style))

        doc.build(elements)
        return filename

    def print_receipt(self, pdf_filename):
        """چاپ فیش روی پرینتر (سایز A5)"""
        try:
            if platform.system() == 'Windows':
                # Windows
                import win32print
                import win32api
                
                printer_name = win32print.GetDefaultPrinter()
                win32api.ShellExecute(0, "print", pdf_filename, 
                                    f'"{printer_name}"', ".", 0)
                return True
            
            elif platform.system() == 'Linux':
                # Linux
                subprocess.run(['lp', '-o', 'media=A5', pdf_filename], check=True)
                return True
            
            elif platform.system() == 'Darwin':
                # macOS
                subprocess.run(['lp', '-o', 'media=A5', pdf_filename], check=True)
                return True
        
        except Exception as e:
            print(f"خطا در چاپ: {e}")
            return False
    
    def generate_and_print(self, data):
        """تولید و چاپ فیش"""
        pdf_file = self.generate_pdf(data)
        return self.print_receipt(pdf_file)
