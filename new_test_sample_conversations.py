"""
测试 sample 目录下的对话记录解析和多模态 LLM 调用
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from conversation_summarizer.summarizer import Summarizer


class ConversationParser:
    """对话记录解析器"""
    
    def __init__(self, conversation_md_path: str):
        self.md_path = conversation_md_path
        self.messages = []
        self.attachments = []
        
    def parse(self) -> Dict:
        """解析 conversation.md 文件"""
        with open(self.md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取基本信息
        req_id = self._extract_field(content, r'\*\*Req ID\*\*:\s*`([^`]+)`')
        session_id = self._extract_field(content, r'\*\*Session ID\*\*:\s*`([^`]+)`')
        time = self._extract_field(content, r'\*\*时间\*\*:\s*(.+)')
        
        # 提取对话内容
        self.messages = self._extract_messages(content)
        
        # 提取附件信息
        self.attachments = self._extract_attachments(content)
        
        return {
            'req_id': req_id,
            'session_id': session_id,
            'time': time,
            'messages': self.messages,
            'attachments': self.attachments,
            'message_count': len(self.messages),
            'attachment_count': len(self.attachments)
        }
    
    def _extract_field(self, content: str, pattern: str) -> str:
        """提取字段"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else ''
    
    def _extract_messages(self, content: str) -> List[Dict]:
        """提取对话消息"""
        messages = []
        
        # 匹配用户和助手的消息
        pattern = r'\*\*([👤🤖])\s+(用户|助手)\*\*\s*\(full\):\s*\n(.*?)(?=\n---|\n\*\*|$)'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            emoji = match.group(1)
            role_type = match.group(2)
            message_content = match.group(3).strip()
            
            role = 'user' if '用户' in role_type else 'assistant'
            
            messages.append({
                'role': role,
                'content': message_content,
                'has_images': '图片' in message_content or '二维码' in message_content
            })
        
        return messages
    
    def _extract_attachments(self, content: str) -> List[Dict]:
        """提取附件信息"""
        attachments = []
        
        # 匹配文件信息
        pattern = r'- \*\*本地路径\*\*:\s*`([^`]+)`\s*\n\s*- 原始 URL:\s*(\S+)\s*\n\s*- 文件大小:\s*(\d+)\s*字节'
        
        for match in re.finditer(pattern, content):
            local_path = match.group(1)
            url = match.group(2)
            file_size = int(match.group(3))
            
            # 判断文件类型
            file_type = 'image' if any(ext in local_path for ext in ['.jpg', '.png', '.jpeg']) else 'document'
            
            attachments.append({
                'local_path': local_path,
                'url': url,
                'file_size': file_size,
                'file_type': file_type
            })
        
        return attachments
    
    def build_multimodal_prompt(self, target_question: str = None) -> List[Dict]:
        """
        构建多模态 prompt
        
        Args:
            target_question: 目标问题（如果为 None，则使用最后一个用户问题）
        
        Returns:
            List[Dict]: 多模态 prompt 格式
        """
        if not target_question:
            # 使用最后一个用户问题
            user_messages = [m for m in self.messages if m['role'] == 'user']
            if user_messages:
                target_question = user_messages[-1]['content']
            else:
                target_question = "请总结这段对话"
        
        # 构建系统提示
        system_prompt = f"""你是一个多模态对话摘要助手。请根据以下对话历史和附件内容，回答用户的问题。

用户问题：{target_question}

对话历史：
"""
        
        # 添加对话历史（只保留最近的几条）
        recent_messages = self.messages[-6:] if len(self.messages) > 6 else self.messages
        
        for msg in recent_messages:
            role_label = "用户" if msg['role'] == 'user' else "助手"
            system_prompt += f"\n{role_label}: {msg['content'][:500]}"
        
        # 构建多模态 prompt
        prompt = []
        
        # 添加系统提示作为文本
        prompt.append({
            "role": "system",
            "content": [{"type": "text", "text": system_prompt}]
        })
        
        # 添加图片附件（如果有）
        image_attachments = [a for a in self.attachments if a['file_type'] == 'image']
        if image_attachments:
            image_content = []
            for img in image_attachments[:3]:  # 最多添加3张图片
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": img['url']}
                })
            
            if image_content:
                prompt.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "以下是相关的图片附件："},
                        *image_content
                    ]
                })
        
        # 添加用户问题
        prompt.append({
            "role": "user",
            "content": [{"type": "text", "text": f"请回答：{target_question}"}]
        })
        
        return prompt


