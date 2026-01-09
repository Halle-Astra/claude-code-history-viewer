#!/usr/bin/env python3
"""
快速查看对话历史统计信息（支持 Claude Code 和 kernelcat）

使用方法:
    python chat_stats.py [路径] [--cli-name CLI工具]

参数:
    路径: 包含jsonl文件的目录（可选，默认为当前目录）

可选参数:
    --cli-name: CLI工具名称，claude-code（默认）或 kcat（kernelcat）

示例:
    # Claude Code
    python chat_stats.py
    python chat_stats.py /path/to/chat/history

    # kernelcat
    python chat_stats.py /path/to/kernelcat/sessions --cli-name kcat
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Tuple


def parse_claude_code_line(data: Dict, file_path: Path) -> Tuple[Dict[str, Any], str]:
    """解析 Claude Code 格式的一行

    Returns:
        (message_dict, session_id)
    """
    msg_type = data.get('type')
    if msg_type not in ['user', 'assistant']:
        return None, ''

    # 检查是否有tool相关内容
    has_tool_use = any(
        c.get('type') == 'tool_use'
        for c in data.get('message', {}).get('content', [])
    )
    has_tool_result = 'toolUseResult' in data

    message = {
        'type': msg_type,
        'timestamp': data.get('timestamp', ''),
        'uuid': data.get('uuid', ''),
        'message': data.get('message', {}),
        'session_id': data.get('sessionId', ''),
        'has_tool_use': has_tool_use,
        'has_tool_result': has_tool_result
    }

    return message, data.get('sessionId', '')


def parse_kernelcat_line(data: Dict, file_path: Path) -> Tuple[Dict[str, Any], str]:
    """解析 kernelcat 格式的一行

    Returns:
        (message_dict, session_id)
    """
    if data.get('type') != 'response_item':
        return None, ''

    payload = data.get('payload', {})
    role = payload.get('role', '')
    if role not in ['user', 'assistant']:
        return None, ''

    # kernelcat 没有 tool_use/tool_result 概念，默认设为 False
    # 从文件名提取 session_id
    session_id = file_path.stem.split('-')[-1]

    # 转换为统一格式
    message_content = []
    for item in payload.get('content', []):
        item_type = item.get('type', '')
        if item_type in ['input_text', 'output_text']:
            message_content.append({
                'type': 'text',
                'text': item.get('text', '')
            })
        else:
            message_content.append(item)

    message = {
        'type': role,
        'timestamp': data.get('timestamp', ''),
        'uuid': '',  # kernelcat 没有 uuid
        'message': {'content': message_content},
        'session_id': session_id,
        'has_tool_use': False,
        'has_tool_result': False
    }

    return message, session_id


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
    """列出所有 kernelcat 项目及会话文件

    Args:
        directory: kernelcat sessions 目录

    Returns:
        字典：项目路径 -> 会话文件列表
    """
    projects = defaultdict(list)
    jsonl_files = list(directory.glob('**/*.jsonl'))

    for file_path in jsonl_files:
        project = get_session_project(file_path)
        if project:
            projects[project].append(file_path)

    return dict(projects)


def get_user_messages_from_file(file_path: Path) -> List[str]:
    """从文件中提取用户消息

    Args:
        file_path: 文件路径

    Returns:
        用户消息列表
    """
    user_messages = []
    try:
        message, _ = parse_kernelcat_line({'type': 'dummy'}, file_path)  # 占位，实际读取文件

        # 直接读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'response_item':
                        payload = data.get('payload', {})
                        if payload.get('role') == 'user':
                            content = payload.get('content', [])
                            for item in content:
                                if isinstance(item, dict) and item.get('type') in ['input_text', 'text']:
                                    text = item.get('text', '').strip()
                                    if text:
                                        # 只取前100个字符
                                        preview = text[:100] + ('...' if len(text) > 100 else '')
                                        user_messages.append(preview)
                except:
                    pass
    except:
        pass
    return user_messages


def deduplicate_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去除重复的消息"""
    seen = set()
    unique_messages = []

    for msg in messages:
        uuid = msg.get('uuid', '')
        if uuid:
            identifier = uuid
        else:
            timestamp = msg.get('timestamp', '')
            content = str(msg.get('message', {}))[:100]
            identifier = f"{timestamp}_{content}"

        if identifier not in seen:
            seen.add(identifier)
            unique_messages.append(msg)

    return unique_messages


