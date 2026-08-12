import os, sys, json, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
REPORT_FILE = "competitor_report.json"
EMAIL_FROM = os.environ.get("EMAIL_FROM", "hishak888@gmail.com")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "hadi@ftm8.com")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
f = open(REPORT_FILE, encoding="utf-8")
data = json.load(f)
f.close()
subject = data.get("subject", "new plants prices offers")
body = data.get("body", "")
msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"] = EMAIL_FROM
msg["To"] = EMAIL_TO
msg.attach(MIMEText(body, "plain", "utf-8"))
server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
server.ehlo()
server.starttls()
server.login(EMAIL_FROM, EMAIL_PASS)
server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_bytes())
server.quit()
print("sent ok")
