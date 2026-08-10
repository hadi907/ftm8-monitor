import os, datetime, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── إعدادات ثابتة لحساب FTM8 ──
BLOG_ID = "6390063"
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "hadi@ftm8.com")

TODAY = datetime.date.today().isoformat()
PLANNER_URL = f"https://app.metricool.com/planner/calendar?blogId={BLOG_ID}"
INSTAGRAM_URL = "https://www.instagram.com/ftm8.__/"


def build_html():
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<style>body{{font-family:Tajawal,Arial;background:#f5f5f5;padding:20px;direction:rtl}}
.card{{background:#fff;border-radius:12px;padding:20px;border:1px solid #e0e0e0}}
a{{color:#1565c0}}</style></head><body><div class="card">
<h2 style="color:#1b5e20">⏰ تذكير: إعلان انستغرام اليوم</h2>
<p>حان وقت التحقق من إعلان اليوم ({TODAY}) على حساب @ftm8.__ — من المفترض أنه نُشر تلقائيًا الساعة 10:00 صباحًا بتوقيت الكويت.</p>
<p><b>تحقق بنفسك:</b></p>
<p><a href="{INSTAGRAM_URL}">فتح صفحة انستغرام @ftm8.__</a></p>
<p><a href="{PLANNER_URL}">فتح Metricool Planner</a></p>
<p style="text-align:center;color:#999;font-size:11px;margin-top:16px">GitHub Actions — {TODAY}</p>
</div></body></html>"""


def send_email():
    subject = f"⏰ FTM8 — تذكير: تأكد من نشر إعلان انستغرام اليوم — {TODAY}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(build_html(), "html", "utf-8"))
    print(f"📧 SMTP: smtp.gmail.com:587 → {EMAIL_TO}")
    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.ehlo()
        srv.login(EMAIL_FROM, EMAIL_PASS)
        srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("✅ تم إرسال التذكير")


if __name__ == "__main__":
    print(f"⏰ check_instagram_publish.py (تذكير بسيط) — {TODAY}")
    send_email()
