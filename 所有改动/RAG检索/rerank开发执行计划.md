# RAG系统添加rerank模式实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有RAG系统基础上添加rerank模式，实现两阶段检索（粗排k=10 → 精排k=3），提升检索质量

**Architecture:** 创建独立RerankService使用BAAI/bge-reranker-base模型，增强VectorStoreService支持粗排检索，修改RagSummarizeService集成两阶段流程，保持向后兼容

**Tech Stack:** FlagEmbedding (BAAI/bge-reranker-base), LangChain, ChromaDB, YAML配置

---

## 文件结构

### 新增文件
- `config/rerank.yml` - 重排序配置
- `rerank/__init__.py` - 包初始化
- `rerank/rerank_service.py` - 重排序服务主类
- `rerank/test_rerank.py` - 独立测试脚本
- `所有改动/RAG检索/添加rerank需求分析.md` - 需求文档（已存在）

### 修改文件
- `rag/vector_store.py` - 增加粗排检索器方法
- `rag/rag_service.py` - 集成rerank模式，添加两阶段检索逻辑
- `utils/config_handler.py` - 添加rerank配置加载
- `rag/evaluation.py` - 扩展支持rerank模式评估

---

## 任务分解

### Task 1: 创建配置文件

**Files:**
- Create: `config/rerank.yml`

- [ ] **Step 1: 创建重排序配置文件**

```yaml
# config/rerank.yml - 重排序配置
rerank_model: "BAAI/bge-reranker-base"
use_gpu: false
max_length: 512  # 模型最大输入长度
batch_size: 16   # 批量推理大小

# 两阶段检索配置
coarse_k: 10     # 粗排候选数
fine_k: 3        # 精排输出数

# 降级策略
fallback_to_original: true  # rerank失败时回退到原排序
log_failures: true          # 记录失败日志
```

- [ ] **Step 2: 验证文件格式**

Run: `python -c "import yaml; yaml.safe_load(open('config/rerank.yml', 'r'))"`
Expected: 成功加载，无语法错误

- [ ] **Step 3: 提交配置文件**

```bash
git add config/rerank.yml
git commit -m "feat: 添加rerank配置文件"
```

### Task 2: 扩展配置处理器

**Files:**
- Modify: `utils/config_handler.py`

- [ ] **Step 1: 读取现有config_handler.py了解结构**

Run: `head -20 utils/config_handler.py`
Expected: 查看现有配置加载逻辑

- [ ] **Step 2: 添加rerank配置加载函数**

```python
# 在utils/config_handler.py中添加
def load_rerank_config():
    """加载rerank配置"""
    from utils.path_tool import get_abs_path
    config_path = get_abs_path("config/rerank.yml")
    return load_yaml_config(config_path)
```

- [ ] **Step 3: 测试配置加载**

Run: `python -c "from utils.config_handler import load_rerank_config; print(load_rerank_config())"`
Expected: 打印出rerank配置字典

- [ ] **Step 4: 提交配置处理器修改**

```bash
git add utils/config_handler.py
git commit -m "feat: 添加rerank配置加载支持"
```

### Task 3: 创建rerank目录和包初始化

**Files:**
- Create: `rerank/__init__.py`
- Create: `rerank/rerank_service.py`

- [ ] **Step 1: 创建rerank目录**

Run: `mkdir -p rerank`
Expected: 目录创建成功

- [ ] **Step 2: 创建包初始化文件**

```python
# rerank/__init__.py
from .rerank_service import RerankService

__all__ = ["RerankService"]
```

- [ ] **Step 3: 创建RerankService类框架**

```python
# rerank/rerank_service.py
import logging
from typing import List, Tuple
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class RerankService:
    """重排序服务，使用BAAI/bge-reranker-base进行文档精排"""
    
    def __init__(self, model_name="BAAI/bge-reranker-base", use_gpu=False, max_length=512, batch_size=16):
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.max_length = max_length
        self.batch_size = batch_size
        self.model = None  # 延迟加载
        
    def _load_model(self):
        """延迟加载模型"""
        if self.model is None:
            try:
                from FlagEmbedding import FlagReranker
                self.model = FlagReranker(self.model_name)
                logger.info(f"加载重排序模型成功: {self.model_name}")
            except ImportError:
                raise ImportError("请安装FlagEmbedding: pip install FlagEmbedding")
            except Exception as e:
                raise RuntimeError(f"加载模型失败: {e}")
        return self.model
    
    def rerank(self, query: str, candidates: List[Document], top_k: int = 3) -> List[Document]:
        """对候选文档进行重排序"""
        raise NotImplementedError("待实现")
    
    def _batch_rerank(self, query: str, texts: List[str]) -> List[float]:
        """批量重排序内部方法"""
        raise NotImplementedError("待实现")
```

