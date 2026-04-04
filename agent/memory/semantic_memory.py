"""
语义记忆（长期记忆）管理器模块 - 基于向量检索的语义记忆系统

本模块提供 SemanticMemory 类，实现基于向量检索的第三层记忆系统（语义检索层）。
基于 ChromaDB 向量存储和 sentence-transformers embedding 模型，支持对历史日志的
语义检索和智能回忆。

核心功能：
1. 日志文件的自动索引和增量更新
2. 基于语义相似度的记忆检索
3. 与现有记忆系统的集成接口
4. 索引状态管理和资源清理

阶段二新增功能：
1. 批量目录索引（index_logs_directory）
2. 增量索引支持（基于 IndexManager）
3. 高级检索功能（日期过滤、类别过滤）
4. 检索结果缓存机制

系统架构：
┌─────────────────────────────────────────┐
│            ReactAgent (主入口)           │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ 短期记忆 │  │ 中期记忆 │  │ 长期记忆 │  │
│  │MemoryMgr│  │FileMemory│  │Semantic │  │
│  └─────────┘  └─────────┘  │ Memory  │  │
│                             └─────────┘  │
│                                  ↓       │
│                            ┌──────────┐  │
│                            │ ChromaDB │  │
│                            │ 向量库   │  │
│                            └──────────┘  │
└─────────────────────────────────────────┘
"""

import os
import time
import json
import hashlib
import concurrent.futures
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
import logging
import threading
from functools import lru_cache

# 预定义导入变量，用于测试mock
Chroma = None
SentenceTransformer = None

try:
    from langchain_chroma import Chroma
    from sentence_transformers import SentenceTransformer
    CHROMA_AVAILABLE = True
except ImportError as e:
    print(f"[SemanticMemory] 警告: 缺少依赖库 {e}")
    print("[SemanticMemory] 请安装: pip install langchain-chroma sentence-transformers")
    CHROMA_AVAILABLE = False

# 预定义日志分块器变量
LogChunker = None

try:
    from agent.memory.memory_chunker import LogChunker
    CHUNKER_AVAILABLE = True
except ImportError:
    CHUNKER_AVAILABLE = False

# 预定义索引管理器变量
IndexManager = None

try:
    from agent.memory.index_manager import IndexManager
    INDEX_MANAGER_AVAILABLE = True
except ImportError:
    INDEX_MANAGER_AVAILABLE = False


@dataclass
class MemoryResult:
    """检索结果数据结构"""
    text: str                    # 原始文本内容
    score: float                 # 相似度分数 (0.0-1.0)
    metadata: Dict[str, Any]     # 元数据
    source_file: str             # 来源文件
    log_date: date               # 日志日期
    chunk_index: int             # 块索引

    def to_context_format(self) -> str:
        """转换为上下文注入格式"""
        date_str = self.log_date.isoformat() if isinstance(self.log_date, date) else str(self.log_date)
        preview = self.text[:200] + "..." if len(self.text) > 200 else self.text
        return f"[{date_str}] {preview}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


