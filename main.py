#!/usr/bin/env python3
"""
mNGS实验排布工具主程序
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime
from src.parser import InputParser, RulesParser, ReferenceParser
from src.planner import LibraryPlanner, ChipPlanner
from src.generator import OutputGenerator


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='mNGS实验排布工具 - 自动化生成文库表和芯片表'
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='输入表Excel文件路径'
    )
    
    parser.add_argument(
        '--rules', '-r',
        type=str,
        default='attachments/规则.xlsx',
        help='规则文件路径（默认: attachments/规则.xlsx）'
    )
    
    parser.add_argument(
        '--nc', '-n',
        type=str,
        default='attachments/NC.xlsx',
        help='阴性对照文件路径（默认: attachments/NC.xlsx）'
    )
    
    parser.add_argument(
        '--pc', '-p',
        type=str,
        default='attachments/PC.xlsx',
        help='阳性对照文件路径（默认: attachments/PC.xlsx）'
    )
    
    parser.add_argument(
        '--species', '-s',
        type=str,
        default='attachments/物种列表.xlsx',
        help='物种列表文件路径（默认: attachments/物种列表.xlsx）'
    )
    
    parser.add_argument(
        '--sequencer', '-q',
        type=str,
        default='attachments/测序仪对应关系.xlsx',
        help='测序仪对应关系文件路径（默认: attachments/测序仪对应关系.xlsx）'
    )
    
    parser.add_argument(
        '--lib-template', '-lt',
        type=str,
        default='ref/文库表模版.xlsx',
        help='文库表模板文件路径（默认: ref/文库表模版.xlsx）'
    )
    
    parser.add_argument(
        '--chip-template', '-ct',
        type=str,
        default='ref/芯片表模版.xlsx',
        help='芯片表模板文件路径（默认: ref/芯片表模版.xlsx）'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='output',
        help='输出目录（默认: output）'
    )
    
    parser.add_argument(
        '--project', '-j',
        type=str,
        default='F项目',
        help='项目名称（默认: F项目）'
    )
    
    parser.add_argument(
        '--chip-capacity', '-c',
        type=int,
        default=96,
        help='芯片容量（默认: 96）'
    )
    
    parser.add_argument(
        '--start-date', '-d',
        type=str,
        default=None,
        help='开始日期（格式: YYYY-MM-DD，默认: 今天）'
    )
    
    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not Path(args.input).exists():
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)
    
    print("=" * 60)
    print("mNGS实验排布工具")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"项目名称: {args.project}")
    print(f"芯片容量: {args.chip_capacity}")
    print()
    
    # 解析输入文件
    print("步骤 1/5: 解析输入表...")
    input_parser = InputParser(args.input)
    input_data = input_parser.parse()
    print(f"  找到 {len(input_data['samples'])} 个样本")
    meta = input_data.get("meta", {})
    # CLI参数优先：注入chip_capacity，供芯片表数量计算使用
    meta["chip_capacity"] = int(args.chip_capacity)
    
    # 解析规则文件
    print("步骤 2/5: 解析规则文件...")
    rules_parser = RulesParser(args.rules)
    rules = rules_parser.parse()
    print(f"  加载了 {len(rules)} 条规则")
    
    # 解析参考文件
    print("步骤 3/5: 解析参考文件...")
    ref_parser = ReferenceParser(
        nc_file=args.nc if Path(args.nc).exists() else None,
        pc_file=args.pc if Path(args.pc).exists() else None,
        species_file=args.species if Path(args.species).exists() else None,
        sequencer_file=args.sequencer if Path(args.sequencer).exists() else None
    )
    nc_list = ref_parser.parse_nc()
    pc_list = ref_parser.parse_pc()
    species_info = ref_parser.parse_species()
    sequencer_info = ref_parser.parse_sequencer()
    print(f"  阴性对照: {len(nc_list)} 条")
    print(f"  阳性对照: {len(pc_list)} 条")
    print(f"  物种信息: {len(species_info)} 条")
    print(f"  测序仪信息: {len(sequencer_info)} 条")
    
    # 规划芯片（按输入表meta）
    print("步骤 4/5: 规划芯片排布...")
    chip_planner = ChipPlanner(rules=rules, sequencer_info=sequencer_info)
    chips = chip_planner.plan_chips_from_input(meta)
    print(f"  生成了 {len(chips)} 个芯片")

    # 规划文库（按规则：芯片SN+SN后三位+接头+日期）
    print("步骤 5/5: 生成文库表...")
    adapter_start = meta.get("接头起点") or "A01"
    library_planner = LibraryPlanner(
        rules=rules,
        species_info=species_info,
        adapter_start=str(adapter_start).strip(),
        pc_list=pc_list,
        nc_list=nc_list,
        pc_spike_rpm_range=str(meta.get("F-PC__value3") or "").strip(),
        nc_spike_rpm_range=str(meta.get("F-NC__value3") or "").strip(),
    )
    libraries = library_planner.plan_libraries(
        samples=input_data["samples"],
        chips=chips,
        research_id=str(meta.get("研究编号") or "").strip(),
        chip_capacity=int(args.chip_capacity),
        include_controls_once=False,
        include_controls_per_chip=True,
    )
    print(f"  生成了 {len(libraries)} 条文库记录")
    
    # 生成输出文件
    print("\n生成输出文件...")
    generator = OutputGenerator(output_dir=args.output)
    
    # 生成合并输出
    output_file = generator.generate_combined_output(
        libraries=libraries,
        chips=chips,
        lib_template_file=args.lib_template if Path(args.lib_template).exists() else None,
        chip_template_file=args.chip_template if Path(args.chip_template).exists() else None,
    )
    print(f"✓ 合并输出文件: {output_file}")
    
    # 生成单独的文库表和芯片表
    lib_file = generator.generate_library_table(
        libraries=libraries,
        template_file=args.lib_template if Path(args.lib_template).exists() else None
    )
    print(f"✓ 文库表: {lib_file}")
    
    chip_file = generator.generate_chip_table(
        chips=chips,
        template_file=args.chip_template if Path(args.chip_template).exists() else None
    )
    print(f"✓ 芯片表: {chip_file}")
    
    print("\n" + "=" * 60)
    print("排布完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
