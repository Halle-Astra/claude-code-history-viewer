#!/usr/bin/env python3
"""
查看 CLI 工具对话历史记录的脚本（支持 Claude Code 和 kernelcat）

使用方法:
    python view_chat_history.py [路径] [--cli-name CLI工具]

参数:
    路径: 包含jsonl文件的目录（可选，默认为当前目录）

可选参数:
    --cli-name: CLI工具名称，claude-code（默认）或 kcat（kernelcat）
    --limit N: 只显示最近的N条消息
    --session ID: 只显示特定会话ID的消息
    --no-thinking: 不显示思考内容
    --no-tools: 不显示工具调用和输出
    --truncate: 截断长输出（默认显示完整内容）
    --no-deduplicate: 不去除重复消息（默认会自动去重）
    --no-color: 禁用颜色输出（默认自动检测）
    --export FILE: 导出到文本文件
    --include-agents: 包含代理文件（仅用于claude-code）

示例:
    # Claude Code
    python view_chat_history.py
    python view_chat_history.py /path/to/chat/history
    python view_chat_history.py ~/claude-sessions --no-thinking

    # kernelcat
    python view_chat_history.py /path/to/kernelcat/sessions --cli-name kcat
    python view_chat_history.py . --cli-name kcat --no-deduplicate

颜色说明:
    用户消息: 红色（醒目）
    助手消息: 蓝色
    思考过程: 暗淡灰色（不重要）
    工具调用: 黄色
    工具输出: 青色
    元信息: 灰色
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import argparse


# ANSI颜色代码
class Colors:
    """终端颜色定义"""
    # 基础颜色
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # 角色颜色（醒目）
    USER = '\033[1;31m'      # 粗体红色 - 用户消息
    ASSISTANT = '\033[1;34m'  # 粗体蓝色 - 助手消息

    # 内容类型颜色
    THINKING = '\033[2;37m'   # 暗淡灰色 - 思考过程（不重要）
    TOOL_CALL = '\033[1;33m'  # 粗体黄色 - 工具调用
    TOOL_OUTPUT = '\033[96m'  # 青色 - 工具输出

    # 元信息颜色
    TIMESTAMP = '\033[90m'    # 灰色 - 时间戳
    SEPARATOR = '\033[2;90m'  # 暗淡灰色 - 分隔线
    INFO = '\033[90m'         # 灰色 - 一般信息

    # 高亮颜色
    HIGHLIGHT = '\033[1;32m'  # 粗体绿色 - 重要信息


def supports_color() -> bool:
    """检测终端是否支持颜色"""
    # 如果输出被重定向（管道），不使用颜色
    if not sys.stdout.isatty():
        return False

    # 检查环境变量
    if os.getenv('NO_COLOR'):
        return False

    # Windows 需要特殊处理，但大多数现代终端都支持
    return True


def colorize(text: str, color: str, use_color: bool = True) -> str:
    """为文本添加颜色

    Args:
        text: 要着色的文本
        color: 颜色代码
        use_color: 是否使用颜色
    """
    if not use_color:
        return text
    return f"{color}{text}{Colors.RESET}"


def parse_claude_code_message(data: Dict, file_name: str) -> Dict[str, Any]:
    """解析 Claude Code 格式的消息"""
    return {
        'type': data['type'],
        'timestamp': data.get('timestamp', ''),
        'session_id': data.get('sessionId', ''),
        'message': data.get('message', {}),
        'uuid': data.get('uuid', ''),
        'file': file_name
    }


def parse_kernelcat_message(data: Dict, file_name: str, session_id: str) -> Dict[str, Any]:
    """解析 kernelcat 格式的消息"""
    payload = data.get('payload', {})
    role = payload.get('role', '')

    # 转换为统一格式
    message_content = []
    for item in payload.get('content', []):
        item_type = item.get('type', '')
        # 将 input_text/output_text 统一转换为 text
        if item_type in ['input_text', 'output_text']:
            message_content.append({
                'type': 'text',
                'text': item.get('text', '')
            })
        else:
            # 保留其他类型
            message_content.append(item)

    return {
        'type': role,  # 'user' 或 'assistant'
        'timestamp': data.get('timestamp', ''),
        'session_id': session_id,
        'message': {'content': message_content},
        'uuid': '',  # kernelcat 没有 uuid，使用timestamp去重
        'file': file_name
    }


def load_messages_from_file(file_path: Path, cli_name: str = 'claude-code') -> List[Dict[str, Any]]:
    """从单个JSONL文件中加载所有消息

    Args:
        file_path: JSONL文件路径
        cli_name: CLI工具名称 ('claude-code' 或 'kcat')
    """
    messages = []

    # 从文件名提取 session_id (用于 kernelcat)
    session_id = file_path.stem.split('-')[-1] if cli_name == 'kcat' else ''

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)

                    if cli_name == 'claude-code':
                        # Claude Code 格式: type 在顶层
                        if data.get('type') in ['user', 'assistant']:
                            msg = parse_claude_code_message(data, file_path.name)
                            messages.append(msg)

                    elif cli_name == 'kcat':
                        # kernelcat 格式: type=response_item，role在payload中
                        if data.get('type') == 'response_item':
                            payload = data.get('payload', {})
                            if payload.get('role') in ['user', 'assistant']:
                                msg = parse_kernelcat_message(data, file_path.name, session_id)
                                messages.append(msg)

                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"警告: 读取文件 {file_path.name} 时出错: {e}")

    return messages


def deduplicate_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去除重复的消息

    重复判断依据：
    1. 首先使用UUID（如果有的话）
    2. 如果没有UUID，使用时间戳+消息内容的前100个字符
    """
    seen = set()
    unique_messages = []

    for msg in messages:
        # 生成消息的唯一标识
        uuid = msg.get('uuid', '')

        if uuid:
            # 使用UUID作为唯一标识
            identifier = uuid
        else:
            # 使用时间戳+内容前100字符作为标识
            timestamp = msg.get('timestamp', '')
            content = str(msg.get('message', {}))[:100]
            identifier = f"{timestamp}_{content}"

        if identifier not in seen:
            seen.add(identifier)
            unique_messages.append(msg)

    return unique_messages


