import asyncio
import nest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

nest_asyncio.apply()  # Needed to run interactive python


async def main():
    # Define server parameters
    server_params = StdioServerParameters(
        command="python",  # The command to run your server
        args=["server.py"],  # Arguments to the command
    )

    # Connect to the server
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            print("Available tools:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Call our calculator tool
            query = "Get details of all the projects and compute the spent budget over employee salary on each project and determine if project is costing more than allocated budget along with the remaining budget"
            response = await session.call_tool("convert_to_sql", arguments={"query": query})
            # response.model_dump_json(indent=4)
            print(f"2 + 3 = {response.model_dump_json(indent=4)}")


if __name__ == "__main__":
    asyncio.run(main())