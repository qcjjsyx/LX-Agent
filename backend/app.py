# backend/app.py
import os
import json
import uuid
import zipfile
import shutil
from pathlib import Path
from datetime import datetime

import dotenv
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from werkzeug.utils import secure_filename

try:
    from .tools import select_tools_for_task
    from .context_manager import maybe_compress_context
except ImportError:
    from tools import select_tools_for_task
    from context_manager import maybe_compress_context

dotenv.load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

MODEL = "deepseek-chat"

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR / "templates"),
    static_folder=str(FRONTEND_DIR / "static")
)


# ====================== 文件上传 / 路径导入配置 ======================

IMPORT_DIR = DATA_DIR / "imports"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_DIR = IMPORT_DIR / "_archives"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# 浏览器上传最大 100MB
# 大文件建议使用“路径导入”，不走浏览器上传
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".html",
    ".css",
    ".js",
    ".v",
    ".sv",
    ".vh",
    ".log",
    ".csv",
    ".zip"
}

ALLOWED_EXTRACT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".html",
    ".css",
    ".js",
    ".v",
    ".sv",
    ".vh",
    ".log",
    ".csv"
}

MAX_ZIP_FILES = 2000
MAX_ZIP_TOTAL_SIZE = 500 * 1024 * 1024


# ====================== 聊天记录配置 ======================

CONVERSATION_DIR = DATA_DIR / "conversations"
CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "你是一个网页版 AI Agent。"
        "你可以根据用户任务调用本轮激活的工具。"
        "如果本轮已经激活了某个 skill，并且用户的问题明显可以由该 skill 的 tool 完成，必须优先调用 tool。"
        "如果没有合适工具，就直接用文字回答。"
        "回答要清晰，适合新手理解。"
    )
}

current_conversation_id = None
messages = [SYSTEM_MESSAGE]


# ====================== 基础函数 ======================

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_conversation_id():
    return "chat_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def conversation_path(conversation_id):
    return CONVERSATION_DIR / f"{conversation_id}.json"


def message_to_dict(message):
    if isinstance(message, dict):
        return message

    if hasattr(message, "model_dump"):
        return message.model_dump()

    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", "")
    }


def sanitize_messages_for_api(raw_messages):
    """
    清洗 messages，避免出现孤立 tool 消息导致 400 错误。
    """
    clean_messages = []
    pending_tool_call_ids = set()

    for raw_msg in raw_messages:
        msg = message_to_dict(raw_msg)
        role = msg.get("role")

        if role in ["system", "user"]:
            clean_messages.append(msg)
            pending_tool_call_ids = set()
            continue

        if role == "assistant":
            clean_messages.append(msg)
            pending_tool_call_ids = set()

            tool_calls = msg.get("tool_calls") or []

            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_call_id = tool_call.get("id")
                else:
                    tool_call_id = getattr(tool_call, "id", None)

                if tool_call_id:
                    pending_tool_call_ids.add(tool_call_id)

            continue

        if role == "tool":
            tool_call_id = msg.get("tool_call_id")

            if tool_call_id in pending_tool_call_ids:
                clean_messages.append(msg)
                pending_tool_call_ids.remove(tool_call_id)
            else:
                print(f"⚠️ 跳过孤立 tool 消息：{tool_call_id}")

            continue

    return clean_messages


def visible_messages_only(raw_messages):
    result = []

    for msg in raw_messages:
        msg = message_to_dict(msg)

        role = msg.get("role")
        content = msg.get("content") or ""

        if role in ["user", "assistant"] and content.strip():
            result.append({
                "role": role,
                "content": content
            })

    return result


def get_title_from_messages(raw_messages):
    for msg in raw_messages:
        msg = message_to_dict(msg)

        if msg.get("role") == "user":
            text = msg.get("content", "").strip()

            if text:
                return text[:24] + ("..." if len(text) > 24 else "")

    return "新对话"


def create_new_conversation():
    global current_conversation_id, messages

    current_conversation_id = make_conversation_id()
    messages = [SYSTEM_MESSAGE]

    save_current_conversation()

    return current_conversation_id


