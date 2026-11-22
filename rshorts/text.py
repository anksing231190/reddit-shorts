"""Turn raw Reddit markdown into clean, speakable narration."""
from __future__ import annotations

import re

ACRONYMS = {
    "AITA": "Am I the A-hole", "AITAH": "Am I the A-hole", "WIBTA": "Would I be the A-hole",
    "NTA": "not the A-hole", "YTA": "you're the A-hole", "ESH": "everyone sucks here",
    "TIFU": "Today I messed up", "TL;DR": "In short", "TLDR": "In short", "TL:DR": "In short",
    "BF": "boyfriend", "GF": "girlfriend", "SO": "partner", "DH": "husband", "DW": "wife",
    "MIL": "mother-in-law", "FIL": "father-in-law", "SIL": "sister-in-law", "BIL": "brother-in-law",
    "OP": "the original poster", "IMO": "in my opinion", "IMHO": "in my opinion", "TBH": "to be honest",
    "IDK": "I don't know", "FWIW": "for what it's worth", "AFAIK": "as far as I know",
    "BTW": "by the way", "IRL": "in real life", "ASAP": "as soon as possible", "LOL": "", "LMAO": "",
    "WTF": "what the heck", "OMG": "oh my god", "ETA": "Edit", "PSA": "public service announcement",
    "NC": "no contact", "LC": "low contact", "ex-BF": "ex-boyfriend", "ex-GF": "ex-girlfriend",
}

# Softer swaps so the video stays advertiser-friendly. Order matters (longest first).
CENSOR = [
    (r"motherf\w*", "mother-freaker"), (r"f+u+c+k+i+n+g?", "freaking"), (r"f+u+c+k+e+d", "messed"),
    (r"f+u+c+k+", "frick"), (r"bullshit", "bull"), (r"shit\w*", "crap"), (r"bitch\w*", "jerk"),
    (r"asshole\w*", "a-hole"), (r"dickhead\w*", "jerk"), (r"cunt\w*", "jerk"), (r"bastard\w*", "jerk"),
    (r"whore\w*", "cheater"), (r"slut\w*", "cheater"), (r"retard\w*", "idiot"), (r"goddamn", "god dang"),
    (r"damn", "dang"), (r"rape\w*", "assault"), (r"raping", "assaulting"), (r"suicide", "unaliving"),
    (r"killed himself", "unalived himself"), (r"killed herself", "unalived herself"),
]

_AGE_GENDER = re.compile(r"\(\s*(\d{1,2})\s*([MFmf]|NB|nb)\s*\)|\(\s*([MFmf])\s*(\d{1,2})\s*\)")
_GENDER = {"m": "male", "f": "female", "nb": "non-binary"}


def _age_gender(m: re.Match) -> str:
    age = m.group(1) or m.group(4)
    g = (m.group(2) or m.group(3)).lower()
    return f", {age} {_GENDER.get(g, '')},"


def _starred(m: re.Match) -> str:
    w = m.group(0).lower()
    if w.startswith("f"):
        return "freaking" if w.endswith(("ing", "in")) else "frick"
    if w.startswith("s"):
        return "crap"
    return "jerk" if w.startswith(("b", "a", "c")) else ""


def clean(text: str, *, censor: bool = True, drop_edits: bool = True) -> str:
    t = text.replace("\r", "")
    if drop_edits:  # cut trailing "EDIT:" / "UPDATE:" sections
        t = re.split(r"\n\s*(?:\*\*)?\s*(?:edit|update|eta)\s*\d*\s*(?:\*\*)?\s*[:\-]", t, flags=re.I)[0]
    t = re.sub(r"\b\w*\*{2,}\w*", _starred, t)                 # pre-censored words like f***ing
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)          # [text](link)
    t = re.sub(r"https?://\S+|www\.\S+", "", t)            # bare urls
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"[*_~`^#>|]+", "", t)                      # markdown symbols
    t = re.sub(r"^\s*[-+]\s+", "", t, flags=re.M)          # bullets
    t = re.sub(r"\bu/\w+", "a user", t)
    t = re.sub(r"\br/(\w+)", r"r slash \1", t)
    t = _AGE_GENDER.sub(_age_gender, t)
    for k, v in ACRONYMS.items():
        t = re.sub(rf"(?<![\w-]){re.escape(k)}(?![\w-])", v, t)
    t = re.sub(r"(\d+)\s?(?:yo|y/o)\b", r"\1 year old", t, flags=re.I)
    t = t.replace("&", " and ")
    if censor:
        for pat, rep in CENSOR:
            t = re.sub(rf"\b{pat}\b", rep, t, flags=re.I)
    t = re.sub(r"\.{3,}|…", "...", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    t = re.sub(r"\s*,\s*,", ",", t)
    t = re.sub(r"\(\s*,", "(", t)
    t = re.sub(r"\n{2,}", "\n\n", t).strip()
    return t


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])[\"')\]]*\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def split_parts(body: str, max_words: int) -> list[str]:
    """Split a long story into roughly equal parts on sentence boundaries."""
    sents = sentences(body)
    total = sum(len(s.split()) for s in sents)
    if total <= max_words:
        return [body]
    n = -(-total // max_words)
    target = total / n
    parts, cur, cur_n = [], [], 0
    for s in sents:
        cur.append(s)
        cur_n += len(s.split())
        if cur_n >= target and len(parts) < n - 1:
            parts.append(" ".join(cur))
            cur, cur_n = [], 0
    if cur:
        parts.append(" ".join(cur))
    return parts


NUM_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
