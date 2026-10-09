"""
Skill Loader — Progressive Disclosure Engine
=============================================
Implements the Agent Skills pattern for regulatory taxonomy:

  Stage 1 (Discovery): Load lightweight index of all skill names
  Stage 2 (Activation): The LLM Agent decides which skill to load using the `read_skill` tool.
  Stage 3 (Execution): The LLM reads the SKILL.md and extracts the final JSON.
"""

import re
from pathlib import Path
from functools import lru_cache

import yaml
from langchain_core.tools import tool

from core.logger import get_logger

logger = get_logger(__name__)

# ── Paths ────────────────────────────────────────────────────────────
_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
_SKILLS_DIR = _KNOWLEDGE_DIR / "skills"
_INDEX_FILE = _KNOWLEDGE_DIR / "skill_index.yaml"


# ── Stage 1: Discovery ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_skill_index() -> list[dict]:
    """
    Load the lightweight skill index (name + description).
    Cached after first call.
    """
    if not _INDEX_FILE.exists():
        logger.warning(f"Skill index not found at {_INDEX_FILE}. Rebuilding...")
        rebuild_index()

    with open(_INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    skills = data.get("skills", [])
    logger.info(f"Loaded {len(skills)} skills from index")
    return skills


def build_discovery_summary() -> str:
    """
    Build a lightweight summary of all available skills for the system prompt.
    This is Stage 1 — only names and descriptions, minimal token cost.
    """
    index = load_skill_index()
    lines = ["Available classification domains (skills):"]
    for skill in index:
        lines.append(f"- **{skill['name']}**: {skill['description']}")
    return "\n".join(lines)


# ── Controlled vocabularies owned by SKILL.md files ──────────────────
# Each SKILL.md has "### Business Unit" and "### Themes" sections with bullets:
#     - <value> — optional usage hint
# The union across all skills is the approved list used for validation.

_BULLET_SEP = " \u2014 "


def _load_skill_list(skill_name: str, heading: str) -> list[str]:
    """Return the bullet values under '### <heading>' in one skill's SKILL.md (in order)."""
    skill_path = _SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        return []
    text = skill_path.read_text(encoding="utf-8")
    m = re.search(rf"^### {re.escape(heading)}\s*\n(.*?)(?=^### |^## |\Z)", text, re.DOTALL | re.MULTILINE)
    if not m:
        return []
    values = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            values.append(line[2:].split(_BULLET_SEP)[0].strip())
    return values


def _load_union(heading: str) -> list[str]:
    """Union of a section across every skill (not cached, so SKILL.md edits apply immediately)."""
    seen: dict[str, None] = {}
    if _SKILLS_DIR.exists():
        for d in sorted(_SKILLS_DIR.iterdir()):
            for v in _load_skill_list(d.name, heading):
                seen.setdefault(v, None)
    return list(seen)


def _check_section(heading: str) -> dict:
    owners: dict[str, list[str]] = {}
    empty = []
    per_skill: dict[str, set] = {}
    for d in sorted(_SKILLS_DIR.iterdir()):
        if not (d / "SKILL.md").exists():
            continue
        values = _load_skill_list(d.name, heading)
        per_skill[d.name] = set(values)
        if not values:
            empty.append(d.name)
        for v in values:
            owners.setdefault(v, []).append(d.name)
    union = set(owners)
    return {
        "total": len(union),
        "owners": owners,
        "skills_without_values": empty,
        "skills_missing_values": {s: sorted(union - v) for s, v in per_skill.items() if v and union - v},
    }


def load_skill_business_units(skill_name: str) -> list[str]:
    """Business units declared in one skill's SKILL.md."""
    return _load_skill_list(skill_name, "Business Unit")


def load_business_units() -> list[str]:
    """All approved business units (union across skills)."""
    return _load_union("Business Unit")


def load_themes() -> list[str]:
    """All approved themes (union across skills)."""
    return _load_union("Themes")


def check_business_units() -> dict:
    """Business units declared by more than one skill, and skills with none."""
    r = _check_section("Business Unit")
    return {
        "total": r["total"],
        "duplicates": {u: s for u, s in r["owners"].items() if len(s) > 1},
        "skills_without_business_units": r["skills_without_values"],
    }


def check_themes() -> dict:
    """Themes: total, skills with none, and skills that don't list every approved theme."""
    r = _check_section("Themes")
    return {
        "total": r["total"],
        "skills_without_themes": r["skills_without_values"],
        "skills_missing_themes": r["skills_missing_values"],
    }


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _normalize_to(value, allowed: list[str], label: str) -> str:
    """Snap a value to the allowed list (case/spacing-insensitive, then close fuzzy match)."""
    import difflib

    if value is None:
        return "N/A"
    v = str(value).strip()
    if v.upper() in ("N/A", "NA", ""):
        return "N/A"

    by_norm = {_norm_key(a): a for a in allowed}
    key = _norm_key(v)
    if key in by_norm:
        return by_norm[key]

    close = difflib.get_close_matches(key, list(by_norm), n=1, cutoff=0.9)
    if close:
        logger.warning(f"{label} '{v}' snapped to '{by_norm[close[0]]}'")
        return by_norm[close[0]]

    logger.warning(f"{label} '{v}' is not in the approved list")
    return v


def normalize_business_unit(value) -> str:
    """Snap an LLM-provided business unit to the approved list ('N/A' stays 'N/A')."""
    return _normalize_to(value, load_business_units(), "Business unit")


APPROVED_THEMES = [
    "Assessment",
    "Automation",
    "Customer Communication",
    "Customer Loan Documentation",
    "Declaration",
    "Definition",
    "Disclosure",
    "External Communication (other than customer)",
    "Governance",
    "Information",
    "Internal Communication",
    "Internal Communication (within bank, staff, branches)",
    "Monitoring",
    "Notification",
    "Policy",
    "Process",
    "Storage and records keeping",
    "System configuration",
    "Themes/ Other Attributes",
    "Verification",
]

_THEME_SYNONYMS = {
    # Rogue levels / BUs / text frequently mistaken for theme
    "exceptionhandling": "Process",
    "operations": "Process",
    "operationsmanagement": "Process",
    "compliance": "Policy",
    "compliancereporting": "External Communication (other than customer)",
    "forexretailbanking": "Process",
    "processandpolicy": "Process",
    "policyandprocess": "Policy",
    "riskmanagement": "Assessment",
    "risk": "Assessment",
    "customerprotection": "Customer Communication",
    "capitaladequacy": "Assessment",
    "licensing": "Governance",
    "corporategovernance": "Governance",
    "trainingandemployeecodeofconduct": "Policy",
    "training": "Internal Communication (within bank, staff, branches)",
    "audittrail": "Monitoring",
    "audit": "Monitoring",
    "reporting": "External Communication (other than customer)",
    "regulatoryreporting": "External Communication (other than customer)",
    "disclosures": "Disclosure",
    "recordkeeping": "Storage and records keeping",
    "storageandrecordkeeping": "Storage and records keeping",
    "storageandrecordskeeping": "Storage and records keeping",
    "recordskeeping": "Storage and records keeping",
    "internalcommunicationwithinbankstaffbranches": "Internal Communication (within bank, staff, branches)",
    "externalcommunication": "External Communication (other than customer)",
    "customercommunications": "Customer Communication",
    "systemconfiguration": "System configuration",
    "systemhealthcheck": "System configuration",
    "systemreconciliation": "Process",
    "duediligence": "Assessment",
}


def normalize_theme(value) -> str:
    """
    Snap an LLM-provided theme strictly to one of the 20 approved themes ('N/A' stays 'N/A').
    Prevents 'Exception Handling', 'Operations', etc. from ever appearing as theme.
    """
    import difflib

    if value is None:
        return "N/A"
    v = str(value).strip()
    if v.upper() in ("N/A", "NA", "", "NONE", "NULL"):
        return "N/A"

    if v in APPROVED_THEMES:
        return v

    key = _norm_key(v)
    if key in _THEME_SYNONYMS:
        snapped = _THEME_SYNONYMS[key]
        logger.info(f"Theme '{v}' mapped to approved theme '{snapped}' via synonym dictionary")
        return snapped

    by_norm = {_norm_key(a): a for a in APPROVED_THEMES}
    if key in by_norm:
        return by_norm[key]

    # Substring checks
    if "extern" in key or "other than customer" in key:
        return "External Communication (other than customer)"
    if "within bank" in key or "branch" in key:
        return "Internal Communication (within bank, staff, branches)"
    if "internal" in key:
        return "Internal Communication"
    if "customer loan" in key:
        return "Customer Loan Documentation"
    if "customer" in key:
        return "Customer Communication"
    if "storage" in key or "record" in key:
        return "Storage and records keeping"
    if "system" in key or "config" in key:
        return "System configuration"
    if "verif" in key:
        return "Verification"
    if "assess" in key:
        return "Assessment"
    if "auto" in key:
        return "Automation"
    if "declar" in key:
        return "Declaration"
    if "defin" in key:
        return "Definition"
    if "disclos" in key:
        return "Disclosure"
    if "govern" in key:
        return "Governance"
    if "monitor" in key:
        return "Monitoring"
    if "notif" in key:
        return "Notification"
    if "polic" in key:
        return "Policy"
    if "process" in key or "operat" in key or "procedure" in key:
        return "Process"
    if "info" in key:
        return "Information"

    # Fuzzy match
    close = difflib.get_close_matches(key, list(by_norm), n=1, cutoff=0.7)
    if close:
        snapped = by_norm[close[0]]
        logger.warning(f"Theme '{v}' fuzzy-snapped to '{snapped}'")
        return snapped

    logger.warning(f"Theme '{v}' is not an approved theme; defaulting to 'Process'")
    return "Process"


ALLOWED_PARA_TYPES = [
    "Action Para",
    "Information Para",
    "Future Effective",
    "Product or Service Not Offered",
    "One-Time Action",
    "Event Based",
    "Repealed",
    "Subsumed",
]

_PARA_TYPE_SYNONYMS = {
    # Information variants
    "information": "Information Para",
    "informationpara": "Information Para",
    "informationparagraph": "Information Para",
    "info": "Information Para",
    "infopara": "Information Para",
    "informational": "Information Para",
    "informationalpara": "Information Para",
    "informationalparagraph": "Information Para",
    "background": "Information Para",
    "context": "Information Para",

    # Action variants
    "action": "Action Para",
    "actionpara": "Action Para",
    "actionparagraph": "Action Para",
    "actionable": "Action Para",
    "directive": "Action Para",
    "instruction": "Action Para",

    # Future Effective variants
    "future": "Future Effective",
    "futureeffective": "Future Effective",
    "futureeffectivedate": "Future Effective",
    "futuredate": "Future Effective",
    "prospect": "Future Effective",
    "prospective": "Future Effective",

    # Product or Service Not Offered variants
    "productorservicenotoffered": "Product or Service Not Offered",
    "productnotoffered": "Product or Service Not Offered",
    "servicenotoffered": "Product or Service Not Offered",
    "notoffered": "Product or Service Not Offered",
    "unoffered": "Product or Service Not Offered",

    # One-Time Action variants
    "onetimeaction": "One-Time Action",
    "onetime": "One-Time Action",
    "singleaction": "One-Time Action",
    "nonrecurring": "One-Time Action",

    # Event Based variants
    "eventbased": "Event Based",
    "event": "Event Based",
    "eventdriven": "Event Based",
    "eventtriggered": "Event Based",

    # Repealed variants
    "repealed": "Repealed",
    "repeal": "Repealed",
    "revoked": "Repealed",
    "rescinded": "Repealed",

    # Subsumed variants
    "subsumed": "Subsumed",
    "subsume": "Subsumed",
    "integrated": "Subsumed",
    "superseded": "Subsumed",
}


def normalize_para_type(value) -> str:
    """
    Snap an LLM-provided paragraph type to one of the 8 canonical types:
      - 'Action Para'
      - 'Information Para'
      - 'Future Effective'
      - 'Product or Service Not Offered'
      - 'One-Time Action'
      - 'Event Based'
      - 'Repealed'
      - 'Subsumed'
    """
    import difflib

    if value is None:
        return "Information Para"
    v = str(value).strip()
    if v in ("Error", "error"):
        return "Error"
    if not v or v.lower() in ("unknown", "null", "none", "n/a", "na"):
        return "Information Para"

    # Exact match check
    if v in ALLOWED_PARA_TYPES:
        return v

    key = _norm_key(v)
    if key in _PARA_TYPE_SYNONYMS:
        snapped = _PARA_TYPE_SYNONYMS[key]
        logger.info(f"Para type '{v}' snapped to '{snapped}' via synonym mapping")
        return snapped

    # Check against normalized allowed list
    by_norm = {_norm_key(a): a for a in ALLOWED_PARA_TYPES}
    if key in by_norm:
        return by_norm[key]

    # Partial substring check
    if "info" in key:
        return "Information Para"
    if "onetime" in key or "one-time" in v.lower():
        return "One-Time Action"
    if "event" in key:
        return "Event Based"
    if "future" in key:
        return "Future Effective"
    if "product" in key or "service" in key:
        return "Product or Service Not Offered"
    if "repeal" in key or "revoke" in key:
        return "Repealed"
    if "subsum" in key:
        return "Subsumed"
    if "action" in key:
        return "Action Para"

    # Fuzzy match
    close = difflib.get_close_matches(key, list(by_norm), n=1, cutoff=0.7)
    if close:
        snapped = by_norm[close[0]]
        logger.warning(f"Para type '{v}' fuzzy-snapped to '{snapped}'")
        return snapped

    # Default fallback
    logger.warning(f"Para type '{v}' could not be matched; defaulting to 'Information Para'")
    return "Information Para"


def load_levels() -> list[tuple[str, str, str]]:
    """Load the master list of levels from knowledge/levels.csv."""
    import csv
    path = _KNOWLEDGE_DIR / "levels.csv"
    if not path.exists():
        return []
    levels = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip header
        for row in reader:
            if len(row) >= 3:
                levels.append((row[0].strip(), row[1].strip(), row[2].strip()))
    return levels


def normalize_levels(l1: str, l2: str, l3: str) -> tuple[str, str, str]:
    """Snap an LLM-provided Level 1, 2, 3 tuple to the exact approved list."""
    if l1 in (None, "N/A", "Unknown", "", "null") and l2 in (None, "N/A", "Unknown", "", "null"):
        return ("N/A", "N/A", "N/A")
        
    master_levels = load_levels()
    if not master_levels:
        return (str(l1), str(l2), str(l3))
        
    v_str = f"{l1} | {l2} | {l3}".strip()
    
    by_norm = {}
    for r1, r2, r3 in master_levels:
        norm_key = _norm_key(f"{r1}{r2}{r3}")
        by_norm[norm_key] = (r1, r2, r3)
        
    key = _norm_key(f"{l1}{l2}{l3}")
    if key in by_norm:
        return by_norm[key]
        
    import difflib
    close = difflib.get_close_matches(key, list(by_norm.keys()), n=1, cutoff=0.85)
    if close:
        res = by_norm[close[0]]
        logger.warning(f"Levels '{v_str}' snapped to '{res[0]} | {res[1]} | {res[2]}'")
        return res
        
    logger.warning(f"Levels '{v_str}' is not in the approved list, snapping to N/A")
    return ("N/A", "N/A", "N/A")



def load_skill_body(skill_name: str) -> str:
    """Return the SKILL.md body (frontmatter stripped), or '' if missing."""
    skill_path = _SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        logger.warning(f"Skill file not found: {skill_path}")
        return ""
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)
    return body.strip()


