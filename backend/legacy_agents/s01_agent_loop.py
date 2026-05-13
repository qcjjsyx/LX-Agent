import os
import dotenv
import subprocess
from openai import OpenAI # 注意：这里用 openai 库，因为 DeepSeek 兼容 OpenAI 格式

# ================= 配置部分 =================
dotenv.load_dotenv()

# 使用 OpenAI 客户端指向 DeepSeek 地址
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
MODEL_NAME = "deepseek-chat"

# ================= 工具定义 =================
TOOLS = [
    {
        "type": "function", # OpenAI/DeepSeek 格式这里要加 type
        "function": {
            "name": "run_bash",
            "description": "在终端中执行 shell 命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"}
                },
                "required": ["command"]
            }
        }
    }
]

# ================= 工具实现 =================
def execute_bash(command):
    print(f"\n🔧 [执行 Bash] {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return (result.stdout + result.stderr).strip() or "执行成功"
    except Exception as e:
        return f"出错: {str(e)}"

TOOL_HANDLERS = {
    "run_bash": execute_bash
}

# ================= 核心循环 (逻辑完全一样，只是 API 调用参数微变) =================
def main():
    print("=== S01: 国内网络版 (使用 DeepSeek) ===")
    user_query = input("你想让我做什么? ")
    
    messages = [{"role": "user", "content": user_query}]

    while True:
        print("\n🤔 模型思考中...")
        # 这里调用变成了 client.chat.completions.create
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        choice = response.choices[0]
        messages.append(choice.message) # 把模型回复加入历史

        # 打印文本
        if choice.message.content:
            print(f"\n💬 模型说: {choice.message.content}")

        # 检查是否要调用工具
        if not choice.message.tool_calls:
            print("\n✅ 任务结束。")
            break

        # 执行工具
        tool_results = []
        for tool_call in choice.message.tool_calls:
            func_name = tool_call.function.name
            import json
            args = json.loads(tool_call.function.arguments)
            
            handler = TOOL_HANDLERS[func_name]
            result = handler(**args)
            
            # DeepSeek/OpenAI 需要把结果拼回去
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": result
            })

if __name__ == "__main__":
    main()