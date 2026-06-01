from fastmcp import FastMCP

mcp = FastMCP("public-health-mcp")


@mcp.tool()
def health_check() -> str:
    return "ok"


if __name__ == "__main__":
    mcp.run()
