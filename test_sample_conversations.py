"""
测试 sample 目录下的对话记录：解析 → 构建多模态 prompt → 调用 LLM summary → 记录 prompt
"""

import os
import re
import json
import sys
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from conversation_summarizer.summarizer import Summarizer

# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────

@dataclass
class Attachment:
    local_path: str
    url: str
    file_size: int
    file_type: str  # image / document

@dataclass
class Message:
    role: str          # user / assistant
    content: str       # 纯文本内容（不含 ### 相关文件）
    turn_index: int    # 第几轮

@dataclass
class ParsedConversation:
    req_id: str
    session_id: str
    time: str
    folder: str
    messages: List[Message] = field(default_factory=list)
    attachments: List[Attachment] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 解析器
# ─────────────────────────────────────────────────────────────

def parse_conversation(md_path: str) -> ParsedConversation:
    """解析 conversation.md，正确分离消息内容和附件元数据"""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1) 元信息
    req_id = _extract(content, r'\*\*Req ID\*\*:\s*`([^`]+)`')
    session_id = _extract(content, r'\*\*Session ID\*\*:\s*`([^`]+)`')
    time_str = _extract(content, r'\*\*时间\*\*:\s*(.+)')
    folder = _extract(content, r'\*\*对话文件夹\*\*:\s*`([^`]+)`')

    # 2) 提取附件（全局）
    attachments = _extract_attachments(content)

    # 3) 提取消息
    messages = _extract_messages(content)

    return ParsedConversation(
        req_id=req_id,
        session_id=session_id,
        time=time_str,
        folder=folder,
        messages=messages,
        attachments=attachments,
    )


