#!/usr/bin/env python3
# farm_compare.py — مقارنة بيانات التطبيق مع Excel وإرسال تقرير يومي
# الإصدار: v2 — Hotmail SMTP

import json
import os
import smtplib
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ══ الإعدادات ══
GITHUB_RAW_URL = "https://raw.githubusercontent.com/hadi907/ftm8-monitor/main/farm_data.json"
XLSX_PATH      = "Farm_Account.xlsx"
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "hadiishak@hotmail.com")
EMAIL_PASS     = os.environ.get("EMAIL_PASS", "")
EMAIL_TO       = "hadi@ftm8.com"
SMTP_SERVER    = "smtp.mail.yahoo.com"
SMTP_PORT      = 587

# ══ جلب بيانات التطبيق من GitHub Raw ══
def fetch_app_data():
    try:
        with urllib.request.urlopen(GITHUB_RAW_URL, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception as e:
        print(f"❌ خطأ في جلب farm_data.json: {e}")
        return None

# ══ قراءة بيانات Excel ══
def read_xlsx():
    try:
        import openpyxl
        wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
        ws = wb.active
        rows = []
        headers = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(c).strip() if c else "" for c in row]
            else:
                if any(c is not None for c in row):
                    rows.append(dict(zip(headers, row)))
        return headers, rows
    except Exception as e:
        print(f"❌ خطأ في قراءة Excel: {e}")
        return [], []

