# server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os, json, re, math, string
from pathlib import Path


try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)
except Exception:
    pass

# PII (Presidio + spaCy)
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider

def ensure_spacy_model(model_name: str = "en_core_web_sm") -> None:
    try:
        import importlib; importlib.import_module(model_name)
    except Exception:
        from spacy.cli import download; download(model_name)
ensure_spacy_model("en_core_web_sm")

provider = NlpEngineProvider(
    nlp_configuration={"nlp_engine_name":"spacy","models":[{"lang_code":"en","model_name":"en_core_web_sm"}]}
)
nlp_engine = provider.create_engine()
registry = RecognizerRegistry(); registry.load_predefined_recognizers()

# Stronger SSN pattern
ssn_pattern = Pattern(
    name="US_SSN_PATTERN",
    regex=r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
    score=0.8,
)
registry.add_recognizer(PatternRecognizer(
    supported_entity="US_SSN",
    patterns=[ssn_pattern],
    context=["ssn","social security","social-security","social sec"]
))
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry, supported_languages=["en"])
TARGET_ENTITIES = ["EMAIL_ADDRESS","US_SSN","PHONE_NUMBER","CREDIT_CARD","IP_ADDRESS"]
SCORE_THRESHOLD = 0.4

# Secrets (regex + entropy) 
def _redact(s: str) -> str:
    if not s: return ""
    return "*"*len(s) if len(s)<=8 else s[:4] + "*"*(len(s)-8) + s[-4:]

def _entropy(s: str) -> float:
    if not s: return 0.0
    freq={ch:s.count(ch) for ch in set(s)}
    return -sum((c/len(s))*math.log2(c/len(s)) for c in freq.values())

SECRET_PATTERNS = [
    ("AWS Access Key ID",
     re.compile(r"(?<![A-Z0-9])(AKIA|ASIA|AIDA|AGPA|ANPA|AROA|AIPA)[A-Z0-9]{16}(?![A-Z0-9])"), 0),
    ("AWS Secret Access Key",
     re.compile(r"(?i)\baws[_-]?secret[_-]?access[_-]?key\b\s*[:=]\s*([A-Za-z0-9/\+=]{40})"), 1),
    ("GitHub Token",         re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b"), 0),
    ("Slack Token",          re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b"), 0),
    ("Google API Key",       re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), 0),
    ("OpenAI API Key",       re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), 0),
    ("Stripe Live Key",      re.compile(r"\b(?:sk_live|rk_live)_[A-Za-z0-9]{24,}\b"), 0),
    ("Twilio Account SID",   re.compile(r"\bAC[0-9a-fA-F]{32}\b"), 0),
    ("Twilio Auth Token",    re.compile(r"\b[0-9a-fA-F]{32}\b"), 0),
    ("Private Key Block",    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"), 0),
]

def scan_secrets_regex(text: str, entropy_threshold: float = 3.5):
    findings=[]
    for name, pattern, grp in SECRET_PATTERNS:
        for m in pattern.finditer(text):
            full = m.group(grp) if (grp and (m.lastindex or 0) >= grp) else m.group(0)
            findings.append({"detector":name,"redacted":_redact(full),
                             "entropy":round(_entropy(full),3),"start":m.start(),"end":m.end()})
    for m in re.finditer(r"\b[A-Za-z0-9/\+=]{20,}\b", text):
        s=m.group(0); ent=_entropy(s)
        already=any(d["start"]<=m.start()<=d["end"] for d in findings)
        if ent>=entropy_threshold and not already:
            findings.append({"detector":"High-Entropy String","redacted":_redact(s),
                             "entropy":round(ent,3),"start":m.start(),"end":m.end()})
    findings.sort(key=lambda x:(x["start"],-(x["end"]-x["start"])))
    dedup=[]
    for f in findings:
        if not any(f["start"]>=d["start"] and f["end"]<=d["end"] for d in dedup):
            dedup.append(f)
    return dedup

# Toxicity (better_profanity only) 
# No regex for detection; we only use better_profanity with a small add-on lexicon.
CUSTOM_TOXIC_WORDS = {
    "hate","hateful","disgusting","idiot","stupid","dumb","moron","loser",
    "trash","garbage","worthless","ugly"
}
_BP_READY = False
def _init_better_profanity():
    """Load default wordlist, then add our custom words (no regex, no ML)."""
    global _BP_READY
    if _BP_READY:
        return
    from better_profanity import profanity
    # load defaults
    profanity.load_censor_words()
    # extend list 
    try:
        profanity.add_censor_words(list(CUSTOM_TOXIC_WORDS))
    except Exception:
        # Some very old versions use a slightly different API; ignore if missing
        pass
    _BP_READY = True

def _simple_tokens(s: str):
    # no regex; whitespace/punctuation split for optional debug
    tbl = str.maketrans({c:" " for c in string.punctuation})
    return (s or "").translate(tbl).lower().split()

#  FastAPI & models 
app = FastAPI(title="Mini Firewall (Local/Hybrid)")

class TextRequest(BaseModel):
    text: str

class AllowlistRequest(BaseModel):
    text: str
    topics: Optional[List[str]] = None  # used by LLM

@app.get("/")
def root():
    paths = sorted({getattr(r,"path","") for r in app.routes if getattr(r,"path","").startswith("/")})
    return {"ok": True, "endpoints": paths}

# endpoints 
@app.post("/pii")
def pii_endpoint(payload: TextRequest):
    results = analyzer.analyze(text=payload.text, language="en",
                               entities=TARGET_ENTITIES, score_threshold=SCORE_THRESHOLD)
    filtered = [r for r in results if r.entity_type in TARGET_ENTITIES and r.score >= SCORE_THRESHOLD]
    findings = [{"entity_type": r.entity_type, "score": float(round(r.score,3)),
                 "start": r.start, "end": r.end, "text": payload.text[r.start:r.end]} for r in filtered]
    findings = sorted(findings, key=lambda x: (x["start"], -(x["end"]-x["start"])))
    dedup=[]
    for f in findings:
        if not any(f["start"]>=d["start"] and f["end"]<=d["end"] for d in dedup):
            dedup.append_BP(f)
    return {"contains_pii": bool(dedup), "findings": dedup}

@app.post("/secretscanning")
def secrets_endpoint(payload: TextRequest):
    findings = scan_secrets_regex(payload.text)
    return {"mode":"regex","contains_secrets": bool(findings), "findings": findings}


from fastapi.responses import JSONResponse

@app.post("/toxicity")
def toxicity_endpoint(payload: TextRequest):
    """
    Pure better_profanity classifier.
    Always returns JSON (even on internal errors).
    """
    try:
        from better_profanity import profanity
        _init_better_profanity()
        text = payload.text or ""
        flagged = bool(profanity.contains_profanity(text))
        return {"model": "better-profanity", "contains_toxicity": flagged}
    except Exception as e:
        # Return JSON so curl | json.tool never fails
        return JSONResponse(
            status_code=200,
            content={"model": "better-profanity", "contains_toxicity": False, "error": str(e)},
        )

# Back-compat aliases for locals
app.add_api_route("/scan/pii",       pii_endpoint,       methods=["POST"])
app.add_api_route("/scan/secrets",   secrets_endpoint,   methods=["POST"])
app.add_api_route("/scan/toxicity",  toxicity_endpoint,  methods=["POST"])

# llm backup
LLM_BACKUP_ENABLED = os.getenv("LLM_BACKUP_ENABLED","0") == "1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL","gpt-4o-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL","https://api.openai.com/v1/chat/completions")

