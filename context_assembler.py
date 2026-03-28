"""
上下文装配层
根据用户问题和意图识别结果，决定当前轮要送哪些内容给模型
"""

from typing import List, Optional
from .models import AttachmentSummary, IntentResult, DocumentAsset


class ContextAssembler:
    """上下文装配器"""

    def assemble_context(
        self,
        user_question: str,
        session_summary: Optional[str],
        attachment_summaries: List[AttachmentSummary],
        intent_result: IntentResult
    ) -> str:
        """
        装配上下文

        规则：
        1. 当前用户问题
        2. 最近会话短摘要
        3. 各附件的 attachment summary + 少量必要原文片段/截图

        Args:
            user_question: 用户问题
            session_summary: 会话摘要
            attachment_summaries: 附件摘要列表
            intent_result: 意图识别结果

        Returns:
            str: 装配好的上下文字符串
        """
        context_parts = []

        # 1. 用户问题
        context_parts.append(f"用户问题：{user_question}")

        # 2. 会话摘要
        if session_summary:
            context_parts.append(f"\n会话历史摘要：{session_summary}")

        # 3. 附件摘要（只包含相关附件）
        relevant_summaries = [
            s for s in attachment_summaries
            if s.file_id in intent_result.relevant_files
        ]

        if relevant_summaries:
            context_parts.append("\n附件摘要：")
            for summary in relevant_summaries:
                context_parts.append(f"\n--- 附件 {summary.file_id} ---")
                context_parts.append(f"标题：{summary.title}")
                context_parts.append(f"类型：{summary.type}")

                if summary.key_points:
                    context_parts.append(f"关键点：{', '.join(summary.key_points)}")

                if summary.tables:
                    context_parts.append(f"表格：{', '.join(summary.tables)}")

                if summary.action_items:
                    context_parts.append(f"待办事项：{', '.join(summary.action_items)}")

                if summary.uncertainties:
                    context_parts.append(f"不确定项：{', '.join(summary.uncertainties)}")

        return "\n".join(context_parts)

    def select_visual_pages(
        self,
        document_assets: List[DocumentAsset],
        intent_result: IntentResult
    ) -> List[str]:
        """
        选择需要发送给模型的视觉页面

        规则：
        - 用户问图表/排版/示意图
        - OCR 质量不稳
        - PPT/PDF 页面以视觉内容为主
        - 表格有图形、颜色、合并单元格语义

        Args:
            document_assets: 文档资产列表
            intent_result: 意图识别结果

        Returns:
            List[str]: 需要发送的图片路径列表
        """
        if not intent_result.need_visual_pages:
            return []

        image_paths = []
        for asset in document_assets:
            if asset.file_id in intent_result.relevant_files:
                for img_block in asset.image_blocks:
                    image_paths.append(img_block.image_path)

        return image_paths
