# jd_match.py - Job Description Matching Module
#
# Compares your resume keywords against a job description.
# Uses TF (Term Frequency) to find the most important words in each.
# Then uses Python set operations to find matches and gaps.
#
# Key NLP concepts:
# - Tokenization: splitting text into words
# - Stop word removal: ignoring "the", "a", "is", etc.
# - Term frequency: counting word occurrences
# - Set intersection: words in both resume and JD
# - Set difference: words in JD but NOT in resume

import re
import logging
from collections import Counter

from parser import extract_skills   # reuse the regex-based skill extractor

log = logging.getLogger("jd_match")

# ── Stop words ────────────────────────────────────────────────────────────
STOP_WORDS: set[str] = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","have","has","had",
    "do","does","did","will","would","could","should","may","might","this",
    "that","these","those","we","you","our","your","their","its","as","if",
    "then","than","so","up","into","through","during","including","such",
    "also","must","not","can","about","more","what","who","how","when",
    "where","which","any","all","both","each","few","some","other",
    "use","using","used","work","working","worked","provide","strong",
    "good","well","able","new","create","make","build","etc","per",
    "year","years","month","months","day","days",
}

# ── Multi-word skill phrases (BUG-10 FIX: extracted BEFORE stripping) ─────
SKILL_PHRASES: list[str] = [
    # ML / AI
    "machine learning", "deep learning", "natural language processing",
    "computer vision", "artificial intelligence", "large language model",
    "reinforcement learning", "neural network",
    # Data
    "data analysis", "data science", "data engineering", "data pipeline",
    "data visualization", "data modelling", "business intelligence",
    "power bi", "google analytics",
    # Dev practices
    "rest api", "restful api", "api development", "api design",
    "full stack", "full-stack", "front end", "front-end", "back end", "back-end",
    "object oriented", "object-oriented", "data structures", "design patterns",
    "test driven development", "behavior driven development",
    "unit testing", "integration testing", "end to end testing",
    "continuous integration", "continuous deployment", "ci/cd",
    "version control", "code review", "pair programming",
    # Architecture
    "cloud computing", "cloud native", "system design", "microservices",
    "event driven", "distributed systems", "service mesh",
    "software engineering", "software development", "web development",
    "mobile development", "application development",
    # Processes
    "agile methodology", "scrum framework", "project management",
    "team collaboration", "cross functional", "stakeholder management",
    "problem solving", "critical thinking", "communication skills",
    # Specific tech combos
    "spring boot", "node js", "node.js", "next.js", "react native",
    "react js", "vue js", "angular js", "express js",
    "scikit learn", "scikit-learn",
    "amazon web services", "google cloud platform", "microsoft azure",
]


# ── Tokeniser (BUG-10 FIX) ────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """
    BUG-10 FIX: Strip only truly non-meaningful punctuation.
    Preserve: + # . / (used in c++, c#, .net, node.js, ci/cd, etc.)
    Strip: , ; ( ) [ ] { } ? ! @ % ^ * = ~ ` ' "
    """
    text = text.lower()
    # Remove characters that are never part of a skill/keyword token
    # but KEEP + # . / - _ (they appear in skill names)
    text = re.sub(r"[,;()\[\]{}\?!@%\^&\*=~`'\"\u2022\u2013\u2014]", " ", text)
    words = text.split()
    # Keep tokens that are meaningful: length > 1 OR known special tokens
    result = []
    for w in words:
        w = w.strip(".")           # strip trailing dots (sentence endings)
        if w and w not in STOP_WORDS and len(w) > 1:
            result.append(w)
    return result


def _get_top_keywords(text: str, top_n: int = 50) -> list[str]:
    """Return top_n most frequent meaningful tokens."""
    tokens = _tokenize(text)
    freq = Counter(tokens)
    return [w for w, _ in freq.most_common(top_n)]


def _get_phrases(text: str) -> list[str]:
    """
    Extract multi-word tech phrases by scanning the raw (lowercased) text
    BEFORE any punctuation stripping.  This preserves 'c++', '.net', etc.
    """
    text_lower = text.lower()
    return [p for p in SKILL_PHRASES if p in text_lower]


