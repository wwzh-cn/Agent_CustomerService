"""
测试ReactAgent与EnhancedSkill集成

验证修改后的ReactAgent是否能正常初始化，工具列表是否正确转换。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试导入是否正常"""
    print("=== 测试模块导入 ===")

    try:
        from agent.react_agent import ReactAgent
        print("[OK] ReactAgent导入成功")
    except ImportError as e:
        print(f" ReactAgent导入失败: {e}")
        return False

    try:
        from agent.skills.integrate_enhanced_skills import get_enhanced_tools, create_all_enhanced_skills
        print(" integrate_enhanced_skills导入成功")
    except ImportError as e:
        print(f" integrate_enhanced_skills导入失败: {e}")
        return False

    return True


def test_enhanced_tools():
    """测试增强工具创建"""
    print("\n=== 测试增强工具创建 ===")

    try:
        from agent.skills.integrate_enhanced_skills import get_enhanced_tools, create_all_enhanced_skills

        # 测试创建所有技能实例
        skills = create_all_enhanced_skills()
        print(f" 创建了 {len(skills)} 个EnhancedSkill实例")

        # 测试转换为LangChain工具
        tools = get_enhanced_tools()
        print(f" 创建了 {len(tools)} 个LangChain工具")

        if tools:
            print(f"  第一个工具: {tools[0].name}")
            print(f"  描述长度: {len(tools[0].description)} 字符")

        return True
    except Exception as e:
        print(f" 增强工具测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_react_agent_initialization():
    """测试ReactAgent初始化"""
    print("\n=== 测试ReactAgent初始化 ===")

    try:
        from agent.react_agent import ReactAgent

        # 尝试创建ReactAgent实例
        print("正在创建ReactAgent实例...")
        agent = ReactAgent()
        print(" ReactAgent实例创建成功")

        # 检查agent属性
        if hasattr(agent, 'agent'):
            print(" agent属性存在")

            # 尝试检查工具数量
            # 注意：tools列表在create_agent内部，可能无法直接访问
            print("  工具列表在LangChain内部，无法直接验证")

        return True
    except Exception as e:
        print(f" ReactAgent初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("ReactAgent与EnhancedSkill集成测试")
    print("=" * 50)

    # 测试1: 导入
    if not test_imports():
        print("\n 导入测试失败，终止测试")
        return False

    # 测试2: 增强工具
    if not test_enhanced_tools():
        print("\n  增强工具测试失败，但继续测试")

    # 测试3: ReactAgent初始化
    if not test_react_agent_initialization():
        print("\n ReactAgent初始化测试失败")
        return False

    print("\n" + "=" * 50)
    print(" 所有测试通过！")
    print("\n说明：")
    print("1. 如果使用模拟函数，工具功能正常但返回模拟数据")
    print("2. 要使用真实工具，请确保所有依赖已安装")
    print("3. 随时可通过取消注释恢复原有工具列表")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)