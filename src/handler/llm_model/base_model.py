from abc import ABC, abstractmethod


class BaseModel(ABC):
    
    @abstractmethod
    async def init_llm_model(self):
        """Initialize the LLM model. This method can be overridden by subclasses."""
        pass