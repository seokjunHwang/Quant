from .backend import LLMBackend, LLMResponse
from .claude_cli import ClaudeCLI
from .claude_api import ClaudeAPI


def make_backend(kind: str, model: str = "claude-opus-4-7") -> LLMBackend:
    if kind == "cli":
        return ClaudeCLI(model=model)
    if kind == "api":
        return ClaudeAPI(model=model)
    raise ValueError(f"unknown backend: {kind}")
