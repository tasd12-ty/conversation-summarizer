"""
预处理器基础接口
"""

from abc import ABC, abstractmethod
from ..models import DocumentAsset


class BaseProcessor(ABC):
    """文件预处理器基类"""

    @abstractmethod
    def process(self, file_path: str, file_id: str, **kwargs) -> DocumentAsset:
        """
        处理文件并返回 DocumentAsset

        Args:
            file_path: 文件路径
            file_id: 文件唯一标识
            **kwargs: 额外参数

        Returns:
            DocumentAsset: 统一文档资产对象
        """
        pass

    @abstractmethod
    def supports(self, ext: str) -> bool:
        """
        检查是否支持该文件扩展名

        Args:
            ext: 文件扩展名（如 .pdf, .docx）

        Returns:
            bool: 是否支持
        """
        pass
