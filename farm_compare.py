import os, json, requests, openpyxl, smtplib, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ══ إعدادات ══
JSONBIN_URL = os.environ.get('JSONBIN_BIN_URL', 'https://api.jsonbin.io/v3/b/6a0c5f4b6877513b27993aed')
JSONBIN_KEY = os.environ.get('JSONBIN_API_KEY', '')
XLSX_PATH   = os.environ.get('XLSX_PATH', 'Farm_Account.xlsx')
EMAIL_FROM  = os.environ.get('EMAIL_FROM', 'hadiishak@hotmail.com')
EMAIL_PASS  = os.environ.get('EMAIL_PASS', '')
EMAIL_TO    = os.environ.get('EMAIL_TO', 'hadi@ftm8.com')
TODAY       = datetime.date.today().isoformat()

# ══ 1. قراءة بيانات JSONBin (التطبيق) ══
def load_jsonbin():
    try:
        res = requests.get(
            JSONBIN_URL + '/latest',
            headers={'X-Master-Key': JSONBIN_KEY},
            timeout=15
        )
        rec = res.json().get('record', {})
        sales = rec.get('SALES', [])
        print(f"✅ JSONBin: {len(sales)} مبيعة")
        return sales
    except Exception as e:
        print(f"❌ خطأ JSONBin: {e}")
        return []

# ══ 2. قراءة بيانات XLSX ══
def load_xlsx():
    sales = []
    try:
        wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
        ws = None
        for name in wb.sheetnames:
            if 'كشف' in name or 'account' in name.lower():
                ws = wb[name]
                break
        if not ws:
            ws = wb.active

        header_row = None
        rows_data = []
        for row in ws.iter_rows(values_only=True):
            if row[0] is None:
                continue
            # البحث عن صف الرأس
            if header_row is None:
                row_str = ' '.join(str(c) for c in row if c)
                if 'سحب' in row_str or 'Debit' in row_str or 'إيداع' in row_str:
                    header_row = [str(c).strip() if c else '' for c in row]
                    continue
            else:
                rows_data.append(row)

        # تحديد أعمدة التاريخ والمرجع والوصف والسحب والإيداع
        if header_row:
            def col(name_parts):
                for i, h in enumerate(header_row):
                    for p in name_parts:
                        if p in h:
                            return i
                return -1

            ci_date  = col(['تاريخ','Date','date'])
            ci_ref   = col(['مرجع','Ref','ref'])
            ci_desc  = col(['بيان','وصف','Desc','desc'])
            ci_debit = col(['سحب','Debit','debit','مدين'])
            ci_credit= col(['إيداع','Credit','credit','دائن'])
            ci_paid  = col(['الدافع','Paid','paid'])
            ci_status= col(['الحالة','Status','status'])

            for row in rows_data:
                def g(i):
                    return row[i] if i >= 0 and i < len(row) else None

                date_val = g(ci_date)
                credit   = g(ci_credit)
                debit    = g(ci_debit)
                ref      = str(g(ci_ref) or '').strip()
                desc     = str(g(ci_desc) or '').strip()
                paid_by  = str(g(ci_paid) or '').strip()
                status   = str(g(ci_status) or '').strip()

                # تحويل التاريخ
                if isinstance(date_val, datetime.datetime):
                    date_str = date_val.date().isoformat()
                elif isinstance(date_val, datetime.date):
                    date_str = date_val.isoformat()
                elif isinstance(date_val, (int, float)) and date_val > 40000:
                    # Excel serial date
                    base = datetime.date(1899, 12, 30)
                    date_str = (base + datetime.timedelta(days=int(date_val))).isoformat()
                else:
                    continue

                # تصفية الصفوف الفارغة والإجماليات
                if not date_str or not desc or desc in ['الإجمالي','TOTALS','ملخص']:
                    continue

                try:
                    credit_f = float(credit) if credit and str(credit).strip() not in ['', '—', '-', 'None'] else 0.0
                    debit_f  = float(debit)  if debit  and str(debit).strip()  not in ['', '—', '-', 'None'] else 0.0
                except:
                    credit_f = debit_f = 0.0

                if credit_f == 0 and debit_f == 0:
                    continue

                sales.append({
                    'date':   date_str,
                    'ref':    ref,
                    'desc':   desc,
                    'credit': round(credit_f, 3),
                    'debit':  round(debit_f, 3),
                    'paidBy': paid_by,
                    'status': status,
                })
        wb.close()
        print(f"✅ XLSX: {len(sales)} سطر")
    except Exception as e:
        print(f"❌ خطأ XLSX: {e}")
    return sales

