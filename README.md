# mNGS实验排布工具

自动化生成mNGS（宏基因组测序）实验的文库表和芯片表的排布工具。

## 功能特性

- 自动解析输入表（样本和物种信息）
- 根据规则文件进行智能排布
- 支持阴性对照（NC）和阳性对照（PC）
- 自动生成文库编号和index
- 自动分配芯片和测序仪
- 生成符合模板格式的文库表和芯片表
- **Web前端界面**：提供友好的图形化操作界面

## 安装

1. 确保已安装Python 3.8或更高版本

2. 安装依赖包：
```bash
pip3 install -r requirements.txt
```

## 使用方法

### 方式一：Web前端（推荐）

#### macOS用户 - 一键启动

双击 `启动服务器.command` 文件，会自动打开终端并启动服务器。

#### 手动启动

1. 启动Web服务器：
```bash
./run_web.sh
```
或者：
```bash
python3 app.py
```

2. 在浏览器中打开：`http://localhost:5123`

3. 在Web界面中：
   - 上传输入表文件（必需）
   - 可选择上传其他参考文件（如不上传将使用默认文件）
   - 配置参数（项目名称、芯片容量、开始日期等）
   - 点击"开始排布"按钮
   - 等待处理完成后下载结果文件

### 方式二：命令行

#### 基本用法

```bash
python3 main.py -i attachments/Input\ table.xlsx
```

## Docker 运行（推荐部署方式）

### 使用 docker-compose（最简单）

在项目根目录执行：

```bash
docker compose up --build
```

然后浏览器打开：`http://localhost:5123`

- **输出文件**会写到你本机的 `./output/`（compose 已做 volume 挂载）

停止：

```bash
docker compose down
```

### 使用 Dockerfile

```bash
docker build -t ngs-planner:latest .
docker run --rm -p 5123:5123 -v "$(pwd)/output:/app/output" --name ngs-planner ngs-planner:latest
```

#### 完整参数

```bash
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
```

