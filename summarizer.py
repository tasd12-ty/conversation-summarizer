"""
意图识别和摘要生成器
调用 Qwen3.5 多模态模型进行意图识别和摘要生成
"""

import json
import os
from typing import List, Optional
from .models import (
    AttachmentSummary,
    IntentResult,
    DocumentAsset,
)


# 意图识别 Prompt
INTENT_CLASSIFIER_PROMPT = """
请分析以下用户问题和附件信息，识别用户意图。

用户问题：{user_question}

可用附件：{available_files}

请输出 JSON 格式的结果（不要输出其他内容）：
{{
  "intent": "summary|compare|extract_action_items|question_answering|table_analysis",
  "relevant_files": ["file_id_1", "file_id_2"],
  "need_visual_pages": true,
  "need_ocr": false
}}
"""

# 单附件摘要 Prompt
ATTACHMENT_SUMMARY_PROMPT = """
请阅读以下附件内容，生成结构化摘要。

文件类型：{file_type}
文件名：{filename}

文本内容：
{text_content}

请输出 JSON 格式的结果（不要输出其他内容）：
{{
  "key_points": ["关键点1", "关键点2"],
  "entities": ["实体1", "实体2"],
  "tables": ["表格描述1"],
  "action_items": ["待办事项1"],
  "uncertainties": ["不确定项1"],
  "source_map": [{{"page": 1, "note": "说明"}}]
}}
"""

# 最终汇总 Prompt
FINAL_SUMMARY_PROMPT = """
请根据以下信息，用一句话（20-50字）总结这次对话的核心内容。

用户问题：{user_question}
会话摘要：{session_summary}

附件摘要：
{attachment_summaries}

请用一句话总结：
"""