class SemanticMemory:
    """语义检索层管理器

    负责管理基于向量检索的长期记忆系统，提供日志索引、语义检索、状态管理等功能。

    阶段二新增功能：
    - 批量目录索引
    - 增量索引支持
    - 高级检索（日期过滤、类别过滤）
    - 检索结果缓存
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化语义记忆管理器

        Args:
            config: 配置字典，包含以下结构：
                enabled: bool - 是否启用
                vector_db: dict - 向量数据库配置
                embedding: dict - embedding模型配置
                indexing: dict - 索引配置
                retrieval: dict - 检索配置
                resources: dict - 资源管理配置
        """
        self.config = config
        self.vector_store = None
        self.embedding_model = None
        self.logger = self._setup_logger()
        self._lock = threading.RLock()

        # 索引状态管理 - 使用新的 IndexManager
        self.index_manager = None
        self._init_index_manager()

        # 兼容旧版本：保留 indexed_files 属性
        self.index_state_file = Path(config.get("index_state_file", "./memory/vector_index_state.json"))
        self.indexed_files = {}  # 将在 _init_index_manager 中初始化

        # 检索缓存
        self._cache_enabled = config.get("retrieval", {}).get("enable_cache", True)
        self._cache_max_size = config.get("retrieval", {}).get("cache_max_size", 100)
        self._search_cache: Dict[str, Tuple[List[MemoryResult], float]] = {}
        self._cache_lock = threading.Lock()

        # 初始化组件
        if CHROMA_AVAILABLE:
            self._initialize_components()
        else:
            self.logger.warning("ChromaDB 依赖不可用，语义记忆功能将受限")

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

    def _init_index_manager(self):
        """初始化索引管理器"""
        if INDEX_MANAGER_AVAILABLE:
            index_config = {
                "force_reindex_days": self.config.get("indexing", {}).get("force_reindex_days", 30),
                "use_file_hash": False,
                "max_indexed_files": self.config.get("resources", {}).get("max_indexed_files", 10000)
            }
            state_file = Path(self.config.get("index_state_file", "./memory/vector_index_state.json"))
            self.index_manager = IndexManager(state_file, index_config)
            self.indexed_files = self.index_manager.indexed_files  # 兼容旧版本
            self.logger.info("索引管理器初始化完成")
        else:
            self.logger.warning("IndexManager 不可用，使用简单索引状态管理")
            self.indexed_files = self._load_index_state()

    def _initialize_components(self):
        """初始化向量存储和 embedding 模型"""
        if not CHROMA_AVAILABLE:
            raise ImportError("缺少必要的依赖库：langchain-chroma 或 sentence-transformers")

        with self._lock:
            try:
                # 初始化 embedding 模型
                embedding_config = self.config.get("embedding", {})
                model_name = embedding_config.get("model_name", "paraphrase-multilingual-MiniLM-L12-v2")
                cache_dir = embedding_config.get("cache_dir", "./models/sentence_transformers")
                device = embedding_config.get("device", "cpu")

                self.logger.info(f"正在加载 embedding 模型: {model_name}")
                self.embedding_model = SentenceTransformer(
                    model_name,
                    cache_folder=cache_dir,
                    device=device
                )
                self.logger.info(f"Embedding 模型加载完成，设备: {device}")

                # 创建自定义 embedding 函数
                def custom_embedding_function(texts: List[str]) -> List[List[float]]:
                    """自定义 embedding 函数，适配 ChromaDB"""
                    embeddings = self.embedding_model.encode(texts)
                    return embeddings.tolist()

                # 初始化向量存储
                vector_db_config = self.config.get("vector_db", {})
                collection_name = vector_db_config.get("collection_name", "agent_memory")
                persist_directory = vector_db_config.get("path", "./memory/vectordb")
                persist = vector_db_config.get("persist", True)

                self.logger.info(f"正在初始化向量存储: {collection_name}")
                self.vector_store = Chroma(
                    collection_name=collection_name,
                    embedding_function=custom_embedding_function,
                    persist_directory=persist_directory,
                )

                # 确保存储目录存在
                Path(persist_directory).mkdir(parents=True, exist_ok=True)

                self.logger.info(f"语义记忆初始化完成，向量库路径: {persist_directory}")

            except Exception as e:
                self.logger.error(f"初始化语义记忆组件失败: {e}")
                raise

    def _load_index_state(self) -> Dict[str, float]:
        """加载索引状态"""
        try:
            if self.index_state_file.exists():
                with open(self.index_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"加载索引状态失败: {e}")
        return {}

    def _save_index_state(self):
        """保存索引状态"""
        try:
            with open(self.index_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.indexed_files, f, indent=2)
        except Exception as e:
            self.logger.error(f"保存索引状态失败: {e}")

    def index_log_file(self, log_path: Path) -> int:
        """索引单个日志文件，返回索引的块数

        Args:
            log_path: 日志文件路径

        Returns:
            int: 索引的块数，失败返回0
        """
        if not CHUNKER_AVAILABLE:
            self.logger.warning("日志分块器不可用，请确保 agent.memory_chunker 模块可用")
            return 0

        if not log_path.exists():
            self.logger.error(f"日志文件不存在: {log_path}")
            return 0

        with self._lock:
            try:
                # 检查是否需要重新索引
                file_mtime = log_path.stat().st_mtime
                if str(log_path) in self.indexed_files and file_mtime <= self.indexed_files[str(log_path)]:
                    self.logger.info(f"文件已是最新，跳过索引: {log_path}")
                    return 0

                # 使用日志分块器分块
                chunker = LogChunker()
                chunks = chunker.chunk_log_file(log_path)

                if not chunks:
                    self.logger.warning(f"文件没有可索引的内容: {log_path}")
                    return 0

                # 准备文档和元数据
                documents = []
                metadatas = []

                for i, chunk in enumerate(chunks):
                    documents.append(chunk.text)
                    metadata = chunk.metadata.copy() if hasattr(chunk, 'metadata') else {}
                    metadata.update({
                        "source_file": str(log_path),
                        "chunk_index": i,
                        "log_date": chunk.log_date.isoformat() if hasattr(chunk, 'log_date') else date.today().isoformat(),
                        "indexed_at": datetime.now().isoformat()
                    })
                    metadatas.append(metadata)

                # 添加到向量存储
                if self.vector_store:
                    ids = [f"{log_path.name}_{i}" for i in range(len(documents))]
                    self.vector_store.add_texts(
                        texts=documents,
                        metadatas=metadatas,
                        ids=ids
                    )

                # 更新索引状态
                self.indexed_files[str(log_path)] = file_mtime
                self._save_index_state()

                self.logger.info(f"成功索引文件 {log_path}，块数: {len(documents)}")
                return len(documents)

            except Exception as e:
                self.logger.error(f"索引文件失败 {log_path}: {e}")
                return 0

    def search(self, query: str, top_k: int = 5,
               min_score: float = 0.0) -> List[MemoryResult]:
        """语义检索相关记忆

        Args:
            query: 查询文本
            top_k: 返回结果数量
            min_score: 最低相似度阈值

        Returns:
            List[MemoryResult]: 检索结果列表
        """
        if not self.vector_store:
            self.logger.warning("向量存储未初始化，无法执行检索")
            return []

        with self._lock:
            try:
                # 执行检索
                results = self.vector_store.similarity_search_with_score(
                    query,
                    k=top_k
                )

                # 转换为 MemoryResult 对象
                memory_results = []
                for doc, score in results:
                    # ChromaDB 返回的分数是距离，转换为相似度（1 - 距离）
                    similarity = 1.0 - score if score <= 1.0 else 1.0 / (1.0 + score)

                    if similarity < min_score:
                        continue

                    # 解析元数据
                    metadata = doc.metadata.copy()
                    source_file = metadata.get("source_file", "unknown")
                    log_date_str = metadata.get("log_date", date.today().isoformat())

                    # 解析日期
                    try:
                        log_date = date.fromisoformat(log_date_str)
                    except (ValueError, TypeError):
                        log_date = date.today()

                    result = MemoryResult(
                        text=doc.page_content,
                        score=similarity,
                        metadata=metadata,
                        source_file=source_file,
                        log_date=log_date,
                        chunk_index=metadata.get("chunk_index", 0)
                    )
                    memory_results.append(result)

                self.logger.info(f"检索查询 '{query[:50]}...' 返回 {len(memory_results)} 个结果")
                return memory_results

            except Exception as e:
                self.logger.error(f"检索失败: {e}")
                return []

    def search_with_context(self, query: str, context: Dict = None) -> str:
        """检索并格式化为上下文文本

        Args:
            query: 查询文本
            context: 附加上下文（未来扩展）

        Returns:
            str: 格式化的上下文文本
        """
        results = self.search(query)

        if not results:
            return "未找到相关记忆。"

        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)

        # 构建上下文
        context_lines = ["## 相关记忆（从历史日志中检索）"]
        for i, result in enumerate(results[:5]):  # 最多5条
            context_lines.append(f"{i+1}. {result.to_context_format()} (相关性: {result.score:.2f})")

        return "\n".join(context_lines)

    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息

        Returns:
            Dict[str, Any]: 统计信息字典
        """
        stats = {
            "enabled": self.vector_store is not None,
            "indexed_files_count": len(self.indexed_files),
            "index_state_file": str(self.index_state_file),
            "config": {
                "embedding_model": self.config.get("embedding", {}).get("model_name", "unknown"),
                "vector_db_path": self.config.get("vector_db", {}).get("path", "unknown"),
            }
        }

        if self.vector_store:
            try:
                # 获取集合信息
                collection = self.vector_store._collection
                if collection:
                    stats["vector_db"] = {
                        "collection_name": collection.name,
                        "count": collection.count(),
                    }
            except Exception as e:
                stats["vector_db_error"] = str(e)

        return stats

    # ==================== 阶段二新增功能 ====================

    def index_logs_directory(self, logs_dir: Path, force_reindex: bool = False,
                             pattern: str = "*.md",
                             progress_callback: Optional[Callable[[int, int, str], None]] = None,
                             max_workers: int = 1) -> Dict[str, Any]:
        """批量索引日志目录

        Args:
            logs_dir: 日志目录路径
            force_reindex: 是否强制重新索引所有文件
            pattern: 文件匹配模式（默认 *.md）
            progress_callback: 进度回调函数 (current, total, message)
            max_workers: 并行工作线程数（默认1，串行处理）

        Returns:
            Dict[str, Any]: 索引结果统计
        """
        result = {
            "total_files": 0,
            "indexed_files": 0,
            "skipped_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "duration_seconds": 0,
            "errors": []
        }

        start_time = time.time()
        logs_dir = Path(logs_dir)

        # 记录初始内存使用情况
        initial_memory = self._get_current_memory_usage()

        if not logs_dir.exists():
            self.logger.error(f"日志目录不存在: {logs_dir}")
            result["errors"].append(f"目录不存在: {logs_dir}")
            return result

        # 获取所有日志文件
        log_files = list(logs_dir.rglob(pattern))
        result["total_files"] = len(log_files)

        self.logger.info(f"开始索引目录 {logs_dir}，共 {len(log_files)} 个文件")
        if progress_callback:
            progress_callback(0, len(log_files), f"发现 {len(log_files)} 个文件")

        # 清理过期的索引条目
        if self.index_manager:
            cleaned = self.index_manager.cleanup_stale_entries(logs_dir)
            if cleaned > 0:
                self.logger.info(f"清理了 {cleaned} 个过期索引条目")

        # 索引文件处理函数
        def index_single_file(file_path: Path) -> Tuple[str, int, str]:
            """索引单个文件"""
            try:
                # 检查是否需要索引
                if not force_reindex and self.index_manager:
                    if not self.index_manager.needs_indexing(file_path):
                        return (str(file_path), 0, "skipped")

                # 执行索引
                chunk_count = self._index_file_internal(file_path)
                return (str(file_path), chunk_count, "indexed")

            except Exception as e:
                return (str(file_path), 0, f"error: {str(e)}")

        # 并行或串行处理
        if max_workers > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(index_single_file, f): f for f in log_files}
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    file_path, chunk_count, status = future.result()

                    if status == "skipped":
                        result["skipped_files"] += 1
                    elif status == "indexed":
                        result["indexed_files"] += 1
                        result["total_chunks"] += chunk_count
                    else:
                        result["failed_files"] += 1
                        result["errors"].append(f"{file_path}: {status}")

                    if progress_callback:
                        progress_callback(i + 1, len(log_files), f"处理 {Path(file_path).name}")
        else:
            # 串行处理
            for i, file_path in enumerate(log_files):
                file_path_str, chunk_count, status = index_single_file(file_path)

                if status == "skipped":
                    result["skipped_files"] += 1
                elif status == "indexed":
                    result["indexed_files"] += 1
                    result["total_chunks"] += chunk_count
                else:
                    result["failed_files"] += 1
                    result["errors"].append(f"{file_path_str}: {status}")

                if progress_callback:
                    progress_callback(i + 1, len(log_files), f"处理 {file_path.name}")

        result["duration_seconds"] = round(time.time() - start_time, 2)

        # 记录结束内存使用情况
        final_memory = self._get_current_memory_usage()
        if initial_memory and final_memory:
            if initial_memory.get("using_psutil") and final_memory.get("using_psutil"):
                memory_delta = final_memory.get("rss_mb", 0) - initial_memory.get("rss_mb", 0)
                result["memory_usage"] = {
                    "initial_rss_mb": initial_memory.get("rss_mb"),
                    "final_rss_mb": final_memory.get("rss_mb"),
                    "delta_mb": round(memory_delta, 2),
                    "final_percent": final_memory.get("percent"),
                    "available_mb": final_memory.get("available_mb")
                }
            else:
                result["memory_usage"] = {
                    "note": "详细内存信息需要安装 psutil 包",
                    "initial": initial_memory,
                    "final": final_memory
                }

        self.logger.info(
            f"索引完成: 总计 {result['total_files']} 文件, "
            f"索引 {result['indexed_files']} 文件, "
            f"跳过 {result['skipped_files']} 文件, "
            f"失败 {result['failed_files']} 文件, "
            f"共 {result['total_chunks']} 块, "
            f"耗时 {result['duration_seconds']} 秒"
        )

        return result

    def _index_file_internal(self, log_path: Path) -> int:
        """内部方法：索引单个文件（不带锁，用于批量索引）

        Args:
            log_path: 日志文件路径

        Returns:
            int: 索引的块数
        """
        if not CHUNKER_AVAILABLE:
            raise ImportError("日志分块器不可用")

        if not log_path.exists():
            raise FileNotFoundError(f"文件不存在: {log_path}")

        # 使用日志分块器分块
        chunker = LogChunker(self.config.get("indexing", {}))
        chunks = chunker.chunk_log_file(log_path)

        if not chunks:
            return 0

        # 准备文档和元数据
        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            documents.append(chunk.text)
            metadata = chunk.metadata.copy() if hasattr(chunk, 'metadata') else {}
            metadata.update({
                "source_file": str(log_path),
                "chunk_index": i,
                "log_date": chunk.log_date.isoformat() if hasattr(chunk, 'log_date') else date.today().isoformat(),
                "indexed_at": datetime.now().isoformat()
            })
            metadatas.append(metadata)
            ids.append(f"{log_path.name}_{i}")

        # 添加到向量存储
        if self.vector_store:
            self.vector_store.add_texts(
                texts=documents,
                metadatas=metadatas,
                ids=ids
            )

        # 更新索引状态
        if self.index_manager:
            self.index_manager.mark_indexed(log_path, len(documents))
        else:
            self.indexed_files[str(log_path)] = log_path.stat().st_mtime
            self._save_index_state()

        return len(documents)

    def search_advanced(self, query: str,
                        top_k: int = 5,
                        min_score: float = 0.0,
                        date_filter: Optional[Tuple[date, date]] = None,
                        category_filter: Optional[List[str]] = None,
                        source_filter: Optional[str] = None) -> List[MemoryResult]:
        """高级语义检索（支持过滤）

        Args:
            query: 查询文本
            top_k: 返回结果数量
            min_score: 最低相似度阈值
            date_filter: 日期范围过滤 (start_date, end_date)
            category_filter: 类别过滤列表（如 ["learning", "error"]）
            source_filter: 来源文件过滤（部分匹配）

        Returns:
            List[MemoryResult]: 检索结果列表
        """
        if not self.vector_store:
            self.logger.warning("向量存储未初始化，无法执行检索")
            return []

        # 检查缓存
        cache_key = self._make_cache_key(query, top_k, min_score, date_filter, category_filter, source_filter)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            self.logger.debug(f"使用缓存结果: {query[:30]}...")
            return cached_result

        with self._lock:
            try:
                # 构建过滤条件
                where_filter = None
                if date_filter or category_filter or source_filter:
                    where_filter = self._build_where_filter(date_filter, category_filter, source_filter)

                # 执行检索
                if where_filter:
                    results = self.vector_store.similarity_search_with_score(
                        query,
                        k=top_k * 2,  # 获取更多结果以便过滤
                        filter=where_filter
                    )
                else:
                    results = self.vector_store.similarity_search_with_score(
                        query,
                        k=top_k
                    )

                # 转换和过滤结果
                memory_results = []
                for doc, score in results:
                    # 转换相似度
                    similarity = 1.0 - score if score <= 1.0 else 1.0 / (1.0 + score)

                    if similarity < min_score:
                        continue

                    # 解析元数据
                    metadata = doc.metadata.copy()
                    source_file = metadata.get("source_file", "unknown")
                    log_date_str = metadata.get("log_date", date.today().isoformat())

                    # 解析日期
                    try:
                        log_date = date.fromisoformat(log_date_str)
                    except (ValueError, TypeError):
                        log_date = date.today()

                    result = MemoryResult(
                        text=doc.page_content,
                        score=similarity,
                        metadata=metadata,
                        source_file=source_file,
                        log_date=log_date,
                        chunk_index=metadata.get("chunk_index", 0)
                    )

                    memory_results.append(result)

                # 按分数排序并截取
                memory_results.sort(key=lambda x: x.score, reverse=True)
                memory_results = memory_results[:top_k]

                # 缓存结果
                self._add_to_cache(cache_key, memory_results)

                self.logger.info(f"高级检索 '{query[:50]}...' 返回 {len(memory_results)} 个结果")
                return memory_results

            except Exception as e:
                self.logger.error(f"高级检索失败: {e}")
                return []

    def _build_where_filter(self, date_filter: Optional[Tuple[date, date]],
                            category_filter: Optional[List[str]],
                            source_filter: Optional[str]) -> Dict[str, Any]:
        """构建 ChromaDB where 过滤条件

        Args:
            date_filter: 日期范围过滤
            category_filter: 类别过滤
            source_filter: 来源文件过滤

        Returns:
            Dict[str, Any]: 过滤条件字典
        """
        conditions = []

        # 日期过滤（使用 $and 因为需要同时满足两个条件）
        if date_filter:
            start_date, end_date = date_filter
            conditions.append({"log_date": {"$gte": start_date.isoformat()}})
            conditions.append({"log_date": {"$lte": end_date.isoformat()}})

        # 类别过滤
        if category_filter:
            if len(category_filter) == 1:
                conditions.append({"category": category_filter[0]})
            else:
                conditions.append({"category": {"$in": category_filter}})

        # 来源文件过滤
        if source_filter:
            conditions.append({"source_file": {"$contains": source_filter}})

        # 组合条件
        if len(conditions) == 0:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _make_cache_key(self, *args) -> str:
        """生成缓存键"""
        key_str = str(args)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[List[MemoryResult]]:
        """从缓存获取结果"""
        if not self._cache_enabled:
            return None

        with self._cache_lock:
            if cache_key in self._search_cache:
                results, timestamp = self._search_cache[cache_key]
                # 缓存有效期 5 分钟
                if time.time() - timestamp < 300:
                    return results
                else:
                    del self._search_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, results: List[MemoryResult]):
        """添加结果到缓存"""
        if not self._cache_enabled:
            return

        with self._cache_lock:
            # 清理过期缓存
            if len(self._search_cache) >= self._cache_max_size:
                # 移除最旧的缓存项
                oldest_key = min(self._search_cache.keys(),
                                key=lambda k: self._search_cache[k][1])
                del self._search_cache[oldest_key]

            self._search_cache[cache_key] = (results, time.time())

    def clear_cache(self):
        """清空检索缓存"""
        with self._cache_lock:
            self._search_cache.clear()
            self.logger.info("检索缓存已清空")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._cache_lock:
            return {
                "enabled": self._cache_enabled,
                "size": len(self._search_cache),
                "max_size": self._cache_max_size
            }

    def search_with_date_range(self, query: str,
                               start_date: date,
                               end_date: date,
                               top_k: int = 5,
                               min_score: float = 0.0) -> List[MemoryResult]:
        """按日期范围检索

        Args:
            query: 查询文本
            start_date: 开始日期
            end_date: 结束日期
            top_k: 返回结果数量
            min_score: 最低相似度阈值

        Returns:
            List[MemoryResult]: 检索结果列表
        """
        return self.search_advanced(
            query=query,
            top_k=top_k,
            min_score=min_score,
            date_filter=(start_date, end_date)
        )

    def search_by_category(self, query: str,
                           categories: List[str],
                           top_k: int = 5,
                           min_score: float = 0.0) -> List[MemoryResult]:
        """按类别检索

        Args:
            query: 查询文本
            categories: 类别列表（如 ["learning", "error", "decision"]）
            top_k: 返回结果数量
            min_score: 最低相似度阈值

        Returns:
            List[MemoryResult]: 检索结果列表
        """
        return self.search_advanced(
            query=query,
            top_k=top_k,
            min_score=min_score,
            category_filter=categories
        )

    def get_index_status(self) -> Dict[str, Any]:
        """获取详细索引状态

        Returns:
            Dict[str, Any]: 索引状态信息
        """
        status = {
            "vector_store": {
                "enabled": self.vector_store is not None,
                "collection_name": None,
                "document_count": 0
            },
            "index_manager": {
                "enabled": self.index_manager is not None,
                "indexed_files": 0,
                "total_chunks": 0
            },
            "cache": self.get_cache_stats()
        }

        # 向量存储信息
        if self.vector_store:
            try:
                collection = self.vector_store._collection
                if collection:
                    status["vector_store"]["collection_name"] = collection.name
                    status["vector_store"]["document_count"] = collection.count()
            except Exception as e:
                status["vector_store"]["error"] = str(e)

        # 索引管理器信息
        if self.index_manager:
            manager_stats = self.index_manager.get_stats()
            status["index_manager"]["indexed_files"] = manager_stats.get("total_indexed_files", 0)
            status["index_manager"]["total_chunks"] = manager_stats.get("total_chunks", 0)
            status["index_manager"]["last_index_time"] = manager_stats.get("last_index_time")
        else:
            status["index_manager"]["indexed_files"] = len(self.indexed_files)

        return status

    def cleanup_old_indices(self, max_age_days: int = 90):
        """清理过期索引（基于日志日期）

        Args:
            max_age_days: 最大保留天数

        Returns:
            Dict[str, Any]: 清理结果统计
        """
        if not self.vector_store:
            self.logger.warning("向量存储未初始化，无法清理索引")
            return {"success": False, "reason": "向量存储未初始化"}

        result = {
            "success": True,
            "max_age_days": max_age_days,
            "deleted_count": 0,
            "deleted_files": [],
            "errors": []
        }

        try:
            # 计算截止日期
            cutoff_date = date.today() - timedelta(days=max_age_days)
            cutoff_date_str = cutoff_date.isoformat()

            self.logger.info(f"开始清理过期索引，保留最近 {max_age_days} 天数据，截止日期: {cutoff_date_str}")

            # 构建过滤条件：删除 log_date 早于截止日期的文档
            where_filter = {"log_date": {"$lt": cutoff_date_str}}

            # 首先获取要删除的文档信息（用于日志记录）
            try:
                # 尝试使用相似度搜索获取匹配文档（不限制数量）
                # 注意：这里可能需要更高效的方法，取决于ChromaDB的API
                old_docs = self.vector_store.get(where=where_filter)

                if old_docs and old_docs.get("ids"):
                    old_count = len(old_docs["ids"])
                    self.logger.info(f"找到 {old_count} 个过期文档（早于 {cutoff_date_str}）")

                    # 收集要删除的文件列表（去重）
                    source_files = set()
                    if old_docs.get("metadatas"):
                        for metadata in old_docs["metadatas"]:
                            if metadata and "source_file" in metadata:
                                source_files.add(metadata["source_file"])

                    result["deleted_files"] = list(source_files)

                    # 删除文档
                    deleted_ids = old_docs["ids"]
                    if deleted_ids:
                        self.vector_store.delete(ids=deleted_ids)
                        result["deleted_count"] = len(deleted_ids)

                        # 更新索引状态：移除已删除文件的索引条目
                        if self.index_manager:
                            for file_path in source_files:
                                self.index_manager.remove_indexed(Path(file_path))
                        else:
                            # 兼容旧版本：从 indexed_files 中移除
                            for file_path in source_files:
                                if file_path in self.indexed_files:
                                    del self.indexed_files[file_path]
                            self._save_index_state()

                        self.logger.info(f"成功删除 {len(deleted_ids)} 个过期文档，涉及 {len(source_files)} 个文件")
                else:
                    self.logger.info("未找到过期文档")

            except Exception as e:
                # 如果 get 方法不可用，尝试直接删除
                self.logger.warning(f"获取过期文档信息失败，尝试直接删除: {e}")
                result["errors"].append(f"获取文档信息失败: {e}")

                # 尝试直接删除
                try:
                    # 注意：某些ChromaDB版本可能支持 where 条件删除
                    self.vector_store.delete(where=where_filter)
                    self.logger.info(f"已通过 where 条件删除过期文档")
                except Exception as delete_error:
                    error_msg = f"删除过期文档失败: {delete_error}"
                    self.logger.error(error_msg)
                    result["errors"].append(error_msg)
                    result["success"] = False

        except Exception as e:
            error_msg = f"清理过期索引失败: {e}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False

        return result

    def _get_current_memory_usage(self) -> Dict[str, Any]:
        """获取当前内存使用情况（简化版）

        Returns:
            Dict[str, Any]: 内存使用信息
        """
        try:
            # 尝试使用 psutil 获取详细内存信息
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()

                return {
                    "rss_mb": round(memory_info.rss / (1024 * 1024), 2),
                    "vms_mb": round(memory_info.vms / (1024 * 1024), 2),
                    "percent": round(process.memory_percent(), 2),
                    "available_mb": round(psutil.virtual_memory().available / (1024 * 1024), 2),
                    "total_mb": round(psutil.virtual_memory().total / (1024 * 1024), 2),
                    "using_psutil": True
                }
            except ImportError:
                # psutil 不可用，返回简单信息
                return {
                    "using_psutil": False,
                    "note": "安装 psutil 包获取详细内存信息",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def get_resource_usage(self) -> Dict[str, Any]:
        """获取系统资源使用情况

        返回内存、CPU、向量库大小等资源使用统计。

        Returns:
            Dict[str, Any]: 资源使用统计
        """
        resource_info = {
            "timestamp": datetime.now().isoformat(),
            "memory_usage": {},
            "vector_db": {},
            "cache": self.get_cache_stats(),
            "index": self.get_index_status()
        }

        try:
            # 尝试导入 psutil 获取详细内存信息
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()

                resource_info["memory_usage"] = {
                    "rss_mb": round(memory_info.rss / (1024 * 1024), 2),
                    "vms_mb": round(memory_info.vms / (1024 * 1024), 2),
                    "percent": round(process.memory_percent(), 2),
                    "available_mb": round(psutil.virtual_memory().available / (1024 * 1024), 2),
                    "total_mb": round(psutil.virtual_memory().total / (1024 * 1024), 2)
                }
            except ImportError:
                # psutil 不可用，使用简单方法
                resource_info["memory_usage"] = {
                    "psutil_not_available": True,
                    "note": "安装 psutil 包获取详细内存信息"
                }

            # 向量库大小信息
            if self.vector_store:
                try:
                    vector_db_path = self.config.get("vector_db", {}).get("path", "./memory/vectordb")
                    if Path(vector_db_path).exists():
                        # 计算目录大小
                        total_size = 0
                        for file_path in Path(vector_db_path).rglob("*"):
                            if file_path.is_file():
                                total_size += file_path.stat().st_size

                        resource_info["vector_db"] = {
                            "path": vector_db_path,
                            "size_mb": round(total_size / (1024 * 1024), 2),
                            "exists": True
                        }
                    else:
                        resource_info["vector_db"] = {
                            "path": vector_db_path,
                            "exists": False
                        }
                except Exception as e:
                    resource_info["vector_db"] = {
                        "error": str(e)
                    }

        except Exception as e:
            resource_info["error"] = f"获取资源使用信息失败: {e}"

        return resource_info

    def __del__(self):
        """清理资源"""
        try:
            if self.vector_store:
                # ChromaDB 会自动持久化
                pass
        except:
            pass


# 全局语义记忆管理器实例（可选）
_global_semantic_memory: Optional[SemanticMemory] = None


def get_global_semantic_memory(config: Optional[Dict[str, Any]] = None) -> SemanticMemory:
    """获取全局语义记忆管理器实例（单例模式）

    Args:
        config: 配置字典，仅在第一次调用时有效

    Returns:
        SemanticMemory 实例
    """
    global _global_semantic_memory
    if _global_semantic_memory is None:
        if config is None:
            # 尝试从配置文件加载
            try:
                from utils.config_handler import agent_conf
                config = agent_conf.get("semantic_memory", {})
            except ImportError:
                config = {}

        _global_semantic_memory = SemanticMemory(config)

    return _global_semantic_memory


if __name__ == "__main__":
    """模块测试"""
    print("=== SemanticMemory 模块测试 ===")

    # 测试配置
    test_config = {
        "enabled": True,
        "vector_db": {
            "path": "./memory/vectordb_test",
            "collection_name": "test_memory",
            "persist": True
        },
        "embedding": {
            "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
            "device": "cpu",
            "cache_dir": "./models/sentence_transformers"
        },
        "indexing": {
            "chunk_size": 500,
            "chunk_overlap": 50,
            "max_chunks_per_file": 100
        },
        "retrieval": {
            "default_top_k": 5,
            "min_similarity_score": 0.3
        }
    }

    # 创建语义记忆管理器
    try:
        sm = SemanticMemory(test_config)
        print(f"语义记忆初始化: {'成功' if sm.vector_store else '部分成功'}")

        # 获取统计信息
        stats = sm.get_stats()
        print("统计信息:")
        for key, value in stats.items():
            if key != "config":
                print(f"  {key}: {value}")

        # 测试检索（空向量库）
        results = sm.search("测试查询")
        print(f"测试检索结果数量: {len(results)}")

    except Exception as e:
        print(f"语义记忆测试失败: {e}")

    print("\n测试完成！")