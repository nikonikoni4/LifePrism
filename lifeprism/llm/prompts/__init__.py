"""
Prompt 集中管理模块

统一管理所有 LLM prompts，提供函数式接口导出
"""

from .prompt_loader import PromptLoader, PromptRef, Prompts

__all__ = [
    "PromptLoader",
    "PromptRef",
    "Prompts",
]
