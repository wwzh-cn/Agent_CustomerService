"""
生成技能清单文档 (skill.md)

使用 EnhancedSkill 实例生成完整的技能清单 markdown 文档。
保持最小代码变更原则，不修改现有项目结构。

注意：此脚本仅用于演示 skill.md 生成功能，不直接集成到主项目。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_skill import generate_skill_markdown
from create_enhanced_skills import (
    create_weather_enhanced_skill,
    create_location_enhanced_skill,
    create_rag_enhanced_skill,
)


def main():
    """生成技能清单文档"""
    # 创建增强技能实例
    weather_skill = create_weather_enhanced_skill()
    location_skill = create_location_enhanced_skill()
    rag_skill = create_rag_enhanced_skill()

    skills = [weather_skill, location_skill, rag_skill]

    # 生成 markdown 内容
    md_content = generate_skill_markdown(skills)

    # 保存到文件
    output_dir = os.path.join(os.path.dirname(__file__), "skills")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "skill.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"技能清单文档已生成: {output_path}")
    print(f"文档大小: {len(md_content)} 字符")
    print(f"包含技能数量: {len(skills)}")

    # 预览前500字符
    print("\n文档预览 (前500字符):")
    print("-" * 50)
    print(md_content[:500])
    print("..." if len(md_content) > 500 else "")
    print("-" * 50)


if __name__ == "__main__":
    main()