import re
import logging
import unicodedata
from typing import Optional

import pdfplumber
import spacy

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("parser")

# ── spaCy model (loaded once at import time) ───────────────────────────────
try:
    nlp = spacy.load("en_core_web_sm")
    log.info("spaCy model loaded.")
except OSError:
    log.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None


# ══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════

# ── Document-level header words that are never a person's name ────────────
_HEADER_BLOCKLIST: set[str] = {
    "resume", "curriculum vitae", "cv", "profile", "bio-data", "biodata",
    "portfolio", "contact", "about me", "personal details",
    "personal information", "applicant profile", "candidate profile",
    "job application", "cover letter",
}

# ── Words that appear in job titles, NOT in personal names ────────────────
# BUG-A FIX: If any word in a candidate line is in this set,
# the line is rejected as a name (it's a job title).
_JOB_TITLE_WORDS: set[str] = {
    # Generic titles
    "engineer", "developer", "analyst", "manager", "designer", "scientist",
    "intern", "lead", "director", "architect", "consultant", "officer",
    "specialist", "coordinator", "administrator", "executive", "head",
    "senior", "junior", "associate", "principal", "staff", "vice",
    "president", "chief", "cto", "ceo", "coo", "vp", "avp", "sde",
    "swe", "sre", "devops",
    # Tech domain words that appear in titles
    "machine", "learning", "data", "intelligence", "artificial",
    "researcher", "professor", "lecturer", "fullstack", "frontend",
    "backend", "software", "cloud", "security", "network", "systems",
    "product", "technical", "technology", "information", "digital",
    "mobile", "web", "site", "platform",
}

# ── Section header detection regex ────────────────────────────────────────
# Matches lines that ARE section headers — used by _build_section_map().
# Written as a single compiled pattern for speed.
_SECTION_HEADER_RE = re.compile(
    r"^("
    r"SKILLS?|TECHNICAL\s+SKILLS?|KEY\s+SKILLS?|CORE\s+SKILLS?|"
    r"PROFESSIONAL\s+SKILLS?|"
    r"EDUCATION|ACADEMIC\s+BACKGROUND|ACADEMIC\s+QUALIFICATIONS?|"
    r"EDUCATIONAL\s+QUALIFICATIONS?|QUALIFICATIONS?|"
    r"EXPERIENCE|WORK\s+EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|"
    r"EMPLOYMENT\s+HISTORY|WORK\s+HISTORY|INTERNSHIP|INTERNSHIPS|"
    r"PROJECTS?|PERSONAL\s+PROJECTS?|ACADEMIC\s+PROJECTS?|"
    r"ACHIEVEMENTS?|ACCOMPLISHMENTS?|AWARDS?|HONORS?|"
    r"CERTIFICATIONS?|CERTIFICATES?|LICENSES?|CREDENTIALS?|"
    r"SUMMARY|PROFESSIONAL\s+SUMMARY|CAREER\s+SUMMARY|"
    r"OBJECTIVE|CAREER\s+OBJECTIVE|PROFESSIONAL\s+OBJECTIVE|"
    r"CONTACT|CONTACT\s+INFORMATION|CONTACT\s+DETAILS|"
    r"PUBLICATIONS?|RESEARCH|PAPERS?|"
    r"INTERESTS?|HOBBIES?|ACTIVITIES|EXTRA.?CURRICULAR|"
    r"LANGUAGES?|VOLUNTEER|REFERENCES?|DECLARATION"
    r")\s*:?\s*$",
    re.I | re.MULTILINE,
)

# ── Phone patterns – NO capturing groups ──────────────────────────────────
_PHONE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\+91[\s\-]?[6-9]\d{9}"),                          # Indian +91
    re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"),                        # Indian 10-digit
    re.compile(r"\+?1[\s\-]?\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}"),  # US/Canada
    re.compile(r"\+?\d{1,3}[\s\-]\(?\d{2,5}\)?[\s\-]\d{3,5}[\s\-]\d{3,5}"),  # Intl
    re.compile(r"(?<!\d)\d{10}(?!\d)"),                             # 10-digit fallback
]