def _require_llm():
    if not LLM_BACKUP_ENABLED:
        raise HTTPException(status_code=501, detail="LLM backup disabled. Set LLM_BACKUP_ENABLED=1")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing in environment")
    return True

def _openai_json(system_prompt: str, user_payload: dict) -> dict:
    import requests
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role":"system","content": system_prompt},
            {"role":"user","content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        "temperature": 0,
        "response_format": {"type":"json_object"},
    }
    r = requests.post(OPENAI_API_URL, headers=headers, json=body, timeout=45)
    try:
        data = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail=f"OpenAI HTTP {r.status_code}")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=str(data))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)

# System prompts
PII_SYS = (
    "You are a privacy classifier. Reply ONLY in JSON.\n"
    'Schema: {"contains_pii": boolean, "findings":[{"entity_type": string, "text": string}]}\n'
    "Consider emails, phone numbers, SSNs, credit cards, IPs. No extra text."
)
SECRETS_SYS = (
    "You are a secret detector. Reply ONLY in JSON.\n"
    'Schema: {"contains_secrets": boolean, "items":[{"type": string, "redacted": string}]}\n'
    "Consider API keys, tokens, access keys, private keys. No extra text."
)
ALLOW_SYS = (
    "You are an allowlist matcher. Reply ONLY in JSON.\n"
    'Schema: {"allowed": boolean, "matched_topic": string|null}\n'
    "Return allowed=true if any topic is contained (case-insensitive). No extra text."
)
TOX_SYS = (
    "You are a content-safety classifier. Reply ONLY in JSON.\n"
    'Schema: {"toxic": boolean, "severity":"low|medium|high", '
    '"categories": ["harassment"|"threat"|"identity_attack"|"sexual"|"self_harm"|"other"...], "reason": string}\n'
    "Be strict for harassment and threats. No extra text."
)

#  LLM endpoints 
@app.post("/pii/llm")
def pii_llm(payload: TextRequest):
    _require_llm()
    return _openai_json(PII_SYS, {"text": payload.text})

@app.post("/secretscanning/llm")
def secrets_llm(payload: TextRequest):
    _require_llm()
    return _openai_json(SECRETS_SYS, {"text": payload.text})

# ALLOWLIST (LLM-only)
@app.post("/allowlist")
def allow_llm_only(payload: AllowlistRequest):
    _require_llm()
    return _openai_json(ALLOW_SYS, {"text": payload.text, "topics": payload.topics or []})

@app.post("/toxicity/llm")
def toxicity_llm(payload: TextRequest):
    _require_llm()
    return _openai_json(TOX_SYS, {"text": payload.text})

# aliases
app.add_api_route("/scan/pii/llm",          pii_llm,      methods=["POST"])
app.add_api_route("/scan/secrets/llm",      secrets_llm,  methods=["POST"])
app.add_api_route("/scan/allow",            allow_llm_only, methods=["POST"])  # back-compat
app.add_api_route("/scan/allow/llm",        allow_llm_only, methods=["POST"])
app.add_api_route("/scan/toxicity/llm",     toxicity_llm, methods=["POST"])

