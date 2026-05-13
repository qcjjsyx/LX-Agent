import os
import dotenv
import subprocess
import json
from openai import OpenAI

# ================= 配置部分 (换成 DeepSeek) =================
dotenv.load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
MODEL_NAME = "deepseek-chat"

# ================= 工具实现区 (Hands)  =================

def execute_bash(command):
    """工具 1: 执行 Bash"""
    print(f"\n🔧 [执行 Bash] {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return (result.stdout + result.stderr).strip() or "Done"
    except Exception as e:
        return f"Error: {str(e)}"

def read_file(filepath):
    """工具 2: 读取文件 (S02 新增)"""
    print(f"\n📖 [读取文件] {filepath}")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取失败: {str(e)}"
    
def write_file(filepath, content):
    """工具 3：写入文件"""
    print(f"\n✍️ [写入文件] {filepath}")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功写入文件：{filepath}"
    except Exception as e:
        return f"写入失败：{str(e)}"

# ================= S02 核心: 调度映射表 (Dispatch Map) (完全没变!) =================
# 口诀: 添加一个工具意味着添加一个 handler

TOOL_HANDLERS = {
    "run_bash": execute_bash,
    "read_file": read_file,  # S02 新增 
    "write_file": write_file  #自加
}

# 给模型看的说明书 (格式微调，适应 OpenAI/DeepSeek)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "执行 shell 命令",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文件内容",
            "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入本地文件内容",
            "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}
        }
    }
]

# ================= 核心循环 (只是换了 API 调用方式，逻辑没变) =================
def main():
    print("=== S02: 添加工具只需添加一个 Handler (国内网络版) ===")
    print("提示：先让我创建文件，再让我读取文件，或者直接读取刚才的 test.txt")
    user_query = input("你想让我做什么? ")
    
    messages = [{"role": "user", "content": user_query}]

    while True:
        # 1. 调用模型
        print("\n🤔 模型思考中...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        choice = response.choices[0]
        
        # 2. 记录回复
        messages.append(choice.message)

        # 3. 打印文本
        if choice.message.content:
            print(f"\n💬 模型说: {choice.message.content}")

        # 4. 检查停止条件 (如果没有 tool_calls 就结束)
        if not choice.message.tool_calls:
            print("\n✅ 任务结束。")
            break

        # 5. S02 改进: 通用工具执行器 (完全没变!)
        for tool_call in choice.message.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            # 核心：从映射表里直接取函数，不需要 if-else
            print(f"📦 [S02 调度] 正在调用映射表中的: {func_name}")
            handler_func = TOOL_HANDLERS[func_name]
            result_data = handler_func(**args)
            
            # 把结果发回给模型
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": result_data
            })

if __name__ == "__main__":
    main()