"""
索引状态管理器模块

本模块提供 IndexManager 类，用于管理语义记忆系统的索引状态。
支持增量索引、状态持久化、索引验证等功能。

主要功能：
1. 跟踪已索引文件的状态（文件路径、最后修改时间、索引时间）
2. 判断文件是否需要重新索引
3. 支持索引状态的持久化存储
4. 提供索引统计和清理功能
"""

import json
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict, field
import logging


@dataclass
class IndexEntry:
    """索引条目数据结构"""
    file_path: str              # 文件路径
    file_mtime: float           # 文件最后修改时间（时间戳）
    indexed_at: float           # 索引时间（时间戳）
    chunk_count: int            # 索引的块数
    file_hash: str = ""         # 文件内容哈希（可选，用于精确检测变化）
    error: str = ""             # 最后一次索引错误（如果有）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndexEntry':
        """从字典创建"""
        return cls(**data)

    def is_expired(self, max_age_days: int = 30) -> bool:
        """检查索引是否过期

        Args:
            max_age_days: 最大索引天数

        Returns:
            bool: 是否过期
        """
        indexed_time = datetime.fromtimestamp(self.indexed_at)
        expiry_time = indexed_time + timedelta(days=max_age_days)
        return datetime.now() > expiry_time


class IndexManager:
    """索引状态管理器

    负责管理语义记忆系统的索引状态，支持增量索引和状态持久化。
    """

    def __init__(self, state_file: Path, config: Optional[Dict[str, Any]] = None):
        """初始化索引管理器

        Args:
            state_file: 状态文件路径
            config: 配置字典，支持以下键：
                force_reindex_days: 强制重新索引的天数（默认30）
                use_file_hash: 是否使用文件哈希检测变化（默认False）
                max_indexed_files: 最大索引文件数（默认10000）
        """
        self.state_file = Path(state_file)
        self.config = config or {}
        self.force_reindex_days = self.config.get("force_reindex_days", 30)
        self.use_file_hash = self.config.get("use_file_hash", False)
        self.max_indexed_files = self.config.get("max_indexed_files", 10000)

        self.logger = self._setup_logger()
        self._lock = threading.RLock()

        # 索引状态：{文件路径: IndexEntry}
        self.indexed_files: Dict[str, IndexEntry] = {}

        # 索引统计
        self.stats = {
            "total_indexed": 0,
            "total_chunks": 0,
            "total_errors": 0,
            "last_index_time": None
        }

        # 加载状态
        self._load_state()

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _load_state(self):
        """从文件加载索引状态"""
        with self._lock:
            try:
                if self.state_file.exists():
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 加载索引条目
                    for path, entry_data in data.get("indexed_files", {}).items():
                        self.indexed_files[path] = IndexEntry.from_dict(entry_data)

                    # 加载统计信息
                    self.stats = data.get("stats", self.stats)

                    self.logger.info(f"已加载索引状态: {len(self.indexed_files)} 个文件")

            except Exception as e:
                self.logger.error(f"加载索引状态失败: {e}")
                self.indexed_files = {}

    def _save_state(self):
        """保存索引状态到文件"""
        with self._lock:
            try:
                # 确保目录存在
                self.state_file.parent.mkdir(parents=True, exist_ok=True)

                # 构建保存数据
                data = {
                    "indexed_files": {
                        path: entry.to_dict()
                        for path, entry in self.indexed_files.items()
                    },
                    "stats": self.stats,
                    "last_saved": datetime.now().isoformat()
                }

                # 写入文件
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                self.logger.debug(f"已保存索引状态: {len(self.indexed_files)} 个文件")

            except Exception as e:
                self.logger.error(f"保存索引状态失败: {e}")

    def needs_indexing(self, file_path: Path) -> bool:
        """检查文件是否需要索引

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否需要索引
        """
        with self._lock:
            file_path_str = str(file_path)

            # 检查是否已索引
            if file_path_str not in self.indexed_files:
                self.logger.debug(f"文件未索引: {file_path}")
                return True

            entry = self.indexed_files[file_path_str]

            # 检查是否有错误需要重试
            if entry.error:
                self.logger.debug(f"文件有错误需要重试: {file_path}")
                return True

            # 检查文件是否被修改
            try:
                file_mtime = file_path.stat().st_mtime
                if file_mtime > entry.file_mtime:
                    self.logger.debug(f"文件已修改: {file_path}")
                    return True
            except FileNotFoundError:
                # 文件不存在，从索引中移除
                self.logger.warning(f"文件不存在: {file_path}")
                return False

            # 检查索引是否过期
            if entry.is_expired(self.force_reindex_days):
                self.logger.debug(f"索引已过期: {file_path}")
                return True

            # 使用文件哈希精确检测（如果启用）
            if self.use_file_hash:
                try:
                    current_hash = self._compute_file_hash(file_path)
                    if current_hash != entry.file_hash:
                        self.logger.debug(f"文件内容已变化: {file_path}")
                        return True
                except Exception as e:
                    self.logger.warning(f"计算文件哈希失败: {e}")

            return False

    def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件内容哈希

        Args:
            file_path: 文件路径

        Returns:
            str: 文件哈希值
        """
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def mark_indexed(self, file_path: Path, chunk_count: int, error: str = ""):
        """标记文件已索引

        Args:
            file_path: 文件路径
            chunk_count: 索引的块数
            error: 错误信息（如果有）
        """
        with self._lock:
            try:
                file_path_str = str(file_path)
                file_mtime = file_path.stat().st_mtime

                # 计算文件哈希（如果启用）
                file_hash = ""
                if self.use_file_hash:
                    try:
                        file_hash = self._compute_file_hash(file_path)
                    except Exception:
                        pass

                # 创建索引条目
                entry = IndexEntry(
                    file_path=file_path_str,
                    file_mtime=file_mtime,
                    indexed_at=datetime.now().timestamp(),
                    chunk_count=chunk_count,
                    file_hash=file_hash,
                    error=error
                )

                self.indexed_files[file_path_str] = entry

                # 更新统计
                self.stats["total_indexed"] = len(self.indexed_files)
                self.stats["total_chunks"] = sum(
                    e.chunk_count for e in self.indexed_files.values()
                )
                if error:
                    self.stats["total_errors"] += 1
                self.stats["last_index_time"] = datetime.now().isoformat()

                # 保存状态
                self._save_state()

                self.logger.debug(f"已标记索引: {file_path}, 块数: {chunk_count}")

            except Exception as e:
                self.logger.error(f"标记索引失败: {e}")

    def remove_indexed(self, file_path: Path):
        """从索引中移除文件

        Args:
            file_path: 文件路径
        """
        with self._lock:
            file_path_str = str(file_path)
            if file_path_str in self.indexed_files:
                del self.indexed_files[file_path_str]
                self._save_state()
                self.logger.info(f"已从索引移除: {file_path}")

    def get_indexed_files(self) -> List[str]:
        """获取所有已索引文件列表

        Returns:
            List[str]: 文件路径列表
        """
        with self._lock:
            return list(self.indexed_files.keys())

    def get_missing_files(self, directory: Path, pattern: str = "*.md") -> List[Path]:
        """获取目录中未索引的文件

        Args:
            directory: 目录路径
            pattern: 文件匹配模式

        Returns:
            List[Path]: 未索引的文件列表
        """
        with self._lock:
            missing = []
            for file_path in directory.rglob(pattern):
                if self.needs_indexing(file_path):
                    missing.append(file_path)
            return missing

    def get_stale_files(self, directory: Path) -> List[str]:
        """获取索引中但已不存在的文件

        Args:
            directory: 目录路径（用于过滤）

        Returns:
            List[str]: 过期文件路径列表
        """
        with self._lock:
            stale = []
            dir_str = str(directory)
            for file_path in self.indexed_files:
                if file_path.startswith(dir_str):
                    if not Path(file_path).exists():
                        stale.append(file_path)
            return stale

    def cleanup_stale_entries(self, directory: Path) -> int:
        """清理不存在的索引条目

        Args:
            directory: 目录路径

        Returns:
            int: 清理的条目数
        """
        with self._lock:
            stale_files = self.get_stale_files(directory)
            for file_path in stale_files:
                del self.indexed_files[file_path]

            if stale_files:
                self._save_state()
                self.logger.info(f"清理了 {len(stale_files)} 个过期索引条目")

            return len(stale_files)

    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息

        Returns:
            Dict[str, Any]: 统计信息字典
        """
        with self._lock:
            stats = {
                "total_indexed_files": len(self.indexed_files),
                "total_chunks": self.stats["total_chunks"],
                "total_errors": self.stats["total_errors"],
                "last_index_time": self.stats["last_index_time"],
                "state_file": str(self.state_file),
                "config": {
                    "force_reindex_days": self.force_reindex_days,
                    "use_file_hash": self.use_file_hash
                }
            }

            # 计算索引大小
            if self.state_file.exists():
                stats["state_file_size"] = self.state_file.stat().st_size

            return stats

    def reset(self):
        """重置索引状态"""
        with self._lock:
            self.indexed_files.clear()
            self.stats = {
                "total_indexed": 0,
                "total_chunks": 0,
                "total_errors": 0,
                "last_index_time": None
            }
            self._save_state()
            self.logger.info("索引状态已重置")

    def export_state(self) -> Dict[str, Any]:
        """导出索引状态

        Returns:
            Dict[str, Any]: 索引状态字典
        """
        with self._lock:
            return {
                "indexed_files": {
                    path: entry.to_dict()
                    for path, entry in self.indexed_files.items()
                },
                "stats": self.stats.copy()
            }

    def import_state(self, state: Dict[str, Any], merge: bool = True):
        """导入索引状态

        Args:
            state: 索引状态字典
            merge: 是否合并到现有状态（True）或替换（False）
        """
        with self._lock:
            if not merge:
                self.indexed_files.clear()

            for path, entry_data in state.get("indexed_files", {}).items():
                self.indexed_files[path] = IndexEntry.from_dict(entry_data)

            # 更新统计
            self.stats["total_indexed"] = len(self.indexed_files)
            self.stats["total_chunks"] = sum(
                e.chunk_count for e in self.indexed_files.values()
            )

            self._save_state()
            self.logger.info(f"已导入 {len(state.get('indexed_files', {}))} 个索引条目")


