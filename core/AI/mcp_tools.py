from AI.tools import execute_mcp_tool_plan, mcp, resolve_mcp_tool_plan

__all__ = ["execute_mcp_tool_plan", "mcp", "resolve_mcp_tool_plan"]


if __name__ == "__main__":
    mcp.run(transport="sse")
