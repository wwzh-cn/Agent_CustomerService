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
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging
import threading

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

        # 索引状态管理
        self.index_state_file = Path(config.get("index_state_file", "./memory/vector_index_state.json"))
        self.indexed_files = self._load_index_state()

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

    def cleanup_old_indices(self, max_age_days: int = 90):
        """清理过期索引（基于日志日期）

        Args:
            max_age_days: 最大保留天数
        """
        # TODO: 实现基于日期的索引清理
        self.logger.info(f"清理过期索引功能待实现 (max_age_days={max_age_days})")

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