def select_skills(paragraph: str, max_skills: int = 2) -> list[str]:
    """
    Deterministically pick the skills whose index keywords best match the
    paragraph. Returns skill names ordered by score (empty list if none match).
    """
    text = paragraph.lower()
    scored: list[tuple[int, str]] = []
    for skill in load_skill_index():
        score = 0
        for kw in skill.get("keywords", []) or []:
            if re.search(rf"(?<![a-z0-9]){re.escape(str(kw).lower())}(?![a-z0-9])", text):
                score += 1
        if score:
            scored.append((score, skill["name"]))
    scored.sort(key=lambda s: -s[0])
    return [name for _, name in scored[:max_skills]]


def all_skill_names() -> list[str]:
    return [s["name"] for s in load_skill_index()]


# ── Stage 2/3: Activation and Execution via Tool ─────────────────────

@tool
def read_skill(skill_name: str) -> str:
    """
    Load the taxonomy (Business Units, Themes, Levels, Control Objectives) for a domain skill.
    Call this tool to inspect the approved values before outputting the final JSON classification.
    Pass the skill_name (e.g. 'treasury-front-office', 'operations-payment', 'corporate-banking').
    """
    import difflib

    target_name = skill_name.strip().lower()
    
    # Common aliases & legacy mappings
    aliases = {
        "treasury-operations": "treasury-front-office",
        "treasury": "treasury-front-office",
        "aml-kyc": "compliance-anti-money-laundering",
        "aml": "compliance-anti-money-laundering",
        "kyc": "compliance-anti-money-laundering",
        "corporate-governance": "audit",
        "governance": "audit",
        "customer-protection": "retail-branch-banking",
        "retail": "retail-branch-banking",
        "branch-banking": "retail-branch-banking",
        "forex-retail-banking": "trade-product-group",
        "forex": "trade-product-group",
        "trade": "trade-product-group",
        "it-cyber-security": "information-technology",
        "it": "information-technology",
        "cybersecurity": "information-technology",
        "lending-credit": "corporate-banking",
        "lending": "corporate-banking",
        "credit": "corporate-banking",
        "operations-payments": "operations-payment",
        "payments": "operations-payment",
        "payment": "operations-payment",
        "risk-management": "risk-enterprise-risk-management",
        "risk": "risk-enterprise-risk-management",
        "compliance-reporting": "operations-regulatory-reporting",
        "regulatory-reporting": "operations-regulatory-reporting",
        "hr": "human-resources",
    }
    
    if target_name in aliases:
        target_name = aliases[target_name]

    skill_path = _SKILLS_DIR / target_name / "SKILL.md"

    if not skill_path.exists():
        # Fuzzy match against all available skill names
        valid_skills = all_skill_names()
        close = difflib.get_close_matches(target_name, valid_skills, n=1, cutoff=0.5)
        if close:
            target_name = close[0]
            skill_path = _SKILLS_DIR / target_name / "SKILL.md"

    if not skill_path.exists():
        logger.warning(f"Skill file not found: {skill_path}")
        return f"Error: Skill '{skill_name}' not found. Available skills: {', '.join(all_skill_names())}"

    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip YAML frontmatter (between --- markers)
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)

    # Strip Few-Shot Examples section to keep tool response focused on taxonomy and prevent LLM confusion
    body = re.split(r"\n## Few-Shot Examples", body, maxsplit=1)[0]

    # Condense the 190-row global Levels table to avoid choking local models with 15KB tables
    def _condense_levels_table(match):
        raw_table = [line for line in match.group(1).strip().splitlines() if line.strip()]
        header = raw_table[:2]  # Header and separator
        rows = raw_table[2:]
        terms = [w.lower() for w in target_name.replace("-", " ").split() if len(w) > 2]
        matched_rows = [r for r in rows if any(t in r.lower() for t in terms)]
        other_rows = [r for r in rows if not any(t in r.lower() for t in terms)]
        selected = matched_rows[:15] + other_rows[: max(0, 20 - len(matched_rows))]
        return "### Levels (Top hierarchy matches for domain)\n\n" + "\n".join(header + selected) + "\n\n"

    body = re.sub(r"### Levels\s*\n(.*?)(?=\n### |\Z)", _condense_levels_table, body, flags=re.DOTALL)

    logger.info(f"Agent loaded skill '{target_name}' via tool call.")
    return body.strip()


