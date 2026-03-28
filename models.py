"""
多模态对话摘要系统 - 数据模型定义
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class FileRecord(BaseModel):
    """文件记录模型"""
    file_id: str
    session_id: str
    filename: str
    mime_type: str
    ext: str
    local_path: str
    size_bytes: int
    created_at: datetime = Field(default_factory=datetime.now)


class TextBlock(BaseModel):
    """文本块模型"""
    content: str
    page_number: Optional[int] = None
    bbox: Optional[list[float]] = None


class ImageBlock(BaseModel):
    """图片块模型"""
    image_path: str
    page_number: Optional[int] = None
    caption: Optional[str] = None
    original_format: Optional[str] = None  # 标注原始文件格式（docx/pptx/xlsx）


class DocumentAsset(BaseModel):
    """统一文档资产模型"""
    file_id: str
    kind: Literal["pdf", "image", "docx", "pptx", "xlsx"]
    text_blocks: list[TextBlock] = Field(default_factory=list)
    image_blocks: list[ImageBlock] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    summary_cache: Optional[str] = None
    source_map: list[dict] = Field(default_factory=list)


class AttachmentSummary(BaseModel):
    """单附件摘要模型"""
    file_id: str
    title: str
    type: str
    key_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    source_map: list[dict] = Field(default_factory=list)


class IntentResult(BaseModel):
    """意图识别结果模型"""
    intent: Literal["summary", "compare", "extract_action_items", "question_answering", "table_analysis"]
    relevant_files: list[str] = Field(default_factory=list)
    need_visual_pages: bool = False
    need_ocr: bool = False


class SessionRecord(BaseModel):
    """会话记录模型"""
    session_id: str
    files: list[FileRecord] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    short_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AnalyzeRequest(BaseModel):
    """分析请求模型"""
    session_id: str
    user_question: str
    file_ids: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """分析响应模型"""
    session_id: str
    intent: str
    summary: str
    attachment_summaries: list[AttachmentSummary]
    source_map: list[dict] = Field(default_factory=list)