def calculate_total_time(messages: List[Dict[str, Any]]) -> tuple[timedelta, List[Dict[str, Any]]]:
    """计算助手总处理时间（包含完整的工具调用过程，排除长时间中断）

    算法：
    1. 找到每个真实的用户消息（非tool_result）
    2. 找到该用户消息之后的所有助手响应（assistant + tool_result）
    3. 计算实际工作时间，排除超过30分钟的消息间隔（视为中断）
    4. 累加所有时间差
    5. 标记超过1小时的长响应

    Returns:
        (total_time, long_responses) 总时间和长响应列表
    """
    total_time = timedelta()
    long_responses = []  # 超过1小时的响应
    IDLE_THRESHOLD = timedelta(minutes=30)  # 超过30分钟视为中断

    i = 0
    while i < len(messages):
        msg = messages[i]

        # 找到真实的用户消息（不是tool_result，且不是空消息）
        if msg['type'] == 'user' and not msg.get('has_tool_result', False):
            # 检查消息内容是否为空（权限确认等空消息不算真实用户提问）
            has_content = False
            for content in msg.get('message', {}).get('content', []):
                if isinstance(content, dict) and content.get('type') == 'text':
                    text = content.get('text', '').strip()
                    if text:
                        has_content = True
                        break

            # 跳过空消息
            if not has_content:
                i += 1
                continue

            # 这是一条真实的用户提问
            try:
                start_time = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))

                # 收集该用户消息后的所有助手相关响应（保留类型信息）
                j = i + 1
                response_events = [{'time': start_time, 'has_tool_use': False, 'has_tool_result': False}]
                assistant_msg_count = 0
                tool_use_count = 0

                while j < len(messages):
                    next_msg = messages[j]

                    if next_msg['type'] == 'assistant' or next_msg.get('has_tool_result', False):
                        # 这是助手的响应或工具结果
                        msg_time = datetime.fromisoformat(next_msg['timestamp'].replace('Z', '+00:00'))
                        response_events.append({
                            'time': msg_time,
                            'has_tool_use': next_msg.get('has_tool_use', False),
                            'has_tool_result': next_msg.get('has_tool_result', False)
                        })
                        assistant_msg_count += 1
                        if next_msg.get('has_tool_use', False):
                            tool_use_count += 1
                        j += 1
                    elif next_msg['type'] == 'user' and not next_msg.get('has_tool_result', False):
                        # 遇到下一个真实用户消息，停止
                        break
                    else:
                        j += 1

                # 计算实际工作时间（排除长时间中断，但保留工具执行时间）
                response_events.sort(key=lambda x: x['time'])
                active_duration = timedelta()
                idle_periods = []  # 记录中断时段

                for k in range(len(response_events) - 1):
                    current_event = response_events[k]
                    next_event = response_events[k + 1]
                    time_gap = next_event['time'] - current_event['time']

                    # 判断这个间隔是否是工具执行时间
                    is_tool_execution = (
                        current_event['has_tool_use'] and
                        next_event['has_tool_result']
                    )

                    if is_tool_execution or time_gap <= IDLE_THRESHOLD:
                        # 工具执行时间或正常工作时间 - 全部计入
                        active_duration += time_gap
                    else:
                        # 中断时段
                        idle_periods.append({
                            'start': current_event['time'],
                            'end': next_event['time'],
                            'duration': time_gap
                        })

                # 总时长（包含中断）
                total_duration = response_events[-1]['time'] - response_events[0]['time'] if len(response_events) > 1 else timedelta()

                if active_duration > timedelta(0):
                    # 提取用户问题的简短摘要
                    user_text = ""
                    for content in msg.get('message', {}).get('content', []):
                        if content.get('type') == 'text':
                            user_text = content.get('text', '')[:100]
                            break

                    # 如果总时长超过1小时，记录详细信息
                    if total_duration >= timedelta(hours=1):
                        long_responses.append({
                            'user_question': user_text,
                            'start_time': start_time,
                            'end_time': response_events[-1]['time'],
                            'total_duration': total_duration,
                            'active_duration': active_duration,
                            'idle_periods': idle_periods,
                            'assistant_messages': assistant_msg_count,
                            'tool_uses': tool_use_count
                        })

                    # 累加实际工作时间（不含中断）
                    total_time += active_duration

            except Exception as e:
                pass

        i += 1

    return total_time, long_responses


