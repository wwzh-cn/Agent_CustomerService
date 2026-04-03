"""
文件记忆管理器模块 - 管理文件层持久化记忆

本模块提供 FileMemory 类，实现基于文件系统的中期记忆存储。
记忆分为三层：身份定义（静态）、长期记忆库（动态）、工具配置（静态）和日常日志。

核心功能：
1. 启动时加载记忆上下文到系统提示词
2. 运行时记录重要事件到日志文件
3. 定期整理日志，提炼知识到长期记忆库
4. 手动更新特定记忆条目

文件结构：
memory/
├── IDENTITY.md      # Agent 身份定义（静态）
├── MEMORY.md        # 长期记忆库（动态更新，≤2000字）
├── TOOLS.md         # 工具配置和环境信息（静态）
└── logs/
    ├── 2026-03-31.md    # 每日工作日志（原始记录）
    ├── 2026-04-01.md    # 按日期组织，天然容量控制
    └── ...
"""

import os
import re
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
import threading

from .memory_consolidator import MemoryConsolidator


class FileMemory:
    """文件记忆管理器类

    负责管理基于文件系统的记忆存储，提供记忆加载、日志记录、记忆更新等功能。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化文件记忆管理器

        Args:
            config: 配置字典，支持以下键：
                - base_dir: 记忆文件根目录 (默认: "./memory")
                - load_on_startup: 启动时是否加载记忆 (默认: True)
                - identity_files: 身份文件列表 (默认: ["IDENTITY.md", "MEMORY.md", "TOOLS.md"])
                - recent_log_days: 加载最近几天日志 (默认: 2)
                - max_memory_size: MEMORY.md 最大字符数 (默认: 2000)
        """
        # 默认配置
        self.config = {
            "base_dir": "./memory",
            "load_on_startup": True,
            "identity_files": ["IDENTITY.md", "MEMORY.md", "TOOLS.md"],
            "recent_log_days": 2,
            "max_memory_size": 2000,
        }

        # 更新用户配置
        if config:
            self.config.update(config)

        # 路径处理
        self.base_dir = Path(self.config["base_dir"])
        self.logs_dir = self.base_dir / "logs"

        # 线程锁，确保文件操作安全
        self._lock = threading.RLock()

        # 记忆整理相关
        self.last_consolidation_time = 0
        self.consolidator = None

        # 初始化记忆整理器（如果启用）
        consolidation_config = self.config.get("consolidation", {})
        if consolidation_config.get("enabled", True):
            strategy = consolidation_config.get("strategy", "rule_based")
            self.consolidator = MemoryConsolidator(strategy=strategy)

        # 确保目录结构存在
        self._ensure_directory_structure()

    def _ensure_directory_structure(self):
        """确保必要的目录和文件存在"""
        with self._lock:
            # 创建目录
            self.base_dir.mkdir(exist_ok=True)
            self.logs_dir.mkdir(exist_ok=True)

            # 创建必要的文件（如果不存在）
            identity_files = self.config["identity_files"]
            for file_name in identity_files:
                file_path = self.base_dir / file_name
                if not file_path.exists():
                    if file_name == "IDENTITY.md":
                        self._create_default_identity(file_path)
                    elif file_name == "MEMORY.md":
                        self._create_default_memory(file_path)
                    elif file_name == "TOOLS.md":
                        self._create_default_tools(file_path)

            # 创建今日日志文件（如果不存在）
            today_log = self._get_today_log_path()
            if not today_log.exists():
                self._create_today_log(today_log)

    def _create_default_identity(self, path: Path):
        """创建默认身份文件"""
        content = """# Agent 身份定义

## 基本身份
- **名称**：智扫通机器人智能客服
- **角色**：扫地机器人和扫拖一体机器人的专业智能客服
- **使命**：为用户提供专业、准确、实用的机器人使用建议和故障解决方案

## 核心能力
1. **自主思考**：具备ReAct（思考→行动→观察→再思考）推理能力
2. **工具调用**：能调用多种工具获取外部信息
3. **专业判断**：基于机器人专业知识提供建议
4. **记忆管理**：能记住重要信息和用户偏好

## 行为准则
1. 优先利用对话历史中的已有信息，避免重复调用工具
2. 工具调用必须精准匹配需求，参数格式正确
3. 报告生成需严格遵守固定执行流程
4. 保持专业、友好的服务态度

## 服务范围
- 扫地/扫拖机器人使用咨询
- 故障排查和维修建议
- 环境适配性分析
- 个性化使用报告生成
- 维护保养指导

## 知识边界
- 专注于扫地机器人相关领域
- 对于超出知识范围的问题，如实告知并提供替代方案
- 不提供医疗、法律等专业领域建议"""
        path.write_text(content, encoding="utf-8")

    def _create_default_memory(self, path: Path):
        """创建默认记忆文件"""
        content = """# 长期记忆

> **注意**：本文件由 Agent 自动维护，请勿手动修改。文件大小限制为 2000 字符以内。

## 重要事实
- *暂无记录*

## 用户偏好
- *暂无记录*

## 常见问题模式
- *暂无记录*

## 学习到的知识
- *暂无记录*

## 待解决的问题
- *暂无记录*

## 决策历史
- *暂无记录*

---

*最后更新：{date}*""".format(date=date.today().isoformat())
        path.write_text(content, encoding="utf-8")

    def _create_default_tools(self, path: Path):
        """创建默认工具文件"""
        content = """# 工具配置和环境信息

## 可用工具列表

### 1. rag_summarize
- **功能**：从向量库检索扫地/扫拖机器人的专业资料
- **使用场景**：需要补充专业信息、行业知识时调用
- **参数**：`query`（检索词，纯文本字符串）
- **限制**：必须传入纯文本字符串参数

### 2. get_weather
- **功能**：获取指定城市的实时天气信息
- **使用场景**：判断环境是否适配机器人使用
- **参数**：`city`（城市名，纯文本字符串）
- **限制**：需要准确的城市名称

### 3. get_user_location
- **功能**：获取用户当前所在城市
- **使用场景**：需要用户地理位置信息时
- **参数**：无
- **限制**：直接调用，无需参数

### 4. get_user_id
- **功能**：获取当前用户的唯一标识
- **使用场景**：生成个性化报告时
- **参数**：无
- **限制**：直接调用，无需参数

### 5. get_current_month
- **功能**：获取系统当前月份
- **使用场景**：报告生成需要月份信息时
- **参数**：无
- **限制**：返回格式为 "YYYY-MM"

### 6. fetch_external_data
- **功能**：检索用户在指定月份的使用记录
- **使用场景**：生成使用报告时
- **参数**：`user_id`（用户ID），`month`（月份）
- **限制**：必须同时传入两个参数

### 7. fill_context_for_report
- **功能**：为报告生成动态注入上下文
- **使用场景**：仅当明确识别报告生成意图时
- **参数**：无
- **限制**：非报告场景严禁调用

## 环境配置
- **外部数据路径**：`data/external/records.csv`
- **高德地图API**：已配置，支持位置查询
- **向量数据库**：ChromaDB，存储机器人专业知识

## 系统约束
1. 工具调用前必须输出真实的自然语言思考过程
2. 优先使用历史信息，避免重复调用工具
3. 报告生成必须遵循固定流程
4. 工具参数必须精确匹配定义"""
        path.write_text(content, encoding="utf-8")

    def _create_today_log(self, path: Path):
        """创建今日日志文件"""
        content = f"""# 工作日志：{date.today().isoformat()}

## 系统启动
- 记忆系统初始化完成
- 加载身份定义、工具配置和长期记忆
- 文件记忆管理器已就绪

---

*日志记录开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"""
        path.write_text(content, encoding="utf-8")

    def _get_today_log_path(self) -> Path:
        """获取今日日志文件路径"""
        return self.logs_dir / f"{date.today().isoformat()}.md"

    def load_context(self) -> str:
        """加载所有记忆上下文

        Returns:
            拼接后的记忆上下文字符串，格式为：
            === IDENTITY.md ===
            [身份内容]

            === MEMORY.md ===
            [记忆内容]

            === TOOLS.md ===
            [工具内容]

            === 最近日志 ===
            [最近N天日志内容]
        """
        with self._lock:
            context_parts = []

            # 加载身份文件
            identity_files = self.config["identity_files"]
            for file_name in identity_files:
                file_path = self.base_dir / file_name
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8").strip()
                        context_parts.append(f"=== {file_name} ===\n{content}")
                    except Exception as e:
                        print(f"[FileMemory] 加载文件 {file_name} 失败: {e}")

            # 加载最近日志
            logs_content = self._load_recent_logs_content()
            if logs_content:
                context_parts.append(f"=== 最近日志 ===\n{logs_content}")

            return "\n\n".join(context_parts)

    def _load_recent_logs_content(self) -> str:
        """加载最近几天的日志内容"""
        days = self.config["recent_log_days"]
        today = date.today()
        logs_content = []

        for i in range(days):
            log_date = today - timedelta(days=i)
            log_path = self.logs_dir / f"{log_date.isoformat()}.md"
            if log_path.exists():
                try:
                    content = log_path.read_text(encoding="utf-8").strip()
                    logs_content.append(f"=== {log_date.isoformat()} ===\n{content}")
                except Exception as e:
                    print(f"[FileMemory] 加载日志 {log_date} 失败: {e}")

        return "\n\n".join(logs_content)

    def log_event(self, category: str, content: str, metadata: Optional[Dict] = None):
        """记录事件到当日日志

        Args:
            category: 事件类别，如 "decision", "learning", "error", "completion"
            content: 事件内容描述
            metadata: 附加元数据（可选）
        """
        with self._lock:
            log_path = self._get_today_log_path()

            # 确保日志文件存在
            if not log_path.exists():
                self._create_today_log(log_path)

            # 格式化日志条目
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"\n\n## [{timestamp}] {category}"

            if metadata:
                metadata_str = " ".join([f"{k}={v}" for k, v in metadata.items()])
                log_entry += f" ({metadata_str})"

            log_entry += f"\n- {content}"

            # 追加到日志文件
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as e:
                print(f"[FileMemory] 写入日志失败: {e}")

    def update_memory(self, key: str, value: str):
        """更新 MEMORY.md 中的指定条目

        Args:
            key: 记忆条目键（如 "重要事实"、"用户偏好"等）
            value: 记忆条目值
        """
        with self._lock:
            memory_path = self.base_dir / "MEMORY.md"

            if not memory_path.exists():
                # 如果文件不存在，创建新文件
                self._create_default_memory(memory_path)

            try:
                content = memory_path.read_text(encoding="utf-8")

                # 查找对应的章节
                marker = f"## {key}"
                lines = content.split("\n")
                new_lines = []
                skip = False
                found = False

                for line in lines:
                    if line.strip() == marker:
                        # 找到对应章节，替换内容
                        new_lines.append(line)
                        new_lines.append(value)
                        skip = True
                        found = True
                    elif skip and line.startswith("## "):
                        # 遇到下一个章节，停止跳过
                        skip = False
                        new_lines.append(line)
                    elif not skip:
                        new_lines.append(line)

                if not found:
                    # 如果没找到对应章节，添加到文件末尾
                    # 先移除最后的更新时间和分隔符
                    while new_lines and new_lines[-1].strip() == "":
                        new_lines.pop()

                    while new_lines and new_lines[-1].startswith("*最后更新："):
                        new_lines.pop()

                    while new_lines and new_lines[-1].startswith("---"):
                        new_lines.pop()

                    # 添加新章节
                    new_lines.extend(["", f"## {key}", value])

                # 添加更新时间和分隔符
                new_lines.extend([
                    "",
                    "---",
                    f"*最后更新：{date.today().isoformat()}*"
                ])

                # 检查文件大小并压缩
                new_content = "\n".join(new_lines)
                if len(new_content) > self.config["max_memory_size"]:
                    new_content = self._compress_memory(new_content)

                # 写入文件
                memory_path.write_text(new_content, encoding="utf-8")

            except Exception as e:
                print(f"[FileMemory] 更新记忆失败: {e}")

    def _compress_memory(self, content: str) -> str:
        """压缩记忆内容，确保不超过最大限制

        简单实现：移除最旧的部分章节
        未来可优化为基于重要性评估的压缩
        """
        lines = content.split("\n")

        # 找到所有章节的起始位置
        section_starts = []
        for i, line in enumerate(lines):
            if line.startswith("## ") and not line.startswith("###"):
                section_starts.append(i)

        # 如果有多个章节，尝试移除第一个非核心章节
        if len(section_starts) > 1:
            # 跳过第一个章节（"长期记忆"标题）
            for i in range(1, len(section_starts)):
                start_idx = section_starts[i]
                end_idx = section_starts[i + 1] if i + 1 < len(section_starts) else len(lines)

                # 检查移除后的大小
                new_lines = lines[:start_idx] + lines[end_idx:]
                new_content = "\n".join(new_lines)

                if len(new_content) <= self.config["max_memory_size"]:
                    print(f"[FileMemory] 压缩记忆：移除章节 {lines[start_idx]}")
                    return new_content

        # 如果仍然太大，进行截断
        print(f"[FileMemory] 记忆内容过大，进行截断")
        return content[:self.config["max_memory_size"]]

    def consolidate_memory(self, days_to_review: int = 7, force: bool = False):
        """记忆整理：从近期日志提炼知识到 MEMORY.md

        Args:
            days_to_review: 回顾最近几天的日志
            force: 是否强制整理（忽略时间间隔）
        """
        with self._lock:
            # 检查是否应该执行整理
            if not self._should_consolidate() and not force:
                print("[FileMemory] 未达到记忆整理时间间隔，跳过")
                return False

            print(f"[FileMemory] 开始记忆整理，回顾最近 {days_to_review} 天日志")

            if self.consolidator is None:
                print("[FileMemory] 记忆整理器未启用，使用简单记录")
                # 记录整理操作
                self.log_event(
                    category="memory_consolidation",
                    content=f"执行记忆整理，回顾了最近 {days_to_review} 天日志（简单记录）",
                    metadata={"days_reviewed": days_to_review}
                )
                return False

            try:
                # 使用记忆整理器进行智能整理
                memory_path = self.base_dir / "MEMORY.md"
                self.consolidator.consolidate_from_directory(
                    logs_dir=self.logs_dir,
                    memory_path=memory_path,
                    days_to_review=days_to_review
                )

                # 更新最后整理时间
                self.last_consolidation_time = time.time()

                # 记录整理操作
                self.log_event(
                    category="memory_consolidation",
                    content=f"执行记忆整理，回顾了最近 {days_to_review} 天日志",
                    metadata={
                        "days_reviewed": days_to_review,
                        "strategy": self.consolidator.strategy.value,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                print("[FileMemory] 记忆整理完成")
                return True

            except Exception as e:
                print(f"[FileMemory] 记忆整理失败: {e}")
                # 记录错误
                self.log_event(
                    category="error",
                    content=f"记忆整理失败: {str(e)}",
                    metadata={"error": str(e), "operation": "consolidate_memory"}
                )
                return False

    def _should_consolidate(self) -> bool:
        """检查是否应该执行记忆整理

        基于配置的时间间隔检查
        """
        consolidation_config = self.config.get("consolidation", {})
        if not consolidation_config.get("enabled", True):
            return False

        interval_hours = consolidation_config.get("interval_hours", 72)
        interval_seconds = interval_hours * 3600

        # 检查时间间隔
        time_since_last = time.time() - self.last_consolidation_time
        return time_since_last >= interval_seconds

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息"""
        with self._lock:
            stats = {
                "base_dir": str(self.base_dir),
                "memory_file_exists": (self.base_dir / "MEMORY.md").exists(),
                "identity_file_exists": (self.base_dir / "IDENTITY.md").exists(),
                "tools_file_exists": (self.base_dir / "TOOLS.md").exists(),
                "log_count": 0,
                "total_log_size": 0,
            }

            # 统计日志文件
            if self.logs_dir.exists():
                log_files = list(self.logs_dir.glob("*.md"))
                stats["log_count"] = len(log_files)
                stats["total_log_size"] = sum(f.stat().st_size for f in log_files)

            # 获取记忆文件大小
            memory_path = self.base_dir / "MEMORY.md"
            if memory_path.exists():
                stats["memory_file_size"] = memory_path.stat().st_size
                stats["memory_content"] = memory_path.read_text(encoding="utf-8")[:100] + "..."

            return stats


# 全局文件记忆管理器实例（可选）
_global_file_memory: Optional[FileMemory] = None


def get_global_file_memory(config: Optional[Dict[str, Any]] = None) -> FileMemory:
    """获取全局文件记忆管理器实例（单例模式）

    Args:
        config: 配置字典，仅在第一次调用时有效

    Returns:
        FileMemory 实例
    """
    global _global_file_memory
    if _global_file_memory is None:
        _global_file_memory = FileMemory(config)
    return _global_file_memory


if __name__ == "__main__":
    """模块测试"""
    print("=== FileMemory 模块测试 ===")

    # 创建文件记忆管理器
    fm = FileMemory({
        "base_dir": "./memory",
        "recent_log_days": 2,
        "max_memory_size": 2000
    })

    # 测试加载上下文
    context = fm.load_context()
    print(f"加载的上下文长度: {len(context)} 字符")
    print(f"上下文预览:\n{context[:500]}...\n")

    # 测试日志记录
    fm.log_event("test", "这是一个测试日志条目", {"test_id": "123"})
    fm.log_event("learning", "学习了新的故障排查方法", {"topic": "扫地机器人"})

    # 测试记忆更新
    fm.update_memory("重要事实", "- 用户经常咨询扫地机器人在潮湿环境下的使用问题")
    fm.update_memory("学习到的知识", "- 扫地机器人在湿度>80%的环境下工作效率会下降")

    # 测试统计信息
    stats = fm.get_memory_stats()
    print("记忆系统统计:")
    for key, value in stats.items():
        if key != "memory_content":  # 跳过长内容
            print(f"  {key}: {value}")

    # 测试记忆整理
    fm.consolidate_memory(days_to_review=3)

    print("\n测试完成！")