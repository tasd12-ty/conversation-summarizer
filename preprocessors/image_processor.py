"""
图片文件预处理器
保留原图，按需触发 OCR
"""

import os
from ..models import DocumentAsset, TextBlock, ImageBlock
from .base import BaseProcessor


class ImageProcessor(BaseProcessor):
    """图片文件预处理器"""

    SUPPORTED_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']

    def supports(self, ext: str) -> bool:
        """检查是否支持图片文件"""
        return ext.lower() in self.SUPPORTED_EXTS

    def process(self, file_path: str, file_id: str, need_ocr: bool = False, ocr_text: str = None) -> DocumentAsset:
        """
        处理图片文件

        Args:
            file_path: 图片文件路径
            file_id: 文件唯一标识
            need_ocr: 是否需要 OCR
            ocr_text: OCR 提取的文本内容（如果已预先提取）

        Returns:
            DocumentAsset: 统一文档资产对象
        """
        image_blocks = [ImageBlock(image_path=file_path)]

        text_blocks = []
        if need_ocr and ocr_text:
            text_blocks.append(TextBlock(content=ocr_text))

        return DocumentAsset(
            file_id=file_id,
            kind="image",
            text_blocks=text_blocks,
            image_blocks=image_blocks,
            metadata={
                "need_ocr": need_ocr,
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
        )
