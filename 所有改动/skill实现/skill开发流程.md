# EnhancedSkill 开发流程与执行计划

## 🎯 项目目标
通过**增强工具描述质量**，帮助 LLM 更准确、快速地选择工具，减少思考步骤和试错调用，从而**节约 Token 消耗**。保持最小代码变更，不改变原有调用逻辑。

---

## 🔄 开发流程（3个阶段）

### **阶段一：分析与设计**（约0.5天）
1. **分析现有工具** - 列出 `agent/tools/agent_tools.py` 中所有 `@tool` 装饰函数，识别描述不足
2. **设计 EnhancedSkill 类** - 定义字段结构：`name`, `description`, `category`, `examples`, `parameters`, `constraints`, `func`
3. **设计 skill.md 格式** - 定义技能清单文档结构，包含：技能名称、分类、描述、参数、示例、限制等字段
4. **制定优化方案** - 为关键工具编写增强描述草稿：
   - `get_weather`：天气查询 Skill
   - `get_user_location`：用户定位 Skill
   - `rag_summarize`：知识库检索 Skill

### **阶段二：实现核心**（约1天）
1. **创建 EnhancedSkill 类** - `agent/enhanced_skill.py`：实现描述增强和 LangChain Tool 转换
2. **实现 skill.md 生成功能** - 在 EnhancedSkill 类中添加 `to_markdown()` 方法，支持生成技能清单文档
3. **重写关键工具** - 创建3个典型 EnhancedSkill 实例：
   - `WeatherEnhancedSkill`：详细天气查询描述
   - `LocationEnhancedSkill`：定位功能说明
   - `RagEnhancedSkill`：检索功能指南
4. **实现转换方法** - `to_langchain_tool()`：生成优化后的结构化描述
5. **生成 skill.md 文档** - 运行脚本生成 `agent/skills/skill.md` 技能清单

### **阶段三：集成测试**（约0.5天）
1. **修改 ReactAgent** - `agent/react_agent.py`：替换工具列表为 EnhancedSkill 转换结果
2. **生成并验证 skill.md** - 检查技能清单文档生成正确性，确保格式清晰、信息完整
3. **功能验证** - 启动 Streamlit 应用，确保原有功能正常工作
4. **效果测试** - 对比优化前后 LLM 工具选择表现（主观评估）

---

## 📊 执行计划（按优先级排序）

| 优先级 | 任务 | 目标 | 预期耗时 | 阶段 |
|--------|------|------|----------|------|
| **P0** | 分析现有工具描述问题 | 识别关键优化点，制定优化策略 | 0.2天 | 阶段一 |
| **P0** | 设计 EnhancedSkill 类结构 | 定义增强描述字段，保持最小化 | 0.2天 | 阶段一 |
| **P0** | 设计 skill.md 格式 | 定义技能清单文档结构，确保信息完整 | 0.1天 | 阶段一 |
| **P0** | 实现 EnhancedSkill 基类 | `agent/enhanced_skill.py`，包含转换方法 | 0.4天 | 阶段二 |
| **P0** | 实现 skill.md 生成功能 | 添加 `to_markdown()` 方法，支持文档生成 | 0.2天 | 阶段二 |
| **P0** | 创建 WeatherEnhancedSkill | 天气查询工具描述优化 | 0.2天 | 阶段二 |
| **P0** | 生成 skill.md 文档 | 运行脚本生成 `agent/skills/skill.md` 技能清单 | 0.1天 | 阶段二 |
| **P0** | 修改 ReactAgent 集成 | 替换工具列表，保持功能正常 | 0.2天 | 阶段三 |
| **P1** | 创建 LocationEnhancedSkill | 用户定位工具描述优化 | 0.2天 | 阶段二 |
| **P1** | 创建 RagEnhancedSkill | 知识检索工具描述优化 | 0.2天 | 阶段二 |
| **P1** | 验证 skill.md 文档 | 检查技能清单格式正确性、信息完整性 | 0.1天 | 阶段三 |
| **P2** | 效果测试与对比 | 验证 Token 节约效果（主观评估） | 0.2天 | 阶段三 |

---

## ⚠️ 简化原则（重点把握）

1. **不改变原有调用逻辑** - EnhancedSkill 仅包装现有 `@tool` 函数，保持 `func` 直接引用
2. **最小架构变更** - 不引入复杂注册、发现机制，仅优化描述信息
3. **向后兼容** - 随时可回退到原始 `@tool` 描述，风险极低
4. **描述简洁有效** - 只增加必要信息：分类、示例、参数说明、限制
5. **保持 MCP 兼容** - 不修改 MCP 客户端调用路径和错误处理

---

## 🎯 预期效果与验证

### **核心指标**
- **工具选择准确率提升**：+30-50%（通过清晰描述匹配用户意图）
- **平均思考步骤减少**：-30% Token 消耗（减少试错和犹豫）
- **参数验证失败减少**：-50% 错误调用（明确参数格式要求）

