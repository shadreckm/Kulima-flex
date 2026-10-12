import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kulima.llm import LLMClient

c = LLMClient()
print("chain:", c.manager.chain)
print("available:", c.is_available)
try:
    r = c.complete("You are terse.", "Say OK.")
    print("provider:", c.last_provider, "| text:", r[:60])
except Exception as e:
    print("all providers failed:", type(e).__name__, str(e)[:200])
try:
    j = c.complete_json("Return JSON.", 'Answer with {"ok": true}')
    print("json ok:", j)
except Exception as e:
    print("json via doc-intelligence n/a (expected offline):", type(e).__name__)