# ── Skill table – (display_name, compiled_pattern | None) ─────────────────
# None → generic word-boundary pattern built at runtime.
# Pre-compiled → for skills with special characters or ambiguous short names.
_SKILL_TABLE: list[tuple[str, Optional[re.Pattern]]] = [
    # ── Programming Languages ──────────────────────────────────────────────
    ("Python",           None),
    ("JavaScript",       None),
    ("Java",             re.compile(r"\bjava(?!script)\b", re.I)),        # not "javascript"
    ("C++",              re.compile(r"c\+\+", re.I)),
    ("C#",               re.compile(r"c#", re.I)),
    ("C",                re.compile(r"(?<![a-zA-Z\d])C(?![a-zA-Z\d+#])")),
    ("TypeScript",       None),
    ("PHP",              None),
    ("Ruby",             None),
    ("Swift",            None),
    ("Kotlin",           None),
    ("Go",               re.compile(r"\bgo\b(?!lang)", re.I)),            # not "golang"
    ("Golang",           None),
    ("Rust",             re.compile(r"(?<![a-zA-Z])rust(?![a-zA-Z])", re.I)),  # not "trust"
    ("Scala",            None),
    ("R",                re.compile(r"(?<![a-zA-Z\d])[Rr](?![a-zA-Z\d])\s*(programming|language|studio|cran)", re.I)),
    ("Bash",             None),
    ("Shell Scripting",  re.compile(r"shell\s*scripting", re.I)),
    ("Perl",             None),
    ("MATLAB",           re.compile(r"\bmatlab\b", re.I)),
    # ── Frontend ──────────────────────────────────────────────────────────
    ("React",            re.compile(r"\breact(?!\.?js\s+native|js\b)", re.I)),
    ("React Native",     re.compile(r"react\s*native", re.I)),
    ("Angular",          None),
    ("Vue.js",           re.compile(r"vue\.?js|vuejs", re.I)),
    ("Next.js",          re.compile(r"next\.?js|nextjs", re.I)),
    ("HTML",             re.compile(r"\bhtml5?\b", re.I)),
    ("CSS",              re.compile(r"\bcss3?\b", re.I)),
    ("Tailwind CSS",     re.compile(r"tailwind", re.I)),
    ("Bootstrap",        None),
    ("Sass",             None),
    ("jQuery",           re.compile(r"jquery", re.I)),
    # ── Backend ───────────────────────────────────────────────────────────
    ("Node.js",          re.compile(r"node\.?js|nodejs", re.I)),
    ("Express.js",       re.compile(r"express\.?js|expressjs", re.I)),
    ("Django",           None),
    ("Flask",            None),
    ("FastAPI",          re.compile(r"fastapi", re.I)),
    ("Spring Boot",      re.compile(r"spring[\s\-]?boot", re.I)),
    ("Spring",           re.compile(r"\bspring\b(?![\s\-]?boot)", re.I)),
    ("Laravel",          None),
    (".NET",             re.compile(r"\.net(?!\w)", re.I)),
    ("GraphQL",          None),
    # ── Databases ─────────────────────────────────────────────────────────
    ("SQL",              re.compile(r"(?<![a-zA-Z])sql(?![a-zA-Z])", re.I)),  # not "nosql"
    ("MySQL",            re.compile(r"mysql", re.I)),
    ("PostgreSQL",       re.compile(r"postgres(?:ql)?", re.I)),
    ("MongoDB",          re.compile(r"mongodb|mongo\b", re.I)),
    ("SQLite",           re.compile(r"sqlite", re.I)),
    ("Redis",            None),
    ("Oracle",           None),
    ("Firebase",         None),
    ("DynamoDB",         re.compile(r"dynamodb", re.I)),
    ("Cassandra",        None),
    ("Elasticsearch",    None),
    ("NoSQL",            re.compile(r"nosql", re.I)),
    # ── DevOps / Cloud ────────────────────────────────────────────────────
    ("Git",              re.compile(r"(?<![a-zA-Z])git(?!hub|lab)(?![a-zA-Z])", re.I)),
    ("GitHub",           re.compile(r"github", re.I)),
    ("GitLab",           re.compile(r"gitlab", re.I)),
    ("Docker",           None),
    ("Kubernetes",       re.compile(r"kubernetes|k8s", re.I)),
    ("AWS",              re.compile(r"\baws\b|amazon\s+web\s+services", re.I)),
    ("Azure",            re.compile(r"\bazure\b", re.I)),
    ("GCP",              re.compile(r"\bgcp\b|google\s+cloud\s+platform", re.I)),
    ("Linux",            None),
    ("Terraform",        None),
    ("Jenkins",          None),
    ("CI/CD",            re.compile(r"ci/cd|ci[\s\-]cd|continuous\s+integration", re.I)),
    ("Ansible",          None),
    ("Nginx",            re.compile(r"nginx", re.I)),
    # ── Data / ML ─────────────────────────────────────────────────────────
    ("Machine Learning", re.compile(r"machine\s+learning", re.I)),
    ("Deep Learning",    re.compile(r"deep\s+learning", re.I)),
    ("NLP",              re.compile(r"\bnlp\b|natural\s+language\s+processing", re.I)),
    ("TensorFlow",       re.compile(r"tensorflow", re.I)),
    ("PyTorch",          re.compile(r"pytorch", re.I)),
    ("Keras",            None),
    ("Scikit-learn",     re.compile(r"scikit[\s\-]?learn|sklearn", re.I)),
    ("Pandas",           None),
    ("NumPy",            re.compile(r"numpy", re.I)),
    ("Matplotlib",       None),
    ("Seaborn",          None),
    ("Data Analysis",    re.compile(r"data\s+analysis", re.I)),
    ("Data Science",     re.compile(r"data\s+science", re.I)),
    ("Computer Vision",  re.compile(r"computer\s+vision", re.I)),
    ("Power BI",         re.compile(r"power\s*bi", re.I)),
    ("Tableau",          None),
    ("Excel",            re.compile(r"\bexcel\b", re.I)),
    ("Spark",            re.compile(r"\bapache\s+spark\b|\bpyspark\b|\bspark\b", re.I)),
    ("Hadoop",           None),
    ("Airflow",          re.compile(r"\bairflow\b", re.I)),
    ("MLflow",           re.compile(r"mlflow", re.I)),
    # ── Practices ─────────────────────────────────────────────────────────
    ("REST API",         re.compile(r"rest[\s\-]?api|restful", re.I)),
    ("Microservices",    None),
    ("Agile",            None),
    ("Scrum",            None),
    ("OOP",              re.compile(r"\boop\b|object[\s\-]+oriented", re.I)),
    ("Data Structures",  re.compile(r"data\s+structures", re.I)),
    ("Algorithms",       None),
    ("System Design",    re.compile(r"system\s+design", re.I)),
    ("Unit Testing",     re.compile(r"unit\s+test(?:ing)?", re.I)),
    ("Postman",          None),
]

