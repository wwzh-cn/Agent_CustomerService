# RAG系统添加rerank模式需求分析

## 项目背景

现有RAG系统采用单阶段向量检索策略：用户查询通过向量相似度检索返回top-3个文档直接用于生成回答。根据实验评估结果，系统在53个测试用例上表现出：

- **平均准确率@3**: 74.21% (优秀)
- **平均召回率@3**: 38.97% (需要改进)

当前检索流程存在**召回率瓶颈**，需要通过两阶段检索（粗排+精排）提升检索质量。

## 需求目标

### 核心目标
在现有RAG系统基础上添加rerank模式，实现两阶段检索流程：
1. **粗排阶段**: 扩大召回范围（top-10候选）
2. **精排阶段**: 精准排序筛选（top-3输出）

### 具体需求
1. **功能需求**:
   - 保持原有RAG系统接口不变，向后兼容
   - 添加rerank开关，支持灵活切换
   - 新增精排模块，使用交叉编码器模型
   - 两阶段检索：粗排k=10 → 精排k=3

2. **质量需求**:
   - 提升检索召回率，保持或提升准确率
   - 系统性能影响控制在可接受范围
   - 提供降级策略，rerank失败时回退到原始排序
   - 良好的可配置性和可维护性

3. **非功能需求**:
   - 个人项目，聚焦核心功能实现
   - 先独立测试再集成
   - 保留原有逻辑（注释而非删除）
   - 按功能组织文件结构

## 技术选型

### 重排序模型
- **模型**: BAAI/bge-reranker-base
- **理由**: 智源研究院专门优化的中文重排序模型，针对中文场景效果好
- **替代方案**: cross-encoder/ms-marco-MiniLM-L-6-v2 (备用)

### 开发策略
- **独立模块开发**: 先创建独立rerank测试模块
- **渐进式集成**: 验证效果后集成到主系统
- **配置驱动**: 通过配置文件控制行为

## 系统架构设计

### 整体流程
```
原流程: 查询 → 向量检索(k=3) → 生成回答
新流程: 查询 → 粗排检索(k=10) → rerank精排(k=3) → 生成回答
```

### 组件关系图
```
┌─────────────────────────────────────────────┐
│             RagSummarizeService             │
├─────────────────────────────────────────────┤
│  - vector_store: VectorStoreService        │
│  - coarse_retriever (k=10)                │
│  - fine_retriever (k=3, 备份)             │
│  - reranker: RerankService (可选)         │
└─────────────────────────────────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐    ┌────────────────┐
│ VectorStore  │    │  RerankService │
│   Service    │    │                │
├──────────────┤    ├────────────────┤
│ - get_retriever│  │ - rerank()    │
│ - get_coarse_ │  │ - 降级策略     │
└──────────────┘    └────────────────┘
```

## 详细设计

### 1. RerankService (rerank/rerank_service.py)
```python
class RerankService:
    """重排序服务，使用BAAI/bge-reranker-base进行文档精排"""
    
    def __init__(self, model_name="BAAI/bge-reranker-base", use_gpu=False):
        self.model = self._load_model(model_name, use_gpu)
        self.max_length = 512  # 模型最大输入长度
        self.batch_size = 16   # 批量推理大小
    
    def rerank(self, query: str, candidates: List[Document], top_k: int = 3) -> List[Document]:
        """
        对候选文档进行重排序
        
        Args:
            query: 用户查询
            candidates: 候选文档列表（Document对象）
            top_k: 返回的文档数量
            
        Returns:
            重排序后的top_k个文档，包含排序分数（metadata中）
        """
        # 1. 准备输入对: (query, document_content)
        # 2. 批量推理获取分数
        # 3. 按分数排序，返回top_k
        # 4. 异常处理：失败时返回原始排序的top_k
```

**特性：**
- 批量推理优化性能
- 长文档截断处理
- 分数记录在metadata中（用于调试）
- 完整的异常处理和降级机制

### 2. VectorStoreService增强 (rag/vector_store.py)
```python
class VectorStoreService:
    def get_retriever(self, k: Optional[int] = None):
        """获取检索器，支持动态k值（保持向后兼容）"""
        if k is None:
            k = chroma_conf["k"]  # 默认3
        return self.vector_store.as_retriever(search_kwargs={"k": k})
    
    def get_coarse_retriever(self, coarse_k: int = 10):
        """获取粗排检索器（返回更多候选）"""
        return self.vector_store.as_retriever(search_kwargs={"k": coarse_k})
```

