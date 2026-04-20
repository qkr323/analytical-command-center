"""
sync_from_email.py — Download broker statement PDFs from Gmail and upload to portfolio tracker.

Supported brokers:
  - Futu HK  (no_reply@stmt.futuhk.com)  → account_id=2
  - SoFi HK  (no-reply@sofi.hk)          → account_id=4

SETUP (one-time):
  1. Go to https://console.cloud.google.com
  2. Create a project → Enable Gmail API
  3. Create OAuth 2.0 credentials (Desktop app) → download as gmail_credentials.json
     and place it in this directory (backend/)
  4. Install dependencies (outside the main venv or inside — both work):
       pip install google-auth-oauthlib google-api-python-client requests
  5. First run will open a browser to authenticate sam.sanghyunpark@gmail.com.
     A gmail_token.json is saved so future runs don't need the browser.

USAGE:
  Make sure the local backend is running (port 8001), then:
    python sync_from_email.py

  The script will:
    - Find any new (unlabelled) statement emails from Futu/SoFi
    - Download the PDF attachment
    - POST it to /upload/statement
    - Label the email "portfolio-synced" so it's skipped next time
"""

import base64
import os
import sys
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── Config ─────────────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent / ".env")

BACKEND_URL = "http://localhost:8001"
API_KEY = os.environ.get("API_SECRET", "")

# Gmail OAuth2 scope — modify allows labelling processed emails
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CREDS_FILE = Path(__file__).parent / "gmail_credentials.json"
TOKEN_FILE  = Path(__file__).parent / "gmail_token.json"

PROCESSED_LABEL_NAME = "portfolio-synced"

# email sender → (broker slug, account_id)
BROKER_MAP: dict[str, tuple[str, int]] = {
    "no_reply@stmt.futuhk.com": ("futu",  2),
    "no-reply@sofi.hk":         ("sofi",  4),
}

# ── Gmail auth ─────────────────────────────────────────────────────────────────

def _get_service():
    if not CREDS_FILE.exists():
        sys.exit(
            f"[ERROR] {CREDS_FILE} not found.\n"
            "Download OAuth2 Desktop credentials from Google Cloud Console "
            "and save as backend/gmail_credentials.json"
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Label helpers ───────────────────────────────────────────────────────────────

def _get_or_create_label(service, name: str) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == name:
            return label["id"]
    created = service.users().labels().create(
        userId="me", body={"name": name, "labelListVisibility": "labelHide"}
    ).execute()
    return created["id"]


# ── Email helpers ───────────────────────────────────────────────────────────────

def _get_header(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_sender_email(from_header: str) -> str:
    """'Futu HK <no_reply@stmt.futuhk.com>' → 'no_reply@stmt.futuhk.com'"""
    if "<" in from_header:
        return from_header.split("<")[1].strip(">").strip().lower()
    return from_header.strip().lower()


def _get_pdf_attachments(service, msg_id: str, payload: dict) -> list[tuple[str, bytes]]:
    """Walk MIME parts and return list of (filename, pdf_bytes)."""
    results = []

    def _walk(parts):
        for part in parts:
            mime = part.get("mimeType", "")
            filename = part.get("filename", "")
            subparts = part.get("parts", [])

            if subparts:
                _walk(subparts)
                continue

            is_pdf = mime == "application/pdf" or filename.lower().endswith(".pdf")
            att_id = part.get("body", {}).get("attachmentId")

            if is_pdf and att_id:
                att = service.users().messages().attachments().get(
                    userId="me", messageId=msg_id, id=att_id
                ).execute()
                data = base64.urlsafe_b64decode(att["data"])
                results.append((filename or f"statement_{msg_id}.pdf", data))

    _walk(payload.get("parts", []))
    return results


# ── Upload helper ───────────────────────────────────────────────────────────────

def _upload_pdf(pdf_bytes: bytes, filename: str, broker: str, account_id: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                f"{BACKEND_URL}/upload/statement",
                headers={"X-API-Key": API_KEY},
                data={"broker": broker, "account_id": str(account_id)},
                files={"file": (filename, f, "application/pdf")},
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()
    finally:
        os.unlink(tmp_path)


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        sys.exit("[ERROR] API_SECRET not found in .env")

    # Check local backend is reachable
    try:
        requests.get(f"{BACKEND_URL}/health", timeout=5)
    except requests.exceptions.ConnectionError:
        sys.exit(
            "[ERROR] Local backend not reachable at http://localhost:8001\n"
            "Start it first: python -m uvicorn main:app --port 8001"
        )

    service = _get_service()
    processed_label_id = _get_or_create_label(service, PROCESSED_LABEL_NAME)

    # Search for unprocessed statement emails
    senders_query = " OR ".join(f"from:{e}" for e in BROKER_MAP)
    query = f"({senders_query}) has:attachment -label:{PROCESSED_LABEL_NAME}"
    result = service.users().messages().list(userId="me", q=query).execute()
    messages = result.get("messages", [])

    if not messages:
        print("No new statement emails found.")
        return

    print(f"Found {len(messages)} new statement email(s).\n")
    synced = 0

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        from_header = _get_header(msg, "from")
        subject     = _get_header(msg, "subject")
        sender      = _extract_sender_email(from_header)
        broker_info = BROKER_MAP.get(sender)

        print(f"Email: {subject}")
        print(f"  From: {sender}")

        if not broker_info:
            print(f"  Skipping — sender not in BROKER_MAP\n")
            continue

        broker, account_id = broker_info
        pdfs = _get_pdf_attachments(service, msg_id, msg["payload"])

        if not pdfs:
            print(f"  No PDF attachments found — skipping\n")
            continue

        all_ok = True
        for filename, pdf_bytes in pdfs:
            print(f"  Uploading {filename} ({broker}, account_id={account_id}) ...", end=" ")
            try:
                result = _upload_pdf(pdf_bytes, filename, broker, account_id)
                pos = result.get("positions_updated", 0) + result.get("positions_imported", 0)
                tx  = result.get("transactions_imported", 0)
                print(f"OK — {pos} positions, {tx} transactions")
            except requests.HTTPError as e:
                print(f"FAILED ({e})")
                all_ok = False
            except Exception as e:
                print(f"FAILED ({e})")
                all_ok = False

        if all_ok:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"addLabelIds": [processed_label_id]},
            ).execute()
            print(f"  Labelled as '{PROCESSED_LABEL_NAME}'")
            synced += 1

        print()

    print(f"Done — {synced}/{len(messages)} email(s) processed successfully.")


if __name__ == "__main__":
    main()
