#!/usr/bin/env python3
"""
MemoryConsolidator 单元测试
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import date, datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from agent.memory.memory_consolidator import MemoryConsolidator, MemoryEntry


class TestMemoryConsolidator:
    """MemoryConsolidator 测试类"""

    def setup_method(self):
        """测试初始化"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.consolidator = MemoryConsolidator(strategy="rule_based")

    def teardown_method(self):
        """测试清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_log(self, date_str: str, content: str) -> Path:
        """创建测试日志文件"""
        log_dir = Path(self.temp_dir) / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"{date_str}.md"
        log_file.write_text(content, encoding="utf-8")
        return log_file

    def test_memory_entry_creation(self):
        """测试记忆条目创建"""
        entry = MemoryEntry(
            category="fact",
            content="扫地机器人在湿度>80%的环境下工作效率会下降",
            source_date=date.today(),
            confidence=0.8,
            keywords=["扫地机器人", "湿度", "工作效率"],
            metadata={"source": "测试"}
        )

        assert entry.category == "fact"
        assert "扫地机器人" in entry.content
        assert entry.confidence == 0.8
        assert "湿度" in entry.keywords
        assert entry.metadata["source"] == "测试"

        # 测试格式转换
        formatted = entry.to_memory_format()
        assert entry.content in formatted
        assert str(entry.source_date) in formatted
        assert "置信度" in formatted

    def test_extract_keywords(self):
        """测试关键词提取"""
        text = "用户经常咨询扫地机器人在潮湿环境下的使用问题"
        keywords = self.consolidator._extract_keywords(text)

        # 应该提取到关键词
        assert len(keywords) > 0
        # 检查是否包含重要词汇
        important_words = ["用户", "经常", "咨询", "扫地机器人", "潮湿", "环境", "使用", "问题"]
        # 至少包含部分重要词汇
        assert any(word in keywords for word in important_words)

        # 测试过滤常见词
        text_with_common = "的了我是在有和就"
        keywords = self.consolidator._extract_keywords(text_with_common)
        # 常见词应该被过滤
        assert len(keywords) == 0

    def test_extract_rule_based(self):
        """测试基于规则的提取"""
        # 创建测试日志内容
        log_content = """# 工作日志：2026-04-01

## 系统启动
- 系统初始化完成

## [10:30:15] learning
- 学习到重要事实：扫地机器人在潮湿环境下容易故障
- 用户偏好：大多数用户喜欢定时清洁功能

## [11:45:20] decision
- 决定推荐用户购买防潮垫
- 这是一个重要决策，需要记住

## [12:00:00] error
- 遇到问题：机器人无法连接WiFi"""

        source_date = date(2026, 4, 1)
        entries = self.consolidator._extract_rule_based(log_content, source_date)

        # 应该提取到多个条目
        assert len(entries) > 0

        # 检查类别
        categories = [entry.category for entry in entries]
        assert "fact" in categories or "knowledge" in categories
        assert "preference" in categories
        assert "decision" in categories
        assert "problem" in categories

        # 检查内容
        contents = [entry.content for entry in entries]
        assert any("潮湿环境" in content for content in contents)
        assert any("定时清洁" in content for content in contents)
        assert any("防潮垫" in content for content in contents)

    def test_evaluate_importance(self):
        """测试重要性评估"""
        # 创建测试条目
        high_confidence_entry = MemoryEntry(
            category="fact",
            content="重要事实：机器人怕水",
            source_date=date.today(),
            confidence=0.9,
            keywords=["机器人", "怕水"],
            metadata={}
        )

        low_confidence_entry = MemoryEntry(
            category="problem",
            content="小问题：用户反馈",
            source_date=date.today(),
            confidence=0.3,
            keywords=["用户", "反馈"],
            metadata={}
        )

        # 评估重要性
        high_importance = self.consolidator.evaluate_importance(high_confidence_entry)
        low_importance = self.consolidator.evaluate_importance(low_confidence_entry)

        # 高置信度条目应该更重要
        assert high_importance > low_importance
        # 重要性应该在合理范围内
        assert 0.0 <= high_importance <= 1.0
        assert 0.0 <= low_importance <= 1.0

    def test_extract_from_logs(self):
        """测试从日志文件提取"""
        # 创建测试日志文件
        log_content1 = """# 工作日志：2026-04-01
- 学习到知识：扫地机器人需要定期清理滚刷"""

        log_content2 = """# 工作日志：2026-04-02
