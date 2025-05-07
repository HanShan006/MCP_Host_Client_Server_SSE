"""
MCP主机程序
此模块实现了一个结合OpenAI的MCP客户端应用，用于自然语言数据库查询

主要功能:
1. 连接到MCP服务器获取数据库服务
2. 接收用户自然语言问题
3. 使用OpenAI将问题转换为SQL查询
4. 执行SQL查询并获取结果
5. 使用OpenAI解释查询结果

技术特点:
- 集成OpenAI接口进行自然语言处理
- 支持配置文件管理API密钥
- 实现完整的错误处理和日志记录
- 提供交互式命令行界面
- 支持异步操作

作者: 程序员寒山
创建日期: 2025-05-07
"""

import asyncio
from mcp_client import MCP_Client
from openai import OpenAI
import json
import logging
from typing import Any
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

# 获取配置文件中的API_KEY
api_key = config.get('secrets', 'API_KEY')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configure OpenAI client
clientOpenai = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

async def format_resource_content(content: Any) -> str:
    """Format resource content"""
    if isinstance(content, (str, int, float)):
        return str(content)
    elif isinstance(content, (list, dict)):
        return json.dumps(content, ensure_ascii=False, indent=2)
    return str(content)

async def main():
    logging.info("Starting MCP Host program...")
    client = MCP_Client(host="127.0.0.1", port=8100)
    
    try:
        # Connect to MCP server
        logging.info("Connecting to MCP server...")
        await client.connect()
        logging.info("Connected to MCP server")

        # Get database schema
        logging.debug("Getting database schema...")
        async for content in client.get_resource("db://schema"):
            formatted = await format_resource_content(content)
            logging.info(f"Database schema: \n{formatted}")

        # List available tools
        tools = await client.list_tools()
        # print(f"Available tools: {[t.name for t in tools]}")
        logging.info("Available tools:"+str(tools))

        while True:
            # Get user question
            user_question = input("\nEnter your question (q to quit): ")
            if user_question.lower() == 'q':
                break

            # Get SQL prompt
            logging.info(f"User question: {user_question}")
            prompt = await client.get_prompt("sql_prompt", question=user_question)
            logging.info(f"Got SQL prompt template: {prompt}")

            # Get tools in OpenAI format
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                param.name: {
                                    "type": param.parameter_type,
                                    "description": param.description
                                } for param in tool.parameters
                            },
                            "required": [param.name for param in tool.parameters if param.required]
                        }
                    }
                } for tool in tools
            ]

            # Generate SQL query using OpenAI with MCP tools
            logging.info("Generating SQL query with OpenAI...")
            prompt_text = prompt.messages[0].content.text
            response = clientOpenai.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个SQL查询助手，请根据用户的问题生成合适的SQL查询语句。"
                    },
                    {
                        "role": "user", 
                        "content": prompt_text
                    }
                ],
                tools=openai_tools,
                tool_choice={"type": "function", "function": {"name": "query_db"}}
            )
            # 自动模式（默认）
            # tool_choice="auto"  # 可以调用零个、一个或多个函数
            # # 强制模式
            # tool_choice="required"  # 必须调用至少一个函数
            # # 指定函数， 强制调用特定函数
            # tool_choice={
            #     "type": "function", 
            #     "function": {"name": "get_weather"}
            # }  # 

            #  ChatCompletion(id='e92a220d-a1e1-4a79-b24f-f7140fa9a64a', choices=[Choice(finish_reason='tool_calls', index=0, logprobs=None, message=ChatCompletionMessage(content='', refusal=None, role='assistant', audio=None, function_call=None, tool_calls=[ChatCompletionMessageToolCall(id='call_0_a5a4250b-3bea-48b1-a457-9e352fffa1d6', function=Function(arguments='{"sql":"SELECT orders.* FROM orders JOIN users ON orders.user_id = users.id WHERE users.name = \'张三\'"}', name='query_db'), type='function', index=0)]))], created=1746146800, model='deepseek-chat', object='chat.completion', service_tier=None, system_fingerprint='fp_8802369eaa_prod0425fp8', usage=CompletionUsage(completion_tokens=37, prompt_tokens=178, total_tokens=215, completion_tokens_details=None, prompt_tokens_details=PromptTokensDetails(audio_tokens=None, cached_tokens=128), prompt_cache_hit_tokens=128, prompt_cache_miss_tokens=50))
            logging.info(f"Response : {response}")

            sql_args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
            sql_query = sql_args["sql"]
            logging.info(f"Generated SQL: {sql_query}")

            # Execute SQL query
            result = await client.call_tool("query_db", {"sql": sql_query})
            logging.info("Query result:")
            logging.info(result)

            # Explain result using OpenAI
            explanation = clientOpenai.chat.completions.create(
                model="deepseek-chat",
                messages=[{
                    "role": "system",
                    "content": "你是一个数据库查询结果解释助手。请用简单的中文解释查询结果。"
                },
                {
                    "role": "user", 
                    "content": f"请用通俗易懂的中文解释这个查询结果:\n{result}"
                }]
            )
            logging.info("Result explanation:")
            logging.info(explanation.choices[0].message.content)

    except Exception as e:
        logging.error(f"Error occurred: {str(e)}", exc_info=True)
    finally:
        # Disconnect
        await client.disconnect()
        logging.info("Disconnected from MCP server")

if __name__ == "__main__":
    asyncio.run(main())
