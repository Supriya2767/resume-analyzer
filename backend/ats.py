
import re
import logging
from typing import Optional

# Import helpers from parser.  extract_skills already uses regex-based
# matching, so we re-use it here.
from parser import extract_skills, extract_email, extract_phone, extract_name

log = logging.getLogger("ats")

# ── ATS section keywords ───────────────────────────────────────────────────
ATS_KEYWORDS: list[str] = [
    "experience", "education", "skills", "project", "projects",
    "achievement", "objective", "summary", "certification",
    "internship", "leadership", "team", "communication",
    "github", "linkedin", "portfolio", "responsibilities",
    "work experience", "technical skills",
]

# ── High-value skills with pre-compiled patterns (BUG-9 FIX) ──────────────
# Tuple format: (display_name, compiled_pattern | None)
# None → generic word-boundary pattern built at runtime.
_HV_SKILLS: list[tuple[str, Optional[re.Pattern]]] = [
    ("Python",          None),
    # "java" must NOT match "javascript"
    ("Java",            re.compile(r"\bjava(?!script)\b", re.I)),
    ("JavaScript",      None),
    ("TypeScript",      None),
    # "react" must NOT match "reactjs" (different entry)
    ("React",           re.compile(r"\breact(?!js\b|\.js\b|\s+native)", re.I)),
    ("Node.js",         re.compile(r"node\.?js|nodejs", re.I)),
    # "sql" must NOT match "nosql"
    ("SQL",             re.compile(r"(?<![a-zA-Z])sql(?![a-zA-Z])", re.I)),
    # "git" must NOT match "github" or "gitlab"
    ("Git",             re.compile(r"(?<![a-zA-Z])git(?!hub|lab)(?![a-zA-Z])", re.I)),
    ("Machine Learning",re.compile(r"machine\s+learning", re.I)),
    ("Data Analysis",   re.compile(r"data\s+analysis", re.I)),
    ("AWS",             re.compile(r"\baws\b|amazon\s+web\s+services", re.I)),
    ("Docker",          None),
    ("REST API",        re.compile(r"rest[\s\-]?api|restful", re.I)),
    ("Agile",           None),
    ("TypeScript",      None),
]

# De-duplicate display names (TypeScript appeared twice above)
_seen: set[str] = set()
_HV_SKILLS_DEDUPED: list[tuple[str, Optional[re.Pattern]]] = []
for _name, _pat in _HV_SKILLS:
    if _name not in _seen:
        _HV_SKILLS_DEDUPED.append((_name, _pat))
        _seen.add(_name)
_HV_SKILLS = _HV_SKILLS_DEDUPED


def _skill_in_text(display_name: str, pattern: Optional[re.Pattern], text: str) -> bool:
    """Return True if the skill is present in text using the safe pattern."""
    if pattern is not None:
        return bool(pattern.search(text))
    # Generic word-boundary fallback
    pat = re.compile(
        r"(?<![a-zA-Z])" + re.escape(display_name) + r"(?![a-zA-Z])", re.I
    )
    return bool(pat.search(text))


# ── Scoring components ─────────────────────────────────────────────────────

def score_keywords(text: str) -> dict:
    """
    COMPONENT 1 — Keyword Match (max 50 points).

    ATS_KEYWORDS are short section-header words (experience, education, etc.).
    These are not skill names, so plain substring matching is acceptable here
    because no ATS_KEYWORDS overlap with common words in other contexts.
    Word-boundary check is still applied for precision.
    """
    text_lower = text.lower()
    matched = []
    missing = []

    for kw in ATS_KEYWORDS:
        # Use word boundary for multi-word phrases; single words already safe
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.I)
        if pattern.search(text_lower):
            matched.append(kw)
        else:
            missing.append(kw)

    score = round((len(matched) / len(ATS_KEYWORDS)) * 50, 1)
    log.debug("Keyword score: %.1f  matched=%d/%d", score, len(matched), len(ATS_KEYWORDS))
    return {
        "score": score,
        "matched_keywords": matched,
        "missing_keywords": missing,
    }