# 全局索引管理器实例
_global_index_manager: Optional[IndexManager] = None


def get_global_index_manager(state_file: Optional[Path] = None,
                              config: Optional[Dict[str, Any]] = None) -> IndexManager:
    """获取全局索引管理器实例（单例模式）

    Args:
        state_file: 状态文件路径，仅在第一次调用时有效
        config: 配置字典

    Returns:
        IndexManager 实例
    """
    global _global_index_manager
    if _global_index_manager is None:
        if state_file is None:
            state_file = Path("./memory/vector_index_state.json")
        _global_index_manager = IndexManager(state_file, config)
    return _global_index_manager


if __name__ == "__main__":
    """模块测试"""
    print("=== IndexManager 模块测试 ===")

    import tempfile
    import shutil

    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # 创建测试配置
        state_file = temp_dir / "index_state.json"
        config = {
            "force_reindex_days": 30,
            "use_file_hash": True
        }

        # 创建索引管理器
        manager = IndexManager(state_file, config)

        # 创建测试文件
        test_file = temp_dir / "test_log.md"
        test_file.write_text("# 测试日志\n\n## 章节1\n- 条目1", encoding='utf-8')

        # 测试 needs_indexing
        print(f"文件需要索引: {manager.needs_indexing(test_file)}")

        # 标记已索引
        manager.mark_indexed(test_file, chunk_count=5)

        # 测试 needs_indexing
        print(f"文件需要索引（已索引）: {manager.needs_indexing(test_file)}")

        # 获取统计
        stats = manager.get_stats()
        print(f"统计信息: {stats}")

        # 修改文件并重新检查
        test_file.write_text("# 修改后的日志\n\n## 新章节\n- 新条目", encoding='utf-8')
        print(f"文件需要索引（已修改）: {manager.needs_indexing(test_file)}")

        # 测试导出/导入
        exported = manager.export_state()
        print(f"导出状态: {len(exported['indexed_files'])} 个文件")

        # 重置并导入
        manager.reset()
        manager.import_state(exported)
        print(f"导入后: {len(manager.indexed_files)} 个文件")

        print("\n测试完成！")

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