- 用户偏好：喜欢安静模式
- 发现问题：滚刷容易缠绕头发"""

        log1 = self.create_test_log("2026-04-01", log_content1)
        log2 = self.create_test_log("2026-04-02", log_content2)

        # 从日志文件提取
        entries = self.consolidator.extract_from_logs([log1, log2])

        # 应该提取到条目
        assert len(entries) >= 2

        # 检查日期
        dates = [entry.source_date for entry in entries]
        assert date(2026, 4, 1) in dates
        assert date(2026, 4, 2) in dates

    def test_build_memory_content(self):
        """测试构建记忆内容"""
        # 创建测试条目
        entries = [
            MemoryEntry(
                category="fact",
                content="测试事实1",
                source_date=date.today(),
                confidence=0.8,
                keywords=["测试"],
                metadata={}
            ),
            MemoryEntry(
                category="preference",
                content="测试偏好1",
                source_date=date.today(),
                confidence=0.7,
                keywords=["偏好"],
                metadata={}
            ),
        ]

        # 分组条目
        grouped = {
            "fact": [(0.8, entries[0])],
            "preference": [(0.7, entries[1])]
        }

        # 构建记忆内容
        content = self.consolidator._build_memory_content(grouped)

        # 检查必要部分
        assert "# 长期记忆" in content
        assert "## 重要事实" in content
        assert "## 用户偏好" in content
        assert "测试事实1" in content
        assert "测试偏好1" in content
        assert date.today().isoformat() in content  # 最后更新时间

    def test_consolidate_to_memory(self):
        """测试整合到记忆文件"""
        # 创建测试记忆文件
        memory_path = Path(self.temp_dir) / "MEMORY.md"
        initial_content = """# 长期记忆

> **注意**：本文件由 Agent 自动维护。

## 重要事实
- 旧事实：机器人需要充电

## 用户偏好
- 旧偏好：用户喜欢定时清洁

---
*最后更新：2026-03-31*"""
        memory_path.write_text(initial_content, encoding="utf-8")

        # 创建测试条目
        entries = [
            MemoryEntry(
                category="fact",
                content="新事实：扫地机器人怕水",
                source_date=date.today(),
                confidence=0.9,
                keywords=["扫地机器人", "怕水"],
                metadata={}
            ),
        ]

        # 整合到记忆文件
        self.consolidator.consolidate_to_memory(entries, memory_path, max_entries_per_category=5)

        # 读取更新后的内容
        updated_content = memory_path.read_text(encoding="utf-8")

        # 检查是否包含新内容
        assert "新事实：扫地机器人怕水" in updated_content
        # 检查是否更新了时间
        assert date.today().isoformat() in updated_content

    def test_consolidate_from_directory(self):
        """测试从目录整合"""
        # 创建测试日志目录
        logs_dir = Path(self.temp_dir) / "logs"
        logs_dir.mkdir(exist_ok=True)

        # 创建测试记忆文件
        memory_path = Path(self.temp_dir) / "MEMORY.md"
        memory_path.write_text("# 长期记忆\n\n## 重要事实\n- 暂无记录\n\n---\n*最后更新：2026-03-31*", encoding="utf-8")

        # 创建几个测试日志文件
        for i in range(3):
            log_date = date.today() - timedelta(days=i)
            log_content = f"""# 工作日志：{log_date.isoformat()}
- 学习到知识{i}：扫地机器人需要定期维护{i}
- 用户偏好{i}：喜欢智能模式{i}"""

            log_file = logs_dir / f"{log_date.isoformat()}.md"
            log_file.write_text(log_content, encoding="utf-8")

        # 执行整合
        self.consolidator.consolidate_from_directory(
            logs_dir=logs_dir,
            memory_path=memory_path,
            days_to_review=3
        )

        # 检查记忆文件是否更新
        updated_content = memory_path.read_text(encoding="utf-8")
        assert "扫地机器人需要定期维护" in updated_content
        assert "喜欢智能模式" in updated_content


def main():
    """运行所有测试"""
    print("=== MemoryConsolidator 单元测试 ===")
    print(f"测试时间: {datetime.now()}")

    test_cases = [
        ("记忆条目创建", TestMemoryConsolidator().test_memory_entry_creation),
        ("关键词提取", TestMemoryConsolidator().test_extract_keywords),
        ("基于规则的提取", TestMemoryConsolidator().test_extract_rule_based),
        ("重要性评估", TestMemoryConsolidator().test_evaluate_importance),
        ("从日志文件提取", TestMemoryConsolidator().test_extract_from_logs),
        ("构建记忆内容", TestMemoryConsolidator().test_build_memory_content),
        ("整合到记忆文件", TestMemoryConsolidator().test_consolidate_to_memory),
        ("从目录整合", TestMemoryConsolidator().test_consolidate_from_directory),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in test_cases:
        # 创建新的测试实例
        test_instance = TestMemoryConsolidator()
        try:
            test_instance.setup_method()
            test_func(test_instance)
            test_instance.teardown_method()
            print(f"✓ PASS: {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAIL: {test_name} - {e}")
            failed += 1
            test_instance.teardown_method()
        except Exception as e:
            print(f"✗ ERROR: {test_name} - {e}")
            failed += 1
            test_instance.teardown_method()

    print(f"\n测试完成: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)