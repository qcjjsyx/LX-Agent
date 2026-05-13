# agent_core.py
import os
import json
import dotenv
from openai import OpenAI

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


def call_model(messages, active_tools):
    """
    调用模型。
    如果本轮有可用工具，就把 tools 传给模型。
    如果没有工具，就让模型直接普通回答。
    """
    params = {
        "model": MODEL,
        "messages": messages
    }

    if active_tools:
        params["tools"] = active_tools
        params["tool_choice"] = "auto"

    return client.chat.completions.create(**params)


def start_agent():
    print("\n【AI Agent 已启动】")
    user_input = input("\n请输入你的任务：")

    # 关键：根据用户输入选择本轮可用工具和 skill
    active_tools, active_handlers, active_skill_names = select_tools_for_task(user_input)

    if active_skill_names:
        print(f"\n🧩 本轮激活 Skill：{', '.join(active_skill_names)}")
    else:
        print("\n🧩 本轮未激活任何 Skill，只使用基础工具或直接回答。")

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个本地 AI Agent。"
                "你可以根据用户任务调用本轮激活的工具。"
                "如果没有合适工具，就直接用文字回答。"
                "回答要清晰，适合新手理解。"
            )
        },
        {
            "role": "user",
            "content": user_input
        }
    ]

    while True:
        messages = maybe_compress_context(client, MODEL, messages)

        print("\n🤔 思考中...")

        response = call_model(messages, active_tools)

        msg = response.choices[0].message
        messages.append(msg)

        if msg.content:
            print(f"\n💬 助手：{msg.content}")

        if not msg.tool_calls:
            print("\n✅ 任务完成！")
            break

        for tool in msg.tool_calls:
            name = tool.function.name
            args = json.loads(tool.function.arguments)

            print(f"⚙️ 调用工具：{name}")

            if name not in active_handlers:
                result = f"工具调用失败：当前任务没有激活 {name} 这个工具。"
            else:
                result = active_handlers[name](**args)

            messages.append({
                "tool_call_id": tool.id,
                "role": "tool",
                "content": result
            })
