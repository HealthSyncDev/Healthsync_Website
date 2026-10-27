"""Serve public/ and POST /contact + /apply via the mailbox in .env."""
import html
import json
import os
import re
import smtplib
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default as email_policy
from http.server import HTTPServer, SimpleHTTPRequestHandler

_STATUS = frozenset({"Student", "Recent graduate", "Currently employed", "Other"})
_ROLE = frozenset({"Backend Developer", "Frontend Developer"})
_REMOTE = frozenset({"Yes", "No"})
_RESUME_EXT = frozenset({".pdf", ".doc", ".docx"})
_URL = re.compile(r"^https?://[^\s]+$", re.I)

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

def parse_multipart(content_type, body):
    msg = message_from_bytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body,
        policy=email_policy,
    )
    fields, files = {}, {}
    if not msg.is_multipart():
        raise ValueError("multipart")
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = (filename, payload, part.get_content_type() or "application/octet-stream")
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
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
        ("Stack", data["stack"]),
        ("Project / problem", data["project"]),
        ("API investigation", data["debug"]),
        ("AI tools & verification", data["ai_tools"]),
        ("Why healthcare", data["why_health"]),
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
    stack = field(fields.get("stack"), 4000, header=False)
    project = field(fields.get("project"), 5000, header=False)
    debug = field(fields.get("debug"), 5000, header=False)
    ai_tools = field(fields.get("ai_tools"), 4000, header=False)
    why_health = field(fields.get("why_health"), 4000, header=False)
    resume = files.get("resume")
    if not resume:
        raise ValueError("resume")
    resume_name, resume_bytes, resume_type = resume
    resume_name = os.path.basename(resume_name.replace("\\", "/")).strip() or "resume.pdf"
    ext = os.path.splitext(resume_name)[1].lower()
    if ext not in _RESUME_EXT or not resume_bytes or len(resume_bytes) > 5_000_000:
        raise ValueError("resume")
    data = {
        "name": name, "email": email, "phone": phone, "location": location,
        "linkedin": linkedin, "portfolio": portfolio, "role": role, "status": status, "remote": remote,
        "stack": stack, "project": project, "debug": debug, "ai_tools": ai_tools,
        "why_health": why_health, "resume_name": resume_name,
    }
    msg = EmailMessage()
    msg["Reply-To"] = email
    msg["Subject"] = f"HealthSync application — {role} — {name}"
    msg.set_content("\n".join([
        f"Name: {name}", f"Email: {email}", f"Phone: {phone}", f"Location: {location}",
        f"Role: {role}", f"Status: {status}", f"Remote: {remote}",
        f"LinkedIn: {linkedin}", f"Portfolio: {portfolio or '-'}",
        f"Resume: {resume_name}", "",
        "Stack:", stack, "", "Project:", project, "", "API debug:", debug, "",
        "AI tools:", ai_tools, "", "Why healthcare:", why_health,
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

    def do_GET(self):
        # ponytail: pretty path only; file stays apply.html
        if self.path.split("?", 1)[0].rstrip("/") == "/apply":
            self.path = "/apply.html"
        return super().do_GET()

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

    def _json(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
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
        if size <= 0 or size > limit:
            self._json(400, {"error": "bad body"})
            return
        raw = self.rfile.read(size)
        try:
            if path == "/contact":
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("json")
                send_enquiry(data)
            else:
                ctype = self.headers.get("Content-Type") or ""
                if "multipart/form-data" not in ctype:
                    raise ValueError("multipart")
                fields, files = parse_multipart(ctype, raw)
                send_application(fields, files)
        except (json.JSONDecodeError, ValueError):
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
        HTTPServer(("0.0.0.0", 5174), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
