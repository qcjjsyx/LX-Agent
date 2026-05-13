# Skill Script Reference: Parser and Knowledge Tools

本文档说明本项目中适合作为 skill 脚本调用的 parser 与 knowledge 相关代码。重点是每个脚本的职责、输入输出、调用顺序和使用边界。

## 总体定位

这套脚本的主线是把 Verilog/SystemVerilog 工程转换成可供文档生成 agent 使用的结构化事实：

1. `parser.pipeline` 读取 RTL filelist 和 top filelist，生成 parser artifacts。
2. `knowledge.loaders` 把 parser artifacts 加载成内存知识库。
3. `knowledge.manual_ir` 把知识库转换成面向手册写作的 Manual IR。
4. `knowledge.manual_ir validate/pack/resolve` 为 skill 提供稳定的校验、取数和上下文打包接口。

推荐 skill 优先调用这些 CLI，而不是直接拼装底层函数：

```bash
python -m parser.pipeline build --inputs <rtl_project_dir> --output <parser_artifacts_dir>
python -m knowledge.manual_ir export --artifacts-root <parser_artifacts_dir> --top-module <top> --output-dir <manual_ir_dir>
python -m knowledge.manual_ir validate --manual-ir-dir <manual_ir_dir> --parser-artifacts-root <parser_artifacts_dir>
python -m knowledge.manual_ir pack --manual-ir-dir <manual_ir_dir> --audience newcomer
python -m knowledge.manual_ir resolve --manual-ir-dir <manual_ir_dir> --object-id module:<name>
```

## `parser/`

### `parser.pipeline`

`parser.pipeline` 是当前推荐的工程级 parser 入口，用来从 RTL 工程生成稳定 JSON artifacts。

#### `parser/pipeline/cli.py`

命令行入口。

主要命令：

```bash
python -m parser.pipeline build \
  --inputs <rtl_project_dir> \
  --output artifacts/parser_pipeline_result
```

`--inputs` 目前要求传入一个 RTL 工程目录，该目录必须包含：

- `read_rtl_list.tcl`
- `rtl_top_list.tcl`

输出目录会被重建，并写入：

- `project_index.json`
- `build_report.json`
- `modules/<module>.json`
- `components/<component>.json`

#### `parser/pipeline/hierarchy_builder.py`

工程级构建编排器。

主要职责：

- 校验输入目录是否包含 `read_rtl_list.tcl` 和 `rtl_top_list.tcl`。
- 调用 `module_index` 建立 module name 到源码路径的索引。
- 从 top module 开始递归构建层级。
- 根据 `boundary_policy` 决定实例目标是普通 module、derived component、helper、外部依赖还是可忽略外部单元。
- 为 module 生成 `interface`、`instances`、`direct_children`、`flow_graph`、`transitive_summary`。
- 为 component leaf 生成 component JSON。
- 汇总 `project_index` 和 `build_report`。

这是 parser pipeline 的核心文件。skill 一般不直接调用内部函数，除非需要在 Python 内嵌流程中使用：

```python
from parser.pipeline.hierarchy_builder import build_project
```

#### `parser/pipeline/module_index.py`

模块发现与 filelist 解析器。

主要职责：

- 解析 `.tcl` filelist 中出现的 `.v`、`.sv`、`.vh` 路径 token。
- 递归发现目录下的 `.v`、`.sv` 文件。
- 排除常见 testbench 文件，例如 `*_tb.v`、`tb_*.sv`。
- 处理 filelist 中同名文件的匹配，优先选择更靠近 filelist、路径更短且不在 `backup/copy/old` 目录下的文件。
- 建立 `module_name -> source_path` 索引。

#### `parser/pipeline/module_parser.py`

Verilog 文件级结构化解析器。

主要职责：

- 去除注释。
- 提取 module 名、参数区、端口区和 module body。
- 解析 ANSI 与部分非 ANSI 端口声明。
- 解析参数、局部 `wire/reg/logic` 信号。
- 解析实例化语句、参数覆盖和 named port connections。
- 推断 reset 端口。
- 为连接信号补充基础 `signal_role`。

