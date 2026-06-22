#!/usr/bin/env python3
"""
farm_report.py — يولّد التقرير الإداري ويرسله بالإيميل
البيانات من: farm_data.json في الريبو (احتياط: JSONBin)
"""

import os, sys, json, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request, urllib.error

# ══ إعدادات ══
FARM_DATA_URL = "https://raw.githubusercontent.com/hadi907/ftm8-monitor/main/farm_data.json"
JSONBIN_URL   = "https://api.jsonbin.io/v3/b/6a0c5f4b6877513b27993aed"
JSONBIN_KEY   = os.environ.get("JSONBIN_API_KEY", "")
EMAIL_FROM    = os.environ.get("EMAIL_FROM", "hishak888@gmail.com")
EMAIL_PASS    = os.environ.get("EMAIL_PASS", "")
EMAIL_TO      = "hadi@ftm8.com"
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT   = 587

sel_month = sys.argv[1].strip() if len(sys.argv) > 1 else ""

AR_MONTHS = ["","يناير","فبراير","مارس","أبريل","مايو","يونيو",
             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]

def month_label(ym):
    try:
        p = ym.split("-")
        return AR_MONTHS[int(p[1])] + " " + p[0]
    except:
        return ym

def fmt(v):
    try:
        return f"{float(v):.3f}"
    except:
        return "0.000"