def save_current_conversation():
    global current_conversation_id, messages

    if current_conversation_id is None:
        create_new_conversation()
        return

    path = conversation_path(current_conversation_id)

    created_at = now_text()
    title = get_title_from_messages(messages)
    manual_title = False

    if path.exists():
        try:
            old_data = json.loads(path.read_text(encoding="utf-8"))
            created_at = old_data.get("created_at", created_at)

            if old_data.get("manual_title"):
                title = old_data.get("title", title)
                manual_title = True

        except Exception:
            pass

    safe_messages = sanitize_messages_for_api(messages)

    data = {
        "id": current_conversation_id,
        "title": title,
        "manual_title": manual_title,
        "created_at": created_at,
        "updated_at": now_text(),
        "messages": [message_to_dict(m) for m in safe_messages]
    }

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_conversation(conversation_id):
    global current_conversation_id, messages

    path = conversation_path(conversation_id)

    if not path.exists():
        return False

    data = json.loads(path.read_text(encoding="utf-8"))

    current_conversation_id = conversation_id
    loaded_messages = data.get("messages", [])

    if not loaded_messages:
        messages = [SYSTEM_MESSAGE]
    else:
        messages = sanitize_messages_for_api(loaded_messages)

        if not messages or messages[0].get("role") != "system":
            messages.insert(0, SYSTEM_MESSAGE)

    return True


def list_conversations():
    items = []

    for path in CONVERSATION_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            items.append({
                "id": data.get("id", path.stem),
                "title": data.get("title", "未命名对话"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })

        except Exception:
            continue

    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    return items


# ====================== 上传 / 解压辅助函数 ======================

def is_allowed_upload(filename):
    suffix = Path(filename).suffix.lower()
    return suffix in ALLOWED_UPLOAD_EXTENSIONS


def is_allowed_extract_file(filename):
    suffix = Path(filename).suffix.lower()
    return suffix in ALLOWED_EXTRACT_EXTENSIONS


def make_safe_upload_name(original_filename):
    suffix = Path(original_filename).suffix.lower()
    stem = Path(original_filename).stem

    safe_stem = secure_filename(stem)

    if not safe_stem:
        safe_stem = "uploaded_file"

    unique_id = uuid.uuid4().hex[:8]

    return f"{safe_stem}_{unique_id}{suffix}"


def make_safe_folder_name(original_filename):
    stem = Path(original_filename).stem
    safe_stem = secure_filename(stem)

    if not safe_stem:
        safe_stem = "uploaded_folder"

    unique_id = uuid.uuid4().hex[:8]

    return f"{safe_stem}_{unique_id}"


def safe_join(base_dir, relative_path):
    """
    安全拼接路径，防止 zip slip。
    """
    base_dir = Path(base_dir).resolve()
    target_path = (base_dir / relative_path).resolve()

    if not str(target_path).startswith(str(base_dir)):
        raise ValueError("检测到危险路径，已阻止解压。")

    return target_path


def sanitize_zip_member_path(member_name):
    """
    清洗 zip 内部路径。
    """
    parts = []

    for part in Path(member_name).parts:
        if part in ["", ".", ".."]:
            continue

        safe_part = secure_filename(part)

        if safe_part:
            parts.append(safe_part)

    if not parts:
        return None

    return Path(*parts)


def extract_zip_safely(zip_path, extract_dir):
    """
    安全解压 zip 文件。
    """
    extracted_files = []
    skipped_files = []

    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    if not zipfile.is_zipfile(zip_path):
        return {
            "ok": False,
            "error": "这不是有效的 zip 文件。",
            "extracted_files": [],
            "skipped_files": []
        }

    total_size = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = zip_ref.infolist()

            if len(members) > MAX_ZIP_FILES:
                return {
                    "ok": False,
                    "error": f"zip 内文件数量过多，最多允许 {MAX_ZIP_FILES} 个文件。",
                    "extracted_files": [],
                    "skipped_files": []
                }

            for member in members:
                if member.is_dir():
                    continue

                original_name = member.filename

                if original_name.startswith("__MACOSX/"):
                    skipped_files.append({
                        "filename": original_name,
                        "reason": "系统隐藏文件，已跳过"
                    })
                    continue

                total_size += member.file_size

                if total_size > MAX_ZIP_TOTAL_SIZE:
                    return {
                        "ok": False,
                        "error": "zip 解压后文件总大小超过限制。",
                        "extracted_files": extracted_files,
                        "skipped_files": skipped_files
                    }

                if not is_allowed_extract_file(original_name):
                    skipped_files.append({
                        "filename": original_name,
                        "reason": "zip 内文件类型不支持，已跳过"
                    })
                    continue

                safe_relative_path = sanitize_zip_member_path(original_name)

                if safe_relative_path is None:
                    skipped_files.append({
                        "filename": original_name,
                        "reason": "文件名无效，已跳过"
                    })
                    continue

                try:
                    target_path = safe_join(extract_dir, safe_relative_path)
                except Exception as e:
                    skipped_files.append({
                        "filename": original_name,
                        "reason": str(e)
                    })
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)

                with zip_ref.open(member, "r") as source:
                    with open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                extracted_files.append({
                    "original_name": original_name,
                    "saved_path": str(target_path).replace("\\", "/")
                })

        return {
            "ok": True,
            "error": "",
            "extracted_files": extracted_files,
            "skipped_files": skipped_files
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"zip 解压失败：{str(e)}",
            "extracted_files": extracted_files,
            "skipped_files": skipped_files
        }


