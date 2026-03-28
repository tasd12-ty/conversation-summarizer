"""
Office 文件预处理器（DOCX/PPTX/XLSX）
统一策略：使用 LibreOffice 转换为 PDF，再使用 PyMuPDF 逐页截图
"""

import os
import subprocess
import fitz  # PyMuPDF
from typing import List
from ..models import DocumentAsset, TextBlock, ImageBlock
from .base import BaseProcessor


class OfficeProcessor(BaseProcessor):
    """Office 文件预处理器（DOCX/PPTX/XLSX）"""

    SUPPORTED_EXTS = ['.docx', '.pptx', '.xlsx']

    def supports(self, ext: str) -> bool:
        """检查是否支持 Office 文件"""
        return ext.lower() in self.SUPPORTED_EXTS

    def process(self, file_path: str, file_id: str, max_pages: int = 50, dpi: int = 200) -> DocumentAsset:
        """
        处理 Office 文件

        流程：
        1. 使用 LibreOffice headless 转换为 PDF
        2. 使用 PyMuPDF 逐页截图
        3. 标注原始文件格式

        Args:
            file_path: Office 文件路径
            file_id: 文件唯一标识
            max_pages: 最大处理页数
            dpi: 截图分辨率

        Returns:
            DocumentAsset: 统一文档资产对象
        """
        # 获取文件扩展名作为原始格式
        ext = os.path.splitext(file_path)[1].lower()
        original_format = ext.lstrip('.')

        # 1. 转换为 PDF
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'processed_cache')
        os.makedirs(cache_dir, exist_ok=True)
        pdf_path = os.path.join(cache_dir, f"{file_id}.pdf")

        try:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", cache_dir, file_path
            ], check=True, capture_output=True)

            # LibreOffice 转换后的文件名可能与原文件不同，需要重命名
            # 查找生成的 PDF 文件
            generated_pdf = os.path.join(cache_dir, os.path.splitext(os.path.basename(file_path))[0] + ".pdf")
            if os.path.exists(generated_pdf) and generated_pdf != pdf_path:
                os.rename(generated_pdf, pdf_path)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"LibreOffice 转换失败: {e.stderr.decode('utf-8', errors='ignore')}")
        except FileNotFoundError:
            raise RuntimeError("LibreOffice 未安装，请先安装 libreoffice")

        # 2. 使用 PyMuPDF 处理 PDF
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        text_blocks: List[TextBlock] = []
        image_blocks: List[ImageBlock] = []

        # 确定要处理的页数
        pages_to_process = range(min(total_pages, max_pages))

        for page_num in pages_to_process:
            page = doc.load_page(page_num)

            # 抽取文本
            text = page.get_text()
            if text.strip():
                text_blocks.append(TextBlock(
                    content=text,
                    page_number=page_num + 1
                ))

            # 渲染截图
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            image_path = os.path.join(cache_dir, f"{file_id}_page_{page_num + 1}.png")
            pix.save(image_path)

            image_blocks.append(ImageBlock(
                image_path=image_path,
                page_number=page_num + 1,
                original_format=original_format  # 标注原始文件格式
            ))

        doc.close()

        # 清理临时 PDF 文件
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        return DocumentAsset(
            file_id=file_id,
            kind=original_format,
            text_blocks=text_blocks,
            image_blocks=image_blocks,
            metadata={
                "original_format": original_format,
                "total_pages": total_pages,
                "processed_pages": len(pages_to_process),
                "dpi": dpi
            }
        )
