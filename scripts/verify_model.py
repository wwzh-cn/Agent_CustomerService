#!/usr/bin/env python3
"""
验证重排序模型是否可用
检查模型加载、配置文件和环境设置
"""

import os
import sys
from pathlib import Path

def setup_environment():
    """设置环境变量"""
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    # 临时禁用离线模式以允许网络检查
    if 'TRANSFORMERS_OFFLINE' in os.environ:
        del os.environ['TRANSFORMERS_OFFLINE']
    if 'HF_HUB_OFFLINE' in os.environ:
        del os.environ['HF_HUB_OFFLINE']

def check_transformers_version():
    """检查transformers版本"""
    try:
        import transformers
        version = transformers.__version__
        from packaging import version as packaging_version

        required = packaging_version.parse("4.44.2")
        current = packaging_version.parse(version)

        if current >= required:
            return True, f"✓ transformers版本满足要求: {version} (>=4.44.2)"
        else:
            return False, f"✗ transformers版本过低: {version} < 4.44.2"
    except ImportError:
        return False, "✗ 未安装transformers"
    except Exception as e:
        return False, f"✗ 检查transformers版本时出错: {e}"

def check_flagembedding():
    """检查FlagEmbedding是否可用"""
    try:
        from FlagEmbedding import FlagReranker
        return True, "✓ FlagEmbedding库可用"
    except ImportError:
        return False, "✗ 未安装FlagEmbedding，请运行: pip install FlagEmbedding"
    except Exception as e:
        return False, f"✗ FlagEmbedding导入错误: {e}"

def check_config_file():
    """检查配置文件"""
    config_path = Path("config/rerank.yml")
    if not config_path.exists():
        return False, f"✗ 配置文件不存在: {config_path}"

    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        info = []
        if config.get('model_path'):
            model_path = Path(config['model_path'])
            if model_path.exists():
                info.append(f"✓ 本地模型路径配置: {config['model_path']}")

                # 检查模型文件
                required_files = ['config.json', 'pytorch_model.bin', 'tokenizer_config.json']
                missing = []
                for file in required_files:
                    file_path = model_path / file
                    if not file_path.exists():
                        # 检查safetensors格式
                        if file == 'pytorch_model.bin':
                            safetensors_path = model_path / 'model.safetensors'
                            if safetensors_path.exists():
                                continue
                        missing.append(file)

                if missing:
                    info.append(f"⚠ 模型文件缺失: {missing}")
                else:
                    info.append("✓ 模型文件完整")
            else:
                info.append(f"⚠ 本地模型路径不存在: {config['model_path']}")
        else:
            info.append("ℹ 使用远程模型: " + config.get('rerank_model', '未指定'))

        return True, "\n".join([f"✓ 配置文件有效: {config_path}"] + info)
    except Exception as e:
        return False, f"✗ 配置文件错误: {e}"

def test_model_loading(model_path=None):
    """测试模型加载"""
    try:
        from FlagEmbedding import FlagReranker

        if model_path:
            # 测试本地模型
            model = FlagReranker(model_path)
            return True, f"✓ 本地模型加载成功: {model_path}"
        else:
            # 测试默认模型（需要网络）
            try:
                model = FlagReranker("BAAI/bge-reranker-base")
                return True, "✓ 远程模型加载成功（需要网络）"
            except Exception as e:
                return False, f"✗ 远程模型加载失败: {e}\n   可能原因: 网络问题或模型未缓存"
    except Exception as e:
        return False, f"✗ 模型加载失败: {e}"

def check_rerank_service():
    """检查RerankService"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from rerank.rerank_service import RerankService

        # 测试创建实例
        service = RerankService()
        return True, "✓ RerankService创建成功"
    except Exception as e:
        return False, f"✗ RerankService错误: {e}"

def check_rag_integration():
    """检查RAG集成"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from rag.rag_service import RagSummarizeService

        # 测试创建实例（不带rerank）
        rag_without = RagSummarizeService(use_rerank=False)

        # 测试创建实例（带rerank）
        try:
            rag_with = RagSummarizeService(use_rerank=True)
            return True, "✓ RAG服务集成成功（带/不带rerank）"
        except Exception as e:
            return True, f"✓ RAG基础服务可用，rerank服务降级中: {e}"
    except Exception as e:
        return False, f"✗ RAG集成错误: {e}"

def main():
    print("=" * 60)
    print("重排序模型验证工具")
    print("=" * 60)

    # 设置环境
    setup_environment()

    checks = []

    # 运行检查
    print("\n[1] 检查transformers版本...")
    ok, msg = check_transformers_version()
    checks.append(("Transformers版本", ok))
    print(f"   {msg}")

    print("\n[2] 检查FlagEmbedding库...")
    ok, msg = check_flagembedding()
    checks.append(("FlagEmbedding库", ok))
    print(f"   {msg}")

    print("\n[3] 检查配置文件...")
    ok, msg = check_config_file()
    checks.append(("配置文件", ok))
    print(f"   {msg}")

    # 读取配置以获取模型路径
    model_path = None
    try:
        import yaml
        with open('config/rerank.yml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if config.get('model_path'):
                model_path = config['model_path']
    except:
        pass

    print("\n[4] 测试模型加载...")
    ok, msg = test_model_loading(model_path)
    checks.append(("模型加载", ok))
    print(f"   {msg}")

    print("\n[5] 检查RerankService...")
    ok, msg = check_rerank_service()
    checks.append(("RerankService", ok))
    print(f"   {msg}")

    print("\n[6] 检查RAG集成...")
    ok, msg = check_rag_integration()
    checks.append(("RAG集成", ok))
    print(f"   {msg}")

    print("\n" + "=" * 60)
    print("验证结果摘要:")
    print("=" * 60)

    all_ok = True
    for name, ok in checks:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"{name}: {status}")
        if not ok:
            all_ok = False

    print("\n" + "=" * 60)

    if all_ok:
        print("✅ 所有检查通过！重排序功能已就绪。")

        # 提供后续步骤
        print("\n下一步:")
        print("1. 运行独立测试: python rerank/test_rerank.py")
        print("2. 运行集成测试: python tests/test_rerank_integration.py")
        print("3. 运行RAG评估: python rag/evaluation.py")

        if model_path:
            print(f"\n当前使用本地模型: {model_path}")
            print("如需切换为远程模型，请清空config/rerank.yml中的model_path设置")
        else:
            print("\n当前使用远程模型，需要网络连接")
            print("如需离线使用，请下载模型并设置model_path")
    else:
        print("❌ 部分检查失败，需要修复问题。")

        # 提供修复建议
        print("\n常见问题解决方案:")
        print("1. Transformers版本不兼容: pip install transformers==4.45.0")
        print("2. 缺少FlagEmbedding: pip install FlagEmbedding")
        print("3. 模型未下载: 运行 scripts/download_rerank_model.py")
        print("4. 配置文件错误: 检查 config/rerank.yml 格式")
        print("\n详细指南请参考: docs/model_download.md")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())