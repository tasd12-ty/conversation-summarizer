"""
测试脚本 - 验证 LLM API 调用和摘要功能
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from conversation_summarizer.summarizer import Summarizer


def test_basic_api_call():
    """测试基础 API 调用"""
    print("=" * 50)
    print("测试 1: 基础 API 调用")
    print("=" * 50)
    
    api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
    api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
    model = os.getenv("LLM_MODEL", "gemini-3-pro-preview")
    
    summarizer = Summarizer(
        api_key=api_key,
        api_base=api_base,
        model=model
    )
    
    messages = [
        {"role": "user", "content": "who are you"}
    ]
    
    try:
        response = summarizer._call_llm(messages, max_tokens=1024, temperature=0.9)
        print(f"✅ API 调用成功!")
        print(f"响应内容: {response[:200]}...")
        return True
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return False


def test_intent_classification():
    """测试意图识别"""
    print("\n" + "=" * 50)
    print("测试 2: 意图识别")
    print("=" * 50)
    
    api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
    api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
    model = os.getenv("LLM_MODEL", "gemini-3-pro-preview")
    
    summarizer = Summarizer(
        api_key=api_key,
        api_base=api_base,
        model=model
    )
    
    user_question = "请总结这份文档的主要内容"
    available_files = ["document1.pdf", "document2.docx"]
    
    try:
        result = summarizer.classify_intent(user_question, available_files)
        print(f"✅ 意图识别成功!")
        print(f"意图: {result.intent}")
        print(f"相关文件: {result.relevant_files}")
        print(f"需要视觉页面: {result.need_visual_pages}")
        return True
    except Exception as e:
        print(f"❌ 意图识别失败: {e}")
        return False


def test_attachment_summary():
    """测试附件摘要"""
    print("\n" + "=" * 50)
    print("测试 3: 附件摘要")
    print("=" * 50)
    
    api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
    api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
    model = os.getenv("LLM_MODEL", "gemini-3-pro-preview")
    
    summarizer = Summarizer(
        api_key=api_key,
        api_base=api_base,
        model=model
    )
    
    sample_text = """
    这是一份关于人工智能发展的报告。
    主要内容包括：
    1. 人工智能的历史发展
    2. 当前技术现状
    3. 未来发展趋势
    4. 应用场景分析
    
    关键数据：
    - 2023年全球AI市场规模达到5000亿美元
    - 预计到2030年将增长到2万亿美元
    - 主要应用领域：医疗、金融、制造、教育
    """
    
    try:
        result = summarizer.summarize_attachment(
            file_type="pdf",
            filename="AI发展报告.pdf",
            text_content=sample_text
        )
        print(f"✅ 附件摘要成功!")
        print(f"标题: {result.title}")
        print(f"类型: {result.type}")
        print(f"关键点: {result.key_points}")
        return True
    except Exception as e:
        print(f"❌ 附件摘要失败: {e}")
        return False


def test_final_summary():
    """测试最终汇总"""
    print("\n" + "=" * 50)
    print("测试 4: 最终汇总")
    print("=" * 50)
    
    api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
    api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
    model = os.getenv("LLM_MODEL", "gemini-3-pro-preview")
    
    summarizer = Summarizer(
        api_key=api_key,
        api_base=api_base,
        model=model
    )
    
    from conversation_summarizer.models import AttachmentSummary
    
    attachment_summaries = [
        AttachmentSummary(
            file_id="file1",
            title="AI发展报告.pdf",
            type="pdf",
            key_points=["AI市场规模快速增长", "应用场景广泛"]
        )
    ]
    
    try:
        result = summarizer.generate_final_summary(
            user_question="请总结这份文档",
            session_summary="之前讨论了AI的基本概念",
            attachment_summaries=attachment_summaries
        )
        print(f"✅ 最终汇总成功!")
        print(f"摘要: {result}")
        return True
    except Exception as e:
        print(f"❌ 最终汇总失败: {e}")
        return False


async def test_batch_processing():
    """测试批量处理"""
    print("\n" + "=" * 50)
    print("测试 5: 批量处理（异步）")
    print("=" * 50)
    
    api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
    api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
    model = os.getenv("LLM_MODEL", "gemini-3-pro-preview")
    
    summarizer = Summarizer(
        api_key=api_key,
        api_base=api_base,
        model=model
    )
    
    # 模拟多个文档
    documents = [
        {"file_type": "pdf", "filename": "doc1.pdf", "text": "文档1内容：关于机器学习的基础知识"},
        {"file_type": "docx", "filename": "doc2.docx", "text": "文档2内容：深度学习的应用"},
        {"file_type": "pdf", "filename": "doc3.pdf", "text": "文档3内容：自然语言处理技术"},
    ]
    
    try:
        # 并发处理多个文档
        tasks = []
        for doc in documents:
            task = asyncio.to_thread(
                summarizer.summarize_attachment,
                doc["file_type"],
                doc["filename"],
                doc["text"]
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"✅ 批量处理完成!")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  文档 {i+1}: 失败 - {result}")
            else:
                print(f"  文档 {i+1}: 成功 - {result.title}")
        
        return True
    except Exception as e:
        print(f"❌ 批量处理失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("多模态对话摘要系统 - 功能测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 同步测试
    results.append(("基础 API 调用", test_basic_api_call()))
    results.append(("意图识别", test_intent_classification()))
    results.append(("附件摘要", test_attachment_summary()))
    results.append(("最终汇总", test_final_summary()))
    
    # 异步测试
    results.append(("批量处理", asyncio.run(test_batch_processing())))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统可以正常运行。")
    else:
        print("\n⚠️  部分测试失败，请检查配置和网络连接。")


if __name__ == "__main__":
    main()
