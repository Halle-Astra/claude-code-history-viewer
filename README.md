# CLI 工具对话历史查看工具

这个工具可以帮助你查看与 AI 助手的对话记录，支持 **Claude Code** 和 **kernelcat** 两种 CLI 工具。

## 支持的 CLI 工具

### Claude Code
- 官方 Anthropic Claude 命令行工具
- 扁平文件结构：所有 `.jsonl` 文件在同一目录
- 支持按会话过滤、去重等功能

### kernelcat
- 第三方 AI CLI 工具
- 按日期组织：`YYYY/MM/DD/` 目录结构
- **支持按项目过滤**：每个会话关联一个工作目录
- **项目统计**：可按项目分组查看统计信息

## 快速开始

### Claude Code 基础使用

```bash
# 查看当前目录的对话记录（默认自动去重）
python3 view_chat_history.py

# 查看指定目录的对话记录
python3 view_chat_history.py /path/to/chat/history

# 只查看最近的10条消息
python3 view_chat_history.py --limit 10

# 不显示思考过程，只显示对话内容
python3 view_chat_history.py --no-thinking

# 不显示工具调用和输出（只看文字对话）
python3 view_chat_history.py --no-tools

# 截断长输出（方便快速浏览，默认显示完整内容）
python3 view_chat_history.py --truncate

# 最简洁模式：只看对话文字，截断长输出
python3 view_chat_history.py --no-thinking --no-tools --truncate

# 不去重（默认会自动去重）
python3 view_chat_history.py --no-deduplicate
```

### kernelcat 基础使用

```bash
# 列出所有项目
python3 view_chat_history.py /path/to/kernelcat/sessions --cli-name kcat --list-projects

# 查看所有对话
python3 view_chat_history.py /path/to/kernelcat/sessions --cli-name kcat

# 按项目过滤（支持部分匹配）
python3 view_chat_history.py /path/to/kernelcat/sessions --cli-name kcat --project jax-dna

# 查看项目的最近10条消息
python3 view_chat_history.py /path/to/kernelcat/sessions --cli-name kcat --project sparsegp --limit 10 --no-thinking
```

### 查看统计信息

```bash
# Claude Code 统计
python3 chat_stats.py

# kernelcat 统计
python3 chat_stats.py /path/to/kernelcat/sessions --cli-name kcat

# kernelcat 列出所有项目
python3 chat_stats.py /path/to/kernelcat/sessions --cli-name kcat --list-projects

# kernelcat 按项目分组统计
python3 chat_stats.py /path/to/kernelcat/sessions --cli-name kcat --group-by-project

# kernelcat 统计特定项目
python3 chat_stats.py /path/to/kernelcat/sessions --cli-name kcat --project prof_skills
```

### 导出对话记录

```bash
# 导出所有对话到文本文件
python3 view_chat_history.py --export my_chat_history.txt

# 导出最近50条消息
python3 view_chat_history.py --limit 50 --export recent_chats.txt

# 导出时不包含思考过程
python3 view_chat_history.py --no-thinking --export clean_history.txt
```

### 查看特定会话

```bash
# 查看特定会话的对话（使用部分会话ID）
python3 view_chat_history.py --session 91f9be77
```

### 包含代理对话

默认情况下，脚本会跳过 `agent-*` 开头的文件（这些是子代理的对话）。如果你想包含它们：

```bash
python3 view_chat_history.py --include-agents
```

## 参数说明

### 通用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `path` | 包含历史记录的目录（位置参数）| `/path/to/chat/history` |
| `--cli-name` | CLI 工具类型：claude-code（默认）或 kcat | `--cli-name kcat` |
| `--limit N` | 只显示最近的N条消息 | `--limit 20` |
| `--session ID` | 只显示特定会话的消息 | `--session 91f9be77` |
| `--no-thinking` | 不显示思考内容 | `--no-thinking` |
| `--no-tools` | 不显示工具调用和输出 | `--no-tools` |
| `--truncate` | 截断长输出（默认显示完整内容）| `--truncate` |
| `--no-deduplicate` | 不去除重复消息（默认会自动去重）| `--no-deduplicate` |
| `--no-color` | 禁用颜色输出（默认自动检测）| `--no-color` |
| `--export FILE` | 导出到文本文件 | `--export history.txt` |

