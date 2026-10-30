import os, json, requests, smtplib, datetime, re, time
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── خريطة الشهور العربية والإنجليزية ──
AR_MONTHS = {
    'يناير':1,'فبراير':2,'مارس':3,'أبريل':4,'ابريل':4,'مايو':5,
    'يونيو':6,'يونيه':6,'يوليو':7,'يوليه':7,'أغسطس':8,'اغسطس':8,
    'سبتمبر':9,'أكتوبر':10,'اكتوبر':10,'نوفمبر':11,'ديسمبر':12,
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12
}
AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789')

def parse_date(date_v):
    """يحلّل التاريخ بجميع الصيغ: datetime، عربي، إنجليزي، أرقام عربية"""
    if date_v is None: return None
    try:
        if pd.isna(date_v): return None
    except: pass
    if hasattr(date_v, 'date'):
        return date_v.date().isoformat()
    s = str(date_v).strip().translate(AR_DIGITS)
    if not s or s in ['nan','None','NaT','']: return None
    m = re.match(r'^(\d{1,2})[-/\s]+([^\d\s\-]+)[-/\s]+(\d{2,4})$', s)
    if m:
        day, month_str, year = m.group(1), m.group(2).strip().lower(), m.group(3)
        month_num = AR_MONTHS.get(month_str)
        if month_num:
            yr = int(year)
            if yr < 100: yr += 2000
            try:
                return datetime.date(yr, month_num, int(day)).isoformat()
            except: pass
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d-%m-%Y','%Y/%m/%d'):
        try: return datetime.datetime.strptime(s, fmt).date().isoformat()
        except: pass
    try: return pd.to_datetime(s, dayfirst=True).date().isoformat()
    except: pass
    return s

def norm_ref(r):
    """تطبيع المرجع: INV-057 = inv-57 = INV057 = INV57"""
    if not r: return ''
    r = str(r).upper().replace(' ','').replace('-','')
    r = re.sub(r'^(INV)0+(\d+)$', r'\g<1>\2', r)
    return r

