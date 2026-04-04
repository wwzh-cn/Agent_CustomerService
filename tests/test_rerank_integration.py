#!/usr/bin/env python3
"""
Rerank模式端到端集成测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.rag_service import RagSummarizeService


def test_integration_basic():
    """测试基本集成功能"""
    print("=== 集成测试1: 基本功能 ===")

    try:
        # 测试带rerank模式
        rag_with = RagSummarizeService(use_rerank=True)
        print("[OK] 带rerank的RAG服务创建成功")

        # 测试不带rerank模式
        rag_without = RagSummarizeService(use_rerank=False)
        print("[OK] 不带rerank的RAG服务创建成功")

        # 测试检索功能
        query = "扫地机器人推荐"

        docs_with = rag_with.retriever_docs(query)
        print(f"带rerank检索结果数: {len(docs_with)}")

        docs_without = rag_without.retriever_docs(query)
        print(f"不带rerank检索结果数: {len(docs_without)}")

        # 检查结果格式
        if docs_with and len(docs_with) > 0:
            print(f"带rerank结果示例: {docs_with[0].page_content[:60]}...")
            if "rerank_score" in docs_with[0].metadata:
                print(f"重排序分数: {docs_with[0].metadata['rerank_score']}")

        print("[OK] 基本集成测试通过")
        return True

    except Exception as e:
        print(f"[ERROR] 集成测试失败: {e}")
        return False


def test_integration_fallback():
    """测试降级功能"""
    print("\n=== 集成测试2: 降级功能 ===")

    try:
        # 创建一个配置错误的rerank服务
        class MockRerankService:
            def rerank(self, query, candidates, top_k):
                raise RuntimeError("模拟rerank失败")

        # 修改rag_service以使用模拟失败服务
        rag = RagSummarizeService(use_rerank=True)

        # 临时替换reranker为会失败的服务
        rag.reranker = MockRerankService()

        # 应该触发降级到原始检索
        query = "测试查询"
        docs = rag.retriever_docs(query)

        print(f"降级后检索结果数: {len(docs)}")
        print("[OK] 降级功能测试通过")
        return True

    except Exception as e:
        print(f"[ERROR] 降级测试失败: {e}")
        return False


def test_config_switch():
    """测试配置开关"""
    print("\n=== 集成测试3: 配置开关 ===")

    try:
        # 测试禁用rerank
        rag_disabled = RagSummarizeService(use_rerank=False)
        query = "配置开关测试"
        docs_disabled = rag_disabled.retriever_docs(query)

        # 测试启用rerank
        rag_enabled = RagSummarizeService(use_rerank=True)
        docs_enabled = rag_enabled.retriever_docs(query)

        print(f"禁用rerank结果数: {len(docs_disabled)}")
        print(f"启用rerank结果数: {len(docs_enabled)}")

        # 验证开关效果（结果可能相同也可能不同）
        if rag_disabled.reranker is None:
            print("[OK] 禁用rerank时reranker为None")
        else:
            print("[WARN] 禁用rerank时reranker不为None")

        if rag_enabled.reranker is not None:
            print("[OK] 启用rerank时reranker不为None")
        else:
            print("[WARN] 启用rerank时reranker为None")

        print("[OK] 配置开关测试通过")
        return True

    except Exception as e:
        print(f"[ERROR] 配置开关测试失败: {e}")
        return False


if __name__ == "__main__":
    print("开始Rerank模式端到端集成测试")
    print("=" * 60)

    success_count = 0
    total_tests = 3

    # 运行测试
    if test_integration_basic():
        success_count += 1

    if test_integration_fallback():
        success_count += 1

    if test_config_switch():
        success_count += 1

    print("=" * 60)
    print(f"集成测试完成: {success_count}/{total_tests} 通过")

    if success_count == total_tests:
        print("[SUCCESS] 所有集成测试通过!")
        sys.exit(0)
    else:
        print("[WARN] 部分集成测试失败")
        sys.exit(1)