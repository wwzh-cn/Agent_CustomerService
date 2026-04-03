"""
日志文件分块器模块

本模块提供 LogChunker 类，用于将日志文件分割成适合向量索引的文本块。
支持多种分块策略：按章节分块、按条目分块、滑动窗口分块等。

主要功能：
1. 解析 Markdown 格式的日志文件
2. 按逻辑单元分割文本（章节、条目）
3. 提取元数据（日期、类别、时间戳）
4. 生成适合 embedding 的文本块
"""

import re
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import logging


@dataclass
class LogChunk:
    """日志块数据结构"""
    text: str                    # 块文本内容
    metadata: Dict[str, Any]     # 元数据
    log_date: date               # 日志日期（从文件名或内容提取）
    chunk_type: str              # 块类型：section, entry, window

    def __str__(self):
        return f"LogChunk(type={self.chunk_type}, date={self.log_date}, text={self.text[:50]}...)"


class LogChunker:
    """日志文件分块器

    负责将日志文件分割成适合向量索引的文本块，支持多种分块策略。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化日志分块器

        Args:
            config: 配置字典，支持以下键：
                chunk_size: 分块大小（字符数，默认500）
                chunk_overlap: 块重叠大小（字符数，默认50）
                max_chunks_per_file: 单文件最大块数（默认100）
                strategies: 使用的分块策略列表（默认所有）
        """
        self.config = config or {}
        self.chunk_size = self.config.get("chunk_size", 500)
        self.chunk_overlap = self.config.get("chunk_overlap", 50)
        self.max_chunks = self.config.get("max_chunks_per_file", 100)
        self.logger = logging.getLogger(__name__)

    def chunk_log_file(self, log_path: Path) -> List[LogChunk]:
        """解析 Markdown 格式日志文件，返回分块列表

        Args:
            log_path: 日志文件路径

        Returns:
            List[LogChunk]: 分块列表
        """
        if not log_path.exists():
            self.logger.error(f"日志文件不存在: {log_path}")
            return []

        try:
            # 读取文件内容
            content = log_path.read_text(encoding='utf-8')
            if not content:
                self.logger.warning(f"日志文件为空: {log_path}")
                return []

            # 从文件名提取日志日期
            log_date = self._extract_date_from_filename(log_path)

            # 分块策略序列
            chunks = []

            # 策略1：按章节分块（## 标题）
            section_chunks = self._chunk_by_sections(content, log_date, log_path)
            if section_chunks:
                chunks.extend(section_chunks)
                self.logger.debug(f"按章节分块: {len(section_chunks)} 块")

            # 策略2：按条目分块（- 开头的项目符号）
            entry_chunks = self._chunk_by_entries(content, log_date, log_path)
            if entry_chunks:
                chunks.extend(entry_chunks)
                self.logger.debug(f"按条目分块: {len(entry_chunks)} 块")

            # 策略3：滑动窗口分块（处理长文本）
            if len(chunks) < self.max_chunks // 2:  # 如果分块不足，使用滑动窗口
                window_chunks = self._chunk_by_sliding_window(content, log_date, log_path)
                if window_chunks:
                    chunks.extend(window_chunks)
                    self.logger.debug(f"滑动窗口分块: {len(window_chunks)} 块")

            # 限制最大块数
            if len(chunks) > self.max_chunks:
                chunks = chunks[:self.max_chunks]
                self.logger.info(f"分块数超过限制，截断为 {self.max_chunks} 块")

            self.logger.info(f"文件 {log_path.name} 分块完成: {len(chunks)} 块")
            return chunks

        except Exception as e:
            self.logger.error(f"分块日志文件失败 {log_path}: {e}")
            return []

    def _extract_date_from_filename(self, log_path: Path) -> date:
        """从文件名提取日期

        Args:
            log_path: 日志文件路径

        Returns:
            date: 提取的日期，失败返回当天日期
        """
        try:
            # 假设文件名格式为 YYYY-MM-DD.md
            date_str = log_path.stem
            return date.fromisoformat(date_str)
        except (ValueError, AttributeError):
            # 尝试从内容中提取日期
            try:
                content = log_path.read_text(encoding='utf-8', errors='ignore')
                # 查找 # 工作日志：YYYY-MM-DD 格式
                match = re.search(r'#\s*工作日志\s*[:：]\s*(\d{4}-\d{2}-\d{2})', content)
                if match:
                    return date.fromisoformat(match.group(1))
            except:
                pass

            self.logger.warning(f"无法从文件名或内容提取日期: {log_path}，使用当天日期")
            return date.today()

    def _chunk_by_sections(self, content: str, log_date: date, log_path: Path) -> List[LogChunk]:
        """按章节分块（## 标题）

        Args:
            content: 文件内容
            log_date: 日志日期
            log_path: 文件路径

        Returns:
            List[LogChunk]: 章节分块列表
        """
        chunks = []
        lines = content.split('\n')
        current_section = []
        current_title = ""
        in_section = False

        for line in lines:
            # 检测章节标题 (## 开头)
            if line.startswith('## '):
                # 保存前一个章节
                if current_section and current_title:
                    chunk_text = '\n'.join(current_section)
                    if chunk_text.strip():
                        metadata = self._extract_metadata_from_section(current_title, chunk_text, log_path)
                        chunks.append(LogChunk(
                            text=chunk_text,
                            metadata=metadata,
                            log_date=log_date,
                            chunk_type="section"
                        ))

                # 开始新章节
                current_title = line[3:].strip()
                current_section = [line]
                in_section = True

            elif in_section:
                current_section.append(line)

        # 处理最后一个章节
        if current_section and current_title:
            chunk_text = '\n'.join(current_section)
            if chunk_text.strip():
                metadata = self._extract_metadata_from_section(current_title, chunk_text, log_path)
                chunks.append(LogChunk(
                    text=chunk_text,
                    metadata=metadata,
                    log_date=log_date,
                    chunk_type="section"
                ))

        return chunks

    def _chunk_by_entries(self, content: str, log_date: date, log_path: Path) -> List[LogChunk]:
        """按条目分块（- 开头的项目符号）

        Args:
            content: 文件内容
            log_date: 日志日期
            log_path: 文件路径

        Returns:
            List[LogChunk]: 条目分块列表
        """
        chunks = []
        lines = content.split('\n')
        current_entry = []
        in_entry = False
        entry_index = 0

        for line in lines:
            # 检测条目开始（- 开头，且不是章节标题）
            if line.strip().startswith('- ') and not line.strip().startswith('##'):
                # 保存前一个条目
                if current_entry and entry_index > 0:
                    chunk_text = '\n'.join(current_entry)
                    if chunk_text.strip():
                        metadata = self._extract_metadata_from_entry(chunk_text, log_path, entry_index)
                        chunks.append(LogChunk(
                            text=chunk_text,
                            metadata=metadata,
                            log_date=log_date,
                            chunk_type="entry"
                        ))

                # 开始新条目
                current_entry = [line]
                in_entry = True
                entry_index += 1

            elif in_entry:
                # 继续当前条目（空行或缩进内容）
                if line.strip() == '' or line.startswith('  ') or line.startswith('\t'):
                    current_entry.append(line)
                else:
                    # 条目结束
                    if current_entry:
                        chunk_text = '\n'.join(current_entry)
                        if chunk_text.strip():
                            metadata = self._extract_metadata_from_entry(chunk_text, log_path, entry_index)
                            chunks.append(LogChunk(
                                text=chunk_text,
                                metadata=metadata,
                                log_date=log_date,
                                chunk_type="entry"
                            ))
                    current_entry = []
                    in_entry = False

        # 处理最后一个条目
        if current_entry:
            chunk_text = '\n'.join(current_entry)
            if chunk_text.strip():
                metadata = self._extract_metadata_from_entry(chunk_text, log_path, entry_index)
                chunks.append(LogChunk(
                    text=chunk_text,
                    metadata=metadata,
                    log_date=log_date,
                    chunk_type="entry"
                ))

        return chunks

    def _chunk_by_sliding_window(self, content: str, log_date: date, log_path: Path) -> List[LogChunk]:
        """滑动窗口分块（处理长文本）

        Args:
            content: 文件内容
            log_date: 日志日期
            log_path: 文件路径

        Returns:
            List[LogChunk]: 滑动窗口分块列表
        """
        chunks = []
        start = 0
        content_length = len(content)

        while start < content_length and len(chunks) < self.max_chunks:
            # 计算块结束位置
            end = min(start + self.chunk_size, content_length)

            # 调整结束位置，避免截断单词或句子
            if end < content_length:
                # 向后查找合适的截断点
                for i in range(end, min(end + 100, content_length)):
                    if content[i] in ['\n', '。', '！', '？', '.', '!', '?', ' ', '\t']:
                        end = i + 1
                        break

            chunk_text = content[start:end].strip()
            if chunk_text:
                metadata = {
                    "source_file": str(log_path),
                    "chunk_type": "window",
                    "window_start": start,
                    "window_end": end,
                    "chunk_size": len(chunk_text)
                }
                chunks.append(LogChunk(
                    text=chunk_text,
                    metadata=metadata,
                    log_date=log_date,
                    chunk_type="window"
                ))

            # 移动窗口，考虑重叠
            start += self.chunk_size - self.chunk_overlap

            # 防止无限循环
            if start <= 0:
                break

        return chunks

    def _extract_metadata_from_section(self, title: str, content: str, log_path: Path) -> Dict[str, Any]:
        """从章节内容提取元数据

        Args:
            title: 章节标题
            content: 章节内容
            log_path: 文件路径

        Returns:
            Dict[str, Any]: 元数据字典
        """
        metadata = {
            "source_file": str(log_path),
            "section_title": title,
            "content_type": "section",
            "extracted_at": datetime.now().isoformat()
        }

        # 尝试从标题提取时间戳
        time_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', title)
        if time_match:
            metadata["timestamp"] = time_match.group(1)

        # 尝试从标题提取类别
        category_match = re.search(r'\]\s*(\w+)', title)
        if category_match:
            metadata["category"] = category_match.group(1)

        # 提取其他可能的信息
        if 'session_id' in content:
            session_match = re.search(r'session_id=([\w_]+)', content)
            if session_match:
                metadata["session_id"] = session_match.group(1)

        if 'query_length' in content:
            length_match = re.search(r'query_length=(\d+)', content)
            if length_match:
                metadata["query_length"] = int(length_match.group(1))

        return metadata

    def _extract_metadata_from_entry(self, content: str, log_path: Path, entry_index: int) -> Dict[str, Any]:
        """从条目内容提取元数据

        Args:
            content: 条目内容
            log_path: 文件路径
            entry_index: 条目索引

        Returns:
            Dict[str, Any]: 元数据字典
        """
        metadata = {
            "source_file": str(log_path),
            "entry_index": entry_index,
            "content_type": "entry",
            "extracted_at": datetime.now().isoformat()
        }

        # 提取条目中的关键信息
        lines = content.split('\n')
        first_line = lines[0] if lines else ""

        # 尝试提取时间戳（如果条目来自有时间戳的章节）
        if '[' in first_line and ']' in first_line:
            time_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', first_line)
            if time_match:
                metadata["timestamp"] = time_match.group(1)

        # 提取类别
        if 'learning' in content.lower():
            metadata["category"] = "learning"
        elif 'error' in content.lower():
            metadata["category"] = "error"
        elif 'decision' in content.lower():
            metadata["category"] = "decision"
        elif 'completion' in content.lower():
            metadata["category"] = "completion"

        # 提取会话ID
        if 'session_id' in content:
            session_match = re.search(r'session_id=([\w_]+)', content)
            if session_match:
                metadata["session_id"] = session_match.group(1)

        return metadata


