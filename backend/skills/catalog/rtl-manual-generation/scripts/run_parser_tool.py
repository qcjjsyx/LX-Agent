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


def run_parser_tool(project_root: str = ".", rtl_inputs: str = "rtl") -> str:
    root = Path(project_root).resolve()
    output_dir = root / "parser_pipeline_rtl"

    if not root.exists():
        return f"Parser failed: project_root does not exist: {root}"

    inputs_path = root / rtl_inputs
    if not inputs_path.exists():
        return (
            f"Parser failed: RTL input directory does not exist: {inputs_path}\n"
            "Check rtl_inputs, for example rtl, test_data/rtl, or tests/fixtures/rtl."
        )

    cmd = [
        sys.executable,
        "-m",
        "parser.pipeline",
        "build",
        "--inputs",
        rtl_inputs,
        "--output",
        "parser_pipeline_rtl",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=180,
            env=package_env(),
        )
    except subprocess.TimeoutExpired:
        return "Parser failed: execution timed out."
    except Exception as exc:
        return f"Parser failed: {exc}"

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        return (
            "Parser Tool execution failed\n"
            f"Command: {' '.join(cmd)}\n"
            f"Working directory: {root}\n\n"
            f"STDOUT:\n{stdout or 'None'}\n\n"
            f"STDERR:\n{stderr or 'None'}"
        )

    expected_items = [
        output_dir / "project_index.json",
        output_dir / "build_report.json",
        output_dir / "modules",
        output_dir / "components",
    ]
    missing = [str(path) for path in expected_items if not path.exists()]

    report = (
        "Parser Tool execution succeeded\n"
        f"Project root: {root}\n"
        f"RTL input directory: {rtl_inputs}\n"
        "Output directory: parser_pipeline_rtl\n\n"
    )

    if missing:
        report += "Some expected artifacts are missing:\n"
        report += "\n".join(f"- {item}" for item in missing)
    else:
        report += (
            "Generated key artifacts:\n"
            "- parser_pipeline_rtl/project_index.json\n"
            "- parser_pipeline_rtl/build_report.json\n"
            "- parser_pipeline_rtl/modules/\n"
            "- parser_pipeline_rtl/components/\n"
        )

    report += f"\n\nSTDOUT:\n{stdout or 'None'}\n"
    report += f"\nSTDERR:\n{stderr or 'None'}"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rtl-inputs", default="rtl")
    args = parser.parse_args()

    print(run_parser_tool(args.project_root, args.rtl_inputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
