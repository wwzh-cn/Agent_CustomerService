"""
验证EnhancedSkill集成

轻量级验证脚本，不依赖完整环境，只检查代码集成是否正确。
"""

import os
import sys


def check_file_exists(filepath, desc):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"[OK] {desc}: {filepath}")
        return True
    else:
        print(f"[FAIL] {desc}: 文件不存在")
        return False


def check_import(module_name, desc):
    """检查模块导入"""
    try:
        __import__(module_name)
        print(f"[OK] {desc}: 导入成功")
        return True
    except ImportError as e:
        print(f"[WARN] {desc}: 导入失败 - {e}")
        return False


def check_react_agent_modifications():
    """检查ReactAgent的修改"""
    print("\n=== 检查ReactAgent修改 ===")

    filepath = "agent/react_agent.py"
    if not check_file_exists(filepath, "ReactAgent文件"):
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        checks = [
            ("原有工具导入被注释", "# from agent.tools.agent_tools import"),
            ("增强技能导入", "from agent.skills.integrate_enhanced_skills import"),
            ("原有工具列表被注释", "# tools=[rag_summarize, get_weather"),
            ("使用增强工具", "tools=get_enhanced_tools()"),
        ]

        all_pass = True
        for desc, pattern in checks:
            if pattern in content:
                print(f"[OK] {desc}")
            else:
                print(f"[FAIL] {desc}: 未找到模式 '{pattern}'")
                all_pass = False

        return all_pass
    except Exception as e:
        print(f"[FAIL] 读取ReactAgent文件失败: {e}")
        return False


def check_enhanced_skills():
    """检查EnhancedSkill相关文件"""
    print("\n=== 检查EnhancedSkill相关文件 ===")

    files_to_check = [
        ("agent/enhanced_skill.py", "EnhancedSkill基类"),
        ("agent/integrate_enhanced_skills.py", "集成脚本"),
        ("agent/create_enhanced_skills.py", "创建脚本"),
        ("agent/generate_full_skill_md.py", "文档生成脚本"),
        ("agent/skills/skill.md", "技能清单文档"),
    ]

    all_pass = True
    for filepath, desc in files_to_check:
        all_pass = check_file_exists(filepath, desc) and all_pass

    return all_pass


def check_skill_md_content():
    """检查skill.md内容"""
    print("\n=== 检查skill.md内容 ===")

    filepath = "agent/skills/skill.md"
    if not os.path.exists(filepath):
        print("[FAIL] skill.md文件不存在")
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        checks = [
            ("文档标题", "# 技能清单 (Skills Directory)"),
            ("rag_summarize技能", "## rag_summarize"),
            ("get_weather技能", "## get_weather"),
            ("get_user_location技能", "## get_user_location"),
            ("分类信息", "**分类**: "),
            ("参数说明", "**参数**: "),
            ("示例信息", "**示例**: "),
            ("限制信息", "**限制**: "),
        ]

        all_pass = True
        for desc, pattern in checks:
            if pattern in content:
                print(f"[OK] {desc}")
            else:
                print(f"[FAIL] {desc}: 未找到模式 '{pattern}'")
                all_pass = False

        # 检查技能数量
        import re
        skill_count = len(re.findall(r'^## \w+', content, re.MULTILINE))
        print(f"[INFO] 技能数量: {skill_count}")

        return all_pass
    except Exception as e:
        print(f"[FAIL] 读取skill.md失败: {e}")
        return False


def check_revert_possibility():
    """检查是否可随时恢复原有逻辑"""
    print("\n=== 检查可恢复性 ===")

    filepath = "agent/react_agent.py"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查是否有注释掉的原有代码
        original_import = "# from agent.tools.agent_tools import"
        original_tools = "# tools=[rag_summarize, get_weather"

        if original_import in content and original_tools in content:
            print("[OK] 原有代码已注释，可随时恢复")
            print("[INFO] 恢复方法:")
            print("  1. 取消注释原有工具导入")
            print("  2. 取消注释原有工具列表")
            print("  3. 注释增强技能导入和工具列表")
            return True
        else:
            print("[FAIL] 原有代码未正确注释")
            return False
    except Exception as e:
        print(f"[FAIL] 检查可恢复性失败: {e}")
        return False


def main():
    """主验证函数"""
    print("EnhancedSkill集成验证")
    print("=" * 60)

    # 添加当前目录到Python路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    results = []

    # 检查ReactAgent修改
    results.append(("ReactAgent修改", check_react_agent_modifications()))

    # 检查EnhancedSkill文件
    results.append(("EnhancedSkill文件", check_enhanced_skills()))

    # 检查skill.md内容
    results.append(("skill.md内容", check_skill_md_content()))

    # 检查可恢复性
    results.append(("可恢复性", check_revert_possibility()))

    print("\n" + "=" * 60)
    print("验证结果汇总:")

    all_pass = True
    for desc, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {desc}: {status}")
        if not passed:
            all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("[SUCCESS] 所有验证通过！EnhancedSkill集成成功。")
        print("\n下一步:")
        print("1. 确保环境依赖已安装: pip install langchain-core langchain")
        print("2. 测试实际功能运行: python -m agent.react_agent")
        print("3. 如需恢复原有逻辑，按上述说明操作")
    else:
        print("⚠️  部分验证失败，请检查以上问题。")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)