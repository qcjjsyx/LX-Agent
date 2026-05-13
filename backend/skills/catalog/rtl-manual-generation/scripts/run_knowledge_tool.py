import argparse
import os
import subprocess
import sys
from pathlib import Path


def package_env():
    skill_dir = Path(__file__).resolve().parents[1]
    package_dir = skill_dir / "packages"
    env = os.environ.copy()
    old_pythonpath = env.get("PYTHONPATH", "")

    paths = [str(package_dir)]
    if old_pythonpath:
        paths.append(old_pythonpath)

    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def run_knowledge_tool(
    project_root: str = ".",
    top_module: str = "",
    audience: str = "newcomer",
    section_id: str = "",
) -> str:
    if not top_module.strip():
        return "Knowledge failed: top_module is required."

    root = Path(project_root).resolve()
    parser_dir = root / "parser_pipeline_rtl"
    manual_ir_dir = root / "manual_ir" / top_module
    context_pack_output = manual_ir_dir / "context_pack.json"
    validation_report_output = manual_ir_dir / "validation_report.json"

    if not root.exists():
        return f"Knowledge failed: project_root does not exist: {root}"

    if not parser_dir.exists():
        return (
            "Knowledge failed: parser_pipeline_rtl was not found.\n"
            "Run run_parser_tool first so parser artifacts exist."
        )

    export_cmd = [
        sys.executable,
        "-m",
        "knowledge.manual_ir",
        "export",
        "--artifacts-root",
        "parser_pipeline_rtl",
        "--top-module",
        top_module,
        "--output-dir",
        str(Path("manual_ir") / top_module),
    ]

    validate_cmd = [
        sys.executable,
        "-m",
        "knowledge.manual_ir",
        "validate",
        "--manual-ir-dir",
        str(Path("manual_ir") / top_module),
        "--parser-artifacts-root",
        "parser_pipeline_rtl",
        "--output",
        str(Path("manual_ir") / top_module / "validation_report.json"),
    ]

    pack_cmd = [
        sys.executable,
        "-m",
        "knowledge.manual_ir",
        "pack",
        "--manual-ir-dir",
        str(Path("manual_ir") / top_module),
        "--audience",
        audience,
        "--output",
        str(Path("manual_ir") / top_module / "context_pack.json"),
    ]

    if section_id:
        pack_cmd.extend(["--section-id", section_id])

    steps = [
        ("Export Manual IR", export_cmd),
        ("Validate Manual IR", validate_cmd),
        ("Generate ContextPack", pack_cmd),
    ]
    logs = []

    try:
        for title, cmd in steps:
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=180,
                env=package_env(),
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            logs.append(
                f"\n===== {title} =====\n"
                f"Command: {' '.join(cmd)}\n"
                f"returncode: {result.returncode}\n"
                f"STDOUT:\n{stdout or 'None'}\n"
                f"STDERR:\n{stderr or 'None'}\n"
            )

            if result.returncode != 0:
                return "Knowledge Tool execution failed\n" + "\n".join(logs)
    except subprocess.TimeoutExpired:
        return "Knowledge failed: execution timed out."
    except Exception as exc:
        return f"Knowledge failed: {exc}"

    expected_items = [
        manual_ir_dir / "manifest.json",
        manual_ir_dir / "system_views.json",
        manual_ir_dir / "module_cards",
        manual_ir_dir / "channel_cards",
        manual_ir_dir / "component_contracts",
        manual_ir_dir / "flow_paths",
        manual_ir_dir / "reading_paths",
        context_pack_output,
        validation_report_output,
    ]
    missing = [str(path) for path in expected_items if not path.exists()]

    report = (
        "Knowledge Tool execution succeeded\n"
        "Input directory: parser_pipeline_rtl\n"
        f"Output directory: manual_ir/{top_module}\n\n"
    )

    if missing:
        report += "Some expected artifacts are missing:\n"
        report += "\n".join(f"- {item}" for item in missing)
    else:
        report += (
            "Generated key artifacts:\n"
            f"- manual_ir/{top_module}/manifest.json\n"
            f"- manual_ir/{top_module}/system_views.json\n"
            f"- manual_ir/{top_module}/module_cards/\n"
            f"- manual_ir/{top_module}/channel_cards/\n"
            f"- manual_ir/{top_module}/component_contracts/\n"
            f"- manual_ir/{top_module}/flow_paths/\n"
            f"- manual_ir/{top_module}/reading_paths/\n"
            f"- manual_ir/{top_module}/context_pack.json\n"
            f"- manual_ir/{top_module}/validation_report.json\n"
        )

    report += "\n".join(logs)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--top-module", required=True)
    parser.add_argument("--audience", default="newcomer")
    parser.add_argument("--section-id", default="")
    args = parser.parse_args()

    print(
        run_knowledge_tool(
            project_root=args.project_root,
            top_module=args.top_module,
            audience=args.audience,
            section_id=args.section_id,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
