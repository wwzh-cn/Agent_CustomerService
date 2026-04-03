# 高德MCP替换实施计划

## 项目背景
当前智扫通机器人智能客服系统中，`agent/tools/agent_tools.py` 文件包含两个手写的高德API调用函数：
1. `get_weather(city: str) -> str` - 直接HTTP调用高德天气API
2. `get_user_location() -> str` - 直接HTTP调用高德IP定位API

**目标**：将这两个手写函数替换为高德官方MCP实现，保持函数接口完全不变。

## 当前状态验证
✅ **MCP连接已验证成功**：通过测试脚本确认可以连接高德MCP服务器，获取到15个工具
✅ **API Key有效**：现有 `gaodekey: f2f13fe4721c1babe351a75e005e6de2` 可用
⚠️ **需要工具识别**：需具体识别天气和定位对应的MCP工具

## 核心原则
1. **接口不变**：保持原有函数名、参数、返回值格式
2. **简单直接**：最小化代码改动，避免复杂架构
3. **无缝替换**：用户无需感知底层实现变更

## 实施步骤

### 第1步：工具识别与验证（今天）
**目的**：确定使用哪个高德MCP工具

1. **运行工具识别脚本**
   ```bash
   python mcp-test/identify_gaode_tools.py
   ```

2. **分析输出结果**
   - 查找天气相关工具（关键词：weather, 天气, climate）
   - 查找定位相关工具（关键词：location, 定位, ip, geocode）
   - 记录工具名称、参数格式、返回值格式

3. **确定适配方案**
   - **方案A**：找到完全匹配的工具 → 直接调用
   - **方案B**：工具接口略有差异 → 简单参数适配
   - **方案C**：找不到合适工具 → 保留原实现或寻找替代方案

### 第2步：创建MCP客户端模块（今天）
**目的**：封装高德MCP连接逻辑

创建文件：`agent/mcp_client.py`
```python
import os
import asyncio
import yaml
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils.logger_handler import logger

class GaodeMCPClient:
    """高德MCP客户端"""

    def __init__(self):
        # 从现有配置文件读取API Key
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "agent.yml")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self.api_key = config["gaodekey"]

        # 初始化MCP客户端
        self.client = MultiServerMCPClient({
            "amap-amap-sse": {
                "url": f"https://mcp.amap.com/sse?key={self.api_key}",
                "transport": "sse"
            }
        })

    async def get_tools(self):
        """获取所有MCP工具"""
        return await self.client.get_tools()

    async def call_weather(self, city: str) -> str:
        """调用高德MCP天气工具"""
        # 根据第1步识别的具体工具实现
        pass

    async def call_location(self) -> str:
        """调用高德MCP定位工具"""
        # 根据第1步识别的具体工具实现
        pass
```

### 第3步：修改现有函数（明天）
**目的**：用MCP实现替换手写逻辑

修改文件：`agent/tools/agent_tools.py`
```python
# 在文件顶部添加导入
from agent.mcp_client import GaodeMCPClient
import asyncio

# 创建全局MCP客户端实例（惰性初始化）
_mcp_client = None

def _get_mcp_client():
    """获取MCP客户端（惰性初始化）"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = GaodeMCPClient()
    return _mcp_client

@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city: str) -> str:
    """使用高德MCP实现的天气查询"""
    if not city or not city.strip():
        return "未提供城市名称，无法查询天气"

    try:
        client = _get_mcp_client()
        # 同步调用异步函数
        return asyncio.run(client.call_weather(city.strip()))
    except Exception as e:
        logger.error(f"[get_weather]MCP天气查询失败 city={city} err={str(e)}")
        # 保持原有错误消息格式
        return f"城市{city}天气查询失败，请稍后重试"

@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    """使用高德MCP实现的用户定位"""
    try:
        client = _get_mcp_client()
        return asyncio.run(client.call_location())
    except Exception as e:
        logger.error(f"[get_user_location]MCP定位失败 err={str(e)}")
        # 保持原有错误消息格式
        return "未知城市"
```

### 第4步：依赖安装与测试（明天）
**目的**：验证功能正确性

1. **安装依赖**
   ```bash
   pip install langchain-mcp-adapters
   ```

2. **功能测试**
   ```python
   # 测试天气查询
   python -c "
   import asyncio
   from agent.tools.agent_tools import get_weather
   print('天气测试:', get_weather('北京'))
   "

   # 测试定位
   python -c "
   import asyncio
   from agent.tools.agent_tools import get_user_location
   print('定位测试:', get_user_location())
   "
   ```

3. **集成测试**
   - 运行现有系统的测试用例
   - 验证其他功能不受影响

## 错误处理策略
1. **MCP连接失败**：记录日志，返回与原函数相同的错误消息
2. **工具调用失败**：记录详细错误，返回友好提示
3. **参数格式不匹配**：在适配层进行转换处理

## 回滚方案
如果MCP实现有问题，可快速回退：
1. 恢复 `agent/tools/agent_tools.py` 的原有实现
2. 删除 `agent/mcp_client.py` 文件
3. 移除 `langchain-mcp-adapters` 依赖

## 时间预估
- **第1步**：0.5天（今天）
- **第2-3步**：1天（明天）
- **第4步**：0.5天（明天）
- **总计**：2天

## 成功标准
1. ✅ `get_weather("北京")` 返回与原实现相同格式的天气信息
2. ✅ `get_user_location()` 返回与原实现相同格式的城市名称
3. ✅ 错误处理保持原有格式和消息
4. ✅ 系统其他功能不受影响

## 下一步行动
**立即执行**：运行工具识别脚本，确定具体使用的高德MCP工具
```bash
cd d:/code/zhisaotong-Agent-master
python mcp-test/identify_gaode_tools.py
```