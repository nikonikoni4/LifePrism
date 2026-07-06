"""
Prompt 集中管理模块

统一管理所有 LLM prompts，提供函数式接口导出
"""

from lifeprism.utils import LazySingleton

from .prompt_loader import PromptLoader, PromptRef, Prompts

prompt_loader: PromptLoader = LazySingleton(PromptLoader)
__all__ = [
    "prompt_loader",
    "PromptRef",
    "Prompts",
]