def get_session_project(file_path: Path) -> str:
    """从 kernelcat session 文件中提取项目路径

    Args:
        file_path: session 文件路径

    Returns:
        项目路径，如果无法获取则返回空字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if first_line.strip():
                data = json.loads(first_line)
                if data.get('type') == 'session_meta':
                    payload = data.get('payload', {})
                    return payload.get('cwd', '')
    except:
        pass
    return ''


def list_kernelcat_projects(directory: Path) -> Dict[str, List[Path]]:
    """列出所有 kernelcat 项目及其会话文件

    Args:
        directory: kernelcat sessions 目录

    Returns:
        字典：项目路径 -> 会话文件列表
    """
    from collections import defaultdict

    projects = defaultdict(list)
    jsonl_files = list(directory.glob('**/*.jsonl'))

    for file_path in jsonl_files:
        project = get_session_project(file_path)
        if project:
            projects[project].append(file_path)

    return dict(projects)


def get_user_messages_from_file(file_path: Path, cli_name: str = 'kcat') -> List[str]:
    """从文件中提取用户消息

    Args:
        file_path: 文件路径
        cli_name: CLI 类型

    Returns:
        用户消息列表
    """
    user_messages = []
    try:
        messages = load_messages_from_file(file_path, cli_name)
        for msg in messages:
            if msg['type'] == 'user':
                # 提取文本内容
                content = msg.get('message', {}).get('content', [])
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text = item.get('text', '').strip()
                        if text:
                            # 只取前100个字符
                            preview = text[:100] + ('...' if len(text) > 100 else '')
                            user_messages.append(preview)
    except:
        pass
    return user_messages


def load_all_messages(directory: Path, include_agents: bool = False, cli_name: str = 'claude-code',
                     project_filter: str = None) -> List[Dict[str, Any]]:
    """加载目录中所有JSONL文件的消息

    Args:
        directory: 包含历史记录的目录
        include_agents: 是否包含agent文件（仅用于claude-code）
        cli_name: CLI工具名称 ('claude-code' 或 'kcat')
        project_filter: 项目路径过滤（仅用于kcat）
    """
    all_messages = []

    if cli_name == 'claude-code':
        # Claude Code: 扁平目录结构，所有文件在同一目录
        jsonl_files = list(directory.glob('*.jsonl'))

        # 过滤 agent 文件
        if not include_agents:
            jsonl_files = [f for f in jsonl_files if not f.name.startswith('agent-')]

    elif cli_name == 'kcat':
        # kernelcat: YYYY/MM/DD 目录结构
        jsonl_files = list(directory.glob('**/*.jsonl'))

        # 如果指定了项目过滤
        if project_filter:
            filtered_files = []
            for file_path in jsonl_files:
                project = get_session_project(file_path)
                if project and project_filter in project:
                    filtered_files.append(file_path)
            jsonl_files = filtered_files
            print(f"项目过滤: {project_filter}")

    print(f"找到 {len(jsonl_files)} 个对话记录文件")

    for file_path in jsonl_files:
        messages = load_messages_from_file(file_path, cli_name)
        all_messages.extend(messages)

    # 按时间戳排序
    all_messages.sort(key=lambda x: x['timestamp'])

    return all_messages


def format_tool_use(tool_item: Dict, use_color: bool = True) -> str:
    """格式化工具调用"""
    tool_name = tool_item.get('name', 'unknown')
    tool_id = tool_item.get('id', '')[:12]
    tool_input = tool_item.get('input', {})

    header = f"🔧 工具调用: {tool_name} [{tool_id}]"
    lines = [f"\n┌─ {colorize(header, Colors.TOOL_CALL, use_color)}"]

    # 显示主要参数
    if tool_name == 'Bash':
        cmd = tool_input.get('command', '')
        desc = tool_input.get('description', '')
        lines.append(f"│  命令: {cmd}")
        if desc:
            lines.append(f"│  说明: {desc}")

    elif tool_name in ['Read', 'Write', 'Edit']:
        file_path = tool_input.get('file_path', '')
        lines.append(f"│  文件: {file_path}")

        if tool_name == 'Edit':
            old_str = tool_input.get('old_string', '')
            new_str = tool_input.get('new_string', '')
            if old_str:
                preview = old_str[:100] + ('...' if len(old_str) > 100 else '')
                lines.append(f"│  修改: {len(old_str)} → {len(new_str)} 字符")
        elif tool_name == 'Write':
            content = tool_input.get('content', '')
            lines.append(f"│  内容长度: {len(content)} 字符")

    elif tool_name == 'Glob':
        pattern = tool_input.get('pattern', '')
        lines.append(f"│  模式: {pattern}")

    elif tool_name == 'Grep':
        pattern = tool_input.get('pattern', '')
        output_mode = tool_input.get('output_mode', 'files_with_matches')
        lines.append(f"│  搜索: {pattern}")
        lines.append(f"│  模式: {output_mode}")

    elif tool_name == 'Task':
        description = tool_input.get('description', '')
        subagent_type = tool_input.get('subagent_type', '')
        lines.append(f"│  任务: {description}")
        lines.append(f"│  代理: {subagent_type}")

    else:
        # 其他工具，显示所有参数
        for key, value in tool_input.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + '...'
            lines.append(f"│  {key}: {value}")

    lines.append("└─")
    return '\n'.join(lines)


def format_tool_result(result_item: Dict, truncate: bool = False, use_color: bool = True) -> str:
    """格式化工具结果

    Args:
        result_item: 工具结果数据
        truncate: 是否截断长输出（默认False，显示完整内容）
        use_color: 是否使用颜色
    """
    tool_id = result_item.get('tool_use_id', '')[:12]
    content = result_item.get('content', '')

    header = f"✅ 工具输出 [{tool_id}]"
    lines = [f"\n┌─ {colorize(header, Colors.TOOL_OUTPUT, use_color)}"]

    # 处理不同类型的内容
    if isinstance(content, str):
        content_lines = content.split('\n')

        if truncate:
            # 截断模式：限制行数和每行长度
            max_lines = 30
            max_line_length = 120

            if len(content_lines) > max_lines:
                show_lines = content_lines[:max_lines]
                lines.append(f"│  (显示前 {max_lines} 行，共 {len(content_lines)} 行)")
                for line in show_lines:
                    if len(line) > max_line_length:
                        line = line[:max_line_length] + '...'
                    lines.append(f"│  {line}")
                lines.append(f"│  ... (还有 {len(content_lines) - max_lines} 行)")
            else:
                for line in content_lines:
                    if len(line) > max_line_length:
                        line = line[:max_line_length] + '...'
                    lines.append(f"│  {line}")
        else:
            # 完整模式：显示所有内容
            for line in content_lines:
                lines.append(f"│  {line}")
    else:
        lines.append(f"│  {content}")

    lines.append("└─")
    return '\n'.join(lines)


def format_message_content(content_list: List[Dict],
                          show_thinking: bool = True,
                          show_tools: bool = True,
                          truncate: bool = False,
                          use_color: bool = True) -> str:
    """格式化消息内容

    Args:
        content_list: 消息内容列表
        show_thinking: 是否显示思考过程
        show_tools: 是否显示工具调用和输出
        truncate: 是否截断长输出（默认False，显示完整内容）
        use_color: 是否使用颜色
    """
    formatted_parts = []

    for content_item in content_list:
        content_type = content_item.get('type', '')

        if content_type == 'text':
            text = content_item.get('text', '')
            if text:
                formatted_parts.append(text)

        elif content_type == 'thinking' and show_thinking:
            thinking = content_item.get('thinking', '')
            if thinking:
                # 思考过程使用暗淡颜色
                header = colorize("╔══ 💭 思考过程 ══╗", Colors.THINKING, use_color)
                formatted_parts.append(f"\n{header}")
                thinking_lines = thinking.split('\n')

                if truncate:
                    # 截断模式：限制行数和每行长度
                    max_thinking_lines = 20
                    max_line_length = 118

                    if len(thinking_lines) > max_thinking_lines:
                        for line in thinking_lines[:max_thinking_lines]:
                            colored_line = colorize(f"║ {line[:max_line_length]}", Colors.THINKING, use_color)
                            formatted_parts.append(colored_line)
                        info_line = colorize(f"║ ... (还有 {len(thinking_lines) - max_thinking_lines} 行)", Colors.THINKING, use_color)
                        formatted_parts.append(info_line)
                    else:
                        for line in thinking_lines:
                            colored_line = colorize(f"║ {line[:max_line_length]}", Colors.THINKING, use_color)
                            formatted_parts.append(colored_line)
                else:
                    # 完整模式：显示所有内容
                    for line in thinking_lines:
                        colored_line = colorize(f"║ {line}", Colors.THINKING, use_color)
                        formatted_parts.append(colored_line)

                footer = colorize(f"╚{'═' * 120}╝", Colors.THINKING, use_color)
                formatted_parts.append(footer)

        elif content_type == 'tool_use' and show_tools:
            formatted_parts.append(format_tool_use(content_item, use_color))

        elif content_type == 'tool_result' and show_tools:
            formatted_parts.append(format_tool_result(content_item, truncate, use_color))

    return '\n'.join(formatted_parts)


def format_timestamp(timestamp_str: str) -> str:
    """格式化时间戳"""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str


def display_messages(messages: List[Dict[str, Any]],
                     show_thinking: bool = True,
                     show_tools: bool = True,
                     truncate: bool = False,
                     limit: int = None,
                     use_color: bool = None):
    """在终端显示消息

    Args:
        use_color: 是否使用颜色（None表示自动检测）
    """
    # 自动检测颜色支持
    if use_color is None:
        use_color = supports_color()

    if limit:
        messages = messages[-limit:]

    print(f"\n{'='*80}")
    print(colorize(f"对话历史记录 (共 {len(messages)} 条消息)", Colors.HIGHLIGHT, use_color))
    print(f"{'='*80}\n")

    for i, msg in enumerate(messages, 1):
        msg_type = msg['type']

        # 用户消息用红色，助手消息用蓝色
        if msg_type == 'user':
            role = colorize("👤 用户", Colors.USER, use_color)
        else:
            role = colorize("🤖 助手", Colors.ASSISTANT, use_color)

        timestamp = format_timestamp(msg['timestamp'])
        timestamp_colored = colorize(timestamp, Colors.TIMESTAMP, use_color)

        # 分隔线
        separator = colorize('─'*80, Colors.SEPARATOR, use_color)
        print(f"\n{separator}")

        # 标题行
        print(f"[{i}] {role} - {timestamp_colored}")

        # 元信息（灰色）
        meta_info = f"会话: {msg['session_id'][:8]}... | 文件: {msg['file']}"
        print(colorize(meta_info, Colors.INFO, use_color))

        print(separator)

        # 提取并格式化消息内容
        message_data = msg.get('message', {})
        content = message_data.get('content', [])

        if isinstance(content, list):
            formatted_content = format_message_content(content, show_thinking, show_tools, truncate, use_color)
            if formatted_content:
                print(formatted_content)
            else:
                print(colorize("[空消息]", Colors.INFO, use_color))
        else:
            print(str(content))

        print()


def export_to_file(messages: List[Dict[str, Any]],
                   output_file: str,
                   show_thinking: bool = True,
                   show_tools: bool = True,
                   truncate: bool = False):
    """导出消息到文本文件（不包含颜色代码）"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Claude Code 对话历史记录\n")
        f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总消息数: {len(messages)}\n")
        f.write(f"{'='*80}\n\n")

        for i, msg in enumerate(messages, 1):
            role = "用户" if msg['type'] == 'user' else "助手"
            timestamp = format_timestamp(msg['timestamp'])

            f.write(f"\n{'─'*80}\n")
            f.write(f"[{i}] {role} - {timestamp}\n")
            f.write(f"会话: {msg['session_id']} | 文件: {msg['file']}\n")
            f.write(f"{'─'*80}\n\n")

            # 提取并格式化消息内容（不使用颜色）
            message_data = msg.get('message', {})
            content = message_data.get('content', [])

            if isinstance(content, list):
                formatted_content = format_message_content(content, show_thinking, show_tools, truncate, use_color=False)
                f.write(formatted_content if formatted_content else "[空消息]")
            else:
                f.write(str(content))

            f.write("\n\n")

    print(f"\n对话历史已导出到: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='查看 CLI 工具对话历史记录（支持 Claude Code 和 kernelcat）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
    # Claude Code（默认）
    python view_chat_history.py
    python view_chat_history.py /path/to/chat/history
    python view_chat_history.py ~/claude-sessions --no-thinking

    # kernelcat - 查看目录
    python view_chat_history.py /path/to/kernelcat/sessions --cli-name kcat
    python view_chat_history.py . --cli-name kcat --no-deduplicate

    # kernelcat - 查看单个文件
    python view_chat_history.py --cli-name kcat --file /path/to/session.jsonl
    python view_chat_history.py --cli-name kcat --file /path/to/session.jsonl --limit 10 --no-thinking
        '''
    )

    parser.add_argument('path', nargs='?', default='.',
                        help='包含jsonl文件的目录（默认为当前目录）')
    parser.add_argument('--cli-name', type=str, default='claude-code',
                        choices=['claude-code', 'kcat'],
                        help='CLI工具名称：claude-code（默认）或 kcat（kernelcat）')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='只显示最近的N条消息')
    parser.add_argument('--session', type=str, metavar='ID',
                        help='只显示特定会话ID的消息')
    parser.add_argument('--no-thinking', action='store_true',
                        help='不显示思考内容（仅显示文本消息）')
    parser.add_argument('--no-tools', action='store_true',
                        help='不显示工具调用和输出')
    parser.add_argument('--truncate', action='store_true',
                        help='截断长输出（限制行数和每行长度，默认显示完整内容）')
    parser.add_argument('--no-deduplicate', action='store_true',
                        help='不去除重复消息（默认会自动去重）')
    parser.add_argument('--no-color', action='store_true',
                        help='禁用颜色输出（默认自动检测终端颜色支持）')
    parser.add_argument('--export', type=str, metavar='FILE',
                        help='导出到指定文件而不是显示在终端')
    parser.add_argument('--include-agents', action='store_true',
                        help='包含代理（agent-*）文件（仅用于claude-code）')

    # kernelcat 专属参数
    parser.add_argument('--list-projects', action='store_true',
                        help='列出所有项目及会话数（仅用于kcat）')
    parser.add_argument('--project', type=str, metavar='PATH',
                        help='按项目路径过滤（支持部分匹配，仅用于kcat）')
    parser.add_argument('--file', type=str, metavar='JSONL',
                        help='直接指定单个jsonl文件（仅用于kcat）')

    args = parser.parse_args()

    # 获取数据目录或文件
    input_path = Path(args.path).expanduser().resolve()

    if not input_path.exists():
        print(f"错误: 路径不存在: {input_path}")
        return

    # 如果指定了 --file 参数（kernelcat 单文件模式）
    if args.file:
        if args.cli_name != 'kcat':
            print("错误: --file 仅适用于 kernelcat (--cli-name kcat)")
            return

        file_path = Path(args.file).expanduser().resolve()
        if not file_path.exists():
            print(f"错误: 文件不存在: {file_path}")
            return

        if not file_path.is_file():
            print(f"错误: 不是文件: {file_path}")
            return

        # 直接加载单个文件
        print(f"正在加载单个会话文件... (kernelcat: {file_path})")
        all_messages = load_messages_from_file(file_path, 'kcat')

        if not all_messages:
            print("文件中没有找到任何对话消息")
            return

        # 显示项目信息
        project = get_session_project(file_path)
        if project:
            print(f"📁 项目: {project}")

        print(f"✓ 加载了 {len(all_messages)} 条消息")

        # 跳过去重（单文件不需要去重）
        # 直接显示
        if args.export:
            export_to_file(all_messages, args.export, not args.no_thinking, not args.no_tools, args.truncate)
        else:
            use_color = None if not args.no_color else False
            display_messages(all_messages, not args.no_thinking, not args.no_tools, args.truncate, args.limit, use_color)
        return

    # 原有的目录处理逻辑
    data_dir = input_path

    if not data_dir.is_dir():
        print(f"错误: 路径不是目录: {data_dir}")
        return

    # kernelcat: 列出项目
    if args.list_projects:
        if args.cli_name != 'kcat':
            print("错误: --list-projects 仅适用于 kernelcat (--cli-name kcat)")
            return

        projects = list_kernelcat_projects(data_dir)
        if not projects:
            print("未找到任何项目")
            return

        print(f"\n找到 {len(projects)} 个项目:\n")
        print("="*120)

        for project, files in sorted(projects.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n📁 {project}")
            print(f"   会话数: {len(files)}\n")

            # 按时间排序文件
            files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

            for i, file_path in enumerate(files_sorted, 1):
                # 获取用户消息
                user_msgs = get_user_messages_from_file(file_path, 'kcat')

                # 显示文件路径
                print(f"   [{i}] {file_path}")

                # 显示用户发言
                if user_msgs:
                    for j, msg in enumerate(user_msgs, 1):
                        # 缩进显示用户消息
                        msg_lines = msg.split('\n')
                        print(f"       💬 用户消息 {j}: {msg_lines[0]}")
                        for line in msg_lines[1:]:
                            if line.strip():
                                print(f"          {line}")
                else:
                    print(f"       （无用户消息）")
                print()

        print("="*120)
        print(f"\n💡 使用 --project 参数过滤特定项目:")
        print(f"   python view_chat_history.py {data_dir} --cli-name kcat --project <项目路径或关键字>\n")
        return

    # 加载所有消息
    cli_display_name = 'kernelcat' if args.cli_name == 'kcat' else 'Claude Code'
    print(f"正在加载对话记录... ({cli_display_name}: {data_dir})")
    all_messages = load_all_messages(data_dir, include_agents=args.include_agents,
                                    cli_name=args.cli_name, project_filter=args.project)

    if not all_messages:
        print("没有找到任何对话消息")
        return

    # 去重处理（默认启用）
    if not args.no_deduplicate:
        original_count = len(all_messages)
        all_messages = deduplicate_messages(all_messages)
        removed_count = original_count - len(all_messages)
        if removed_count > 0:
            print(f"✓ 已去重: 移除了 {removed_count} 条重复消息（{original_count} → {len(all_messages)}）")
        else:
            print(f"✓ 已去重: 未发现重复消息")
    else:
        print(f"⚠️  未去重: 保留了所有消息（可能包含重复）")

    # 如果指定了会话ID，进行过滤
    if args.session:
        all_messages = [msg for msg in all_messages if args.session in msg['session_id']]
        print(f"过滤后找到 {len(all_messages)} 条消息（会话 {args.session}）")

    # 显示或导出
    if args.export:
        export_to_file(all_messages, args.export, not args.no_thinking, not args.no_tools, args.truncate)
    else:
        # 确定是否使用颜色
        use_color = None if not args.no_color else False
        display_messages(all_messages, not args.no_thinking, not args.no_tools, args.truncate, args.limit, use_color)


if __name__ == '__main__':
    main()
