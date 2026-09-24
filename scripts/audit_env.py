"""Audit env files for presence of required keys (values are NEVER printed).

Usage: python scripts/audit_env.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    os.path.join(ROOT, "frontend", ".env.local"),
    os.path.join(ROOT, "backend", ".env"),
]

REQUIRED = {
    "frontend/.env.local": [
        "NEXTAUTH_URL",
        "NEXTAUTH_SECRET",
        "NEXT_PUBLIC_API_URL",
    ],
    "backend/.env": [
        "NEXTAUTH_SECRET",
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
    ],
}


def main() -> int:
    failures = 0
    for rel, keys in REQUIRED.items():
        path = None
        for f in FILES:
            if rel.split("/")[0] in f and rel.split("/")[1] in f:
                path = f
        if path is None or not os.path.isfile(path):
            print(f"[MISSING FILE] {rel}")
            failures += 1
            continue
        values = {}
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
        print(f"--- {rel} ---")
        for key in keys:
            raw = values.get(key, "")
            if raw is None or raw == "":
                print(f"  {key}: EMPTY")
                failures += 1
            else:
                print(f"  {key}: SET (len={len(raw)})")
    print()
    print("FAILURES:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
