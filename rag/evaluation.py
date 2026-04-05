"""
RAG检索效果评估模块
专注于计算准确率（Precision）和召回率（Recall）
"""

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'  # 解决OpenMP库冲突问题
# os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'  # 设置huggingface下载超时300秒
# os.environ['HF_HUB_CONNECT_TIMEOUT'] = '60'    # 设置连接超时60秒
# os.environ['TRANSFORMERS_OFFLINE'] = '1'       # 离线模式，不使用网络
# os.environ['HF_HUB_OFFLINE'] = '1'             # huggingface hub离线模式

import json
import sys
from pathlib import Path

# 添加父目录到路径，以便导入rag_service
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.rag_service import RagSummarizeService


def count_relevant(retrieved_chunks, relevant_keywords):
    """
    简化版相关性判断：检查检索片段是否包含关键词
    实际应用中可使用更复杂的语义匹配

    Args:
        retrieved_chunks: 检索到的文档片段列表
        relevant_keywords: 相关关键词列表

    Returns:
        int: 相关片段数量
    """
    count = 0
    for chunk in retrieved_chunks:
        chunk_lower = chunk.lower()  # 转为小写进行不区分大小写匹配
        for keyword in relevant_keywords:
            if keyword.lower() in chunk_lower:
                count += 1
                break  # 只要匹配一个关键词就算相关
    return count


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
    # 确定测试用例路径
    if test_cases_path is None:
        # 默认使用项目根目录下的测试数据
        base_dir = Path(__file__).parent.parent
        test_cases_path = base_dir / "所有改动" / "RAG检索" / "测试数据_50.json"

    # 加载测试用例
    test_cases_path = Path(test_cases_path)
    if not test_cases_path.exists():
        print(f"错误：测试用例文件不存在: {test_cases_path}")
        return None

    try:
        with open(test_cases_path, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    except Exception as e:
        print(f"加载测试用例失败: {e}")
        return None

    # 初始化RAG服务
    try:
        rag = RagSummarizeService(use_rerank=use_rerank)
    except Exception as e:
        print(f"初始化RAG服务失败: {e}")
        return None

    def _single_evaluate(test_cases, k, rag_service):
        """
        单次RAG评估内部函数

        Args:
            test_cases: 测试用例列表
            k: top-k值
            rag_service: 初始化的RAG服务实例

        Returns:
            tuple: (precision平均值, recall平均值, case_results列表)
        """
        total_precision = 0
        total_recall = 0
        case_results = []

        for i, case in enumerate(test_cases, 1):
            query = case["query"]
            relevant_keywords = case.get("relevant_keywords", [])

            # 获取检索结果（仅检索阶段，不生成回答）
            try:
                docs = rag_service.retriever_docs(query)
                # 取前k个文档的内容片段
                retrieved_chunks = [doc.page_content for doc in docs[:k]]

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
                    "retrieved_count": len(retrieved_chunks),
                    "relevant_retrieved": relevant_retrieved,
                    "total_relevant": total_relevant
                })

            except Exception as e:
                print(f"用例{i}执行失败: {e}")
                continue

        # 计算平均指标
        avg_precision = total_precision / len(case_results) if case_results else 0
        avg_recall = total_recall / len(case_results) if case_results else 0

        return avg_precision, avg_recall, case_results

    # 初始化收集列表
    all_precisions = []
    all_recalls = []
    all_case_details = []  # 可选：保存每次实验的详细结果
    successful_runs = 0

    print(f"开始评估RAG检索效果 (k={k}, runs={runs})，共{len(test_cases)}个测试用例")
    print("=" * 60)

    for run in range(runs):
        try:
            # 运行单次评估
            print(f"\n--- 实验 {run+1}/{runs} ---")
            precision, recall, case_details = _single_evaluate(test_cases, k, rag)

            # 收集本次实验的结果
            all_precisions.append(precision)
            all_recalls.append(recall)
            all_case_details.append(case_details)
            successful_runs += 1

            # 显示进度
            print(f"[OK] 完成实验 {run+1}/{runs}，准确率: {precision:.2%}, 召回率: {recall:.2%}")

        except Exception as e:
            if skip_failures:
                print(f"[WARN] 实验 {run+1}/{runs} 失败: {e}，跳过...")
                continue
            else:
                raise

    # 检查是否有成功实验
    if successful_runs == 0:
        print("所有实验都失败了！")
        return None

    print("=" * 60)
    print(f"评估完成！成功实验: {successful_runs}/{runs}")

    # 计算统计指标
    import math

    # 计算平均值
    precision_mean = sum(all_precisions) / successful_runs
    recall_mean = sum(all_recalls) / successful_runs

    # 计算标准差
    if successful_runs > 1:
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

    # 计算范围
    precision_range = precision_max - precision_min
    recall_range = recall_max - recall_min

    # 构建结果字典（保持向后兼容）
    results = {
        "precision@3": precision_mean,  # 平均值，保持向后兼容
        "recall@3": recall_mean,        # 平均值，保持向后兼容
        "total_cases": len(test_cases),
        "successful_cases": len(all_case_details[-1]) if all_case_details else 0,  # 最后一次成功的用例数
        "case_details": all_case_details[-1] if all_case_details else [],  # 最后一次实验的详细结果（可选）
        "statistics": {
            "precision@3": {
                "mean": precision_mean,
                "std": precision_std,
                "min": precision_min,
                "max": precision_max,
                "range": precision_range
            },
            "recall@3": {
                "mean": recall_mean,
                "std": recall_std,
                "min": recall_min,
                "max": recall_max,
                "range": recall_range
            },
            "runs": {
                "requested": runs,
                "successful": successful_runs,
                "failed": runs - successful_runs
            }
        },
        "config": {
            "k": k,
            "runs": runs,
            "skip_failures": skip_failures,
            "test_data_path": str(test_cases_path)
        }
    }

    # 输出统计摘要
    print(f"平均准确率@3: {precision_mean:.2%} (标准差: {precision_std:.4f})")
    print(f"平均召回率@3: {recall_mean:.2%} (标准差: {recall_std:.4f})")
    print(f"准确率范围: {precision_min:.2%} - {precision_max:.2%}")
    print(f"召回率范围: {recall_min:.2%} - {recall_max:.2%}")

    return results

