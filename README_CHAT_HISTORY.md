# Claude Code 对话历史查看工具

这个工具可以帮助你查看所有与 Claude 的对话记录，即使对话记录分散在多个文件中。

## 快速开始

### 基础使用

```bash
# 查看所有对话记录（包含工具调用和输出）
python3 view_chat_history.py

# 只查看最近的10条消息（推荐加上去重）
python3 view_chat_history.py --limit 10 --deduplicate

# 不显示思考过程，只显示对话内容
python3 view_chat_history.py --no-thinking

# 不显示工具调用和输出（只看文字对话）
python3 view_chat_history.py --no-tools

# 截断长输出（方便快速浏览，默认显示完整内容）
python3 view_chat_history.py --truncate

# 最简洁模式：只看对话文字，去重，截断长输出
python3 view_chat_history.py --no-thinking --no-tools --deduplicate --truncate
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

| 参数 | 说明 | 示例 |
|------|------|------|
| `--limit N` | 只显示最近的N条消息 | `--limit 20` |
| `--session ID` | 只显示特定会话的消息 | `--session 91f9be77` |
| `--no-thinking` | 不显示思考内容 | `--no-thinking` |
| `--no-tools` | 不显示工具调用和输出 | `--no-tools` |
| `--truncate` | 截断长输出（默认显示完整内容）| `--truncate` |
| `--deduplicate` | 去除重复消息（session交叉时有用）| `--deduplicate` |
| `--no-color` | 禁用颜色输出（默认自动检测）| `--no-color` |
| `--export FILE` | 导出到文本文件 | `--export history.txt` |
| `--include-agents` | 包含代理文件 | `--include-agents` |

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

## 未来可能添加的功能

- [ ] 按日期范围过滤
- [ ] 搜索功能（在脚本内搜索关键词）
- [ ] HTML格式导出
- [ ] 统计信息（消息数量、会话数量等）
- [ ] 交互式浏览模式