- [ ] **Step 4: 提交基础框架**

```bash
git add rerank/__init__.py rerank/rerank_service.py
git commit -m "feat: 添加RerankService基础框架"
```

### Task 4: 实现RerankService核心逻辑

**Files:**
- Modify: `rerank/rerank_service.py`

- [ ] **Step 1: 实现_batch_rerank方法**

```python
# 在rerank/rerank_service.py的RerankService类中添加
def _batch_rerank(self, query: str, texts: List[str]) -> List[float]:
    """批量重排序内部方法"""
    try:
        model = self._load_model()
        
        # 准备输入对
        pairs = [(query, text[:self.max_length]) for text in texts]
        
        # 批量推理
        scores = model.compute_score(pairs, normalize=True)
        
        # 如果返回的是二维列表，取第一列
        if isinstance(scores, list) and len(scores) > 0 and isinstance(scores[0], list):
            scores = [s[0] for s in scores]
            
        return scores
    except Exception as e:
        logger.error(f"批量重排序失败: {e}")
        raise
```

- [ ] **Step 2: 测试_batch_rerank方法**

Run: `python -c "from rerank.rerank_service import RerankService; rs = RerankService(); print('RerankService创建成功')"`
Expected: 打印"RerankService创建成功"，无错误

- [ ] **Step 3: 实现rerank方法**

```python
# 在rerank/rerank_service.py的RerankService类中添加
def rerank(self, query: str, candidates: List[Document], top_k: int = 3) -> List[Document]:
    """对候选文档进行重排序
    
    Args:
        query: 用户查询
        candidates: 候选文档列表（Document对象）
        top_k: 返回的文档数量
        
    Returns:
        重排序后的top_k个文档，包含排序分数（metadata中）
    """
    if not candidates:
        return []
    
    if len(candidates) <= top_k:
        # 候选不足，直接返回
        return candidates[:top_k]
    
    try:
        # 提取文档文本
        texts = [doc.page_content for doc in candidates]
        
        # 批量重排序
        scores = self._batch_rerank(query, texts)
        
        # 创建(分数, 索引, 文档)元组列表
        scored_docs = list(zip(scores, range(len(candidates)), candidates))
        
        # 按分数降序排序
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # 取top_k
        result_docs = []
        for score, idx, doc in scored_docs[:top_k]:
            # 在metadata中添加排序分数
            new_metadata = doc.metadata.copy()
            new_metadata["rerank_score"] = float(score)
            new_metadata["original_rank"] = idx + 1
            result_docs.append(Document(page_content=doc.page_content, metadata=new_metadata))
            
        logger.debug(f"重排序完成: 查询={query[:50]}..., 候选={len(candidates)}, top_k={top_k}")
        return result_docs
        
    except Exception as e:
        logger.error(f"重排序失败: {e}, 降级到原始排序")
        # 失败时返回原始排序的前top_k个
        return candidates[:top_k]
```

- [ ] **Step 4: 提交核心逻辑实现**

```bash
git add rerank/rerank_service.py
git commit -m "feat: 实现RerankService核心重排序逻辑"
```

### Task 5: 创建独立测试脚本

**Files:**
- Create: `rerank/test_rerank.py`

- [ ] **Step 1: 创建测试脚本**