def test_conversation_parsing(sample_dir: str):
    """测试对话记录解析"""
    print("=" * 70)
    print("测试 sample 目录下的对话记录解析")
    print("=" * 70)
    
    # 获取所有 conversation.md 文件
    sample_path = Path(sample_dir)
    conversation_files = list(sample_path.glob('*/conversation.md'))
    
    if not conversation_files:
        print("❌ 未找到 conversation.md 文件")
        return
    
    print(f"\n找到 {len(conversation_files)} 个对话记录\n")
    
    # 测试第一个对话记录
    test_file = conversation_files[0]
    print(f"测试文件: {test_file}")
    print("-" * 70)
    
    # 解析对话
    parser = ConversationParser(str(test_file))
    result = parser.parse()
    
    print(f"\n✅ 解析成功!")
    print(f"  Req ID: {result['req_id']}")
    print(f"  Session ID: {result['session_id']}")
    print(f"  消息数量: {result['message_count']}")
    print(f"  附件数量: {result['attachment_count']}")
    
    # 显示消息摘要
    print(f"\n对话消息摘要:")
    for i, msg in enumerate(result['messages'][:5]):
        role = "👤 用户" if msg['role'] == 'user' else "🤖 助手"
        content_preview = msg['content'][:80].replace('\n', ' ')
        print(f"  {i+1}. {role}: {content_preview}...")
    
    # 显示附件信息
    if result['attachments']:
        print(f"\n附件信息:")
        for i, att in enumerate(result['attachments'][:5]):
            file_type = "🖼️ 图片" if att['file_type'] == 'image' else "📄 文档"
            print(f"  {i+1}. {file_type}: {Path(att['local_path']).name} ({att['file_size']} 字节)")
    
    return parser, result


def test_multimodal_prompt_building(parser: ConversationParser, result: Dict):
    """测试多模态 prompt 构建"""
    print("\n" + "=" * 70)
    print("测试多模态 prompt 构建")
    print("=" * 70)
    
    # 获取最后一个用户问题
    user_messages = [m for m in result['messages'] if m['role'] == 'user']
    if not user_messages:
        print("❌ 未找到用户消息")
        return None
    
    target_question = user_messages[-1]['content']
    print(f"\n目标问题: {target_question[:100]}...")
    
    # 构建多模态 prompt
    prompt = parser.build_multimodal_prompt(target_question)
    
    print(f"\n✅ Prompt 构建成功!")
    print(f"  Prompt 消息数量: {len(prompt)}")
    
    # 记录完整的 prompt
    print(f"\n完整的 Prompt 结构:")
    for i, msg in enumerate(prompt):
        print(f"\n--- 消息 {i+1} (role: {msg['role']}) ---")
        for j, content_item in enumerate(msg['content']):
            if content_item['type'] == 'text':
                text_preview = content_item['text'][:200].replace('\n', ' ')
                print(f"  内容 {j+1} [文本]: {text_preview}...")
            elif content_item['type'] == 'image_url':
                print(f"  内容 {j+1} [图片]: {content_item['image_url']['url'][:80]}...")
    
    # 保存 prompt 到文件
    prompt_output_path = Path(__file__).parent / 'test_prompt_output.json'
    with open(prompt_output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'conversation_file': str(parser.md_path),
            'target_question': target_question,
            'prompt': prompt,
            'message_count': len(prompt),
            'has_images': any(
                item['type'] == 'image_url'
                for msg in prompt
                for item in msg['content']
            )
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Prompt 已保存到: {prompt_output_path}")
    
    return prompt


def test_llm_call(prompt: List[Dict]):
    """测试 LLM 调用"""
    print("\n" + "=" * 70)
    print("测试 LLM 调用")
    print("=" * 70)
    
    api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
    api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
    model = os.getenv("LLM_MODEL", "gpt-5.4-0305-global")
    
    print(f"\n模型: {model}")
    print(f"API 端点: {api_base}")
    
    summarizer = Summarizer(
        api_key=api_key,
        api_base=api_base,
        model=model
    )
    
    try:
        print("\n正在调用 LLM...")
        response = summarizer._call_llm(prompt, max_tokens=1024, temperature=0.7)
        
        print(f"\n✅ LLM 调用成功!")
        print(f"\n响应内容:\n{response[:500]}")
        
        return response
    except Exception as e:
        print(f"\n❌ LLM 调用失败: {e}")
        return None


def main():
    """主函数"""
    sample_dir = str(Path(__file__).parent.parent / 'sample')
    
    # 测试 1: 解析对话记录
    parser, result = test_conversation_parsing(sample_dir)
    
    if not parser or not result:
        print("\n❌ 解析失败，终止测试")
        return
    
    # 测试 2: 构建多模态 prompt
    prompt = test_multimodal_prompt_building(parser, result)
    
    if not prompt:
        print("\n❌ Prompt 构建失败，终止测试")
        return
    
    # 测试 3: 调用 LLM
    response = test_llm_call(prompt)
    
    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"✅ 对话记录解析: 成功")
    print(f"✅ 多模态 Prompt 构建: 成功")
    print(f"{'✅' if response else '❌'} LLM 调用: {'成功' if response else '失败'}")
    print(f"\n完整的 Prompt 已保存到: conversation_summarizer/test_prompt_output.json")


if __name__ == "__main__":
    main()
