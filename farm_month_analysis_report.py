#!/usr/bin/env python3
"""
farm_month_analysis_report.py — يولّد تقرير "تحليل الشهر" ويرسله بالإيميل
نفس منطق صفحة "تحليل الشهر" بالتطبيق (buildMonthAnalysisData / buildNaqdaWamdBalances /
تصنيف المصاريف e.maClass) — راجع CLAUDE.md قسم "🧮 صفحة تحليل الشهر" قبل أي تعديل.
البيانات من: farm_data.json في الريبو (احتياط: JSONBin)

ملاحظة: DEBTS و EXP الكاملتان مرفوعتان بالكامل عبر _getAllData() في التطبيق (منذ v6_29)،
لذا لا حاجة لأي تعديل على آلية المزامنة الحالية.

DRY_RUN=1 (متغيّر بيئة) يطبع التقرير بدل إرساله بالإيميل — للاختبار فقط.
"""

import os, sys, json, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request, urllib.error

# ══ إعدادات ══
FARM_DATA_URL = "https://raw.githubusercontent.com/hadi907/ftm8-monitor/main/farm_data.json"
JSONBIN_URL   = os.environ.get("JSONBIN_BIN_URL", "https://api.jsonbin.io/v3/b/6a0c5f4b6877513b27993aed")
JSONBIN_KEY   = os.environ.get("JSONBIN_API_KEY", "")
GH_TOKEN      = os.environ.get("GH_TOKEN", "")
EMAIL_FROM    = os.environ.get("EMAIL_FROM", "hishak888@gmail.com")
EMAIL_PASS    = os.environ.get("EMAIL_PASS", "")
EMAIL_TO      = "hadi@ftm8.com"
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
DRY_RUN       = os.environ.get("DRY_RUN", "") == "1"

sel_month = sys.argv[1].strip() if len(sys.argv) > 1 else ""

AR_MONTHS = ["","يناير","فبراير","مارس","أبريل","مايو","يونيو",
             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]

def month_label(ym):
    try:
        p = ym.split("-")
        return AR_MONTHS[int(p[1])] + " " + p[0]
    except Exception:
        return ym

def fmt(v):
    try:
        return f"{float(v):.3f}"
    except Exception:
        return "0.000"

def in_scope(d):
    if not d:
        return False
    return d[:7] == sel_month if sel_month else True

def fetch_jsonbin():
    """يجلب البيانات من JSONBin مباشرة"""
    try:
        url = JSONBIN_URL.rstrip('/') + '/latest'
        req = urllib.request.Request(url, headers={"X-Master-Key": JSONBIN_KEY})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get('record', data)
    except Exception as e:
        print(f"⚠️ JSONBin فشل: {e}")
        return None

# ══ جلب البيانات ══
raw = None
print("📡 جلب البيانات من farm_data.json...")
try:
    req0 = urllib.request.Request(FARM_DATA_URL)
    if GH_TOKEN:
        req0.add_header("Authorization", f"token {GH_TOKEN}")
    with urllib.request.urlopen(req0, timeout=15) as resp:
        raw = json.loads(resp.read().decode())
    print("✅ تم جلب البيانات من farm_data.json")
except Exception as e:
    print(f"⚠️ farm_data.json فشل: {e}")

if raw is None and JSONBIN_KEY:
    print("📡 محاولة JSONBin...")
    raw = fetch_jsonbin()
    if raw:
        print("✅ تم جلب البيانات من JSONBin")

if raw is None:
    print("❌ فشل جلب البيانات من كل المصادر")
    sys.exit(1)

sales = raw.get("SALES", raw.get("ps3_sales", []))
exps  = raw.get("EXP",   raw.get("ps3_exp",   []))
debts = raw.get("DEBTS", raw.get("ps3_debts", []))

print(f"📊 مبيعات: {len(sales)} | مصروفات: {len(exps)} | ديون: {len(debts)}")

