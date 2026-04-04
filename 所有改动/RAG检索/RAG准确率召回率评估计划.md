# RAG检索准确率与召回率评估执行计划

## 评估目标
量化当前RAG系统的检索效果，聚焦两个核心指标：
- **准确率（Precision@k）**：前k个检索结果中相关文档的比例
- **召回率（Recall@k）**：前k个检索结果覆盖全部相关文档的比例

默认设置 k=3（与当前配置 `chroma.yml` 中的 `k: 3` 一致）

## 执行流程

### 阶段一：构建测试数据集（手动标注，约30分钟）
1. **选择测试问题**（10个典型样例）：
   - 从 `data/` 文档中提取真实用户可能提出的问题
   - 示例：
     - "小户型适合哪些扫地机器人？"
     - "扫地机器人的续航时间多久合适？"
     - "如何选择扫地机器人的吸力？"
     - "带宠物家庭应该选什么类型的扫地机器人？"

2. **标注相关文档片段**（ground truth）：
   - 人工阅读文档，为每个问题标注**真正相关**的文档段落
   - 记录文件名和行号范围
   - 每个问题标注1-3个相关片段

3. **保存测试集格式**（JSON）：
```json
[
  {
    "query": "小户型适合哪些扫地机器人",
    "relevant_chunks": [
      "选购指南.txt第1-3行",
      "扫地机器人100问.txt第15-20行"
    ],
    "relevant_keywords": ["小户型", "轻便", "机身高度", "续航"]
  }
]
```

### 阶段二：实现评估脚本（约30分钟）

在 `rag/evaluation.py` 中创建评估模块：

```python
"""
RAG检索效果评估模块
专注于计算准确率（Precision）和召回率（Recall）
"""

import json
from rag.rag_service import RagSummarizeService


def count_relevant(retrieved_chunks, relevant_keywords):
    """
    简化版相关性判断：检查检索片段是否包含关键词
    实际应用中可使用更复杂的语义匹配
    """
    count = 0
    for chunk in retrieved_chunks:
        for keyword in relevant_keywords:
            if keyword in chunk:
                count += 1
                break  # 只要匹配一个关键词就算相关
    return count


def evaluate_rag(test_cases_path="test_rag_cases.json", k=3):
    """
    评估RAG检索效果
    
    Args:
        test_cases_path: 测试用例JSON文件路径
        k: 评估的top-k值（默认3，与系统配置一致）
    
    Returns:
        dict: 包含准确率、召回率等指标的字典
    """
    # 加载测试用例
    with open(test_cases_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)
    
    # 初始化RAG服务
    rag = RagSummarizeService()
    
    total_precision = 0
    total_recall = 0
    case_results = []
    
    print(f"开始评估RAG检索效果 (k={k})，共{len(test_cases)}个测试用例")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        query = case["query"]
        relevant_keywords = case.get("relevant_keywords", [])
        
        # 获取检索结果（仅检索阶段，不生成回答）
        try:
            docs = rag.retriever_docs(query)
            retrieved_chunks = [doc.page_content[:200] for doc in docs[:k]]  # 取前k个
            
            # 计算相关文档数
            relevant_retrieved = count_relevant(retrieved_chunks, relevant_keywords)
            total_relevant = len(relevant_keywords)  # 简化：关键词数量作为相关文档总数
            
            # 计算指标
            precision = relevant_retrieved / k if k > 0 else 0
            recall = relevant_retrieved / total_relevant if total_relevant > 0 else 0
            
            total_precision += precision
            total_recall += recall
            
            case_results.append({
                "query": query,
                "precision": precision,
                "recall": recall,
                "retrieved_count": len(retrieved_chunks)
            })
            
            print(f"用例{i}: '{query}'")
            print(f"  检索到{len(retrieved_chunks)}个片段，相关{relevant_retrieved}个")
            print(f"  准确率: {precision:.2%}, 召回率: {recall:.2%}")
            
        except Exception as e:
            print(f"用例{i}执行失败: {e}")
            continue
    
    # 计算平均指标
    avg_precision = total_precision / len(case_results) if case_results else 0
    avg_recall = total_recall / len(case_results) if case_results else 0
    
    print("=" * 60)
    print(f"评估完成！")
    print(f"平均准确率@3: {avg_precision:.2%}")
    print(f"平均召回率@3: {avg_recall:.2%}")
    
    return {
        "precision@3": avg_precision,
        "recall@3": avg_recall,
        "total_cases": len(test_cases),
        "successful_cases": len(case_results),
        "case_details": case_results
    }


if __name__ == "__main__":
    # 默认测试文件路径
    test_file = "data/test_rag_cases.json"  # 需要先创建测试文件
    results = evaluate_rag(test_file)
    
    # 保存评估结果
    with open("rag_evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("评估结果已保存到 rag_evaluation_results.json")
```

### 阶段三：执行评估与结果分析（约15分钟）

1. **准备测试文件**：
   - 将标注好的测试用例保存为 `data/test_rag_cases.json`
   - 确保文件格式正确

2. **运行评估**：
```bash
cd d:\code\zhisaotong-Agent-master
python rag/evaluation.py
```

3. **预期输出示例**：
```
开始评估RAG检索效果 (k=3)，共10个测试用例
============================================================
用例1: '小户型适合哪些扫地机器人'
  检索到3个片段，相关2个
  准确率: 66.67%, 召回率: 66.67%
...
============================================================
评估完成！
平均准确率@3: 73.33%
平均召回率@3: 68.89%
评估结果已保存到 rag_evaluation_results.json
```

4. **结果解读标准**：
   - **优秀**：准确率/召回率 > 80%
   - **良好**：准确率/召回率 60%-80%
   - **需要改进**：准确率/召回率 < 60%

## 简化假设与局限性

1. **相关性判断简化**：使用关键词匹配代替语义相似度计算
2. **测试集规模小**：仅10个样例，适合快速验证
3. **仅评估检索阶段**：不评估生成回答的质量
4. **关键词依赖**：需要人工标注相关关键词

## 后续扩展建议

如需更精确评估，可考虑：
1. 增加测试用例数量（20-50个）
2. 使用语义相似度模型（如BERT）进行相关性判断
3. 增加更多指标：MRR、NDCG@k、Hit Rate@k
4. 对比不同k值（k=1,3,5）的效果
5. 与BM25等传统检索方法进行基线对比

## 时间预估
- 总耗时：约1-1.5小时
- 阶段一（标注）：30分钟
- 阶段二（编码）：30分钟  
- 阶段三（执行）：15分钟
- 分析优化：15分钟（可选）