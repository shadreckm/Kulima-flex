"""Compare the two NEXTAUTH_SECRET values (frontend vs backend) WITHOUT printing them."""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_secret(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("NEXTAUTH_SECRET="):
                return line.partition("=")[2].strip().strip('"').strip("'")
    return ""


fe = read_secret(os.path.join(ROOT, "frontend", ".env.local"))
be = read_secret(os.path.join(ROOT, "backend", ".env"))

print("frontend secret fingerprint:", hashlib.sha256(fe.encode()).hexdigest()[:16] if fe else "EMPTY")
print("backend  secret fingerprint:", hashlib.sha256(be.encode()).hexdigest()[:16] if be else "EMPTY")
print("MATCH" if fe and fe == be else "MISMATCH")

# Non-secret URLs are safe to print
for path in (os.path.join(ROOT, "frontend", ".env.local"),):
    print("---", os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path), "---")
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in {"NEXTAUTH_URL", "NEXT_PUBLIC_API_URL"}:
                print(f"{key.strip()}={value.strip()}")
