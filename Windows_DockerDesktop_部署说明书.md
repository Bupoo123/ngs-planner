# Windows（Docker Desktop）部署说明书（给同事用）

> 适用：Windows 10/11  
> 目标：不安装 Python、不配环境，直接用 Docker 运行本工具，在浏览器里使用。

---

## 你需要准备的东西

- 一台 Windows 电脑（建议 Windows 10/11）
- 能打开浏览器
- 能安装软件（Docker Desktop）
- 项目地址（Gitee）：`https://gitee.com/bupoo/ngs-planner`

---

## 第 1 步：安装 Docker Desktop（只做一次）

1. 在 Windows 上安装 **Docker Desktop**
2. 安装完成后打开 Docker Desktop
3. 等待 Docker Desktop 进入运行状态  
   - 一般界面会显示 **Running**（正在运行）

### 如果 Docker Desktop 提示需要 WSL2（常见）

按提示点击“安装/启用 WSL2”，可能需要重启电脑一次。重启后再打开 Docker Desktop，确保它是 Running。

---

## 第 2 步：下载项目代码（两种方式，任选一种）

### 方式 A：用 git 克隆（推荐）

1. 打开 **PowerShell**（开始菜单搜索 PowerShell）
2. 进入桌面并克隆项目：

```powershell
cd $env:USERPROFILE\Desktop
git clone https://gitee.com/bupoo/ngs-planner.git
cd ngs-planner
```

> 如果提示 `git` 不是命令，说明电脑没装 Git，请用下面“方式 B”。

### 方式 B：下载 ZIP（最简单）

1. 打开 Gitee 项目页面：`https://gitee.com/bupoo/ngs-planner`
2. 点击“下载 ZIP”
3. 解压到桌面（得到文件夹 `ngs-planner`）
4. 打开 PowerShell，进入项目目录：

```powershell
cd $env:USERPROFILE\Desktop\ngs-planner
```

---

## 第 3 步：一键启动服务

确保 Docker Desktop 正在 Running，然后在项目目录执行：

```powershell
docker compose up --build
```

第一次启动会下载依赖，可能需要几分钟。  
看到日志里出现类似 “Running on …5123” 说明启动成功。

---

## 第 4 步：在浏览器里使用

打开浏览器访问：

- `http://localhost:5123`

使用流程（按页面提示）：

- 上传输入表（例如项目里的 `attachments/Input table.xlsx`）
- 第一步：编辑芯片表 → 确认
- 第二步：预览/编辑文库表 → 确认生成文件
- 下载结果文件

---

## 第 5 步：输出文件在哪里

生成的结果会出现在你电脑的项目目录：

- `ngs-planner\\output\\`

（Docker 已经把容器内的输出目录映射到本机 `./output`）

---

## 第 6 步：停止服务

在运行日志的 PowerShell 窗口：

1. 按 **Ctrl + C**
2. 再执行：

```powershell
docker compose down
```

---

## 常见问题（按下面做就能解决）

### 1）打不开 `http://localhost:5123`

可能原因：端口被占用，或 Docker 没启动。

先检查 Docker Desktop 是否 Running。  
如果仍打不开，可把端口改成 5124：

1. 用记事本打开项目根目录的 `docker-compose.yml`
2. 找到：

```yaml
ports:
  - "5123:5123"
```

改成：

```yaml
ports:
  - "5124:5123"
```

3. 重新运行：

```powershell
docker compose up --build
```

4. 打开：`http://localhost:5124`

### 2）`docker compose up --build` 报错

把报错内容截图发回给我（或发给项目负责人），一般 1–2 条信息就能定位问题。

### 3）公司网络慢，第一次构建很久

第一次构建会下载依赖。建议在网络好的时候先跑一次；也可以请 IT 配置 Docker 镜像加速（Docker Desktop 设置里）。

---

## 你只需要记住的最简命令

启动：

```powershell
docker compose up --build
```

停止：

```powershell
docker compose down
```

