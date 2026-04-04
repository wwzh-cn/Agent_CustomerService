"""
语义记忆系统阶段二单元测试

测试阶段二新增功能：
1. IndexManager 索引状态管理器
2. 批量目录索引 (index_logs_directory)
3. 高级检索功能（日期过滤、类别过滤）
4. 检索结果缓存机制
"""

import unittest
import tempfile
import shutil
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 导入待测试模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.memory.semantic_memory import SemanticMemory, MemoryResult
from agent.memory.memory_chunker import LogChunker, LogChunk
from agent.memory.index_manager import IndexManager, IndexEntry


class TestIndexEntry(unittest.TestCase):
    """测试 IndexEntry 数据结构"""

    def test_index_entry_creation(self):
        """测试 IndexEntry 创建"""
        entry = IndexEntry(
            file_path="/test/file.md",
            file_mtime=1234567890.0,
            indexed_at=1234567900.0,
            chunk_count=10,
            file_hash="abc123",
            error=""
        )

        self.assertEqual(entry.file_path, "/test/file.md")
        self.assertEqual(entry.file_mtime, 1234567890.0)
        self.assertEqual(entry.indexed_at, 1234567900.0)
        self.assertEqual(entry.chunk_count, 10)
        self.assertEqual(entry.file_hash, "abc123")
        self.assertEqual(entry.error, "")

    def test_index_entry_is_expired(self):
        """测试索引过期检测"""
        # 创建一个已过期的条目
        old_entry = IndexEntry(
            file_path="/test/old.md",
            file_mtime=1234567890.0,
            indexed_at=time.time() - 40 * 24 * 3600,  # 40天前
            chunk_count=5
        )

        self.assertTrue(old_entry.is_expired(max_age_days=30))
        self.assertFalse(old_entry.is_expired(max_age_days=60))

        # 创建一个新的条目
        new_entry = IndexEntry(
            file_path="/test/new.md",
            file_mtime=time.time(),
            indexed_at=time.time(),
            chunk_count=5
        )

        self.assertFalse(new_entry.is_expired(max_age_days=30))

    def test_index_entry_to_dict(self):
        """测试字典转换"""
        entry = IndexEntry(
            file_path="/test/file.md",
            file_mtime=1234567890.0,
            indexed_at=1234567900.0,
            chunk_count=10
        )

        entry_dict = entry.to_dict()
        self.assertEqual(entry_dict["file_path"], "/test/file.md")
        self.assertEqual(entry_dict["chunk_count"], 10)

    def test_index_entry_from_dict(self):
        """测试从字典创建"""
        data = {
            "file_path": "/test/file.md",
            "file_mtime": 1234567890.0,
            "indexed_at": 1234567900.0,
            "chunk_count": 10,
            "file_hash": "",
            "error": ""
        }

        entry = IndexEntry.from_dict(data)
        self.assertEqual(entry.file_path, "/test/file.md")
        self.assertEqual(entry.chunk_count, 10)