def save_results(results, output_path="rag_evaluation_results.json"):
    """
    保存评估结果到文件

    Args:
        results: 评估结果字典
        output_path: 输出文件路径
    """
    output_path = Path(output_path)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"评估结果已保存到 {output_path}")
        return True
    except Exception as e:
        print(f"保存结果失败: {e}")
        return False


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
        print("[OK] Rerank模式整体效果更优")
    elif comparison["summary"]["rerank_better_precision"]:
        print("[WARN] Rerank模式准确率更高，但召回率相似或更低")
    elif comparison["summary"]["rerank_better_recall"]:
        print("[WARN] Rerank模式召回率更高，但准确率相似或更低")
    else:
        print("[ERROR] Rerank模式未带来明显改进")

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


if __name__ == "__main__":
    # 使用默认测试数据路径
    test_file = None  # 使用默认路径

    print("=== RAG检索效果评估 ===")
    print(f"工作目录: {os.getcwd()}")

    ## 使用rerank
    results = evaluate_rag(test_file, use_rerank=False)

    ## 不使用rerank
    # results = evaluate_rag(test_file)

    if results:
        # 保存评估结果
        output_file = "rag_evaluation_results.json"
        if save_results(results, output_file):
            print("\n评估摘要:")
            print(f"- 测试用例总数: {results['total_cases']}")
            print(f"- 成功执行用例: {results['successful_cases']}")
            print(f"- 平均准确率@3: {results['precision@3']:.2%}")
            print(f"- 平均召回率@3: {results['recall@3']:.2%}")

            # 简要分析
            precision = results['precision@3']
            recall = results['recall@3']

            if precision > 0.8 and recall > 0.8:
                rating = "优秀"
            elif precision > 0.6 and recall > 0.6:
                rating = "良好"
            else:
                rating = "需要改进"

            print(f"- 评估评级: {rating}")
        else:
            print("评估完成但结果保存失败")
    else:
        print("评估失败")