def score_skills(text: str) -> dict:
    """
    COMPONENT 2 — High-Value Skills Match (max 30 points).

    BUG-9 FIX: Uses _skill_in_text() with pre-compiled regex patterns
    instead of the old plain `skill in text_lower` substring check.
    """
    matched = []
    missing = []

    for display_name, pattern in _HV_SKILLS:
        if _skill_in_text(display_name, pattern, text):
            matched.append(display_name)
        else:
            missing.append(display_name)

    score = round((len(matched) / len(_HV_SKILLS)) * 30, 1)
    log.debug("Skills score: %.1f  matched=%d/%d", score, len(matched), len(_HV_SKILLS))
    return {
        "score": score,
        "matched_skills": matched,
        "missing_skills": missing,
    }


def score_completeness(text: str, precomputed_skills: list[str]) -> dict:
    """
    COMPONENT 3 — Resume Completeness (max 20 points).

    BUG-6 FIX: Accepts the already-computed skills list as a parameter
    instead of calling extract_skills(text) again internally.

    +4  name found
    +4  email found
    +4  phone found
    +4  3+ skills detected
    +4  150+ words
    """
    score = 0
    details: dict = {}

    name = extract_name(text)
    has_name = bool(name) and name != "Unknown"
    if has_name:
        score += 4
    details["has_name"] = has_name

    has_email = bool(extract_email(text))
    if has_email:
        score += 4
    details["has_email"] = has_email

    has_phone = bool(extract_phone(text))
    if has_phone:
        score += 4
    details["has_phone"] = has_phone

    # BUG-6 FIX: reuse the list passed in — no re-extraction
    has_skills = len(precomputed_skills) >= 3
    if has_skills:
        score += 4
    details["has_skills"] = has_skills

    word_count = len(text.split())
    has_length = word_count >= 150
    if has_length:
        score += 4
    details["word_count"] = word_count
    details["has_adequate_length"] = has_length

    log.debug("Completeness score: %d", score)
    return {"score": score, "details": details}


def build_suggestions(kw_data: dict, sk_data: dict, comp_data: dict) -> list[str]:
    """Generate actionable improvement tips from the three scoring results."""
    tips: list[str] = []
    d = comp_data.get("details", {})

    if not d.get("has_email"):
        tips.append("Add your email address — recruiters need it to contact you.")
    if not d.get("has_phone"):
        tips.append("Add a phone number to your resume.")
    if not d.get("has_skills"):
        tips.append("Add a dedicated 'Technical Skills' section with at least 3 skills.")
    if not d.get("has_adequate_length"):
        tips.append("Your resume is too short. Expand your project and experience descriptions.")

    missing_kw = kw_data.get("missing_keywords", [])
    if missing_kw:
        tips.append(f"Add these missing resume sections: {', '.join(missing_kw[:3])}")

    missing_sk = sk_data.get("missing_skills", [])
    if missing_sk:
        tips.append(f"Consider learning these high-value skills: {', '.join(missing_sk[:4])}")

    tips.append("Use action verbs: 'developed', 'designed', 'implemented', 'led'.")
    tips.append("Quantify achievements — e.g. 'Reduced API latency by 40%'.")
    tips.append("Include your LinkedIn profile URL and GitHub username.")

    return tips


def calculate_ats_score(resume_text: str) -> dict:
    """
    Main entry point — runs all three scoring components.

    BUG-6 FIX: Calls extract_skills() exactly ONCE here at the top,
    then passes the result to score_completeness() so it is never
    recomputed inside that function.
    """
    # Extract skills once and reuse everywhere
    skills = extract_skills(resume_text)

    kw   = score_keywords(resume_text)
    sk   = score_skills(resume_text)
    comp = score_completeness(resume_text, precomputed_skills=skills)  # BUG-6 FIX

    total = min(round(kw["score"] + sk["score"] + comp["score"], 1), 100)

    if total >= 80:
        rating = "Excellent"
    elif total >= 60:
        rating = "Good"
    elif total >= 40:
        rating = "Average"
    else:
        rating = "Needs Improvement"

    log.info("ATS score: %.1f (%s)", total, rating)

    return {
        "ats_score": total,
        "rating": rating,
        "breakdown": {
            "keyword_score":      kw["score"],
            "skills_score":       sk["score"],
            "completeness_score": comp["score"],
        },
        "matched_keywords":    kw["matched_keywords"],
        "missing_keywords":    kw["missing_keywords"],
        "matched_skills":      sk["matched_skills"],
        "missing_skills":      sk["missing_skills"],
        "completeness_details": comp["details"],
        "suggestions":         build_suggestions(kw, sk, comp),
    }