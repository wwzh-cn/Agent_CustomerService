"""
记忆整理器模块 - 从日志中智能提取和整合知识

本模块提供 MemoryConsolidator 类，负责从日常日志中提炼有价值的信息，
并将其整合到长期记忆文件（MEMORY.md）中。

核心功能：
1. 分析日志内容，提取关键事实、决策、模式等
2. 评估信息的重要性，决定是否保留到长期记忆
3. 更新 MEMORY.md 文件，保持结构化和容量控制
4. 提供多种整理策略（基于规则、基于LLM等）

整理策略：
- rule_based: 基于关键词和模式的规则提取
- llm_assisted: 使用LLM智能分析日志内容（未来扩展）
"""

import re
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class ConsolidationStrategy(Enum):
    """记忆整理策略"""
    RULE_BASED = "rule_based"      # 基于规则的提取
    LLM_ASSISTED = "llm_assisted"  # LLM辅助分析（未来）


@dataclass
class MemoryEntry:
    """记忆条目数据类"""
    category: str           # 类别：fact, preference, pattern, knowledge, problem, decision
    content: str           # 内容描述
    source_date: date      # 来源日期
    confidence: float      # 置信度（0.0-1.0）
    keywords: List[str]    # 关键词列表
    metadata: Dict[str, Any]  # 附加元数据

    def to_memory_format(self) -> str:
        """转换为记忆文件中的格式"""
        return f"- {self.content} (来源: {self.source_date}, 置信度: {self.confidence:.2f})"