# ── إذا EXP أو DEBTS فارغة بـ farm_data.json (تأخر مزامنة الساعة)، اجلبها من JSONBin مباشرة ──
if (not exps or not debts) and JSONBIN_KEY:
    print("⚠️ بيانات ناقصة — جلب مباشر من JSONBin...")
    jb = fetch_jsonbin()
    if jb:
        if not exps:
            exps = jb.get("ps3_exp", jb.get("EXP", []))
            print(f"✅ تم جلب {len(exps)} مصروف من JSONBin مباشرة")
        if not debts:
            debts = jb.get("ps3_debts", jb.get("DEBTS", []))
            print(f"✅ تم جلب {len(debts)} دين من JSONBin مباشرة")

print(f"✅ مبيعات: {len(sales)} | مصروفات: {len(exps)} | ديون: {len(debts)}")

# ══ تحليل الشهر لكل عميل (نفس منطق buildMonthAnalysisData بالتطبيق) ══
by_client = {}
def ensure(n):
    if n not in by_client:
        by_client[n] = {"name": n, "sellCash": 0.0, "sellWamd": 0.0, "sellCard": 0.0,
                         "paidCash": 0.0, "paidWamd": 0.0, "paidOther": 0.0, "remaining": 0.0}
    return by_client[n]

for s in sales:
    d = s.get("date", "")
    if not d:
        continue
    if sel_month and not d.startswith(sel_month):
        continue
    n = (s.get("client", "") or "").strip()
    if not n:
        continue
    c = ensure(n)
    pay = s.get("payment", "نقد")
    amt = float(s.get("total", 0) or 0)
    if pay in ("نقد", "نقدا"):
        c["sellCash"] += amt
    elif pay in ("تحويل", "ومض"):
        c["sellWamd"] += amt
    elif pay == "بطاقة":
        c["sellCard"] += amt
    else:
        c["sellCash"] += amt

for d_ in debts:
    n = (d_.get("client", "") or "").strip()
    if not n:
        continue
    c = ensure(n)
    c["remaining"] += float(d_.get("remaining", 0) or 0)  # الرصيد الحالي دائماً — بدون فلتر شهر
    payments = d_.get("payments") or []
    sum_logged = 0.0
    for p in payments:
        amt = float(p.get("amount", 0) or 0)
        sum_logged += amt
        pdate = p.get("date", "") or ""
        if sel_month and not pdate.startswith(sel_month):
            continue
        method = (p.get("method", "") or "").strip()
        if "نقد" in method:
            c["paidCash"] += amt
        elif ("ومض" in method) or ("تحويل" in method) or ("بنك" in method):
            c["paidWamd"] += amt
        else:
            c["paidOther"] += amt
    legacy = float(d_.get("paid", 0) or 0) - sum_logged
    if legacy > 0.0005:
        leg_date = d_.get("lastPayDate") or d_.get("date") or ""
        if not sel_month or leg_date.startswith(sel_month):
            c["paidOther"] += legacy

rows = list(by_client.values())
if sel_month:
    rows = [c for c in rows if (c["sellCash"] + c["sellWamd"] + c["sellCard"] +
                                 c["paidCash"] + c["paidWamd"] + c["paidOther"]) > 0.0005]
rows.sort(key=lambda c: c["name"])

t_sell_cash  = sum(c["sellCash"]  for c in rows)
t_sell_wamd  = sum(c["sellWamd"]  for c in rows)
t_sell_card  = sum(c["sellCard"]  for c in rows)
t_paid_cash  = sum(c["paidCash"]  for c in rows)
t_paid_wamd  = sum(c["paidWamd"]  for c in rows)
t_paid_other = sum(c["paidOther"] for c in rows)
t_remain     = sum(c["remaining"] for c in rows)

# ══ صندوقا "نقدا" و"ومض" (نفس منطق buildNaqdaWamdBalances بالتطبيق) ══
cash_in = wamd_in = cash_out = wamd_out = 0.0
for s in sales:
    if not in_scope(s.get("date", "")):
        continue
    amt = float(s.get("total", 0) or 0)
    pay = s.get("payment", "")
    if pay in ("نقد", "نقدا"):
        cash_in += amt
    elif pay in ("تحويل", "ومض"):
        wamd_in += amt

