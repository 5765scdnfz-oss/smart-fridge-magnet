"""
食材识别模块 — 调用 MiMo v2.5 识别冰箱照片中的食材
"""
import os
import json
from datetime import datetime
from .mimo_client import call_mimo_vision, call_mimo_text_with_json
from .prompts import FOOD_RECOGNITION_PROMPT
from . import database as db


def recognize_food(image_path):
    """
    识别图片中的食材

    Args:
        image_path: 图片文件路径

    Returns:
        list: 识别到的食材列表
    """
    # 调用 MiMo 视觉模型
    result = call_mimo_vision(
        prompt=FOOD_RECOGNITION_PROMPT,
        image_path=image_path
    )

    # 解析返回的 JSON
    if isinstance(result, str):
        try:
            # 尝试解析 JSON
            items = json.loads(result)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            items = extract_json_from_text(result)
    else:
        items = result

    # 验证和标准化
    if isinstance(items, list):
        items = [standardize_item(item) for item in items]
    elif isinstance(items, dict) and 'error' in items:
        return items
    else:
        items = []

    return items


def extract_json_from_text(text):
    """从文本中提取JSON"""
    # 尝试找 JSON 数组
    start = text.find('[')
    if start != -1:
        bracket_count = 0
        for i in range(start, len(text)):
            if text[i] == '[':
                bracket_count += 1
            elif text[i] == ']':
                bracket_count -= 1
            if bracket_count == 0:
                try:
                    return json.loads(text[start:i+1])
                except:
                    break

    # 尝试找 JSON 对象
    start = text.find('{')
    if start != -1:
        brace_count = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
            if brace_count == 0:
                try:
                    return [json.loads(text[start:i+1])]
                except:
                    break

    return []


def standardize_item(item):
    """标准化食材数据"""
    # 确保必要字段存在
    standardized = {
        'name': item.get('name', '未知'),
        'category': item.get('category', '其他'),
        'quantity': parse_number(item.get('quantity', 1)),
        'unit': item.get('unit', '个'),
        'production_date': parse_date(item.get('production_date')),
        'expiry_date': parse_date(item.get('expiry_date')),
        'confidence': item.get('confidence', '中')
    }
    return standardized


def parse_number(value):
    """解析数字"""
    if isinstance(value, (int, float)):
        return value
    try:
        # 移除非数字字符
        import re
        nums = re.findall(r'[\d.]+', str(value))
        if nums:
            return float(nums[0])
    except:
        pass
    return 1


def parse_date(value):
    """解析日期"""
    if not value:
        return None

    # 如果已经是 YYYY-MM-DD 格式
    if isinstance(value, str) and len(value) == 10 and value[4] == '-':
        return value

    # 尝试其他格式
    formats = ['%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日', '%m/%d/%Y']
    for fmt in formats:
        try:
            return datetime.strptime(str(value), fmt).strftime('%Y-%m-%d')
        except:
            continue

    return None


def save_to_inventory(items, photo_path=None):
    """
    将识别结果保存到数据库

    Args:
        items: 食材列表
        photo_path: 照片路径

    Returns:
        list: 保存的食材列表
    """
    saved = []
    for item in items:
        item_id = db.add_inventory_item(
            name=item['name'],
            category=item['category'],
            quantity=item['quantity'],
            unit=item['unit'],
            production_date=item.get('production_date'),
            expiry_date=item.get('expiry_date'),
            confidence=item.get('confidence', '中'),
            photo_path=photo_path
        )
        item['id'] = item_id
        saved.append(item)

    return saved


def format_recognition_result(items):
    """
    格式化识别结果为用户友好的文本

    Args:
        items: 食材列表

    Returns:
        str: 格式化的文本
    """
    if not items:
        return "未识别到任何食材 😅"

    if isinstance(items, dict) and 'error' in items:
        return f"识别失败：{items.get('error', '未知错误')}"

    lines = [f"🔍 识别到 {len(items)} 种食材：\n"]

    for i, item in enumerate(items, 1):
        line = f"{i}. {item['name']} × {item['quantity']}{item['unit']}"
        if item.get('expiry_date'):
            line += f"（保质期至 {item['expiry_date']}）")
        if item.get('confidence') == '低':
            line += " ⚠️识别不确定"
        lines.append(line)

    lines.append(f"\n✅ 已存入冰箱库存")
    return "\n".join(lines)


# ==================== 主函数 ====================

def process_photo(image_path):
    """
    处理照片：识别食材并存入库存

    Args:
        image_path: 图片文件路径

    Returns:
        dict: {
            "items": 识别到的食材列表,
            "message": 用户友好的消息,
            "success": 是否成功
        }
    """
    # 识别食材
    items = recognize_food(image_path)

    if isinstance(items, dict) and 'error' in items:
        return {
            "items": [],
            "message": f"识别失败：{items.get('error')}",
            "success": False
        }

    if not items:
        return {
            "items": [],
            "message": "未识别到任何食材，请重新拍照或调整角度",
            "success": False
        }

    # 保存到数据库
    saved_items = save_to_inventory(items, photo_path=image_path)

    # 格式化结果
    message = format_recognition_result(saved_items)

    return {
        "items": saved_items,
        "message": message,
        "success": True
    }


if __name__ == '__main__':
    # 测试
    print("食材识别模块")
    print("请通过 process_photo(image_path) 调用")