# ── Education degree / institution patterns (word-boundary safe) ──────────
_EDU_DEGREE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bbachelor", re.I),
    re.compile(r"\bmaster", re.I),
    re.compile(r"\bph\.?d\b", re.I),
    re.compile(r"\bb\.?\s?tech\b", re.I),
    re.compile(r"\bm\.?\s?tech\b", re.I),
    re.compile(r"\bb\.?\s?e\.?\b", re.I),
    re.compile(r"\bm\.?\s?e\.?\b", re.I),
    re.compile(r"\bb\.?\s?sc\b", re.I),
    re.compile(r"\bm\.?\s?sc\b", re.I),
    re.compile(r"\bmba\b", re.I),
    re.compile(r"\bbca\b", re.I),
    re.compile(r"\bmca\b", re.I),
    re.compile(r"\bb\.?\s?com\b", re.I),
    re.compile(r"\bdiploma\b", re.I),
    re.compile(r"\bdegree\b", re.I),
    re.compile(r"\buniversity\b", re.I),
    re.compile(r"\bcollege\b(?!ague)", re.I),     # not "colleague"
    re.compile(r"\binstitute\b(?!d\b)", re.I),    # not "instituted"
    re.compile(r"(?<![a-zA-Z])school\b", re.I),   # not "preschool"
    re.compile(r"\bgpa\b", re.I),
    re.compile(r"\bgrade\b", re.I),
    re.compile(r"\bgraduat", re.I),
    re.compile(r"\bcgpa\b", re.I),
    re.compile(r"\bpercentage\b", re.I),
]


# ══════════════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ══════════════════════════════════════════════════════════════════════════

