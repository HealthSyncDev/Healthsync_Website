"""Serve public/ and POST /contact + /apply via the mailbox in .env."""
import hashlib
import hmac
import html
import json
import os
import random
import re
import smtplib
import threading
import time
from collections import defaultdict
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default as email_policy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_STATUS = frozenset({"Student", "Recent graduate", "Currently employed", "Other"})
_ROLE = frozenset({"Backend Intern"})
_REMOTE = frozenset({"Yes", "No"})
_RESUME_EXT = frozenset({".pdf", ".doc", ".docx"})
_URL = re.compile(r"^https?://[^\s]+$", re.I)
_SAFE_NAME = re.compile(r"^[\w.\- ()+]{1,120}$")

# ponytail: in-process only; put nginx/cloudflare in front for real DDoS
_rate_lock = threading.Lock()
_rate_hits = defaultdict(list)

def load_env(path=".env"):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def split_addrs(raw):
    return [part.strip() for part in (raw or "").split(",") if part.strip()]

def field(value, limit, header=True):
    text = str(value or "").strip()
    if header and ("\n" in text or "\r" in text):
        raise ValueError("bad field")
    if not text or len(text) > limit:
        raise ValueError("bad field")
    return text

def _esc(text):
    return html.escape(text).replace("\n", "<br>")

LABEL = "padding-bottom:8px;font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:#8a9bb0;"
VALUE = "font-size:15px;line-height:1.65;color:#182236;"


def _rule(gap):
    return (
        f'<tr><td style="padding:{gap} 44px 0;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid #e6edf5;font-size:0;line-height:0;"><tr><td>&nbsp;</td></tr></table>'
        f'</td></tr>'
    )