### Claude Code 专属参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--include-agents` | 包含代理文件（默认不包含）| `--include-agents` |

### kernelcat 专属参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--list-projects` | 列出所有项目及会话数 | `--list-projects` |
| `--project PATH` | 按项目路径过滤（支持部分匹配）| `--project jax-dna` |
| `--group-by-project` | 按项目分组统计（仅 chat_stats.py）| `--group-by-project` |

## 颜色说明（v3.0新增）

脚本会自动检测终端颜色支持，为不同内容添加颜色，轻重分明：

| 内容类型 | 颜色 | 说明 |
|---------|------|------|
| 👤 用户消息 | **红色**（醒目）| 你说的话，最容易识别 |
| 🤖 助手消息 | **蓝色** | Claude的回答 |
| 💭 思考过程 | 暗淡灰色 | 不重要的内容，视觉权重低 |
| 🔧 工具调用 | **黄色** | 工具操作醒目 |
| ✅ 工具输出 | 青色 | 工具结果清晰 |
| ⏰ 元信息 | 灰色 | 时间戳、会话ID等 |

**自动检测**：
- 终端支持颜色时自动启用
- 输出被重定向时自动禁用（如管道、重定向到文件）
- 导出文件时自动禁用（纯文本，无ANSI代码）
- 可用 `--no-color` 手动禁用

## 常用场景

### 1. 快速浏览最近的对话（推荐）

```bash
# 去重 + 不显示思考 + 只看最近50条
python3 view_chat_history.py --limit 50 --no-thinking --deduplicate
```

### 2. 处理重复消息问题

如果发现不同session有交叉内容（这是Claude Code的正常现象），使用 `--deduplicate` 去重：

```bash
# 去重后查看所有对话
python3 view_chat_history.py --deduplicate

# 去重后导出
python3 view_chat_history.py --deduplicate --export clean_history.txt
```

**去重说明**：
- 使用消息的UUID进行去重（如果有的话）
- 如果没有UUID，使用时间戳+内容前100字符作为唯一标识
- 去重后会显示移除了多少条重复消息

### 3. 控制输出长度

默认显示完整内容（包括很长的工具输出），如果想快速浏览，使用 `--truncate`：

```bash
# 截断长输出，方便快速浏览
python3 view_chat_history.py --truncate --no-thinking

# 截断规则：
# - 思考过程：最多20行，每行最多118字符
# - 工具输出：最多30行，每行最多120字符
# - 默认不截断，显示完整内容
```

### 4. 导出完整的对话历史用于备份

```bash
python3 view_chat_history.py --export full_backup_$(date +%Y%m%d).txt
```

### 3. 查找特定会话的内容

先查看会话列表：
```bash
ls -lh *.jsonl | grep -v agent
```

然后查看特定会话：
```bash
python3 view_chat_history.py --session 会话ID前几位
```

### 4. 搜索特定关键词的对话

```bash
python3 view_chat_history.py --export temp.txt
grep -i "关键词" temp.txt
```

## 文件说明

- `*.jsonl` 文件：主要的对话会话文件（以UUID命名）
- `agent-*.jsonl` 文件：子代理的对话记录
- 每个文件包含一个会话的所有消息，按时间顺序记录

## 注意事项

1. 脚本会自动按时间顺序排序所有消息，即使它们来自不同的文件
2. 默认不包含 agent 文件，因为这些通常是内部子任务
3. 思考过程（thinking）包含了 Claude 的内部推理过程，可以通过 `--no-thinking` 隐藏
4. 导出的文件是纯文本格式，方便搜索和备份

## kernelcat 数据结构详解

### 目录组织

kernelcat 使用按日期组织的目录结构：

```
kernelcat-files/
├── history.jsonl          # 用户输入索引文件
├── config.toml           # 配置文件
└── sessions/             # 会话详细记录
    └── YYYY/             # 年份
        └── MM/           # 月份
            └── DD/       # 日期
                ├── rollout-{timestamp}-{session_id}.jsonl
                ├── rollout-{timestamp}-{session_id}.jsonl
                └── ...
```

### 文件关系说明