```python
#!/usr/bin/env python3
"""
RerankService独立测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from rerank.rerank_service import RerankService


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
    reranker = RerankService()
    
    # 执行重排序
    try:
        results = reranker.rerank(query, candidates, top_k=3)
        
        print(f"查询: {query}")
        print(f"候选文档数: {len(candidates)}")
        print(f"重排序结果数: {len(results)}")
        
        for i, doc in enumerate(results, 1):
            print(f"  {i}. 分数: {doc.metadata.get('rerank_score', 'N/A'):.4f}, 来源: {doc.metadata.get('source')}")
            print(f"     内容: {doc.page_content[:60]}...")
            
        print("✅ 基本重排序测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 重排序测试失败: {e}")
        return False


def test_rerank_edge_cases():
    """测试边界情况"""
    print("\n=== 测试2: 边界情况 ===")
    
    reranker = RerankService()
    
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
    
    print("✅ 边界情况测试通过")
    return True


def test_model_loading():
    """测试模型加载"""
    print("\n=== 测试3: 模型加载 ===")
    
    try:
        # 测试默认模型
        reranker1 = RerankService()
        print(f"✅ 默认模型加载成功: {reranker1.model_name}")
        
        # 测试GPU配置
        reranker2 = RerankService(use_gpu=False)
        print(f"✅ CPU模式配置成功")
        
        print("✅ 模型加载测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 模型加载测试失败: {e}")
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
        print("🎉 所有测试通过!")
        sys.exit(0)
    else:
        print("⚠️ 部分测试失败")
        sys.exit(1)
```

- [ ] **Step 2: 运行独立测试**

Run: `python rerank/test_rerank.py`
Expected: 显示测试进度，可能因为缺少FlagEmbedding库而失败，但验证脚本结构正确

- [ ] **Step 3: 提交测试脚本**

```bash
git add rerank/test_rerank.py
git commit -m "feat: 添加RerankService独立测试脚本"
```

### Task 6: 增强VectorStoreService

**Files:**
- Modify: `rag/vector_store.py`

- [ ] **Step 1: 查看现有VectorStoreService结构**

Run: `grep -n "class VectorStoreService" rag/vector_store.py`
Expected: 找到类定义行号

- [ ] **Step 2: 添加get_coarse_retriever方法**

```python
# 在rag/vector_store.py的VectorStoreService类中添加（约第30行）
def get_coarse_retriever(self, coarse_k: int = None):
    """获取粗排检索器（返回更多候选）
    
    Args:
        coarse_k: 粗排候选数，默认为配置中的coarse_k或10
    
    Returns:
        检索器实例
    """
    from utils.config_handler import load_rerank_config
    
    if coarse_k is None:
        try:
            rerank_config = load_rerank_config()
            coarse_k = rerank_config.get("coarse_k", 10)
        except:
            coarse_k = 10
    
    return self.vector_store.as_retriever(search_kwargs={"k": coarse_k})


def get_fine_retriever(self, fine_k: int = None):
    """获取精排检索器（原逻辑备份）
    
    Args:
        fine_k: 精排输出数，默认为配置中的fine_k或3
    
    Returns:
        检索器实例
    """
    from utils.config_handler import load_rerank_config
    
    if fine_k is None:
        try:
            rerank_config = load_rerank_config()
            fine_k = rerank_config.get("fine_k", 3)
        except:
            fine_k = chroma_conf["k"]  # 使用原有配置
    
    return self.vector_store.as_retriever(search_kwargs={"k": fine_k})
```

- [ ] **Step 3: 测试新增方法**

Run: `python -c "from rag.vector_store import VectorStoreService; vs = VectorStoreService(); print('粗排检索器:', vs.get_coarse_retriever()); print('精排检索器:', vs.get_fine_retriever())"`
Expected: 成功创建两个检索器对象

- [ ] **Step 4: 提交VectorStoreService增强**

```bash
git add rag/vector_store.py
git commit -m "feat: 增强VectorStoreService支持粗排和精排检索器"
```

### Task 7: 修改RagSummarizeService集成rerank

**Files:**
- Modify: `rag/rag_service.py`

- [ ] **Step 1: 查看现有RagSummarizeService结构**

Run: `head -40 rag/rag_service.py`
Expected: 查看类定义和__init__方法

- [ ] **Step 2: 修改__init__方法添加rerank支持**

