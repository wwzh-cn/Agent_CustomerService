import logging
from typing import List, Tuple
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class RerankService:
    """重排序服务，使用BAAI/bge-reranker-base进行文档精排"""

    def __init__(self, model_name="BAAI/bge-reranker-base", use_gpu=False, max_length=512, batch_size=16):
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.max_length = max_length
        self.batch_size = batch_size
        self.model = None  # 延迟加载

    def _load_model(self):
        """延迟加载模型"""
        if self.model is None:
            try:
                from FlagEmbedding import FlagReranker
                self.model = FlagReranker(self.model_name)
                logger.info(f"加载重排序模型成功: {self.model_name}")
            except ImportError:
                raise ImportError("请安装FlagEmbedding: pip install FlagEmbedding")
            except Exception as e:
                raise RuntimeError(f"加载模型失败: {e}")
        return self.model

    def rerank(self, query: str, candidates: List[Document], top_k: int = 3) -> List[Document]:
        """对候选文档进行重排序"""
        raise NotImplementedError("待实现")

    def _batch_rerank(self, query: str, texts: List[str]) -> List[float]:
        """批量重排序内部方法"""
        raise NotImplementedError("待实现")