def _clean_text(text: str) -> str:
    """
    Normalise raw text from pdfplumber before any parsing is done.

    Operations applied (in order):
    1. Strip (cid:NNN) artifacts  — BUG-B FIX
       pdfplumber emits "(cid:127)" for bullet characters and undecodable
       glyphs.  These corrupt the lines they appear on.
    2. NFKC Unicode normalisation
       Converts ligatures (ﬁ→fi), fullwidth ASCII, etc.
    3. Replace exotic whitespace (non-breaking space, thin space, etc.)
       with regular spaces.
    4. Convert smart quotes and typographic dashes to ASCII equivalents.
    5. Collapse runs of 3+ spaces to two spaces (preserves indentation
       signals while removing noise from column-layout PDFs).
    """
    # BUG-B FIX: Remove CID artifacts produced by pdfplumber
    # Pattern: (cid:  followed by one or more digits  followed by )
    text = re.sub(r"\(cid:\d+\)", " ", text)

    # NFKC normalisation: ligatures, fullwidth characters, etc.
    text = unicodedata.normalize("NFKC", text)

    # Exotic whitespace → regular space
    text = re.sub(r"[\u00a0\u202f\u2009\u200b\u00ad\u2060]", " ", text)

    # Smart quotes → ASCII
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')

    # Typographic dashes → ASCII hyphen
    text = text.replace("\u2013", "-").replace("\u2014", "-")

    # Bullet-like characters → a space (they appear between skill names)
    text = re.sub(r"[•·▪▸◆►❖✦✔]", " ", text)

    # Collapse runs of spaces (but preserve newlines)
    text = re.sub(r" {3,}", "  ", text)

    return text


# ══════════════════════════════════════════════════════════════════════════
# PDF EXTRACTION
# ══════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract all text from a PDF file, page by page.

    - _clean_text() is applied per page (removes CID, normalises Unicode).
    - Pages joined with double-newline to prevent cross-page line merging.
    - Explicit None guard for image-only pages.
    - Per-page try/except so one broken page doesn't abort the document.
    - Returns "" on any failure (never None).
    """
    pages: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            log.info("Opened '%s' — %d page(s).", file_path, len(pdf.pages))
            for i, page in enumerate(pdf.pages, 1):
                try:
                    raw = page.extract_text()
                    if raw is None:
                        log.warning("Page %d returned None (image-only?).", i)
                        continue
                    pages.append(_clean_text(raw))
                    log.debug("Page %d: %d chars.", i, len(raw))
                except Exception as page_err:
                    log.error("Page %d extraction failed: %s", i, page_err)
    except FileNotFoundError:
        log.error("File not found: %s", file_path)
        return ""
    except Exception as err:
        log.error("Cannot open PDF '%s': %s", file_path, err)
        return ""

    if not pages:
        log.warning("No text extracted from '%s'.", file_path)
        return ""

    full = "\n\n".join(pages)
    log.info("Total extracted: %d chars from %d page(s).", len(full), len(pages))
    return full.strip()


# ══════════════════════════════════════════════════════════════════════════
# SECTION MAP  (BUG-C / BUG-E FIX)
# ══════════════════════════════════════════════════════════════════════════

def _build_section_map(text: str) -> dict[str, str]:
    """
    Split the resume text into named sections by detecting section headers.

    Returns a dict where:
        key   = canonical upper-case section name  (e.g. "EDUCATION")
        value = all lines belonging to that section, joined as a string

    Special key "HEADER" holds everything BEFORE the first section header
    (typically: name, contact info, job title).

    This is the core fix for BUG-C and BUG-E.  Once sections are isolated,
    extract_education() can operate ONLY on the EDUCATION section text, and
    extract_experience() operates ONLY on the EXPERIENCE section text,
    completely preventing cross-section contamination.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {}
    current_key = "HEADER"   # Text before any header goes here
    sections[current_key] = []

    for line in lines:
        stripped = line.strip()
        if _SECTION_HEADER_RE.match(stripped):
            # Normalise the section key (collapse internal spaces, upper-case)
            key = re.sub(r"\s+", " ", stripped.upper().rstrip(":"))
            current_key = key
            if current_key not in sections:
                sections[current_key] = []
            # Don't append the header line itself — it's just a label
        else:
            sections[current_key].append(line)

    # Convert lists to stripped strings
    result = {k: "\n".join(v).strip() for k, v in sections.items()}
    log.debug("Section map keys: %s", list(result.keys()))
    return result