def enquiry_html(name, email, chosen, brief):
    reply = html.escape(email, quote=True)
    needs = " &nbsp;&middot;&nbsp; ".join(_esc(item.strip()) for item in chosen.split(",") if item.strip())
    sections = [("Needs", needs, 32)]
    if brief:
        sections.append((
            "Brief",
            f'<div style="background:#f5f8fc;border-radius:12px;padding:16px 18px;font-size:15px;line-height:1.7;color:#31415a;">{_esc(brief)}</div>',
            24,
        ))
    rows = "".join(
        _rule(gap) + f'<tr><td style="padding:16px 44px 0;"><div style="{LABEL}">{label}</div><div style="{VALUE}">{value}</div></td></tr>'
        for label, value, gap in sections
    )
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>New enquiry — HealthSync</title></head>
<body style="margin:0;padding:0;background:#eef2f7;">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{_esc(name)} &middot; {_esc(email)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#eef2f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
 <tr><td align="center" style="padding:44px 20px;">
 <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e4ebf3;border-radius:18px;">
 <tr><td height="5" style="height:5px;line-height:0;font-size:0;background:#00a8ff;background-image:linear-gradient(90deg,#1e327e 0%,#00a8ff 100%);">&nbsp;</td></tr>
 <tr><td style="padding:40px 44px 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
 <td width="34" height="34" align="center" valign="middle" bgcolor="#1e327e" style="width:34px;height:34px;border-radius:10px;color:#ffffff;font-size:15px;font-weight:700;line-height:34px;">H</td>
 <td style="padding-left:13px;font-size:13px;font-weight:700;letter-spacing:.26em;color:#1e327e;">HEALTHSYNC</td>
 <td align="right" style="font-size:12px;font-weight:500;letter-spacing:.02em;color:#9aa8ba;">healthsync.ae</td>
 </tr></table></td></tr>
 <tr><td style="padding:34px 44px 0;">
 <div style="padding-bottom:14px;font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#00a8ff;">New enquiry</div>
 <div style="font-size:30px;line-height:1.2;font-weight:600;letter-spacing:-.02em;color:#141f33;">{_esc(name)}</div>
 <div style="padding-top:10px;font-size:15px;line-height:1.6;color:#64748b;"><a href="mailto:{reply}" style="color:#0077b8;text-decoration:none;">{_esc(email)}</a></div>
 </td></tr>
 {rows}
 <tr><td style="padding:34px 44px 38px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid #e6edf5;"><tr>
 <td style="padding-top:18px;font-size:12px;line-height:1.6;color:#8a9bb0;">HealthSync &middot; healthsync.ae</td>
 <td align="right" style="padding-top:18px;font-size:12px;line-height:1.6;color:#aab6c4;">&copy; 2026 HealthSync</td>
 </tr></table></td></tr>
 </table></td></tr></table></body></html>"""

_NAME = re.compile(r"(?u)^[^\W\d_](?:[^\W\d_]|['’.-])*(?: [^\W\d_](?:[^\W\d_]|['’.-])*)+$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

def person_name(value):
    text = " ".join(str(value or "").split())
    if not _NAME.fullmatch(text) or len(text) > 200:
        raise ValueError("name")
    return text

def person_email(value):
    text = str(value or "").strip()
    if not _EMAIL.fullmatch(text) or len(text) > 200:
        raise ValueError("email")
    return text

def _smtp_send(msg, to_env="CONTACT_TO", cc_env="CONTACT_CC"):
    to = split_addrs(os.environ.get(to_env))
    cc = split_addrs(os.environ.get(cc_env) if cc_env else "")
    user = os.environ.get("SMTP_USER") or ""
    password = os.environ.get("SMTP_PASS") or ""
    host = os.environ.get("SMTP_HOST") or ""
    if not to or not user or not password or not host:
        raise RuntimeError("mail not configured")
    msg["From"] = user
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    port = int(os.environ.get("SMTP_PORT") or "465")
    # ponytail: one SMTP login per message; a pool only matters under real volume
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)
        smtp.starttls()
    try:
        smtp.login(user, password)
        smtp.send_message(msg)
    finally:
        smtp.quit()

def send_enquiry(data):
    name = person_name(data.get("name"))
    email = person_email(data.get("email"))
    brief = str(data.get("brief") or "").strip()
    needs = data.get("need") or []
    if not isinstance(needs, list) or not needs or len(needs) > 8 or len(brief) > 5000:
        raise ValueError("need")
    chosen = ", ".join(field(item, 80) for item in needs)
    msg = EmailMessage()
    msg["Reply-To"] = email
    msg["Subject"] = "HealthSync enquiry — " + chosen
    msg.set_content("\n".join([
        f"Name: {name}",
        f"Email: {email}",
        f"Needs: {chosen}",
        "",
        brief,
    ]))
    msg.add_alternative(enquiry_html(name, email, chosen, brief), subtype="html")
    _smtp_send(msg)

def optional_url(value, limit=300):
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > limit or not _URL.fullmatch(text):
        raise ValueError("url")
    return text

def _captcha_key():
    # ponytail: reuse SMTP_PASS as signing key until CAPTCHA_SECRET is set
    return (os.environ.get("CAPTCHA_SECRET") or os.environ.get("SMTP_PASS") or "healthsync").encode()

def issue_captcha():
    a, b = random.randint(2, 12), random.randint(2, 12)
    exp = int(time.time()) + 900
    payload = f"{a}.{b}.{a + b}.{exp}"
    sig = hmac.new(_captcha_key(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return {"a": a, "b": b, "token": f"{payload}.{sig}"}

def check_captcha(token, answer):
    try:
        a, b, expect, exp, sig = str(token or "").split(".")
        payload = f"{a}.{b}.{expect}.{exp}"
        want = hmac.new(_captcha_key(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(want, sig) or int(exp) < int(time.time()) or int(answer) != int(expect):
            raise ValueError("captcha")
    except (TypeError, ValueError):
        raise ValueError("captcha")

def rate_allow(key, limit, window):
    now = time.time()
    with _rate_lock:
        keep = [t for t in _rate_hits[key] if now - t < window]
        if len(keep) >= limit:
            _rate_hits[key] = keep
            return False
        keep.append(now)
        _rate_hits[key] = keep
        # ponytail: prune idle keys so the dict can't grow forever under IP churn
        if len(_rate_hits) > 5000:
            dead = [k for k, v in _rate_hits.items() if not v or now - v[-1] >= window]
            for k in dead[:2000]:
                _rate_hits.pop(k, None)
        return True

def parse_multipart(content_type, body):
    if len(content_type) > 200:
        raise ValueError("multipart")
    msg = message_from_bytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body,
        policy=email_policy,
    )
    fields, files = {}, {}
    if not msg.is_multipart():
        raise ValueError("multipart")
    parts = 0
    for part in msg.iter_parts():
        parts += 1
        if parts > 40:
            raise ValueError("parts")
        name = part.get_param("name", header="content-disposition")
        if not name or len(str(name)) > 64:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            if len(payload) > 5_000_000:
                raise ValueError("resume")
            files[str(name)] = (filename, payload, part.get_content_type() or "application/octet-stream")
        else:
            if len(payload) > 20_000:
                raise ValueError("field")
            fields[str(name)] = payload.decode("utf-8", errors="replace")
    return fields, files

def application_html(data):
    reply = html.escape(data["email"], quote=True)
    order = [
        ("Phone", data["phone"]),
        ("Location", data["location"]),
        ("Role", data["role"]),
        ("Status", data["status"]),
        ("Remote / flexible hours", data["remote"]),
        ("LinkedIn", data["linkedin"]),
        ("GitHub / portfolio", data["portfolio"] or "-"),
        ("Resume", data["resume_name"]),
        ("AI tools & verification", data["ai_tools"]),
        ("Salary expectation (INR)", data["salary"]),
    ]
    rows = "".join(
        _rule(24 if i else 32)
        + f'<tr><td style="padding:16px 44px 0;"><div style="{LABEL}">{label}</div><div style="{VALUE}">{_esc(value)}</div></td></tr>'
        for i, (label, value) in enumerate(order)
    )
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>New application — HealthSync</title></head>
<body style="margin:0;padding:0;background:#eef2f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#eef2f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
 <tr><td align="center" style="padding:44px 20px;">
 <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e4ebf3;border-radius:18px;">
 <tr><td height="5" style="height:5px;line-height:0;font-size:0;background:#00a8ff;background-image:linear-gradient(90deg,#1e327e 0%,#00a8ff 100%);">&nbsp;</td></tr>
 <tr><td style="padding:40px 44px 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
 <td width="34" height="34" align="center" valign="middle" bgcolor="#1e327e" style="width:34px;height:34px;border-radius:10px;color:#ffffff;font-size:15px;font-weight:700;line-height:34px;">H</td>
 <td style="padding-left:13px;font-size:13px;font-weight:700;letter-spacing:.26em;color:#1e327e;">HEALTHSYNC</td>
 <td align="right" style="font-size:12px;font-weight:500;color:#9aa8ba;">Application</td>
 </tr></table></td></tr>
 <tr><td style="padding:34px 44px 0;">
 <div style="padding-bottom:14px;font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#00a8ff;">New application</div>
 <div style="font-size:30px;line-height:1.2;font-weight:600;letter-spacing:-.02em;color:#141f33;">{_esc(data["name"])}</div>
 <div style="padding-top:10px;font-size:15px;line-height:1.6;color:#64748b;"><a href="mailto:{reply}" style="color:#0077b8;text-decoration:none;">{_esc(data["email"])}</a></div>
 </td></tr>
 {rows}
 <tr><td style="padding:34px 44px 38px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid #e6edf5;"><tr>
 <td style="padding-top:18px;font-size:12px;line-height:1.6;color:#8a9bb0;">HealthSync &middot; healthsync.ae</td>
 <td align="right" style="padding-top:18px;font-size:12px;line-height:1.6;color:#aab6c4;">&copy; 2026 HealthSync</td>
 </tr></table></td></tr>
 </table></td></tr></table></body></html>"""

def send_application(fields, files):
    check_captcha(fields.get("captcha_token"), fields.get("captcha"))
    name = person_name(fields.get("name"))
    email = person_email(fields.get("email"))
    phone = field(fields.get("phone"), 40)
    location = field(fields.get("location"), 120)
    linkedin = optional_url(fields.get("linkedin"))
    if not linkedin:
        raise ValueError("linkedin")
    portfolio = optional_url(fields.get("portfolio"))
    role = field(fields.get("role"), 40)
    status = field(fields.get("status"), 40)
    remote = field(fields.get("remote"), 8)
    if role not in _ROLE or status not in _STATUS or remote not in _REMOTE:
        raise ValueError("choice")
    ai_tools = field(fields.get("ai_tools"), 4000, header=False)
    salary = field(fields.get("salary"), 120)
    resume = files.get("resume")
    if not resume:
        raise ValueError("resume")
    resume_name, resume_bytes, resume_type = resume
    resume_name = os.path.basename(str(resume_name).replace("\\", "/")).strip() or "resume.pdf"
    if not _SAFE_NAME.fullmatch(resume_name):
        resume_name = f"resume{os.path.splitext(resume_name)[1].lower() or '.pdf'}"
    ext = os.path.splitext(resume_name)[1].lower()
    if ext not in _RESUME_EXT or not resume_bytes or len(resume_bytes) > 5_000_000:
        raise ValueError("resume")
    data = {
        "name": name, "email": email, "phone": phone, "location": location,
        "linkedin": linkedin, "portfolio": portfolio, "role": role, "status": status, "remote": remote,
        "ai_tools": ai_tools, "salary": salary, "resume_name": resume_name,
    }
    msg = EmailMessage()
    msg["Reply-To"] = email
    msg["Subject"] = f"HealthSync application — {role} — {name}"
    msg.set_content("\n".join([
        f"Name: {name}", f"Email: {email}", f"Phone: {phone}", f"Location: {location}",
        f"Role: {role}", f"Status: {status}", f"Remote: {remote}",
        f"LinkedIn: {linkedin}", f"Portfolio: {portfolio or '-'}",
        f"Salary: {salary}", f"Resume: {resume_name}", "",
        "AI tools:", ai_tools,
    ]))
    msg.add_alternative(application_html(data), subtype="html")
    main = {"application/pdf": "pdf", "application/msword": "doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"}.get(resume_type, "octet-stream")
    msg.add_attachment(resume_bytes, maintype="application", subtype=main, filename=resume_name)
    # ponytail: APPLY_TO only; no APPLY_CC until they ask
    _smtp_send(msg, to_env="APPLY_TO", cc_env="")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="public", **kwargs)

    def _client_ip(self):
        xff = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return (xff or self.client_address[0])[:64]

    def _discard(self, size):
        left = max(0, min(size, 5_200_000))
        while left > 0:
            chunk = self.rfile.read(min(65536, left))
            if not chunk:
                break
            left -= len(chunk)

    def _serve_apply(self):
        # inject captcha so mobile still shows the question if JS fetch is slow/blocked
        with open(os.path.join("public", "apply.html"), encoding="utf-8") as fh:
            page = fh.read()
        c = issue_captcha()
        q = f"What is {c['a']} + {c['b']}?"
        page = page.replace(
            'id="captcha-q">Loading…</p>',
            f'id="captcha-q" data-ready="1">{html.escape(q)}</p>',
            1,
        ).replace(
            'name="captcha_token" value=""',
            f'name="captcha_token" value="{html.escape(c["token"], quote=True)}"',
            1,
        )
        raw = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/apply-captcha":
                ip = self._client_ip()
                if not rate_allow(f"captcha:{ip}", 30, 600):
                    self._json(429, {"error": "too many"}, retry=60)
                    return
                self._json(200, issue_captcha())
                return
            if path in ("/apply", "/apply.html"):
                self._serve_apply()
                return
            return super().do_GET()
        except Exception as err:
            print("GET failed:", type(err).__name__, flush=True)
            self.send_error(500)

    def end_headers(self):
        # ponytail: one origin; add a list if more sites call this
        if self.headers.get("Origin") == "https://healthsync.ae":
            self.send_header("Access-Control-Allow-Origin", "https://healthsync.ae")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _json(self, code, body, retry=None):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if retry is not None:
            self.send_header("Retry-After", str(retry))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path not in ("/contact", "/apply"):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            size = 0
        limit = 5_200_000 if path == "/apply" else 20_000
        ip = self._client_ip()
        # rate-limit before reading the body so floods don't burn RAM
        bucket = (3, 900, 120) if path == "/apply" else (5, 600, 60)
        if not rate_allow(f"post:{path}:{ip}", bucket[0], bucket[1]):
            self._discard(size)
            self._json(429, {"error": "too many"}, retry=bucket[2])
            return
        if size <= 0 or size > limit:
            self._discard(size)
            self._json(400, {"error": "bad body"})
            return
        try:
            raw = self.rfile.read(size)
            if path == "/contact":
                data = json.loads(raw)
                if not isinstance(data, dict) or len(data) > 20:
                    raise ValueError("json")
                send_enquiry(data)
            else:
                ctype = self.headers.get("Content-Type") or ""
                if "multipart/form-data" not in ctype:
                    raise ValueError("multipart")
                fields, files = parse_multipart(ctype, raw)
                send_application(fields, files)
        except (json.JSONDecodeError, ValueError, UnicodeError):
            self._json(400, {"error": "bad field"})
        except Exception as err:
            print(path, "mail failed:", type(err).__name__, flush=True)
            self._json(502, {"error": "mail failed"})
        else:
            self._json(200, {"ok": True})

