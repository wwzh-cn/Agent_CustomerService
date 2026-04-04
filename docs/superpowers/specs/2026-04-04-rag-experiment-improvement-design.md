---
name: rag-experiment-improvement
description: 改进RAG实验评估方法，支持多次运行取平均值以减少随机性影响
type: project
---

# RAG实验改进设计文档

## 背景

智扫通机器人智能客服项目已经实现了RAG检索效果的评估模块（`rag/evaluation.py`），能够计算准确率（Precision@3）和召回率（Recall@3）。然而，由于大模型具有随机性，单次实验结果可能存在波动，仅凭一次实验指标不够准确。

## 目标

1. **提高实验可靠性**：通过多次运行实验取平均值，减少随机性对评估结果的影响
2. **保持向后兼容**：现有评估代码继续正常工作，不破坏现有功能
3. **最小化修改**：在现有代码基础上最小化改动，降低风险
4. **支持统计信息**：提供平均值、标准差等基本统计指标

## 需求澄清

通过问答确认的需求：

1. **随机性来源**：主要来自大模型生成阶段，但当前实验仅评估检索阶段
2. **评估范围**：先改进检索阶段的评估，暂不考虑生成阶段
3. **运行方式**：顺序运行三次实验
4. **输出格式**：只保存最终统计（平均值），不保存每次实验详细结果
5. **错误处理**：跳过失败实验，基于成功实验计算统计

## 设计方案

选择**方案一：最小化修改**，在现有 `evaluate_rag()` 函数基础上添加多实验支持。

### 函数签名修改

```python
def evaluate_rag(test_cases_path=None, k=3, runs=1, skip_failures=True):
    """
    评估RAG检索效果
    
    Args:
        test_cases_path: 测试用例JSON文件路径（默认使用内置测试数据）
        k: 评估的top-k值（默认3，与系统配置一致）
        runs: 实验运行次数（默认1，保持向后兼容）
        skip_failures: 是否跳过失败的实验（默认True）
    
    Returns:
        dict: 包含准确率、召回率等指标的字典，添加统计信息
    """
```

**关键设计决策**：
- `runs=1`：默认值保持向后兼容，现有调用代码无需修改
- `skip_failures=True`：默认跳过失败实验，避免单次失败导致整个评估失败

### 内部循环逻辑

```python
# 初始化收集列表
all_precisions = []
all_recalls = []
successful_runs = 0

for run in range(runs):
    try:
        # 运行单次评估（重用现有逻辑）
        # 收集本次实验的 precision, recall
        all_precisions.append(precision)
        all_recalls.append(recall)
        successful_runs += 1
        
        # 显示进度
        print(f"✓ 完成实验 {run+1}/{runs}，准确率: {precision:.2%}, 召回率: {recall:.2%}")
        
    except Exception as e:
        if skip_failures:
            print(f"⚠ 实验 {run+1}/{runs} 失败: {e}，跳过...")
            continue
        else:
            raise
```

### 统计计算

使用Python标准库计算基本统计指标：

```python
if successful_runs > 0:
    # 计算平均值
    precision_mean = sum(all_precisions) / successful_runs
    recall_mean = sum(all_recalls) / successful_runs
    
    # 计算标准差（需要时再计算）
    if successful_runs > 1:
        import math
        precision_std = math.sqrt(sum((x - precision_mean)**2 for x in all_precisions) / (successful_runs - 1))
        recall_std = math.sqrt(sum((x - recall_mean)**2 for x in all_recalls) / (successful_runs - 1))
    else:
        precision_std = 0
        recall_std = 0
    
    # 计算最小值和最大值
    precision_min = min(all_precisions)
    precision_max = max(all_precisions)
    recall_min = min(all_recalls)
    recall_max = max(all_recalls)
```

### 输出格式

保持向后兼容的输出结构，添加统计字段：

