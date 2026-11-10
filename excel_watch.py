# -*- coding: utf-8 -*-
"""
مراقبة ملف عرض السعر على OneDrive وإرسال تنبيه تيليغرام عند أي تغيير.
يقرأ الملف فقط ولا يعدّل فيه أي شيء.
"""
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from openpyxl import load_workbook

SHARE_URL = os.environ.get(
    "SHARE_URL",
    "https://1drv.ms/x/c/7F0561B6990FF3B8/IQCwOfuGSU5rQZXj69lFkJBYAQxZWNMza8gnqyMndX2zA_g",
)
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_DIR = ".excel_watch_state"
STATE_FILE = os.path.join(STATE_DIR, "snapshot.json")
FAIL_FILE = os.path.join(STATE_DIR, "download_failed")
TOTAL_CELL = "E48"
MAX_LINES = 30
KW = timezone(timedelta(hours=3))


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )
    print("Telegram:", r.status_code)


def download():
    enc = base64.urlsafe_b64encode(SHARE_URL.encode()).decode().rstrip("=")
    urls = [
        f"https://api.onedrive.com/v1.0/shares/u!{enc}/root/content",
        f"https://api.onedrive.com/v1.0/shares/u!{enc}/driveItem/content",
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=60, allow_redirects=True)
            print(u[:60], "->", r.status_code, len(r.content))
            if r.ok and r.content[:2] == b"PK":
                with open("watched.xlsx", "wb") as f:
                    f.write(r.content)
                return True
        except Exception as ex:
            print("error:", ex)

    # الطريقة الثانية: نفس الطريقة التي يستخدمها موقع OneDrive لفتح الرابط بدون تسجيل دخول
    try:
        t = requests.post(
            "https://api-badgerp.svc.ms/v1.0/token",
            json={"appId": "5cbed6ac-a083-4e14-b191-b4ba07653de2"},
            timeout=30,
        )
        print("badger token ->", t.status_code)
        token = t.json()["token"]
        h = {"Authorization": f"Badger {token}", "Prefer": "autoredeem"}
        m = requests.get(f"https://api.onedrive.com/v1.0/shares/u!{enc}/driveitem",
                         headers=h, timeout=60)
        print("badger item ->", m.status_code)
        dl = m.json().get("@content.downloadUrl")
        if not dl:
            item = m.json()
            drive = item.get("parentReference", {}).get("driveId")
            if drive and item.get("id"):
                c = requests.get(
                    f"https://api.onedrive.com/v1.0/drives/{drive}/items/{item['id']}/content",
                    headers=h, timeout=60, allow_redirects=True)
                print("badger content ->", c.status_code, len(c.content))
                if c.ok and c.content[:2] == b"PK":
                    with open("watched.xlsx", "wb") as f:
                        f.write(c.content)
                    return True
            return False
        r = requests.get(dl, timeout=60)
        print("badger download ->", r.status_code, len(r.content))
        if r.ok and r.content[:2] == b"PK":
            with open("watched.xlsx", "wb") as f:
                f.write(r.content)
            return True
    except Exception as ex:
        print("badger error:", ex)
    return False


def fmt(v):
    if v is None or v == "":
        return "(فارغ)"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (int, float)):
        return f"{v:,}"
    return str(v)


def snapshot():
    wb = load_workbook("watched.xlsx", data_only=True)
    data = {}
    for ws in wb.worksheets:
        cells = {}
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None and c.value != "":
                    v = c.value
                    if isinstance(v, datetime):
                        v = v.strftime("%Y/%m/%d")
                    cells[c.coordinate] = v
        data[ws.title] = cells
    return data


def header_for(cells, coord):
    col = "".join(ch for ch in coord if ch.isalpha())
    row = int("".join(ch for ch in coord if ch.isdigit()))
    h = cells.get(f"{col}{47 if row > 47 else 5}")
    return str(h) if h else col


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    now = datetime.now(KW).strftime("%Y/%m/%d %H:%M")

    if not download():
        if not os.path.exists(FAIL_FILE):
            send("⚠️ تعذّر فتح ملف عرض السعر من رابط OneDrive.\n"
                 "تأكد أن الرابط ما زال يعمل ومشاركته مفتوحة لأي شخص.")
            open(FAIL_FILE, "w").close()
        sys.exit(1)
    if os.path.exists(FAIL_FILE):
        os.remove(FAIL_FILE)

    new = snapshot()

    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False)
        first = next(iter(new.values()), {})
        send("✅ بدأت مراقبة ملف عرض السعر.\n"
             "سيصلك تنبيه هنا عند أي تغيير (الفحص كل ساعتين).\n"
             f"💰 الإجمالي الحالي: {fmt(first.get(TOTAL_CELL))}\n🕒 {now}")
        return

    with open(STATE_FILE, encoding="utf-8") as f:
        old = json.load(f)

    lines = []
    for sheet in sorted(set(old) | set(new)):
        o, n = old.get(sheet, {}), new.get(sheet, {})
        for coord in sorted(set(o) | set(n), key=lambda k: (int("".join(ch for ch in k if ch.isdigit())), k)):
            if coord == TOTAL_CELL:
                continue
            ov, nv = o.get(coord), n.get(coord)
            if ov != nv:
                row = "".join(ch for ch in coord if ch.isdigit())
                label = f"• {header_for(n or o, coord)} – صف {row}: "
                if ov in (None, ""):
                    lines.append(label + f"أُضيف {fmt(nv)}")
                elif nv in (None, ""):
                    lines.append(label + f"حُذف {fmt(ov)}")
                else:
                    lines.append(label + f"كان {fmt(ov)}، أصبح {fmt(nv)}")

    if lines:
        first = next(iter(new.values()), {})
        t_old = old.get(next(iter(old)), {}).get(TOTAL_CELL)
        t_new = first.get(TOTAL_CELL)
        diff = ""
        if isinstance(t_old, (int, float)) and isinstance(t_new, (int, float)) and t_new != t_old:
            d = t_new - t_old
            diff = f" ({'+' if d > 0 else '-'}{fmt(abs(d))})"
        extra = f"\n… و{len(lines) - MAX_LINES} تغيير آخر" if len(lines) > MAX_LINES else ""
        send("📝 تغييرات جديدة في ملف عرض السعر\n\n"
             + "\n".join(lines[:MAX_LINES]) + extra
             + f"\n\n💰 الإجمالي قبل: {fmt(t_old)}"
             + f"\n💰 الإجمالي بعد: {fmt(t_new)}{diff}"
             + f"\n🕒 {now}")
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False)
    else:
        print("No changes.")


if __name__ == "__main__":
    main()
