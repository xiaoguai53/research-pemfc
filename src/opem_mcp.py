"""Expose the independently verified OPEM model over MCP stdio."""

from fastmcp import FastMCP

from tools.amphlett import amphlett_mcp


mcp = FastMCP(name="Hydrogen Fuel Cell Research")
mcp.mount(amphlett_mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
