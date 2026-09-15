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


# ── Stage 2/3: Activation and Execution via Tool ─────────────────────

@tool
def read_skill(skill_name: str) -> str:
    """
    Load the full SKILL.md instructions and taxonomy values for a given domain skill.
    Call this tool BEFORE responding if the paragraph relates to one of the available skills.
    Pass the exact 'name' of the skill from the available classification domains.
    """
    skill_path = _SKILLS_DIR / skill_name / "SKILL.md"

    if not skill_path.exists():
        logger.warning(f"Skill file not found: {skill_path}")
        return f"Error: Skill '{skill_name}' not found. Please check the name and try again."

    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip YAML frontmatter (between --- markers)
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)

    logger.debug(f"Agent loaded skill '{skill_name}' via tool call.")
    return body.strip()


# ── Index Rebuilder ──────────────────────────────────────────────────

def rebuild_index():
    """
    Scan all SKILL.md files in knowledge/skills/ and regenerate
    the skill_index.yaml file from their YAML frontmatter.
    """
    skills_data = []

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

        skills_data.append({
            "name": name,
            "description": description,
        })

    index_data = {"skills": skills_data}

    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
        yaml.dump(index_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Rebuilt skill index with {len(skills_data)} skills → {_INDEX_FILE}")


# ── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--rebuild-index" in sys.argv:
        rebuild_index()
        print("✅ Skill index rebuilt successfully.")
    else:
        print(build_discovery_summary())
