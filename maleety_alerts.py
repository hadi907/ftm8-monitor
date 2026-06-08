#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ماليتي — تنبيهات تلقائية يومية
يقرأ البيانات من Supabase ويرسل إيميل عبر Gmail إذا وُجدت تنبيهات
"""

import os
import json
import smtplib
import requests
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── إعدادات من GitHub Secrets ──────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
EMAIL_TO     = os.environ.get("EMAIL_TO", GMAIL_USER)

# ── مساعدات ────────────────────────────────────────────────
def days_left(date_str):
    if not date_str:
        return 9999
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return 9999

def icon(days):
    if days < 0:   return "🔴"
    if days <= 7:  return "🟠"
    return "🟡"

def sl(days):
    if days < 0:   return f"انتهت منذ {abs(days)} يوم"
    if days == 0:  return "تنتهي اليوم!"
    return f"تنتهي خلال {days} يوم"

def fmt(n):
    try:
        return f"{float(n):,.3f} د.ك"
    except Exception:
        return str(n)

# ── جلب البيانات من Supabase ────────────────────────────────
def fetch_data():
    url = f"{SUPABASE_URL}/rest/v1/maleety_data?id=eq.main&select=data"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError("لا توجد بيانات في Supabase")
    return rows[0]["data"]

# ── فحص التنبيهات ───────────────────────────────────────────
def build_alerts(D):
    alerts = []

    # وثائق
    for doc in D.get("documents", []):
        if doc.get("renewed"):
            continue
        days = days_left(doc.get("expiryDate"))
        notify_at = int(doc.get("notifyDays") or 30)
        if days <= notify_at:
            alerts.append({
                "section": "📋 وثائق",
                "line": f"{icon(days)} {doc.get('name','—')} ({doc.get('type','وثيقة')})",
                "detail": f"📅 {doc.get('expiryDate','')} · ⏰ {sl(days)}"
            })

    # تأمين السيارات — 30 يوم
    for c in D.get("cars", []):
        exp = c.get("insuranceExpiry")
        if not exp:
            continue
        days = days_left(exp)
        if days <= 30:
            alerts.append({
                "section": "🚗 تأمين سيارات",
                "line": f"{icon(days)} {c.get('carName','سيارة')}",
                "detail": f"📅 {exp} · ⏰ {sl(days)}"
            })

    # الإقامات — 30 يوم
    for r in D.get("residencies", []):
        exp = r.get("expiryDate")
        if not exp:
            continue
        days = days_left(exp)
        if days <= 30:
            alerts.append({
                "section": "🪪 إقامات",
                "line": f"{icon(days)} {r.get('name','إقامة')}",
                "detail": f"📅 {exp} · ⏰ {sl(days)}"
            })

    # العقود — 30 يوم
    for c in D.get("contracts", []):
        exp = c.get("endDate")
        if not exp:
            continue
        days = days_left(exp)
        if days <= 30:
            alerts.append({
                "section": "📜 عقود",
                "line": f"{icon(days)} {c.get('contractName','عقد')}",
                "detail": f"📅 {exp} · ⏰ {sl(days)}"
            })

    # الودائع — 30 يوم
    for d in D.get("deposits", []):
        exp = d.get("endDate")
        if not exp:
            continue
        days = days_left(exp)
        if days <= 30:
            alerts.append({
                "section": "🏦 ودائع",
                "line": f"{icon(days)} {d.get('name','وديعة')} — {fmt(d.get('amount',0))}",
                "detail": f"📅 {exp} · ⏰ {sl(days)}"
            })

    return alerts

# ── بناء HTML الإيميل ────────────────────────────────────────
def build_html(alerts, today_str):
    sections = {}
    for a in alerts:
        sections.setdefault(a["section"], []).append(a)

    rows_html = ""
    for sec, items in sections.items():
        rows_html += f"""
        <tr>
          <td colspan="2" style="background:#1e293b;color:#94a3b8;font-size:12px;
              padding:8px 16px;font-weight:700;letter-spacing:.5px">{sec}</td>
        </tr>"""
        for a in items:
            bg = "#450a0a" if a["line"].startswith("🔴") else (
                 "#431407" if a["line"].startswith("🟠") else "#1c1917")
            rows_html += f"""
        <tr style="background:{bg}">
          <td style="padding:10px 16px;color:#f1f5f9;font-size:14px">{a['line']}</td>
          <td style="padding:10px 16px;color:#94a3b8;font-size:12px;text-align:left">{a['detail']}</td>
        </tr>"""

    count = len(alerts)
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8">
<style>
  body{{font-family:Arial,sans-serif;background:#0f172a;color:#f1f5f9;margin:0;padding:20px}}
  .card{{max-width:620px;margin:0 auto;background:#1e293b;border-radius:12px;overflow:hidden;
         box-shadow:0 4px 24px rgba(0,0,0,.4)}}
  .header{{background:linear-gradient(135deg,#7c3aed,#2563eb);padding:24px;text-align:center}}
  .header h1{{margin:0;font-size:22px;color:#fff}}
  .header p{{margin:6px 0 0;font-size:13px;color:#c4b5fd}}
  table{{width:100%;border-collapse:collapse}}
  td{{border-bottom:1px solid #334155;vertical-align:middle}}
  .footer{{padding:16px;text-align:center;font-size:12px;color:#475569}}
  .badge{{display:inline-block;background:#7c3aed22;border:1px solid #7c3aed55;
          color:#a78bfa;border-radius:20px;padding:4px 14px;font-size:13px;margin-top:8px}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>🔔 تنبيهات ماليتي</h1>
    <p>{today_str}</p>
    <div class="badge">{count} تنبيه يحتاج متابعة</div>
  </div>
  <table>{rows_html}
  </table>
  <div class="footer">
    يرجى المراجعة والاتخاذ اللازم ✅<br>
    <small>تم الإرسال تلقائياً عبر GitHub Actions — ماليتي</small>
  </div>
</div>
</body>
</html>"""

# ── إرسال الإيميل ────────────────────────────────────────────
def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())

# ── main ─────────────────────────────────────────────────────
def main():
    print("📡 جاري جلب البيانات من Supabase...")
    D = fetch_data()
    print("✅ تم جلب البيانات")

    alerts = build_alerts(D)
    print(f"🔔 عدد التنبيهات: {len(alerts)}")

    if not alerts:
        print("✅ لا توجد تنبيهات — لن يُرسل إيميل")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    subject = f"🔔 ماليتي — {len(alerts)} تنبيه · {today_str}"
    html = build_html(alerts, today_str)

    print(f"📧 جاري الإرسال إلى {EMAIL_TO}...")
    send_email(subject, html)
    print("✅ تم إرسال الإيميل بنجاح")

    for a in alerts:
        print(f"  {a['line']} — {a['detail']}")

if __name__ == "__main__":
    main()
