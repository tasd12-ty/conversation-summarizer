"""
PDF 文件预处理器
使用 PyMuPDF 进行文本抽取和页面截图
"""

import os
import fitz  # PyMuPDF
from typing import List
from ..models import DocumentAsset, TextBlock, ImageBlock
from .base import BaseProcessor


class PDFProcessor(BaseProcessor):
    """PDF 文件预处理器"""

    def supports(self, ext: str) -> bool:
        """检查是否支持 PDF 文件"""
        return ext.lower() in ['.pdf']

    def process(self, file_path: str, file_id: str, max_pages: int = 50, dpi: int = 200) -> DocumentAsset:
        """
        处理 PDF 文件

        Args:
            file_path: PDF 文件路径
            file_id: 文件唯一标识
            max_pages: 最大处理页数（超过此数只处理前 N 页）
            dpi: 截图分辨率

        Returns:
            DocumentAsset: 统一文档资产对象
        """
        doc = fitz.open(file_path)
        total_pages = len(doc)

        text_blocks: List[TextBlock] = []
        image_blocks: List[ImageBlock] = []

        # 确定要处理的页数
        pages_to_process = range(min(total_pages, max_pages))

        for page_num in pages_to_process:
            page = doc.load_page(page_num)

            # 1. 抽取文本
            text = page.get_text()
            if text.strip():
                text_blocks.append(TextBlock(
                    content=text,
                    page_number=page_num + 1
                ))

            # 2. 渲染截图
            # 计算缩放矩阵（dpi / 72）
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 保存图片
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'processed_cache')
            os.makedirs(cache_dir, exist_ok=True)
            image_path = os.path.join(cache_dir, f"{file_id}_page_{page_num + 1}.png")
            pix.save(image_path)

            image_blocks.append(ImageBlock(
                image_path=image_path,
                page_number=page_num + 1
            ))

        doc.close()

        return DocumentAsset(
            file_id=file_id,
            kind="pdf",
            text_blocks=text_blocks,
            image_blocks=image_blocks,
            metadata={
                "total_pages": total_pages,
                "processed_pages": len(pages_to_process),
                "dpi": dpi
            }
        )
