#!/usr/bin/env python3
"""
测试RAG检索功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.rag_service import RagSummarizeService

def main():
    print("=== 测试RAG检索 ===")

    # 创建RAG服务实例
    rag = RagSummarizeService()

    # 测试查询
    test_queries = [
        "小户型适合哪些扫地机器人",
        "扫地机器人的续航时间多久合适",
        "如何选择扫地机器人的吸力"
    ]

    for query in test_queries:
        print(f"\n查询: '{query}'")
        try:
            # 调用retriever_docs
            docs = rag.retriever_docs(query)
            print(f"  检索到 {len(docs)} 个文档")

            for i, doc in enumerate(docs[:3]):  # 最多显示3个
                print(f"  文档{i+1}:")
                print(f"    内容: {doc.page_content[:100]}...")
                print(f"    元数据: {doc.metadata}")

            # 也测试完整的rag_summarize
            response = rag.rag_summarize(query)
            print(f"  完整回答: {response[:100]}...")

        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()