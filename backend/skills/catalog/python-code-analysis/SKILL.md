---
name: python-code-analysis
description: Analyze Python source files and snippets. Use when the user asks about Python code structure, imports, functions, classes, variables, module organization, main loops, or files such as backend/app.py, agent_core.py, tools.py, and other .py files.
---

# Python Code Analysis

Use this skill to inspect Python code structure before explaining or changing it.

## Workflow

1. Use `read_file` when the user refers to a local Python file path.
2. Use `parse_python_code` on the file content or provided snippet to extract imports, functions, classes, methods, and module-level variables.
3. Explain the code from the parsed structure first, then add source-level details only when needed.
4. If the user asks for edits, keep changes aligned with the existing project style and module boundaries.

## Notes

- Treat file reading as a shared base tool, not as a separate skill.
- Prefer concrete file paths and line-level references when explaining local code.
- Do not run shell commands unless the user explicitly asks to execute or test something.
