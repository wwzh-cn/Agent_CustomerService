import os
# os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'  # 解决OpenMP库冲突问题
# # 设置huggingface镜像和超时
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用国内镜像
# os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'  # 设置huggingface下载超时300秒
# os.environ['HF_HUB_CONNECT_TIMEOUT'] = '60'    # 设置连接超时60秒
# # os.environ['TRANSFORMERS_OFFLINE'] = '1'       # 离线模式，不使用网络
# # os.environ['HF_HUB_OFFLINE'] = '1'             # huggingface hub离线模式

import logging
from typing import List, Tuple
from langchain_core.documents import Document
import torch
from FlagEmbedding import FlagReranker
logger = logging.getLogger(__name__)


class RerankService:
    """重排序服务，使用FlagEmbedding FlagReranker进行文档精排"""

    def __init__(self, model_name="BAAI/bge-reranker-base", model_path=None, cache_dir=None, use_gpu=False, max_length=512, batch_size=16, use_fp16=True):
        self.model_name = model_name
        self.model_path = model_path  # 本地模型路径，优先级高于model_name
        self.cache_dir = cache_dir    # 模型缓存目录
        self.use_gpu = use_gpu
        self.max_length = max_length
        self.batch_size = batch_size
        self.use_fp16 = use_fp16
        self.model = None

        # 确定设备
        self.device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"

    def _load_model(self):
        """加载FlagEmbedding FlagReranker模型"""
        if self.model is None:
            try:
                from FlagEmbedding import FlagReranker

                # 确定要加载的模型：优先使用本地路径
                model_to_load = self.model_path if self.model_path else self.model_name

                # 创建并加载模型
                self.model = FlagReranker(model_to_load, use_fp16=self.use_fp16)
                logger.info(f"加载重排序模型成功: {model_to_load}, 设备: {self.device}, use_fp16: {self.use_fp16}")
            except ImportError:
                raise ImportError("请安装FlagEmbedding: pip install FlagEmbedding")
            except Exception as e:
                raise RuntimeError(f"加载模型失败: {e}")
        return self.model

    def rerank(self, query: str, candidates: List[Document], top_k: int = 3) -> List[Document]:
        """对候选文档进行重排序

        Args:
            query: 用户查询
            candidates: 候选文档列表（Document对象）
            top_k: 返回的文档数量

        Returns:
            重排序后的top_k个文档，包含排序分数（metadata中）
        """
        if not candidates:
            return []

        if len(candidates) <= top_k:
            # 候选不足，直接返回
            return candidates[:top_k]

        try:
            # 提取文档文本
            texts = [doc.page_content for doc in candidates]

            # 批量重排序
            scores = self._batch_rerank(query, texts)

            # 创建(分数, 索引, 文档)元组列表
            scored_docs = list(zip(scores, range(len(candidates)), candidates))

            # 按分数降序排序
            scored_docs.sort(key=lambda x: x[0], reverse=True)

            # 取top_k
            result_docs = []
            for score, idx, doc in scored_docs[:top_k]:
                # 在metadata中添加排序分数
                new_metadata = doc.metadata.copy()
                new_metadata["rerank_score"] = float(score)
                new_metadata["original_rank"] = idx + 1
                result_docs.append(Document(page_content=doc.page_content, metadata=new_metadata))

            logger.debug(f"重排序完成: 查询={query[:50]}..., 候选={len(candidates)}, top_k={top_k}")
            return result_docs

        except Exception as e:
            logger.error(f"重排序失败: {e}, 降级到原始排序")
            # 失败时返回原始排序的前top_k个
            return candidates[:top_k]

    def _batch_rerank(self, query: str, texts: List[str]) -> List[float]:
        """批量重排序内部方法"""
        try:
            model = self._load_model()

            # 准备输入对: [[query, text], ...]
            pairs = [[query, text[:self.max_length]] for text in texts]

            # 批量推理
            scores = model.compute_score(pairs, normalize=True)

            return scores
        except Exception as e:
            logger.error(f"批量重排序失败: {e}")
            raise