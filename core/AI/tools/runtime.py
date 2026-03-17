from dataclasses import dataclass
from typing import Any, Callable

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - local compatibility until the package is installed
    class FastMCP:  # type: ignore[override]
        def __init__(self, name: str):
            self.name = name

        def tool(self, description: str):
            def decorator(func):
                return func

            return decorator

        def run(self, transport: str = "sse"):
            raise RuntimeError(
                "The 'mcp' package is not installed. Add it to the environment to run the FastMCP server."
            )


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    handler: Callable[..., str]


@dataclass
class MCPToolPlan:
    tool_name: str
    arguments: dict[str, Any]


mcp = FastMCP("MoPD-KPI-MCP")
RUNTIME_TOOLS: dict[str, MCPToolDefinition] = {}


def register_runtime_tool(*, description: str):
    def decorator(func):
        RUNTIME_TOOLS[func.__name__] = MCPToolDefinition(
            name=func.__name__,
            description=description.strip(),
            handler=func,
        )
        return func

    return decorator
