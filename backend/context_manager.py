# context_manager.py

# ====================== 上下文压缩配置 ======================

MAX_CONTEXT_CHARS = 6000       # 超过多少字符就压缩
KEEP_RECENT_MESSAGES = 6       # 保留最近几条消息不压缩


def message_to_dict(message):
    """
    把 OpenAI SDK 返回的 message 对象转换成普通 dict。
    因为模型返回的 msg 有时候不是字典，而是对象。
    """
    if isinstance(message, dict):
        return message

    if hasattr(message, "model_dump"):
        return message.model_dump()

    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", "")
    }


def estimate_messages_size(messages):
    """
    粗略估算上下文长度。
    """
    total = 0

    for msg in messages:
        msg = message_to_dict(msg)
        total += len(str(msg))

    return total


def messages_to_text(messages):
    """
    把 messages 转成普通文本，方便交给模型总结。
    """
    lines = []

    for msg in messages:
        msg = message_to_dict(msg)

        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            content += f"\n[工具调用]: {tool_calls}"

        lines.append(f"{role}: {content}")

    return "\n\n".join(lines)


def compress_context(client, model, messages):
    """
    压缩旧上下文：
    1. 旧消息交给模型总结
    2. 最近几条消息原样保留
    3. 返回新的 messages
    """
    if len(messages) <= KEEP_RECENT_MESSAGES:
        return messages

    old_messages = messages[:-KEEP_RECENT_MESSAGES]
    recent_messages = messages[-KEEP_RECENT_MESSAGES:]

    old_text = messages_to_text(old_messages)

    print("\n🧠 上下文过长，正在压缩旧上下文...")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个上下文压缩器。"
                    "请把用户、助手、工具调用和工具返回结果总结成一份简洁但信息完整的摘要。"
                    "必须保留：用户目标、已经完成的步骤、重要文件名、关键结论、工具执行结果、未完成事项。"
                    "不要编造信息。"
                )
            },
            {
                "role": "user",
                "content": old_text
            }
        ]
    )

    summary = response.choices[0].message.content

    compressed_messages = [
        {
            "role": "system",
            "content": (
                "以下是之前对话和工具执行结果的压缩摘要。"
                "后续回答必须基于这个摘要继续，不要忘记其中的重要事实。\n\n"
                + summary
            )
        }
    ]

    compressed_messages.extend(recent_messages)

    print("✅ 上下文压缩完成。")

    return compressed_messages


def maybe_compress_context(client, model, messages):
    """
    对外暴露的主函数。
    agent_core.py 只需要调用这个函数即可。
    """
    size = estimate_messages_size(messages)

    if size > MAX_CONTEXT_CHARS:
        return compress_context(client, model, messages)

    return messages