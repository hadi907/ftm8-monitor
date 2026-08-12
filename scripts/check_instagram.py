#!/usr/bin/env python3
"""
Weekly check of competitor Instagram accounts (agriculture/nursery businesses)
and email an Arabic summary of anything new posted in the last ~7 days.

Reads Instagram profiles anonymously via Instaloader. NOTE: Instagram actively
rate-limits / blocks anonymous requests from datacenter IPs (which is what
GitHub Actions runners use). This script is best-effort: if a profile can't
be reached, it is reported as "تعذر الوصول" instead of failing the whole run.

Required GitHub repo secrets:
  EMAIL_ADDRESS       - the Gmail address to send FROM (e.g. you@gmail.com)
  EMAIL_APP_PASSWORD  - a Gmail "App Password" (not your normal password)
  TO_EMAIL            - destination address (e.g. hadi@ftm8.com)
"""

import os
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import instaloader

ACCOUNTS = [
    "alisalhamad",
    "wroudnursery",
    "yasminfarms",
    "f7m77772020",
    "wafra_farm",
    "albohayra",
]

LOOKBACK_DAYS = 7
MAX_POSTS_PER_ACCOUNT = 12  # how many recent posts to inspect per profile before filtering

# Only report posts that look related to plants, prices, or offers.
# Heuristic keyword match on the Arabic/English caption text.
RELEVANT_KEYWORDS = [
    # prices / offers
    "سعر", "أسعار", "عرض", "عروض", "خصم", "خصومات", "تخفيض", "ريال",
    "توصيل", "الطلب", "متوفر", "متوفره", "متوفرة", "كمية", "بالجملة",
    "price", "offer", "sale", "discount",
    # plants
    "نبات", "نباتات", "شتلة", "شتلات", "شجرة", "أشجار", "شجيرة",
    "زهرة", "زهور", "ورد", "نخيل", "فسائل", "بذور", "شتل", "مشتل",
    "plant", "seedling", "sapling",
]


def is_relevant(caption: str) -> bool:
    text = caption.lower()
    return any(kw.lower() in text for kw in RELEVANT_KEYWORDS)


def fetch_recent_posts(loader: instaloader.Instaloader, username: str):
    """Return a list of dicts for relevant posts within the lookback window, or raise."""
    profile = instaloader.Profile.from_username(loader.context, username)
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    recent = []
    for i, post in enumerate(profile.get_posts()):
        if i >= MAX_POSTS_PER_ACCOUNT:
            break
        post_date = post.date_utc.replace(tzinfo=timezone.utc)
        if post_date < cutoff:
            break
        caption = (post.caption or "").strip().replace("\n", " ")
        if not is_relevant(caption):
            continue
        if len(caption) > 100:
            caption = caption[:100] + "…"
        recent.append(
            {
                "date": post_date.strftime("%Y-%m-%d"),
                "caption": caption or "(بدون نص)",
                "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
                "image_url": post.url,  # direct link to the displayed image, for reference
            }
        )
    return recent


def build_account_section(username: str, loader: instaloader.Instaloader) -> str:
    try:
        posts = fetch_recent_posts(loader, username)
    except instaloader.exceptions.ProfileNotExistsException:
        return f"@{username}: الحساب غير موجود أو تم تغيير اسمه.\n"
    except Exception as exc:  # noqa: BLE001 - report any failure, don't crash the run
        return f"@{username}: تعذر الوصول (قد يكون إنستغرام حظر الطلب التلقائي).\n"

    if not posts:
        return ""  # nothing relevant this week — skip the account entirely, keep report short

    lines = [f"@{username}"]
    for p in posts:
        # image_url is a direct link to the displayed photo (expires after ~1-2 days);
        # post_url is the permanent Instagram post link, kept as a durable fallback.
        lines.append(
            f"- {p['date']} | {p['caption']} | صورة: {p['image_url']} | منشور: {p['post_url']}"
        )
    return "\n".join(lines) + "\n"


def build_report() -> str:
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sections = [f"جديد النباتات/الأسعار/العروض ({today})\n"]

    for username in ACCOUNTS:
        section = build_account_section(username, loader)
        if section.strip():
            sections.append(section)
        time.sleep(3)  # be gentle to reduce chance of getting rate-limited

    if len(sections) == 1:
        sections.append("لا جديد يخص النباتات أو الأسعار أو العروض هذا الأسبوع.")

    return "\n".join(sections)


def send_email(body: str) -> None:
    from_addr = os.environ["EMAIL_ADDRESS"]
    app_password = os.environ["EMAIL_APP_PASSWORD"]
    to_addr = os.environ["TO_EMAIL"]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "جديد النباتات والأسعار والعروض — منافسين إنستغرام"
    msg["From"] = from_addr
    msg["To"] = to_addr

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(from_addr, app_password)
        server.sendmail(from_addr, [to_addr], msg.as_string())


def main() -> None:
    report = build_report()
    print(report)  # also visible in the GitHub Actions run log
    send_email(report)


if __name__ == "__main__":
    main()
