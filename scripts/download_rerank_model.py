#!/usr/bin/env python3
"""
下载BAAI/bge-reranker-base模型到本地目录
支持断点续传和镜像源
"""

import os
import sys
import argparse
from pathlib import Path

def setup_environment():
    """设置环境变量"""
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'
    os.environ['HF_HUB_CONNECT_TIMEOUT'] = '60'
    # 注意：下载时需要禁用离线模式
    if 'TRANSFORMERS_OFFLINE' in os.environ:
        del os.environ['TRANSFORMERS_OFFLINE']
    if 'HF_HUB_OFFLINE' in os.environ:
        del os.environ['HF_HUB_OFFLINE']

def download_model(model_id="BAAI/bge-reranker-base", output_dir="models/bge-reranker-base", use_mirror=False):
    """
    下载模型到指定目录

    Args:
        model_id: 模型ID，如 "BAAI/bge-reranker-base"
        output_dir: 输出目录
        use_mirror: 是否使用镜像源
    """
    try:
        from huggingface_hub import snapshot_download

        # 设置镜像源（如果需要）
        if use_mirror:
            # 国内镜像源配置
            os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
            print(f"使用镜像源: {os.environ['HF_ENDPOINT']}")

        # 确保输出目录存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"开始下载模型: {model_id}")
        print(f"目标目录: {output_path.absolute()}")

        # 下载模型
        downloaded_path = snapshot_download(
            repo_id=model_id,
            local_dir=output_path,
            local_dir_use_symlinks=False,  # 不使用符号链接，直接复制文件
            resume_download=True,           # 支持断点续传
            max_workers=4,                  # 并行下载线程数
        )

        print(f"模型下载完成!")
        print(f"保存位置: {downloaded_path}")

        # 验证模型文件
        required_files = ["config.json", "pytorch_model.bin", "tokenizer_config.json", "vocab.txt"]
        missing_files = []

        for file in required_files:
            file_path = output_path / file
            if not file_path.exists():
                # 检查是否有其他可能的名称（如model.safetensors）
                if file == "pytorch_model.bin":
                    # 检查safetensors格式
                    safetensors_path = output_path / "model.safetensors"
                    if safetensors_path.exists():
                        print(f"✓ 找到 safetensors 格式模型文件: {safetensors_path.name}")
                        continue
                missing_files.append(file)

        if missing_files:
            print(f"警告: 以下文件缺失: {missing_files}")
            print("模型可能不完整，但某些功能仍可用")
        else:
            print("✓ 所有必需文件都存在")

        return str(output_path)

    except ImportError:
        print("错误: 需要安装 huggingface_hub 库")
        print("请运行: pip install huggingface_hub")
        return None
    except Exception as e:
        print(f"下载失败: {e}")
        print("\n故障排除建议:")
        print("1. 检查网络连接")
        print("2. 尝试使用镜像源: --use-mirror")
        print("3. 手动下载: https://huggingface.co/BAAI/bge-reranker-base")
        print("4. 将下载的文件复制到: models/bge-reranker-base/")
        return None

def create_model_readme(model_dir):
    """创建README文件说明如何使用本地模型"""
    readme_path = Path(model_dir) / "README.md"
    content = f"""# 本地重排序模型

## 模型信息
- 名称: BAAI/bge-reranker-base
- 下载时间: import datetime; datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
- 用途: RAG文档重排序

## 使用方法

### 1. 配置本地路径
在 `config/rerank.yml` 中设置:

```yaml
rerank_model: "BAAI/bge-reranker-base"
model_path: "{model_dir}"  # 使用本地路径
cache_dir: null
```

### 2. 测试模型加载
```bash
KMP_DUPLICATE_LIB_OK=TRUE python -c "from FlagEmbedding import FlagReranker; model = FlagReranker('{model_dir}'); print('本地模型加载成功')"
```

### 3. 运行测试
```bash
KMP_DUPLICATE_LIB_OK=TRUE python rerank/test_rerank.py
```

## 文件清单
"""
    try:
        import datetime
        content = content.replace("import datetime; datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')",
                                 datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 添加文件列表
        model_path = Path(model_dir)
        if model_path.exists():
            with open(readme_path, 'a', encoding='utf-8') as f:
                for file in sorted(model_path.iterdir()):
                    size = file.stat().st_size / (1024*1024)  # MB
                    f.write(f"- {file.name} ({size:.2f} MB)\n")

        print(f"✓ 创建说明文件: {readme_path}")
    except Exception as e:
        print(f"创建说明文件失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="下载重排序模型")
    parser.add_argument("--model", default="BAAI/bge-reranker-base",
                       help="模型ID (默认: BAAI/bge-reranker-base)")
    parser.add_argument("--output", default="models/bge-reranker-base",
                       help="输出目录 (默认: models/bge-reranker-base)")
    parser.add_argument("--use-mirror", action="store_true",
                       help="使用国内镜像源 (hf-mirror.com)")
    parser.add_argument("--skip-readme", action="store_true",
                       help="跳过创建README文件")

    args = parser.parse_args()

    print("=" * 60)
    print("重排序模型下载工具")
    print("=" * 60)

    # 设置环境
    setup_environment()

    # 下载模型
    model_path = download_model(args.model, args.output, args.use_mirror)

    if model_path:
        # 创建README文件
        if not args.skip_readme:
            create_model_readme(model_path)

        print("\n" + "=" * 60)
        print("下一步:")
        print("1. 更新配置文件 config/rerank.yml:")
        print(f"   model_path: \"{model_path}\"")
        print("2. 重新运行测试:")
        print("   KMP_DUPLICATE_LIB_OK=TRUE python rerank/test_rerank.py")
        print("3. 如需离线使用，重新启用离线模式:")
        print("   set TRANSFORMERS_OFFLINE=1")
        print("   set HF_HUB_OFFLINE=1")
        print("=" * 60)

        # 验证模型是否可以加载
        print("\n验证模型加载...")
        try:
            os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
            # 临时禁用离线模式以加载本地模型
            if 'TRANSFORMERS_OFFLINE' in os.environ:
                del os.environ['TRANSFORMERS_OFFLINE']
            if 'HF_HUB_OFFLINE' in os.environ:
                del os.environ['HF_HUB_OFFLINE']

            from FlagEmbedding import FlagReranker
            model = FlagReranker(model_path)
            print("✓ 本地模型验证通过")
        except Exception as e:
            print(f"✗ 模型验证失败: {e}")
            print("  模型文件可能不完整，但重排序服务可能仍能降级运行")

    return 0 if model_path else 1

if __name__ == "__main__":
    sys.exit(main())