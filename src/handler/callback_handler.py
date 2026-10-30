from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
# from langchain.schema import AgentAction, AgentFinish, LLMResult
from langchain_core.agents import AgentAction, AgentFinish
import time
from typing import Any, Dict, List, Union
from src.utils.logger import get_logger
logger = get_logger(__name__)

class CustomCallbackHandler(BaseCallbackHandler):
    """自定义回调处理器，用于记录LLM执行过程中的关键事件"""
    
    def __init__(self):
        self.start_time = None
        self.total_tokens = 0
        self.llm_calls = 0
        self.agent_actions = []
        
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """LLM开始生成时调用"""
        logger.info(f"on_llm_start kwargs: {str(kwargs)}")
        self.start_time = time.time()
        self.llm_calls += 1
        print(f"--->LLM调用 #{self.llm_calls} 开始，输入提示: {prompts[0][:50]}..." if len(prompts[0]) > 50 else prompts[0])
        
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM生成结束时调用"""
        logger.info(f"on_llm_end kwargs: {str(kwargs)}")
        if self.start_time:
            duration = time.time() - self.start_time
            print(f"--->LLM调用完成，耗时: {duration:.2f}秒")
            response.llm_output["custom_metadata"] = "1212"
            # 直接从 response.llm_output 获取 token_usage
            if response.llm_output and "token_usage" in response.llm_output:
                usage = response.llm_output["token_usage"]
                total_tokens = usage.get("total_tokens", 0)
                self.total_tokens += total_tokens
                print(f"--->本次调用使用的token: {total_tokens}")

            print(f"--->累计token使用量: {self.total_tokens}")
            
    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """LLM生成出错时调用"""
        print(f"--->LLM调用出错: {str(error)}")
        
    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Chain开始执行时调用"""
        logger.info(f"on_chain_start kwargs: {str(kwargs)}")
        chain_type = serialized.get("name", "Unknown Chain") if serialized else "Unknown Chain"
        print(f"--->{chain_type} 开始执行")
        
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Chain执行结束时调用"""
        logger.info(f"on_chain_end kwargs: {str(kwargs)}")
        print(f"--->Chain执行完成")
        
    def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        logger.info(f"kwargs: {str(kwargs)}")
        """Chain执行出错时调用"""
        print(f"--->Chain执行出错: {str(error)}")
        
    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """工具开始执行时调用"""
        tool_name = serialized.get("name", "Unknown Tool")
        print(f"--->工具 {tool_name} 开始执行，输入: {input_str[:50]}..." if len(input_str) > 50 else input_str)
        
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """工具执行结束时调用"""
        print(f"--->工具执行完成，输出: {output[:50]}..." if len(output) > 50 else output)
        
    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """工具执行出错时调用"""
        print(f"--->工具执行出错: {str(error)}")
        
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        """Agent执行操作时调用"""
        self.agent_actions.append(action)
        print(f"--->Agent执行操作: {action.tool}，参数: {action.tool_input}")
        
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Agent完成执行时调用"""
        print(f"--->Agent执行完成，最终输出: {finish.return_values.get('output', '')[:50]}..." if len(finish.return_values.get('output', '')) > 50 else finish.return_values.get('output', ''))
        print(f"--->Agent共执行了 {len(self.agent_actions)} 个操作")