# ══ 3. المقارنة ══
def compare(app_sales, xlsx_rows):
    # ── إجماليات ──
    app_total  = round(sum(s.get('total', 0) for s in app_sales), 3)
    xlsx_credit= round(sum(r['credit'] for r in xlsx_rows), 3)
    xlsx_debit = round(sum(r['debit']  for r in xlsx_rows), 3)
    diff_total = round(app_total - xlsx_credit, 3)

    # ── مبيعات في التطبيق (مايو 2026 فقط للتقرير اليومي) ──
    app_by_ref = {}
    for s in app_sales:
        ref = (s.get('invNum') or '').strip().upper()
        prod= s.get('product','')
        key = f"{ref}|{prod}"
        app_by_ref.setdefault(key, []).append(s)

    # ── سجلات XLSX ──
    xlsx_by_ref = {}
    for r in xlsx_rows:
        ref = r['ref'].strip().upper()
        key = f"{ref}|{r['desc'][:20]}"
        xlsx_by_ref.setdefault(key, []).append(r)

    # ── فوارق ──
    diffs = []

    # مبيعات في التطبيق بقيمة مختلفة عن XLSX
    for s in app_sales:
        ref  = (s.get('invNum') or '').strip().upper()
        prod = s.get('product','')
        amt  = round(s.get('total',0), 3)
        date = s.get('date','')

        # إيجاد مقابل في XLSX
        matches = [r for r in xlsx_rows
                   if r['ref'].upper() == ref
                   and r['credit'] > 0]
        if not matches:
            diffs.append({
                'type': 'في التطبيق فقط',
                'ref': ref, 'desc': prod,
                'date': date,
                'app_val': amt, 'xlsx_val': 0,
                'diff': amt
            })
        else:
            xlsx_amt = round(sum(m['credit'] for m in matches), 3)
            if abs(xlsx_amt - amt) > 0.005:
                diffs.append({
                    'type': 'فارق في القيمة',
                    'ref': ref, 'desc': prod,
                    'date': date,
                    'app_val': amt, 'xlsx_val': xlsx_amt,
                    'diff': round(amt - xlsx_amt, 3)
                })

    # سجلات في XLSX غير موجودة في التطبيق
    app_refs = set((s.get('invNum','') or '').strip().upper() for s in app_sales)
    for r in xlsx_rows:
        if r['credit'] <= 0: continue
        ref = r['ref'].strip().upper()
        if ref and ref not in app_refs and ref not in ['0','']:
            diffs.append({
                'type': 'في XLSX فقط',
                'ref': ref, 'desc': r['desc'],
                'date': r['date'],
                'app_val': 0, 'xlsx_val': r['credit'],
                'diff': -r['credit']
            })

    # إزالة المكررات
    seen = set()
    unique_diffs = []
    for d in diffs:
        k = f"{d['ref']}|{d['type']}"
        if k not in seen:
            seen.add(k)
            unique_diffs.append(d)

    return {
        'app_total':   app_total,
        'xlsx_credit': xlsx_credit,
        'xlsx_debit':  xlsx_debit,
        'diff_total':  diff_total,
        'diffs':       unique_diffs,
        'app_count':   len(app_sales),
        'xlsx_count':  len(xlsx_rows),
    }

