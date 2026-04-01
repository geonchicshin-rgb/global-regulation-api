"""
oracle_engine.py - B2A Macro-economic Oracle
============================================
Adheres strictly to Core B2A Safety & Compliance Directives:
  1. ZERO SECRETS POLICY        - API key loaded via .env only.
  2. MANDATORY FAIL-SAFE        - Every section wrapped in try/except; defaults to STANDBY on error.
  3. COMPLIANCE TERMINOLOGY     - Only CLEAR | RESTRICTED | STANDBY used.
  4. AUDIT TRACEABILITY         - All outputs include ISO-8601 timestamps.
"""

import os
import json
import base64
import datetime

# ── Dependency imports (fail gracefully) ──────────────────────────────────────
try:
    import feedparser
except ImportError:
    raise SystemExit("Missing dependency: pip install feedparser")

try:
    from dotenv import load_dotenv
except ImportError:
    raise SystemExit("Missing dependency: pip install python-dotenv")

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    raise SystemExit("Missing dependency: pip install google-genai")

try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
except ImportError:
    raise SystemExit("Missing dependency: pip install cryptography")

# ── Constants ─────────────────────────────────────────────────────────────────
YAHOO_FINANCE_RSS   = "https://finance.yahoo.com/news/rssindex"
HEADLINES_TO_FETCH  = 3
CONFIDENCE_THRESHOLD = 95
OUTPUT_STATUS_FILE  = "oracle_status.json"
AUDIT_LOG_FILE      = "audit_history.jsonl"

SAFE_STATE = {
    "signal":        "STANDBY",
    "confidence":    0,
    "reason":        "System defaulted to STANDBY due to an internal error.",
    "rsa_signature": None,
    "timestamp":     None,
}


# ── Helper: ISO-8601 timestamp ────────────────────────────────────────────────
def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Step 1 — Sensor: Fetch headlines from Yahoo Finance RSS ───────────────────
def fetch_headlines() -> list[str]:
    """Return up to HEADLINES_TO_FETCH titles from Yahoo Finance RSS."""
    try:
        feed = feedparser.parse(YAHOO_FINANCE_RSS)
        titles = [entry.title for entry in feed.entries[:HEADLINES_TO_FETCH]]
        if not titles:
            raise ValueError("RSS feed returned no entries.")
        print(f"[SENSOR]   Fetched {len(titles)} headline(s).")
        return titles
    except Exception as exc:
        print(f"[SENSOR]   ERROR - {exc}")
        return []


# ── Step 2 — Parser: Ask Gemini to classify the headlines ────────────────────
def parse_with_llm(headlines: list[str], api_key: str) -> dict:
    """
    Send headlines to Gemini. The model MUST return a plain JSON object with:
      signal     : "CLEAR" | "RESTRICTED" | "STANDBY"
      confidence : int 0–100
      reason     : str
    """
    default = {"signal": "STANDBY", "confidence": 0, "reason": "LLM parse failed."}
    # Prioritised fallback list — engine tries each until one succeeds
    MODEL_FALLBACKS = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]
    try:
        client = genai.Client(api_key=api_key)

        headline_block = "\n".join(f"- {h}" for h in headlines)
        prompt = f"""You are a macro-economic compliance oracle.
Analyse the following financial news headlines and classify the overall market posture.

Headlines:
{headline_block}

Return ONLY a valid JSON object -- no markdown, no explanation -- with exactly these keys:
  "signal"     : one of "CLEAR", "RESTRICTED", or "STANDBY"
  "confidence" : integer between 0 and 100 representing your certainty
  "reason"     : a single concise sentence explaining the classification

Rules:
- Use "CLEAR" when macro conditions appear broadly stable and positive.
- Use "RESTRICTED" when there are notable risks or mixed signals.
- Use "STANDBY" when data is insufficient, contradictory, or extremely volatile.
- NEVER output "BUY", "SELL", or "TRADE" under any circumstances.
"""
        response = None
        for model_name in MODEL_FALLBACKS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                print(f"[PARSER]   Using model: {model_name}")
                break
            except Exception as model_err:
                print(f"[PARSER]   Model '{model_name}' unavailable - {model_err}")
                continue

        if response is None:
            raise RuntimeError("All Gemini models failed. Check your API key permissions.")

        raw_text = response.text.strip()

        # Strip accidental markdown code fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        # Validate required keys
        for key in ("signal", "confidence", "reason"):
            if key not in parsed:
                raise ValueError(f"LLM response missing key: '{key}'")

        # Enforce allowed signal values
        if parsed["signal"] not in ("CLEAR", "RESTRICTED", "STANDBY"):
            raise ValueError(f"Invalid signal value returned: {parsed['signal']}")

        parsed["confidence"] = int(parsed["confidence"])
        print(f"[PARSER]   Signal={parsed['signal']}  Confidence={parsed['confidence']}%")
        return parsed

    except Exception as exc:
        print(f"[PARSER]   ERROR - {exc}")
        return default