def _extract(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def _extract_attachments(content: str) -> List[Attachment]:
    """提取所有附件信息"""
    results = []
    pattern = (
        r'- \*\*本地路径\*\*:\s*`([^`]+)`\s*\n'
        r'\s*- 原始 URL:\s*(\S+)\s*\n'
        r'\s*- 文件大小:\s*(\d+)\s*字节'
    )
    seen_paths = set()
    for m in re.finditer(pattern, content):
        local_path = m.group(1)
        if local_path in seen_paths:
            continue
        seen_paths.add(local_path)

        url = m.group(2)
        file_size = int(m.group(3))
        is_image = any(local_path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"))
        results.append(Attachment(
            local_path=local_path,
            url=url,
            file_size=file_size,
            file_type="image" if is_image else "document",
        ))
    return results


def _extract_messages(content: str) -> List[Message]:
    """提取对话消息，将 ### 相关文件 部分从消息内容中剥离"""
    messages: List[Message] = []

    # 找到 ### 对话内容 之后的部分
    conversation_start = content.find("### 对话内容")
    if conversation_start == -1:
        return messages
    conversation_body = content[conversation_start:]

    # 按 --- 分割成块
    blocks = re.split(r'\n---\n', conversation_body)

    turn_index = 0
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # 匹配用户消息
        user_match = re.search(r'\*\*👤\s*用户\*\*\s*\(full\):\s*\n(.*)', block, re.DOTALL)
        if user_match:
            raw_content = user_match.group(1).strip()
            clean_content = _strip_attachments_section(raw_content)
            messages.append(Message(role="user", content=clean_content, turn_index=turn_index))
            turn_index += 1
            continue

        # 匹配助手消息
        assistant_match = re.search(r'\*\*🤖\s*助手\*\*\s*\(full\):\s*\n(.*)', block, re.DOTALL)
        if assistant_match:
            raw_content = assistant_match.group(1).strip()
            clean_content = _strip_attachments_section(raw_content)
            messages.append(Message(role="assistant", content=clean_content, turn_index=turn_index))
            turn_index += 1
            continue

    return messages


def _strip_attachments_section(text: str) -> str:
    """从消息文本中移除 ### 相关文件 及其后续内容"""
    idx = text.find("### 相关文件")
    if idx != -1:
        return text[:idx].strip()
    return text.strip()


# ─────────────────────────────────────────────────────────────
# Summary Prompt 构建
# ─────────────────────────────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = """你是一个对话摘要助手。请根据以下多轮对话内容，生成一段简洁的对话摘要。

摘要要求：
1. 用 2-4 句话概括整段对话的核心内容
2. 包含用户的主要需求和助手的关键响应
3. 如果涉及文件操作（如图片识别、表格生成、格式转换等），请明确提及
4. 如果有图片附件，请说明图片在对话中的作用

请直接输出摘要文本，不要输出 JSON 或其他格式。"""


def build_summary_prompt(
    parsed: ParsedConversation,
    sample_dir: str,
) -> Tuple[List[Dict], int]:
    """
    构建用于 summary 的多模态 prompt。

    结构：
      [0] system  -> 摘要指令
      [1] user    -> 对话历史文本 + 图片附件（如果有本地图片）
    """
    # ── 对话历史文本 ──
    history_lines = []
    for msg in parsed.messages:
        role_label = "用户" if msg.role == "user" else "助手"
        text = msg.content
        if len(text) > 600:
            text = text[:600] + "…（已截断）"
        history_lines.append(f"【{role_label}】{text}")

    conversation_text = "\n\n".join(history_lines)

    # ── 附件描述 ──
    if parsed.attachments:
        attachment_desc_lines = ["\n\n【附件列表】"]
        for att in parsed.attachments:
            kind = "图片" if att.file_type == "image" else "文档"
            fname = Path(att.local_path).name
            attachment_desc_lines.append(f"- [{kind}] {fname} ({att.file_size} 字节)")
        conversation_text += "\n".join(attachment_desc_lines)

    # ── 构建 prompt ──
    prompt: List[Dict] = []

    # system
    prompt.append({
        "role": "system",
        "content": SUMMARY_SYSTEM_PROMPT,
    })

    # user: 对话历史 + 图片
    user_content: List[Dict] = [
        {"type": "text", "text": f"以下是需要摘要的对话内容：\n\n{conversation_text}"}
    ]

    # 尝试加载本地图片（最多 3 张）
    image_attachments = [a for a in parsed.attachments if a.file_type == "image" and a.file_size > 0]
    loaded_image_count = 0
    for att in image_attachments[:3]:
        img_path = Path(sample_dir) / Path(att.local_path).name
        if not img_path.exists():
            img_path = Path(sample_dir).parent / att.local_path
        if img_path.exists() and img_path.stat().st_size > 0:
            try:
                with open(img_path, "rb") as f:
                    img_bytes = f.read()
                ext = img_path.suffix.lower().replace(".", "")
                if ext == "jpg":
                    ext = "jpeg"
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{ext};base64,{b64}"}
                })
                loaded_image_count += 1
            except Exception:
                pass

    prompt.append({"role": "user", "content": user_content})

    return prompt, loaded_image_count


# ─────────────────────────────────────────────────────────────
# 主测试流程
# ─────────────────────────────────────────────────────────────

def _sanitize_prompt_for_log(prompt: List[Dict]) -> List[Dict]:
    """去掉 base64 图片数据，只保留前缀标记"""
    sanitized = []
    for msg in prompt:
        new_msg = {"role": msg["role"]}
        if isinstance(msg["content"], str):
            new_msg["content"] = msg["content"]
        elif isinstance(msg["content"], list):
            new_items = []
            for item in msg["content"]:
                if item["type"] == "text":
                    new_items.append(item)
                elif item["type"] == "image_url":
                    url = item["image_url"]["url"]
                    if url.startswith("data:"):
                        new_items.append({
                            "type": "image_url",
                            "image_url": {"url": url[:40] + "...[base64 truncated]"}
                        })
                    else:
                        new_items.append(item)
            new_msg["content"] = new_items
        sanitized.append(new_msg)
    return sanitized


def run_test():
    sample_root = Path(__file__).parent.parent / "sample"
    conversation_dirs = sorted([d for d in sample_root.iterdir() if d.is_dir()])

    print("=" * 70)
    print(f"找到 {len(conversation_dirs)} 个对话记录")
    print("=" * 70)

    summarizer = Summarizer(
        api_key=os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d"),
        api_base=os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat"),
        model=os.getenv("LLM_MODEL", "gpt-5.4-0305-global"),
    )

    all_results = []

    for idx, conv_dir in enumerate(conversation_dirs):
        md_path = conv_dir / "conversation.md"
        if not md_path.exists():
            continue

        print(f"\n{'─' * 70}")
        print(f"[{idx+1}/{len(conversation_dirs)}] {conv_dir.name}")
        print(f"{'─' * 70}")

        # ── Step 1: 解析 ──
        parsed = parse_conversation(str(md_path))
        print(f"\n📋 解析结果:")
        print(f"   Req ID     : {parsed.req_id}")
        print(f"   Session ID : {parsed.session_id}")
        print(f"   消息数     : {len(parsed.messages)}")
        print(f"   附件数     : {len(parsed.attachments)}")

        print(f"\n💬 对话消息:")
        for msg in parsed.messages:
            icon = "👤" if msg.role == "user" else "🤖"
            preview = msg.content[:80].replace("\n", " ")
            print(f"   {icon} [{msg.turn_index}] {preview}{'...' if len(msg.content) > 80 else ''}")

        if parsed.attachments:
            print(f"\n📎 附件:")
            for att in parsed.attachments:
                kind = "🖼️" if att.file_type == "image" else "📄"
                fname = Path(att.local_path).name[:50]
                print(f"   {kind} {fname} ({att.file_size} B)")

        # ── Step 2: 构建 prompt ──
        prompt, loaded_images = build_summary_prompt(parsed, str(conv_dir))

        print(f"\n🔧 Prompt 构建:")
        print(f"   消息数量   : {len(prompt)}")
        print(f"   加载图片数 : {loaded_images}")

        print(f"\n📝 Prompt 结构详情:")
        for pi, pmsg in enumerate(prompt):
            print(f"   ── 消息 {pi} (role={pmsg['role']}) ──")
            if isinstance(pmsg["content"], str):
                preview = pmsg["content"][:150].replace("\n", "\\n")
                print(f"      [文本] {preview}...")
            elif isinstance(pmsg["content"], list):
                for ci, item in enumerate(pmsg["content"]):
                    if item["type"] == "text":
                        preview = item["text"][:150].replace("\n", "\\n")
                        print(f"      [{ci}][文本] {preview}...")
                    elif item["type"] == "image_url":
                        url_preview = item["image_url"]["url"][:60]
                        print(f"      [{ci}][图片] {url_preview}...")

        # ── Step 3: 调用 LLM ──
        print(f"\n🤖 调用 LLM (model={summarizer.model})...")
        try:
            summary = summarizer._call_llm(prompt, max_tokens=512, temperature=0.3)
            print(f"\n✅ Summary 结果:")
            print(f"   {summary}")
        except Exception as e:
            summary = f"[ERROR] {e}"
            print(f"\n❌ LLM 调用失败: {e}")

        # 记录结果
        prompt_for_log = _sanitize_prompt_for_log(prompt)
        all_results.append({
            "conversation_dir": conv_dir.name,
            "req_id": parsed.req_id,
            "session_id": parsed.session_id,
            "message_count": len(parsed.messages),
            "attachment_count": len(parsed.attachments),
            "image_attachments": sum(1 for a in parsed.attachments if a.file_type == "image"),
            "doc_attachments": sum(1 for a in parsed.attachments if a.file_type == "document"),
            "loaded_images": loaded_images,
            "prompt": prompt_for_log,
            "summary": summary,
        })

    # ── 保存完整结果 ──
    output_path = Path(__file__).parent / "test_prompt_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"全部测试完成！结果已保存到: {output_path}")
    print(f"{'=' * 70}")

    # 汇总表
    print(f"\n{'对话目录':<22} {'消息':>4} {'附件':>4} {'图片':>4} {'加载':>4} {'Summary'}")
    print("-" * 90)
    for r in all_results:
        summary_preview = r["summary"][:40].replace("\n", " ")
        print(f"{r['conversation_dir']:<22} {r['message_count']:>4} {r['attachment_count']:>4} "
              f"{r['image_attachments']:>4} {r['loaded_images']:>4} {summary_preview}...")


if __name__ == "__main__":
    run_test()
