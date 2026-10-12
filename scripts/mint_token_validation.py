"""Mint a token for the existing 'validation-engineer' user using frontend NEXTAUTH_SECRET."""
import os
import time
import jwt

secret = None
for path in (r"frontend\.env.local", r"backend\.env"):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("NEXTAUTH_SECRET="):
                    raw = line.partition("=")[2].strip()
                    secret = raw.strip('"').strip("'")
                    break
        if secret:
            break

payload = {
    "sub": "validation-engineer",
    "iat": int(time.time()),
    "exp": int(time.time()) + 86400 * 30,
}
token = jwt.encode(payload, secret, algorithm="HS256")
with open(r"C:\temp\kulima_test\token.txt", "w", encoding="utf-8") as out:
    out.write(token)
print("minted", len(token))
