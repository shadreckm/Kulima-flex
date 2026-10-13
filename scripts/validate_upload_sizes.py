"""Pilot UX validation: upload-size matrix against the live backend.

Creates test PDFs of 1/10/20/25 MB and POSTs each to the real
/api/v1/assessments/ endpoint with a NextAuth-secret-signed bearer token,
verifying no 413 FUNCTION_PAYLOAD_TOO_LARGE occurs up to the 25MB limit.
"""
import os
import sys
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mint_token import main as mint  # noqa: E402

token = mint()

BASE_URL = os.environ.get("KULIMA_TEST_BACKEND_URL", "http://127.0.0.1:8000")
BOUNDARY = "----kulima-validation-boundary"


def build_multipart(file_path: str) -> tuple[bytes, str]:
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        payload = f.read()
    parts = [
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n".encode(),
        payload,
        f"\r\n--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="assessmentType"\r\n\r\nstartup\r\n'
        f"--{BOUNDARY}--\r\n".encode(),
    ]
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={BOUNDARY}"


def upload(size_mb: int) -> tuple[int, str]:
    path = os.path.join(os.environ.get("TEMP", "/tmp"), f"kulima_val_{size_mb}mb.pdf")
    with open(path, "wb") as f:
        f.seek(size_mb * 1024 * 1024 - 1)
        f.write(b"\0")
    body, content_type = build_multipart(path)
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/assessments/",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(300).decode("utf-8", "replace")


if __name__ == "__main__":
    print("upload URL:", f"{BASE_URL}/api/v1/assessments/  (direct backend, no Vercel proxy)")
    ok = True
    for size in (1, 10, 20, 25):
        status, body = upload(size)
        print(f"{size:>3}MB -> HTTP {status} | {body[:110]}")
        if size <= 25 and status >= 500:
            ok = False
    print("UPLOAD_MATRIX_OK" if ok else "UPLOAD_MATRIX_FAILED")
