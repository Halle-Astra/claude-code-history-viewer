#!/usr/bin/env python3
"""
快速查看对话历史统计信息

使用方法:
    python chat_stats.py [路径]

参数:
    路径: 包含jsonl文件的目录（可选，默认为当前目录）

示例:
    python chat_stats.py
    python chat_stats.py /path/to/chat/history
    python chat_stats.py ~/claude-sessions
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any


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


def get_stats(data_dir: Path = None):
    """获取对话历史统计信息

    Args:
        data_dir: 包含jsonl文件的目录，默认为当前工作目录
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
    earliest_date = None
    latest_date = None

    # 遍历所有jsonl文件
    for file_path in data_dir.glob('*.jsonl'):
        # 统计文件类型（但都要处理）
        if file_path.name.startswith('agent-'):
            files_by_type['agent'] += 1
        else:
            files_by_type['main'] += 1

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        msg_type = data.get('type')

                        if msg_type in ['user', 'assistant']:
                            # 检查是否有tool相关内容
                            has_tool_use = any(
                                c.get('type') == 'tool_use'
                                for c in data.get('message', {}).get('content', [])
                            )
                            has_tool_result = 'toolUseResult' in data

                            # 收集消息
                            all_messages.append({
                                'type': msg_type,
                                'timestamp': data.get('timestamp', ''),
                                'uuid': data.get('uuid', ''),
                                'message': data.get('message', {}),
                                'session_id': data.get('sessionId', ''),
                                'has_tool_use': has_tool_use,
                                'has_tool_result': has_tool_result
                            })

                            # 记录会话ID
                            session_id = data.get('sessionId', '')
                            if session_id:
                                sessions.add(session_id)

                            # 记录日期
                            timestamp_str = data.get('timestamp', '')
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

    print("\n" + "="*80)
    print("\n💡 查看完整对话内容:")
    print("   python3 view_chat_history.py --deduplicate --no-thinking --limit 50\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='查看对话历史统计信息',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
    python chat_stats.py
    python chat_stats.py /path/to/chat/history
    python chat_stats.py ~/claude-sessions
        '''
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='包含jsonl文件的目录（默认为当前目录）'
    )
    args = parser.parse_args()
    get_stats(args.path)
