import asyncio
import json
import traceback
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from core.llm import hf_interface
import logging

logger = logging.getLogger(__name__)

# nest_asyncio.apply()  # Needed to run interactive python

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.llm = hf_interface.load_model()
        self.tools = []
        self.messages = []
        self.logger = logger
        var = self.stdio, self.write


    # connect to MCP server
    async def connect_to_server(self, server_script_path: str):
        try:
            is_python = server_script_path.endswith(".py")
            is_js = server_script_path.endswith(".js")
            if not (is_python and is_js):
                raise ValueError("Server script must be a .py or .js file")

            command = "python" if is_python else "node"
            server_params = StdioServerParameters(
                command=command,
                args=[server_script_path],
                env=None
            )

            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )

            await self.session.initialize()

            self.logger.info("Connected to MCP server")

            mcp_tools = await self.get_mcp_tools()
            self.tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in mcp_tools
            ]

            return True

        except Exception as e:
            self.logger.error(f"Error connecting to MCP server: {e}")
            traceback.print_exc()
            raise


    # call a mcp tool


    # get mcp tool list
    async def get_mcp_tools(self):
        try:
            response = await self.session.list_tools()
            self.tools = response.tools

        except Exception as e:
            self.logger.error(f"Error getting to MCP tools: {e}")
            raise


    # process query
    async def process_query(self, natural_language_query: str):
        try:
            self.logger.info(f"Processing query: {natural_language_query}")
            user_message = {"role": "user", "content": natural_language_query}
            self.messages = [user_message]

            if not "convert_to_sql" in self.tools:
                self.logger.info("Required tool not found for processing query.\n Exiting the process.")
                raise

            response = await self.session.call_tool("convert_to_sql", arguments={"query": natural_language_query})
            self.logger.info(f"Processed query response: {response}")
            assistant_message = {
                "role": "assistant",
                "content": response.content[0].text
            }
            self.messages.append(assistant_message)

            return self.messages
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            raise


    # execute query
    async def execute_query(self):
        ...



    # cleanup
    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
            self.logger.info("Cleaned up MCP server")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()
            raise



# mcp_client = MCPClient()

# async def main(self):
#     # Define server parameters
#     server_params = StdioServerParameters(
#         command="python",  # The command to run your server
#         args=["server.py"],  # Arguments to the command
#     )
#
#     # Connect to the server
#     async with stdio_client(server_params) as (read_stream, write_stream):
#         async with ClientSession(read_stream, write_stream) as session:
#             # Initialize the connection
#             await session.initialize()
#
#             # List available tools
#             tools_result = await session.list_tools()
#             # print("Available tools:")
#             # for tool in tools_result.tools:
#             #     print(f"  - {tool.name}: {tool.description}")
#
#             # Call our calculator tool
#             query = "Get details of all the projects and compute the spent budget over employee salary on each project and determine if project is costing more than allocated budget along with the remaining budget"
#             response = await session.call_tool("convert_to_sql", arguments={"query": query})
#             print(json.loads(response.content[0].text))
#             # print(json.loads(response.content[0].text)["sql"])
#             # response = await session.call_tool("add_numbers", arguments={"a": 3, "b": 4})
#             # print(f"2 + 3 = {response.content[0].text}")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())