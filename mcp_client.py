"""
MCP客户端实现文件
此模块实现了MCP协议的客户端，用于与MCP服务器进行通信

主要功能:
1. 与MCP服务器建立SSE连接
2. 获取并管理可用工具列表
3. 调用远程工具
4. 获取提示模板
5. 访问服务器资源

技术特点:
- 使用SSE实现与服务器的实时通信
- 支持异步操作
- 提供完整的工具和资源管理
- 实现错误处理和日志记录
- 支持自定义连接参数

作者: 程序员寒山
创建日期: 2025-05-07
"""

from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from contextlib import AsyncExitStack
import json
import logging
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from urllib.parse import urlparse
from pydantic import BaseModel

@dataclass
class ToolParameter:
    """Represents a parameter for a tool.
    
    Attributes:
        name: Parameter name
        parameter_type: Parameter type (e.g., "string", "number")
        description: Parameter description
        required: Whether the parameter is required
        default: Default value for the parameter
    """
    name: str
    parameter_type: str
    description: str
    required: bool = False
    default: Any = None

@dataclass
class ToolDef:
    """Represents a tool definition.
    
    Attributes:
        name: Tool name
        description: Tool description
        parameters: List of ToolParameter objects
        metadata: Optional dictionary of additional metadata
        identifier: Tool identifier (defaults to name)
    """
    name: str
    description: str
    parameters: List[ToolParameter]
    metadata: Optional[Dict[str, Any]] = None
    identifier: str = ""

@dataclass
class ToolInvocationResult:
    """Represents the result of a tool invocation.
    
    Attributes:
        content: Result content as a string
        error_code: Error code (0 for success, 1 for error)
    """
    content: str
    error_code: int

class MCP_Client:
    def __init__(self, host="127.0.0.1", port=8100):
        """Initialize MCP Client"""
        self.url = f"http://{host}:{port}/sse"
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    async def connect(self):
        """Connect to MCP server using SSE transport"""
        try:
            # Create SSE client
            logging.debug("Creating SSE client...")
            self._streams_context = sse_client(url=self.url)
            streams = await self.exit_stack.enter_async_context(self._streams_context)

            # Create session
            logging.debug("Creating client session...")
            self._session_context = ClientSession(*streams)
            self.session = await self.exit_stack.enter_async_context(self._session_context)

            # Initialize session
            logging.debug("Initializing session...")
            await self.session.initialize()
            logging.info(f"Connected to MCP server at {self.url}")

            # Verify connection by listing tools
            tools = await self.session.list_tools()
            logging.debug(f"Available tools: {[t.name for t in tools.tools]}")

        except Exception as e:
            logging.error(f"Connection failed: {str(e)}")
            await self.disconnect()
            raise ConnectionError(f"Failed to connect to MCP server: {str(e)}")

    async def disconnect(self):
        """Disconnect from MCP server"""
        await self.exit_stack.aclose()
        self.session = None
        logging.info("Disconnected from MCP server")

    async def list_tools(self) -> List[ToolDef]:
        """List available tools from the MCP endpoint
        
        Returns:
            List of ToolDef objects describing available tools
        """
        if not self.session:
            raise ConnectionError("Not connected to MCP server")
            
        tools = []
        tools_result = await self.session.list_tools()
        
        for tool in tools_result.tools:
            parameters = []
            required_params = tool.inputSchema.get("required", [])
            for param_name, param_schema in tool.inputSchema.get("properties", {}).items():
                parameters.append(
                    ToolParameter(
                        name=param_name,
                        parameter_type=param_schema.get("type", "string"),
                        description=param_schema.get("description", ""),
                        required=param_name in required_params,
                        default=param_schema.get("default"),
                    )
                )
            tools.append(
                ToolDef(
                    name=tool.name,
                    description=tool.description,
                    parameters=parameters,
                    metadata={"endpoint": self.url},
                    identifier=tool.name
                )
            )
        return tools
    #tools

    async def call_tool(self, name: str, arguments: Optional[dict[str, Any]] = None) -> ToolInvocationResult:
        """Call a tool by name
        
        Args:
            name: Name of the tool to invoke
            arguments: Dictionary of parameters to pass to the tool
            
        Returns:
            ToolInvocationResult containing the tool's response
        """
        if not self.session:
            raise ConnectionError("Not connected to MCP server")
            
        result = await self.session.call_tool(name, arguments or {})
        return ToolInvocationResult(
            content="\n".join([result.model_dump_json() for result in result.content]),
            error_code=1 if result.isError else 0,
        )

    async def get_prompt(self, name: str, **kwargs):
        """Get a prompt template"""
        if not self.session:
            raise ConnectionError("Not connected to MCP server")
        return await self.session.get_prompt(name, kwargs)

    async def get_resource(self, uri: str):
        """Get a resource"""
        if not self.session:
            raise ConnectionError("Not connected to MCP server")
        response = await self.session.read_resource(uri)
        for item in response:
            yield item