#### 1. history.jsonl（索引文件）
- **作用**：记录每次用户输入的索引
- **格式**：每行一个 JSON 对象
- **字段**：
  ```json
  {
    "session_id": "019b4a12-371e-7913-b52c-9c8d296dcec7",
    "ts": 1703318266,
    "text": "用户输入的问题..."
  }
  ```
- **特点**：
  - 只记录用户输入，不包含助手回复
  - 不包含项目信息
  - 所有 `session_id` 都对应 sessions 文件夹中的完整记录

#### 2. sessions/{YYYY}/{MM}/{DD}/rollout-{timestamp}-{session_id}.jsonl
- **作用**：完整的对话记录文件
- **文件名格式**：`rollout-2025-12-23T15-17-46-019b4a12-371e-7913-b52c-9c8d296dcec7.jsonl`
  - 前半部分：时间戳（`2025-12-23T15-17-46`）
  - 后半部分：session_id（`019b4a12-371e-7913-b52c-9c8d296dcec7`）

- **文件结构**：
  ```
  第一行：session_meta（会话元信息）
  后续行：response_item（用户和助手的消息）
  ```

- **session_meta 示例**：
  ```json
  {
    "timestamp": "2025-12-23T07:17:46.401Z",
    "type": "session_meta",
    "payload": {
      "id": "019b4a12-371e-7913-b52c-9c8d296dcec7",
      "cwd": "/root/hzy/prof_skills_test",  # 项目工作目录
      "originator": "kernelcat_cli_rs",
      "cli_version": "0.5.0",
      "model_provider": "autokernel"
    }
  }
  ```

- **response_item 示例**：
  ```json
  {
    "timestamp": "2025-12-23T07:17:46.533Z",
    "type": "response_item",
    "payload": {
      "type": "message",
      "role": "user",  # 或 "assistant"
      "content": [
        {
          "type": "input_text",  # 用户消息
          "text": "帮我分析一下性能..."
        }
      ]
    }
  }
  ```

### session_id 与文件的对应关系

每个 session_id 在两个地方出现：

1. **history.jsonl**：记录用户输入时的 session_id
2. **sessions 文件**：完整对话的文件名包含相同的 session_id

**验证结果**：
- history.jsonl 中有 38 个 session_id
- sessions 文件夹中有 72 个文件
- **100% 匹配**：history.jsonl 中的所有 session_id 都能在 sessions 中找到对应文件
- 额外的 34 个文件：可能是未记录到 history.jsonl 的会话

### 项目（工程目录）组织

每个 session 文件的第一行 `session_meta` 包含 `cwd` 字段，记录了当前工作目录：

**示例统计**（共 12 个项目，72 个会话）：

```
📁 /root/hzy/prof_skills_test
   会话数: 17

📁 /root/lzh/workspace
   会话数: 16

📁 /root/hzy/kernelx_test/kernelcat
   会话数: 12

📁 /root/wjd/jax-dna-kernelcat
   会话数: 2
```

**使用方式**：
```bash
# 列出所有项目
python3 view_chat_history.py /path/to/sessions --cli-name kcat --list-projects

# 查看特定项目的对话
python3 view_chat_history.py /path/to/sessions --cli-name kcat --project jax-dna

# 按项目分组统计
python3 chat_stats.py /path/to/sessions --cli-name kcat --group-by-project
```

### kernelcat vs Claude Code 对比

| 特性 | kernelcat | Claude Code |
|------|-----------|-------------|
| 目录结构 | 按日期：YYYY/MM/DD | 扁平结构 |
| 文件命名 | rollout-{timestamp}-{session_id} | {session_id}.jsonl |
| 索引文件 | history.jsonl（用户输入索引）| 无 |
| 项目信息 | 每个会话记录 cwd | 无（按目录区分）|
| 消息格式 | response_item + payload | 直接 user/assistant |
| 会话元信息 | session_meta（第一行）| 无专门元信息 |
| 工具调用 | 未明确区分 | 明确的 tool_use/tool_result |

## 未来可能添加的功能

- [ ] 按日期范围过滤
- [ ] 搜索功能（在脚本内搜索关键词）
- [ ] HTML格式导出
- [x] ~~统计信息（消息数量、会话数量等）~~ ✅ 已实现
- [ ] 交互式浏览模式
- [x] ~~支持多种 CLI 工具~~ ✅ 已支持 Claude Code 和 kernelcat