```json
{
  "precision@3": 0.833,           // 平均值（保持原有字段名）
  "recall@3": 0.429,              // 平均值（保持原有字段名）
  "statistics": {                 // 新增：详细统计
    "precision@3": {
      "mean": 0.833,
      "std": 0.05,
      "min": 0.78,
      "max": 0.89,
      "range": 0.11
    },
    "recall@3": {
      "mean": 0.429,
      "std": 0.08,
      "min": 0.35,
      "max": 0.52,
      "range": 0.17
    },
    "runs": {
      "requested": 3,
      "successful": 3,
      "failed": 0
    }
  },
  "total_cases": 10,              // 原有字段
  "successful_cases": 10,         // 原有字段
  "case_details": [...],          // 最后一次运行的详细结果（可选）
  "config": {
    "k": 3,
    "runs": 3,
    "skip_failures": true,
    "test_data_path": "..."
  }
}
```

**关键设计决策**：
1. 顶级字段 `precision@3` 和 `recall@3` 保持为平均值，确保与现有代码兼容
2. 新增 `statistics` 字段包含详细统计信息
3. `case_details` 可选保留最后一次运行结果，用于调试和分析
4. `config` 字段扩展，包含实验配置信息

### 错误处理

1. **实验失败处理**：
   - 当 `skip_failures=True` 时，记录失败信息并继续
   - 当 `skip_failures=False` 时，抛出异常终止评估

2. **全部失败处理**：
   - 如果所有实验都失败，返回 `None` 并显示错误信息
   - 记录每个失败实验的原因

3. **部分成功处理**：
   - 只要有成功实验，就基于成功实验计算统计
   - 在 `statistics.runs` 中记录成功和失败数量

### 兼容性保证

1. **参数兼容**：
   - 现有调用 `evaluate_rag(test_file)` 继续工作（`runs=1`）
   - 现有调用 `evaluate_rag(test_file, k=3)` 继续工作

2. **输出兼容**：
   - 现有代码依赖 `precision@3` 和 `recall@3` 字段，这两个字段保持为平均值
   - 新增字段不影响现有解析逻辑

3. **功能兼容**：
   - 单次实验（`runs=1`）的行为与原来完全一致
   - 错误处理行为与原来一致（默认跳过失败）

### 性能考虑

1. **顺序执行**：避免并行执行可能导致的资源竞争和状态混乱
2. **内存优化**：默认不保留每次运行的详细结果（`case_details`）
3. **进度提示**：显示运行进度，提高用户体验
4. **时间预估**：三次实验时间约为单次的三倍，在可接受范围内

## 实施计划

### 修改文件
- `rag/evaluation.py`：主要修改 `evaluate_rag()` 函数

### 具体修改内容
1. 在函数签名中添加 `runs=1` 和 `skip_failures=True` 参数
2. 提取单次评估的核心逻辑（可选重构为内部函数）
3. 添加循环运行多次实验
4. 实现统计计算逻辑
5. 更新输出格式，添加统计信息
6. 更新文档字符串和错误处理

### 测试验证
1. **功能测试**：
   - 运行 `runs=1`，验证行为与原来一致
   - 运行 `runs=3`，验证三次实验执行
   - 验证统计计算正确性
   
2. **兼容性测试**：
   - 现有测试用例（如果有）继续通过
   - 输出格式保持兼容

3. **错误处理测试**：
   - 测试 `skip_failures=True` 时的跳过行为
   - 测试 `skip_failures=False` 时的异常抛出

### 风险评估与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 破坏现有功能 | 低 | 高 | 保持 `runs=1` 默认值，确保向后兼容 |
| 性能下降 | 中 | 中 | 顺序执行，不引入并行复杂性 |
| 统计计算错误 | 低 | 中 | 使用Python标准库，避免复杂统计 |
| 输出格式不兼容 | 低 | 高 | 保持核心字段不变，新增可选字段 |

## 后续扩展建议

如果需要更复杂的实验支持，未来可考虑：

1. **并行执行**：使用多进程并行运行实验，减少总时间
2. **更多统计指标**：添加置信区间、p值等统计指标
3. **结果可视化**：生成统计图表，直观展示结果分布
4. **实验配置持久化**：保存实验配置，便于重复实验
5. **生成阶段评估**：扩展支持生成回答质量的评估

## 时间预估

- **设计**：已完成（当前文档）
- **实现**：1-2小时（包括代码修改和基本测试）
- **验证**：30分钟（运行实际实验验证）
- **文档更新**：30分钟（更新README和函数文档）

总预估时间：2-3小时