输出会进入 module JSON，是后续 hierarchy、flow graph 和 Manual IR 的事实来源。

#### `parser/pipeline/boundary_policy.py`

解析边界策略。

主要职责：

- 判断一个实例目标应该继续递归解析为 module，还是截断为 derived component。
- 识别已知控制组件 family，例如 `SelSplit`、`NatSplit`、`WaitMerge`、`ArbMerge`、`MutexMerge`、`Fifo1`、`PmtFifo1`、`eventSource`。
- 识别 FIFO-like 命名。
- 将 `delay<number>U` / `delay<number>Unit` 识别为透明 helper。
- 将少量明确的外部目标标记为 ignored external，例如 `contTap`、`freeSetDelay`、`IUMB`。

该文件决定 parser 的抽象层级。修改它会直接影响哪些 Verilog 文件被展开、哪些被当成组件协议来描述。

#### `parser/pipeline/flow_inference.py`

信号角色与局部 flow graph 推断。

主要职责：

- 根据命名规则把信号分为 `event_drive`、`event_free`、`payload_data`、`condition`、`reset` 或 `unknown`。
- 解析简单拼接表达式，例如 `{a,b,c}`。
- 为 module 生成 `flow_graph.signals` 和 `flow_graph.edges`。
- 把透明 delay helper 转换成输入信号到输出信号的透明 flow 边。
- 汇总使用到的 component family。

注意：这里是命名规则和连接关系级别的静态推断，不解析 `always`、FSM、寄存器时序或过程语义。

#### `parser/pipeline/family_json_builder.py`

derived component JSON 构建器。

主要职责：

- 读取 `parser/schemas/json_templates/family_level.json` 中的 family 模板。
- 根据端口名推断 component 的 upstream、downstream、payload、condition、fire 角色。
- 把 family contract、release rule、flow semantics 写入 component JSON。
- 记录内部依赖，并声明 `stops_at_family_level: true`。

#### `parser/pipeline/cc_header_reader.py`

读取源码中的 `//@cc:` header。

主要职责：

- 从 Verilog 文件中提取连续 `//@cc:` 注释块。
- 使用 `tools.cc_header_tools.parser.parse_yaml_min` 做轻量 YAML 解析。

当前 pipeline 的 family/role 判断主要依赖命名和端口，`cc_header` 更多是兼容与扩展入口。

#### `parser/pipeline/result_writer.py`

结果写盘器。

主要职责：

- 重建输出目录。
- 写入 `modules/`、`components/`、`project_index.json`、`build_report.json`。

#### 兼容辅助文件

- `classifier.py`：包装 `boundary_policy`，返回简化 artifact 分类结果。
- `family_inference.py`：兼容旧调用的 family 推断 wrapper。
- `helper_units.py`：兼容旧调用的 delay helper 判断 wrapper。
- `errors.py`：定义构建 issue 数据结构。

### `parser.verilog`

`parser.verilog` 是较早期的轻量单文件 parser，适合快速提取一个 `.v` 文件的 top module、实例化子模块名和简单接口。

#### `parser/verilog/cli.py`

命令行入口：

```bash
python -m parser.verilog parse --file path/to/top.v --format json
python -m parser.verilog parse --file path/to/top.v --format text
```

输出包含：

- `parsed_file`
- `top_module_name`
- `internal_subnames`
- `interface`，如果端口列表可以被解析

#### `parser/verilog/parser.py`

轻量解析实现。

主要职责：

- 去注释。
- 找到第一个顶层 `module ... endmodule`。
- 提取实例化模块类型名。
- 解析简单端口列表，生成 `inputs`、`output.ports`、`inout`、`reset`。

使用边界：

- 只接受 `.v` 文件。
- 不适合作为完整工程解析入口。
- 不建立 hierarchy，也不生成 component contract 或 flow graph。

#### `parser/verilog/run_top_parsing.py`

