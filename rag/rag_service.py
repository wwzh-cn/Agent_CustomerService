
"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model


def print_prompt(prompt):
    print("="*20)
    print(prompt.to_string())
    print("="*20)
    return prompt


class RagSummarizeService(object):
    def __init__(self, use_rerank: bool = True):
        self.vector_store = VectorStoreService()

        # 创建粗排和精排检索器
        self.coarse_retriever = self.vector_store.get_coarse_retriever()
        self.fine_retriever = self.vector_store.get_fine_retriever()

        # Rerank服务（可选）
        if use_rerank:
            try:
                from rerank.rerank_service import RerankService
                from utils.config_handler import load_rerank_config

                rerank_config = load_rerank_config()
                self.reranker = RerankService(
                    model_name=rerank_config.get("rerank_model", "BAAI/bge-reranker-base"),
                    use_gpu=rerank_config.get("use_gpu", False),
                    max_length=rerank_config.get("max_length", 512),
                    batch_size=rerank_config.get("batch_size", 16)
                )
            except Exception as e:
                print(f"警告: 无法加载rerank服务，将降级到原始检索: {e}")
                self.reranker = None
        else:
            self.reranker = None

        # 原有初始化逻辑保持不变
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        """两阶段检索：粗排→精排

        Args:
            query: 用户查询

        Returns:
            检索到的文档列表
        """
        from utils.config_handler import load_rerank_config

        if not self.reranker:
            # 降级模式：使用原逻辑
            return self.fine_retriever.invoke(query)

        try:
            # 获取配置
            rerank_config = load_rerank_config()
            fallback_enabled = rerank_config.get("fallback_to_original", True)

            # 1. 粗排：获取候选文档
            coarse_docs = self.coarse_retriever.invoke(query)

            if len(coarse_docs) <= 3:
                # 候选不足，直接返回
                return coarse_docs[:3]

            # 2. 精排：rerank筛选top-3
            fine_k = rerank_config.get("fine_k", 3)
            fine_docs = self.reranker.rerank(query, coarse_docs, top_k=fine_k)
            return fine_docs

        except Exception as e:
            # rerank失败时降级到原始排序
            if fallback_enabled:
                print(f"警告: Rerank失败，降级到原始检索: {e}")
                return self.fine_retriever.invoke(query)
            else:
                raise RuntimeError(f"Rerank失败且未启用降级: {e}")

    # 注释掉原有的retriever_docs方法，但不删除
    # def retriever_docs(self, query: str) -> list[Document]:
    #     return self.retriever.invoke(query)  # 单阶段检索

    def rag_summarize(self, query: str) -> str:

        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService()

    print(rag.rag_summarize("小户型适合哪些扫地机器人"))