def _get_section(section_map: dict[str, str], *candidates: str) -> str:
    """
    Return the text of the first matching section from a list of candidate names.

    Tries exact match first, then prefix match so that
    "WORK EXPERIENCE" is found when you ask for "EXPERIENCE".

    Returns "" if nothing found.
    """
    # Exact match
    for name in candidates:
        key = name.upper()
        if key in section_map:
            return section_map[key]

    # Prefix match (e.g. "EXPERIENCE" matches "PROFESSIONAL EXPERIENCE")
    for name in candidates:
        key = name.upper()
        for skey, sval in section_map.items():
            if key in skey or skey in key:
                return sval

    return ""


# ══════════════════════════════════════════════════════════════════════════
# FIELD EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════

def extract_email(text: str) -> str:
    """
    Find the first valid email address.
    Strict TLD check (2–6 alpha chars) avoids version-string false matches.
    """
    pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,6}"
    )
    for match in pattern.finditer(text):
        candidate = match.group()
        domain = candidate.split("@", 1)[1]
        if "." in domain:
            log.info("Email: %s", candidate)
            return candidate
    log.info("No email found.")
    return ""


def extract_phone(text: str) -> str:
    """
    Find a phone number using a family of non-capturing-group patterns.
    Returns the first match whose digit-only count is >= 10.
    """
    for pat in _PHONE_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group()
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 10:
                log.info("Phone: %s  (digits: %s)", raw.strip(), digits)
                return raw.strip()
    log.info("No phone number found.")
    return ""


def _is_likely_name(line: str) -> bool:
    """
    Returns True if a line of text looks like a person's full name.

    Rules applied (all must pass):
    1. Non-empty after stripping.
    2. Not in the document-header blocklist ("Resume", "CV", etc.).
    3. Not ALL-UPPERCASE (section headers are usually all-caps).
    4. Contains no typical non-name characters: @ : / \\ digits | • ( )
    5. Word count is between 2 and 5.
    6. Every word starts with an uppercase letter (Title Case).
    7. Every word contains only letters, hyphens, or apostrophes.
    8. BUG-A FIX: No word matches a known job-title word.
       This rejects "Machine Learning Engineer", "Data Scientist", etc.
    """
    line = line.strip()
    if not line:
        return False
    if line.lower() in _HEADER_BLOCKLIST:
        return False
    # ALL-CAPS lines are section headers, not names
    if line.isupper() and len(line) > 3:
        return False
    # Lines with these characters are contact info, URLs, or section labels
    if re.search(r"[@:/\\\d|•·,\(\)\[\]<>]", line):
        return False
    words = line.split()
    if not (2 <= len(words) <= 5):
        return False
    # Every word must start with a capital letter
    # (allow connectors like "van", "de", "la", "bin")
    connectors = {"van", "de", "la", "von", "bin", "binti", "al", "el"}
    if not all(w[0].isupper() or w.lower() in connectors for w in words):
        return False
    # Every word must be purely alphabetic (hyphens and apostrophes allowed)
    if not all(re.match(r"[A-Za-z][A-Za-z\-']*$", w) for w in words):
        return False
    # BUG-A FIX: Reject lines that contain job-title vocabulary
    if any(w.lower() in _JOB_TITLE_WORDS for w in words):
        return False
    return True


def extract_name(text: str, section_map: Optional[dict[str, str]] = None) -> str:
    """
    Extract the candidate's full name.

    BUG-A FIX  — Name is searched ONLY in the HEADER section (text before
    the first section keyword like SKILLS / EDUCATION / EXPERIENCE).
    This prevents job titles and section content from being mistaken for a name.

    BUG-D FIX  — Heuristic now scans header text only (not 20 lines of full doc).

    Strategy 1 (Heuristic — preferred):
        Scan each line of the HEADER section.
        Return the first line that passes _is_likely_name().

    Strategy 2 (spaCy NER — fallback):
        Run NER on the header text only.
        Accept the first PERSON or ORG entity that also passes _is_likely_name().
        (ORG is included because spaCy sometimes mislabels non-English names.)

    Strategy 3 (Last resort):
        Return the first non-empty line of the header that is not in the
        blocklist and not all-uppercase, even if _is_likely_name() fails.
        This handles single-word names or unusual formats.
    """
    # Determine the text to search: HEADER section if section_map is available
    if section_map is not None:
        search_text = section_map.get("HEADER", "")
    else:
        # Fall back: use only the first 20 lines of the document
        search_text = "\n".join(text.strip().split("\n")[:20])

    if not search_text.strip():
        search_text = "\n".join(text.strip().split("\n")[:20])

    # ── Strategy 1: Heuristic scan of header lines ────────────────────────
    for line in search_text.split("\n"):
        if _is_likely_name(line):
            log.info("Name via heuristic: %s", line.strip())
            return line.strip()

    # ── Strategy 2: spaCy NER on header text ──────────────────────────────
    if nlp:
        try:
            doc = nlp(search_text[:1000])
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG"):
                    candidate = ent.text.strip()
                    if _is_likely_name(candidate):
                        log.info("Name via NER (%s): %s", ent.label_, candidate)
                        return candidate
        except Exception as ner_err:
            log.warning("spaCy NER error: %s", ner_err)

    # ── Strategy 3: Last-resort — first reasonable non-empty header line ──
    for line in search_text.split("\n"):
        stripped = line.strip()
        if (
            stripped
            and stripped.lower() not in _HEADER_BLOCKLIST
            and not stripped.isupper()
            and not re.search(r"[@:/\\\d]", stripped)
            and 1 <= len(stripped.split()) <= 6
        ):
            log.warning("Name via last-resort fallback: %s", stripped)
            return stripped

    log.warning("Name not found.")
    return "Unknown"


