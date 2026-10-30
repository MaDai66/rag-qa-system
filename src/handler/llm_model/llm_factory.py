# 新增文件: langchat/handler/llm_model/model_factory.py

from src.handler.llm_model.deepseek_model import DeepSeekModel
from src.handler.llm_model.openai_model import OpenAIModel
from src.handler.llm_model.base_model import BaseModel

class LLMFactory:
    @staticmethod
    def create_model(model_type: str) -> BaseModel:
        if model_type == "deepseek":
            return DeepSeekModel()
        elif model_type == "openai":
            return OpenAIModel()
        else:
            raise ValueError(f"Unsupported model type: {model_type}")