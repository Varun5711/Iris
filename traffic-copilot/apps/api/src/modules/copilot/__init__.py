"""LLM copilot orchestration."""
from src.modules.copilot.llm_client import generate_recommendation, generate_chat_answer, build_deterministic_fallback
from src.modules.copilot.prompt_loader import load_prompt, load_system_prompt, load_task_prompt, format_prompt
__all__ = ["generate_recommendation", "generate_chat_answer", "build_deterministic_fallback", "load_prompt", "load_system_prompt", "load_task_prompt", "format_prompt"]
