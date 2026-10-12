"""Helper to generate a valid test JWT token using NEXTAUTH_SECRET from backend/.env"""
import os
import time
import jwt

def main():
    secret = None
    fe_path = os.path.join(os.path.dirname(__file__), "..", "frontend", ".env.local")
    if os.path.exists(fe_path):
        with open(fe_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("NEXTAUTH_SECRET="):
                    secret = line.strip().partition("=")[2].strip().strip('"').strip("'")
                    break
    if not secret:
        env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("NEXTAUTH_SECRET="):
                        secret = line.strip().partition("=")[2].strip().strip('"').strip("'")
                        break
    if not secret:
        secret = os.environ.get("NEXTAUTH_SECRET", "dev-secret-test-key-32-chars-long")

    payload = {
        "sub": "validation-engineer",
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 30,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    os.makedirs(r"C:\temp\kulima_test", exist_ok=True)
    with open(r"C:\temp\kulima_test\token.txt", "w", encoding="utf-8") as out:
        out.write(token)
    print("Minted token written to C:\\temp\\kulima_test\\token.txt")
    return token

if __name__ == "__main__":
    main()
