# backend/skills/registry.py

from pathlib import Path

try:
    from .spec import SkillSpec, load_skill_from_directory, unique_names
except ImportError:
    from spec import SkillSpec, load_skill_from_directory, unique_names


SKILL_CATALOG_DIR = Path(__file__).resolve().parent / "catalog"

BASE_TOOL_RULES = (
    {
        "triggers": (
            "读取",
            "查看",
            "打开",
            "文件",
            ".txt",
            ".json",
            ".html",
            ".css",
            ".py",
            ".md",
        ),
        "tool_names": (
            "read_file",
        ),
    },
    {
        "triggers": (
            "写入",
            "创建文件",
            "修改文件",
            "保存",
        ),
        "tool_names": (
            "write_file",
        ),
    },
    {
        "triggers": (
            "运行命令",
            "执行命令",
            "终端执行",
            "cmd",
            "powershell",
            "安装依赖",
            "启动项目",
            "执行测试",
            "运行测试",
            "pip install",
            "dir",
            "ls",
        ),
        "tool_names": (
            "run_bash",
        ),
    },
    {
        "triggers": (
            "最大公约数",
            "gcd",
            "公约数",
        ),
        "tool_names": (
            "gcd_two_numbers",
        ),
    },
)


def load_all_skills() -> tuple[SkillSpec, ...]:
    if not SKILL_CATALOG_DIR.exists():
        return ()

    skills = []
    for skill_dir in sorted(SKILL_CATALOG_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill = load_skill_from_directory(skill_dir)
        if skill:
            skills.append(skill)

    return tuple(sorted(skills, key=lambda item: item.priority))


ALL_SKILLS: tuple[SkillSpec, ...] = load_all_skills()


def match_base_tool_names(user_input):
    text = user_input.lower()
    tool_names = []

    for rule in BASE_TOOL_RULES:
        if any(trigger.lower() in text for trigger in rule["triggers"]):
            tool_names.extend(rule["tool_names"])

    return tool_names


def collect_skill_result(selected_skills, base_tool_names=None):
    tool_names = list(base_tool_names or [])
    skill_names = []
    skill_instructions = []
    reference_files = []

    for skill in selected_skills:
        skill_names.append(skill.name)
        tool_names.extend(skill.tool_names)
        reference_files.extend(skill.reference_files)

        if skill.instruction:
            skill_instructions.append(
                f"【{skill.name} skill 指令】\n{skill.instruction}"
            )

    return (
        unique_names(tool_names),
        skill_names,
        skill_instructions,
        unique_names(reference_files),
    )


def select_tool_names_for_task(user_input):
    """
    Skill 选择入口。

    规则：
    1. 基础文件、命令、数学能力只是 tool 路由，不作为 skill 激活。
    2. 目录式 skill 位于 backend/skills/catalog/<skill-name>/。
    3. 高优先级 skill 命中后直接返回，避免普通 skill 干扰。
    4. 普通 skill 可以叠加。
    """
    base_tool_names = match_base_tool_names(user_input)

    high_priority_skills = [
        skill for skill in ALL_SKILLS
        if skill.priority < 50 and skill.matches(user_input)
    ]

    if high_priority_skills:
        return collect_skill_result(high_priority_skills)

    normal_skills = [
        skill for skill in ALL_SKILLS
        if skill.priority >= 50 and skill.matches(user_input)
    ]

    return collect_skill_result(normal_skills, base_tool_names)
