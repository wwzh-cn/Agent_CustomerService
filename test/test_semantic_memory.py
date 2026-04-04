"""
语义记忆系统单元测试

测试 SemanticMemory 类和相关组件的功能。
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import date
from unittest.mock import Mock, patch, MagicMock

# 导入待测试模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.memory.semantic_memory import SemanticMemory, MemoryResult
from agent.memory.memory_chunker import LogChunker, LogChunk


class TestMemoryResult(unittest.TestCase):
    """测试 MemoryResult 数据结构"""

    def test_memory_result_creation(self):
        """测试 MemoryResult 创建"""
        metadata = {"source": "test", "category": "learning"}
        result = MemoryResult(
            text="测试文本内容",
            score=0.85,
            metadata=metadata,
            source_file="test.md",
            log_date=date(2026, 4, 2),
            chunk_index=1
        )

        self.assertEqual(result.text, "测试文本内容")
        self.assertEqual(result.score, 0.85)
        self.assertEqual(result.metadata, metadata)
        self.assertEqual(result.source_file, "test.md")
        self.assertEqual(result.log_date, date(2026, 4, 2))
        self.assertEqual(result.chunk_index, 1)

    def test_to_context_format(self):
        """测试上下文格式转换"""
        result = MemoryResult(
            text="这是一个测试文本内容，用于测试上下文格式转换功能。",
            score=0.9,
            metadata={},
            source_file="test.md",
            log_date=date(2026, 4, 2),
            chunk_index=0
        )

        context = result.to_context_format()
        self.assertIn("2026-04-02", context)
        self.assertIn("这是一个测试文本内容", context)

    def test_to_dict(self):
        """测试字典转换"""
        result = MemoryResult(
            text="测试",
            score=0.5,
            metadata={"key": "value"},
            source_file="test.md",
            log_date=date(2026, 4, 2),
            chunk_index=0
        )

        result_dict = result.to_dict()
        self.assertEqual(result_dict["text"], "测试")
        self.assertEqual(result_dict["score"], 0.5)
        self.assertEqual(result_dict["metadata"]["key"], "value")
        self.assertEqual(result_dict["source_file"], "test.md")
        self.assertEqual(result_dict["chunk_index"], 0)


class TestLogChunker(unittest.TestCase):
    """测试 LogChunker 类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "chunk_size": 200,
            "chunk_overlap": 50,
            "max_chunks_per_file": 20
        }
        self.chunker = LogChunker(self.config)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_extract_date_from_filename(self):
        """测试从文件名提取日期"""
        # 测试标准格式文件名
        test_file = Path(self.temp_dir) / "2026-04-02.md"
        test_file.touch()

        extracted_date = self.chunker._extract_date_from_filename(test_file)
        self.assertEqual(extracted_date, date(2026, 4, 2))

        # 测试无效文件名
        invalid_file = Path(self.temp_dir) / "invalid_name.md"
        invalid_file.touch()

        extracted_date = self.chunker._extract_date_from_filename(invalid_file)
        # 应该返回当天日期
        self.assertIsInstance(extracted_date, date)

    def test_chunk_by_sections(self):
        """测试按章节分块"""
        content = """# 工作日志：2026-04-02

## 系统启动
- 系统初始化完成
- 记忆加载成功

## [00:00:01] learning
- 用户查询测试"""

        log_date = date(2026, 4, 2)
        log_path = Path(self.temp_dir) / "test.md"

        chunks = self.chunker._chunk_by_sections(content, log_date, log_path)

        self.assertEqual(len(chunks), 2)  # 两个章节
        self.assertEqual(chunks[0].chunk_type, "section")
        self.assertIn("系统启动", chunks[0].text)
        self.assertIn("learning", chunks[1].text)

    def test_chunk_by_entries(self):
        """测试按条目分块"""
        content = """# 测试日志

## 测试章节
- 条目1内容
  附加内容
- 条目2内容

其他文本"""

        log_date = date(2026, 4, 2)
        log_path = Path(self.temp_dir) / "test.md"

        chunks = self.chunker._chunk_by_entries(content, log_date, log_path)

        self.assertTrue(len(chunks) >= 2)  # 至少两个条目
        self.assertEqual(chunks[0].chunk_type, "entry")
        self.assertIn("条目1", chunks[0].text)
        self.assertIn("条目2", chunks[1].text)

    def test_chunk_log_file_integration(self):
        """测试完整的分块流程"""
        # 创建测试日志文件
        log_content = """# 工作日志：2026-04-02

## 系统启动
- 系统初始化完成

## [00:00:01] learning (session_id=test123)
- 用户查询: 测试问题
Agent响应: 测试答案"""

        log_file = Path(self.temp_dir) / "2026-04-02.md"
        log_file.write_text(log_content, encoding='utf-8')

        # 执行分块
        chunks = self.chunker.chunk_log_file(log_file)

        self.assertTrue(len(chunks) > 0)

        # 验证分块属性
        for chunk in chunks:
            self.assertIsInstance(chunk, LogChunk)
            self.assertTrue(chunk.text.strip())
            self.assertIsInstance(chunk.metadata, dict)
            self.assertEqual(chunk.log_date, date(2026, 4, 2))