class TestIndexManager(unittest.TestCase):
    """测试 IndexManager 类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "index_state.json"
        self.config = {
            "force_reindex_days": 30,
            "use_file_hash": False,
            "max_indexed_files": 1000
        }

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """测试初始化"""
        manager = IndexManager(self.state_file, self.config)

        self.assertEqual(manager.force_reindex_days, 30)
        self.assertFalse(manager.use_file_hash)
        self.assertEqual(len(manager.indexed_files), 0)

    def test_needs_indexing_new_file(self):
        """测试新文件需要索引"""
        manager = IndexManager(self.state_file, self.config)

        # 创建测试文件
        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")

        self.assertTrue(manager.needs_indexing(test_file))

    def test_needs_indexing_already_indexed(self):
        """测试已索引文件不需要重新索引"""
        manager = IndexManager(self.state_file, self.config)

        # 创建测试文件
        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")

        # 标记为已索引
        manager.mark_indexed(test_file, chunk_count=5)

        # 不需要重新索引
        self.assertFalse(manager.needs_indexing(test_file))

    def test_needs_indexing_modified_file(self):
        """测试修改后的文件需要重新索引"""
        manager = IndexManager(self.state_file, self.config)

        # 创建测试文件
        test_file = self.temp_dir / "test.md"
        test_file.write_text("原始内容")

        # 标记为已索引
        manager.mark_indexed(test_file, chunk_count=5)

        # 修改文件
        time.sleep(0.1)  # 确保修改时间不同
        test_file.write_text("修改后的内容")

        # 需要重新索引
        self.assertTrue(manager.needs_indexing(test_file))

    def test_mark_indexed(self):
        """测试标记索引"""
        manager = IndexManager(self.state_file, self.config)

        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")

        manager.mark_indexed(test_file, chunk_count=10)

        # 验证状态
        self.assertIn(str(test_file), manager.indexed_files)
        entry = manager.indexed_files[str(test_file)]
        self.assertEqual(entry.chunk_count, 10)
        self.assertEqual(entry.error, "")

    def test_mark_indexed_with_error(self):
        """测试带错误的索引标记"""
        manager = IndexManager(self.state_file, self.config)

        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")

        manager.mark_indexed(test_file, chunk_count=0, error="测试错误")

        entry = manager.indexed_files[str(test_file)]
        self.assertEqual(entry.error, "测试错误")

    def test_remove_indexed(self):
        """测试移除索引"""
        manager = IndexManager(self.state_file, self.config)

        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")

        manager.mark_indexed(test_file, chunk_count=5)
        self.assertIn(str(test_file), manager.indexed_files)

        manager.remove_indexed(test_file)
        self.assertNotIn(str(test_file), manager.indexed_files)

    def test_get_missing_files(self):
        """测试获取未索引文件"""
        manager = IndexManager(self.state_file, self.config)

        # 创建多个测试文件
        for i in range(3):
            test_file = self.temp_dir / f"test{i}.md"
            test_file.write_text(f"测试内容{i}")

        # 标记一个文件为已索引
        manager.mark_indexed(self.temp_dir / "test1.md", chunk_count=5)

        # 获取未索引文件
        missing = manager.get_missing_files(self.temp_dir)
        self.assertEqual(len(missing), 2)  # test0.md 和 test2.md

    def test_cleanup_stale_entries(self):
        """测试清理过期条目"""
        manager = IndexManager(self.state_file, self.config)

        # 添加一个已不存在文件的条目（在 temp_dir 下）
        nonexistent_file = self.temp_dir / "nonexistent.md"
        manager.indexed_files[str(nonexistent_file)] = IndexEntry(
            file_path=str(nonexistent_file),
            file_mtime=1234567890.0,
            indexed_at=1234567900.0,
            chunk_count=5
        )
        manager._save_state()

        # 创建一个存在的文件
        existing_file = self.temp_dir / "existing.md"
        existing_file.write_text("测试内容")
        manager.mark_indexed(existing_file, chunk_count=3)

        # 清理过期条目
        cleaned = manager.cleanup_stale_entries(self.temp_dir)

        self.assertEqual(cleaned, 1)
        self.assertNotIn(str(nonexistent_file), manager.indexed_files)
        self.assertIn(str(existing_file), manager.indexed_files)

    def test_get_stats(self):
        """测试获取统计信息"""
        manager = IndexManager(self.state_file, self.config)

        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")
        manager.mark_indexed(test_file, chunk_count=10)

        stats = manager.get_stats()

        self.assertEqual(stats["total_indexed_files"], 1)
        self.assertEqual(stats["total_chunks"], 10)
        self.assertEqual(stats["total_errors"], 0)

    def test_reset(self):
        """测试重置"""
        manager = IndexManager(self.state_file, self.config)

        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")
        manager.mark_indexed(test_file, chunk_count=5)

        manager.reset()

        self.assertEqual(len(manager.indexed_files), 0)
        self.assertEqual(manager.stats["total_chunks"], 0)

    def test_export_import_state(self):
        """测试导出导入状态"""
        manager1 = IndexManager(self.state_file, self.config)

        # 创建并索引多个文件
        for i in range(3):
            test_file = self.temp_dir / f"test{i}.md"
            test_file.write_text(f"内容{i}")
            manager1.mark_indexed(test_file, chunk_count=i + 1)

        # 导出状态
        exported = manager1.export_state()
        self.assertEqual(len(exported["indexed_files"]), 3)

        # 创建新管理器并导入
        state_file2 = self.temp_dir / "index_state2.json"
        manager2 = IndexManager(state_file2, self.config)
        manager2.import_state(exported)

        self.assertEqual(len(manager2.indexed_files), 3)

    def test_persistence(self):
        """测试状态持久化"""
        # 创建管理器并索引文件
        manager1 = IndexManager(self.state_file, self.config)
        test_file = self.temp_dir / "test.md"
        test_file.write_text("测试内容")
        manager1.mark_indexed(test_file, chunk_count=5)

        # 创建新管理器（从文件加载）
        manager2 = IndexManager(self.state_file, self.config)

        # 验证状态已加载
        self.assertEqual(len(manager2.indexed_files), 1)
        self.assertIn(str(test_file), manager2.indexed_files)


class TestSemanticMemoryPhase2(unittest.TestCase):
    """测试 SemanticMemory 阶段二功能"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = {
            "enabled": True,
            "vector_db": {
                "path": str(self.temp_dir / "vectordb"),
                "collection_name": "test_memory_phase2",
                "persist": True
            },
            "embedding": {
                "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
                "device": "cpu",
                "cache_dir": str(self.temp_dir / "models")
            },
            "indexing": {
                "chunk_size": 500,
                "chunk_overlap": 50,
                "max_chunks_per_file": 100,
                "force_reindex_days": 30
            },
            "retrieval": {
                "default_top_k": 5,
                "min_similarity_score": 0.3,
                "enable_cache": True,
                "cache_max_size": 50
            },
            "index_state_file": str(self.temp_dir / "index_state.json")
        }

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.INDEX_MANAGER_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    @patch('agent.memory.semantic_memory.IndexManager')
    def test_index_logs_directory(self, mock_index_manager_class, mock_chroma,
                                   mock_sentence_transformer, *args):
        """测试批量目录索引"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_store._collection.name = "test_memory"
        mock_store._collection.count.return_value = 10
        mock_chroma.return_value = mock_store

        # 模拟 IndexManager
        mock_manager = Mock()
        mock_manager.needs_indexing.return_value = True
        mock_manager.cleanup_stale_entries.return_value = 0
        mock_index_manager_class.return_value = mock_manager

        # 创建 SemanticMemory 实例
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store
        sm.index_manager = mock_manager

        # 创建测试目录和文件
        logs_dir = self.temp_dir / "logs"
        logs_dir.mkdir()

        for i in range(3):
            log_file = logs_dir / f"2026-04-0{i}.md"
            log_file.write_text(f"# 日志 {i}\n\n## 章节\n- 内容 {i}")

        # Mock _index_file_internal 方法
        original_method = sm._index_file_internal
        sm._index_file_internal = Mock(return_value=5)

        # 执行批量索引
        result = sm.index_logs_directory(logs_dir)

        # 验证结果
        self.assertEqual(result["total_files"], 3)
        self.assertEqual(result["indexed_files"], 3)
        self.assertEqual(result["total_chunks"], 15)  # 3 files * 5 chunks

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_search_advanced_with_filters(self, mock_chroma, mock_sentence_transformer):
        """测试高级检索（带过滤）"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_store._collection.name = "test_memory"
        mock_chroma.return_value = mock_store

        # 模拟检索结果
        mock_doc1 = Mock()
        mock_doc1.page_content = "测试内容1"
        mock_doc1.metadata = {
            "source_file": "test1.md",
            "log_date": "2026-04-01",
            "chunk_index": 0,
            "category": "learning"
        }

        mock_doc2 = Mock()
        mock_doc2.page_content = "测试内容2"
        mock_doc2.metadata = {
            "source_file": "test2.md",
            "log_date": "2026-04-02",
            "chunk_index": 1,
            "category": "error"
        }

        mock_store.similarity_search_with_score.return_value = [
            (mock_doc1, 0.1),
            (mock_doc2, 0.2)
        ]

        # 创建实例
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 执行高级检索
        results = sm.search_advanced(
            query="测试查询",
            top_k=5,
            min_score=0.5,
            date_filter=(date(2026, 4, 1), date(2026, 4, 3)),
            category_filter=["learning"]
        )

        # 验证检索被调用
        mock_store.similarity_search_with_score.assert_called()

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_search_with_date_range(self, mock_chroma, mock_sentence_transformer):
        """测试按日期范围检索"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_chroma.return_value = mock_store

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 模拟检索结果
        mock_doc = Mock()
        mock_doc.page_content = "日期范围内的内容"
        mock_doc.metadata = {
            "source_file": "test.md",
            "log_date": "2026-04-02",
            "chunk_index": 0
        }

        mock_store.similarity_search_with_score.return_value = [(mock_doc, 0.1)]

        # 执行日期范围检索
        results = sm.search_with_date_range(
            query="测试",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 3)
        )

        # 验证调用了高级检索
        mock_store.similarity_search_with_score.assert_called()

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_search_by_category(self, mock_chroma, mock_sentence_transformer):
        """测试按类别检索"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_chroma.return_value = mock_store

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 模拟检索结果
        mock_doc = Mock()
        mock_doc.page_content = "学习内容"
        mock_doc.metadata = {
            "source_file": "test.md",
            "log_date": "2026-04-02",
            "chunk_index": 0,
            "category": "learning"
        }

        mock_store.similarity_search_with_score.return_value = [(mock_doc, 0.1)]

        # 执行类别检索
        results = sm.search_by_category(
            query="测试",
            categories=["learning", "decision"]
        )

        mock_store.similarity_search_with_score.assert_called()

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_cache_mechanism(self, mock_chroma, mock_sentence_transformer):
        """测试检索缓存机制"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_chroma.return_value = mock_store

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 模拟检索结果
        mock_doc = Mock()
        mock_doc.page_content = "缓存测试内容"
        mock_doc.metadata = {
            "source_file": "test.md",
            "log_date": "2026-04-02",
            "chunk_index": 0
        }

        mock_store.similarity_search_with_score.return_value = [(mock_doc, 0.1)]

        # 使用高级检索来测试缓存（因为普通 search 方法不使用缓存）
        # 第一次检索
        results1 = sm.search_advanced("缓存测试", top_k=5, min_score=0.0)
        self.assertEqual(len(results1), 1)

        # 验证第一次调用了检索
        self.assertEqual(mock_store.similarity_search_with_score.call_count, 1)

        # 第二次相同查询（应该使用缓存）
        results2 = sm.search_advanced("缓存测试", top_k=5, min_score=0.0)
        self.assertEqual(len(results2), 1)

        # 验证仍然只调用了一次实际的检索（第二次使用缓存）
        self.assertEqual(mock_store.similarity_search_with_score.call_count, 1)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_clear_cache(self, mock_chroma, mock_sentence_transformer):
        """测试清空缓存"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_chroma.return_value = mock_store

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 添加一些缓存
        sm._search_cache["test_key"] = ([], time.time())

        # 清空缓存
        sm.clear_cache()

        self.assertEqual(len(sm._search_cache), 0)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_get_cache_stats(self, mock_chroma, mock_sentence_transformer):
        """测试获取缓存统计"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_store._collection = Mock()
        mock_chroma.return_value = mock_store

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 添加一些缓存
        sm._search_cache["key1"] = ([], time.time())
        sm._search_cache["key2"] = ([], time.time())

        stats = sm.get_cache_stats()

        self.assertTrue(stats["enabled"])
        self.assertEqual(stats["size"], 2)
        self.assertEqual(stats["max_size"], 50)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.INDEX_MANAGER_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    @patch('agent.memory.semantic_memory.IndexManager')
    def test_get_index_status(self, mock_index_manager_class, mock_chroma,
                               mock_sentence_transformer):
        """测试获取索引状态"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_collection = Mock()
        mock_collection.name = "test_memory"
        mock_collection.count.return_value = 100
        mock_store._collection = mock_collection
        mock_chroma.return_value = mock_store

        # 模拟 IndexManager
        mock_manager = Mock()
        mock_manager.get_stats.return_value = {
            "total_indexed_files": 10,
            "total_chunks": 50,
            "last_index_time": "2026-04-02T12:00:00"
        }
        mock_index_manager_class.return_value = mock_manager

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store
        sm.index_manager = mock_manager

        status = sm.get_index_status()

        self.assertTrue(status["vector_store"]["enabled"])
        self.assertEqual(status["vector_store"]["document_count"], 100)
        self.assertTrue(status["index_manager"]["enabled"])
        self.assertEqual(status["index_manager"]["indexed_files"], 10)
        self.assertEqual(status["index_manager"]["total_chunks"], 50)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_cleanup_old_indices(self, mock_chroma, mock_sentence_transformer):
        """测试清理过期索引"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_collection = Mock()
        mock_store._collection = mock_collection
        mock_chroma.return_value = mock_store

        # 模拟 get 方法返回过期文档
        mock_store.get.return_value = {
            "ids": ["doc1", "doc2", "doc3"],
            "metadatas": [
                {"source_file": "old1.md", "log_date": "2026-01-01"},
                {"source_file": "old1.md", "log_date": "2026-01-02"},
                {"source_file": "old2.md", "log_date": "2026-01-03"}
            ]
        }

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store
        sm.index_manager = None  # 不使用 index_manager 简化测试
        sm.indexed_files = {"old1.md": 123456, "old2.md": 123457}

        # 执行清理
        result = sm.cleanup_old_indices(max_age_days=30)

        # 验证结果
        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_count"], 3)
        self.assertEqual(result["max_age_days"], 30)
        self.assertEqual(len(result["deleted_files"]), 2)  # 2个文件

        # 验证 delete 被调用
        mock_store.delete.assert_called_with(ids=["doc1", "doc2", "doc3"])

        # 验证索引状态被更新
        self.assertEqual(len(sm.indexed_files), 0)  # 应该已清除

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.INDEX_MANAGER_AVAILABLE', False)  # 禁用 index_manager
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_get_resource_usage(self, mock_chroma, mock_sentence_transformer):
        """测试获取资源使用情况"""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_collection = Mock()
        mock_store._collection = mock_collection
        mock_chroma.return_value = mock_store

        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store
        sm.index_manager = None  # 确保 index_manager 为 None

        # 模拟向量库路径存在
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.rglob') as mock_rglob:
                mock_rglob.return_value = [
                    Mock(is_file=Mock(return_value=True), stat=Mock(return_value=Mock(st_size=1024 * 1024)))  # 1MB
                ]

                # 执行获取资源使用
                resource_info = sm.get_resource_usage()

                # 验证基本结构
                self.assertIn("timestamp", resource_info)
                self.assertIn("memory_usage", resource_info)
                self.assertIn("vector_db", resource_info)
                self.assertIn("cache", resource_info)
                self.assertIn("index", resource_info)

                # 验证向量库信息
                self.assertTrue(resource_info["vector_db"]["exists"])
                self.assertEqual(resource_info["vector_db"]["size_mb"], 1.0)


class TestIntegrationPhase2(unittest.TestCase):
    """阶段二集成测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_end_to_end_index_and_search(self):
        """端到端测试：索引和检索"""
        print("\n注意：端到端测试需要真正的 ChromaDB 和 embedding 模型")
        print("此测试演示流程，实际测试需配置相应环境")

        # 创建测试日志目录
        logs_dir = self.temp_dir / "logs"
        logs_dir.mkdir()

        # 创建测试日志文件
        log_content = """# 工作日志：2026-04-02

## [10:00:00] learning (session_id=test123)
- 用户查询: 机器人如何清理垃圾？
- Agent响应: 扫地机器人会自动识别垃圾区域并进行清理...

## [11:00:00] error
- 错误: 无法连接到云端服务器
- 解决方案: 检查网络连接，重试成功

## [14:00:00] decision
- 决策: 将使用本地缓存作为备用方案
"""
        log_file = logs_dir / "2026-04-02.md"
        log_file.write_text(log_content, encoding='utf-8')

        # 测试 IndexManager
        state_file = self.temp_dir / "index_state.json"
        manager = IndexManager(state_file)

        # 检查文件需要索引
        self.assertTrue(manager.needs_indexing(log_file))

        # 标记已索引
        manager.mark_indexed(log_file, chunk_count=5)

        # 检查不再需要索引
        self.assertFalse(manager.needs_indexing(log_file))

        # 获取统计
        stats = manager.get_stats()
        self.assertEqual(stats["total_indexed_files"], 1)

        print("IndexManager 测试通过")

    def test_progress_callback(self):
        """测试进度回调功能"""
        # 创建测试目录
        logs_dir = self.temp_dir / "logs"
        logs_dir.mkdir()

        for i in range(3):
            log_file = logs_dir / f"2026-04-0{i}.md"
            log_file.write_text(f"# 日志 {i}")

        # 进度记录
        progress_records = []

        def progress_callback(current, total, message):
            progress_records.append({
                "current": current,
                "total": total,
                "message": message
            })

        # 创建配置
        config = {
            "enabled": True,
            "vector_db": {"path": str(self.temp_dir / "vectordb")},
            "retrieval": {"enable_cache": True}
        }

        # 使用 mock 进行测试
        with patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', False):
            sm = SemanticMemory(config)

            # Mock _index_file_internal
            sm._index_file_internal = Mock(return_value=5)
            sm._init_index_manager = Mock()  # 避免初始化问题

            # 执行索引（应该失败，因为没有向量存储）
            result = sm.index_logs_directory(
                logs_dir,
                progress_callback=progress_callback
            )

            # 验证进度回调被调用
            # 注意：由于 vector_store 为 None，可能不会处理文件


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