# ── Step 3 — Logic: Enforce confidence threshold ─────────────────────────────
def apply_confidence_gate(llm_result: dict) -> dict:
    """Force signal to STANDBY when confidence falls below threshold."""
    if llm_result.get("confidence", 0) < CONFIDENCE_THRESHOLD:
        original = llm_result.get("signal", "STANDBY")
        llm_result["signal"] = "STANDBY"
        llm_result["reason"] = (
            f"Signal overridden to STANDBY - confidence {llm_result['confidence']}% "
            f"is below required threshold of {CONFIDENCE_THRESHOLD}% "
            f"(original assessment: {original})."
        )
        print(f"[GATE]     Confidence below {CONFIDENCE_THRESHOLD}% -> forced STANDBY.")
    else:
        print(f"[GATE]     Confidence gate passed ({llm_result['confidence']}%).")
    return llm_result


# ── Step 4 — Signature: RSA sign the payload ─────────────────────────────────
def generate_rsa_signature(payload_str: str) -> tuple[str, str]:
    """
    Generate a fresh RSA-2048 key pair, sign the payload, and return
    (base64_signature, base64_public_key_pem).
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    signature_bytes = private_key.sign(
        payload_str.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    signature_b64 = base64.b64encode(signature_bytes).decode("utf-8")
    print("[SIGNATURE] RSA-2048 signature generated successfully.")
    return signature_b64, pub_pem


# ── Step 5 — Output 1: Write oracle_status.json ──────────────────────────────
def write_status_file(final_result: dict) -> None:
    try:
        with open(OUTPUT_STATUS_FILE, "w", encoding="utf-8") as fh:
            json.dump(final_result, fh, indent=2)
        print(f"[OUTPUT]   Status written -> {OUTPUT_STATUS_FILE}")
    except Exception as exc:
        print(f"[OUTPUT]   ERROR writing status file - {exc}")


# ── Step 6 — Output 2: Append to audit_history.jsonl ─────────────────────────
def append_audit_log(final_result: dict) -> None:
    try:
        audit_entry = {
            "timestamp": final_result.get("timestamp"),
            "signal":    final_result.get("signal"),
            "reason":    final_result.get("reason"),
        }
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(audit_entry) + "\n")
        print(f"[AUDIT]    Entry appended -> {AUDIT_LOG_FILE}")
    except Exception as exc:
        print(f"[AUDIT]    ERROR writing audit log - {exc}")


# ── Main orchestrator ─────────────────────────────────────────────────────────
def main() -> None:
    timestamp = utc_now_iso()
    print("=" * 60)
    print("  B2A Macro-economic Oracle - Engine Start")
    print(f"  Timestamp: {timestamp}")
    print("=" * 60)

    # ── Load secrets from .env (ZERO SECRETS POLICY) ──────────────────────────
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[CONFIG]   GEMINI_API_KEY not set in .env - defaulting to STANDBY.")
        final_result = {**SAFE_STATE, "timestamp": timestamp}
        write_status_file(final_result)
        append_audit_log(final_result)
        return

    # ── MANDATORY FAIL-SAFE wrapper ───────────────────────────────────────────
    try:
        # Step 1 — Sensor
        headlines = fetch_headlines()
        if not headlines:
            raise ValueError("No headlines retrieved; cannot proceed.")

        # Step 2 — LLM Parse
        llm_result = parse_with_llm(headlines, api_key)

        # Step 3 — Confidence gate
        gated_result = apply_confidence_gate(llm_result)

        # Step 4 — Build signable payload (without signature field)
        payload_for_signing = {
            "signal":     gated_result["signal"],
            "confidence": gated_result["confidence"],
            "reason":     gated_result["reason"],
            "timestamp":  timestamp,
            "headlines":  headlines,
        }
        payload_str = json.dumps(payload_for_signing, sort_keys=True)

        rsa_signature, public_key_pem = generate_rsa_signature(payload_str)

        # Step 5 — Compose final result
        final_result = {
            **payload_for_signing,
            "rsa_signature":  rsa_signature,
            "rsa_public_key": public_key_pem,
        }

    except Exception as exc:
        print(f"[FATAL]    Unhandled error - {exc}")
        final_result = {**SAFE_STATE, "timestamp": timestamp}

    # ── Outputs (run regardless of success/failure path) ──────────────────────
    write_status_file(final_result)
    append_audit_log(final_result)

    print("=" * 60)
    print("  Oracle cycle complete.")
    print("  Final signal:", final_result.get('signal'))
    print("=" * 60)


if __name__ == "__main__":
    main()