# ══ 4. بناء HTML التقرير ══
def build_html(result):
    today_ar = datetime.date.today().strftime('%Y-%m-%d')
    diff_color = '#c62828' if abs(result['diff_total']) > 0.01 else '#1b5e20'
    status_icon = '⚠️' if result['diffs'] else '✅'
    status_text = f"{len(result['diffs'])} فارق بحاجة مراجعة" if result['diffs'] else "كل البيانات متطابقة"

    rows_html = ''
    if result['diffs']:
        for d in sorted(result['diffs'], key=lambda x: x['date'], reverse=True):
            type_color = {'في التطبيق فقط':'#e65100','في XLSX فقط':'#1565c0','فارق في القيمة':'#6a1b9a'}.get(d['type'],'#555')
            diff_sign = '+' if d['diff'] > 0 else ''
            rows_html += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #eee">{d['date']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;color:#1565c0;font-weight:700">{d['ref']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee">{d['desc'][:35]}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">
                <span style="background:{type_color}22;color:{type_color};padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{d['type']}</span>
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;direction:ltr">{d['app_val']:.3f}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;direction:ltr">{d['xlsx_val']:.3f}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;direction:ltr;font-weight:900;color:{diff_color}">{diff_sign}{d['diff']:.3f}</td>
            </tr>"""
    else:
        rows_html = '<tr><td colspan="7" style="padding:20px;text-align:center;color:#1b5e20;font-size:16px">✅ لا توجد فوارق — كل البيانات متطابقة</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:Tajawal,Arial,sans-serif;direction:rtl;background:#f5f5f5;padding:20px;color:#1c1c1c}}
  .card{{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #e0e0e0}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
  .kpi{{background:#f8fffe;border-radius:8px;padding:14px;text-align:center;border:1px solid #e0e0e0}}
  .kpi-lbl{{font-size:12px;color:#666;margin-bottom:4px}}
  .kpi-val{{font-size:20px;font-weight:900;direction:ltr}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{background:#1b5e20;color:#fff;padding:10px 12px;text-align:right;font-weight:700}}
  tr:nth-child(even){{background:#f9f9f9}}
</style></head>
<body>
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #1b5e20;padding-bottom:12px;margin-bottom:16px">
    <div>
      <h1 style="font-size:18px;color:#1b5e20;font-weight:900">🌿 مزرعة هادي اسحاق</h1>
      <p style="color:#555;font-size:13px">تقرير المقارنة اليومي — {today_ar}</p>
    </div>
    <div style="text-align:center;background:{'#fff3e0' if result['diffs'] else '#e8f5e9'};padding:10px 20px;border-radius:8px">
      <div style="font-size:22px">{status_icon}</div>
      <div style="font-size:12px;font-weight:700;color:{diff_color}">{status_text}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi">
      <div class="kpi-lbl">مبيعات التطبيق</div>
      <div class="kpi-val" style="color:#1b5e20">{result['app_total']:.3f} دك</div>
      <div style="font-size:11px;color:#999">{result['app_count']} سجل</div>
    </div>
    <div class="kpi">
      <div class="kpi-lbl">مبيعات XLSX</div>
      <div class="kpi-val" style="color:#1565c0">{result['xlsx_credit']:.3f} دك</div>
      <div style="font-size:11px;color:#999">{result['xlsx_count']} سطر</div>
    </div>
    <div class="kpi">
      <div class="kpi-lbl">الفارق</div>
      <div class="kpi-val" style="color:{diff_color}">{result['diff_total']:+.3f} دك</div>
      <div style="font-size:11px;color:#999">{'يحتاج مراجعة' if abs(result['diff_total'])>0.01 else 'ممتاز'}</div>
    </div>
    <div class="kpi">
      <div class="kpi-lbl">الفوارق</div>
      <div class="kpi-val" style="color:{diff_color}">{len(result['diffs'])}</div>
      <div style="font-size:11px;color:#999">سجل مختلف</div>
    </div>
  </div>
</div>

<div class="card">
  <h2 style="font-size:15px;font-weight:900;margin-bottom:12px;color:#333">📋 تفاصيل الفوارق</h2>
  <table>
    <thead><tr>
      <th>التاريخ</th><th>الفاتورة</th><th>الوصف</th><th style="text-align:center">النوع</th>
      <th style="text-align:center">التطبيق</th><th style="text-align:center">XLSX</th><th style="text-align:center">الفارق</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<p style="text-align:center;color:#999;font-size:11px;margin-top:12px">
  تم الإرسال تلقائياً من GitHub Actions — {today_ar} 10:00 م
</p>
</body></html>"""

# ══ 5. إرسال الإيميل ══
def send_email(html_body, diff_count):
    subject = f"{'⚠️' if diff_count else '✅'} تقرير المقارنة اليومي — مزرعة هادي اسحاق — {TODAY}"
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = EMAIL_FROM
    msg['To']      = EMAIL_TO
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        # Hotmail/Outlook SMTP
        with smtplib.SMTP('smtp.mail.yahoo.com', 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(EMAIL_FROM, EMAIL_PASS)
            srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"✅ تم إرسال التقرير إلى {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"❌ فشل إرسال الإيميل: {e}")
        return False

# ══ MAIN ══
if __name__ == '__main__':
    print(f"🔍 بدء المقارنة — {TODAY}")

    app_sales  = load_jsonbin()
    xlsx_rows  = load_xlsx()

    if not app_sales and not xlsx_rows:
        print("❌ لا توجد بيانات في أي مصدر")
        exit(1)

    result   = compare(app_sales, xlsx_rows)
    html     = build_html(result)
    diff_cnt = len(result['diffs'])

    print(f"📊 النتيجة: تطبيق={result['app_total']:.3f} | XLSX={result['xlsx_credit']:.3f} | فارق={result['diff_total']:+.3f} | فوارق={diff_cnt}")

    send_email(html, diff_cnt)