def _demo():
    assert split_addrs(" a@x.com, b@y.com ") == ["a@x.com", "b@y.com"]
    assert split_addrs("") == []
    try:
        field("a\nb", 20)
    except ValueError:
        pass
    else:
        raise SystemExit("newline accepted")
    body = enquiry_html("A&B", "a@b.com", "Claims", "line\n<script>")
    assert "&amp;" in body and "&lt;script&gt;" in body and "<br>" in body
    assert person_name("  Ada  Lovelace ") == "Ada Lovelace"
    assert person_email("ada@hospital.ae") == "ada@hospital.ae"
    for bad in ("adsaf", "Ada", "Ada 2"):
        try:
            person_name(bad)
        except ValueError:
            pass
        else:
            raise SystemExit(bad)
    for bad in ("a@b", "ada@hospital", "ada @x.com"):
        try:
            person_email(bad)
        except ValueError:
            pass
        else:
            raise SystemExit(bad)
    assert optional_url("") == ""
    assert optional_url("https://github.com/x") == "https://github.com/x"
    try:
        optional_url("not-a-url")
    except ValueError:
        pass
    else:
        raise SystemExit("bad url")
    c = issue_captcha()
    check_captcha(c["token"], str(c["a"] + c["b"]))
    try:
        check_captcha(c["token"], "0")
    except ValueError:
        pass
    else:
        raise SystemExit("bad captcha")
    assert rate_allow("t:demo", 2, 60) and rate_allow("t:demo", 2, 60)
    assert not rate_allow("t:demo", 2, 60)
    # multipart smoke
    boundary = "----hs"
    sample = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\nAda Lovelace\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"resume\"; filename=\"cv.pdf\"\r\n"
        f"Content-Type: application/pdf\r\n\r\n%PDF\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    fields, files = parse_multipart(f"multipart/form-data; boundary={boundary}", sample)
    assert fields["name"] == "Ada Lovelace" and files["resume"][0] == "cv.pdf"

if __name__ == "__main__":
    _demo()
    load_env()
    print("http://127.0.0.1:5174", flush=True)
    try:
        ThreadingHTTPServer(("0.0.0.0", 5174), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
