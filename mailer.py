#!/usr/bin/env python3
"""Optionaler E-Mail-Versand des Tagesergebnisses.

No-op, wenn die nötigen Umgebungsvariablen fehlen – so bricht der Workflow
nicht, solange kein Mailversand konfiguriert ist.

Benötigte Variablen (als GitHub-Secrets hinterlegen, um Mail zu aktivieren):
  MAIL_TO     Empfänger (Komma-getrennt für mehrere)
  MAIL_FROM   Absenderadresse (oft = SMTP_USER)
  SMTP_HOST   z.B. smtp.gmail.com
  SMTP_PORT   z.B. 465 (SSL) oder 587 (STARTTLS); Standard 465
  SMTP_USER   SMTP-Benutzername
  SMTP_PASS   SMTP-Passwort bzw. App-Passwort (bei Gmail zwingend App-Passwort)
Optional:
  PAGES_URL   öffentliche URL der Website – wird in die Mail eingebettet
"""

from __future__ import annotations
import os
import ssl
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

OUT_DIR = Path(os.environ.get("OUT_DIR", "docs"))


def main() -> int:
    to = os.environ.get("MAIL_TO", "").strip()
    if not to:
        print("Mailversand übersprungen (MAIL_TO nicht gesetzt).")
        return 0

    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    if not (host and user and pw):
        print("Mailversand übersprungen (SMTP_HOST/SMTP_USER/SMTP_PASS unvollständig).",
              file=sys.stderr)
        return 0

    sender = os.environ.get("MAIL_FROM", user).strip()
    port = int(os.environ.get("SMTP_PORT", "465"))
    pages_url = os.environ.get("PAGES_URL", "").strip()

    html_path = OUT_DIR / "index.html"
    if not html_path.exists():
        print("Keine index.html gefunden – nichts zu versenden.", file=sys.stderr)
        return 1
    html = html_path.read_text(encoding="utf-8")

    if pages_url:
        banner = (f'<p style="font:14px sans-serif;background:#eef4f4;padding:10px 14px;'
                  f'border-left:4px solid #008b8b;">Online-Version: '
                  f'<a href="{pages_url}">{pages_url}</a></p>')
        html = html.replace("<body>", "<body>" + banner, 1)

    msg = EmailMessage()
    import datetime as dt
    msg["Subject"] = f"Policy Radar – Tagesscan {dt.date.today():%d.%m.%Y}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("Der Policy-Radar-Tagesscan liegt vor. "
                    "Diese E-Mail benötigt einen HTML-fähigen Client.")
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, pw)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=ctx)
            s.login(user, pw)
            s.send_message(msg)

    print(f"Mail an {to} versendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
