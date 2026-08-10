import os, datetime, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── إعدادات ثابتة لحساب FTM8 ──
BLOG_ID = "6390063"
USER_ID = "4922881"
TIMEZONE = "Asia/Kuwait"

TOKEN = os.environ.get("METRICOOL_USER_TOKEN", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "hadi@ftm8.com")

TODAY = datetime.date.today().isoformat()
PLANNER_URL = f"https://app.metricool.com/planner/calendar?blogId={BLOG_ID}"
INSTAGRAM_URL = "https://www.instagram.com/ftm8.__/"


def check_today_posts():
    """يتحقق من منشورات انستغرام المجدولة/المسودة لليوم الحالي عبر Metricool API.
    ملاحظة: هذا فحص تقريبي (best effort) — إن اختفى المنشور من قائمة
    'المجدولة' فهذا مؤشر جيد (وليس تأكيدًا قاطعًا) على أنه نُشر.
    """
    url = "https://app.metricool.com/api/v2/scheduler/posts"
    params = {
        "blogId": BLOG_ID,
        "userId": USER_ID,
        "start": f"{TODAY}T00:00:00",
        "end": f"{TODAY}T23:59:59",
        "timezone": TIMEZONE,
    }
    headers = {"X-Mc-Auth": TOKEN}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=20)
        res.raise_for_status()
        data = res.json()
        posts = data.get("data", data) if isinstance(data, dict) else data
        ig_posts = [
            p for p in posts
            if any(pr.get("network") == "instagram" for pr in p.get("providers", []))
        ]
        return ig_posts, None
    except Exception as e:
        return None, str(e)


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    print(f"📧 SMTP: smtp.gmail.com:587 → {EMAIL_TO}")
    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.ehlo()
        srv.login(EMAIL_FROM, EMAIL_PASS)
        srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("✅ تم إرسال الإيميل")


def wrap(title, body_html):
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<style>body{{font-family:Tajawal,Arial;background:#f5f5f5;padding:20px;direction:rtl}}
.card{{background:#fff;border-radius:12px;padding:20px;border:1px solid #e0e0e0}}
a{{color:#1565c0}}</style></head><body><div class="card">
<h2 style="color:#1b5e20">{title}</h2>{body_html}
<p style="text-align:center;color:#999;font-size:11px;margin-top:16px">GitHub Actions — {TODAY}</p>
</div></body></html>"""


def main():
    if not TOKEN:
        send_email(
            f"⚠️ FTM8 — مفقود METRICOOL_USER_TOKEN — {TODAY}",
            wrap("⚠️ لم يتم ضبط رمز Metricool", "<p>أضف السر METRICOOL_USER_TOKEN في إعدادات المستودع ثم أعد التشغيل.</p>"),
        )
        return

    posts, err = check_today_posts()

    if err:
        send_email(
            f"⚠️ FTM8 — تعذر التحقق من نشر إعلان انستغرام — {TODAY}",
            wrap(
                "⚠️ تعذر الاتصال بـ Metricool للتحقق",
                f'<p>حدث خطأ أثناء التحقق من إعلان اليوم:</p><p style="color:#c62828">{err}</p>'
                f'<p>تحقق يدويًا: <a href="{PLANNER_URL}">فتح Metricool Planner</a></p>',
            ),
        )
        return

    if not posts:
        send_email(
            f"✅ FTM8 — على الأغلب نُشر إعلان اليوم — {TODAY}",
            wrap(
                "✅ إعلان اليوم لم يعد ضمن قائمة المسودات/المجدولة",
                f"<p>هذا مؤشر جيد (وليس تأكيدًا قاطعًا) على أنه نُشر بنجاح على انستغرام الساعة 10:00 صباحًا.</p>"
                f'<p><b>تأكد بنفسك:</b></p>'
                f'<p><a href="{INSTAGRAM_URL}">فتح صفحة انستغرام @ftm8.__</a></p>'
                f'<p><a href="{PLANNER_URL}">فتح Metricool للتأكد</a></p>',
            ),
        )
        return

    lines = ""
    for p in posts:
        provider = (p.get("providers") or [{}])[0]
        status = provider.get("detailedStatus", provider.get("status", "غير معروف"))
        draft = p.get("draft", False)
        txt = (p.get("text", "")[:60] + "…") if p.get("text") else ""
        lines += f"<li>الحالة: <b>{status}</b> | مسودة: {'نعم' if draft else 'لا'} | {txt}</li>"

    send_email(
        f"⚠️ FTM8 — إعلان اليوم لم يُنشر بعد — {TODAY}",
        wrap(
            "⚠️ إعلان اليوم لا يزال ضمن القائمة",
            f"<ul>{lines}</ul>"
            f"<p>يرجى المراجعة يدويًا ونشره إذا كان جاهزًا:</p>"
            f'<p><a href="{PLANNER_URL}">فتح Metricool</a></p>',
        ),
    )


if __name__ == "__main__":
    print(f"📸 check_instagram_publish.py — {TODAY}")
    main()