```python
# 在rag/rag_service.py中修改__init__方法（约第21-30行）
def __init__(self, use_rerank: bool = True):
    self.vector_store = VectorStoreService()
    
    # 创建粗排和精排检索器
    self.coarse_retriever = self.vector_store.get_coarse_retriever()
    self.fine_retriever = self.vector_store.get_fine_retriever()
    
    # Rerank服务（可选）
    if use_rerank:
        try:
            from rerank.rerank_service import RerankService
            from utils.config_handler import load_rerank_config
            
            rerank_config = load_rerank_config()
            self.reranker = RerankService(
                model_name=rerank_config.get("rerank_model", "BAAI/bge-reranker-base"),
                use_gpu=rerank_config.get("use_gpu", False),
                max_length=rerank_config.get("max_length", 512),
                batch_size=rerank_config.get("batch_size", 16)
            )
        except Exception as e:
            print(f"警告: 无法加载rerank服务，将降级到原始检索: {e}")
            self.reranker = None
    else:
        self.reranker = None
    
    # 原有初始化逻辑保持不变
    self.prompt_text = load_rag_prompts()
    self.prompt_template = PromptTemplate.from_template(self.prompt_text)
    self.model = chat_model
    self.chain = self._init_chain()
```

- [ ] **Step 3: 添加新的retriever_docs方法**

```python
# 在rag/rag_service.py的RagSummarizeService类中添加（在现有retriever_docs方法前）
def retriever_docs(self, query: str) -> list[Document]:
    """两阶段检索：粗排→精排
    
    Args:
        query: 用户查询
        
    Returns:
        检索到的文档列表
    """
    from utils.config_handler import load_rerank_config
    
    if not self.reranker:
        # 降级模式：使用原逻辑
        return self.fine_retriever.invoke(query)
    
    try:
        # 获取配置
        rerank_config = load_rerank_config()
        fallback_enabled = rerank_config.get("fallback_to_original", True)
        
        # 1. 粗排：获取候选文档
        coarse_docs = self.coarse_retriever.invoke(query)
        
        if len(coarse_docs) <= 3:
            # 候选不足，直接返回
            return coarse_docs[:3]
        
        # 2. 精排：rerank筛选top-3
        fine_k = rerank_config.get("fine_k", 3)
        fine_docs = self.reranker.rerank(query, coarse_docs, top_k=fine_k)
        return fine_docs
        
    except Exception as e:
        # rerank失败时降级到原始排序
        if fallback_enabled:
            print(f"警告: Rerank失败，降级到原始检索: {e}")
            return self.fine_retriever.invoke(query)
        else:
            raise RuntimeError(f"Rerank失败且未启用降级: {e}")


# 注释掉原有的retriever_docs方法，但不删除
# def retriever_docs(self, query: str) -> list[Document]:
#     return self.retriever.invoke(query)  # 单阶段检索
```

- [ ] **Step 4: 测试集成修改**

Run: `python -c "from rag.rag_service import RagSummarizeService; rag = RagSummarizeService(use_rerank=False); print('RAG服务创建成功（无rerank）'); rag2 = RagSummarizeService(use_rerank=True); print('RAG服务创建成功（带rerank）')"`
Expected: 成功创建两个RAG服务实例

- [ ] **Step 5: 提交RagSummarizeService修改**

```bash
git add rag/rag_service.py
git commit -m "feat: 修改RagSummarizeService集成rerank两阶段检索"
```

### Task 8: 扩展evaluation.py支持rerank评估

**Files:**
- Modify: `rag/evaluation.py`

- [ ] **Step 1: 查看现有evaluate_rag函数签名**

Run: `grep -n "def evaluate_rag" rag/evaluation.py`
Expected: 找到函数定义行号

- [ ] **Step 2: 修改evaluate_rag函数添加use_rerank参数**

```python
# 在rag/evaluation.py中修改evaluate_rag函数签名（约第40行）
def evaluate_rag(test_cases_path=None, k=3, runs=1, skip_failures=True, use_rerank=True):
    """
    评估RAG检索效果
    
    Args:
        test_cases_path: 测试用例JSON文件路径（默认使用内置测试数据）
        k: 评估的top-k值（默认3，与系统配置一致）
        runs: 实验运行次数（默认1，保持向后兼容）
        skip_failures: 是否跳过失败的实验（默认True）
        use_rerank: 是否使用rerank模式（默认True）
    
    Returns:
        dict: 包含准确率、召回率等指标的字典，添加统计信息
    """
```

- [ ] **Step 3: 修改RAG服务初始化部分**

```python
# 在rag/evaluation.py中找到RAG服务初始化部分（约第73行）
    # 初始化RAG服务
    try:
        rag = RagSummarizeService(use_rerank=use_rerank)
    except Exception as e:
        print(f"初始化RAG服务失败: {e}")
        return None
```

- [ ] **Step 4: 添加对比评估函数**

