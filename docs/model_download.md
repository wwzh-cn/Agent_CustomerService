# 重排序模型下载与配置指南

## 概述

本指南说明如何下载和配置BAAI/bge-reranker-base模型，以启用RAG系统的文档重排序功能。

## 背景

FlagEmbedding库需要BAAI/bge-reranker-base模型进行语义重排序。由于网络限制，模型可能无法自动下载。本指南提供多种下载和配置方案。

## 方案一：使用下载脚本（推荐）

### 1. 确保网络连接
暂时禁用离线模式，确保可以访问HuggingFace或镜像源。

### 2. 运行下载脚本
```bash
# 临时禁用离线模式
set TRANSFORMERS_OFFLINE=0
set HF_HUB_OFFLINE=0

# 运行下载脚本
python scripts/download_rerank_model.py

# 或使用镜像源（国内用户）
python scripts/download_rerank_model.py --use-mirror

# 指定自定义目录
python scripts/download_rerank_model.py --output "models/my-reranker"
```

### 3. 重新启用离线模式
```bash
set TRANSFORMERS_OFFLINE=1
set HF_HUB_OFFLINE=1
```

## 方案二：手动下载

### 1. 访问模型页面
打开 https://huggingface.co/BAAI/bge-reranker-base

### 2. 下载必要文件
下载以下文件到本地目录（如 `models/bge-reranker-base/`）:
- `config.json`
- `pytorch_model.bin` 或 `model.safetensors`
- `tokenizer_config.json`
- `vocab.txt`
- `special_tokens_map.json`
- `tokenizer.json`

### 3. 目录结构
```
models/
└── bge-reranker-base/
    ├── config.json
    ├── pytorch_model.bin
    ├── tokenizer_config.json
    ├── vocab.txt
    └── ...
```

## 方案三：使用现有缓存

如果其他项目已经下载过该模型，可以复用缓存：

### 1. 查找缓存位置
```bash
# Windows
echo %USERPROFILE%\.cache\huggingface\hub

# Linux/Mac
echo ~/.cache/huggingface/hub
```

### 2. 查找模型目录
在缓存目录中查找包含 `bge-reranker-base` 的文件夹。

### 3. 配置缓存目录
在 `config/rerank.yml` 中设置：
```yaml
rerank_model: "BAAI/bge-reranker-base"
cache_dir: "C:/Users/用户名/.cache/huggingface/hub"
# 或使用相对路径
# cache_dir: "~/.cache/huggingface/hub"
```

## 配置本地模型路径

### 1. 更新配置文件
编辑 `config/rerank.yml`：

```yaml
# 使用本地路径（优先）
rerank_model: "BAAI/bge-reranker-base"
model_path: "models/bge-reranker-base"  # 本地模型路径
cache_dir: null
use_gpu: false
max_length: 512
batch_size: 16
```

### 2. 验证配置
```bash
# 测试模型加载（临时禁用离线模式）
set TRANSFORMERS_OFFLINE=0
set HF_HUB_OFFLINE=0
KMP_DUPLICATE_LIB_OK=TRUE python -c "from FlagEmbedding import FlagReranker; model = FlagReranker('models/bge-reranker-base'); print('本地模型加载成功')"

# 重新启用离线模式
set TRANSFORMERS_OFFLINE=1
set HF_HUB_OFFLINE=1
```

### 3. 运行测试
```bash
KMP_DUPLICATE_LIB_OK=TRUE python rerank/test_rerank.py
```

## 故障排除

### 1. 模型加载失败
**症状**: "We couldn't connect to 'https://huggingface.co' to load this file"

**解决方案**:
- 确保模型文件已下载完整
- 检查 `model_path` 配置是否正确
- 验证文件权限

### 2. OpenMP冲突
**症状**: "OMP: Error #15: Initializing libiomp5md.dll"

**解决方案**:
```bash
# 设置环境变量
set KMP_DUPLICATE_LIB_OK=TRUE

# 或在Python代码中添加
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
```

### 3. Transformers版本不兼容
**症状**: "cannot import name 'is_torch_fx_available'"

**解决方案**:
```bash
# 降级transformers版本
pip install transformers==4.45.0
```

### 4. 网络连接问题
**解决方案**:
- 使用镜像源：`--use-mirror` 参数
- 手动下载模型文件
- 配置代理（如果需要）

## 离线使用配置

一旦模型下载完成，可以永久启用离线模式：

### 1. 环境变量配置
在运行脚本前设置：
```bash
# Windows
set KMP_DUPLICATE_LIB_OK=TRUE
set TRANSFORMERS_OFFLINE=1
set HF_HUB_OFFLINE=1

# Linux/Mac
export KMP_DUPLICATE_LIB_OK=TRUE
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
```

### 2. Python代码配置
在Python文件开头添加：
```python
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
# os.environ['TRANSFORMERS_OFFLINE'] = '1'
# os.environ['HF_HUB_OFFLINE'] = '1'
```

## 验证安装

### 1. 验证模型加载
```bash
KMP_DUPLICATE_LIB_OK=TRUE python scripts/verify_model.py
```

### 2. 运行完整测试套件
```bash
# 独立测试
KMP_DUPLICATE_LIB_OK=TRUE python rerank/test_rerank.py

# 集成测试
KMP_DUPLICATE_LIB_OK=TRUE python tests/test_rerank_integration.py

# RAG评估测试
KMP_DUPLICATE_LIB_OK=TRUE python rag/evaluation.py
```

## 模型信息

- **名称**: BAAI/bge-reranker-base
- **类型**: 双语重排序模型
- **大小**: 约110MB
- **语言**: 中英文
- **用途**: 文档重排序，提高RAG检索准确率

## 性能预期

- **在线模式**: 完整重排序功能，显著提升检索质量
- **离线模式（无模型）**: 降级到原始检索，功能可用但无重排序
- **离线模式（有模型）**: 完整重排序功能，最佳体验

## 更新日志

- 2026-04-04: 添加本地模型路径支持，创建下载工具
- 2026-04-04: 修复transformers兼容性问题，降级到4.45.0
- 2026-04-04: 添加OpenMP冲突解决方案