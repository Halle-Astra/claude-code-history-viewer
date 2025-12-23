#!/usr/bin/env python3
"""
测试颜色输出的演示脚本
"""

# ANSI颜色代码
class Colors:
    RESET = '\033[0m'
    USER = '\033[1;31m'      # 粗体红色
    ASSISTANT = '\033[1;34m'  # 粗体蓝色
    THINKING = '\033[2;37m'   # 暗淡灰色
    TOOL_CALL = '\033[1;33m'  # 粗体黄色
    TOOL_OUTPUT = '\033[96m'  # 青色
    TIMESTAMP = '\033[90m'    # 灰色
    SEPARATOR = '\033[2;90m'  # 暗淡灰色
    INFO = '\033[90m'         # 灰色
    HIGHLIGHT = '\033[1;32m'  # 粗体绿色


print("=" * 80)
print(f"{Colors.HIGHLIGHT}对话历史颜色演示{Colors.RESET}")
print("=" * 80)
print()

print(f"{Colors.SEPARATOR}{'─' * 80}{Colors.RESET}")
print(f"[1] {Colors.USER}👤 用户{Colors.RESET} - {Colors.TIMESTAMP}2025-12-11 18:30:00{Colors.RESET}")
print(f"{Colors.INFO}会话: abc123... | 文件: test.jsonl{Colors.RESET}")
print(f"{Colors.SEPARATOR}{'─' * 80}{Colors.RESET}")
print("这是用户说的话，应该是醒目的红色")
print()

print(f"{Colors.SEPARATOR}{'─' * 80}{Colors.RESET}")
print(f"[2] {Colors.ASSISTANT}🤖 助手{Colors.RESET} - {Colors.TIMESTAMP}2025-12-11 18:30:05{Colors.RESET}")
print(f"{Colors.INFO}会话: abc123... | 文件: test.jsonl{Colors.RESET}")
print(f"{Colors.SEPARATOR}{'─' * 80}{Colors.RESET}")
print("这是助手的回答，应该是蓝色")
print()

print(f"{Colors.THINKING}╔══ 💭 思考过程 ══╗{Colors.RESET}")
print(f"{Colors.THINKING}║ 这是思考过程的内容{Colors.RESET}")
print(f"{Colors.THINKING}║ 应该是暗淡的灰色（不重要）{Colors.RESET}")
print(f"{Colors.THINKING}╚{'═' * 120}╝{Colors.RESET}")
print()

print(f"┌─ {Colors.TOOL_CALL}🔧 工具调用: Bash [toolu_123]{Colors.RESET}")
print("│  命令: ls -lah")
print("│  说明: List files")
print("└─")
print()

print(f"┌─ {Colors.TOOL_OUTPUT}✅ 工具输出 [toolu_123]{Colors.RESET}")
print("│  total 18M")
print("│  drwx------ 2 root root 4.0K")
print("│  -rw------- 1 root root 12K file.py")
print("└─")
print()

print("=" * 80)
print("如果看到颜色，说明终端支持ANSI颜色代码")
print("如果没有颜色，只看到普通文本，可能需要使用支持颜色的终端")
print("=" * 80)