固定目标文件批量解析脚本，偏示例/历史用途。

当前脚本内置了若干 CPU 示例路径。作为 skill 使用时不建议直接依赖它，除非先确认这些路径在当前仓库中存在并符合你的目标工程。

## `knowledge/`

### `knowledge.loaders`

#### `knowledge/loaders/knowledge_base.py`

parser artifacts 加载器。

主要职责：

- 读取 `project_index.json`。
- 读取 `modules/*.json` 和 `components/*.json`。
- 封装成 `ProjectKnowledgeBase`。
- 提供 `kb.get(name)` 与 `kb.all_records()`。
- 为检索提供 `ArtifactRecord.searchable_text()`。

Python 调用示例：

```python
from pathlib import Path
from knowledge.loaders.knowledge_base import load_knowledge_base

kb = load_knowledge_base(Path("artifacts/parser_pipeline_result"))
record = kb.get("cpu_top")
```

### `knowledge.retrieval`

#### `knowledge/retrieval/retriever.py`

轻量关键词检索器。

主要职责：

- 对问题分词。
- 根据 artifact 名称、文件路径、children、family、contract 等字段打分。
- 返回最相关的 module/component records。
- 如果选中 module，会补充部分直接子 module/component，帮助回答架构问题。

这是规则检索，不是向量检索。适合作为 skill 的快速上下文选择辅助。

### `knowledge.manual_ir`

`knowledge.manual_ir` 是面向手册生成的核心知识表示层。它把 parser artifacts 重组为更适合写作和问答的对象。

#### `knowledge/manual_ir/cli.py`

Manual IR 的稳定命令行接口。

支持四类命令：

```bash
python -m knowledge.manual_ir export \
  --artifacts-root artifacts/parser_pipeline_result \
  --top-module <top> \
  --output manual_ir.json

python -m knowledge.manual_ir export \
  --artifacts-root artifacts/parser_pipeline_result \
  --top-module <top> \
  --output-dir artifacts/manual_ir/<top>

python -m knowledge.manual_ir validate \
  --manual-ir-dir artifacts/manual_ir/<top> \
  --parser-artifacts-root artifacts/parser_pipeline_result

python -m knowledge.manual_ir pack \
  --manual-ir-dir artifacts/manual_ir/<top> \
  --audience newcomer \
  --output context_pack.json

python -m knowledge.manual_ir resolve \
  --manual-ir-dir artifacts/manual_ir/<top> \
  --object-id module:<top>
```

skill 推荐使用 split export，即 `--output-dir`。这样后续可以按对象 id 精确加载，而不是每次读取一个大 JSON。

#### `knowledge/manual_ir/models.py`

Manual IR 数据模型定义。

主要对象：

- `SystemView`：top module 的系统视图，包含边界接口、主模块、主组件、families、外部依赖和全局风险。
- `ModuleCard`：单个 module 的手册卡片，包含职责、关键接口、子模块、子组件、反压点、风险点。
- `ChannelCard`：以 drive/free/payload 为核心的局部 channel 摘要。
- `ComponentContract`：derived component 的协议卡片，包含 family、role mapping、semantic contract、release rule、backpressure behavior。
- `FlowPath`：module-local event/data/completion flow 路径。
- `ReadingPath`：面向 `newcomer`、`maintainer`、`reviewer` 的手册阅读/写作路径。
- `ManualIRIndexes`：按 id、module、family、tag 建立轻量索引。

这些对象都保留 `source_refs`、`warnings` 和 `confidence`，用于控制手册生成时的证据边界。

#### `knowledge/manual_ir/builder.py`

Manual IR 构建器。

主要职责：

- 从 `ProjectKnowledgeBase` 中以 top module 为起点收集可达 module/component。
- 构建 `SystemView`、`ModuleCard`、`ComponentContract`、`ChannelCard`、`FlowPath`、`ReadingPath`。
- 根据 parser artifact 的 `interface_summary`、`instances`、`flow_graph`、`direct_children` 和 family contract 生成文档友好的摘要。
- 构建 `indexes`。
- 记录 partial flow、low-confidence flow、外部依赖等 warnings。