### 参数说明

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--input` | `-i` | 输入表Excel文件路径（必需） | - |
| `--rules` | `-r` | 规则文件路径 | `attachments/规则.xlsx` |
| `--nc` | `-n` | 阴性对照文件路径 | `attachments/NC.xlsx` |
| `--pc` | `-p` | 阳性对照文件路径 | `attachments/PC.xlsx` |
| `--species` | `-s` | 物种列表文件路径 | `attachments/物种列表.xlsx` |
| `--sequencer` | `-q` | 测序仪对应关系文件路径 | `attachments/测序仪对应关系.xlsx` |
| `--lib-template` | `-lt` | 文库表模板文件路径 | `attachments/文库表模版.xlsx` |
| `--chip-template` | `-ct` | 芯片表模板文件路径 | `attachments/芯片表模版.xlsx` |
| `--output` | `-o` | 输出目录 | `output` |
| `--project` | `-j` | 项目名称 | `F项目` |
| `--chip-capacity` | `-c` | 芯片容量 | `96` |
| `--start-date` | `-d` | 开始日期（YYYY-MM-DD格式） | 今天 |

## 输入文件格式

### 输入表（Input table.xlsx）

输入表应包含以下列：
- A列：参数名/样本名
- B列：Value1
- C列：Value2（通常为空；病原体行用于 rpm 范围，例如 `1~10`）
- D列：Value3（通常为空；病原体行用于 spike-rpm 范围，例如 `7000~10000`）

示例：
- 配置项行：`研究编号 / 实验启动时间 / 接头起点 / 测序仪SN / RUN ...` 等通常只填 Value1
- 病原体行（样本行）：A列为样本名（如 `F-0020-01`），Value1 为病原体名称，Value2 为预期检出 rpm 范围，Value3 为 spike-rpm 范围

#### 单个样本关注多个病原体（支持）

同一个样本可以在 **Value1/Value2/Value3** 中用英文分号 `;` 分隔多个值，并按顺序配对：

- **Value1**：`病原体1;病原体2;病原体3`
- **Value2**：`rpm范围1;rpm范围2;rpm范围3`
- **Value3**：`spike-rpm范围1;spike-rpm范围2;spike-rpm范围3`

示例：

- 样本名：`F-0020-01`
- Value1：`肺炎支原体;人疱疹病毒5型(CMV);铜绿假单胞菌`
- Value2：`1~10;1~10;10~100`
- Value3：`7000~10000;7000~10000;7000~10000`

工具会把该样本在文库表中拆成多条记录（每个病原体一行），**但同一个样本只对应一个文库编号、只占用一个接头（index 不递增）**；每条记录的 `rpm/内部对照spike.1RPM值` 按对应范围随机生成。

### 规则文件（规则.xlsx）

规则文件定义了排布的规则和约束条件。

### 对照文件

- **NC.xlsx**：阴性对照信息
- **PC.xlsx**：阳性对照信息

### 参考文件

- **物种列表.xlsx**：物种相关信息
- **测序仪对应关系.xlsx**：测序仪型号和SN对应关系

## 输出文件

工具会在输出目录中生成以下文件：

1. **排布结果_YYYYMMDD_HHMMSS.xlsx**：包含文库表和芯片表的合并文件
2. **文库表_YYYYMMDD_HHMMSS.xlsx**：单独的文库表
3. **芯片表_YYYYMMDD_HHMMSS.xlsx**：单独的芯片表

### 文库表格式

| 芯片 | 芯片数据量 | 上机时间 | 上机时间.1 | 样本名称 | 文库编号 | index | 物种名称 |
|------|-----------|---------|-----------|---------|---------|-------|---------|

### 芯片表格式

| 实验项目 | 测序日期 | 测序仪SN | Run数 | 芯片SN | 测序仪型号 | 试验结果 | 备注2 |
|---------|---------|---------|-------|--------|-----------|---------|-------|

## 项目结构

```
NGS-Planner/
├── main.py                 # 命令行主程序入口
├── app.py                  # Web应用主程序
├── run_web.sh             # Web服务器启动脚本
├── 启动服务器.command      # macOS一键启动脚本
├── requirements.txt        # 依赖包列表
├── README.md              # 本文件
├── src/                   # 源代码目录
│   ├── __init__.py
│   ├── parser.py          # 输入文件解析模块
│   ├── planner.py         # 排布算法核心模块
│   └── generator.py       # 输出文件生成模块
├── templates/             # HTML模板目录
│   ├── base.html         # 基础模板
│   └── index.html        # 主页模板
├── attachments/           # 输入文件目录
│   ├── Input table.xlsx
│   ├── 规则.xlsx
│   ├── NC.xlsx
│   ├── PC.xlsx
│   ├── 物种列表.xlsx
│   ├── 测序仪对应关系.xlsx
│   ├── 文库表模版.xlsx
│   └── 芯片表模版.xlsx
├── schemas/              # JSON Schema定义
│   ├── input.schema.json
│   ├── library.schema.json
│   └── chip.schema.json
└── output/               # 输出目录（自动创建）
```

## 开发说明

### 模块说明

- **parser.py**：负责解析各种输入文件（输入表、规则、对照、参考文件）
- **planner.py**：实现排布算法，包括文库规划和芯片规划
- **generator.py**：生成符合格式要求的输出Excel文件

### 扩展开发

如需添加新的排布规则或功能，可以：

1. 在 `planner.py` 中扩展 `LibraryPlanner` 或 `ChipPlanner` 类
2. 在 `parser.py` 中添加新的解析器
3. 在 `generator.py` 中添加新的输出格式

## 许可证

本项目仅供内部使用。

## 更新日志

### v1.0.0 (2026-01-16)
- 初始版本
- 支持基本的文库和芯片排布功能
- 支持模板文件格式输出
- 添加Web前端界面
- 添加一键启动脚本
