#!/bin/bash

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 切换到项目目录
cd "$SCRIPT_DIR"

# 设置终端窗口标题
echo -ne "\033]0;mNGS实验排布工具 - Web服务器\007"

# 清屏
clear

# 显示启动信息
echo "=========================================="
echo "  mNGS实验排布工具 - Web前端服务器"
echo "=========================================="
echo ""
echo "项目目录: $SCRIPT_DIR"
echo "访问地址: http://localhost:5123"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "=========================================="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

# 检查依赖是否安装
if ! python3 -c "import flask" 2>/dev/null; then
    echo "警告: Flask 未安装，正在尝试安装依赖..."
    echo ""
    pip3 install -r requirements.txt
    echo ""
fi

# 启动Flask服务器
echo "正在启动服务器..."
echo ""
python3 app.py

# 如果服务器意外退出，暂停以便查看错误信息
if [ $? -ne 0 ]; then
    echo ""
    echo "服务器启动失败，请检查错误信息"
    echo ""
    read -p "按回车键退出..."
fi