def copy_file_to_imports(source_path):
    """
    通过路径导入普通文件。
    """
    safe_name = make_safe_upload_name(source_path.name)
    target_path = IMPORT_DIR / safe_name

    with open(source_path, "rb") as src:
        with open(target_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

    return target_path


# ====================== 模型调用 ======================

def call_model(active_messages, active_tools):
    safe_messages = sanitize_messages_for_api(active_messages)

    params = {
        "model": MODEL,
        "messages": safe_messages
    }

    if active_tools:
        params["tools"] = active_tools
        params["tool_choice"] = "auto"

    return client.chat.completions.create(**params)


def build_debug_tip(active_skill_names, used_tools):
    lines = []

    if active_skill_names:
        lines.append(f"【已激活 Skill：{', '.join(active_skill_names)}】")
    else:
        lines.append("【未激活 Skill】")

    if used_tools:
        lines.append(f"【已使用 Tool：{', '.join(used_tools)}】")
    else:
        lines.append("【未使用 Tool：模型直接回答】")

    return "\n".join(lines)


def build_skill_context(active_skill_instructions, active_reference_files):
    if not active_skill_instructions and not active_reference_files:
        return None

    parts = []

    if active_skill_instructions:
        parts.extend(active_skill_instructions)

    if active_reference_files:
        reference_text = "本轮触发的 skill 需要优先读取以下 reference 文件：\n"

        for path in active_reference_files:
            reference_text += f"- {path}\n"

        reference_text += (
            "\n请先使用 read_file 逐个读取这些 reference 文件。"
            "如果文件不存在，请说明缺失并继续读取其他 reference。"
            "读取完成后，再根据这些文档理解 parser tool 和 knowledge tool 的职责。"
        )

        parts.append(reference_text)

    return "\n\n".join(parts)


# ====================== Agent 单轮执行 ======================

def run_agent_once(user_input):
    global messages

    if not user_input.strip():
        return "请输入内容。"

    if current_conversation_id is None:
        create_new_conversation()

    (
        active_tools,
        active_handlers,
        active_skill_names,
        active_skill_instructions,
        active_reference_files
    ) = select_tools_for_task(user_input)

    used_tools = []

    print("\n🧩 Reference Skill Selector")

    if active_skill_names:
        print(f"本轮激活 Skill：{', '.join(active_skill_names)}")
    else:
        print("本轮未激活 Skill")

    messages.append({
        "role": "user",
        "content": user_input
    })

    skill_context = build_skill_context(
        active_skill_instructions,
        active_reference_files
    )

    if skill_context:
        messages.append({
            "role": "system",
            "content": skill_context
        })

    while True:
        messages = sanitize_messages_for_api(messages)
        messages = maybe_compress_context(client, MODEL, messages)
        messages = sanitize_messages_for_api(messages)

        response = call_model(messages, active_tools)

        msg = response.choices[0].message
        msg_dict = message_to_dict(msg)

        messages.append(msg_dict)

        if msg.content:
            print(f"\n💬 助手：{msg.content}")

        if not msg.tool_calls:
            reply = msg.content or ""

            final_reply = build_debug_tip(active_skill_names, used_tools) + "\n\n" + reply

            messages[-1] = {
                "role": "assistant",
                "content": final_reply
            }

            save_current_conversation()

            return final_reply

        for tool_call in msg.tool_calls:
            name = tool_call.function.name

            try:
                args = json.loads(tool_call.function.arguments)
            except Exception as e:
                result = f"工具参数解析失败：{str(e)}"

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": result
                })

                continue

            print(f"⚙️ 网页版调用工具：{name}")

            if name not in active_handlers:
                result = f"工具调用失败：当前任务没有激活 {name} 这个工具。"
            else:
                try:
                    used_tools.append(name)
                    result = active_handlers[name](**args)
                except Exception as e:
                    result = f"工具执行失败：{str(e)}"

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": result
            })