def extract_skills(text: str) -> list[str]:
    """
    Scan text for known skills using pre-compiled regex patterns.

    Each entry in _SKILL_TABLE carries either:
    - A pre-compiled pattern for ambiguous / special-character skills.
    - None → a generic word-boundary pattern is built from the display name.

    Returns a sorted, deduplicated list of matched skill display names.
    """
    found: set[str] = set()

    for display_name, pattern in _SKILL_TABLE:
        if pattern is not None:
            if pattern.search(text):
                found.add(display_name)
        else:
            # Generic: match the skill name as a whole word (case-insensitive)
            pat = re.compile(
                r"(?<![a-zA-Z])" + re.escape(display_name) + r"(?![a-zA-Z])",
                re.I,
            )
            if pat.search(text):
                found.add(display_name)

    result = sorted(found)
    log.info("Skills found (%d): %s", len(result), result)
    return result


def extract_education(text: str, section_map: Optional[dict[str, str]] = None) -> list[str]:
    """
    Extract education entries.

    BUG-C / BUG-E FIX — Operates ONLY on the EDUCATION section text.
    If the section map is available, we pass only the EDUCATION block
    to the extraction logic, so achievement lines and experience lines
    from other sections can never appear here.

    Within the education section:
    - Lines matching any _EDU_DEGREE_PATTERNS are primary education entries.
    - The immediately following non-empty line is attached as context
      (e.g., university name, GPA) if it doesn't look like a new entry
      or a different section.
    """
    # BUG-C FIX: work only on the education section
    if section_map is not None:
        edu_text = _get_section(
            section_map,
            "EDUCATION",
            "ACADEMIC BACKGROUND",
            "ACADEMIC QUALIFICATIONS",
            "EDUCATIONAL QUALIFICATIONS",
            "QUALIFICATIONS",
        )
    else:
        edu_text = text  # fallback if section map not provided

    if not edu_text.strip():
        log.info("No education section found.")
        return []

    lines = edu_text.split("\n")
    entries: list[str] = []
    i = 0

    while i < len(lines) and len(entries) < 10:
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        # Check if this line contains an education degree / institution keyword
        if any(pat.search(line) for pat in _EDU_DEGREE_PATTERNS):
            entry_lines = [line]

            # Look ahead: attach the next 1–2 non-empty lines as context
            # (these are typically: institution name, year, GPA)
            j = i + 1
            attached = 0
            while j < len(lines) and attached < 2:
                nxt = lines[j].strip()
                if not nxt:
                    j += 1
                    continue
                # Stop if the next line looks like another edu entry
                if any(pat.search(nxt) for pat in _EDU_DEGREE_PATTERNS):
                    break
                # Stop if it looks like a section header
                if _SECTION_HEADER_RE.match(nxt):
                    break
                entry_lines.append(nxt)
                attached += 1
                j += 1

            entries.append("  |  ".join(entry_lines))
            # Skip the lines we already consumed as context
            i = j
            continue

        i += 1

    log.info("Education entries: %d", len(entries))
    return entries