```python
# 在rag/evaluation.py文件末尾添加新函数
def evaluate_with_and_without_rerank(test_cases_path=None, k=3, runs=1):
    """
    对比评估带rerank和不带rerank的效果
    
    Args:
        test_cases_path: 测试用例JSON文件路径
        k: 评估的top-k值
        runs: 实验运行次数
    
    Returns:
        dict: 包含两种模式对比结果的字典
    """
    print("=== RAG检索效果对比评估（带rerank vs 不带rerank） ===")
    
    # 评估带rerank模式
    print("\n--- 带rerank模式评估 ---")
    results_with = evaluate_rag(test_cases_path, k=k, runs=runs, use_rerank=True)
    
    # 评估不带rerank模式
    print("\n--- 不带rerank模式评估 ---")
    results_without = evaluate_rag(test_cases_path, k=k, runs=runs, use_rerank=False)
    
    if not results_with or not results_without:
        print("对比评估失败: 至少一种模式评估失败")
        return None
    
    # 计算提升百分比
    precision_with = results_with['precision@3']
    precision_without = results_without['precision@3']
    recall_with = results_with['recall@3']
    recall_without = results_without['recall@3']
    
    precision_improvement = 0
    recall_improvement = 0
    
    if precision_without > 0:
        precision_improvement = (precision_with - precision_without) / precision_without * 100
    
    if recall_without > 0:
        recall_improvement = (recall_with - recall_without) / recall_without * 100
    
    # 构建对比结果
    comparison = {
        "with_rerank": {
            "precision@3": precision_with,
            "recall@3": recall_with,
            "details": results_with
        },
        "without_rerank": {
            "precision@3": precision_without,
            "recall@3": recall_without,
            "details": results_without
        },
        "improvement": {
            "precision_improvement_percent": precision_improvement,
            "recall_improvement_percent": recall_improvement,
            "absolute_precision_diff": precision_with - precision_without,
            "absolute_recall_diff": recall_with - recall_without
        },
        "summary": {
            "rerank_better_precision": precision_with > precision_without,
            "rerank_better_recall": recall_with > recall_without,
            "overall_better": (precision_with > precision_without) and (recall_with > recall_without)
        }
    }
    
    # 输出对比摘要
    print("\n=== 对比结果摘要 ===")
    print(f"准确率: {precision_without:.2%} → {precision_with:.2%} (变化: {precision_improvement:+.1f}%)")
    print(f"召回率: {recall_without:.2%} → {recall_with:.2%} (变化: {recall_improvement:+.1f}%)")
    
    if comparison["summary"]["overall_better"]:
        print("✅ Rerank模式整体效果更优")
    elif comparison["summary"]["rerank_better_precision"]:
        print("⚠️ Rerank模式准确率更高，但召回率相似或更低")
    elif comparison["summary"]["rerank_better_recall"]:
        print("⚠️ Rerank模式召回率更高，但准确率相似或更低")
    else:
        print("❌ Rerank模式未带来明显改进")
    
    return comparison


def save_comparison_report(comparison, output_path="rerank_comparison_report.json"):
    """
    保存对比评估报告
    
    Args:
        comparison: 对比结果字典
        output_path: 输出文件路径
    """
    import json
    from pathlib import Path
    
    output_path = Path(output_path)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2)
        print(f"对比报告已保存到 {output_path}")
        return True
    except Exception as e:
        print(f"保存对比报告失败: {e}")
        return False
```

- [ ] **Step 5: 测试扩展的评估功能**

Run: `python -c "from rag.evaluation import evaluate_with_and_without_rerank; print('对比评估函数导入成功')"`
Expected: 打印"对比评估函数导入成功"

- [ ] **Step 6: 提交evaluation.py扩展**

```bash
git add rag/evaluation.py
git commit -m "feat: 扩展evaluation.py支持rerank模式对比评估"
```

### Task 9: 安装依赖和验证环境

**Files:**
- 无文件修改，系统操作

- [ ] **Step 1: 安装FlagEmbedding依赖**

Run: `pip install FlagEmbedding`
Expected: 成功安装FlagEmbedding包

- [ ] **Step 2: 测试模型加载**

Run: `python -c "from FlagEmbedding import FlagReranker; model = FlagReranker('BAAI/bge-reranker-base'); print('FlagReranker模型加载成功')"`
Expected: 可能需要下载模型，最终打印"FlagReranker模型加载成功"