def fetch_jsonbin():
    """يجلب البيانات من JSONBin مباشرة"""
    try:
        req = urllib.request.Request(
            JSONBIN_URL,
            headers={"X-Master-Key": JSONBIN_KEY, "X-Bin-Meta": "false"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"⚠️ JSONBin فشل: {e}")
        return None

# ══ جلب البيانات ══
raw = None

# أولاً: farm_data.json
print("📡 جلب البيانات من farm_data.json...")
try:
    req0 = urllib.request.Request(FARM_DATA_URL)
    with urllib.request.urlopen(req0, timeout=15) as resp:
        raw = json.loads(resp.read().decode())
    print(f"✅ تم جلب البيانات من farm_data.json")
except Exception as e:
    print(f"⚠️ farm_data.json فشل: {e}")

# ثانياً: JSONBin كاحتياط كامل
if raw is None and JSONBIN_KEY:
    print("📡 محاولة JSONBin...")
    raw = fetch_jsonbin()
    if raw:
        print("✅ تم جلب البيانات من JSONBin")

if raw is None:
    print("❌ فشل جلب البيانات من كل المصادر")
    sys.exit(1)

# ══ استخراج البيانات ══
sales   = raw.get("SALES", raw.get("ps3_sales", []))
exps    = raw.get("EXP",   raw.get("ps3_exp",   []))
cash    = raw.get("CASH",  raw.get("ps3_cash",   []))

print(f"📊 مبيعات: {len(sales)} | مصروفات: {len(exps)} | كاش: {len(cash)}")

# ── إذا EXP فارغ في farm_data.json، اجلبه مباشرة من JSONBin ──
if not exps and JSONBIN_KEY:
    print("⚠️ EXP فارغ — جلب مباشر من JSONBin...")
    jb = fetch_jsonbin()
    if jb:
        exps = jb.get("ps3_exp", jb.get("EXP", []))
        print(f"✅ تم جلب {len(exps)} مصروف من JSONBin مباشرة")

print(f"✅ مبيعات: {len(sales)} | مصروفات: {len(exps)} | كاش: {len(cash)}")

# ══ بناء الصفوف ══
all_rows = []

for s in sales:
    d = s.get("date","")
    if not d: continue
    if sel_month and not d.startswith(sel_month): continue
    client  = s.get("client","") or s.get("customer","")
    product = s.get("product","") or s.get("name","")
    method  = s.get("paymentMethod","") or s.get("payment","نقد")
    total   = float(s.get("total",0) or 0)
    inv     = s.get("invNum","") or "—"
    detail  = f"مبيعة: {product}"
    if client: detail += f" | {client}"
    all_rows.append({"date":d,"ref":inv,"detail":detail,"exp":0,"income":total,"notes":method,"is_partner":False})

for e in exps:
    d = e.get("date","")
    if not d: continue
    if sel_month and not d.startswith(sel_month): continue
    is_partner = (e.get("source","") == "شريك")
    amt      = float(e.get("amount",0) or 0)
    etype    = e.get("type","مصروف")
    desc     = e.get("desc","") or ""
    paid_by  = e.get("paidBy","") or ""
    inv_ref  = e.get("invRef","") or e.get("id","")
    detail   = f"مصروف: {desc or etype}"
    if is_partner:
        detail += f" | 👤 {paid_by}" if paid_by else " | 👥 مصروف شريك"
    else:
        detail += " | 👜 محفظة"
    all_rows.append({"date":d,"ref":str(inv_ref)[:10],"detail":detail,
                     "exp":0 if is_partner else amt,
                     "income":0,"notes":etype,"is_partner":is_partner,"partner_amt":amt if is_partner else 0})

for x in cash:
    if x.get("autoFrom") in ("sale","expense"): continue
    d = x.get("date","")
    if not d: continue
    if sel_month and not d.startswith(sel_month): continue
    amt    = float(x.get("amount",0) or 0)
    xtype  = x.get("type","")
    notes  = x.get("notes","") or x.get("ref","")
    detail = f"{notes} | 👜 محفظة"
    exp_val = amt if xtype == "صادر" else 0
    inc_val = amt if xtype == "وارد" and not x.get("isDelivery") else 0
    all_rows.append({"date":d,"ref":x.get("ref","—"),"detail":detail,
                     "exp":exp_val,"income":inc_val,"notes":x.get("payment",""),"is_partner":False})

all_rows.sort(key=lambda r: r["date"])

tot_inc = sum(r["income"] for r in all_rows)
tot_exp = sum(r["exp"] for r in all_rows)
balance_final = tot_inc - tot_exp

months_data = {}
for r in all_rows:
    m = r["date"][:7]
    if not m: continue
    if m not in months_data: months_data[m] = {"income":0,"exp":0}
    months_data[m]["income"] += r["income"]
    months_data[m]["exp"]    += r["exp"]

months_surplus = {}
for r in all_rows:
    m = r["date"][:7]
    if not m: continue
    if m not in months_surplus: months_surplus[m] = {"income":0,"exp":0}
    months_surplus[m]["income"] += r["income"]
    if not r["is_partner"]: months_surplus[m]["exp"] += r["exp"]

month_keys = sorted(months_data.keys())

partner_debts = {}
for e in exps:
    pb = e.get("paidBy","")
    if not pb: continue
    amt      = float(e.get("amount",0) or 0)
    settled  = float(e.get("settledAmt",0) or 0)
    if pb not in partner_debts: partner_debts[pb] = {"paid":0,"settled":0}
    partner_debts[pb]["paid"]    += amt
    partner_debts[pb]["settled"] += settled

# ══ بناء HTML ══
today_str  = datetime.now().strftime("%A، %d %B %Y")
period_str = month_label(sel_month) if sel_month else "كل الفترات"
bal_color  = "#1b5e20" if balance_final >= 0 else "#b71c1c"
bal_str    = fmt(abs(balance_final))
if balance_final < 0: bal_str = "-" + bal_str

html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>التقرير الإداري — {period_str}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Tajawal',Arial,sans-serif;direction:rtl;background:#f5f5f5;font-size:9pt;color:#222}}
.wrap{{max-width:900px;margin:0 auto;background:#fff;box-shadow:0 2px 20px rgba(0,0,0,.12)}}
.header{{background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;padding:18px 24px;text-align:center}}
.header h1{{font-size:20pt;font-weight:900;margin-bottom:4px}}
.header h2{{font-size:10pt;font-weight:400;opacity:.85}}
.sub{{background:#e8f5e9;padding:8px 20px;display:flex;justify-content:space-between;align-items:center;font-size:9pt;color:#1b5e20;font-weight:700;border-bottom:2px solid #1b5e20;flex-wrap:wrap;gap:6px}}
table{{width:100%;border-collapse:collapse;font-size:8.5pt}}
thead tr{{background:#1b5e20;color:#fff}}
thead th{{padding:8px 10px;text-align:right;border:1px solid #0d3d12}}
tbody tr:nth-child(even){{background:#f1f8f1}}
tbody td{{padding:6px 10px;border:1px solid #ddd;vertical-align:top}}
.grand{{background:#1b5e20;color:#fff;font-weight:900}}
.grand td{{padding:9px 10px;border:1px solid #0d3d12}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 20px}}
.box{{border-radius:8px;overflow:hidden;border:1px solid #ccc}}
.stitle{{padding:8px 14px;font-weight:700;font-size:9pt;color:#fff}}
.partner-box{{margin:16px 20px;border-radius:8px;overflow:hidden;border:2px solid #0d47a1}}
.partner-cards{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:14px;background:#e8eaf6}}
.pcard{{border:1.5px solid #bbdefb;border-top:4px solid #0d47a1;border-radius:8px;padding:14px;background:#fff}}
.footer{{background:#0a2e0a;color:#a5d6a7;padding:8px 20px;text-align:center;font-size:8pt}}
@media(max-width:600px){{.grid2{{grid-template-columns:1fr}}.partner-cards{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">
<div class="header">
  <h1>🌿 مزرعة هادي اسحاق</h1>
  <h2>ADMINISTRATIVE REPORT — التقرير الإداري — {period_str}</h2>
</div>
<div class="sub">
  <span>📅 {today_str}</span>
  <span>💰 إيرادات: {fmt(tot_inc)} | 💸 مصروفات: {fmt(tot_exp)} | الرصيد: <strong style="color:{bal_color}">{bal_str} دك</strong></span>
</div>
<div style="overflow-x:auto;padding:0 20px">
<table>
<thead><tr>
<th>#</th><th>التاريخ</th><th>المرجع</th><th>التفاصيل</th>
<th style="color:#ff8a80">مصروفات (دك)</th>
<th style="color:#b9f6ca">إيراد (دك)</th>
<th>المتبقي (دك)</th><th>ملاحظات</th>
</tr></thead><tbody>"""

running = 0
for i, r in enumerate(all_rows):
    running += r["income"] - r["exp"]
    bg = '#e3f2fd' if r["is_partner"] else ('' if i%2==0 else '#f1f8f1')
    dc = '#1565c0' if r["is_partner"] else 'inherit'
    rc = '#1b5e20' if running >= 0 else '#b71c1c'
    rs = fmt(abs(running)); rs = ("-"+rs) if running < 0 else rs
    es = fmt(r["exp"]) if r["exp"] > 0 else "—"
    is_ = fmt(r["income"]) if r["income"] > 0 else "—"
    st = f'style="background:{bg}"' if bg else ""
    html += f'<tr {st}><td style="text-align:center;color:#888">{i+1}</td><td>{r["date"]}</td><td style="font-weight:700;color:#1b5e20">{r["ref"]}</td><td style="color:{dc}">{r["detail"]}</td><td style="text-align:center;color:#b71c1c;font-weight:700;direction:ltr">{es}</td><td style="text-align:center;color:#1b5e20;font-weight:700;direction:ltr">{is_}</td><td style="text-align:center;font-weight:800;color:{rc};direction:ltr">{rs}</td><td style="color:#888;font-size:8pt">{r["notes"]}</td></tr>'

fc = '#b9f6ca' if balance_final >= 0 else '#ff8a80'
html += f'</tbody><tfoot><tr class="grand"><td colspan="4" style="text-align:right">الإجمالي الكلي</td><td style="text-align:center;direction:ltr">{fmt(tot_exp)}</td><td style="text-align:center;direction:ltr">{fmt(tot_inc)}</td><td style="text-align:center;direction:ltr;color:{fc}">{bal_str}</td><td></td></tr></tfoot></table></div>'

if month_keys:
    g_inc = sum(months_data[m]["income"] for m in month_keys)
    g_exp = sum(months_data[m]["exp"] for m in month_keys)
    g_net = g_inc - g_exp
    gns = fmt(abs(g_net)); gns = ("-"+gns) if g_net < 0 else gns
    gnc = '#b9f6ca' if g_net >= 0 else '#ff8a80'
    html += '<div class="grid2">'
    html += '<div class="box"><div class="stitle" style="background:linear-gradient(135deg,#37474f,#546e7a)">📅 الملخص الشهري</div><table><thead><tr style="background:#37474f;color:#fff"><th>الشهر</th><th style="color:#b9f6ca">المدخول</th><th style="color:#ff8a80">المصروف</th><th>الصافي</th></tr></thead><tbody>'
    for i,m in enumerate(month_keys):
        d=months_data[m]; net=d["income"]-d["exp"]
        nc='#1b5e20' if net>=0 else '#c62828'
        ns=fmt(abs(net)); ns=("-"+ns) if net<0 else ns
        bg='#f8fffe' if i%2==0 else '#fff'
        html+=f'<tr style="background:{bg}"><td style="font-weight:700;color:#37474f">{month_label(m)}</td><td style="text-align:center;color:#1b5e20;font-weight:700;direction:ltr">{fmt(d["income"])}</td><td style="text-align:center;color:#b71c1c;font-weight:700;direction:ltr">{fmt(d["exp"]) if d["exp"]>0 else "—"}</td><td style="text-align:center;font-weight:900;color:{nc};direction:ltr">{ns}</td></tr>'
    html+=f'</tbody><tfoot><tr style="background:#263238;color:#fff;font-weight:900"><td>الإجمالي</td><td style="text-align:center;color:#b9f6ca;direction:ltr">{fmt(g_inc)}</td><td style="text-align:center;color:#ff8a80;direction:ltr">{fmt(g_exp) if g_exp>0 else "—"}</td><td style="text-align:center;color:{gnc};direction:ltr">{gns}</td></tr></tfoot></table></div>'

    ts=0
    html+='<div class="box"><div class="stitle" style="background:linear-gradient(135deg,#1565c0,#1976d2)">💰 فائض الأشهر</div><table><thead><tr style="background:#1565c0;color:#fff"><th>الشهر</th><th style="color:#b9f6ca">إيراد / مصروف</th><th>الفائض</th></tr></thead><tbody>'
    for i,m in enumerate(month_keys):
        d=months_surplus.get(m,{"income":0,"exp":0}); s=d["income"]-d["exp"]; ts+=s
        sc='#1b5e20' if s>=0 else '#c62828'; icon='📈' if s>=0 else '📉'
        ss=fmt(abs(s)); ss=("-"+ss) if s<0 else ss
        bg='#f0f4ff' if i%2==0 else '#fff'
        html+=f'<tr style="background:{bg}"><td style="font-weight:700;color:#37474f">{month_label(m)}</td><td style="text-align:center;font-size:8pt;color:#555;direction:ltr"><span style="display:block;color:#1b5e20">📥 {fmt(d["income"])}</span><span style="display:block;color:#b71c1c">📤 {fmt(d["exp"])}</span></td><td style="text-align:center;font-weight:900;color:{sc};direction:ltr">{icon} {ss}</td></tr>'
    tsc='#b9f6ca' if ts>=0 else '#ff8a80'; tss=fmt(abs(ts)); tss=("-"+tss) if ts<0 else tss
    html+=f'</tbody><tfoot><tr style="background:#263238;color:#fff;font-weight:900"><td>الإجمالي</td><td style="text-align:center;opacity:.7">—</td><td style="text-align:center;color:{tsc};direction:ltr">{tss}</td></tr></tfoot></table></div>'
    html+='</div>'

if partner_debts:
    html+='<div class="partner-box"><div class="stitle" style="background:linear-gradient(135deg,#0d47a1,#1565c0);font-size:10pt">👥 ملخص مستحقات الشركاء</div><div class="partner-cards">'
    for name,p in partner_debts.items():
        rem=p["paid"]-p["settled"]; rc2='#e65100' if rem>0 else '#2e7d32'
        html+=f'<div class="pcard"><div style="font-weight:900;color:#0d47a1;font-size:11pt;margin-bottom:10px">👤 {name}</div><div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #e3f2fd;font-size:9pt"><span style="color:#555">دفع من ماله</span><strong style="color:#c62828;direction:ltr">{fmt(p["paid"])} دك</strong></div><div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #e3f2fd;font-size:9pt"><span style="color:#555">تم تسديده</span><strong style="color:#1b5e20;direction:ltr">{fmt(p["settled"])} دك</strong></div><div style="display:flex;justify-content:space-between;padding:8px 0 4px;border-top:2px solid #bbdefb;margin-top:6px"><span style="font-weight:800">مستحق له</span><strong style="color:{rc2};font-size:11pt;direction:ltr">{fmt(rem)} دك</strong></div></div>'
    html+='</div></div>'

html+=f'<div class="footer">🌿 مزرعة هادي اسحاق — التقرير الإداري — {today_str}</div></div></body></html>'

# ══ إرسال الإيميل ══
print(f"📧 إرسال التقرير إلى {EMAIL_TO}...")
subject = f"📊 التقرير الإداري — {period_str} | مزرعة هادي اسحاق"
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
    print(f"✅ تم إرسال التقرير! ({len(all_rows)} صف)")
except Exception as e:
    print(f"❌ فشل إرسال الإيميل: {e}")
    sys.exit(1)