def extract_experience(text: str, section_map: Optional[dict[str, str]] = None) -> list[str]:
    """
    Extract work experience entries.

    BUG-C / BUG-E FIX — Operates ONLY on the EXPERIENCE section text.
    Education degree lines (which contain years like "B.Tech 2016–2020")
    can no longer contaminate this list.

    Detection logic:
    - Lines with a year range or duration ("Jun 2021 – Present", "2019 - 2022")
    - Lines with job-title keywords (Engineer, Developer, Analyst, etc.)

    Context attachment:
    - The 1–2 lines immediately following a detected entry header are
      attached (company name, responsibilities summary, etc.) if they
      don't look like a new entry or section header.
    """
    # BUG-C FIX: work only on the experience section
    if section_map is not None:
        exp_text = _get_section(
            section_map,
            "EXPERIENCE",
            "WORK EXPERIENCE",
            "PROFESSIONAL EXPERIENCE",
            "EMPLOYMENT HISTORY",
            "WORK HISTORY",
            "INTERNSHIP",
            "INTERNSHIPS",
        )
    else:
        exp_text = text  # fallback

    if not exp_text.strip():
        log.info("No experience section found.")
        return []

    year_re = re.compile(r"\b(19|20)\d{2}\b")
    # Date range signals: "Jun 2021 - Present", "2019 – 2022", "Jan 2020 to Dec 2021"
    date_range_re = re.compile(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|"
        r"march|april|june|july|august|september|october|november|december)?"
        r"\s*\d{4}\s*[-–to]+\s*(present|current|now|\d{4})",
        re.I,
    )
    title_re = re.compile(
        r"\b(engineer|developer|analyst|manager|architect|consultant|"
        r"designer|intern|lead|director|officer|specialist|scientist|"
        r"administrator|coordinator|programmer|devops|sre|researcher|"
        r"associate|executive|head|president|vice)\b",
        re.I,
    )

    lines = exp_text.split("\n")
    seen: set[str] = set()
    entries: list[str] = []
    i = 0

    while i < len(lines) and len(entries) < 10:
        line = lines[i].strip()

        if not line or line in seen:
            i += 1
            continue

        is_date_line = date_range_re.search(line) or (
            year_re.search(line) and len(line) < 60
        )
        is_title_line = title_re.search(line) and len(line) >= 8

        if is_date_line or is_title_line:
            seen.add(line)
            entry_lines = [line]

            # Attach up to 2 context lines (company, summary, tech stack)
            j = i + 1
            attached = 0
            while j < len(lines) and attached < 2:
                nxt = lines[j].strip()
                if not nxt:
                    j += 1
                    continue
                if _SECTION_HEADER_RE.match(nxt):
                    break
                if date_range_re.search(nxt) or (year_re.search(nxt) and title_re.search(nxt)):
                    break
                entry_lines.append(nxt)
                attached += 1
                j += 1

            entries.append("  |  ".join(entry_lines))
            i = j
            continue

        i += 1

    log.info("Experience entries: %d", len(entries))
    return entries


# ══════════════════════════════════════════════════════════════════════════
# MASTER PARSER
# ══════════════════════════════════════════════════════════════════════════

def parse_resume(text: str) -> dict:
    """
    Orchestrates all field extractors and returns a single result dict.

    Key change: _build_section_map() is called ONCE at the top.
    The section map is then passed to every extractor so they all operate
    on their own isolated section text.  This is the root fix for
    BUG-A, BUG-C, BUG-D, BUG-E — all of which stem from extractors
    operating on the full document text without section awareness.

    extract_skills() intentionally still receives the FULL text because
    skills are often listed in multiple sections (SKILLS, PROJECTS,
    EXPERIENCE) and scanning all of them gives the best coverage.
    """
    log.info("Parsing resume (%d chars).", len(text))

    # Build section map once; reuse for every extractor
    section_map = _build_section_map(text)

    # Skills: scan full text for maximum coverage
    skills = extract_skills(text)

    result = {
        "name":               extract_name(text, section_map),
        "email":              extract_email(text),
        "phone":              extract_phone(text),
        "skills":             skills,
        "education":          extract_education(text, section_map),
        "experience":         extract_experience(text, section_map),
        "total_skills_found": len(skills),
    }

    log.info(
        "Done — name=%r  email=%r  phone=%r  skills=%d  edu=%d  exp=%d",
        result["name"], result["email"], result["phone"],
        result["total_skills_found"],
        len(result["education"]), len(result["experience"]),
    )
    return result