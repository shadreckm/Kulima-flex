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

# ── MVP validation: verify Gemini specifically (Issue 3) ─────────────
try:
    m = c.manager
    m.disable_provider("openai"); m.disable_provider("groq"); m._retried.clear()
    print("gemini isolated chain:", m.chain)
    r = m._run("Reply with one word only.", "Say OK", 0.0)
    print("GEMINI simple:", r.provider, r.model, repr(r.text[:30]))
    r = m.classify("Classify: business model, revenue projections, funding ask. Reply class name only.", "doc")
    print("GEMINI classification:", r[:60])
    r = m.summarize("Summarize in one sentence.", "NGO in Malawi trains 5000 rural women in agribusiness with donor funding.")
    print("GEMINI summary:", r[:80])
    r = m.research("Analyze credibility in one sentence.", "Startup claims 40% MoM growth with 3 customers.")
    print("GEMINI analysis:", r[:80])
    print("GEMINI_VALIDATION_OK")
except Exception as e:
    print("GEMINI_FAILED:", type(e).__name__, str(e)[:200])
