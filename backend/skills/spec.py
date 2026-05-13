from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    triggers: tuple[str, ...] = field(default_factory=tuple)
    tool_names: tuple[str, ...] = field(default_factory=tuple)
    instruction: str = ""
    reference_files: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 100

    def matches(self, user_input: str) -> bool:
        text = user_input.lower()
        return any(trigger.lower() in text for trigger in self.triggers)


def split_skill_markdown(content: str):
    if not content.startswith("---"):
        return {}, content.strip()

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content.strip()

    metadata = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")

    return metadata, parts[2].strip()


def load_skill_from_directory(skill_dir: Path):
    skill_path = skill_dir / "SKILL.md"
    metadata_path = skill_dir / "skill.json"

    if not skill_path.exists() or not metadata_path.exists():
        return None

    frontmatter, body = split_skill_markdown(
        skill_path.read_text(encoding="utf-8")
    )
    runtime_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    return SkillSpec(
        name=frontmatter["name"],
        description=frontmatter["description"],
        triggers=tuple(runtime_metadata.get("triggers", [])),
        tool_names=tuple(runtime_metadata.get("tool_names", [])),
        instruction=body,
        reference_files=tuple(runtime_metadata.get("reference_files", [])),
        priority=int(runtime_metadata.get("priority", 100)),
    )


def unique_names(names):
    result = []
    seen = set()

    for name in names:
        if name not in seen:
            result.append(name)
            seen.add(name)

    return result
