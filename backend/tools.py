# tools.py
import subprocess
import ast
import sys
from pathlib import Path


# ====================== 工具 1：执行命令 ======================
def run_bash(command):
    print(f"\n🔧 [执行命令] {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )

        return (result.stdout + result.stderr)[:1200].strip() or "执行成功"

    except Exception as e:
        return f"命令错误：{str(e)}"


# ====================== 工具 2：读取文件 ======================
def read_file(filepath):
    print(f"\n📖 [读取文件] {filepath}")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        return f"读取失败：{str(e)}"


# ====================== 工具 3：写入文件 ======================
def write_file(filepath, content):
    print(f"\n✍️ [写入文件] {filepath}")

    try:
        path = Path(filepath)

        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"文件写入成功：{filepath}"

    except Exception as e:
        return f"写入失败：{str(e)}"


# ====================== 工具 4：最大公约数 ======================
def gcd_two_numbers(a: int, b: int):
    print(f"\n🔢 [计算GCD] {a} 和 {b}")

    x, y = abs(a), abs(b)

    while y:
        x, y = y, x % y

    return f"最大公约数：{x}"


# ====================== 工具 5：解析 Python 代码 ======================
def parse_python_code(code: str):
    """
    解析 Python 代码，提取：
    - import
    - 顶层函数
    - 异步函数
    - 类
    - 类方法
    - 顶层变量
    """
    print("\n🧾 [解析Python代码] 正在分析代码结构...")

    try:
        tree = ast.parse(code)

        imports = []
        functions = []
        async_functions = []
        classes = []
        class_methods = {}
        variables = []

        lines = code.strip().splitlines()
        line_count = len(lines)

        for node in tree.body:

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        imports.append(f"import {alias.name} as {alias.asname}")
                    else:
                        imports.append(f"import {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if alias.asname:
                        imports.append(f"from {module} import {alias.name} as {alias.asname}")
                    else:
                        imports.append(f"from {module} import {alias.name}")

            elif isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "line": node.lineno
                })

            elif isinstance(node, ast.AsyncFunctionDef):
                args = [arg.arg for arg in node.args.args]
                async_functions.append({
                    "name": node.name,
                    "args": args,
                    "line": node.lineno
                })

            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno
                })

                methods = []

                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        args = [arg.arg for arg in item.args.args]
                        methods.append({
                            "name": item.name,
                            "args": args,
                            "line": item.lineno
                        })

                    elif isinstance(item, ast.AsyncFunctionDef):
                        args = [arg.arg for arg in item.args.args]
                        methods.append({
                            "name": item.name,
                            "args": args,
                            "line": item.lineno,
                            "async": True
                        })

                class_methods[node.name] = methods

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables.append({
                            "name": target.id,
                            "line": node.lineno
                        })

            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    variables.append({
                        "name": node.target.id,
                        "line": node.lineno
                    })

        report = "📊 Python 代码解析报告\n"
        report += f"├─ 代码总行数：{line_count}\n"
        report += f"├─ 导入模块数量：{len(imports)}\n"
        report += f"├─ 顶层函数数量：{len(functions)}\n"
        report += f"├─ 异步函数数量：{len(async_functions)}\n"
        report += f"├─ 类数量：{len(classes)}\n"
        report += f"├─ 顶层变量数量：{len(variables)}\n"
        report += "└─ 状态：解析完成\n\n"

        if imports:
            report += "📦 导入模块：\n"
            for item in imports:
                report += f"  - {item}\n"
            report += "\n"

        if variables:
            report += "🧩 顶层变量：\n"
            for var in variables:
                report += f"  - {var['name']}，第 {var['line']} 行\n"
            report += "\n"

        if functions:
            report += "🔧 顶层函数：\n"
            for func in functions:
                args_text = ", ".join(func["args"])
                report += f"  - {func['name']}({args_text})，第 {func['line']} 行\n"
            report += "\n"

        if async_functions:
            report += "⚡ 异步函数：\n"
            for func in async_functions:
                args_text = ", ".join(func["args"])
                report += f"  - async {func['name']}({args_text})，第 {func['line']} 行\n"
            report += "\n"

        if classes:
            report += "🏗️ 类：\n"
            for cls in classes:
                class_name = cls["name"]
                report += f"  - class {class_name}，第 {cls['line']} 行\n"

                methods = class_methods.get(class_name, [])

                if methods:
                    report += "    方法：\n"
                    for method in methods:
                        args_text = ", ".join(method["args"])
                        prefix = "async " if method.get("async") else ""
                        report += f"      - {prefix}{method['name']}({args_text})，第 {method['line']} 行\n"
                else:
                    report += "    方法：无\n"

            report += "\n"

        report += "🧠 结构理解：\n"

        if classes and functions:
            report += "  - 这段代码同时包含类和函数，可能是一个模块化脚本或小型工具库。\n"
        elif classes:
            report += "  - 这段代码主要是面向对象结构，核心逻辑大概率封装在类中。\n"
        elif functions:
            report += "  - 这段代码主要由函数组成，属于过程式或工具函数风格。\n"
        else:
            report += "  - 这段代码没有明显函数或类，可能是简单脚本或配置代码。\n"

        return report.strip()

    except SyntaxError as e:
        return f"解析失败：Python 语法错误，第 {e.lineno} 行：{e.msg}"

    except Exception as e:
        return f"解析失败：{str(e)}"