class Summarizer:
    """摘要生成器"""

    def __init__(self, api_key: str, api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen-vl-max"):
        """
        初始化摘要生成器

        Args:
            api_key: API Key
            api_base: API Base URL
            model: 模型名称
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model

    def _call_llm(self, messages: List[dict], response_format: str = None, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """
        调用大模型，支持两种后端模式：
        - cloud（默认）：阿里内部 LLM API，使用自定义请求格式
        - vllm：本地 vLLM 部署，使用 OpenAI 兼容格式

        通过环境变量 LLM_API_MODE 切换，默认为 cloud。

        Args:
            messages: 消息列表
            response_format: 响应格式（如 "json"）
            max_tokens: 最大 token 数
            temperature: 温度参数

        Returns:
            str: 模型响应内容
        """
        api_mode = os.getenv("LLM_API_MODE", "cloud").lower()

        if api_mode == "vllm":
            return self._call_vllm(messages, max_tokens, temperature)
        else:
            return self._call_cloud_api(messages, max_tokens, temperature)

    def _call_vllm(self, messages: List[dict], max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """
        调用本地 vLLM 部署的模型（OpenAI 兼容格式）

        vLLM 请求格式：
        {
            "model": "Qwen/Qwen2.5-VL-72B-Instruct",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 1024,
            "temperature": 0.3
        }
        """
        try:
            import requests

            # 构建 OpenAI 兼容的 messages 格式
            formatted_messages = []
            for msg in messages:
                content = msg.get("content")
                if isinstance(content, str):
                    formatted_messages.append({"role": msg.get("role", "user"), "content": content})
                elif isinstance(content, list):
                    formatted_messages.append({"role": msg.get("role", "user"), "content": content})
                else:
                    formatted_messages.append({"role": msg.get("role", "user"), "content": str(content)})

            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            response = requests.post(
                self.api_base,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )

            if response.status_code != 200:
                error_msg = f"vLLM API 请求失败: HTTP {response.status_code}"
                try:
                    error_msg += f", 详情: {response.json()}"
                except Exception:
                    error_msg += f", 响应内容: {response.text[:500]}"
                raise RuntimeError(error_msg)

            result = response.json()

            # OpenAI 兼容格式：result.choices[0].message.content
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return str(result)

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"调用 vLLM 失败: {str(e)}")

    def _call_cloud_api(self, messages: List[dict], max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """
        调用云端 API（阿里内部 LLM API 自定义格式）

        云端请求格式：
        {
            "model": "gpt-5.4-0305-global",
            "prompt": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            "params": {"max_tokens": 1024, "temperature": 0.9},
            "app": "llm_application",
            "access_key": "...",
            ...
        }
        """
        try:
            import requests

            # 构建 prompt 格式
            prompt = []
            for msg in messages:
                content = []
                if isinstance(msg.get("content"), str):
                    content.append({"type": "text", "text": msg["content"]})
                elif isinstance(msg.get("content"), list):
                    content = msg["content"]
                else:
                    content.append({"type": "text", "text": str(msg.get("content", ""))})
                
                prompt.append({
                    "role": msg.get("role", "user"),
                    "content": content
                })

            # 调用 API
            response = requests.post(
                self.api_base,
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "params": {
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    "app": "llm_application",
                    "quota_id": os.getenv("LLM_QUOTA_ID", "00da3781-1f9d-4a63-857e-7c045c460290"),
                    "user_id": os.getenv("LLM_USER_ID", "345245"),
                    "access_key": self.api_key,
                    "tag": os.getenv("LLM_TAG", "conversation_summarizer")
                },
                timeout=60
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"API 请求失败: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f", 详情: {error_detail}"
                except Exception:
                    error_msg += f", 响应内容: {response.text[:500]}"
                raise RuntimeError(error_msg)
            
            result = response.json()

            # 提取响应内容 - 处理嵌套结构
            # 优先从 data.completion.choices 提取
            if "data" in result:
                data = result["data"]
                if "completion" in data and "choices" in data["completion"]:
                    return data["completion"]["choices"][0]["message"]["content"]
                elif "choices" in data:
                    return data["choices"][0]["message"]["content"]
                elif "message" in data:
                    return data["message"]
            
            # 直接从根级别提取
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            elif "message" in result:
                return result["message"]
            else:
                # 如果无法解析，返回完整响应用于调试
                return str(result)

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"调用大模型失败: {str(e)}")

    def classify_intent(self, user_question: str, available_files: List[str]) -> IntentResult:
        """
        意图识别

        Args:
            user_question: 用户问题
            available_files: 可用文件列表

        Returns:
            IntentResult: 意图识别结果
        """
        prompt = INTENT_CLASSIFIER_PROMPT.format(
            user_question=user_question,
            available_files=", ".join(available_files)
        )

        messages = [
            {"role": "system", "content": "你是一个意图识别助手，请分析用户意图并输出 JSON 格式的结果。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_llm(messages)

        try:
            # 提取 JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)
            return IntentResult(**result)
        except Exception as e:
            # 默认返回 summary 意图
            return IntentResult(
                intent="summary",
                relevant_files=available_files[:3],
                need_visual_pages=False,
                need_ocr=False
            )

    def summarize_attachment(
        self,
        file_type: str,
        filename: str,
        text_content: str
    ) -> AttachmentSummary:
        """
        单附件摘要生成

        Args:
            file_type: 文件类型
            filename: 文件名
            text_content: 文本内容

        Returns:
            AttachmentSummary: 附件摘要
        """
        prompt = ATTACHMENT_SUMMARY_PROMPT.format(
            file_type=file_type,
            filename=filename,
            text_content=text_content[:3000]  # 限制文本长度
        )

        messages = [
            {"role": "system", "content": "你是一个文档分析助手，请阅读附件内容并生成结构化摘要。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_llm(messages)

        try:
            # 提取 JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)
            return AttachmentSummary(
                file_id="",  # 由调用方设置
                title=filename,
                type=file_type,
                **result
            )
        except Exception as e:
            # 返回空摘要
            return AttachmentSummary(
                file_id="",
                title=filename,
                type=file_type,
                key_points=["无法生成摘要"],
                uncertainties=["解析失败"]
            )

    def generate_final_summary(
        self,
        user_question: str,
        session_summary: Optional[str],
        attachment_summaries: List[AttachmentSummary]
    ) -> str:
        """
        最终汇总摘要生成

        Args:
            user_question: 用户问题
            session_summary: 会话摘要
            attachment_summaries: 附件摘要列表

        Returns:
            str: 一句话摘要
        """
        # 格式化附件摘要
        summaries_text = "\n".join([
            f"- {s.title} ({s.type}): {', '.join(s.key_points[:3])}"
            for s in attachment_summaries
        ])

        prompt = FINAL_SUMMARY_PROMPT.format(
            user_question=user_question,
            session_summary=session_summary or "无",
            attachment_summaries=summaries_text
        )

        messages = [
            {"role": "system", "content": "你是一个摘要生成助手，请用一句话（20-50字）总结对话核心内容。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_llm(messages)
        return response.strip()