# ── Main matching function ─────────────────────────────────────────────────

def match_job_description(resume_text: str, job_description: str) -> dict:
    """
    Compare resume text against a job description.

    Three-layer matching:
    Layer 1 — Multi-word tech phrases (extracted before punctuation stripping).
    Layer 2 — Single-word keyword frequency (top-N tokens).
    Layer 3 — Skill-level comparison using parser.extract_skills() on both
              texts for precise, regex-validated skill matching.

    match_pct = |intersection| / |JD keywords| × 100
    """
    # ── Layer 1: phrases ──────────────────────────────────────────────────
    resume_phrases = set(_get_phrases(resume_text))
    jd_phrases     = set(_get_phrases(job_description))

    # ── Layer 2: single-word keywords ─────────────────────────────────────
    resume_kws = set(_get_top_keywords(resume_text, 60))
    jd_kws     = set(_get_top_keywords(job_description, 50))

    # ── Layer 3: validated skill matching ────────────────────────────────
    resume_skills_validated = set(s.lower() for s in extract_skills(resume_text))
    jd_skills_validated     = set(s.lower() for s in extract_skills(job_description))

    # ── Combine all layers ────────────────────────────────────────────────
    all_resume = resume_phrases | resume_kws | resume_skills_validated
    all_jd     = jd_phrases     | jd_kws     | jd_skills_validated

    matched = list(all_resume & all_jd)
    missing = list(all_jd - all_resume)

    match_pct = round((len(matched) / len(all_jd)) * 100, 1) if all_jd else 0.0

    # ── Skill-specific matched / missing (for UI display) ────────────────
    # Prefer validated skills over raw tokens for cleaner UI output
    skill_matched = sorted(
        (jd_skills_validated & resume_skills_validated),
        key=lambda s: s.lower(),
    )
    skill_missing = sorted(
        (jd_skills_validated - resume_skills_validated),
        key=lambda s: s.lower(),
    )

    # Capitalise for display
    skill_matched_display = [s.title() for s in skill_matched][:15]
    skill_missing_display = [s.title() for s in skill_missing][:15]

    # Also include unvalidated high-frequency matched/missing keywords
    kw_matched = [k for k in matched if len(k) > 3 and k not in skill_matched][:10]
    kw_missing = [k for k in missing if len(k) > 3 and k not in skill_missing][:10]

    if match_pct >= 75:
        quality = "Strong Match"
    elif match_pct >= 50:
        quality = "Good Match"
    elif match_pct >= 25:
        quality = "Partial Match"
    else:
        quality = "Low Match"

    # ── Recommendations ───────────────────────────────────────────────────
    recs: list[str] = []
    if skill_missing_display:
        recs.append(
            f"Add these missing skills to your resume: "
            f"{', '.join(skill_missing_display[:5])}"
        )
    if kw_missing:
        recs.append(
            f"Use these keywords from the job description: "
            f"{', '.join(kw_missing[:5])}"
        )
    if match_pct < 50:
        recs.append("Tailor your resume to mirror the language used in this job posting.")
        recs.append("Add a 'Projects' section demonstrating the required skills.")
    if match_pct < 30:
        recs.append("Consider upskilling in the areas highlighted as missing above.")
    recs.append("Quantify all achievements with numbers (%, $, time, scale).")

    # Deduplicate while preserving order
    seen_recs: set[str] = set()
    unique_recs: list[str] = []
    for r in recs:
        if r not in seen_recs:
            unique_recs.append(r)
            seen_recs.add(r)

    log.info(
        "JD match: %.1f%%  quality=%s  matched=%d  missing=%d",
        match_pct, quality, len(matched), len(missing),
    )

    return {
        "match_percentage":   match_pct,
        "match_quality":      quality,
        "matched_keywords":   kw_matched,
        "missing_keywords":   kw_missing,
        "matched_skills":     skill_matched_display,
        "missing_skills":     skill_missing_display,
        "total_jd_keywords":  len(all_jd),
        "total_matched":      len(matched),
        "recommendations":    unique_recs,
    }