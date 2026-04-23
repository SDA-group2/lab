import os
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


MZINGA_BASE_URL = os.getenv("MZINGA_BASE_URL", "http://localhost:3000").rstrip("/")
MZINGA_EMAIL = os.getenv("MZINGA_EMAIL")
MZINGA_PASSWORD = os.getenv("MZINGA_PASSWORD")

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "3"))

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@example.com")


class MzingaApiClient:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.token: str | None = None
        self.session = requests.Session()

    def login(self) -> None:
        url = f"{self.base_url}/api/users/login"
        response = self.session.post(
            url,
            json={
                "email": self.email,
                "password": self.password,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("token")
        if not token:
            raise RuntimeError("Login riuscito ma token mancante nella risposta.")

        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print("Autenticazione REST API completata.")

    def request(self, method: str, path: str, retry_on_401: bool = True, **kwargs) -> requests.Response:
        if not self.token:
            self.login()

        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, timeout=30, **kwargs)

        if response.status_code == 401 and retry_on_401:
            print("Token scaduto o non valido. Riprovo autenticazione...")
            self.login()
            return self.request(method, path, retry_on_401=False, **kwargs)

        response.raise_for_status()
        return response

    def get_pending_communications(self) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            "/api/communications",
            params={
                "where[status][equals]": "pending",
                "depth": 1,
            },
        )
        data = response.json()
        return data.get("docs", [])

    def get_communication(self, communication_id: str) -> dict[str, Any]:
        response = self.request(
            "GET",
            f"/api/communications/{communication_id}",
            params={"depth": 1},
        )
        return response.json()

    def update_status(self, communication_id: str, status: str) -> None:
        self.request(
            "PATCH",
            f"/api/communications/{communication_id}",
            json={"status": status},
        )


def extract_emails(relationship_items: list[dict[str, Any]] | None) -> list[str]:
    if not relationship_items:
        return []

    emails: list[str] = []

    for item in relationship_items:
        value = item.get("value")
        if isinstance(value, dict):
            email = value.get("email")
            if email:
                emails.append(email)

    return emails


def slate_to_html(nodes: list[dict[str, Any]] | None) -> str:
    if not nodes:
        return ""

    return "".join(render_slate_node(node) for node in nodes)


def render_slate_node(node: dict[str, Any]) -> str:
    if "text" in node:
        text = node.get("text", "")
        if node.get("bold"):
            text = f"<strong>{text}</strong>"
        if node.get("italic"):
            text = f"<em>{text}</em>"
        if node.get("underline"):
            text = f"<u>{text}</u>"
        return text

    children = "".join(render_slate_node(child) for child in node.get("children", []))
    node_type = node.get("type")

    if node_type == "paragraph":
        return f"<p>{children}</p>"
    if node_type == "h1":
        return f"<h1>{children}</h1>"
    if node_type == "h2":
        return f"<h2>{children}</h2>"
    if node_type == "h3":
        return f"<h3>{children}</h3>"
    if node_type == "ul":
        return f"<ul>{children}</ul>"
    if node_type == "ol":
        return f"<ol>{children}</ol>"
    if node_type == "li":
        return f"<li>{children}</li>"
    if node_type == "link":
        url = node.get("url", "#")
        return f'<a href="{url}">{children}</a>'

    return children


def send_email(
    subject: str,
    html_body: str,
    to_emails: list[str],
    cc_emails: list[str],
    bcc_emails: list[str],
) -> None:
    if not to_emails and not cc_emails and not bcc_emails:
        raise ValueError("Nessun destinatario trovato.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    if to_emails:
        msg["To"] = ", ".join(to_emails)
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    plain_body = "Questa email contiene contenuto HTML."
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    all_recipients = to_emails + cc_emails + bcc_emails

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_USE_TLS:
            server.starttls()

        if SMTP_USERNAME and SMTP_PASSWORD:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)

        server.sendmail(SMTP_FROM, all_recipients, msg.as_string())


def process_communication(api_client: MzingaApiClient, communication: dict[str, Any]) -> None:
    communication_id = communication["id"]
    print(f"Processo communication {communication_id}...")

    api_client.update_status(communication_id, "processing")

    full_doc = api_client.get_communication(communication_id)

    to_emails = extract_emails(full_doc.get("tos"))
    cc_emails = extract_emails(full_doc.get("ccs"))
    bcc_emails = extract_emails(full_doc.get("bccs"))

    subject = full_doc.get("subject", "(senza oggetto)")
    body = full_doc.get("body")
    html_body = slate_to_html(body)

    send_email(
        subject=subject,
        html_body=html_body,
        to_emails=to_emails,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
    )

    api_client.update_status(communication_id, "sent")
    print(f"Communication {communication_id} inviata con successo.")


def validate_env() -> None:
    missing = []

    if not MZINGA_EMAIL:
        missing.append("MZINGA_EMAIL")
    if not MZINGA_PASSWORD:
        missing.append("MZINGA_PASSWORD")

    if missing:
        raise RuntimeError(f"Variabili mancanti nel .env: {', '.join(missing)}")


def main() -> None:
    validate_env()

    api_client = MzingaApiClient(
        base_url=MZINGA_BASE_URL,
        email=MZINGA_EMAIL,
        password=MZINGA_PASSWORD,
    )

    print("Worker REST API avviato.")

    while True:
        try:
            pending_docs = api_client.get_pending_communications()

            if not pending_docs:
                print(f"Nessuna communication pending. Riprovo tra {POLL_INTERVAL_SECONDS} secondi...")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            print(f"Trovate {len(pending_docs)} communication pending.")

            for communication in pending_docs:
                communication_id = communication.get("id")
                try:
                    process_communication(api_client, communication)
                except Exception as exc:
                    print(f"Errore durante il processing di {communication_id}: {exc}")
                    try:
                        api_client.update_status(communication_id, "failed")
                    except Exception as patch_exc:
                        print(f"Impossibile aggiornare lo status a failed per {communication_id}: {patch_exc}")

        except Exception as exc:
            print(f"Errore nel loop principale: {exc}")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()