Python 调用示例：

```python
from knowledge.manual_ir import build_manual_ir

manual_ir = build_manual_ir(kb, "cpu_top")
payload = manual_ir.to_dict()
```

#### `knowledge/manual_ir/split_store.py`

split Manual IR 读取工具。

主要职责：

- 加载 `manifest.json`。
- 建立 `object_id -> file` catalog。
- 通过稳定 id 解析单个对象，例如 `module:cpu_top`、`component:cFifo1_cpu`、`flow:cpu_top:i_drv`。
- 列出和选择 `ReadingPath`。

适合 skill 在写某一节手册时精确取对象。

#### `knowledge/manual_ir/validator.py`

split Manual IR 预检工具。

主要职责：

- 校验 split 输出目录结构。
- 校验 `manifest.json` 的 files/counts。
- 校验 parser artifacts 是否存在。
- 校验默认 audience：`newcomer`、`maintainer`、`reviewer`。
- 校验每个 `ReadingSection.covers` 是否能解析到对象。
- 汇总 object warnings、partial/low-confidence flow、external dependencies。

推荐在手册生成前作为 preflight 步骤。

#### `knowledge/manual_ir/context_pack.py`

面向写作片段的证据包构建器。

主要职责：

- 根据 `reading_path_id` 或 `audience` 选择 ReadingPath。
- 可选用 `section_id` 限定到一个章节。
- 解析章节 `covers` 中列出的 Manual IR 对象。
- 输出 `covered_objects`、`source_refs`、`warnings`、`unresolved_covers`。
- 明确写入 `evidence_boundary`，提醒下游不要越过 parser/Manual IR 事实做猜测。

这是 skill 写手册正文时最适合使用的上下文入口。

#### `knowledge/manual_ir/manual_context.py`

旧式/简化上下文构建器。

主要职责：

- 调用 `build_manual_ir()`。
- 生成 module summaries 和 component summaries。
- 为 agent 提供较扁平的 `ManualContext`。

如果 skill 已经使用 `pack`，通常不需要再走这个文件。

#### `knowledge/manual_ir/__init__.py`

包级导出文件。

主要导出：

- `build_manual_ir`
- `build_context_pack`
- `validate_manual_ir_split`
- `resolve_manual_ir_object`
- `resolve_manual_ir_objects`
- `build_object_catalog`
- Manual IR dataclass models

适合 Python 内嵌调用时使用。

## `tools/cc_header_tools/`

该目录不在 `knowledge/` 下，但与 parser pipeline 的 component header 扩展有关。如果你的 skill 需要维护 `//@cc:` header，可以把它作为辅助工具使用。

### `tools/cc_header_tools/cli.py`

命令行入口：

```bash
python -m tools.cc_header_tools lint --repo . --inputs <rtl_dir>
python -m tools.cc_header_tools scan --repo . --inputs <rtl_dir>
python -m tools.cc_header_tools skeleton --repo . --family SelSplit --file path/to/file.v --inplace
python -m tools.cc_header_tools strip --repo . --inputs <rtl_dir> --inplace
python -m tools.cc_header_tools autogen --repo . --inputs <rtl_dir> --only-missing --inplace
```

命令含义：

- `lint`：检查 `//@cc:` header 是否完整、family 是否合法、role ports 是否存在。
- `scan`：只输出存在 header 错误的文件路径。
- `skeleton`：从 `parser/families/cc_headers/<family>.txt` 插入 header 模板。
- `strip`：删除文件中的 `//@cc:` blocks。
- `autogen`：根据文件名、module 参数和端口自动生成 header。

### `tools/cc_header_tools/parser.py`

`//@cc:` header 与轻量 Verilog header 解析工具。

主要职责：

- 提取连续 `//@cc:` block。
- 解析轻量 YAML 子集。
- 解析 module header、参数和端口。
- 根据文件名推断 component family。