class TestSemanticMemory(unittest.TestCase):
    """测试 SemanticMemory 类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()

        # 模拟配置
        self.config = {
            "enabled": True,
            "vector_db": {
                "path": str(Path(self.temp_dir) / "vectordb"),
                "collection_name": "test_memory",
                "persist": True
            },
            "embedding": {
                "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
                "device": "cpu",
                "cache_dir": str(Path(self.temp_dir) / "models")
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

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_initialization_with_mocks(self, mock_chroma, mock_sentence_transformer):
        """测试初始化（使用模拟对象）"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_chroma.return_value = mock_store

        # 创建实例
        sm = SemanticMemory(self.config)

        # 验证初始化调用
        mock_sentence_transformer.assert_called_once()
        mock_chroma.assert_called_once()

        self.assertEqual(sm.vector_store, mock_store)
        self.assertEqual(sm.embedding_model, mock_model)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', False)
    def test_initialization_without_dependencies(self):
        """测试缺少依赖时的初始化"""
        sm = SemanticMemory(self.config)

        self.assertIsNone(sm.vector_store)
        self.assertIsNone(sm.embedding_model)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_search_with_mocks(self, mock_chroma, mock_sentence_transformer):
        """测试检索功能（使用模拟对象）"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_chroma.return_value = mock_store

        # 模拟检索结果
        mock_doc1 = Mock()
        mock_doc1.page_content = "测试文档内容1"
        mock_doc1.metadata = {
            "source_file": "test1.md",
            "log_date": "2026-04-01",
            "chunk_index": 0
        }

        mock_doc2 = Mock()
        mock_doc2.page_content = "测试文档内容2"
        mock_doc2.metadata = {
            "source_file": "test2.md",
            "log_date": "2026-04-02",
            "chunk_index": 1
        }

        mock_store.similarity_search_with_score.return_value = [
            (mock_doc1, 0.1),  # 距离0.1，相似度0.9
            (mock_doc2, 0.3)   # 距离0.3，相似度0.7
        ]

        # 创建实例并测试检索
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        results = sm.search("测试查询", top_k=2)

        # 验证检索调用
        mock_store.similarity_search_with_score.assert_called_once_with("测试查询", k=2)

        # 验证结果
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].text, "测试文档内容1")
        self.assertEqual(results[1].text, "测试文档内容2")
        self.assertAlmostEqual(results[0].score, 0.9)  # 1 - 0.1
        self.assertAlmostEqual(results[1].score, 0.7)  # 1 - 0.3

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_search_with_min_score(self, mock_chroma, mock_sentence_transformer):
        """测试带最低分数阈值的检索"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_chroma.return_value = mock_store

        # 模拟检索结果（一个高分，一个低分）
        mock_doc1 = Mock()
        mock_doc1.page_content = "高分文档"
        mock_doc1.metadata = {"source_file": "test1.md", "log_date": "2026-04-01", "chunk_index": 0}

        mock_doc2 = Mock()
        mock_doc2.page_content = "低分文档"
        mock_doc2.metadata = {"source_file": "test2.md", "log_date": "2026-04-02", "chunk_index": 1}

        mock_store.similarity_search_with_score.return_value = [
            (mock_doc1, 0.1),  # 相似度0.9
            (mock_doc2, 0.8)   # 相似度0.2
        ]

        # 创建实例并测试检索，设置最低分数0.5
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        results = sm.search("测试查询", top_k=5, min_score=0.5)

        # 应该只返回高分文档
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].text, "高分文档")
        self.assertGreaterEqual(results[0].score, 0.5)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_search_with_context(self, mock_chroma, mock_sentence_transformer):
        """测试检索并格式化为上下文"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_chroma.return_value = mock_store

        # 模拟检索结果
        mock_doc = Mock()
        mock_doc.page_content = "这是一个测试文档内容，用于测试上下文格式化功能。"
        mock_doc.metadata = {
            "source_file": "test.md",
            "log_date": "2026-04-02",
            "chunk_index": 0
        }

        mock_store.similarity_search_with_score.return_value = [
            (mock_doc, 0.2)  # 相似度0.8
        ]

        # 创建实例并测试检索
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        context = sm.search_with_context("测试查询")

        # 验证上下文格式
        self.assertIn("相关记忆（从历史日志中检索）", context)
        self.assertIn("这是一个测试文档内容", context)
        self.assertIn("相关性: 0.80", context)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    def test_get_stats(self, mock_chroma, mock_sentence_transformer):
        """测试获取统计信息"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_chroma.return_value = mock_store

        # 模拟集合
        mock_collection = Mock()
        mock_collection.name = "test_memory"
        mock_collection.count.return_value = 42
        mock_store._collection = mock_collection

        # 创建实例
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store
        sm.indexed_files = {"file1.md": 1234567890.0, "file2.md": 1234567891.0}

        # 获取统计信息
        stats = sm.get_stats()

        # 验证统计信息
        self.assertTrue(stats["enabled"])
        self.assertEqual(stats["indexed_files_count"], 2)
        self.assertEqual(stats["config"]["embedding_model"], "paraphrase-multilingual-MiniLM-L12-v2")

        # 验证向量数据库统计
        self.assertIn("vector_db", stats)
        self.assertEqual(stats["vector_db"]["collection_name"], "test_memory")
        self.assertEqual(stats["vector_db"]["count"], 42)

    @patch('agent.memory.semantic_memory.CHROMA_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.CHUNKER_AVAILABLE', True)
    @patch('agent.memory.semantic_memory.SentenceTransformer')
    @patch('agent.memory.semantic_memory.Chroma')
    @patch('agent.memory.semantic_memory.LogChunker')
    def test_index_log_file(self, mock_log_chunker_class, mock_chroma, mock_sentence_transformer):
        """测试索引日志文件"""
        # 设置模拟对象
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model

        mock_store = Mock()
        mock_chroma.return_value = mock_store

        # 模拟日志分块器
        mock_chunker_instance = Mock()
        mock_log_chunker_class.return_value = mock_chunker_instance

        # 模拟分块结果
        mock_chunk1 = Mock()
        mock_chunk1.text = "分块1内容"
        mock_chunk1.metadata = {"key": "value1"}
        mock_chunk1.log_date = date(2026, 4, 2)

        mock_chunk2 = Mock()
        mock_chunk2.text = "分块2内容"
        mock_chunk2.metadata = {"key": "value2"}
        mock_chunk2.log_date = date(2026, 4, 2)

        mock_chunker_instance.chunk_log_file.return_value = [mock_chunk1, mock_chunk2]

        # 创建实例
        sm = SemanticMemory(self.config)
        sm.vector_store = mock_store

        # 创建测试文件
        test_file = Path(self.temp_dir) / "test_log.md"
        test_file.write_text("测试日志内容")

        # 测试索引
        chunk_count = sm.index_log_file(test_file)

        # 验证索引调用
        mock_chunker_instance.chunk_log_file.assert_called_once_with(test_file)
        mock_store.add_texts.assert_called_once()

        # 验证返回的块数
        self.assertEqual(chunk_count, 2)

        # 验证索引状态更新
        self.assertIn(str(test_file), sm.indexed_files)

    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效配置
        invalid_config = {"invalid": "config"}

        with self.assertLogs(level='WARNING') as log:
            sm = SemanticMemory(invalid_config)
            self.assertIsNone(sm.vector_store)
            self.assertIn("依赖不可用", log.output[0])


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_end_to_end_with_mocks(self):
        """端到端测试（使用模拟对象）"""
        # 这个测试演示了完整的工作流程
        # 在实际环境中，需要真正的 ChromaDB 和模型才能运行

        print("\n注意：端到端测试需要真正的 ChromaDB 和 embedding 模型")
        print("此测试仅演示流程，实际测试需配置相应环境")

        # 模拟配置
        config = {
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
            }
        }

        # 创建实例（可能会失败，因为缺少依赖）
        try:
            sm = SemanticMemory(config)
            stats = sm.get_stats()
            print(f"语义记忆状态: {stats}")
        except Exception as e:
            print(f"语义记忆初始化失败（预期中）: {e}")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)