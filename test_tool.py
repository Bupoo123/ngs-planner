#!/usr/bin/env python3
"""
测试工具脚本
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.parser import InputParser, RulesParser, ReferenceParser
from src.planner import LibraryPlanner, ChipPlanner
from src.generator import OutputGenerator

def test_tool():
    """测试工具"""
    print("=" * 60)
    print("mNGS实验排布工具 - 测试")
    print("=" * 60)
    
    input_file = "attachments/Input table.xlsx"
    
    # 检查文件是否存在
    if not Path(input_file).exists():
        print(f"错误: 输入文件不存在: {input_file}")
        return False
    
    print(f"\n1. 解析输入文件: {input_file}")
    try:
        input_parser = InputParser(input_file)
        input_data = input_parser.parse()
        print(f"   ✓ 成功解析 {len(input_data['samples'])} 个样本")
        
        if len(input_data['samples']) > 0:
            print(f"   示例样本: {input_data['samples'][0]}")
    except Exception as e:
        print(f"   ✗ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 解析规则文件
    print(f"\n2. 解析规则文件")
    try:
        rules_path = "attachments/规则.xlsx"
        rules = {}
        if Path(rules_path).exists():
            rules_parser = RulesParser(rules_path)
            rules = rules_parser.parse()
            print(f"   ✓ 成功加载 {len(rules)} 条规则")
        else:
            print(f"   ⚠ 规则文件不存在，使用空规则")
    except Exception as e:
        print(f"   ⚠ 规则解析失败: {e}，使用空规则")
        rules = {}
    
    # 解析参考文件
    print(f"\n3. 解析参考文件")
    try:
        ref_parser = ReferenceParser(
            nc_file="attachments/NC.xlsx" if Path("attachments/NC.xlsx").exists() else None,
            pc_file="attachments/PC.xlsx" if Path("attachments/PC.xlsx").exists() else None,
            species_file="attachments/物种列表.xlsx" if Path("attachments/物种列表.xlsx").exists() else None,
            sequencer_file="attachments/测序仪对应关系.xlsx" if Path("attachments/测序仪对应关系.xlsx").exists() else None
        )
        nc_list = ref_parser.parse_nc()
        pc_list = ref_parser.parse_pc()
        species_info = ref_parser.parse_species()
        sequencer_info = ref_parser.parse_sequencer()
        print(f"   ✓ NC: {len(nc_list)}, PC: {len(pc_list)}, 物种: {len(species_info)}, 测序仪: {len(sequencer_info)}")
    except Exception as e:
        print(f"   ⚠ 参考文件解析失败: {e}")
        nc_list = []
        pc_list = []
        species_info = {}
        sequencer_info = {}
    
    # 规划文库
    print(f"\n4. 规划文库排布")
    try:
        library_planner = LibraryPlanner(
            rules=rules,
            nc_list=nc_list,
            pc_list=pc_list,
            species_info=species_info
        )
        libraries = library_planner.plan_libraries(
            samples=input_data['samples'],
            chip_capacity=96
        )
        print(f"   ✓ 生成了 {len(libraries)} 个文库")
        if len(libraries) > 0:
            print(f"   示例文库: {libraries[0]}")
    except Exception as e:
        print(f"   ✗ 文库规划失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 规划芯片
    print(f"\n5. 规划芯片排布")
    try:
        chip_planner = ChipPlanner(
            rules=rules,
            sequencer_info=sequencer_info
        )
        chips = chip_planner.plan_chips(
            libraries=libraries,
            project_name="F项目",
            start_date=datetime.now()
        )
        print(f"   ✓ 生成了 {len(chips)} 个芯片")
        if len(chips) > 0:
            print(f"   示例芯片: {chips[0]}")
    except Exception as e:
        print(f"   ✗ 芯片规划失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 生成输出文件
    print(f"\n6. 生成输出文件")
    try:
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)
        generator = OutputGenerator(output_dir=str(output_dir))
        
        output_file = generator.generate_combined_output(
            libraries=libraries,
            chips=chips
        )
        print(f"   ✓ 成功生成输出文件: {output_file}")
        print(f"   文件大小: {Path(output_file).stat().st_size} 字节")
    except Exception as e:
        print(f"   ✗ 文件生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("测试完成！所有步骤都成功执行。")
    print("=" * 60)
    return True

if __name__ == '__main__':
    success = test_tool()
    sys.exit(0 if success else 1)
