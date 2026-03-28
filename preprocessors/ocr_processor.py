"""
OCR 处理器
使用 PaddleOCR 进行按需 OCR
"""

import os
from typing import Optional


class OCRProcessor:
    """OCR 处理器（使用 PaddleOCR）"""

    def __init__(self, lang: str = "ch"):
        """
        初始化 OCR 处理器

        Args:
            lang: OCR 语言（ch=中文，en=英文）
        """
        self.lang = lang
        self._ocr = None

    def _get_ocr(self):
        """懒加载 PaddleOCR 实例"""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang)
            except ImportError:
                raise ImportError("请先安装 PaddleOCR: pip install paddleocr paddlepaddle")
        return self._ocr

    def run_ocr(self, image_path: str) -> dict:
        """
        对图片进行 OCR

        Args:
            image_path: 图片路径

        Returns:
            dict: 包含 text（文本内容）和 confidence（置信度）
        """
        ocr = self._get_ocr()
        result = ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return {"text": "", "confidence": 0.0}

        # 提取文本和置信度
        texts = []
        confidences = []
        for line in result[0]:
            if line and len(line) >= 2:
                texts.append(line[1][0])
                confidences.append(line[1][1])

        text = "\n".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": text,
            "confidence": avg_confidence
        }

    def should_ocr(self, text_content: str = "", file_type: str = "", user_question: str = "") -> bool:
        """
        判断是否需要触发 OCR

        策略：
        - 文本内容为空或质量差
        - 用户问题明确提到"图中文字"、"识别文字"
        - 扫描 PDF / 图片型文件

        Args:
            text_content: 已抽取的文本内容
            file_type: 文件类型
            user_question: 用户问题

        Returns:
            bool: 是否需要 OCR
        """
        # 用户问题明确提到文字识别
        ocr_keywords = ["图中文字", "识别文字", "OCR", "提取文字", "文字内容"]
        if any(keyword in user_question for keyword in ocr_keywords):
            return True

        # 文本内容为空或质量差
        if not text_content or len(text_content.strip()) < 10:
            return True

        return False
