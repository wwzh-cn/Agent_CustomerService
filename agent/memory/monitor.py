"""
语义记忆监控器

监控语义记忆系统的性能指标和健康状态。
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json


class SemanticMemoryMonitor:
    """语义记忆监控器

    记录索引和检索性能指标，提供健康检查功能。
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        初始化监控器

        Args:
            log_dir: 日志目录，如果为None则使用默认目录
        """
        if log_dir is None:
            log_dir = Path("./memory/logs")
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 性能指标
        self.index_stats = {
            "total_files": 0,
            "total_chunks": 0,
            "total_time_sec": 0.0,
            "avg_time_per_file": 0.0,
            "last_index_time": None
        }

        self.search_stats = {
            "total_queries": 0,
            "total_time_sec": 0.0,
            "avg_time_per_query": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }

        # 健康状态
        self.health_status = {
            "vector_db_connected": False,
            "embedding_model_loaded": False,
            "last_health_check": None,
            "errors": []
        }

    def record_index_time(self, file_count: int, chunk_count: int, duration: float):
        """记录索引性能指标

        Args:
            file_count: 索引的文件数量
            chunk_count: 索引的块数量
            duration: 索引耗时（秒）
        """
        self.index_stats["total_files"] += file_count
        self.index_stats["total_chunks"] += chunk_count
        self.index_stats["total_time_sec"] += duration

        if file_count > 0:
            self.index_stats["avg_time_per_file"] = (
                self.index_stats["total_time_sec"] / self.index_stats["total_files"]
            )

        self.index_stats["last_index_time"] = datetime.now().isoformat()

        # 记录到日志文件
        self._log_metric("index", {
            "file_count": file_count,
            "chunk_count": chunk_count,
            "duration_sec": duration,
            "timestamp": self.index_stats["last_index_time"]
        })

    def record_search_time(self, query_length: int, result_count: int,
                          duration: float, cache_hit: bool = False):
        """记录检索性能指标

        Args:
            query_length: 查询文本长度
            result_count: 返回结果数量
            duration: 检索耗时（秒）
            cache_hit: 是否缓存命中
        """
        self.search_stats["total_queries"] += 1
        self.search_stats["total_time_sec"] += duration
        self.search_stats["avg_time_per_query"] = (
            self.search_stats["total_time_sec"] / self.search_stats["total_queries"]
        )

        if cache_hit:
            self.search_stats["cache_hits"] += 1
        else:
            self.search_stats["cache_misses"] += 1

        # 记录到日志文件
        self._log_metric("search", {
            "query_length": query_length,
            "result_count": result_count,
            "duration_sec": duration,
            "cache_hit": cache_hit,
            "timestamp": datetime.now().isoformat()
        })

    def update_health_status(self, vector_db_connected: bool,
                           embedding_model_loaded: bool, errors: list = None):
        """更新健康状态

        Args:
            vector_db_connected: 向量数据库是否连接
            embedding_model_loaded: embedding模型是否加载
            errors: 错误列表
        """
        self.health_status["vector_db_connected"] = vector_db_connected
        self.health_status["embedding_model_loaded"] = embedding_model_loaded
        self.health_status["last_health_check"] = datetime.now().isoformat()

        if errors:
            self.health_status["errors"].extend(errors)
            # 只保留最近100个错误
            if len(self.health_status["errors"]) > 100:
                self.health_status["errors"] = self.health_status["errors"][-100:]

    def get_stats(self) -> Dict[str, Any]:
        """获取所有统计信息

        Returns:
            包含所有统计信息的字典
        """
        stats = {
            "index": self.index_stats.copy(),
            "search": self.search_stats.copy(),
            "health": self.health_status.copy(),
            "timestamp": datetime.now().isoformat()
        }

        # 计算缓存命中率
        total_cache = self.search_stats["cache_hits"] + self.search_stats["cache_misses"]
        if total_cache > 0:
            stats["search"]["cache_hit_rate"] = (
                self.search_stats["cache_hits"] / total_cache * 100
            )
        else:
            stats["search"]["cache_hit_rate"] = 0.0

        return stats

    def clear_stats(self):
        """清空统计信息"""
        self.index_stats = {
            "total_files": 0,
            "total_chunks": 0,
            "total_time_sec": 0.0,
            "avg_time_per_file": 0.0,
            "last_index_time": None
        }

        self.search_stats = {
            "total_queries": 0,
            "total_time_sec": 0.0,
            "avg_time_per_query": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    def _log_metric(self, metric_type: str, data: Dict[str, Any]):
        """记录指标到日志文件

        Args:
            metric_type: 指标类型（index/search）
            data: 指标数据
        """
        log_file = self.log_dir / f"semantic_memory_{datetime.now().strftime('%Y-%m-%d')}.log"

        log_entry = {
            "type": metric_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[SemanticMemoryMonitor] 日志记录失败: {e}")

    def health_check(self) -> Dict[str, Any]:
        """执行健康检查

        Returns:
            健康检查结果
        """
        health_result = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": []
        }

        # 检查向量数据库连接
        vector_db_check = {
            "name": "vector_db_connection",
            "status": "pass" if self.health_status["vector_db_connected"] else "fail",
            "message": "向量数据库连接正常" if self.health_status["vector_db_connected"] else "向量数据库未连接"
        }
        health_result["checks"].append(vector_db_check)

        # 检查embedding模型
        embedding_check = {
            "name": "embedding_model",
            "status": "pass" if self.health_status["embedding_model_loaded"] else "fail",
            "message": "Embedding模型已加载" if self.health_status["embedding_model_loaded"] else "Embedding模型未加载"
        }
        health_result["checks"].append(embedding_check)

        # 检查错误数量
        error_check = {
            "name": "error_count",
            "status": "pass" if len(self.health_status["errors"]) < 10 else "warn",
            "message": f"最近错误数: {len(self.health_status['errors'])}",
            "recent_errors": self.health_status["errors"][-5:] if self.health_status["errors"] else []
        }
        health_result["checks"].append(error_check)

        # 检查索引状态
        if self.index_stats["last_index_time"]:
            last_index_time = datetime.fromisoformat(self.index_stats["last_index_time"])
            hours_since_last_index = (datetime.now() - last_index_time).total_seconds() / 3600
            index_freshness_check = {
                "name": "index_freshness",
                "status": "pass" if hours_since_last_index < 24 else "warn",
                "message": f"上次索引时间: {hours_since_last_index:.1f}小时前",
                "hours_since_last_index": hours_since_last_index
            }
            health_result["checks"].append(index_freshness_check)

        # 确定总体状态
        failed_checks = [check for check in health_result["checks"] if check["status"] == "fail"]
        if failed_checks:
            health_result["status"] = "unhealthy"
        elif any(check["status"] == "warn" for check in health_result["checks"]):
            health_result["status"] = "degraded"

        return health_result