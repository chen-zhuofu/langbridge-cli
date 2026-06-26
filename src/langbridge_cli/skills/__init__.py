from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent


def load_skill(name):
    """Return the body of a skill's SKILL.md (YAML frontmatter stripped)."""
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    return _strip_frontmatter(text).strip()


def list_skills():
    """Return [(name, description), ...] for every skill folder with a SKILL.md.

    The folder name is the skill's id (what load_skill / read_skill take); the
    description comes from the SKILL.md frontmatter.
    """
    skills = []
    for path in sorted(SKILLS_DIR.iterdir()):
        skill_md = path / "SKILL.md"
        if path.is_dir() and skill_md.exists():
            meta = _frontmatter(skill_md.read_text(encoding="utf-8"))
            skills.append((path.name, meta.get("description", "")))
    return skills


def skill_catalog_text():
    """One '- name: description' line per skill, for prompt injection."""
    return "\n".join(f"- {name}: {description}" for name, description in list_skills())


def _frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    meta = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + len("\n---") :].lstrip("\n")
    return text
