# AutoTerminal - 智能终端工具

AutoTerminal 是一个基于大语言模型的智能终端工具，可以将自然语言转换为终端命令，提高工作效率。

## 功能特点

- 🧠 基于LLM的智能命令生成
- 🔐 安全的命令执行机制（需要用户确认）
- ⚙️ 灵活的配置管理
- 🌍 中文支持
- 🔄 支持多种LLM模型
- 📚 命令历史记录和上下文感知
- 📁 当前目录内容上下文感知

## 安装

### 方法1：使用uv（开发模式）
确保已安装 `uv` 工具，然后运行：

```bash
uv sync
```

### 方法2：使用pip安装到用户目录（推荐给最终用户）
```bash
pip install --user .
```

安装后可以直接使用 `at` 命令：

```bash
at "查看当前目录"
```

### 卸载
```bash
pip uninstall autoterminal
```

### 全局安装（需要管理员权限）
```bash
sudo pip install .
```

## 配置

首次运行时，先选择服务商，再输入 API Key（隐藏输入）：

1. DeepSeek
2. 智谱（中国）
3. Kimi（月之暗面）
4. Qwen（百炼，北京地域）
5. 其他 OpenAI 兼容服务（手动填写 Base URL）

前四家自动填写接口地址，随后获取账号的模型列表。可以输入列表序号，也可以直接输入模型 ID。模型列表接口超时、不支持或返回空时，仍可手动输入；列表查询不等于模型调用权限验证。

配置保存在 `~/.autoterminal/config.json`。已有配置继续兼容；重新选择服务商请运行：

```bash
at --configure
# 或直接指定服务商
at --configure --provider deepseek
```

支持 `--provider deepseek|zhipu|kimi|qwen`；命令行 `--api-key`、`--base-url`、`--model` 优先于配置文件。完整配置的临时覆盖不写回文件；首次补齐配置或 `--configure` 时会保存。

### 配置选项与上下文

- `max_history`：保存及默认使用的历史数量（默认 10）。
- `--history-count N`：本次使用的历史数量，0 禁用 AutoTerminal 和 Shell 历史上下文，不清空已有记录。
- 上下文包含工作目录、操作系统、Shell、目录项（含隐藏文件）、历史命令及退出码。
- 目录采集最多 200 项；Shell 历史最多读取末尾 256 KiB；发送历史最多各 100 条，并分别限制文本长度。
- Shell 历史只能读取已写入历史文件的命令。Bash 当前会话如需立即同步，可先运行 `history -a`；子进程无法直接读取父 Shell 尚未保存的历史。
- 命令在子 Shell 中执行，`cd` / `export` 不会改变父终端状态。

