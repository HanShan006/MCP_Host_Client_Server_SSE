"""
MCP服务器实现文件
此模块实现了一个基于MCP协议的SQLite数据库查询服务器

主要功能:
1. 提供SQL查询接口，支持对SQLite数据库进行查询操作
2. 提供数据库表结构查询功能
3. 支持SQL查询提示生成
4. 使用SSE(Server-Sent Events)实现服务器推送
5. 支持日志记录和错误处理

技术特点:
- 使用FastMCP框架构建MCP服务器
- 基于Starlette实现Web服务器功能
- 使用SSE实现服务器推送机制
- 集成SQLite数据库操作
- 支持异步处理

作者: 程序员寒山
创建日期: 2025-05-07
"""

import sqlite3
import logging
from typing import Optional, Any
from mcp.server.fastmcp import FastMCP

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 会话处理函数
async def session_handler(ctx):
    """会话处理函数"""
    logging.info(f"客户端已连接，开始会话. Session ID: {ctx.session_id}")
    logging.debug(f"Connection details: {ctx.connection_info}")
    logging.debug(f"Request headers: {ctx.request.headers}")
    try:
        result = await ctx.run()
        logging.info(f"会话处理完成: {result}")
        return result
    except Exception as e:
        logging.error(f"会话处理出错: {str(e)}")
        raise
    finally:
        logging.info("客户端会话结束")

# 创建FastMCP实例
logging.debug("创建FastMCP实例...")
mcp = FastMCP(
    "SQLiteDB", 
    instructions="基于MCP协议的SQLite数据库查询服务",
    session_handler=session_handler
)

# 设置网络参数
mcp.host = "0.0.0.0"
mcp.port = 8100

@mcp.tool(description="执行SQL查询")
async def query_db(sql: str) -> str:
    logging.info(f"收到SQL查询请求: {sql}")
    """执行SQL查询
    
    Args:
        sql: SQL查询语句
    
    Returns:
        查询结果字符串
    """
    try:
        logging.debug(f"执行SQL查询: {sql}")
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        logging.debug("SQL查询执行完成")
        return "\n".join(str(row) for row in result)
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logging.error(f"SQL查询执行失败: {error_msg}")
        return error_msg
    finally:
        conn.close()

@mcp.resource("db://schema", description="获取数据库表结构")
async def get_schema() -> list[str]:
    """获取数据库表结构
    
    Returns:
        表结构信息列表
    """
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    schema = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        schema.append(f"表 {table[0]}:")
        for col in columns:
            schema.append(f"  - {col[1]} ({col[2]})")
    
    conn.close()
    return schema

@mcp.prompt(description="生成SQL查询提示")
def sql_prompt(question: str) -> str:
    """生成SQL查询提示
    
    Args:
        question: 用户问题
    
    Returns:
        用于生成SQL的提示语
    """
    return f"""请将以下问题转换为SQL查询：
问题: {question}

可用的表结构:
- users(id, name, age, email)
- orders(id, user_id, product_name, price, order_date)

请生成标准的SQLite SQL语句，不要生成其他内容，只返回SQL语句本身。"""

from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route

def create_starlette_app(mcp_server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8100, help='Port to listen on')
    args = parser.parse_args()

    # 运行服务器
    logging.info("启动MCP服务器...")
    logging.info(f"监听地址: {args.host}:{args.port}")
    try:
        # 创建Starlette应用
        starlette_app = create_starlette_app(mcp._mcp_server, debug=True)
        import uvicorn
        uvicorn.run(starlette_app, host=args.host, port=args.port)
    except Exception as e:
        logging.error(f"服务器异常: {str(e)}")