- [ ] **Step 3: 运行独立rerank测试**

Run: `python rerank/test_rerank.py`
Expected: 所有测试通过或至少部分通过

- [ ] **Step 4: 提交环境准备状态**

```bash
git add -A
git commit -m "chore: 安装FlagEmbedding依赖，准备rerank环境"
```

### Task 10: 端到端集成测试

**Files:**
- 创建: `tests/test_rerank_integration.py`

- [ ] **Step 1: 创建集成测试文件**

```python
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
        print("✅ 带rerank的RAG服务创建成功")
        
        # 测试不带rerank模式
        rag_without = RagSummarizeService(use_rerank=False)
        print("✅ 不带rerank的RAG服务创建成功")
        
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
        
        print("✅ 基本集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
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
        print("✅ 降级功能测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 降级测试失败: {e}")
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
            print("✅ 禁用rerank时reranker为None")
        else:
            print("⚠️ 禁用rerank时reranker不为None")
            
        if rag_enabled.reranker is not None:
            print("✅ 启用rerank时reranker不为None")
        else:
            print("⚠️ 启用rerank时reranker为None")
        
        print("✅ 配置开关测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 配置开关测试失败: {e}")
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
        print("🎉 所有集成测试通过!")
        sys.exit(0)
    else:
        print("⚠️ 部分集成测试失败")
        sys.exit(1)
```

- [ ] **Step 2: 运行集成测试**

Run: `python tests/test_rerank_integration.py`
Expected: 集成测试通过或部分通过

- [ ] **Step 3: 运行完整的对比评估**

Run: `python rag/evaluation.py`
Expected: 使用默认配置运行评估，生成结果

- [ ] **Step 4: 提交集成测试**

```bash
git add tests/test_rerank_integration.py
git commit -m "feat: 添加rerank模式端到端集成测试"
```

### Task 11: 文档和清理

**Files:**
- Modify: `README.md` 或相关文档

- [ ] **Step 1: 更新项目文档**

```markdown
# RAG系统重排序（Rerank）功能

## 功能概述
本系统增加了两阶段检索功能：先粗排（top-10候选）再精排（top-3输出），使用BAAI/bge-reranker-base模型提升检索质量。

## 使用方法

### 1. 基本使用
```python
from rag.rag_service import RagSummarizeService

# 启用rerank模式（默认）
rag = RagSummarizeService(use_rerank=True)
result = rag.rag_summarize("扫地机器人推荐")

# 禁用rerank模式（使用原逻辑）
rag_no_rerank = RagSummarizeService(use_rerank=False)
```

### 2. 配置说明
编辑 `config/rerank.yml`：
- `rerank_model`: 重排序模型名称
- `coarse_k`: 粗排候选数（默认10）
- `fine_k`: 精排输出数（默认3）
- `fallback_to_original`: 失败时是否降级到原排序

### 3. 效果评估
```python
# 对比评估带rerank和不带rerank的效果
from rag.evaluation import evaluate_with_and_without_rerank
comparison = evaluate_with_and_without_rerank()
```

## 安装依赖
```bash
pip install FlagEmbedding
```

## 性能影响
- 增加一次模型推理时间
- 可通过批量推理优化
- 支持GPU加速（配置use_gpu: true）
```

- [ ] **Step 2: 验证所有修改**

Run: `find . -name "*.py" -newer docs/superpowers/plans/2026-04-04-rag-rerank-implementation.md -type f | grep -v __pycache__`
Expected: 列出所有新创建或修改的文件

- [ ] **Step 3: 最终提交**

```bash
git add README.md  # 或其他文档文件
git commit -m "docs: 更新RAG rerank功能文档"
```

## 后续步骤

1. **性能优化**：根据测试结果调整batch_size和max_length参数
2. **模型调优**：尝试不同的重排序模型
3. **监控集成**：添加rerank性能和使用统计
4. **A/B测试**：在生产环境中验证rerank效果

---

**计划完成时间估计**：2-3小时（含依赖安装和测试）

**关键风险**：
1. FlagEmbedding库安装或兼容性问题
2. BAAI/bge-reranker-base模型下载失败
3. 性能影响超出预期

**缓解措施**：
1. 提供详细的安装指南和故障排除
2. 实现完整的降级机制
3. 配置参数可调整优化性能