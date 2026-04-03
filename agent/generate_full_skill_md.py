"""
生成完整技能清单文档 (skill.md)

使用integrate_enhanced_skills模块生成包含所有7个工具的完整技能清单markdown文档。
保持最小代码变更原则，不修改现有项目结构。

注意：此脚本用于生成完整的技能清单文档，包含所有工具。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_skill import generate_skill_markdown
from integrate_enhanced_skills import create_all_enhanced_skills


def main():
    """生成完整技能清单文档"""
    # 创建所有增强技能实例
    skills = create_all_enhanced_skills()

    # 生成 markdown 内容
    md_content = generate_skill_markdown(skills)

    # 保存到文件
    output_dir = os.path.join(os.path.dirname(__file__), "skills")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "skill_full.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"完整技能清单文档已生成: {output_path}")
    print(f"文档大小: {len(md_content)} 字符")
    print(f"包含技能数量: {len(skills)}")

    # 按分类统计
    categories = {}
    for skill in skills:
        cat = skill.category
        categories[cat] = categories.get(cat, 0) + 1

    print("\n技能分类统计:")
    for cat, count in categories.items():
        print(f"  {cat}: {count} 个技能")

    # 预览前800字符
    print("\n文档预览 (前800字符):")
    print("-" * 50)
    print(md_content[:800])
    print("..." if len(md_content) > 800 else "")
    print("-" * 50)

    # 同时保存一份到skill.md（覆盖原有）
    main_output_path = os.path.join(output_dir, "skill.md")
    with open(main_output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n同时保存到主文档: {main_output_path}")


if __name__ == "__main__":
    main()