# ====================== Flask 路由 ======================

@app.route("/")
def index():
    global current_conversation_id

    if current_conversation_id is None:
        create_new_conversation()

    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message", "")

    try:
        reply = run_agent_once(user_input)

        return jsonify({
            "reply": reply,
            "conversation_id": current_conversation_id,
            "conversations": list_conversations()
        })

    except Exception as e:
        return jsonify({
            "reply": f"出错了：{str(e)}"
        })


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    浏览器上传文件。
    小文件用这个。
    大文件建议用 /import_path。
    """
    if "files" not in request.files:
        return jsonify({
            "error": "没有收到文件。"
        }), 400

    files = request.files.getlist("files")

    if not files:
        return jsonify({
            "error": "没有选择文件。"
        }), 400

    saved_files = []
    extracted_zip_files = []
    rejected_files = []

    for file in files:
        original_name = file.filename

        if not original_name:
            continue

        if not is_allowed_upload(original_name):
            rejected_files.append({
                "filename": original_name,
                "reason": "不支持的文件类型"
            })
            continue

        suffix = Path(original_name).suffix.lower()

        if suffix != ".zip":
            safe_name = make_safe_upload_name(original_name)
            save_path = IMPORT_DIR / safe_name

            try:
                file.save(save_path)

                saved_files.append({
                    "original_name": original_name,
                    "saved_name": safe_name,
                    "saved_path": str(save_path).replace("\\", "/"),
                    "type": "file"
                })

            except Exception as e:
                rejected_files.append({
                    "filename": original_name,
                    "reason": str(e)
                })

            continue

        safe_zip_name = make_safe_upload_name(original_name)
        zip_save_path = ARCHIVE_DIR / safe_zip_name

        try:
            file.save(zip_save_path)

            extract_folder_name = make_safe_folder_name(original_name)
            extract_dir = IMPORT_DIR / extract_folder_name

            result = extract_zip_safely(zip_save_path, extract_dir)

            if not result["ok"]:
                rejected_files.append({
                    "filename": original_name,
                    "reason": result["error"]
                })
                continue

            saved_files.append({
                "original_name": original_name,
                "saved_name": safe_zip_name,
                "saved_path": str(zip_save_path).replace("\\", "/"),
                "extract_dir": str(extract_dir).replace("\\", "/"),
                "type": "zip"
            })

            extracted_zip_files.append({
                "zip_name": original_name,
                "extract_dir": str(extract_dir).replace("\\", "/"),
                "files": result["extracted_files"],
                "skipped_files": result["skipped_files"]
            })

        except Exception as e:
            rejected_files.append({
                "filename": original_name,
                "reason": str(e)
            })

    if not saved_files and not extracted_zip_files and rejected_files:
        return jsonify({
            "error": "文件上传失败。",
            "rejected_files": rejected_files
        }), 400

    return jsonify({
        "message": "文件上传完成。",
        "files": saved_files,
        "extracted_zip_files": extracted_zip_files,
        "rejected_files": rejected_files
    })


@app.route("/import_path", methods=["POST"])
def import_path():
    """
    通过本机路径导入文件、zip 或文件夹。

    适合大文件：
    - 不经过浏览器上传
    - 由 Flask 后端直接读取本机路径

    支持：
    - 文件夹：直接返回路径，不复制
    - 普通文件：复制到 data/imports/
    - zip：复制到 data/imports/_archives/ 并解压到 data/imports/<zip_name_xxxxxxxx>/
    """
    data = request.get_json()
    source_path_text = data.get("path", "").strip()

    if not source_path_text:
        return jsonify({
            "error": "请输入本机文件、zip 或文件夹路径。"
        }), 400

    source_path = Path(source_path_text)

    if not source_path.exists():
        return jsonify({
            "error": f"路径不存在：{source_path_text}"
        }), 400

    # 1. 文件夹：不复制，直接返回原路径
    if source_path.is_dir():
        return jsonify({
            "message": "文件夹路径已导入。",
            "type": "folder",
            "source_path": str(source_path.resolve()).replace("\\", "/"),
            "tip": "这是一个文件夹，不需要复制。Agent 可以直接读取或解析这个目录。"
        })

    if not source_path.is_file():
        return jsonify({
            "error": f"该路径不是有效文件或文件夹：{source_path_text}"
        }), 400

    suffix = source_path.suffix.lower()

    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({
            "error": f"不支持的文件类型：{suffix}"
        }), 400

    # 2. 普通文件
    if suffix != ".zip":
        try:
            target_path = copy_file_to_imports(source_path)

            return jsonify({
                "message": "文件已通过路径导入。",
                "type": "file",
                "original_path": str(source_path.resolve()).replace("\\", "/"),
                "saved_path": str(target_path).replace("\\", "/")
            })

        except Exception as e:
            return jsonify({
                "error": f"文件导入失败：{str(e)}"
            }), 500

    # 3. zip 文件
    safe_zip_name = make_safe_upload_name(source_path.name)
    zip_save_path = ARCHIVE_DIR / safe_zip_name

    try:
        with open(source_path, "rb") as src:
            with open(zip_save_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        extract_folder_name = make_safe_folder_name(source_path.name)
        extract_dir = IMPORT_DIR / extract_folder_name

        result = extract_zip_safely(zip_save_path, extract_dir)

        if not result["ok"]:
            return jsonify({
                "error": result["error"]
            }), 400

        return jsonify({
            "message": "zip 已通过路径导入并解压。",
            "type": "zip",
            "original_path": str(source_path.resolve()).replace("\\", "/"),
            "saved_zip": str(zip_save_path).replace("\\", "/"),
            "extract_dir": str(extract_dir).replace("\\", "/"),
            "files": result["extracted_files"],
            "skipped_files": result["skipped_files"]
        })

    except Exception as e:
        return jsonify({
            "error": f"zip 路径导入失败：{str(e)}"
        }), 500


@app.route("/conversations", methods=["GET"])
def get_conversations():
    return jsonify({
        "current_id": current_conversation_id,
        "conversations": list_conversations()
    })


@app.route("/conversation/<conversation_id>", methods=["GET"])
def get_conversation(conversation_id):
    ok = load_conversation(conversation_id)

    if not ok:
        return jsonify({
            "error": "聊天记录不存在"
        }), 404

    return jsonify({
        "conversation_id": current_conversation_id,
        "messages": visible_messages_only(messages),
        "conversations": list_conversations()
    })


@app.route("/conversation/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    global current_conversation_id, messages

    path = conversation_path(conversation_id)

    if not path.exists():
        return jsonify({
            "error": "聊天记录不存在"
        }), 404

    try:
        path.unlink()

        if current_conversation_id == conversation_id:
            create_new_conversation()

        return jsonify({
            "message": "聊天记录已删除。",
            "current_id": current_conversation_id,
            "messages": visible_messages_only(messages),
            "conversations": list_conversations()
        })

    except Exception as e:
        return jsonify({
            "error": f"删除失败：{str(e)}"
        }), 500


@app.route("/conversation/<conversation_id>/rename", methods=["POST"])
def rename_conversation(conversation_id):
    data = request.get_json()
    new_title = data.get("title", "").strip()

    if not new_title:
        return jsonify({
            "error": "标题不能为空"
        }), 400

    path = conversation_path(conversation_id)

    if not path.exists():
        return jsonify({
            "error": "聊天记录不存在"
        }), 404

    try:
        conversation_data = json.loads(path.read_text(encoding="utf-8"))

        conversation_data["title"] = new_title
        conversation_data["manual_title"] = True
        conversation_data["updated_at"] = now_text()

        path.write_text(
            json.dumps(conversation_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return jsonify({
            "message": "标题已重命名。",
            "conversations": list_conversations()
        })

    except Exception as e:
        return jsonify({
            "error": f"重命名失败：{str(e)}"
        }), 500


@app.route("/new_chat", methods=["POST"])
def new_chat():
    conversation_id = create_new_conversation()

    return jsonify({
        "conversation_id": conversation_id,
        "messages": visible_messages_only(messages),
        "conversations": list_conversations()
    })


@app.route("/reset", methods=["POST"])
def reset():
    global messages

    messages = [SYSTEM_MESSAGE]
    save_current_conversation()

    return jsonify({
        "message": "当前聊天已清空。",
        "messages": visible_messages_only(messages),
        "conversations": list_conversations()
    })


if __name__ == "__main__":
    app.run(debug=True)
