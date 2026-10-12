import hashlib
import json
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent


def load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key == "MINIMOTH_API_KEY":
                os.environ[key] = value
            elif key and not os.environ.get(key, "").strip():
                os.environ[key] = value


load_env()
DB_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "finance.sqlite3"))


def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                phone TEXT NOT NULL UNIQUE,
                minimoth_identity_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                category TEXT NOT NULL,
                date TEXT NOT NULL
            );
        """)


def normalize_phone(value):
    if not isinstance(value, str):
        raise ValueError("Enter a valid phone number, including country code if needed.")
    digits = re.sub(r"[\s()-]", "", value)
    if re.fullmatch(r"[6-9]\d{9}", digits):
        return "+91" + digits
    if re.fullmatch(r"\+[1-9]\d{7,14}", digits):
        return digits
    raise ValueError("Enter a valid phone number, including country code if needed.")


def minimoth_request(path, payload):
    api_key = os.environ.get("MINIMOTH_API_KEY", "").strip()
    if not api_key or api_key == "mm_test_replace_with_your_project_key":
        raise RuntimeError("Set MINIMOTH_API_KEY in backend/.env before using OTP sign-in.")
    request = urllib.request.Request(
        "https://api.minimoth.dev/v1/otp/" + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            details = json.loads(error.read().decode("utf-8"))
            message = details.get("message") or details.get("error")
        except (ValueError, AttributeError):
            message = None
        raise ValueError(message or "MiniMoth could not complete the OTP request.") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("Could not reach MiniMoth. Check your network and try again.") from error


class ApiHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10_000:
                raise ValueError("Request body is too large.")
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as error:
            raise ValueError("Send a valid JSON request.") from error
        if not isinstance(data, dict):
            raise ValueError("Send a JSON object.")
        return data

    def authenticated_user(self):
        header = self.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with connect_db() as db:
            row = db.execute("""
                SELECT users.id FROM sessions JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.created_at > ?
            """, (token_hash, (datetime.now(timezone.utc) - timedelta(days=30)).isoformat())).fetchone()
        return row["id"] if row else None

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self.read_json()
            if path == "/api/auth/otp/send":
                phone = normalize_phone(data.get("phone", ""))
                result = minimoth_request("send", {"phone": phone})
                self.send_json(200, {"otp_id": result.get("otp_id"), "expires_at": result.get("expires_at")})
                return
            if path == "/api/auth/otp/verify":
                phone = normalize_phone(data.get("phone", ""))
                code = str(data.get("code", "")).strip()
                if not re.fullmatch(r"\d{6}", code):
                    raise ValueError("Enter the 6-digit code you received.")
                result = minimoth_request("verify", {"phone": phone, "code": code})
                identity_id = result.get("identity_id")
                if not identity_id:
                    raise ValueError("MiniMoth did not confirm this code. Check it and try again.")
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                with connect_db() as db:
                    db.execute("INSERT INTO users (phone, minimoth_identity_id) VALUES (?, ?) ON CONFLICT(phone) DO UPDATE SET minimoth_identity_id = excluded.minimoth_identity_id", (phone, identity_id))
                    user_id = db.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()["id"]
                    db.execute("INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)", (token_hash, user_id, datetime.now(timezone.utc).isoformat()))
                self.send_json(200, {"token": token, "phone": phone})
                return
            if path == "/api/transactions":
                user_id = self.authenticated_user()
                if user_id is None:
                    self.send_json(401, {"error": "Please sign in again."})
                    return
                description = str(data.get("description", "")).strip()
                category = str(data.get("category", "")).strip()
                transaction_type = data.get("type")
                try:
                    amount = float(data.get("amount"))
                except (TypeError, ValueError):
                    raise ValueError("Enter an amount greater than zero.")
                if not description or len(description) > 80:
                    raise ValueError("Description must be between 1 and 80 characters.")
                if not category or len(category) > 32:
                    raise ValueError("Choose a valid category.")
                if transaction_type not in ("income", "expense"):
                    raise ValueError("Choose income or expense.")
                if not 0 < amount <= 1_000_000_000:
                    raise ValueError("Amount must be greater than zero and at most 1,000,000,000.")
                with connect_db() as db:
                    cursor = db.execute("INSERT INTO transactions (user_id, description, amount, type, category, date) VALUES (?, ?, ?, ?, ?, ?)", (user_id, description, amount, transaction_type, category, date.today().isoformat()))
                self.send_json(201, {"id": cursor.lastrowid})
                return
            self.send_json(404, {"error": "Endpoint not found."})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(503, {"error": str(error)})
        except Exception:
            self.send_json(500, {"error": "Server error. Please try again."})

    def do_GET(self):
        if urlparse(self.path).path != "/api/transactions":
            self.send_json(404, {"error": "Endpoint not found."})
            return
        user_id = self.authenticated_user()
        if user_id is None:
            self.send_json(401, {"error": "Please sign in again."})
            return
        with connect_db() as db:
            rows = db.execute("SELECT id, description, amount, type, category, date FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,)).fetchall()
        self.send_json(200, {"transactions": [dict(row) for row in rows]})

    def do_DELETE(self):
        match = re.fullmatch(r"/api/transactions/(\d+)", urlparse(self.path).path)
        if not match:
            self.send_json(404, {"error": "Endpoint not found."})
            return
        user_id = self.authenticated_user()
        if user_id is None:
            self.send_json(401, {"error": "Please sign in again."})
            return
        with connect_db() as db:
            cursor = db.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (int(match.group(1)), user_id))
        if cursor.rowcount == 0:
            self.send_json(404, {"error": "Transaction not found."})
        else:
            self.send_json(200, {"deleted": True})

    def log_message(self, format_string, *args):
        print(f"{self.log_date_time_string()} {self.address_string()} {format_string % args}")


if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"Personal Finance API running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()