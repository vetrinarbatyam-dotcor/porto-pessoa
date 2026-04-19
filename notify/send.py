"""Dispatch the weekly summary via WhatsApp + Gmail (using existing Claude skills)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NOTIFY_WHATSAPP_NUMBER, NOTIFY_GMAIL_ADDRS
from notify.summary import build

CLAUDE_CMD = "claude"


def _claude_prompt(prompt: str, timeout: int = 120) -> str:
    r = subprocess.run(
        [CLAUDE_CMD, "-p", prompt, "--permission-mode", "bypassPermissions"],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8",
    )
    return r.stdout


def send_whatsapp(text: str):
    prompt = (
        f"Use the `whatsapp` skill to send this message to phone {NOTIFY_WHATSAPP_NUMBER}:\n\n"
        f"---\n{text}\n---\n\n"
        "Just send it. No summary, no commentary, no asking. "
        "After sending, reply with only: SENT or FAIL: <reason>."
    )
    return _claude_prompt(prompt)


def send_gmail(subject: str, html: str):
    addrs = ",".join(NOTIFY_GMAIL_ADDRS)
    prompt = (
        f"Use the `gmail` skill to send an HTML email.\n"
        f"To: {addrs}\nSubject: {subject}\n"
        f"html: (the full HTML content below, passed as the `html` param)\n\n"
        f"---\n{html}\n---\n\n"
        "Just send it. No summary, no asking. Reply only with: SENT or FAIL: <reason>."
    )
    return _claude_prompt(prompt)


def main():
    s = build()
    print("[notify] WhatsApp…")
    print(send_whatsapp(s["text"]))
    print("[notify] Gmail…")
    print(send_gmail(s["subject"], s["html"]))


if __name__ == "__main__":
    main()