### 3. RagSummarizeService集成 (rag/rag_service.py)
```python
class RagSummarizeService:
    def __init__(self, use_rerank: bool = True):
        self.vector_store = VectorStoreService()
        self.coarse_retriever = self.vector_store.get_coarse_retriever(coarse_k=10)
        self.fine_retriever = self.vector_store.get_retriever(k=3)  # 原逻辑备份
        
        # Rerank服务（可选）
        if use_rerank:
            self.reranker = RerankService()
        else:
            self.reranker = None
        
        # 原有初始化逻辑保持不变...
    
    def retriever_docs(self, query: str) -> list[Document]:
        """两阶段检索：粗排→精排"""
        if not self.reranker:
            # 降级模式：使用原逻辑（注释而非删除）
            # return self.fine_retriever.invoke(query)
            return self.fine_retriever.invoke(query)
        
        try:
            # 1. 粗排：获取top-10候选
            coarse_docs = self.coarse_retriever.invoke(query)
            
            if len(coarse_docs) <= 3:
                # 候选不足，直接返回
                return coarse_docs[:3]
            
            # 2. 精排：rerank筛选top-3
            fine_docs = self.reranker.rerank(query, coarse_docs, top_k=3)
            return fine_docs
            
        except Exception as e:
            # rerank失败时降级到原始排序
            logger.warning(f"Rerank失败，降级到原始检索: {e}")
            return self.fine_retriever.invoke(query)
```

**原有逻辑处理：**
```python
# 原retriever_docs方法注释掉，但不删除
# def retriever_docs(self, query: str) -> list[Document]:
#     return self.retriever.invoke(query)  # 单阶段检索
```

### 4. 配置系统

**新增 config/rerank.yml:**
```yaml
# 重排序配置
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

**utils/config_handler.py扩展：**
```python
# 添加rerank配置加载
def load_rerank_config():
    """加载rerank配置"""
    config_path = os.path.join(BASE_DIR, "config", "rerank.yml")
    return load_yaml_config(config_path)
```

## 文件结构

```
项目根目录/
├── config/
│   ├── chroma.yml          # 原有配置
│   ├── rag.yml             # 原有配置  
│   └── rerank.yml          # 新增：重排序配置
├── rag/
│   ├── rag_service.py      # 修改：集成rerank
│   ├── vector_store.py     # 修改：增强检索器
│   └── rerank_service.py   # 新增：重排序服务
├── rerank/                 # 新增：重排序模块目录
│   ├── __init__.py
│   ├── rerank_service.py   # 主服务类
│   └── test_rerank.py      # 独立测试脚本
├── agent/skills/
│   └── rag.py              # 可能修改：透传配置
└── 所有改动/RAG检索/
    └── 添加rerank需求分析.md  # 本文档
