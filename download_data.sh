#!/bin/bash
# 从 OSS 下载对话数据
# 使用方法: bash download_data.sh

set -e

OSS_BUCKET="oss://quark-llm/datasets/tuyongsiqi.tysq/data-excel-0328"
DATA_FILE="downloaded_conversations.tar.gz"
TARGET_DIR="."

echo "========================================="
echo "从 OSS 下载对话数据"
echo "========================================="

# 检查 ossutil 是否已安装
if ! command -v ossutil &> /dev/null; then
    echo "错误: ossutil 未安装，请先安装 ossutil"
    echo "安装命令: curl -o /tmp/ossutil https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64 && chmod +x /tmp/ossutil && sudo mv /tmp/ossutil /usr/local/bin/ossutil"
    exit 1
fi

# 检查 OSS 配置
echo "检查 OSS 连接..."
if ! ossutil ls "$OSS_BUCKET" > /dev/null 2>&1; then
    echo "错误: 无法连接到 OSS，请检查 ossutil 配置"
    echo "配置命令: ossutil config -e http://oss-cn-zhangjiakou.aliyuncs.com -i <your-access-key-id> -k <your-access-key-secret>"
    exit 1
fi

# 检查文件是否存在
echo "检查数据文件是否存在..."
if ! ossutil ls "$OSS_BUCKET/$DATA_FILE" > /dev/null 2>&1; then
    echo "错误: OSS 中不存在文件 $DATA_FILE"
    echo "请确认文件已上传到: $OSS_BUCKET/$DATA_FILE"
    exit 1
fi

# 下载文件
echo "开始下载 $DATA_FILE ..."
ossutil cp "$OSS_BUCKET/$DATA_FILE" "$TARGET_DIR/$DATA_FILE"

echo "========================================="
echo "下载完成!"
echo "文件位置: $TARGET_DIR/$DATA_FILE"
echo "========================================="

# 询问是否解压
read -p "是否立即解压文件? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "解压文件..."
    tar -xzf "$DATA_FILE"
    echo "解压完成!"
fi
