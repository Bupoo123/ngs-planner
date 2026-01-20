#!/bin/bash
# mNGS实验排布工具使用示例

# 基本用法
echo "运行基本排布..."
python3 main.py -i "attachments/Input table.xlsx"

# 完整参数用法
echo "运行完整参数排布..."
python3 main.py \
  --input "attachments/Input table.xlsx" \
  --rules "attachments/规则.xlsx" \
  --nc "attachments/NC.xlsx" \
  --pc "attachments/PC.xlsx" \
  --species "attachments/物种列表.xlsx" \
  --sequencer "attachments/测序仪对应关系.xlsx" \
  --lib-template "attachments/文库表模版.xlsx" \
  --chip-template "attachments/芯片表模版.xlsx" \
  --output "output" \
  --project "F项目" \
  --chip-capacity 96 \
  --start-date "2026-01-16"

echo "完成！请查看 output/ 目录中的输出文件。"
