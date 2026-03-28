# 多模态对话摘要系统 (Conversation Summarizer)

基于大模型的多模态对话摘要生成系统，支持解析多轮对话记录（含图片、PDF、Office 文档附件），一次性传入 LLM 生成整体摘要。

## 目录

- [环境要求](#环境要求)
- [数据获取](#数据获取)
- [快速开始（本机）](#快速开始本机)
- [API 后端配置](#api-后端配置)
  - [模式一：云端 API](#模式一云端-api)
  - [模式二：本地 vLLM 部署](#模式二本地-vllm-部署)
- [迁移到新服务器](#迁移到新服务器)
- [vLLM 部署指南](#vllm-部署指南)
- [大规模批量 Summary](#大规模批量-summary)
- [项目结构](#项目结构)

---

## 数据获取

### 从 OSS 下载对话数据

对话数据已上传到 OSS，使用以下脚本下载：

```bash
# 1. 安装 ossutil（如果未安装）
curl -o /tmp/ossutil https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64
chmod +x /tmp/ossutil
sudo mv /tmp/ossutil /usr/local/bin/ossutil

# 2. 配置 OSS 凭证
ossutil config -e http://oss-cn-zhangjiakou.aliyuncs.com -i <your-access-key-id> -k <your-access-key-secret>

# 3. 下载数据
bash download_data.sh
```

**OSS 配置信息：**
- **Endpoint**: `http://oss-cn-zhangjiakou.aliyuncs.com`
- **Region**: `cn-zhangjiakou`
- **数据路径**: `oss://quark-llm/datasets/tuyongsiqi.tysq/data-excel-0328/`

**手动下载命令：**
```bash
ossutil cp oss://quark-llm/datasets/tuyongsiqi.tysq/data-excel-0328/downloaded_conversations.tar.gz .
tar -xzf downloaded_conversations.tar.gz
```

> **注意**：数据文件较大（约 2GB），请确保有足够的磁盘空间。

---

## 环境要求

- **Python** >= 3.10
- **uv**（推荐）或 pip
- **GPU 服务器**（vLLM 部署时需要，推荐 A100/H100/L40S）

---

## 快速开始（本机）

### 1. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 创建环境并安装依赖

```bash
cd conversation_summarizer

# 创建虚拟环境
uv venv
source .venv/bin/activate

# 安装项目依赖
uv pip install -e .

# 如需开发/测试依赖
uv pip install -e ".[dev]"
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API 配置（见下方说明）
```

### 4. 运行测试

```bash
python conversation_summarizer/test_sample_conversations.py
```

### 5. 启动 API 服务

```bash
uv run python -m conversation_summarizer.main
# 服务启动在 http://0.0.0.0:8000
# Swagger 文档：http://localhost:8000/docs
```

---

## API 后端配置

本系统支持两种 LLM 后端模式，通过环境变量切换，**无需修改代码**。

### 模式一：云端 API

使用阿里内部 LLM API 或其他云端 API 服务。

**.env 配置：**

```bash
# 云端 API 配置
LLM_API_BASE=https://llm-chat-api.alibaba-inc.com/v1/api/chat
LLM_MODEL=gpt-5.4-0305-global
LLM_ACCESS_KEY=efc8c9ca4ac5b0dd4018bcd3a83d767d
LLM_QUOTA_ID=00da3781-1f9d-4a63-857e-7c045c460290
LLM_USER_ID=345245
LLM_TAG=conversation_summarizer
```

**请求格式（自定义格式）：**

```bash
curl -X POST "https://llm-chat-api.alibaba-inc.com/v1/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.4-0305-global",
    "prompt": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
    "params": {"max_tokens": 1024, "temperature": 0.9},
    "app": "llm_application",
    "quota_id": "00da3781-1f9d-4a63-857e-7c045c460290",
    "user_id": "345245",
    "access_key": "efc8c9ca4ac5b0dd4018bcd3a83d767d",
    "tag": "conversation_summarizer"
  }'
```

### 模式二：本地 vLLM 部署

使用 GPU 服务器上通过 vLLM 部署的本地模型。

> **重要**：vLLM 提供的是 **OpenAI 兼容 API**，请求格式与云端 API 不同。
> 切换到 vLLM 时需要设置 `LLM_API_MODE=vllm`，系统会自动使用 OpenAI 兼容格式。

**.env 配置：**

```bash
# vLLM 本地部署配置
LLM_API_MODE=vllm
LLM_API_BASE=http://<GPU_SERVER_IP>:8000/v1/chat/completions
LLM_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
LLM_ACCESS_KEY=not-needed

# 以下字段在 vLLM 模式下不需要
# LLM_QUOTA_ID=
# LLM_USER_ID=
# LLM_TAG=
```

**vLLM OpenAI 兼容请求格式：**

```bash
curl -X POST "http://<GPU_SERVER_IP>:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-VL-72B-Instruct",
    "messages": [
      {"role": "system", "content": "你是一个对话摘要助手"},
      {"role": "user", "content": [
        {"type": "text", "text": "请总结这段对话"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
      ]}
    ],
    "max_tokens": 1024,
    "temperature": 0.3
  }'
```

---

## 迁移到新服务器

### 步骤一：在 GPU 服务器上部署 vLLM

```bash
# 1. 安装 vLLM
pip install vllm

# 2. 下载模型（以 Qwen2.5-VL-72B 为例）
# 方式 A：从 HuggingFace 下载
huggingface-cli download Qwen/Qwen2.5-VL-72B-Instruct --local-dir /data/models/Qwen2.5-VL-72B-Instruct

# 方式 B：从 ModelScope 下载（国内推荐）
pip install modelscope
modelscope download --model Qwen/Qwen2.5-VL-72B-Instruct --local_dir /data/models/Qwen2.5-VL-72B-Instruct

# 3. 启动 vLLM 服务
python -m vllm.entrypoints.openai.api_server \
  --model /data/models/Qwen2.5-VL-72B-Instruct \
  --served-model-name Qwen/Qwen2.5-VL-72B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 4 \
  --max-model-len 32768 \
  --trust-remote-code \
  --dtype auto \
  --gpu-memory-utilization 0.9
```

> **GPU 显存参考**：
> - Qwen2.5-VL-7B：1×A100 (80GB)
> - Qwen2.5-VL-72B：4×A100 (80GB) 或 2×H100
> - Qwen2.5-VL-3B：1×L40S (48GB)

### 步骤二：验证 vLLM 服务

```bash
# 检查模型列表
curl http://<GPU_SERVER_IP>:8000/v1/models | python -m json.tool

# 测试对话
curl -X POST "http://<GPU_SERVER_IP>:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-VL-72B-Instruct",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 100
  }'
```

### 步骤三：在应用服务器上部署 Summarizer

```bash
# 1. 克隆项目
git clone <repo_url>
cd conversation_summarizer

# 2. 安装 uv 和依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv && source .venv/bin/activate
uv pip install -e .

# 3. 配置环境变量（指向 GPU 服务器的 vLLM）
cat > .env << 'EOF'
LLM_API_MODE=vllm
LLM_API_BASE=http://<GPU_SERVER_IP>:8000/v1/chat/completions
LLM_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
LLM_ACCESS_KEY=not-needed
HOST=0.0.0.0
PORT=8080
EOF

# 4. 测试连通性
python conversation_summarizer/test_sample_conversations.py

# 5. 启动服务
uv run python -m conversation_summarizer.main
```

### 步骤四：（可选）使用 systemd 管理服务

```bash
sudo tee /etc/systemd/system/conversation-summarizer.service << 'EOF'
[Unit]
Description=Conversation Summarizer
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/conversation_summarizer
Environment=PATH=/opt/conversation_summarizer/.venv/bin:/usr/bin
EnvironmentFile=/opt/conversation_summarizer/.env
ExecStart=/opt/conversation_summarizer/.venv/bin/uvicorn \
  conversation_summarizer.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now conversation-summarizer
sudo systemctl status conversation-summarizer
```

---

## vLLM 部署指南

### 推荐模型

| 模型 | 参数量 | 多模态 | 最低 GPU | 推荐场景 |
|------|--------|--------|----------|----------|
| Qwen2.5-VL-3B-Instruct | 3B | ✅ | 1×L40S | 轻量测试 |
| Qwen2.5-VL-7B-Instruct | 7B | ✅ | 1×A100 | 中等规模 |
| Qwen2.5-VL-72B-Instruct | 72B | ✅ | 4×A100 | **生产推荐** |
| Qwen3-235B-A22B | 235B | ❌ | 8×H100 | 纯文本高质量 |

### vLLM 启动参数说明

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /data/models/Qwen2.5-VL-72B-Instruct \  # 模型路径
  --served-model-name Qwen/Qwen2.5-VL-72B-Instruct \  # API 中的模型名
  --host 0.0.0.0 \                                     # 监听地址
  --port 8000 \                                         # 监听端口
  --tensor-parallel-size 4 \                            # 张量并行 GPU 数
  --max-model-len 32768 \                               # 最大上下文长度
  --trust-remote-code \                                 # 信任远程代码
  --dtype auto \                                        # 数据类型（auto/float16/bfloat16）
  --gpu-memory-utilization 0.9 \                        # GPU 显存利用率
  --max-num-seqs 32 \                                   # 最大并发请求数
  --enable-prefix-caching                               # 启用前缀缓存（提升吞吐）
```

### 多模态图片支持

vLLM 支持在 `messages` 中传入 base64 编码的图片：

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "请描述这张图片"},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}
  ]
}
```

> **注意**：图片会占用大量 token，建议：
> - 单张图片压缩到 1MB 以内
> - 每次请求最多传入 3-5 张图片
> - 设置 `--max-model-len 32768` 以支持长上下文

### 使用 Docker 部署 vLLM

```bash
docker run --gpus all \
  -v /data/models:/models \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model /models/Qwen2.5-VL-72B-Instruct \
  --served-model-name Qwen/Qwen2.5-VL-72B-Instruct \
  --tensor-parallel-size 4 \
  --max-model-len 32768 \
  --trust-remote-code
```

---

## 大规模批量 Summary

对于全量对话记录的批量摘要任务：

### 并发批量处理

```python
import asyncio
from pathlib import Path
from conversation_summarizer.test_sample_conversations import (
    parse_conversation,
    build_summary_prompt,
)
from conversation_summarizer.summarizer import Summarizer

async def batch_summarize(data_dir: str, max_concurrency: int = 5):
    """批量处理对话记录，控制并发数"""
    summarizer = Summarizer(
        api_key="not-needed",
        api_base="http://<GPU_SERVER_IP>:8000/v1/chat/completions",
        model="Qwen/Qwen2.5-VL-72B-Instruct",
    )

    semaphore = asyncio.Semaphore(max_concurrency)
    conversation_dirs = sorted(Path(data_dir).iterdir())

    async def process_one(conv_dir):
        async with semaphore:
            md_path = conv_dir / "conversation.md"
            if not md_path.exists():
                return None
            parsed = parse_conversation(str(md_path))
            prompt, _ = build_summary_prompt(parsed, str(conv_dir))
            summary = await asyncio.to_thread(
                summarizer._call_llm, prompt, max_tokens=512, temperature=0.3
            )
            return {"dir": conv_dir.name, "summary": summary}

    tasks = [process_one(d) for d in conversation_dirs if d.is_dir()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if r and not isinstance(r, Exception)]

# 运行
results = asyncio.run(batch_summarize("/path/to/conversations", max_concurrency=10))
```

### 性能参考

| 配置 | 并发数 | 吞吐量 | 说明 |
|------|--------|--------|------|
| 云端 API | 5-10 | ~20 req/min | 受 API 限流 |
| vLLM 4×A100 (72B) | 10-20 | ~60 req/min | 本地无限流 |
| vLLM 1×A100 (7B) | 20-50 | ~200 req/min | 轻量模型高吞吐 |

---

## 项目结构

```
conversation_summarizer/
├── __init__.py                    # 包初始化
├── api.py                         # FastAPI 接口定义
├── context_assembler.py           # 上下文装配器
├── main.py                        # 服务入口
├── models.py                      # 数据模型定义
├── summarizer.py                  # 核心：LLM 调用和摘要生成
├── test_sample_conversations.py   # 测试脚本
├── test_summarizer.py             # 单元测试
├── pyproject.toml                 # uv/pip 依赖管理
├── .env.example                   # 环境变量模板
└── README.md                      # 本文档
```

### 关键文件说明

- **`summarizer.py`**：核心模块，包含 `_call_llm()` 方法，负责构建请求并调用 LLM API
- **`test_sample_conversations.py`**：完整的端到端测试，解析 conversation.md → 构建多模态 prompt → 调用 LLM → 记录结果
- **`.env`**：所有 API 配置通过环境变量管理，切换后端只需修改此文件

---

## 常见问题

### Q: 切换到 vLLM 后需要改代码吗？

需要在 `summarizer.py` 的 `_call_llm` 方法中添加 vLLM 模式支持。当 `LLM_API_MODE=vllm` 时，使用 OpenAI 兼容格式发送请求：

```python
# vLLM 模式：OpenAI 兼容格式
payload = {
    "model": self.model,
    "messages": prompt,  # 直接使用 messages 字段
    "max_tokens": max_tokens,
    "temperature": temperature,
}

# 云端 API 模式：自定义格式
payload = {
    "model": self.model,
    "prompt": prompt,  # 使用 prompt 字段
    "params": {"max_tokens": max_tokens, "temperature": temperature},
    "app": "llm_application",
    "access_key": self.api_key,
    ...
}
```

### Q: vLLM 支持多模态图片吗？

支持。vLLM 对 Qwen2.5-VL 系列模型支持 base64 图片输入，格式与 OpenAI Vision API 一致。

### Q: 如何监控 vLLM 服务状态？

```bash
# 查看 GPU 使用
nvidia-smi

# 查看 vLLM 指标
curl http://<GPU_SERVER_IP>:8000/metrics

# 查看已加载模型
curl http://<GPU_SERVER_IP>:8000/v1/models
```
