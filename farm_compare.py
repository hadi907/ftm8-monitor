import os, json, requests, openpyxl, smtplib, datetime, re
import pandas as pd

def norm_ref(r):
    if not r: return ''
    r = str(r).upper().replace(' ','').replace('-','')
    r = re.sub(r'^(INV)0+(\d+)$', r'\g<1>\2', r)
    return r

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GITHUB_RAW = 'https://raw.githubusercontent.com/hadi907/ftm8-monitor/main/farm_data.json'
XLSX_PATH  = os.environ.get('XLSX_PATH', 'Farm_Account.xlsx')
EMAIL_FROM = os.environ.get('EMAIL_FROM', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
EMAIL_TO   = os.environ.get('EMAIL_TO', 'hadi@ftm8.com')
TODAY      = datetime.date.today().isoformat()

def load_app():
    try:
        res = requests.get(GITHUB_RAW, timeout=15)
        data = res.json()
        sales = data.get('SALES', [])
        print(f"✅ farm_data.json — {len(sales)} مبيعة")
        return sales
    except Exception as e:
        print(f"❌ خطأ farm_data.json: {e}")
        return []

def load_xlsx():
    rows = []
    try:
        df = pd.read_excel(XLSX_PATH, sheet_name='المحفظة', header=None)
        for _, row in df.iterrows():
            date_v  = row[0]
            ref     = str(row[1] if pd.notna(row[1]) else '').strip()
            desc    = str(row[2] if pd.notna(row[2]) else '').strip()
            credit_v= row[4]
            if not ref or ref in ['0','nan','None'] or pd.isna(date_v):
                continue
            if hasattr(date_v, 'date'):
                date_str = date_v.date().isoformat()
            else:
                continue
            try:
                c = float(credit_v) if pd.notna(credit_v) and str(credit_v).strip() not in ['—','-',''] else 0.0
            except:
                c = 0.0
            if c <= 0:
                continue
            rows.append({'date':date_str,'ref':ref,'ref_norm':norm_ref(ref),'desc':desc,'credit':round(c,3)})
        print(f"✅ XLSX (المحفظة) — {len(rows)} سطر، إجمالي={sum(r['credit'] for r in rows):.3f} دك")
    except Exception as e:
        print(f"❌ خطأ XLSX: {e}")
        import traceback; traceback.print_exc()
    return rows

def compare(app_sales, xlsx_rows):
    app_total   = round(sum(s.get('total', 0) for s in app_sales), 3)
    xlsx_credit = round(sum(r['credit'] for r in xlsx_rows), 3)
    xlsx_by_ref = {}
    for r in xlsx_rows:
        xlsx_by_ref.setdefault(r['ref_norm'], []).append(r)
    app_refs = set()
    for s in app_sales:
        ref = norm_ref(s.get('invNum') or '')
        if ref: app_refs.add(ref)
    diffs = []
    seen  = set()
    for s in app_sales:
        ref  = norm_ref(s.get('invNum') or '')
        amt  = round(s.get('total', 0), 3)
        prod = s.get('product', '')
        date = s.get('date', '')
        if amt <= 0 or not ref: continue
        matches = [r for r in xlsx_by_ref.get(ref, []) if r['credit'] > 0]
        key = f"{ref}|{prod}"
        if key in seen: continue
        seen.add(key)
        if not matches:
            diffs.append({'type':'في التطبيق فقط','ref':ref,'desc':prod,'date':date,'app_val':amt,'xlsx_val':0,'diff':amt})
        else:
            xlsx_amt = round(sum(m['credit'] for m in matches), 3)
            if abs(xlsx_amt - amt) > 0.005:
                diffs.append({'type':'فارق في القيمة','ref':ref,'desc':prod,'date':date,'app_val':amt,'xlsx_val':xlsx_amt,'diff':round(amt-xlsx_amt,3)})
    for ref_norm, rws in xlsx_by_ref.items():
        if ref_norm in app_refs: continue
        for r in rws:
            key = f"{ref_norm}|xlsx"
            if key in seen: continue
            seen.add(key)
            diffs.append({'type':'في XLSX فقط','ref':r['ref'],'desc':r['desc'],'date':r['date'],'app_val':0,'xlsx_val':r['credit'],'diff':-r['credit']})
    return {'app_total':app_total,'xlsx_credit':xlsx_credit,'diff_total':round(app_total-xlsx_credit,3),'diffs':sorted(diffs,key=lambda x:x['date'],reverse=True),'app_count':len(app_sales),'xlsx_count':len(xlsx_rows)}

def build_html(r):
    dc = '#c62828' if abs(r['diff_total']) > 0.01 else '#1b5e20'
    icon = '⚠️' if r['diffs'] else '✅'
    status = f"{len(r['diffs'])} فارق بحاجة مراجعة" if r['diffs'] else "كل البيانات متطابقة"
    rows_html = ''
    if r['diffs']:
        for d in r['diffs']:
            tc = {'في التطبيق فقط':'#e65100','في XLSX فقط':'#1565c0','فارق في القيمة':'#6a1b9a'}.get(d['type'],'#555')
            sign = '+' if d['diff'] > 0 else ''
            rows_html += f'<tr><td style="padding:8px 12px;border-bottom:1px solid #eee">{d["date"]}</td><td style="padding:8px 12px;color:#1565c0;font-weight:700;border-bottom:1px solid #eee">{d["ref"]}</td><td style="padding:8px 12px;border-bottom:1px solid #eee">{d["desc"][:35]}</td><td style="padding:8px 12px;text-align:center;border-bottom:1px solid #eee"><span style="background:{tc}22;color:{tc};padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{d["type"]}</span></td><td style="padding:8px 12px;text-align:center;direction:ltr;border-bottom:1px solid #eee">{d["app_val"]:.3f}</td><td style="padding:8px 12px;text-align:center;direction:ltr;border-bottom:1px solid #eee">{d["xlsx_val"]:.3f}</td><td style="padding:8px 12px;text-align:center;direction:ltr;font-weight:900;color:{dc};border-bottom:1px solid #eee">{sign}{d["diff"]:.3f}</td></tr>'
    else:
        rows_html = '<tr><td colspan="7" style="padding:20px;text-align:center;color:#1b5e20;font-size:16px">✅ لا توجد فوارق</td></tr>'
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Tajawal,Arial;direction:rtl;background:#f5f5f5;padding:20px}}.card{{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #e0e0e0}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}.kpi{{background:#f8fffe;border-radius:8px;padding:14px;text-align:center;border:1px solid #e0e0e0}}.kpi-lbl{{font-size:12px;color:#666;margin-bottom:4px}}.kpi-val{{font-size:20px;font-weight:900;direction:ltr}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{background:#1b5e20;color:#fff;padding:10px 12px;text-align:right}}tr:nth-child(even){{background:#f9f9f9}}</style></head>
<body><div class="card"><div style="display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #1b5e20;padding-bottom:12px;margin-bottom:16px">
<div><h1 style="font-size:18px;color:#1b5e20;font-weight:900">🌿 مزرعة هادي اسحاق</h1><p style="color:#555;font-size:13px">تقرير المقارنة — {TODAY}</p></div>
<div style="background:{'#fff3e0' if r['diffs'] else '#e8f5e9'};padding:10px 20px;border-radius:8px;text-align:center"><div style="font-size:22px">{icon}</div><div style="font-size:12px;font-weight:700;color:{dc}">{status}</div></div></div>
<div class="kpis">
<div class="kpi"><div class="kpi-lbl">مبيعات التطبيق</div><div class="kpi-val" style="color:#1b5e20">{r['app_total']:.3f} دك</div><div style="font-size:11px;color:#999">{r['app_count']} سجل</div></div>
<div class="kpi"><div class="kpi-lbl">مبيعات XLSX</div><div class="kpi-val" style="color:#1565c0">{r['xlsx_credit']:.3f} دك</div><div style="font-size:11px;color:#999">{r['xlsx_count']} سطر</div></div>
<div class="kpi"><div class="kpi-lbl">الفارق</div><div class="kpi-val" style="color:{dc}">{r['diff_total']:+.3f} دك</div></div>
<div class="kpi"><div class="kpi-lbl">الفوارق</div><div class="kpi-val" style="color:{dc}">{len(r['diffs'])}</div></div></div></div>
<div class="card"><h2 style="font-size:15px;font-weight:900;margin-bottom:12px">📋 تفاصيل الفوارق</h2>
<table><thead><tr><th>التاريخ</th><th>الفاتورة</th><th>الوصف</th><th style="text-align:center">النوع</th><th style="text-align:center">التطبيق</th><th style="text-align:center">XLSX</th><th style="text-align:center">الفارق</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p style="text-align:center;color:#999;font-size:11px;margin-top:12px">GitHub Actions — {TODAY}</p>
</body></html>"""

def send_email(html_body, diff_count):
    subject = f"{'⚠️' if diff_count else '✅'} تقرير مزرعة هادي — {TODAY}"
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To']   = EMAIL_TO
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    print(f"📧 SMTP: smtp.gmail.com:587")
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(EMAIL_FROM, EMAIL_PASS)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"✅ تم إرسال التقرير إلى {EMAIL_TO}")
    except Exception as e:
        print(f"❌ فشل Gmail: {e}")

if __name__ == '__main__':
    print(f"🌿 farm_compare.py — {TODAY} {datetime.datetime.now().strftime('%H:%M')}")
    print(f"📬 من: {EMAIL_FROM} → إلى: {EMAIL_TO}")
    app_sales = load_app()
    xlsx_rows = load_xlsx()
    if not app_sales and not xlsx_rows:
        print("❌ لا توجد بيانات"); exit(1)
    result = compare(app_sales, xlsx_rows)
    print(f"📊 تطبيق={result['app_total']:.3f} | XLSX={result['xlsx_credit']:.3f} | فارق={result['diff_total']:+.3f} | فوارق={len(result['diffs'])}")
    html = build_html(result)
    send_email(html, len(result['diffs']))