GITHUB_RAW = 'https://raw.githubusercontent.com/hadi907/ftm8-monitor/main/farm_data.json'
XLSX_PATH  = os.environ.get('XLSX_PATH', 'Farm_Account.xlsx')
EMAIL_FROM = os.environ.get('EMAIL_FROM', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
EMAIL_TO   = os.environ.get('EMAIL_TO', 'hadi@ftm8.com')
GH_TOKEN   = os.environ.get('GH_TOKEN', '')
TODAY      = datetime.date.today().isoformat()
CURRENT_MONTH = TODAY[:7]  # 'YYYY-MM' — تقرير المقارنة يقتصر على الشهر الحالي فقط
AR_MONTH_NAMES = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
MONTH_LABEL = f"{AR_MONTH_NAMES[int(CURRENT_MONTH[5:7])-1]} {CURRENT_MONTH[:4]}"

def load_app():
    """يجلب farm_data.json مع إعادة محاولة تلقائية (حتى 3 مرات) لو صار
    انقطاع/تأخر مؤقت بالشبكة أو رد غير صالح (مثل 404 مؤقت من CDN GitHub).
    يرجّع None فقط لو فشلت كل المحاولات — حتى لا يُحسب هذا كـ"صفر مبيعات
    حقيقي" ويُنتج فارقاً وهمياً بالتقرير.
    ── المستودع خاص (private)، فلازم تمرير توكن مصادقة وإلا raw.githubusercontent.com
    يرجّع 404 دائماً حتى لو الملف موجود فعلاً ──"""
    local = os.environ.get('FARM_DATA_FILE', '')
    if local:  # للاختبار المحلي فقط
        data = json.load(open(local, encoding='utf-8'))
        return {'sales': data.get('SALES', data.get('ps3_sales', [])),
                'exp':   data.get('EXP',   data.get('ps3_exp',   []))}
    headers = {'Authorization': f'token {GH_TOKEN}'} if GH_TOKEN else {}
    last_err = None
    for attempt in range(1, 4):
        try:
            res = requests.get(GITHUB_RAW, headers=headers, timeout=20)
            res.raise_for_status()
            data = res.json()
            # ── إصلاح: يدعم المفاتيحين uppercase (SALES) و lowercase (ps3_sales) ──
            sales = data.get('SALES', data.get('ps3_sales', []))
            exps  = data.get('EXP',   data.get('ps3_exp',   []))
            print(f"✅ farm_data.json — {len(sales)} مبيعة، {len(exps)} مصروف")
            return {'sales': sales, 'exp': exps}
        except Exception as e:
            last_err = e
            print(f"⚠️ محاولة {attempt}/3 لجلب farm_data.json فشلت: {e}")
            if attempt < 3:
                time.sleep(5 * attempt)
    print(f"❌ فشل جلب farm_data.json بعد 3 محاولات: {last_err} — سيتم إيقاف التقرير لتفادي نتائج غير دقيقة")
    return None

def _num(v):
    try:
        return float(v) if pd.notna(v) and str(v).strip() not in ['—','-',''] else 0.0
    except:
        return 0.0

# ── مصروفات XLSX (عمود سحب/مدين) + تنبيهات التواريخ المشبوهة — أُضيفت 2026-10-30 ──
XLSX_EXP = []          # [{date, desc, amount, paid_by}]
XLSX_BAD_DATES = []    # صفوف بسنة غير معقولة (مثل 2022 بدل 2026)

def load_xlsx():
    rows = []
    XLSX_EXP.clear(); XLSX_BAD_DATES.clear()
    this_year = datetime.date.today().year
    try:
        df = pd.read_excel(XLSX_PATH, sheet_name='كشف الحساب', header=None, skiprows=3)
        skipped_date = []
        skipped_zero = 0
        for _, row in df.iterrows():
            date_v   = row[0]
            ref      = str(row[1] if pd.notna(row[1]) else '').strip()
            desc     = str(row[2] if pd.notna(row[2]) else '').strip()
            credit_v = row[4]
            debit    = _num(row[3])
            c        = _num(credit_v)
            date_str = parse_date(date_v)

            # تنبيه: سنة خارج المدى المتوقع (بيانات الدفتر تبدأ 2026)
            if (debit > 0 or c > 0) and date_str and re.match(r'^\d{4}-', date_str):
                yr = int(date_str[:4])
                if yr < 2026 or yr > this_year:
                    XLSX_BAD_DATES.append({'date': date_str, 'ref': ref, 'desc': desc,
                                           'amount': round(debit or c, 3),
                                           'kind': 'مصروف' if debit > 0 else 'مبيعة'})

            # مصروف (سحب/مدين) — لا يشترط رقم مرجع
            if debit > 0 and date_str:
                paid_by = str(row[6] if len(row) > 6 and pd.notna(row[6]) else '').strip()
                XLSX_EXP.append({'date': date_str, 'desc': desc,
                                 'amount': round(debit, 3), 'paid_by': paid_by})

            if not ref or ref in ['0','nan','None']:
                continue

            if not date_str:
                skipped_date.append(f"ref={ref}, raw={date_v!r}")
                continue

            if c <= 0:
                skipped_zero += 1
                continue

            rows.append({
                'date':     date_str,
                'ref':      ref,
                'ref_norm': norm_ref(ref),
                'desc':     desc,
                'credit':   round(c, 3)
            })

        total = sum(r['credit'] for r in rows)
        print(f"✅ XLSX (كشف الحساب) — {len(rows)} سطر، إجمالي={total:.3f} دك")
        if skipped_date:
            print(f"  ⚠️ تجاهلت {len(skipped_date)} صف بسبب تاريخ غير صالح:")
            for s in skipped_date: print(f"    - {s}")
        if skipped_zero:
            print(f"  ℹ️ تجاهلت {skipped_zero} صف credit=0 (مدين أو فارغ)")
    except Exception as e:
        print(f"❌ خطأ XLSX: {e}")
        import traceback; traceback.print_exc()
    return rows

def compare(app_sales, xlsx_rows):
    app_total   = round(sum(s.get('total', 0) for s in app_sales), 3)
    xlsx_credit = round(sum(r['credit'] for r in xlsx_rows), 3)

    # ── نطاق المزامنة: JSONBin يحتفظ بآخر 50 فاتورة فقط، فأي سطر XLSX أقدم
    #    من أقدم فاتورة موجودة فعلياً في التطبيق (السحابة) لا يُعتبر "ناقصاً"،
    #    لأنه ببساطة خارج نطاق ما يُرفع للمقارنة (موجود بالكامل في المتصفح محلياً) ──
    app_dates = [s.get('date') for s in app_sales if s.get('date')]
    min_app_date = min(app_dates) if app_dates else None

    xlsx_by_ref = {}
    for r in xlsx_rows:
        xlsx_by_ref.setdefault(r['ref_norm'], []).append(r)

    app_refs = set()
    for s in app_sales:
        ref = norm_ref(s.get('invNum') or '')
        if ref: app_refs.add(ref)

    diffs = []
    out_of_range = []
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
            item = {'type':'في XLSX فقط','ref':r['ref'],'desc':r['desc'],'date':r['date'],'app_val':0,'xlsx_val':r['credit'],'diff':-r['credit']}
            # فاتورة بتاريخ أقدم من (أو يساوي) أقدم فاتورة مزامنة = خارج نطاق JSONBin (50 فقط)
            # نستخدم "<=" وليس "<" لأن أكثر من فاتورة قد تقع في نفس يوم حدّ القطع (تأكّد فعلياً بفحص المتصفح)
            if min_app_date and r['date'] and r['date'] <= min_app_date:
                out_of_range.append(item)
            else:
                diffs.append(item)

    # الفارق الإجمالي يُحسب فقط على النطاق المشترك (نفس فترة آخر 50 فاتورة)
    # حتى لا يظهر فارق وهمي بسبب الفواتير القديمة خارج نطاق المزامنة
    out_of_range_total_tmp = round(sum(-i['diff'] for i in out_of_range), 3)
    xlsx_credit_in_range = round(xlsx_credit - out_of_range_total_tmp, 3)

    return {
        'app_total':   app_total,
        'xlsx_credit': xlsx_credit,
        'xlsx_credit_in_range': xlsx_credit_in_range,
        'diff_total':  round(app_total - xlsx_credit_in_range, 3),
        'diffs':       sorted(diffs, key=lambda x: x['date'], reverse=True),
        'out_of_range': sorted(out_of_range, key=lambda x: x['date'], reverse=True),
        'out_of_range_total': round(sum(-i['diff'] for i in out_of_range), 3),
        'min_app_date': min_app_date,
        'app_count':   len(app_sales),
        'xlsx_count':  len(xlsx_rows)
    }

def compare_expenses(app_exp, xlsx_exp):
    """مطابقة المصروفات بالمبلغ + التاريخ.
    1) تطابق تام (نفس التاريخ ونفس المبلغ)
    2) نفس المبلغ بتاريخ مختلف (±7 أيام) = فارق تاريخ فقط (لا يؤثر على الإجمالي)
    3) الباقي = موجود بطرف واحد فقط"""
    def d2o(d):
        try: return datetime.date.fromisoformat(d[:10]).toordinal()
        except: return None
    A = [{'date': (e.get('date') or '')[:10],
          'desc': (e.get('desc') or e.get('type') or '').strip(),
          'amount': round(float(e.get('amount') or 0), 3),
          'src': e.get('source') or ''} for e in app_exp]
    A = [a for a in A if a['amount'] > 0]
    X = [dict(x) for x in xlsx_exp]
    used = set()
    date_only, app_only = [], []
    pending = []
    for a in A:
        hit = next((i for i, x in enumerate(X) if i not in used
                    and x['date'] == a['date'] and abs(x['amount'] - a['amount']) < 0.005), None)
        if hit is not None: used.add(hit)
        else: pending.append(a)
    for a in pending:
        ao = d2o(a['date'])
        cands = [(abs(d2o(x['date']) - ao), i) for i, x in enumerate(X)
                 if i not in used and abs(x['amount'] - a['amount']) < 0.005
                 and ao is not None and d2o(x['date']) is not None and abs(d2o(x['date']) - ao) <= 7]
        if cands:
            _, i = min(cands); used.add(i)
            date_only.append({'desc': a['desc'], 'amount': a['amount'],
                              'app_date': a['date'], 'xlsx_date': X[i]['date']})
        else:
            app_only.append(a)
    xlsx_only = [x for i, x in enumerate(X) if i not in used]
    diffs = ([{'type': 'في التطبيق فقط', 'date': a['date'], 'desc': a['desc'],
               'app_val': a['amount'], 'xlsx_val': 0, 'diff': a['amount']} for a in app_only] +
             [{'type': 'في XLSX فقط', 'date': x['date'], 'desc': x['desc'],
               'app_val': 0, 'xlsx_val': x['amount'], 'diff': -x['amount']} for x in xlsx_only])
    app_total  = round(sum(a['amount'] for a in A), 3)
    xlsx_total = round(sum(x['amount'] for x in X), 3)
    return {'app_total': app_total, 'xlsx_total': xlsx_total,
            'diff_total': round(app_total - xlsx_total, 3),
            'app_count': len(A), 'xlsx_count': len(X),
            'diffs': sorted(diffs, key=lambda d: d['date'], reverse=True),
            'date_only': sorted(date_only, key=lambda d: d['app_date'], reverse=True)}

def build_html(r):
    e   = r['exp']
    bad = r.get('bad_dates', [])
    net_app  = round(r['app_total'] - e['app_total'], 3)
    net_xlsx = round(r['xlsx_credit_in_range'] - e['xlsx_total'], 3)
    net_diff = round(net_app - net_xlsx, 3)
    n_issues = len(r['diffs']) + len(e['diffs']) + len(bad)
    dc     = '#c62828' if n_issues else '#1b5e20'
    icon   = '⚠️' if n_issues else '✅'
    status = f"{n_issues} فارق بحاجة مراجعة" if n_issues else "كل البيانات متطابقة"
    TD  = 'padding:8px 12px;border-bottom:1px solid #eee'
    TDN = TD + ';text-align:center;direction:ltr'

    def badge(t):
        tc = {'في التطبيق فقط':'#e65100','في XLSX فقط':'#1565c0','فارق في القيمة':'#6a1b9a'}.get(t,'#555')
        return f'<span style="background:{tc}22;color:{tc};padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{t}</span>'

    def sum_row(label, a, x, d):
        ok = abs(d) < 0.005
        col = '#1b5e20' if ok else '#c62828'
        mark = '✅' if ok else '❌'
        return (f'<tr><td style="{TD};font-weight:900">{label}</td>'
                f'<td style="{TDN}">{a:.3f}</td><td style="{TDN}">{x:.3f}</td>'
                f'<td style="{TDN};font-weight:900;color:{col}">{d:+.3f} {mark}</td></tr>')

    summary = (sum_row('💰 المبيعات', r['app_total'], r['xlsx_credit_in_range'], r['diff_total']) +
               sum_row('🧾 المصروفات', e['app_total'], e['xlsx_total'], e['diff_total']) +
               sum_row('📊 الصافي (مبيعات − مصروفات)', net_app, net_xlsx, net_diff))

    # جدول فوارق المبيعات
    if r['diffs']:
        s_rows = ''.join(
            f'<tr><td style="{TD}">{d["date"]}</td>'
            f'<td style="{TD};color:#1565c0;font-weight:700">{d["ref"]}</td>'
            f'<td style="{TD}">{d["desc"][:35]}</td>'
            f'<td style="{TD};text-align:center">{badge(d["type"])}</td>'
            f'<td style="{TDN}">{d["app_val"]:.3f}</td><td style="{TDN}">{d["xlsx_val"]:.3f}</td>'
            f'<td style="{TDN};font-weight:900;color:#c62828">{d["diff"]:+.3f}</td></tr>' for d in r['diffs'])
    else:
        s_rows = '<tr><td colspan="7" style="padding:16px;text-align:center;color:#1b5e20">✅ المبيعات متطابقة</td></tr>'

    # جدول فوارق المصروفات
    if e['diffs']:
        e_rows = ''.join(
            f'<tr><td style="{TD}">{d["date"]}</td>'
            f'<td style="{TD}">{d["desc"][:45]}</td>'
            f'<td style="{TD};text-align:center">{badge(d["type"])}</td>'
            f'<td style="{TDN}">{d["app_val"]:.3f}</td><td style="{TDN}">{d["xlsx_val"]:.3f}</td>'
            f'<td style="{TDN};font-weight:900;color:#c62828">{d["diff"]:+.3f}</td></tr>' for d in e['diffs'])
    else:
        e_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#1b5e20">✅ المصروفات متطابقة</td></tr>'

    extra = ''
    if bad:
        items = ''.join(f'<li>{b["date"]} — {b["kind"]} — {b["desc"][:40]} — {b["amount"]:.3f} دك</li>' for b in bad)
        extra += ('<div style="background:#ffebee;border-right:4px solid #c62828;padding:10px 16px;border-radius:6px;'
                  'font-size:13px;color:#b71c1c;margin-top:12px"><b>⚠️ تواريخ بسنة غير صحيحة في XLSX'
                  ' (لن تُحسب ضمن الشهر):</b><ul style="margin:6px 20px 0">' + items + '</ul></div>')
    if e['date_only']:
        items = ''.join(f'<li>{d["desc"][:40]} — {d["amount"]:.3f} دك: التطبيق {d["app_date"]} / XLSX {d["xlsx_date"]}</li>'
                        for d in e['date_only'])
        extra += ('<div style="background:#fffde7;border-right:4px solid #f9a825;padding:10px 16px;border-radius:6px;'
                  'font-size:12px;color:#795548;margin-top:12px"><b>ℹ️ مصروفات بنفس المبلغ وتاريخ مختلف'
                  ' (لا تؤثر على الإجمالي):</b><ul style="margin:6px 20px 0">' + items + '</ul></div>')
    if r['out_of_range']:
        extra += ('<div style="background:#e3f2fd;border-right:4px solid #1565c0;padding:10px 16px;border-radius:6px;'
                  f'font-size:12px;color:#1565c0;margin-top:12px"><b>ملاحظة:</b> {len(r["out_of_range"])} فاتورة قديمة '
                  f'(قبل {r["min_app_date"]}) بقيمة {r["out_of_range_total"]:.3f} دك خارج نطاق المزامنة — لا تُعتبر فارقاً.</div>')

    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Tajawal,Arial;direction:rtl;background:#f5f5f5;padding:20px}}.card{{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #e0e0e0}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{background:#1b5e20;color:#fff;padding:10px 12px;text-align:right}}tr:nth-child(even){{background:#f9f9f9}}h2{{font-size:15px;font-weight:900;margin-bottom:12px}}</style></head>
<body><div class="card"><div style="display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #1b5e20;padding-bottom:12px;margin-bottom:16px">
<div><h1 style="font-size:18px;color:#1b5e20;font-weight:900">🌿 مزرعة هادي اسحاق</h1><p style="color:#555;font-size:13px">تقرير المقارنة — {MONTH_LABEL} — {TODAY}</p></div>
<div style="background:{'#fff3e0' if n_issues else '#e8f5e9'};padding:10px 20px;border-radius:8px;text-align:center"><div style="font-size:22px">{icon}</div><div style="font-size:12px;font-weight:700;color:{dc}">{status}</div></div></div>
<h2>📋 الملخص</h2>
<table><thead><tr><th>البند</th><th style="text-align:center">التطبيق</th><th style="text-align:center">XLSX</th><th style="text-align:center">الفارق</th></tr></thead>
<tbody>{summary}</tbody></table>
<p style="font-size:11px;color:#999;margin-top:6px">مبيعات: {r['app_count']} تطبيق / {r['xlsx_count']} XLSX — مصروفات: {e['app_count']} تطبيق / {e['xlsx_count']} XLSX</p>
{extra}
</div>
<div class="card"><h2>💰 فوارق المبيعات</h2>
<table><thead><tr><th>التاريخ</th><th>الفاتورة</th><th>الوصف</th><th style="text-align:center">النوع</th><th style="text-align:center">التطبيق</th><th style="text-align:center">XLSX</th><th style="text-align:center">الفارق</th></tr></thead>
<tbody>{s_rows}</tbody></table></div>
<div class="card"><h2>🧾 فوارق المصروفات</h2>
<table><thead><tr><th>التاريخ</th><th>البيان</th><th style="text-align:center">النوع</th><th style="text-align:center">التطبيق</th><th style="text-align:center">XLSX</th><th style="text-align:center">الفارق</th></tr></thead>
<tbody>{e_rows}</tbody></table></div>
<p style="text-align:center;color:#999;font-size:11px;margin-top:12px">GitHub Actions — {TODAY}</p>
</body></html>"""

def send_email(html_body, diff_count):
    subject = f"{'⚠️' if diff_count else '✅'} مزرعة هادي اسحاق - مقارنة {MONTH_LABEL} — {TODAY}"
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = EMAIL_FROM
    msg['To']      = EMAIL_TO
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    print(f"📧 SMTP: smtp.gmail.com:587 → {EMAIL_TO}")
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo()
            srv.login(EMAIL_FROM, EMAIL_PASS)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"✅ تم إرسال التقرير")
        return True
    except Exception as e:
        print(f"❌ فشل Gmail: {e}")
        return False

if __name__ == '__main__':
    print(f"🌿 farm_compare.py — {TODAY} {datetime.datetime.now().strftime('%H:%M')}")
    print(f"📬 من: {EMAIL_FROM} → إلى: {EMAIL_TO}")
    app = load_app()
    if app is None:
        print("❌ توقف التقرير: تعذّر جلب بيانات التطبيق (farm_data.json) بعد عدة محاولات — لن يُرسل تقرير بأرقام غير دقيقة")
        exit(1)
    app_sales, app_exp = app['sales'], app['exp']
    xlsx_rows = load_xlsx()
    if not app_sales and not xlsx_rows:
        print("❌ لا توجد بيانات"); exit(1)

    # ── تقييد المقارنة على الشهر الحالي فقط (بطلب هادي) ──
    in_month = lambda d: (d or '')[:7] == CURRENT_MONTH
    app_all_count  = len(app_sales)
    xlsx_all_count = len(xlsx_rows)
    app_sales = [s for s in app_sales if in_month(s.get('date'))]
    xlsx_rows = [r for r in xlsx_rows if in_month(r.get('date'))]
    app_exp_m  = [x for x in app_exp  if in_month(x.get('date'))]
    xlsx_exp_m = [x for x in XLSX_EXP if in_month(x.get('date'))]
    print(f"📅 تصفية للشهر الحالي ({MONTH_LABEL}): مبيعات تطبيق {len(app_sales)}/{app_all_count} | XLSX {len(xlsx_rows)}/{xlsx_all_count} | مصروفات تطبيق {len(app_exp_m)} | XLSX {len(xlsx_exp_m)}")
    result = compare(app_sales, xlsx_rows)
    result['exp'] = compare_expenses(app_exp_m, xlsx_exp_m)
    result['bad_dates'] = list(XLSX_BAD_DATES)
    e = result['exp']
    print(f"📊 مبيعات: تطبيق={result['app_total']:.3f} | XLSX={result['xlsx_credit_in_range']:.3f} | فارق={result['diff_total']:+.3f} | فوارق={len(result['diffs'])}")
    print(f"📊 مصروفات: تطبيق={e['app_total']:.3f} | XLSX={e['xlsx_total']:.3f} | فارق={e['diff_total']:+.3f} | فوارق={len(e['diffs'])} | فارق تاريخ فقط={len(e['date_only'])}")
    print(f"📊 تواريخ مشبوهة في XLSX: {len(result['bad_dates'])}")
    # ── الإرسال فقط عند حدوث تغيير بنتيجة المقارنة (فوارق أو تطابق) — بطلب هادي 2026-10-03 ──
    sig = json.dumps({
        'month': CURRENT_MONTH,
        'app_total': result['app_total'], 'app_count': result['app_count'],
        'xlsx_total': result['xlsx_credit_in_range'], 'xlsx_count': result['xlsx_count'],
        'diffs': [(d['ref'], d['desc'], d['type'], d['diff']) for d in result['diffs']],
        'exp_app': e['app_total'], 'exp_xlsx': e['xlsx_total'],
        'exp_diffs': [(d['date'], d['desc'], d['type'], d['diff']) for d in e['diffs']],
        'bad_dates': [(b['date'], b['desc'], b['amount']) for b in result['bad_dates']],
    }, ensure_ascii=False, sort_keys=True)
    SIG_FILE = os.environ.get('SIG_FILE', '.compare_state/last_sent.txt')
    try:
        last = open(SIG_FILE, encoding='utf-8').read()
    except Exception:
        last = ''
    if last == sig:
        print("ℹ️ لا تغيير منذ آخر إيميل — لن يُرسل إيميل")
        exit(0)
    html = build_html(result)
    if os.environ.get('DRY_RUN'):
        open(os.environ['DRY_RUN'], 'w', encoding='utf-8').write(html)
        print(f"🧪 DRY_RUN — حُفظ HTML في {os.environ['DRY_RUN']} بدون إرسال")
        exit(0)
    n_issues = len(result['diffs']) + len(e['diffs']) + len(result['bad_dates'])
    if send_email(html, n_issues):
        os.makedirs(os.path.dirname(SIG_FILE) or '.', exist_ok=True)
        open(SIG_FILE, 'w', encoding='utf-8').write(sig)
