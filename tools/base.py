"""
MRAgent — Base Tool Interface
Defines the Tool base class with OpenAI function-calling schema generation.

Created: 2026-02-15

Usage:
    class MyTool(Tool):
        name = "my_tool"
        description = "Does something"
        parameters = {
            "type": "object",
            "properties": {"arg1": {"type": "string", "description": "..."}},
            "required": ["arg1"]
        }
        def execute(self, arg1: str) -> str:
            return "result"
"""

import time
from abc import ABC, abstractmethod

from utils.logger import get_logger, log_tool_execution

logger = get_logger("tools.base")


class Tool(ABC):
    """
    Base class for all agent tools.

    Each tool:
    1. Has a name, description, and JSON Schema parameters
    2. Can execute with given arguments
    3. Can export itself as an OpenAI function-calling tool definition
    """

    name: str = ""
    description: str = ""
    parameters: dict = {"type": "object", "properties": {}}

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__.lower()
        self.logger = get_logger(f"tools.{self.name}")

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Execute the tool with given arguments.

        Returns:
            String result to be fed back into the LLM.
        """
        pass

    def safe_execute(self, **kwargs) -> str:
        """Execute with logging, timing, and error handling."""
        start_time = time.time()
        try:
            result = self.execute(**kwargs)
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                self.logger, self.name, kwargs,
                result_preview=str(result)[:200],
                duration_ms=duration_ms, success=True,
            )
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                self.logger, self.name, kwargs,
                result_preview=str(e),
                duration_ms=duration_ms, success=False,
            )
            return f"Error executing {self.name}: {e}"

    def to_openai_tool(self) -> dict:
        """Export as OpenAI function-calling tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of available tools. Provides lookup and schema export."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self.logger = get_logger("tools.registry")

    def register(self, tool: Tool):
        """Register a tool by name."""
        self._tools[tool.name] = tool
        self.logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def execute(self, name: str, **kwargs) -> str:
        """Execute a tool by name with safe error handling."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"
        return tool.safe_execute(**kwargs)

    def get_openai_tools(self) -> list[dict]:
        """Export all tools as OpenAI function-calling definitions."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def list_tools(self) -> list[dict]:
        """Return a list of all registered tools with their info."""
        return [
            {"name": t.name, "description": t.description}
            for t in self._tools.values()
        ]

    @property
    def count(self) -> int:
        return len(self._tools)