### **验证方法**
1. **skill.md 文档验证**：检查生成文档格式正确性、信息完整性、可读性
2. **人工测试用例**：设计10个典型用户查询（如"北京热吗？"、"我在哪？"、"扫地机器人推荐"）
3. **对比观察**：记录优化前后 LLM 的思考步骤和工具选择
4. **主观评估**：评估工具选择准确性和响应速度提升

### **成功标准**
1. ✅ 原有功能100%正常（天气、定位、RAG检索）
2. ✅ skill.md 文档生成正确，格式清晰、信息完整
3. ✅ LLM 工具选择更准确、更快速（主观评估）
4. ✅ 代码变更量最小（<120行核心代码，包含 skill.md 生成）
5. ✅ 随时可回退到原始状态，风险可控

---

## 🔧 技术实现要点

### **EnhancedSkill 类设计**
```python
class EnhancedSkill:
    name: str                    # 工具名称（与 @tool 函数名一致）
    description: str             # 详细功能描述（何时调用、解决什么问题）
    category: str                # 分类：查询/计算/数据/通信
    examples: List[str]          # 2-3个调用示例（自然语言格式）
    parameters: Dict[str, str]   # 参数说明 {参数名: 说明}
    constraints: List[str]       # 使用限制（如"仅支持中国城市"）
    func: Callable               # 原有的 @tool 装饰函数

    def to_langchain_tool(self) -> Tool:
        """转换为 LangChain Tool，生成优化后的结构化描述"""

    def to_markdown(self) -> str:
        """生成 skill.md 格式的 markdown 片段"""
        # 返回格式化的技能描述
        return f"""
## {self.name}

**分类**: {self.category}
**描述**: {self.description}
**参数**: {self._format_parameters()}
**示例**: {self._format_examples()}
**限制**: {self._format_constraints()}
        """.strip()
```

### **skill.md 文档设计**
```markdown
# 技能清单 (Skills Directory)

## get_weather
**分类**: 查询类
**描述**: 查询中国城市实时天气信息，包括温度、湿度、风力等
**参数**: city (必填) - 中文城市名称，如"北京"、"上海市"
**示例**:
  - "查询北京的天气"
  - "上海今天天气怎么样"
  - "get_weather(city='广州')"
**限制**:
  - 仅支持中国城市
  - 需要网络连接
  - 数据来自高德天气API

## get_user_location
**分类**: 查询类
**描述**: 根据用户IP地址自动定位所在城市
**参数**: 无
**示例**:
  - "我在哪个城市？"
  - "获取我的位置"
  - "定位用户所在城市"
**限制**:
  - 依赖用户公网IP
  - 定位精度为城市级别

## rag_summarize
**分类**: 检索类
**描述**: 从知识库检索相关文档并总结回答
**参数**: query (必填) - 用户查询文本
**示例**:
  - "扫地机器人推荐"
  - "小户型适合哪些扫地机器人"
  - "rag_summarize(query='故障排除')"
**限制**:
  - 依赖向量数据库
  - 检索结果基于已有知识库
```

### **skill.md 生成流程**
```python
# 生成技能清单文档
def generate_skill_markdown(skills: List[EnhancedSkill]) -> str:
    content = "# 技能清单 (Skills Directory)\n\n"
    for skill in skills:
        content += skill.to_markdown() + "\n\n"
    return content

# 保存到文件
with open("agent/skills/skill.md", "w", encoding="utf-8") as f:
    f.write(generate_skill_markdown(skills))
```

### **工作流程对比**
```
❌ 原有流程:
用户查询 → LLM思考(@tool简单描述) → 可能试错 → 调用工具 → 返回结果

✅ 优化后流程:
用户查询 → LLM思考(EnhancedSkill详细描述) → 准确匹配 → 调用同一工具 → 返回结果
                      ↑
                （仅描述优化，调用逻辑不变）
```

### **与现有代码集成**
```python
# 修改前（react_agent.py）
tools=[get_weather, get_user_location, rag_summarize]

# 修改后（react_agent.py）
weather_skill = WeatherEnhancedSkill(func=get_weather)
location_skill = LocationEnhancedSkill(func=get_user_location)
rag_skill = RagEnhancedSkill(func=rag_summarize)

tools = [
    weather_skill.to_langchain_tool(),
    location_skill.to_langchain_tool(),
    rag_skill.to_langchain_tool(),
]
```

---

## 🎓 核心价值

通过**最小代码变更**实现**最大描述优化**：

1. **直接帮助 LLM 决策**：清晰的分类、示例、参数说明让 LLM 更易理解工具用途
2. **减少思考试错**：明确的使用场景和限制条件减少犹豫和错误选择
3. **节约 Token 消耗**：更快的工具选择意味着更少的思考步骤和 Token 使用
4. **保持架构简单**：不改变原有调用逻辑，随时可回退，风险极低

**关键心态**：将此视为一次**描述优化实验**，重点是验证"更好的工具描述能否帮助 LLM 更高效工作"，为未来的工具设计提供实践经验。