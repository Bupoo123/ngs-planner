#!/usr/bin/env python3
"""
简单测试脚本 - 只测试文件读取
"""
import sys
from pathlib import Path

print("测试1: 检查文件是否存在")
input_file = Path("attachments/Input table.xlsx")
if input_file.exists():
    print(f"✓ 文件存在: {input_file}")
    print(f"  文件大小: {input_file.stat().st_size} 字节")
else:
    print(f"✗ 文件不存在: {input_file}")
    sys.exit(1)

print("\n测试2: 检查pandas和openpyxl")
try:
    import pandas as pd
    print(f"✓ pandas版本: {pd.__version__}")
except ImportError:
    print("✗ pandas未安装")
    sys.exit(1)

try:
    import openpyxl
    print(f"✓ openpyxl版本: {openpyxl.__version__}")
except ImportError:
    print("✗ openpyxl未安装")
    sys.exit(1)

print("\n测试3: 尝试读取Excel文件")
try:
    df = pd.read_excel(input_file, engine='openpyxl')
    print(f"✓ 成功读取文件")
    print(f"  列名: {list(df.columns)}")
    print(f"  行数: {len(df)}")
    if len(df) > 0:
        print(f"  前3行数据:")
        print(df.head(3).to_string())
except Exception as e:
    print(f"✗ 读取失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n所有测试通过！")