```

## 测试计划

### 阶段一：独立模块测试
1. **RerankService单元测试**
   - 测试模型加载和推理
   - 测试批量处理能力
   - 测试异常处理和降级
   - 验证排序效果

2. **性能基准测试**
   - 单次推理耗时
   - 批量推理吞吐量
   - 内存占用分析

### 阶段二：集成测试
1. **端到端功能测试**
   - 对比rerank开启/关闭的结果差异
   - 验证两阶段检索流程
   - 测试降级策略生效

2. **效果评估**
   - 使用现有53个测试用例
   - 对比准确率/召回率变化
   - 分析排序质量提升

### 阶段三：回归测试
1. **向后兼容性**
   - 关闭rerank时行为与原有系统一致
   - API接口保持不变
   - 原有功能不受影响

### 阶段四：评估脚本改进 (evaluation.py)
现有的`rag/evaluation.py`需要扩展以支持rerank模式测试：

1. **双模式评估功能**
   - 支持`use_rerank=True/False`参数控制rerank开关
   - 同时评估带rerank和不带rerank的两种模式
   - 输出对比结果，显示rerank带来的提升

2. **增强的评估指标**
   - 保持原有准确率/召回率计算
   - 新增排序质量指标：NDCG@k, MRR
   - 记录rerank推理时间，评估性能影响
   - 统计降级触发频率和原因

3. **详细的对比报告**
   - 生成HTML或Markdown格式的对比报告
   - 可视化准确率/召回率提升趋势
   - 按查询类型分析rerank效果差异
   - 提供具体的改进建议

4. **代码改进要点**
   ```python
   # 在evaluate_rag函数中添加use_rerank参数
   def evaluate_rag(test_cases_path=None, k=3, runs=1, skip_failures=True, use_rerank=True):
       # 初始化RAG服务时传入use_rerank参数
       rag = RagSummarizeService(use_rerank=use_rerank)
       
   # 添加对比评估函数
   def evaluate_with_and_without_rerank(test_cases_path, k=3):
       # 分别运行带rerank和不带rerank的评估
       results_with = evaluate_rag(test_cases_path, k=k, use_rerank=True)
       results_without = evaluate_rag(test_cases_path, k=k, use_rerank=False)
       
       # 计算提升百分比
       precision_improvement = (results_with['precision@3'] - results_without['precision@3']) / results_without['precision@3']
       recall_improvement = (results_with['recall@3'] - results_without['recall@3']) / results_without['recall@3']
   ```

## 实施步骤

### 第1步：环境准备
1. 安装依赖：`pip install FlagEmbedding`
2. 下载模型：BAAI/bge-reranker-base
3. 创建配置目录结构

### 第2步：独立模块开发
1. 创建`rerank/`目录和`rerank_service.py`
2. 实现RerankService核心逻辑
3. 编写`test_rerank.py`测试脚本
4. 验证模块功能

### 第3步：系统集成
1. 修改`rag/vector_store.py`增加粗排检索器
2. 修改`rag/rag_service.py`集成rerank
3. 创建`config/rerank.yml`配置文件
4. 更新`utils/config_handler.py`

### 第4步：测试验证
1. 运行独立模块测试
2. 执行端到端集成测试
3. 对比性能指标
4. 评估效果提升

### 第5步：文档和清理
1. 更新项目文档
2. 确保原有逻辑正确注释
3. 整理代码结构
4. 提交版本控制

## 风险与缓解

### 技术风险
1. **模型性能问题**
   - 风险：rerank推理耗时过长影响用户体验
   - 缓解：批量推理优化，配置GPU加速，设置超时降级

2. **模型效果不达预期**
   - 风险：rerank未提升检索质量
   - 缓解：保留降级开关，A/B测试验证效果

3. **依赖问题**
   - 风险：FlagEmbedding库兼容性问题
   - 缓解：pin版本，提供安装指南，测试环境验证

### 项目风险
1. **范围蔓延**
   - 风险：过度设计，偏离核心需求
   - 缓解：聚焦两阶段检索核心，YAGNI原则

2. **集成复杂度**
   - 风险：修改影响现有稳定功能
   - 缓解：渐进式集成，充分测试，降级保证

## 成功标准

### 技术标准
1. ✅ 实现两阶段检索流程（粗排k=10 → 精排k=3）
2. ✅ 保持原有系统接口和功能不变
3. ✅ rerank模块独立可测试
4. ✅ 完整的异常处理和降级策略
5. ✅ 配置驱动，易于调整参数

### 效果标准
1. ⬆️ 召回率提升（目标：从38.97%提升至50%+）
2. ↔️ 准确率保持或小幅提升
3. ⏱️ 系统响应时间增加控制在30%以内
4. 🧪 通过所有回归测试

### 项目标准
1. 📁 清晰的代码组织和文件结构
2. 📝 完整的文档和注释
3. 🔧 灵活的配置选项
4. 🧪 全面的测试覆盖

## 附录

### 相关文件参考
1. [所有改动/RAG检索/RAG检索流程对比](所有改动/RAG检索/RAG检索流程对比) - 原检索流程
2. [所有改动/RAG检索/实验结果.md](所有改动/RAG检索/实验结果.md) - 当前效果评估
3. [rag/rag_service.py](rag/rag_service.py) - 现有RAG服务
4. [config/chroma.yml](config/chroma.yml) - 向量库配置

### 技术参考
1. **BAAI/bge-reranker-base**: https://huggingface.co/BAAI/bge-reranker-base
2. **FlagEmbedding库**: https://github.com/FlagOpen/FlagEmbedding
3. **Rerank技术原理**: 交叉编码器(Cross-Encoder) vs 双编码器(Bi-Encoder)

---
*文档版本: 1.0*
*创建日期: 2026-04-04*
*最后更新: 2026-04-04*