### `tools/cc_header_tools/lint.py`

header 校验器。

主要职责：

- 要求 `schema: cc_header_v1`。
- 校验 `family` 是否属于支持集合。
- 校验 role 中引用的端口是否存在于 module 端口。
- 对 `ArbMergeN`、`MutexMergeN` 做特定 contract 校验。
- 在 strict 模式下把 TODO 当作错误。

### `tools/cc_header_tools/autogen.py`

header 自动生成器。

主要职责：

- 根据文件名推断 family 和端口数量。
- 根据端口方向和命名生成 upstream/downstream/fire roles。
- 补充 `NUM_PORTS`、`DATA_WIDTH` 等 params。
- 可选择只给缺失 header 的文件生成，也可 force 覆盖已有 header。

## 推荐 Skill 工作流

### 1. 构建 parser artifacts

```bash
python -m parser.pipeline build \
  --inputs <rtl_project_dir> \
  --output artifacts/parser_pipeline_result
```

该步骤产出工程结构事实，是后续所有知识工具的 ground truth。

### 2. 导出 split Manual IR

```bash
python -m knowledge.manual_ir export \
  --artifacts-root artifacts/parser_pipeline_result \
  --top-module <top_module> \
  --output-dir artifacts/manual_ir/<top_module>
```

split 目录中主要文件：

- `manifest.json`
- `system_views.json`
- `module_cards/*.json`
- `channel_cards/*.json`
- `component_contracts/*.json`
- `flow_paths/*.json`
- `reading_paths/*.json`

### 3. 预检 Manual IR

```bash
python -m knowledge.manual_ir validate \
  --manual-ir-dir artifacts/manual_ir/<top_module> \
  --parser-artifacts-root artifacts/parser_pipeline_result
```

如果返回失败，不建议直接进入手册生成。应该先看 `issues` 和 `warning_summary`。

### 4. 为写作生成 ContextPack

```bash
python -m knowledge.manual_ir pack \
  --manual-ir-dir artifacts/manual_ir/<top_module> \
  --audience newcomer \
  --output artifacts/manual_ir/<top_module>/context_newcomer.json
```

如果只写一个章节，可以加：

```bash
--section-id <section_id>
```

### 5. 按对象取证据

```bash
python -m knowledge.manual_ir resolve \
  --manual-ir-dir artifacts/manual_ir/<top_module> \
  --object-id module:<module_name>
```

适合交互式问答或局部重写。

## 证据边界

这些脚本的输出是静态结构事实，不是完整 RTL 语义证明。

可以可靠使用的事实包括：

- module 名称、文件路径、参数、端口、reset。
- 实例化关系、连接关系、直接子模块、直接 component。
- component family、role mapping、family contract。
- 基于命名和连接的 event/free/payload/condition/reset 分类。
- parser 构建出的 module-local flow graph。
- Manual IR 中带 `source_refs` 的摘要、warnings 和 confidence。

不应直接从当前输出中推断的内容包括：

- `always` block 内的时序行为。
- FSM 状态转移。
- 寄存器更新条件。
- 组合逻辑表达式的完整语义。
- 未出现在 parser artifacts 或 Manual IR 中的跨模块协议细节。

如果手册生成需要这些内容，应该先扩展 parser 层的事实提取，再让 Manual IR 消费这些新事实。

## 选择哪个入口

- 工程级解析：使用 `python -m parser.pipeline build`。
- 单文件快速看 top/submodule：使用 `python -m parser.verilog parse`。
- 手册生成前的知识构建：使用 `python -m knowledge.manual_ir export --output-dir`。
- 手册写作上下文：使用 `python -m knowledge.manual_ir pack`。
- 精确读取一个 Manual IR 对象：使用 `python -m knowledge.manual_ir resolve`。
- 校验 split Manual IR：使用 `python -m knowledge.manual_ir validate`。
- 维护 `//@cc:` header：使用 `python -m tools.cc_header_tools ...`。