# ══ بناء التقرير HTML ══
def build_report(app_data, xlsx_rows, xlsx_headers):
    today = datetime.now().strftime("%Y-%m-%d")
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── إحصائيات التطبيق ──
    sales    = app_data.get("ps3_sales", []) if app_data else []
    expenses = app_data.get("ps3_exp",   []) if app_data else []
    inv      = app_data.get("ps3_inv",   []) if app_data else []

    total_sales = sum(float(s.get("total", 0)) for s in sales)
    total_exp   = sum(float(e.get("amount", 0)) for e in expenses)
    app_profit  = total_sales - total_exp
    inv_count   = len(inv)
    low_stock   = [p for p in inv if float(p.get("remaining", 0)) <= float(p.get("minStock", 5))]
    out_stock   = [p for p in inv if float(p.get("remaining", 0)) <= 0]

    # ── إحصائيات Excel ──
    xlsx_count = len(xlsx_rows)

    # ── حالة المقارنة ──
    app_ok   = app_data is not None
    xlsx_ok  = xlsx_count > 0
    status   = "✅ كلا الملفين متاحان" if (app_ok and xlsx_ok) else "⚠️ تحقق من الملفات"
    status_color = "#2e7d32" if (app_ok and xlsx_ok) else "#e65100"

    # ── بناء HTML ──
    low_rows = ""
    for p in low_stock:
        rem = float(p.get("remaining", 0))
        mn  = float(p.get("minStock", 5))
        color = "#ffebee" if rem <= 0 else "#fff8e1"
        icon  = "🔴" if rem <= 0 else "🟡"
        low_rows += f"""
        <tr style="background:{color}">
          <td>{icon} {p.get('name','—')}</td>
          <td>{p.get('type','—')}</td>
          <td style="text-align:center;font-weight:700">{int(rem)}</td>
          <td style="text-align:center">{int(mn)}</td>
        </tr>"""

    if not low_rows:
        low_rows = '<tr><td colspan="4" style="text-align:center;color:#2e7d32;padding:12px">✅ جميع الأصناف فوق الحد الأدنى</td></tr>'

    xlsx_preview = ""
    for row in xlsx_rows[:10]:
        cells = "".join(f"<td style='padding:5px 8px;border:1px solid #e0e0e0'>{v if v is not None else '—'}</td>" for v in list(row.values())[:6])
        xlsx_preview += f"<tr>{cells}</tr>"

    if not xlsx_preview:
        xlsx_preview = '<tr><td colspan="6" style="text-align:center;color:#e65100;padding:12px">⚠️ لم يتم العثور على بيانات في Excel</td></tr>'

    header_cells = "".join(f"<th style='padding:6px 8px;background:#1b5e20;color:#fff;border:1px solid #388e3c'>{h}</th>" for h in xlsx_headers[:6])

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background:#f5f5f5; margin:0; padding:20px; direction:rtl; }}
  .container {{ max-width:800px; margin:0 auto; background:#fff; border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,.1); overflow:hidden; }}
  .header {{ background:linear-gradient(135deg,#1b5e20,#388e3c); color:#fff; padding:24px 28px; }}
  .header h1 {{ margin:0 0 6px; font-size:1.4rem; }}
  .header p {{ margin:0; opacity:.85; font-size:.9rem; }}
  .status-bar {{ background:{status_color}; color:#fff; padding:10px 28px; font-weight:700; font-size:.95rem; }}
  .section {{ padding:20px 28px; border-bottom:1px solid #f0f0f0; }}
  .section h2 {{ color:#1b5e20; font-size:1rem; margin:0 0 14px; padding-bottom:8px; border-bottom:2px solid #e8f5e9; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:4px; }}
  .kpi {{ background:#f9f9f9; border-radius:8px; padding:14px; text-align:center; border:1px solid #e0e0e0; }}
  .kpi .val {{ font-size:1.4rem; font-weight:800; color:#1b5e20; }}
  .kpi .lbl {{ font-size:.75rem; color:#666; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
  th {{ background:#e8f5e9; color:#1b5e20; padding:8px; text-align:right; border:1px solid #c8e6c9; }}
  td {{ padding:7px 8px; border:1px solid #e0e0e0; }}
  .footer {{ background:#f9f9f9; padding:14px 28px; text-align:center; font-size:.78rem; color:#888; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🌿 مزرعة هادي اسحاق — التقرير اليومي</h1>
    <p>📅 {now} | تقرير تلقائي</p>
  </div>
  <div class="status-bar">{status}</div>

  <div class="section">
    <h2>📊 ملخص التطبيق</h2>
    <div class="kpi-grid">
      <div class="kpi"><div class="val">{total_sales:.3f}</div><div class="lbl">إجمالي المبيعات (د.ك)</div></div>
      <div class="kpi"><div class="val">{total_exp:.3f}</div><div class="lbl">إجمالي المصروفات (د.ك)</div></div>
      <div class="kpi"><div class="val" style="color:{'#2e7d32' if app_profit>=0 else '#c62828'}">{app_profit:.3f}</div><div class="lbl">صافي الربح (د.ك)</div></div>
      <div class="kpi"><div class="val">{len(sales)}</div><div class="lbl">عدد المبيعات</div></div>
      <div class="kpi"><div class="val">{inv_count}</div><div class="lbl">أصناف المخزون</div></div>
      <div class="kpi"><div class="val" style="color:{'#c62828' if out_stock else '#2e7d32'}">{len(out_stock)}</div><div class="lbl">أصناف نافدة</div></div>
    </div>
  </div>

  <div class="section">
    <h2>⚠️ تنبيهات المخزون ({len(low_stock)} صنف)</h2>
    <table>
      <tr><th>الصنف</th><th>النوع</th><th style="text-align:center">المتبقي</th><th style="text-align:center">الحد الأدنى</th></tr>
      {low_rows}
    </table>
  </div>

  <div class="section">
    <h2>📋 بيانات Excel — Farm_Account.xlsx ({xlsx_count} سطر)</h2>
    <table>
      <tr>{header_cells}</tr>
      {xlsx_preview}
    </table>
    {"<p style='color:#888;font-size:.78rem;margin-top:8px'>* يعرض أول 10 صفوف فقط</p>" if xlsx_count > 10 else ""}
  </div>

  <div class="footer">
    تقرير تلقائي — مزرعة هادي اسحاق | {now}<br>
    المُرسَل إلى: {EMAIL_TO}
  </div>
</div>
</body>
</html>"""
    return html

# ══ إرسال الإيميل ══
def send_email(html_content):
    if not EMAIL_PASS:
        print("❌ EMAIL_PASS غير موجود في Secrets")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌿 تقرير مزرعة هادي اسحاق — {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"✅ تم إرسال التقرير إلى {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"❌ خطأ في إرسال الإيميل: {e}")
        return False

# ══ الدالة الرئيسية ══
def main():
    print(f"🌿 farm_compare.py — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"📧 من: {EMAIL_FROM} → إلى: {EMAIL_TO}")
    print(f"🔗 SMTP: {SMTP_SERVER}:{SMTP_PORT}")

    print("📥 جاري جلب بيانات التطبيق...")
    app_data = fetch_app_data()
    if app_data:
        sales_count = len(app_data.get("ps3_sales", []))
        print(f"✅ farm_data.json — {sales_count} مبيعة")
    else:
        print("⚠️ تعذّر جلب farm_data.json")

    print("📊 جاري قراءة Farm_Account.xlsx...")
    xlsx_headers, xlsx_rows = read_xlsx()
    print(f"✅ Excel — {len(xlsx_rows)} سطر")

    print("📝 جاري بناء التقرير...")
    html = build_report(app_data, xlsx_rows, xlsx_headers)

    print("📤 جاري إرسال التقرير...")
    send_email(html)

if __name__ == "__main__":
    main()
