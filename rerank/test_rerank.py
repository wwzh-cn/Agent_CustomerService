#!/usr/bin/env python3
"""
RerankService独立测试脚本
"""

import sys
import os

# 设置环境变量必须在导入任何包之前
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from rerank.rerank_service import RerankService
from utils.config_handler import load_rerank_config


def test_rerank_basic():
    """测试基本重排序功能"""
    print("=== 测试1: 基本重排序功能 ===")

    # 创建测试数据
    query = "扫地机器人推荐"
    candidates = [
        Document(page_content="这款扫地机器人吸力强大，适合大户型家庭", metadata={"source": "doc1"}),
        Document(page_content="轻便型扫地机器人，机身高度仅8cm，适合小户型", metadata={"source": "doc2"}),
        Document(page_content="智能扫地机器人支持APP控制，可定时清扫", metadata={"source": "doc3"}),
        Document(page_content="扫拖一体机器人，可同时完成扫地和拖地", metadata={"source": "doc4"}),
        Document(page_content="宠物家庭专用扫地机器人，毛发清理效果好", metadata={"source": "doc5"}),
    ]

    # 创建rerank服务
    rerank_config = load_rerank_config()
    reranker = RerankService(
        model_name=rerank_config.get("rerank_model", "BAAI/bge-reranker-base"),
        model_path=rerank_config.get("model_path"),
        use_gpu=rerank_config.get("use_gpu", False),
        max_length=rerank_config.get("max_length", 512),
        batch_size=rerank_config.get("batch_size", 16)
    )

    # 执行重排序
    try:
        results = reranker.rerank(query, candidates, top_k=3)

        print(f"查询: {query}")
        print(f"候选文档数: {len(candidates)}")
        print(f"重排序结果数: {len(results)}")

        for i, doc in enumerate(results, 1):
            score = doc.metadata.get('rerank_score', 'N/A')
            score_str = f"{score:.4f}" if score != 'N/A' else score
            print(f"  {i}. 分数: {score_str}, 来源: {doc.metadata.get('source')}")
            print(f"     内容: {doc.page_content[:60]}...")

        print("[OK] 基本重排序测试通过")
        return True

    except Exception as e:
        print(f"[ERROR] 重排序测试失败: {e}")
        return False


def test_rerank_edge_cases():
    """测试边界情况"""
    print("\n=== 测试2: 边界情况 ===")

    rerank_config = load_rerank_config()
    reranker = RerankService(
        model_name=rerank_config.get("rerank_model", "BAAI/bge-reranker-base"),
        model_path=rerank_config.get("model_path"),
        use_gpu=rerank_config.get("use_gpu", False),
        max_length=rerank_config.get("max_length", 512),
        batch_size=rerank_config.get("batch_size", 16)
    )

    # 测试1: 空候选列表
    empty_results = reranker.rerank("测试", [], top_k=3)
    print(f"空候选列表: 返回{len(empty_results)}个文档 (预期: 0)")

    # 测试2: 候选不足top_k
    single_doc = [Document(page_content="只有一个文档", metadata={"source": "single"})]
    single_results = reranker.rerank("测试", single_doc, top_k=3)
    print(f"候选不足top_k: 返回{len(single_results)}个文档 (预期: 1)")

    # 测试3: 完全相同的文档
    same_docs = [
        Document(page_content="相同内容", metadata={"source": "same1"}),
        Document(page_content="相同内容", metadata={"source": "same2"}),
    ]
    same_results = reranker.rerank("测试", same_docs, top_k=2)
    print(f"相同文档: 返回{len(same_results)}个文档 (预期: 2)")

    print("[OK] 边界情况测试通过")
    return True


def test_model_loading():
    """测试模型加载"""
    print("\n=== 测试3: 模型加载 ===")

    try:
        rerank_config = load_rerank_config()

        # 测试默认模型
        reranker1 = RerankService(
            model_name=rerank_config.get("rerank_model", "BAAI/bge-reranker-base"),
            model_path=rerank_config.get("model_path"),
            use_gpu=rerank_config.get("use_gpu", False),
            max_length=rerank_config.get("max_length", 512),
            batch_size=rerank_config.get("batch_size", 16)
        )
        print(f"[OK] 默认模型加载成功: {reranker1.model_name}")

        # 测试GPU配置
        reranker2 = RerankService(
            model_name=rerank_config.get("rerank_model", "BAAI/bge-reranker-base"),
            model_path=rerank_config.get("model_path"),
            use_gpu=False,
            max_length=rerank_config.get("max_length", 512),
            batch_size=rerank_config.get("batch_size", 16)
        )
        print(f"[OK] CPU模式配置成功")

        print("[OK] 模型加载测试通过")
        return True

    except Exception as e:
        print(f"[ERROR] 模型加载测试失败: {e}")
        return False


if __name__ == "__main__":
    print("开始RerankService独立测试")
    print("=" * 60)

    success_count = 0
    total_tests = 3

    # 运行测试
    if test_model_loading():
        success_count += 1

    if test_rerank_basic():
        success_count += 1

    if test_rerank_edge_cases():
        success_count += 1

    print("=" * 60)
    print(f"测试完成: {success_count}/{total_tests} 通过")

    if success_count == total_tests:
        print("[SUCCESS] 所有测试通过!")
        sys.exit(0)
    else:
        print("[WARN] 部分测试失败")
        sys.exit(1)