服务商地址依据官方文档：[DeepSeek](https://api-docs.deepseek.com/)、[智谱](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)、[Kimi](https://platform.moonshot.cn/docs)、[百炼](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)。百炼预设使用仍兼容的北京公共域名；其他地域或专属域名可通过 `--base-url` 覆盖。

## 使用方法

### 方法1：使用uv run
```bash
uv run python -m autoterminal.main "查看当前目录下的所有文件"
```

### 方法2：安装后使用at命令
```bash
uv pip install -e .
at "查看当前目录下的所有文件"
```

### 使用历史命令上下文
```bash
at --history-count 5 "基于前面的命令，删除所有.txt文件"
```

程序会显示生成命令，仅按回车确认后执行，输入其他内容或 Ctrl+C 取消。截断响应不会执行，执行退出码会返回给调用者。

## 示例

```
$ at "列出当前目录下的所有文件"
$ ls -a
Press Enter to execute...
.  ..  autoterminal  config.json  .git  .gitignore  pyproject.toml  .python-version  README.md  uv.lock
```

## 支持的LLM

- 内置 DeepSeek、智谱（中国）、Kimi、Qwen（百炼）
- 自定义 OpenAI 兼容接口

## 项目结构

```
autoterminal/
├── __init__.py             # 包初始化文件
├── main.py                 # 主程序入口
├── config/                 # 配置管理模块
│   ├── __init__.py         # 包初始化文件
│   ├── loader.py           # 配置加载器
│   └── manager.py          # 配置管理器
├── llm/                    # LLM相关模块
│   ├── __init__.py         # 包初始化文件
│   └── client.py           # LLM客户端
├── history/                # 历史命令管理模块
│   ├── __init__.py         # 包初始化文件
│   └── history.py          # 历史命令管理器
├── utils/                  # 工具函数
│   ├── __init__.py         # 包初始化文件
│   └── helpers.py          # 辅助函数
├── pyproject.toml          # 项目配置
├── config.json             # 用户配置文件
├── .gitignore
└── README.md

## 开发验证

```bash
AUTOTERMINAL_FILE_LOG=false uv run python -m unittest discover -s tests -v
```

测试使用模拟 API，不消耗真实账号额度。

## 让无参数 at 纠正上一条失败命令

独立进程无法直接读取父终端的内存历史及 `$?`。在当前终端启用接入：

```bash
# Bash
 eval "$(at --shell-init bash)"
# Zsh（二选一）
 eval "$(at --shell-init zsh)"
```

长期使用可将对应的 `eval` 行放到 `~/.bashrc` 或 `~/.zshrc`，放在 PATH 配置之后。
接入仅对直接运行 `at` 生效；`uv run at` 不会经过这个 Shell 函数。
它会传递上一条命令和退出码，不捕获终端 stderr。模型在无参数模式下优先纠正失败命令。
未启用接入时，无参数 `at` 会使用最近有效的 Shell 历史，跳过 `at` 自身调用。
例如历史中出现 `atp list --upgradable` 时，会让模型优先纠正为 `apt list --upgradable`，保留参数。
磁盘历史的退出码未知，但不妨碍纠正明显拼写错误；Shell 接入是增强功能，不是使用前提。

```bash
apt insall
at --show-context  # shell_session 应包含 apt insall 及非零 returncode；不调用 API
# 实际纠错时，重新运行错误命令后紧接着运行 at
apt insall
at
```

`--history-count 0` 同时禁用当前 Shell 会话上下文。修改源码后，全局安装需运行
`uv tool install --force .` 更新，然后在终端执行上面的 `eval`。

## 发布到 PyPI（维护者）

当前 GitHub Actions 仅同步到 Gitea，不会自动发布到 PyPI。
发布前更新 `pyproject.toml`、`uv.lock` 中的项目版本以及 `CHANGELOG.md`。
以下以 1.1.1 为例；后续版本需同步替换命令中的版本号。

```bash
AUTOTERMINAL_FILE_LOG=false uv run --frozen python -m unittest discover -s tests -v
uv build --out-dir dist/1.1.1
uv run --frozen twine check dist/1.1.1/*
uv run --frozen twine upload --username __token__ dist/1.1.1/*
```

上传时密码填写 PyPI API Token（以 `pypi-` 开头），不是登录密码。
已配置 `.pypirc`、环境变量或 keyring 时，Twine 可复用对应凭据。
Token 可在 [PyPI 账号设置](https://pypi.org/manage/account/#api-tokens) 中创建，选择 `autoterminal` 项目权限。
不要将 Token 写进仓库。PyPI 已上传的文件不能覆盖；后续发布需要新版本号。

Git 提交与 PyPI 上传是独立步骤；上传成功后可以用 `uv tool install --force autoterminal==1.1.1` 安装。
参考：[Python 官方打包教程](https://packaging.python.org/en/latest/tutorials/packaging-projects/)。

### 升级时的默认提示词迁移

升级后首次读取配置时，程序会补齐缺失的提示词，并把已知旧版默认提示词更新为当前版本，原子保存至 `~/.autoterminal/config.json`。用户自定义提示词、API Key、模型和服务地址保留。`prompt_version` 和 `prompt_defaults` 记录默认版本与快照，用于后续升级识别；不必删除配置或重新运行向导。配置不可写时，本次运行仍使用更新后的默认值。