RTL_MANUAL_SKILL_DIR = (
    Path(__file__).resolve().parent
    / "skills"
    / "catalog"
    / "rtl-manual-generation"
)


def run_skill_script(script_name, args, timeout=220):
    script_path = RTL_MANUAL_SKILL_DIR / "scripts" / script_name

    if not script_path.exists():
        return f"工具脚本不存在：{script_path}"

    cmd = [sys.executable, str(script_path), *args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"工具脚本执行超时：{script_name}"
    except Exception as e:
        return f"工具脚本执行失败：{str(e)}"

    output = (result.stdout + result.stderr).strip()

    if result.returncode != 0:
        return (
            f"工具脚本执行失败：{script_name}\n"
            f"returncode：{result.returncode}\n\n"
            f"{output or '无输出'}"
        )

    return output or "工具脚本执行完成。"


# ====================== 工具 6：Parser Tool ======================
def run_parser_tool(project_root: str = ".", rtl_inputs: str = "rtl"):
    """
    Parser Tool：

    职责：
        阅读 RTL / 源代码。

    当测试文件类型是 rtl 时：
        固定生成 parser_pipeline_rtl。

    输入：
        project_root: 项目根目录，默认 "."
        rtl_inputs: RTL 输入目录，默认 "rtl"

    输出：
        parser_pipeline_rtl/
    """
    print("\n[Parser Tool] 调用 rtl-manual-generation/scripts/run_parser_tool.py...")
    return run_skill_script(
        "run_parser_tool.py",
        [
            "--project-root",
            project_root,
            "--rtl-inputs",
            rtl_inputs,
        ],
    )


# ====================== 工具 7：Knowledge Tool ======================
def run_knowledge_tool(
    project_root: str = ".",
    top_module: str = "",
    audience: str = "newcomer",
    section_id: str = ""
):
    """
    Knowledge Tool：

    职责：
        阅读 parser 生成的产物。

    固定输入：
        parser_pipeline_rtl/

    固定输出：
        manual_ir/<top_module>/
    """
    print("\n[Knowledge Tool] 调用 rtl-manual-generation/scripts/run_knowledge_tool.py...")

    args = [
        "--project-root",
        project_root,
        "--top-module",
        top_module,
        "--audience",
        audience,
    ]

    if section_id:
        args.extend(["--section-id", section_id])

    return run_skill_script("run_knowledge_tool.py", args)


# ====================== 工具调度表 ======================
TOOL_HANDLERS = {
    "run_bash": run_bash,
    "read_file": read_file,
    "write_file": write_file,
    "gcd_two_numbers": gcd_two_numbers,
    "parse_python_code": parse_python_code,
    "run_parser_tool": run_parser_tool,
    "run_knowledge_tool": run_knowledge_tool,
}


# ====================== 工具说明书：给模型看 ======================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "执行 CMD / PowerShell / shell 命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "要读取的文件路径，例如 README.md、docs/xxx.md、manual_ir/top/context_pack.json"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "要写入的文件路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的内容"
                    }
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gcd_two_numbers",
            "description": "计算两个整数的最大公约数",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "integer",
                        "description": "第一个整数"
                    },
                    "b": {
                        "type": "integer",
                        "description": "第二个整数"
                    }
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_python_code",
            "description": "解析一段 Python 代码，提取函数、类、变量、导入模块等结构信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要解析的 Python 代码字符串"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_parser_tool",
            "description": "Parser Tool：阅读 RTL 源码目录，运行 parser pipeline，并固定生成 parser_pipeline_rtl 目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_root": {
                        "type": "string",
                        "description": "项目根目录，默认使用当前目录 ."
                    },
                    "rtl_inputs": {
                        "type": "string",
                        "description": "RTL 输入目录。用户说测试文件是 rtl 时，默认使用 rtl。"
                    }
                },
                "required": ["project_root", "rtl_inputs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_knowledge_tool",
            "description": "Knowledge Tool：读取 parser_pipeline_rtl，生成 manual_ir/<top_module>，并生成 validation_report.json 和 context_pack.json。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_root": {
                        "type": "string",
                        "description": "项目根目录，默认使用当前目录 ."
                    },
                    "top_module": {
                        "type": "string",
                        "description": "顶层模块名，例如 arm_soc_top"
                    },
                    "audience": {
                        "type": "string",
                        "description": "阅读对象，例如 newcomer、maintainer，默认 newcomer"
                    },
                    "section_id": {
                        "type": "string",
                        "description": "可选，只生成某个 section 的 ContextPack"
                    }
                },
                "required": ["project_root", "top_module"]
            }
        }
    }
]