# 全局日志分块器实例（可选）
_global_log_chunker: Optional[LogChunker] = None


def get_global_log_chunker(config: Optional[Dict[str, Any]] = None) -> LogChunker:
    """获取全局日志分块器实例（单例模式）

    Args:
        config: 配置字典，仅在第一次调用时有效

    Returns:
        LogChunker 实例
    """
    global _global_log_chunker
    if _global_log_chunker is None:
        _global_log_chunker = LogChunker(config)
    return _global_log_chunker


if __name__ == "__main__":
    """模块测试"""
    print("=== LogChunker 模块测试 ===")

    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 创建测试日志内容
    test_log_content = """# 工作日志：2026-04-02

## 系统启动
- 记忆系统初始化完成
- 加载身份定义、工具配置和长期记忆
- 文件记忆管理器已就绪

---

*日志记录开始时间：2026-04-02 00:00:01*

## [00:00:03] memory_consolidation (days_reviewed=7 strategy=rule_based timestamp=2026-04-02T00:00:03.634786)
- 执行记忆整理，回顾了最近 7 天日志

## [00:05:25] learning (session_id=streamlit_session_aca4caee query_length=7 response_length=433 is_important=True)
- 用户查询: 今天天气怎么样... | Agent响应: 今天天气怎么样
为了回答您关于今天天气的问题，我需要先获取您所在的城市位置，因为天气信息是基于具体城市查询的。我将调用工具获取您的位置信息。
长沙
现在我已经获取到您所在的城市是长沙，接下来我将查询长沙今天的天气情况。
城市长沙市天气为中雨，气温18摄氏度，空气湿度未知%，东风1-3级，数据发布时间2026-04-02。
根据查询结果，今天长沙的天气情况如下：

- **天气状况**：中雨
- **温度**：18°C
- **风向风力**：东风1-3级
"""

    # 写入临时测试文件
    test_file = Path("./test_log_2026-04-02.md")
    test_file.write_text(test_log_content, encoding='utf-8')

    try:
        # 创建分块器
        chunker = LogChunker({
            "chunk_size": 300,
            "chunk_overlap": 50,
            "max_chunks_per_file": 10
        })

        # 执行分块
        chunks = chunker.chunk_log_file(test_file)

        print(f"分块结果: {len(chunks)} 个块")
        for i, chunk in enumerate(chunks):
            print(f"\n--- 块 {i+1} ({chunk.chunk_type}) ---")
            print(f"日期: {chunk.log_date}")
            print(f"元数据: {chunk.metadata}")
            print(f"文本预览: {chunk.text[:100]}...")

    finally:
        # 清理临时文件
        if test_file.exists():
            test_file.unlink()

    print("\n测试完成！")