"""
多模态对话摘要系统 - FastAPI 路由
"""

import os
import uuid
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from .models import (
    FileRecord,
    DocumentAsset,
    AttachmentSummary,
    SessionRecord,
    AnalyzeRequest,
    AnalyzeResponse,
)
from .preprocessors import PDFProcessor, ImageProcessor, OfficeProcessor, OCRProcessor
from .context_assembler import ContextAssembler
from .summarizer import Summarizer

app = FastAPI(title="多模态对话摘要系统", version="1.0.0")

# 全局状态存储（生产环境应使用数据库）
sessions: Dict[str, SessionRecord] = {}
file_records: Dict[str, FileRecord] = {}
document_assets: Dict[str, DocumentAsset] = {}
attachment_summaries: Dict[str, AttachmentSummary] = {}

# 初始化上下文装配器
context_assembler = ContextAssembler()

# 摘要生成器（需要 API Key）
summarizer = None

def get_summarizer() -> Summarizer:
    """获取摘要生成器实例"""
    global summarizer
    if summarizer is None:
        api_key = os.getenv("LLM_ACCESS_KEY", "efc8c9ca4ac5b0dd4018bcd3a83d767d")
        api_base = os.getenv("LLM_API_BASE", "https://llm-chat-api.alibaba-inc.com/v1/api/chat")
        model = os.getenv("LLM_MODEL", "gemini-3-pro-preview")
        summarizer = Summarizer(api_key=api_key, api_base=api_base, model=model)
    return summarizer


def preprocess_file(file_record: FileRecord, need_ocr: bool = False, user_question: str = "") -> DocumentAsset:
    """
    预处理文件

    Args:
        file_record: 文件记录
        need_ocr: 是否需要 OCR
        user_question: 用户问题

    Returns:
        DocumentAsset: 文档资产
    """
    ext = os.path.splitext(file_record.filename)[1]

    # 选择处理器
    if pdf_processor.supports(ext):
        asset = pdf_processor.process(file_record.local_path, file_record.file_id)
    elif office_processor.supports(ext):
        asset = office_processor.process(file_record.local_path, file_record.file_id)
    elif image_processor.supports(ext):
        # 判断是否需要 OCR
        if need_ocr or ocr_processor.should_ocr(user_question=user_question):
            ocr_result = ocr_processor.run_ocr(file_record.local_path)
            asset = image_processor.process(
                file_record.local_path,
                file_record.file_id,
                need_ocr=True,
                ocr_text=ocr_result["text"]
            )
        else:
            asset = image_processor.process(file_record.local_path, file_record.file_id)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    return asset


@app.post("/sessions")
async def create_session():
    """创建新会话"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = SessionRecord(session_id=session_id)
    return {"session_id": session_id, "message": "会话创建成功"}


@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = None
):
    """
    上传文件

    Args:
        file: 上传的文件
        session_id: 会话 ID（可选）

    Returns:
        dict: 文件记录信息
    """
    if not session_id:
        # 自动创建会话
        session_id = str(uuid.uuid4())
        sessions[session_id] = SessionRecord(session_id=session_id)

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 生成文件 ID
    file_id = str(uuid.uuid4())

    # 保存文件
    cache_dir = os.path.join(os.path.dirname(__file__), 'processed_cache')
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{file_id}_{file.filename}")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 创建文件记录
    file_record = FileRecord(
        file_id=file_id,
        session_id=session_id,
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        ext=os.path.splitext(file.filename)[1],
        local_path=file_path,
        size_bytes=len(content)
    )

    file_records[file_id] = file_record
    sessions[session_id].files.append(file_record)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "session_id": session_id,
        "message": "文件上传成功"
    }


@app.post("/messages/analyze")
async def analyze_message(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    分析消息并生成摘要

    流程：
    1. 读取 session 历史
    2. 读取本轮附件
    3. 若附件未预处理，则触发 preprocess
    4. 调用 intent classifier
    5. 选取上下文
    6. 调用 final summarizer
    7. 更新 session short summary
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = sessions[request.session_id]
    summarizer_instance = get_summarizer()

    # 1. 预处理附件
    assets = []
    for file_id in request.file_ids:
        if file_id not in file_records:
            continue

        file_record = file_records[file_id]

        # 如果已预处理，直接使用缓存
        if file_id in document_assets:
            assets.append(document_assets[file_id])
        else:
            # 触发预处理
            asset = preprocess_file(
                file_record,
                need_ocr=False,  # 由意图识别决定
                user_question=request.user_question
            )
            document_assets[file_id] = asset
            assets.append(asset)

    # 2. 意图识别
    available_files = [file_records[fid].filename for fid in request.file_ids if fid in file_records]
    intent_result = summarizer_instance.classify_intent(request.user_question, available_files)

    # 3. 生成单附件摘要
    summaries = []
    for asset in assets:
        if asset.file_id in attachment_summaries:
            summaries.append(attachment_summaries[asset.file_id])
        else:
            # 组合文本内容
            text_content = "\n".join([block.content for block in asset.text_blocks])
            summary = summarizer_instance.summarize_attachment(
                file_type=asset.kind,
                filename=file_records[asset.file_id].filename,
                text_content=text_content
            )
            summary.file_id = asset.file_id
            attachment_summaries[asset.file_id] = summary
            summaries.append(summary)

    # 4. 装配上下文
    context = context_assembler.assemble_context(
        user_question=request.user_question,
        session_summary=session.short_summary,
        attachment_summaries=summaries,
        intent_result=intent_result
    )

    # 5. 生成最终摘要
    final_summary = summarizer_instance.generate_final_summary(
        user_question=request.user_question,
        session_summary=session.short_summary,
        attachment_summaries=summaries
    )

    # 6. 更新会话
    session.short_summary = final_summary
    session.updated_at = session.updated_at.__class__.now()

    return AnalyzeResponse(
        session_id=request.session_id,
        intent=intent_result.intent,
        summary=final_summary,
        attachment_summaries=summaries
    )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = sessions[session_id]
    return {
        "session_id": session.session_id,
        "files": [
            {
                "file_id": f.file_id,
                "filename": f.filename,
                "ext": f.ext
            }
            for f in session.files
        ],
        "short_summary": session.short_summary,
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }
