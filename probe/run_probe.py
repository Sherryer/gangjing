"""
探针主程序
==========
运行方式：
    python probe/run_probe.py                    # 跑默认样本（代码）
    python probe/run_probe.py --type code        # 指定样本类型
    python probe/run_probe.py --type business
    python probe/run_probe.py --type content
    python probe/run_probe.py --type all         # 跑全部三个样本
    python probe/run_probe.py --level 3          # 指定杠精等级
    python probe/run_probe.py --provider openai  # 指定提供商

验证目标：
    ✅ 输出格式是否符合 Review Report 模板
    ✅ P 级分类是否与预期答案一致
    ✅ 问题定位是否精准（有行号/段落）
    ✅ 修复建议是否可执行
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# 把项目根目录加入 sys.path，确保能 import 项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.critic_shrimp import review
from probe.test_samples import SAMPLES


def run_single(sample_type: str, critic_level: int, provider: str | None):
    """跑单个样本并打印结果"""
    print("\n" + "=" * 60)
    print(f"  探针测试：{sample_type} 样本  |  Level {critic_level}  |  {provider or 'default'}")
    print("=" * 60 + "\n")

    content = SAMPLES[sample_type]
    report = review(
        content=content,
        content_type=sample_type,
        critic_level=critic_level,
        provider=provider,
    )

    print("\n" + "─" * 60)
    print("  Review Report 输出：")
    print("─" * 60)
    print(report)

    # 保存到文件，方便对比分析
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"probe_{sample_type}_L{critic_level}_{timestamp}.md"
    output_file.write_text(report, encoding="utf-8")
    print(f"\n[已保存到] {output_file}")


def main():
    parser = argparse.ArgumentParser(description="杠精虾探针测试")
    parser.add_argument(
        "--type", "-t",
        choices=["code", "business", "content", "all"],
        default="code",
        help="测试样本类型（默认：code）"
    )
    parser.add_argument(
        "--level", "-l",
        type=int,
        choices=[1, 2, 3],
        default=2,
        help="杠精等级 1=温柔 2=正常 3=魔鬼（默认：2）"
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["deepseek", "claude", "openai", "qwen", "venus"],
        default=None,
        help="LLM 提供商（默认：用 config.py 里的 DEFAULT_PROVIDER）"
    )

    args = parser.parse_args()

    if args.type == "all":
        for sample_type in ["code", "business", "content"]:
            run_single(sample_type, args.level, args.provider)
    else:
        run_single(args.type, args.level, args.provider)


if __name__ == "__main__":
    main()