# ====================== 工具选择辅助函数 ======================
def get_tool_name(tool):
    return tool["function"]["name"]


def get_tools_by_names(tool_names):
    selected_tools = []

    for tool in TOOLS:
        name = get_tool_name(tool)
        if name in tool_names:
            selected_tools.append(tool)

    return selected_tools


def get_handlers_by_names(tool_names):
    selected_handlers = {}

    for name in tool_names:
        if name in TOOL_HANDLERS:
            selected_handlers[name] = TOOL_HANDLERS[name]

    return selected_handlers


def remove_duplicate_names(names):
    result = []
    seen = set()

    for name in names:
        if name not in seen:
            result.append(name)
            seen.add(name)

    return result


def select_tools_for_task(user_input):
    """
    reference 机制入口。

    skill 负责：
    1. 判断是否触发
    2. 返回需要启用哪些 tool
    3. 返回 skill instruction
    4. 返回该 skill 需要读取的 reference files

    tools.py 负责：
    1. 根据 tool name 找到工具 schema
    2. 根据 tool name 找到真正的 handler
    """
    try:
        from .skills.registry import select_tool_names_for_task
    except ImportError:
        from skills.registry import select_tool_names_for_task

    (
        tool_names,
        active_skill_names,
        active_skill_instructions,
        active_reference_files
    ) = select_tool_names_for_task(user_input)

    tool_names = remove_duplicate_names(tool_names)

    active_tools = get_tools_by_names(tool_names)
    active_handlers = get_handlers_by_names(tool_names)

    return (
        active_tools,
        active_handlers,
        active_skill_names,
        active_skill_instructions,
        active_reference_files
    )


def get_all_tools_and_handlers():
    """
    兼容旧代码。
    """
    return TOOLS, TOOL_HANDLERS