for e in exps:
    if not in_scope(e.get("date", "")):
        continue
    amt = float(e.get("paid", 0) or 0)
    if amt <= 0:
        continue
    eff = e.get("maClass") or e.get("source") or ""
    if eff == "نقدا":
        cash_out += amt
    elif eff == "ومض":
        wamd_out += amt

cash_bal = cash_in - cash_out
wamd_bal = wamd_in - wamd_out
kpi_remaining_total = cash_bal + wamd_bal  # "إجمالي المتبقي حالياً" = نفس منطق الشاشة (وليس دين العملاء)

# ══ تصنيف المصاريف (نفس منطق buildMaClassRows / renderMaClassSummary بالتطبيق) ══
class_rows = [e for e in exps if e.get("date") and in_scope(e.get("date", ""))]
class_rows.sort(key=lambda e: e.get("date", ""))

class_totals = {}
unclassified = 0.0
for e in class_rows:
    cls = e.get("maClass") or ""
    amt = float(e.get("amount", 0) or 0)
    if not cls:
        unclassified += amt
    else:
        class_totals[cls] = class_totals.get(cls, 0.0) + amt

# ══ بناء HTML ══
today_str  = datetime.now().strftime("%A، %d %B %Y")
period_str = month_label(sel_month) if sel_month else "كل الفترات"