def format_timedelta(td: timedelta) -> str:
    """格式化时间间隔"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}秒")

    return " ".join(parts)


def get_stats(data_dir: Path = None, cli_name: str = 'claude-code', project_filter: str = None,
              group_by_project: bool = False):
    """获取对话历史统计信息

    Args:
        data_dir: 包含jsonl文件的目录，默认为当前工作目录
        cli_name: CLI工具名称 ('claude-code' 或 'kcat')
        project_filter: 项目路径过滤（仅用于kcat）
        group_by_project: 是否按项目分组显示统计（仅用于kcat）
    """
    if data_dir is None:
        data_dir = Path.cwd()
    else:
        data_dir = Path(data_dir)

    if not data_dir.exists():
        print(f"错误: 目录不存在: {data_dir}")
        return

    if not data_dir.is_dir():
        print(f"错误: 路径不是目录: {data_dir}")
        return

    # 统计信息
    all_messages = []  # 收集所有消息
    sessions = set()
    files_by_type = {'main': 0, 'agent': 0}
    messages_by_date = defaultdict(int)
    messages_by_project = defaultdict(list)  # 按项目收集消息（仅kcat）
    earliest_date = None
    latest_date = None

    # 根据 CLI 类型选择文件搜索模式
    if cli_name == 'claude-code':
        jsonl_files = list(data_dir.glob('*.jsonl'))
    elif cli_name == 'kcat':
        jsonl_files = list(data_dir.glob('**/*.jsonl'))

        # 如果指定了项目过滤
        if project_filter:
            filtered_files = []
            for file_path in jsonl_files:
                project = get_session_project(file_path)
                if project and project_filter in project:
                    filtered_files.append(file_path)
            jsonl_files = filtered_files
            if project_filter:
                print(f"\n🔍 项目过滤: {project_filter}")
    else:
        print(f"错误: 不支持的 CLI 类型: {cli_name}")
        return

    # 选择解析器
    parser_func = parse_claude_code_line if cli_name == 'claude-code' else parse_kernelcat_line

    # 遍历所有jsonl文件
    for file_path in jsonl_files:
        # 统计文件类型（仅对 claude-code 有意义）
        if cli_name == 'claude-code':
            if file_path.name.startswith('agent-'):
                files_by_type['agent'] += 1
            else:
                files_by_type['main'] += 1
        else:
            files_by_type['main'] += 1

        # 获取项目信息（仅 kernelcat）
        project = ''
        if cli_name == 'kcat' and group_by_project:
            project = get_session_project(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)

                        # 使用对应的解析器
                        message, session_id = parser_func(data, file_path)
                        if message is None:
                            continue

                        # 收集消息
                        all_messages.append(message)

                        # 如果需要按项目分组（仅 kernelcat）
                        if cli_name == 'kcat' and group_by_project and project:
                            messages_by_project[project].append(message)

                        # 记录会话ID
                        if session_id:
                            sessions.add(session_id)

                        # 记录日期
                        timestamp_str = message.get('timestamp', '')
                        if timestamp_str:
                            try:
                                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                date_str = dt.strftime('%Y-%m-%d')
                                messages_by_date[date_str] += 1

                                if earliest_date is None or dt < earliest_date:
                                    earliest_date = dt
                                if latest_date is None or dt > latest_date:
                                    latest_date = dt
                            except:
                                pass

                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    # 去重
    original_count = len(all_messages)
    all_messages = deduplicate_messages(all_messages)
    deduplicated_count = len(all_messages)

    # 按时间排序
    all_messages.sort(key=lambda x: x['timestamp'])

    # 统计消息数
    user_messages = sum(1 for msg in all_messages if msg['type'] == 'user')
    assistant_messages = sum(1 for msg in all_messages if msg['type'] == 'assistant')
    total_messages = len(all_messages)

    # 计算总耗时和长响应
    total_time, long_responses = calculate_total_time(all_messages)

    # 打印统计信息
    print("\n" + "="*80)
    print("对话历史统计信息（已去重）")
    print("="*80)

    print(f"\n📁 文件统计:")
    print(f"   主会话文件: {files_by_type['main']} 个")
    print(f"   代理文件: {files_by_type['agent']} 个")
    print(f"   总计: {files_by_type['main'] + files_by_type['agent']} 个文件")

    print(f"\n💬 消息统计:")
    print(f"   原始消息: {original_count:,} 条")
    if original_count != deduplicated_count:
        removed = original_count - deduplicated_count
        print(f"   去重后: {deduplicated_count:,} 条（移除了 {removed:,} 条重复，{removed*100//original_count}%）")
    print(f"   用户消息: {user_messages:,} 条")
    print(f"   助手消息: {assistant_messages:,} 条")

    print(f"\n🔗 会话统计:")
    print(f"   不同会话: {len(sessions)} 个")

    if earliest_date and latest_date:
        print(f"\n📅 时间跨度:")
        print(f"   最早消息: {earliest_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   最新消息: {latest_date.strftime('%Y-%m-%d %H:%M:%S')}")
        days_span = (latest_date - earliest_date).days
        print(f"   跨度: {days_span} 天")

    # 耗时统计
    print(f"\n⏱️  总耗时统计:")
    print(f"   助手处理总时长: {format_timedelta(total_time)}")
    if assistant_messages > 0:
        avg_time = total_time / assistant_messages
        print(f"   平均响应时间: {format_timedelta(avg_time)}")

    # 计算工作效率
    if earliest_date and latest_date:
        total_span = latest_date - earliest_date
        if total_span.total_seconds() > 0:
            work_percentage = (total_time.total_seconds() / total_span.total_seconds()) * 100
            print(f"   工作时间占比: {work_percentage:.1f}% （总耗时/总跨度）")

    # 显示长响应信息
    if long_responses:
        print(f"\n⚠️  长时间响应（≥1小时）：")
        print(f"   共 {len(long_responses)} 次超过1小时的响应")
        print(f"\n   详细信息：")
        for i, resp in enumerate(long_responses, 1):
            total_duration_str = format_timedelta(resp['total_duration'])
            active_duration_str = format_timedelta(resp['active_duration'])
            start_str = resp['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            end_str = resp['end_time'].strftime('%m-%d %H:%M:%S')
            question = resp['user_question']
            if len(question) > 60:
                question = question[:57] + '...'

            print(f"\n   {i}. 时间跨度: {start_str} → {end_str}")
            print(f"      总时长: {total_duration_str}")
            print(f"      实际工作: {active_duration_str}")
            print(f"      用户问题: {question}")
            print(f"      助手消息数: {resp['assistant_messages']} 条")
            print(f"      工具调用: {resp['tool_uses']} 次")

            # 显示中断时段
            if resp['idle_periods']:
                total_idle = sum((p['duration'] for p in resp['idle_periods']), timedelta())
                print(f"      中断次数: {len(resp['idle_periods'])} 次（共 {format_timedelta(total_idle)}）")
                for j, idle in enumerate(resp['idle_periods'], 1):
                    idle_start = idle['start'].strftime('%m-%d %H:%M')
                    idle_end = idle['end'].strftime('%m-%d %H:%M')
                    idle_duration = format_timedelta(idle['duration'])
                    print(f"         • 中断{j}: {idle_start} → {idle_end} ({idle_duration})")

        print(f"\n   💡 总耗时已排除中断时间（超过30分钟无消息视为中断）")
        print(f"      如需调整中断阈值，请修改代码中的 IDLE_THRESHOLD")

    print(f"\n💡 说明:")
    print(f"   • 总耗时 = 所有「用户提问→助手完整回复」的实际工作时间")
    print(f"   • 包含助手的思考、工具调用、代码编写等完整过程")
    print(f"   • 不含等待用户输入的时间")
    print(f"   • 已排除中断时间（超过30分钟无消息视为中断）")
    print(f"   • 已去重，避免重复计算")

    if messages_by_date:
        print(f"\n📊 每日消息数（最近10天）:")
        sorted_dates = sorted(messages_by_date.items(), reverse=True)[:10]
        for date_str, count in sorted_dates:
            bar = "█" * (count // 10) + "▌" * ((count % 10) // 5)
            print(f"   {date_str}: {count:4d} 条 {bar}")

    # 按项目分组统计（仅 kernelcat）
    if cli_name == 'kcat' and group_by_project and messages_by_project:
        print(f"\n📁 按项目分组统计:")
        print("="*80)

        # 对每个项目计算统计
        for project, project_messages in sorted(messages_by_project.items(),
                                                 key=lambda x: len(x[1]), reverse=True):
            # 去重
            project_messages_dedup = deduplicate_messages(project_messages)
            user_msgs = sum(1 for msg in project_messages_dedup if msg['type'] == 'user')
            assistant_msgs = sum(1 for msg in project_messages_dedup if msg['type'] == 'assistant')

            # 计算耗时
            total_time, _ = calculate_total_time(project_messages_dedup)

            print(f"\n📁 {project}")
            print(f"   消息数: {len(project_messages_dedup)} 条（用户: {user_msgs}, 助手: {assistant_msgs}）")
            print(f"   总耗时: {format_timedelta(total_time)}")

        print("\n" + "="*80)

    print("\n" + "="*80)
    print("\n💡 查看完整对话内容:")
    print("   python3 view_chat_history.py --deduplicate --no-thinking --limit 50\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='查看对话历史统计信息（支持 Claude Code 和 kernelcat）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
    # Claude Code（默认）
    python chat_stats.py
    python chat_stats.py /path/to/chat/history

    # kernelcat
    python chat_stats.py /path/to/kernelcat/sessions --cli-name kcat
    python chat_stats.py /path/to/kernelcat/sessions --cli-name kcat --group-by-project
    python chat_stats.py /path/to/kernelcat/sessions --cli-name kcat --project jax-dna
        '''
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='包含jsonl文件的目录（默认为当前目录）'
    )
    parser.add_argument(
        '--cli-name',
        type=str,
        default='claude-code',
        choices=['claude-code', 'kcat'],
        help='CLI工具名称：claude-code（默认）或 kcat（kernelcat）'
    )

    # kernelcat 专属参数
    parser.add_argument(
        '--list-projects',
        action='store_true',
        help='列出所有项目及会话数（仅用于kcat）'
    )
    parser.add_argument(
        '--project',
        type=str,
        metavar='PATH',
        help='按项目路径过滤（支持部分匹配，仅用于kcat）'
    )
    parser.add_argument(
        '--group-by-project',
        action='store_true',
        help='按项目分组显示统计（仅用于kcat）'
    )

    args = parser.parse_args()

    data_dir = Path(args.path).expanduser().resolve()

    # 如果是列出项目
    if args.list_projects:
        if args.cli_name != 'kcat':
            print("错误: --list-projects 仅适用于 kernelcat (--cli-name kcat)")
            exit(1)

        projects = list_kernelcat_projects(data_dir)
        if not projects:
            print("未找到任何项目")
            exit(0)

        print(f"\n找到 {len(projects)} 个项目:\n")
        print("="*120)

        for project, files in sorted(projects.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n📁 {project}")
            print(f"   会话数: {len(files)}\n")

            # 按时间排序文件
            files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

            for i, file_path in enumerate(files_sorted, 1):
                # 获取用户消息
                user_msgs = get_user_messages_from_file(file_path)

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
        print(f"   python chat_stats.py {data_dir} --cli-name kcat --project <项目路径或关键字>")
        print(f"\n💡 使用 --group-by-project 按项目分组统计:")
        print(f"   python chat_stats.py {data_dir} --cli-name kcat --group-by-project\n")
        exit(0)

    get_stats(args.path, args.cli_name, args.project, args.group_by_project)
