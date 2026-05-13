---
name: rtl-manual-generation
description: Generate structured code manuals for RTL or source-code projects using the parser and knowledge tools. Use when the user asks to generate a code manual, module manual, project manual, documentation from RTL, Manual IR, ContextPack, parser output, knowledge output, or manual_ir artifacts.
---

# RTL Manual Generation

Use this skill to generate a structured Markdown manual for RTL or source-code projects. Do not summarize RTL directly when the parser and knowledge artifacts are available; use the generated evidence chain.

## Core Rules

1. Do not inspect parser or knowledge implementation files unless the user explicitly asks to analyze those tools.
2. Treat `scripts/run_parser_tool.py` and `scripts/run_knowledge_tool.py` as skill-owned implementation scripts.
3. Use the exposed tools `run_parser_tool` and `run_knowledge_tool`; they are thin wrappers around the skill scripts.
4. Base the final manual on `manual_ir/<top_module>` evidence, especially `context_pack.json`.
5. Clearly mark evidence gaps as insufficient evidence instead of guessing.

## Workflow

1. Read available reference files listed by the skill metadata.
2. Summarize the parser tool, knowledge tool, inputs, outputs, and evidence boundary.
3. If `project_root` is missing, use `.`.
4. If the user says the test files are RTL but does not provide `rtl_inputs`, use `rtl`.
5. If `top_module` is missing, ask the user for it before running the knowledge tool.
6. Run `run_parser_tool(project_root, rtl_inputs)`.
7. Run `run_knowledge_tool(project_root, top_module)`.
8. Read `manual_ir/<top_module>/context_pack.json`.
9. Read other `manual_ir/<top_module>` files only when needed.
10. Plan the manual outline before writing the full manual.
11. Describe what each chapter will contain and which evidence supports it.
12. Generate the final Markdown manual.
13. If the user asks to save it, write it to `docs/manuals/<top_module>_generated.md`.

## Bundled Resources

- `scripts/run_parser_tool.py`: runs the parser pipeline and checks `parser_pipeline_rtl` artifacts.
- `scripts/run_knowledge_tool.py`: runs Manual IR export, validation, and ContextPack generation.
- `packages/parser/`: parser implementation used by `run_parser_tool.py`.
- `packages/knowledge/`: Manual IR and knowledge implementation used by `run_knowledge_tool.py`.
- `packages/tools/`: support package used by parser code.
- `references/skill_script_reference.md`: script and workflow reference for this skill.

The scripts set `PYTHONPATH` to `packages/` before invoking module commands, so use the exposed tools instead of importing these packages from application code.

## Suggested Chapters

Adapt the structure to the evidence instead of forcing every chapter:

- Project overview
- Top module
- Module hierarchy
- Key module responsibilities
- Ports and interfaces
- Channels, data flow, and control flow
- Handshake behavior
- Component contracts
- Flow paths
- Reading path
- Maintenance notes
- Risks and evidence gaps