html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>تحليل الشهر — {period_str}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Tajawal',Arial,sans-serif;direction:rtl;background:#f5f5f5;font-size:9pt;color:#222}}
.wrap{{max-width:900px;margin:0 auto;background:#fff;box-shadow:0 2px 20px rgba(0,0,0,.12)}}
.header{{background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;padding:18px 24px;text-align:center}}
.header h1{{font-size:20pt;font-weight:900;margin-bottom:4px}}
.header h2{{font-size:10pt;font-weight:400;opacity:.85}}
.sub{{background:#e8f5e9;padding:8px 20px;text-align:center;font-size:9pt;color:#1b5e20;font-weight:700;border-bottom:2px solid #1b5e20}}
.kgrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 20px}}
.kpi{{border-radius:8px;padding:12px 14px;color:#fff}}
.kpi .v{{font-size:1.35rem;font-weight:900;direction:ltr}}
.kpi .l{{font-size:0.72rem;opacity:.9;margin-top:2px}}
.kg{{background:linear-gradient(135deg,#1b5e20,#2e7d32)}}
.kb{{background:linear-gradient(135deg,#0d47a1,#1565c0)}}
.kt{{background:linear-gradient(135deg,#00695c,#00897b)}}
.ko{{background:linear-gradient(135deg,#e65100,#f57c00)}}
.pools{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0 20px 16px}}
.pool{{border-radius:8px;padding:14px 18px;color:#fff}}
.pool .t{{font-size:0.82rem;opacity:.85}}
.pool .v{{font-size:1.6rem;font-weight:900;direction:ltr;margin-top:4px}}
.pool .s{{font-size:0.7rem;opacity:.8;margin-top:4px}}
.section-title{{margin:20px 20px 8px;font-size:10pt;font-weight:800;color:#1b5e20;padding-bottom:6px;border-bottom:2px solid #e8f5e9}}
table{{width:100%;border-collapse:collapse;font-size:8.5pt}}
thead tr{{background:#1b5e20;color:#fff}}
thead th{{padding:8px 8px;text-align:right;border:1px solid #0d3d12}}
tbody tr:nth-child(even){{background:#f1f8f1}}
tbody td{{padding:6px 8px;border:1px solid #ddd;vertical-align:top}}
.grand{{background:#1b5e20;color:#fff;font-weight:900}}
.grand td{{padding:9px 8px;border:1px solid #0d3d12}}
.cls-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 20px}}
.footer{{background:#0a2e0a;color:#a5d6a7;padding:8px 20px;text-align:center;font-size:8pt;margin-top:16px}}
@media(max-width:600px){{.kgrid{{grid-template-columns:1fr 1fr}}.pools{{grid-template-columns:1fr}}.cls-grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="wrap">
<div class="header">
  <h1>🌿 مزرعة هادي اسحاق</h1>
  <h2>MONTH ANALYSIS — تحليل الشهر — {period_str}</h2>
</div>
<div class="sub">📅 {today_str}</div>

<div class="kgrid">
  <div class="kpi kg"><div class="v">{fmt(t_sell_cash)}</div><div class="l">💵 بيع نقداً</div></div>
  <div class="kpi kb"><div class="v">{fmt(t_sell_wamd)}</div><div class="l">🏦 بيع ومض</div></div>
  <div class="kpi kt"><div class="v">{fmt(t_sell_card)}</div><div class="l">💳 بيع بطاقة</div></div>
  <div class="kpi kg"><div class="v">{fmt(t_paid_cash)}</div><div class="l">💵 صرف (تحصيل) نقداً</div></div>
  <div class="kpi kb"><div class="v">{fmt(t_paid_wamd)}</div><div class="l">🏦 صرف (تحصيل) ومض</div></div>
  <div class="kpi ko"><div class="v">{fmt(kpi_remaining_total)}</div><div class="l">⏳ إجمالي المتبقي حالياً</div></div>
</div>

<div class="pools">
  <div class="pool" style="background:linear-gradient(135deg,#1b5e20,#2e7d32)">
    <div class="t">💵 رصيد نقدا (كاش باليد)</div>
    <div class="v">{fmt(cash_bal)}</div>
    <div class="s">بيع نقداً {fmt(cash_in)} − مصروفات نقدا {fmt(cash_out)}</div>
  </div>
  <div class="pool" style="background:linear-gradient(135deg,#0d47a1,#1565c0)">
    <div class="t">🏦 رصيد ومض (الحساب البنكي)</div>
    <div class="v">{fmt(wamd_bal)}</div>
    <div class="s">بيع ومض {fmt(wamd_in)} − مصروفات ومض {fmt(wamd_out)}</div>
  </div>
</div>

<div class="section-title">👤 تفصيل حسب العميل</div>
<div style="overflow-x:auto;padding:0 20px">
<table>
<thead><tr>
<th>#</th><th>العميل</th><th>بيع نقدا</th><th>بيع ومض</th><th>بيع بطاقة</th>
<th>صرف نقدا</th><th>صرف ومض</th><th>صرف غير محدد</th><th>المتبقي حالياً</th>
</tr></thead><tbody>"""

if not rows:
    html += '<tr><td colspan="9" style="text-align:center;padding:16px;color:#888">لا توجد عمليات عملاء بهذه الفترة</td></tr>'
else:
    for i, c in enumerate(rows):
        rc = '#b71c1c' if c["remaining"] > 0 else '#1b5e20'
        html += (
            f'<tr><td style="text-align:center;color:#888">{i+1}</td>'
            f'<td style="font-weight:700">{c["name"]}</td>'
            f'<td style="direction:ltr;text-align:center">{fmt(c["sellCash"]) if c["sellCash"]>0 else "—"}</td>'
            f'<td style="direction:ltr;text-align:center">{fmt(c["sellWamd"]) if c["sellWamd"]>0 else "—"}</td>'
            f'<td style="direction:ltr;text-align:center">{fmt(c["sellCard"]) if c["sellCard"]>0 else "—"}</td>'
            f'<td style="direction:ltr;text-align:center;color:#1b5e20">{fmt(c["paidCash"]) if c["paidCash"]>0 else "—"}</td>'
            f'<td style="direction:ltr;text-align:center;color:#1b5e20">{fmt(c["paidWamd"]) if c["paidWamd"]>0 else "—"}</td>'
            f'<td style="direction:ltr;text-align:center;color:#888">{fmt(c["paidOther"]) if c["paidOther"]>0 else "—"}</td>'
            f'<td style="direction:ltr;text-align:center;font-weight:800;color:{rc}">{fmt(c["remaining"])}</td></tr>'
        )

html += (
    f'</tbody><tfoot><tr class="grand">'
    f'<td colspan="2" style="text-align:right">الإجمالي</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_sell_cash)}</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_sell_wamd)}</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_sell_card)}</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_paid_cash)}</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_paid_wamd)}</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_paid_other)}</td>'
    f'<td style="text-align:center;direction:ltr">{fmt(t_remain)}</td>'
    f'</tr></tfoot></table></div>'
)

# ── تصنيف المصاريف ──
html += '<div class="section-title">🏷️ تصنيف المصاريف</div><div class="cls-grid">'
html += f'<div class="kpi kg"><div class="v">{fmt(class_totals.get("نقدا",0))}</div><div class="l">💵 مصروفات نقدا</div></div>'
html += f'<div class="kpi kb"><div class="v">{fmt(class_totals.get("ومض",0))}</div><div class="l">🏦 مصروفات ومض</div></div>'
for k in sorted(k for k in class_totals if k not in ("نقدا", "ومض")):
    html += f'<div class="kpi kt"><div class="v">{fmt(class_totals[k])}</div><div class="l">👤 مصروفات {k}</div></div>'
html += f'<div class="kpi ko"><div class="v">{fmt(unclassified)}</div><div class="l">❔ مصروفات غير مصنّف</div></div>'
html += '</div>'

html += '<div style="overflow-x:auto;padding:0 20px 10px"><table><thead><tr><th>التاريخ</th><th>البيان</th><th>المبلغ (دك)</th><th>التصنيف</th></tr></thead><tbody>'
if not class_rows:
    html += '<tr><td colspan="4" style="text-align:center;padding:16px;color:#888">لا توجد مصاريف بهذه الفترة</td></tr>'
else:
    for e in class_rows:
        desc = e.get("desc", "") or ""
        etype = e.get("type", "") or ""
        label = etype + (f" — {desc}" if desc else "")
        cls = e.get("maClass") or ""
        cls_disp = ("💵 " + cls) if cls == "نقدا" else ("🏦 " + cls) if cls == "ومض" else (f"👤 {cls}" if cls else '<span style="color:#c62828">❔ غير مصنّف</span>')
        html += f'<tr><td>{e.get("date","")}</td><td>{label}</td><td style="direction:ltr;text-align:center;font-weight:700">{fmt(e.get("amount",0))}</td><td>{cls_disp}</td></tr>'
html += '</tbody></table></div>'

html += f'<div class="footer">🌿 مزرعة هادي اسحاق — تحليل الشهر — {today_str}</div></div></body></html>'

# ══ إرسال الإيميل ══
subject = f"🧮 تحليل الشهر — {period_str} | مزرعة هادي اسحاق"

if DRY_RUN:
    print(f"🧪 DRY_RUN — لن يُرسل إيميل. العنوان: {subject}")
    print(f"   عملاء: {len(rows)} | رصيد نقدا: {fmt(cash_bal)} | رصيد ومض: {fmt(wamd_bal)}")
    with open("month_analysis_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("   ✅ تم حفظ معاينة HTML في month_analysis_preview.html")
    sys.exit(0)

print(f"📧 إرسال تقرير تحليل الشهر إلى {EMAIL_TO}...")
msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = EMAIL_FROM
msg["To"]      = EMAIL_TO
msg.attach(MIMEText(html, "html", "utf-8"))

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo(); server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_bytes())
    print(f"✅ تم إرسال تقرير تحليل الشهر! ({len(rows)} عميل, {len(class_rows)} مصروف)")
except Exception as e:
    print(f"❌ فشل إرسال الإيميل: {e}")
    sys.exit(1)