# ── Index Rebuilder ──────────────────────────────────────────────────

def rebuild_index():
    """
    Scan all SKILL.md files in knowledge/skills/ and regenerate
    the skill_index.yaml file from their YAML frontmatter.
    """
    skills_data = []

    # Preserve keywords from the existing index (they are not in SKILL.md frontmatter)
    existing_keywords: dict[str, list] = {}
    if _INDEX_FILE.exists():
        try:
            with open(_INDEX_FILE, "r", encoding="utf-8") as f:
                for s in (yaml.safe_load(f) or {}).get("skills", []):
                    existing_keywords[s["name"]] = s.get("keywords", [])
        except Exception as e:
            logger.warning(f"Could not read existing index keywords: {e}")

    if not _SKILLS_DIR.exists():
        logger.warning(f"Skills directory not found: {_SKILLS_DIR}")
        return

    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract YAML frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            logger.warning(f"No frontmatter in {skill_file}")
            continue

        frontmatter = yaml.safe_load(match.group(1))
        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "").strip()

        entry = {
            "name": name,
            "description": description,
        }
        # Keywords: SKILL.md frontmatter wins; else keep what the index already had
        keywords = frontmatter.get("keywords") or existing_keywords.get(name)
        if keywords:
            entry["keywords"] = keywords
        skills_data.append(entry)

    index_data = {"skills": skills_data}

    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(
            "# Auto-generated skill index for progressive disclosure (Stage 1: Discovery)\n"
            "# To regenerate: python -m core.skill_loader --rebuild-index\n\n"
        )
        yaml.dump(index_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Rebuilt skill index with {len(skills_data)} skills → {_INDEX_FILE}")


# ── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--rebuild-index" in sys.argv:
        rebuild_index()
        print("✅ Skill index rebuilt successfully.")
    elif "--check-business-units" in sys.argv:
        report = check_business_units()
        print(f"Total business units across skills: {report['total']}")
        print(f"Duplicates (declared in >1 skill): {report['duplicates'] or 'none'}")
        print(f"Skills without business units: {report['skills_without_business_units'] or 'none'}")
    elif "--check-themes" in sys.argv:
        report = check_themes()
        print(f"Total themes across skills: {report['total']}")
        print(f"Skills without themes: {report['skills_without_themes'] or 'none'}")
        print(f"Skills not listing every theme: {report['skills_missing_themes'] or 'none'}")
    else:
        print(build_discovery_summary())