class MemoryConsolidator:
    """记忆整理器类

    负责从日志文件中提取有价值的信息，并整合到长期记忆。
    """

    # 关键类别和触发词
    CATEGORY_KEYWORDS = {
        "fact": ["事实", "数据", "统计", "记录", "发现", "观察到",
                "城市", "天气", "位置", "地点", "所在地", "区域",
                "温度", "气温", "湿度", "风力", "风速", "气象", "气候",
                "时间", "日期", "发布时间", "记录时间"],
        "preference": ["偏好", "喜欢", "不喜欢", "习惯", "常用", "倾向",
                      "关注", "关心", "注意", "重视", "在意"],
        "pattern": ["模式", "规律", "经常", "总是", "通常", "反复", "常见", "频繁"],
        "knowledge": ["学习", "了解", "知道", "掌握", "经验", "技巧", "知识", "信息"],
        "problem": ["问题", "困难", "故障", "错误", "bug", "无法", "失败", "异常"],
        "decision": ["决定", "决策", "选择", "方案", "建议", "推荐", "意见", "结论"],
        "query_history": ["用户查询", "Agent响应", "用户问", "历史对话", "对话记录", "查询历史"],
    }

    def __init__(self, strategy: str = "rule_based", llm_client=None):
        """初始化记忆整理器

        Args:
            strategy: 整理策略，可选 "rule_based" 或 "llm_assisted"
            llm_client: LLM客户端（用于llm_assisted策略）
        """
        self.strategy = ConsolidationStrategy(strategy)
        self.llm_client = llm_client

    def extract_from_logs(self, log_files: List[Path]) -> List[MemoryEntry]:
        """从日志文件提取潜在记忆条目

        Args:
            log_files: 日志文件路径列表

        Returns:
            提取到的记忆条目列表
        """
        entries = []

        for log_file in log_files:
            if not log_file.exists():
                continue

            try:
                # 从文件名解析日期
                date_str = log_file.stem
                try:
                    source_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    source_date = date.today()

                # 读取日志内容
                content = log_file.read_text(encoding="utf-8")

                # 根据策略提取条目
                if self.strategy == ConsolidationStrategy.RULE_BASED:
                    file_entries = self._extract_rule_based(content, source_date)
                elif self.strategy == ConsolidationStrategy.LLM_ASSISTED:
                    file_entries = self._extract_llm_assisted(content, source_date)
                else:
                    file_entries = []

                entries.extend(file_entries)

                print(f"[MemoryConsolidator] 从 {log_file.name} 提取到 {len(file_entries)} 个记忆条目")

            except Exception as e:
                print(f"[MemoryConsolidator] 处理日志文件 {log_file} 失败: {e}")

        return entries

    def _extract_rule_based(self, log_content: str, source_date: date) -> List[MemoryEntry]:
        """基于规则的提取方法

        通过关键词匹配和简单模式识别提取潜在记忆条目。
        """
        entries = []

        # 按行处理日志内容
        lines = log_content.split("\n")

        for line in lines:
            line = line.strip()

            # 跳过空行和标题行
            if not line or line.startswith("#") or line.startswith("==="):
                continue

            # 检查日志条目格式（以 "- " 开头）
            if line.startswith("- "):
                entry_text = line[2:].strip()

                # 专门检测用户查询历史模式（高优先级）
                if "用户查询:" in entry_text and "Agent响应:" in entry_text:
                    # 这是明确的查询历史记录，给予高置信度
                    confidence = 0.9
                    content_keywords = self._extract_keywords(entry_text)

                    entry = MemoryEntry(
                        category="query_history",
                        content=entry_text,
                        source_date=source_date,
                        confidence=confidence,
                        keywords=content_keywords,
                        metadata={"extraction_method": "query_pattern"}
                    )
                    entries.append(entry)
                    continue  # 已处理，跳过后续关键词匹配

                # 为每个类别检查关键词
                for category, keywords in self.CATEGORY_KEYWORDS.items():
                    if any(keyword in entry_text for keyword in keywords):
                        # 计算置信度（基于关键词匹配数量）
                        matched_keywords = [k for k in keywords if k in entry_text]
                        confidence = min(0.3 + 0.1 * len(matched_keywords), 0.9)

                        # 提取关键词（非类别关键词）
                        content_keywords = self._extract_keywords(entry_text)

                        entry = MemoryEntry(
                            category=category,
                            content=entry_text,
                            source_date=source_date,
                            confidence=confidence,
                            keywords=content_keywords,
                            metadata={"extraction_method": "rule_based"}
                        )
                        entries.append(entry)
                        break  # 匹配到一个类别就停止检查其他类别

            # 检查章节标题（以 "## " 开头）
            elif line.startswith("## "):
                section_title = line[3:].strip()

                # 检查章节标题中是否包含重要信息
                for category, keywords in self.CATEGORY_KEYWORDS.items():
                    if any(keyword in section_title for keyword in keywords):
                        # 章节标题本身可能就是一个记忆条目
                        entry = MemoryEntry(
                            category=category,
                            content=f"相关讨论: {section_title}",
                            source_date=source_date,
                            confidence=0.4,  # 章节标题的置信度较低
                            keywords=self._extract_keywords(section_title),
                            metadata={"extraction_method": "section_title"}
                        )
                        entries.append(entry)

        return entries

    def _extract_llm_assisted(self, log_content: str, source_date: date) -> List[MemoryEntry]:
        """基于LLM的提取方法（占位实现）

        未来可以使用LLM更智能地分析日志内容。
        """
        # 这是一个占位实现，实际需要调用LLM API
        print("[MemoryConsolidator] LLM辅助提取尚未实现，回退到规则提取")
        return self._extract_rule_based(log_content, source_date)

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词

        简单实现：提取中文词汇和重要术语
        """
        # 移除标点符号
        cleaned = re.sub(r'[^\w\u4e00-\u9fff]+', ' ', text)

        # 分割词汇
        words = cleaned.split()

        # 过滤短词和常见词
        common_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "也", "这", "那", "个"}
        keywords = [w for w in words if len(w) > 1 and w not in common_words]

        # 限制数量
        return keywords[:10]

    def evaluate_importance(self, entry: MemoryEntry) -> float:
        """评估记忆条目的重要性

        Args:
            entry: 记忆条目

        Returns:
            重要性分数 (0.0-1.0)
        """
        base_score = entry.confidence

        # 基于类别的权重调整
        category_weights = {
            "fact": 0.9,        # 事实很重要
            "preference": 0.8,  # 用户偏好很重要
            "pattern": 0.7,     # 模式有价值
            "knowledge": 0.8,   # 学习到的知识重要
            "problem": 0.6,     # 问题需要关注但可能过时
            "decision": 0.9,    # 决策很重要
            "query_history": 0.85, # 用户查询历史重要
        }

        category_weight = category_weights.get(entry.category, 0.5)
        base_score *= category_weight

        # 基于关键词数量的调整
        if len(entry.keywords) >= 3:
            base_score *= 1.1
        elif len(entry.keywords) == 0:
            base_score *= 0.9

        # 基于时间的衰减（未来实现）
        # days_old = (date.today() - entry.source_date).days
        # time_factor = max(0.5, 1.0 - days_old / 30)  # 30天线性衰减
        # base_score *= time_factor

        return min(max(base_score, 0.0), 1.0)

    def consolidate_to_memory(self, entries: List[MemoryEntry], memory_path: Path,
                              max_entries_per_category: int = 10):
        """将重要条目整合到 MEMORY.md

        Args:
            entries: 记忆条目列表
            memory_path: MEMORY.md 文件路径
            max_entries_per_category: 每个类别最大条目数
        """
        if not entries:
            print("[MemoryConsolidator] 没有需要整合的记忆条目")
            return

        # 评估每个条目的重要性
        scored_entries = []
        for entry in entries:
            importance = self.evaluate_importance(entry)
            scored_entries.append((importance, entry))

        # 按重要性排序
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # 去重：基于内容文本，保留重要性最高的条目
        seen_contents = set()
        deduplicated_entries = []
        for importance, entry in scored_entries:
            # 简化内容用于去重（移除可能变化的尾部）
            simplified_content = entry.content.split('...')[0] if '...' in entry.content else entry.content[:100]
            content_key = f"{entry.category}:{simplified_content}"

            if content_key not in seen_contents:
                seen_contents.add(content_key)
                deduplicated_entries.append((importance, entry))
            else:
                print(f"[MemoryConsolidator] 跳过重复条目: {entry.content[:50]}...")

        # 按类别分组，并限制每个类别的条目数
        grouped_entries: Dict[str, List[Tuple[float, MemoryEntry]]] = {}
        for importance, entry in deduplicated_entries:
            if entry.category not in grouped_entries:
                grouped_entries[entry.category] = []

            if len(grouped_entries[entry.category]) < max_entries_per_category:
                grouped_entries[entry.category].append((importance, entry))

        # 构建新的记忆内容
        new_content = self._build_memory_content(grouped_entries)

        # 读取现有记忆文件（如果存在）
        existing_content = ""
        if memory_path.exists():
            try:
                existing_content = memory_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[MemoryConsolidator] 读取现有记忆文件失败: {e}")

        # 合并新旧内容（这里简单替换，未来可以更智能）
        final_content = self._merge_memory_content(existing_content, new_content)

        # 写入文件
        try:
            memory_path.write_text(final_content, encoding="utf-8")
            print(f"[MemoryConsolidator] 成功整合 {len(entries)} 个条目到记忆文件")
        except Exception as e:
            print(f"[MemoryConsolidator] 写入记忆文件失败: {e}")

    def _build_memory_content(self, grouped_entries: Dict[str, List[Tuple[float, MemoryEntry]]]) -> str:
        """构建记忆文件内容

        Args:
            grouped_entries: 按类别分组的记忆条目

        Returns:
            格式化的记忆内容
        """
        # 类别显示名称映射
        category_names = {
            "fact": "重要事实",
            "preference": "用户偏好",
            "pattern": "常见问题模式",
            "knowledge": "学习到的知识",
            "problem": "待解决的问题",
            "decision": "决策历史",
            "query_history": "用户查询历史",
        }

        lines = ["# 长期记忆", ""]
        lines.append("> **注意**：本文件由 Agent 自动维护，请勿手动修改。文件大小限制为 2000 字符以内。")
        lines.append("")

        # 添加每个类别的条目
        for category_id, entries in grouped_entries.items():
            category_name = category_names.get(category_id, category_id)
            lines.append(f"## {category_name}")
            lines.append("")

            if entries:
                for importance, entry in entries:
                    lines.append(entry.to_memory_format())
                lines.append("")
            else:
                lines.append("- *暂无记录*")
                lines.append("")

        # 添加最后更新时间和分隔符
        lines.append("---")
        lines.append(f"*最后更新：{date.today().isoformat()}*")

        return "\n".join(lines)

    def _merge_memory_content(self, existing_content: str, new_content: str) -> str:
        """合并新旧记忆内容

        简单实现：直接使用新内容替换
        未来可以更智能地合并，如保留部分旧条目、去重等。

        Args:
            existing_content: 现有记忆内容
            new_content: 新提取的记忆内容

        Returns:
            合并后的内容
        """
        # 这里使用新内容替换旧内容
        # 在实际应用中，可能需要更复杂的合并逻辑
        return new_content

    def consolidate_from_directory(self, logs_dir: Path, memory_path: Path,
                                   days_to_review: int = 7):
        """从日志目录整合记忆

        Args:
            logs_dir: 日志目录路径
            memory_path: 记忆文件路径
            days_to_review: 回顾最近几天的日志
        """
        # 收集最近几天的日志文件
        today = date.today()
        log_files = []

        for i in range(days_to_review):
            log_date = today - timedelta(days=i)
            log_file = logs_dir / f"{log_date.isoformat()}.md"
            if log_file.exists():
                log_files.append(log_file)

        if not log_files:
            print(f"[MemoryConsolidator] 最近 {days_to_review} 天没有找到日志文件")
            return

        print(f"[MemoryConsolidator] 找到 {len(log_files)} 个日志文件进行整理")

        # 提取记忆条目
        entries = self.extract_from_logs(log_files)

        if not entries:
            print("[MemoryConsolidator] 没有提取到有价值的记忆条目")
            return

        # 整合到记忆文件
        self.consolidate_to_memory(entries, memory_path)


# 全局记忆整理器实例（可选）
_global_memory_consolidator: Optional[MemoryConsolidator] = None


def get_global_memory_consolidator(strategy: str = "rule_based",
                                    llm_client=None) -> MemoryConsolidator:
    """获取全局记忆整理器实例（单例模式）

    Args:
        strategy: 整理策略
        llm_client: LLM客户端

    Returns:
        MemoryConsolidator 实例
    """
    global _global_memory_consolidator
    if _global_memory_consolidator is None:
        _global_memory_consolidator = MemoryConsolidator(strategy, llm_client)
    return _global_memory_consolidator


if __name__ == "__main__":
    """模块测试"""
    print("=== MemoryConsolidator 模块测试 ===")

    # 创建记忆整理器
    consolidator = MemoryConsolidator(strategy="rule_based")

    # 测试关键词提取
    test_text = "用户经常咨询扫地机器人在潮湿环境下的使用问题"
    keywords = consolidator._extract_keywords(test_text)
    print(f"关键词提取测试: {test_text}")
    print(f"提取到的关键词: {keywords}")

    # 测试记忆条目创建
    test_entry = MemoryEntry(
        category="fact",
        content="扫地机器人在湿度>80%的环境下工作效率会下降",
        source_date=date.today(),
        confidence=0.8,
        keywords=["扫地机器人", "湿度", "工作效率"],
        metadata={"source": "测试"}
    )

    print(f"\n测试记忆条目:")
    print(f"  类别: {test_entry.category}")
    print(f"  内容: {test_entry.content}")
    print(f"  格式: {test_entry.to_memory_format()}")
    print(f"  重要性评估: {consolidator.evaluate_importance(test_entry):.2f}")

    # 测试从目录整合（需要实际日志文件）
    logs_dir = Path("./memory/logs")
    memory_path = Path("./memory/MEMORY.md")

    if logs_dir.exists() and memory_path.exists():
        print(f"\n测试从目录整合记忆:")
        consolidator.consolidate_from_directory(logs_dir, memory_path, days_to_review=3)
    else:
        print(f"\n跳过目录整合测试：日志目录或记忆文件不存在")

    print("\n测试完成！")