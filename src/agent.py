"""
Agent 模块 — 处理对话、提取画像、推荐菜谱
增强版：更智能的意图识别、更丰富的画像提取、更精准的菜谱推荐
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .mimo_client import call_mimo_text, call_mimo_text_with_json
from .prompts import (
    PROFILE_EXTRACTION_SYSTEM,
    build_profile_extraction_prompt,
    RECIPE_SYSTEM,
    build_recipe_prompt,
    build_chat_prompt
)
from . import database as db


# ==================== 意图识别增强 ====================

# 意图关键词权重
INTENT_KEYWORDS = {
    "profile": {
        "keywords": ["家里", "几口人", "不吃", "忌口", "身高", "体重", "过敏", "减肥",
                      "糖尿病", "高血压", "孕妇", "哺乳", "老人", "小孩", "宝宝",
                      "不喜欢", "讨厌", "爱吃", "喜欢", "偏好", "口味"],
        "weight": 1.5  # 画像意图权重更高
    },
    "inventory": {
        "keywords": ["冰箱", "库存", "有什么", "还有什么", "看看", "查看", "还剩",
                      "多少", "快过期", "快坏了", "新鲜"],
        "weight": 1.0
    },
    "recommend": {
        "keywords": ["吃什么", "做饭", "做菜", "菜谱", "推荐", "晚饭", "午饭", "早饭",
                      "晚餐", "午餐", "早餐", "夜宵", "加餐", "想吃", "做啥",
                      "怎么吃", "搭配", "营养", "健康"],
        "weight": 1.2
    },
    "confirm": {
        "keywords": ["选A", "选B", "确认", "就这个", "好的", "可以", "行",
                      "选第一个", "选第二个"],
        "weight": 2.0  # 确认意图优先级最高
    },
    "help": {
        "keywords": ["帮助", "怎么用", "功能", "你能做什么", "说明", "教程"],
        "weight": 0.8
    }
}

# 餐次关键词
MEAL_KEYWORDS = {
    "早餐": ["早餐", "早饭", "早上", "早晨", "早"],
    "午餐": ["午餐", "午饭", "中午", "午"],
    "晚餐": ["晚餐", "晚饭", "晚上", "晚"],
    "夜宵": ["夜宵", "宵夜", "夜"],
    "加餐": ["加餐", "零食", "下午茶"]
}

# 人数提取模式
PEOPLE_PATTERNS = [
    r'(\d+)\s*[个人人]',
    r'[一家]\s*(\d+)\s*口',
    r'(\d+)\s*人份',
    r'(\d+)\s*位',
]


def detect_intent(user_input: str) -> str:
    """
    检测用户意图（增强版）

    Args:
        user_input: 用户输入

    Returns:
        str: intent类型
    """
    user_lower = user_input.lower()

    scores = {}
    for intent, config in INTENT_KEYWORDS.items():
        score = 0
        for keyword in config['keywords']:
            if keyword in user_input:
                score += config['weight']
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)

    return "general"


def parse_meal_info(user_input: str) -> Dict:
    """
    解析用餐信息（增强版）

    Args:
        user_input: 用户输入

    Returns:
        dict: {"meal_type": str, "people_count": int}
    """
    info = {}

    # 解析餐次
    for meal_type, keywords in MEAL_KEYWORDS.items():
        if any(kw in user_input for kw in keywords):
            info['meal_type'] = meal_type
            break

    # 如果没指定，根据时间判断
    if 'meal_type' not in info:
        hour = datetime.now().hour
        if hour < 10:
            info['meal_type'] = '早餐'
        elif hour < 14:
            info['meal_type'] = '午餐'
        elif hour < 17:
            info['meal_type'] = '下午茶'
        elif hour < 21:
            info['meal_type'] = '晚餐'
        else:
            info['meal_type'] = '夜宵'

    # 解析人数
    for pattern in PEOPLE_PATTERNS:
        match = re.search(pattern, user_input)
        if match:
            info['people_count'] = int(match.group(1))
            break

    return info


# ==================== 上下文管理 ====================

def get_context() -> str:
    """获取当前上下文"""
    members = db.get_all_members()
    inventory_result = db.get_inventory(page_size=1000)
    inventory = inventory_result.get('items', [])
    expiring = db.get_expiring_items(days=3)

    context_parts = []

    # 家庭成员
    if members:
        context_parts.append(f"【家庭成员】{len(members)}人")
        for m in members:
            parts = [m['member_name']]
            if m.get('age'):
                parts.append(f"{m['age']}岁")
            if m.get('dislikes_main'):
                parts.append(f"不吃{','.join(m['dislikes_main'])}")
            if m.get('dislikes_taste'):
                parts.append(f"不吃{','.join(m['dislikes_taste'])}")
            if m.get('dislikes_ingredient'):
                parts.append(f"不要{','.join(m['dislikes_ingredient'])}")
            if m.get('health_notes'):
                parts.append(m['health_notes'])
            context_parts.append("  " + "，".join(parts))
    else:
        context_parts.append("【家庭成员】未设置")

    # 冰箱库存
    if inventory:
        context_parts.append(f"【冰箱库存】{len(inventory)}种食材")

        # 按分类统计
        categories = {}
        for item in inventory:
            cat = item.get('category', '其他')
            categories[cat] = categories.get(cat, 0) + 1
        cat_str = "、".join([f"{cat}{count}种" for cat, count in categories.items()])
        context_parts.append(f"  分类：{cat_str}")

        # 快过期提醒
        if expiring:
            exp_names = "、".join([i['name'] for i in expiring[:3]])
            context_parts.append(f"  ⚠️ 即将过期：{exp_names}")
    else:
        context_parts.append("【冰箱库存】空")

    return "\n".join(context_parts)


# ==================== 对话处理 ====================

def chat(user_input: str, session_id: str = "default") -> Dict:
    """
    处理用户对话

    Args:
        user_input: 用户输入
        session_id: 会话ID

    Returns:
        dict: {"reply": 回复, "action": 动作类型, "data": 相关数据}
    """
    # 保存用户消息
    db.add_conversation(session_id, "user", user_input)

    # 获取当前上下文
    context = get_context()

    # 判断用户意图
    intent = detect_intent(user_input)

    if intent == "profile":
        result = handle_profile_update(user_input)
    elif intent == "inventory":
        result = handle_inventory_query(user_input)
    elif intent == "recommend":
        result = handle_recommend_request(user_input)
    elif intent == "confirm":
        result = handle_confirm(user_input)
    elif intent == "help":
        result = handle_help()
    else:
        result = handle_general_chat(user_input, context)

    # 保存助手回复
    db.add_conversation(session_id, "assistant", result["reply"], result.get("action"))

    return result


# ==================== 画像处理（增强版）====================

def handle_profile_update(user_input: str) -> Dict:
    """
    处理画像更新（增强版）

    支持：
    - 自然语言描述家庭成员
    - 批量添加/更新
    - 忌口分层处理
    - 健康备注
    - 用餐时间
    """
    # 调用 MiMo 提取结构化数据
    prompt = build_profile_extraction_prompt(user_input)
    result = call_mimo_text_with_json(prompt, PROFILE_EXTRACTION_SYSTEM)

    if isinstance(result, dict) and 'error' in result:
        return {
            "reply": "抱歉，我没有完全理解你说的内容，能再描述一下吗？\n\n"
                     "比如：\n"
                     "- 家里3口人，爸爸不吃辣，孩子不吃苦瓜\n"
                     "- 老婆怀孕了，需要补铁\n"
                     "- 我在减肥，少吃油腻",
            "action": "profile_error"
        }

    # 处理提取结果
    action = result.get('action', 'create')
    members = result.get('members', [])
    meal_times = result.get('meal_times')

    if not members:
        return {
            "reply": "我没有识别到家庭成员信息，能再说一遍吗？\n\n"
                     "示例：\n"
                     "- 家里3口人：爸爸（不吃辣）、妈妈（不吃香菜）、孩子（5岁，不吃苦瓜）\n"
                     "- 老公身高175，体重70公斤，不吃海鲜",
            "action": "profile_error"
        }

    # 保存到数据库
    saved_members = []
    updated_members = []

    for member in members:
        member_name = member.get('name', '未知')

        # 查找已有成员
        existing = db.get_all_members()
        existing_member = None
        for ex in existing:
            if ex['member_name'] == member_name:
                existing_member = ex
                break

        if existing_member and action in ('update', 'auto'):
            # 更新已有成员
            update_data = {}
            for field in ['height', 'weight', 'age', 'allergies', 'dislikes_main',
                          'dislikes_ingredient', 'dislikes_taste', 'health_notes']:
                new_val = member.get(field)
                old_val = existing_member.get(field)

                # 只更新有新值的字段
                if new_val is not None:
                    if isinstance(new_val, list) and isinstance(old_val, list):
                        # 列表类型：合并去重
                        merged = list(set(old_val + new_val))
                        update_data[field] = merged
                    elif isinstance(new_val, str) and isinstance(old_val, str):
                        # 字符串类型：追加或覆盖
                        if old_val and new_val not in old_val:
                            update_data[field] = f"{old_val}；{new_val}"
                        else:
                            update_data[field] = new_val
                    else:
                        update_data[field] = new_val

            if update_data:
                db.update_member(existing_member['id'], **update_data)
                updated_members.append(member_name)
        else:
            # 新增成员
            db.add_member(
                member_name=member_name,
                height=member.get('height'),
                weight=member.get('weight'),
                age=member.get('age'),
                allergies=member.get('allergies', []),
                dislikes_main=member.get('dislikes_main', []),
                dislikes_ingredient=member.get('dislikes_ingredient', []),
                dislikes_taste=member.get('dislikes_taste', []),
                health_notes=member.get('health_notes', '')
            )
            saved_members.append(member)

    # 保存用餐时间
    if meal_times:
        for meal_type, time in meal_times.items():
            if time:
                db.set_meal_schedule(meal_type, time)

    # 构建回复
    reply_parts = []

    if saved_members:
        reply_parts.append("✅ 新增家庭成员：")
        for m in saved_members:
            reply_parts.append(format_member_info(m))

    if updated_members:
        reply_parts.append(f"\n🔄 更新了 {len(updated_members)} 位成员信息")

    if meal_times:
        reply_parts.append("\n⏰ 用餐时间：")
        meal_names = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}
        for meal_type, time in meal_times.items():
            if time:
                reply_parts.append(f"  {meal_names.get(meal_type, meal_type)}：{time}")

    if not reply_parts:
        reply_parts.append("已记录！还有什么需要补充的吗？")
    else:
        reply_parts.append("\n还有什么需要补充的吗？")

    return {
        "reply": "\n".join(reply_parts),
        "action": "profile_update",
        "data": {
            "saved": [m.get('name') for m in saved_members],
            "updated": updated_members
        }
    }


def format_member_info(member: Dict) -> str:
    """格式化成员信息"""
    line = f"  👤 {member.get('name', '未知')}"

    details = []
    if member.get('age'):
        details.append(f"{member['age']}岁")
    if member.get('height') and member.get('weight'):
        details.append(f"{member['height']}cm/{member['weight']}kg")
    if member.get('dislikes_main'):
        details.append(f"不吃{','.join(member['dislikes_main'])}")
    if member.get('dislikes_ingredient'):
        details.append(f"不要{','.join(member['dislikes_ingredient'])}")
    if member.get('dislikes_taste'):
        details.append(f"不吃{','.join(member['dislikes_taste'])}")
    if member.get('allergies'):
        details.append(f"过敏：{','.join(member['allergies'])}")
    if member.get('health_notes'):
        details.append(member['health_notes'])

    if details:
        line += "：" + "，".join(details)

    return line


# ==================== 库存查询（增强版）====================

def handle_inventory_query(user_input: str) -> Dict:
    """
    处理库存查询（增强版）

    支持：
    - 分类查询
    - 过期查询
    - 数量查询
    """
    # 解析查询条件
    category = None
    expiring_only = False

    # 检查分类
    categories = ['蔬菜', '水果', '肉类', '海鲜', '蛋类', '乳制品',
                  '豆制品', '主食', '调味品', '饮料', '零食', '冷冻食品']
    for cat in categories:
        if cat in user_input:
            category = cat
            break

    # 检查过期
    if any(kw in user_input for kw in ['快过期', '快坏了', '要过期', '即将过期']):
        expiring_only = True

    # 查询
    if expiring_only:
        items = db.get_expiring_items(days=3)
        if not items:
            return {
                "reply": "🎉 没有即将过期的食材，库存都很新鲜！",
                "action": "inventory_query",
                "data": []
            }
        title = f"⚠️ 即将过期的食材（{len(items)}种）："
    elif category:
        items = db.get_inventory_by_category(category)
        if not items:
            return {
                "reply": f"🧊 冰箱里没有{category}类食材。",
                "action": "inventory_query",
                "data": []
            }
        title = f"🧊 {category}类食材（{len(items)}种）："
    else:
        result = db.get_inventory(page_size=1000)
        items = result.get('items', [])
        if not items:
            return {
                "reply": "🧊 冰箱是空的哦！\n\n你可以拍一张冰箱照片，我来帮你识别食材。",
                "action": "inventory_empty"
            }
        title = f"🧊 冰箱里有 {len(items)} 种食材："

    # 格式化
    lines = [title + "\n"]

    # 按分类分组（如果不是按分类查询）
    if not category:
        grouped = {}
        for item in items:
            cat = item.get('category', '其他')
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(item)

        for cat, cat_items in grouped.items():
            lines.append(f"【{cat}】")
            for item in cat_items:
                lines.append(format_inventory_item(item))
    else:
        for item in items:
            lines.append(format_inventory_item(item))

    # 统计信息
    expiring = db.get_expiring_items(days=3)
    if expiring and not expiring_only:
        lines.append(f"\n⚠️ 有 {len(expiring)} 种食材即将过期，建议优先使用！")

    return {
        "reply": "\n".join(lines),
        "action": "inventory_query",
        "data": items
    }


def format_inventory_item(item: Dict) -> str:
    """格式化库存项"""
    line = f"  • {item['name']} × {item['quantity']}{item.get('unit', '个')}"

    if item.get('days_left') is not None:
        days = item['days_left']
        if days < 0:
            line += " ❌已过期"
        elif days == 0:
            line += " ⚠️今天过期"
        elif days <= 3:
            line += f" ⚠️{days}天后过期"
        elif days <= 7:
            line += f" 📅{days}天后过期"

    return line


# ==================== 菜谱推荐（增强版）====================

def handle_recommend_request(user_input: str) -> Dict:
    """
    处理菜谱推荐请求（增强版）

    支持：
    - 自动识别餐次和人数
    - 优先使用快过期食材
    - 考虑家庭画像忌口
    - 提供营养信息
    """
    # 解析餐次和人数
    meal_info = parse_meal_info(user_input)
    meal_type = meal_info.get('meal_type', '晚餐')
    people_count = meal_info.get('people_count')

    # 如果没有指定人数，从画像获取
    if not people_count:
        members = db.get_all_members()
        if members:
            people_count = len(members)
        else:
            return {
                "reply": "请问今天几个人吃饭？",
                "action": "ask_people_count"
            }

    # 生成推荐
    return generate_recommendation(meal_type, people_count, user_input)


def get_nutrition_for_inventory() -> Optional[str]:
    """获取冰箱食材的营养数据"""
    items = db.get_inventory(page_size=1000).get('items', [])
    if not items:
        return None

    nutrition_lines = []
    for item in items[:10]:  # 只取前10种，避免prompt太长
        name = item['name']
        nutrition = db.get_nutrition_summary(name)
        if nutrition:
            nutrition_lines.append(f"- {nutrition}")

    return "\n".join(nutrition_lines) if nutrition_lines else None


def generate_recommendation(meal_type: str, people_count: int, user_input: str = "") -> Dict:
    """
    生成菜谱推荐（增强版）

    Args:
        meal_type: 餐次
        people_count: 人数
        user_input: 用户原始输入

    Returns:
        dict: 推荐结果
    """
    # 获取库存和画像
    inventory_summary = db.get_inventory_summary()
    profile_summary = db.get_profile_summary()

    if inventory_summary == "冰箱为空":
        return {
            "reply": "🧊 冰箱是空的，没法推荐菜谱哦！\n\n"
                     "请先拍一张冰箱照片，识别食材后再来问我。",
            "action": "inventory_empty"
        }

    # 获取快过期食材
    expiring = db.get_expiring_items(days=3)
    expiring_names = [i['name'] for i in expiring] if expiring else []

    # 获取营养数据
    nutrition_data = get_nutrition_for_inventory()

    # 构建增强 Prompt
    prompt = build_enhanced_recipe_prompt(
        inventory_summary=inventory_summary,
        profile_summary=profile_summary,
        meal_type=meal_type,
        people_count=people_count,
        nutrition_data=nutrition_data,
        expiring_items=expiring_names,
        user_input=user_input
    )

    # 调用 MiMo 生成菜谱
    result = call_mimo_text_with_json(prompt, RECIPE_SYSTEM)

    if isinstance(result, dict) and 'error' in result:
        return {
            "reply": "抱歉，生成菜谱时出了点问题，请稍后再试。",
            "action": "recommend_error"
        }

    # 保存到数据库
    plan_id = db.add_meal_plan(
        meal_type=meal_type,
        meal_time=datetime.now().strftime('%H:%M'),
        people_count=people_count,
        plan_a=result.get('plan_a'),
        plan_b=result.get('plan_b')
    )

    # 格式化回复
    reply = format_recommendation(meal_type, people_count, result, plan_id, expiring_names)

    return {
        "reply": reply,
        "action": "recommend",
        "data": {
            "plan_id": plan_id,
            "meal_type": meal_type,
            "people_count": people_count,
            "plan_a": result.get('plan_a'),
            "plan_b": result.get('plan_b')
        }
    }


def build_enhanced_recipe_prompt(
    inventory_summary: str,
    profile_summary: str,
    meal_type: str,
    people_count: int,
    nutrition_data: Optional[str] = None,
    expiring_items: List[str] = None,
    user_input: str = ""
) -> str:
    """构建增强版菜谱推荐 Prompt"""

    expiring_section = ""
    if expiring_items:
        expiring_section = f"""
【即将过期的食材（优先使用）】
{', '.join(expiring_items)}
这些食材应该优先使用，避免浪费。
"""

    nutrition_section = ""
    if nutrition_data:
        nutrition_section = f"""
【食材营养参考数据（每100g）】
{nutrition_data}
"""

    user_hint = ""
    if user_input:
        # 提取用户的特殊要求
        special_requests = []
        if any(kw in user_input for kw in ['简单', '快手', '快速']):
            special_requests.append("简单快手")
        if any(kw in user_input for kw in ['营养', '健康']):
            special_requests.append("营养健康")
        if any(kw in user_input for kw in ['清淡', '少油']):
            special_requests.append("清淡少油")
        if any(kw in user_input for kw in ['下饭', '好吃']):
            special_requests.append("下饭好吃")
        if special_requests:
            user_hint = f"\n【用户特殊要求】{', '.join(special_requests)}"

    return f"""
请根据以下信息推荐菜谱：

【冰箱库存】
{inventory_summary}

【家庭画像】
{profile_summary}
{expiring_section}{nutrition_section}
【用餐信息】
- 餐次：{meal_type}
- 用餐人数：{people_count}人
{user_hint}

请生成A/B两套方案，返回JSON格式：
{{
    "plan_a": {{
        "dishes": [
            {{
                "name": "菜名",
                "ingredients": [
                    {{"name": "食材名", "amount": "用量"}}
                ],
                "cooking_time": "烹饪时间",
                "difficulty": "简单/中等/困难",
                "nutrition_highlight": "营养亮点（可选）",
                "skip_ingredients": ["需要跳过的配料"],
                "skip_reason": "跳过原因（如果没有则为空字符串）"
            }}
        ],
        "total_time": "总时间",
        "total_difficulty": "整体难度"
    }},
    "plan_b": {{
        "dishes": [...同上格式...],
        "total_time": "总时间",
        "total_difficulty": "整体难度"
    }}
}}

推荐原则：
1. 优先使用冰箱库存中已有的食材
2. 优先使用快过期的食材
3. 主材料忌口：完全避开该食材，不推荐含此食材的菜
4. 配料忌口：保留菜品，但标注去掉该配料
5. 口味忌口：调整做法或推荐替代菜
6. 菜品要家常、易做、适合家庭
7. 每套方案2-3道菜，荤素搭配
8. 考虑营养均衡
"""


def format_recommendation(
    meal_type: str,
    people_count: int,
    plans: Dict,
    plan_id: int,
    expiring_items: List[str] = None
) -> str:
    """格式化推荐结果"""
    lines = [f"🍽️ {meal_type}推荐（{people_count}人份）\n"]

    if expiring_items:
        lines.append(f"💡 优先使用即将过期的食材：{', '.join(expiring_items)}\n")

    for plan_name, plan_key in [('A方案', 'plan_a'), ('B方案', 'plan_b')]:
        plan = plans.get(plan_key)
        if not plan:
            continue

        lines.append(f"━━━ {plan_name} ━━━")

        total_calories = 0
        total_protein = 0
        total_fat = 0

        for dish in plan.get('dishes', []):
            # 菜名和难度
            difficulty = dish.get('difficulty', '')
            diff_emoji = {'简单': '🟢', '中等': '🟡', '困难': '🔴'}.get(difficulty, '')
            lines.append(f"\n🥘 {dish['name']} {diff_emoji}")
            lines.append(f"   ⏱️ {dish.get('cooking_time', '未知')}")

            # 食材（带营养信息）
            ingredients = dish.get('ingredients', [])
            if ingredients:
                ing_strs = []
                for ing in ingredients:
                    if isinstance(ing, dict):
                        name = ing.get('name', '')
                        amount = ing.get('amount', '')
                        ing_strs.append(f"{name}{amount}")

                        # 尝试获取营养数据
                        nutrition = db.get_nutrition_by_name(name)
                        if nutrition:
                            if nutrition.get('energy_kcal'):
                                total_calories += nutrition['energy_kcal']
                            if nutrition.get('protein'):
                                total_protein += nutrition['protein']
                            if nutrition.get('fat'):
                                total_fat += nutrition['fat']
                    else:
                        ing_strs.append(str(ing))
                lines.append(f"   🥬 {', '.join(ing_strs)}")

            # 营养亮点
            if dish.get('nutrition_highlight'):
                lines.append(f"   💪 {dish['nutrition_highlight']}")

            # 忌口处理
            if dish.get('skip_ingredients'):
                lines.append(f"   ⚠️ 不放：{','.join(dish['skip_ingredients'])}")
                if dish.get('skip_reason'):
                    lines.append(f"      原因：{dish['skip_reason']}")

        # 总结
        if plan.get('total_time'):
            lines.append(f"\n   ⏰ 总用时：{plan['total_time']}")
        if plan.get('total_difficulty'):
            lines.append(f"   📊 整体难度：{plan['total_difficulty']}")

        # 营养估算
        if total_calories > 0:
            lines.append(f"   🔥 预估热量：约{int(total_calories)}kcal")
        if total_protein > 0:
            lines.append(f"   💪 蛋白质：约{int(total_protein)}g")

        lines.append("")

    lines.append(f"💡 回复「选A」或「选B」确认方案，我会自动扣减库存")

    return "\n".join(lines)


# ==================== 确认方案 ====================

def handle_confirm(user_input: str) -> Dict:
    """处理确认请求"""
    # 解析选择
    if any(kw in user_input for kw in ['选A', 'A', '第一个', '方案A']):
        selected = 'A'
    elif any(kw in user_input for kw in ['选B', 'B', '第二个', '方案B']):
        selected = 'B'
    else:
        return {
            "reply": "请选择 A 或 B 方案？",
            "action": "ask_selection"
        }

    # 获取待确认的计划
    plans = db.get_pending_plans()
    if not plans:
        return {
            "reply": "没有待确认的用餐计划，请先让我推荐菜谱。",
            "action": "no_pending_plan"
        }

    # 取最新的计划
    plan = plans[0]
    return confirm_plan(plan['id'], selected)


def confirm_plan(plan_id: int, selected_plan: str) -> Dict:
    """
    确认菜谱方案并扣减库存

    Args:
        plan_id: 计划ID
        selected_plan: 选择的方案（A/B）

    Returns:
        dict: 确认结果
    """
    # 获取计划
    plans = db.get_pending_plans()
    plan = None
    for p in plans:
        if p['id'] == plan_id:
            plan = p
            break

    if not plan:
        return {
            "reply": "未找到该用餐计划，可能已过期。",
            "action": "confirm_error"
        }

    # 获取选择的方案
    plan_data = plan.get(f'plan_{selected_plan.lower()}')
    if not plan_data:
        return {
            "reply": f"未找到{selected_plan}方案。",
            "action": "confirm_error"
        }

    # 提取需要扣减的食材
    items_to_deduct = []
    for dish in plan_data.get('dishes', []):
        for ing in dish.get('ingredients', []):
            if isinstance(ing, dict):
                name = ing.get('name', '')
                amount = ing.get('amount', '')
                qty = parse_amount(amount)
                if name:
                    items_to_deduct.append({"name": name, "quantity": qty})

    # 扣减库存
    try:
        deduct_results = db.deduct_inventory(items_to_deduct)
    except ValueError as e:
        return {
            "reply": f"库存不足：{str(e)}",
            "action": "deduct_error"
        }

    # 更新计划状态
    db.confirm_meal_plan(plan_id, selected_plan)

    # 格式化回复
    lines = [f"✅ 已选择{selected_plan}方案\n", "📦 库存更新："]
    for r in deduct_results:
        if 'error' in r:
            lines.append(f"  • {r['name']}：库存不足")
        else:
            lines.append(f"  • {r['name']}：{r['old']}→{r['new']}")

    meal_type = plan.get('meal_type', '餐')
    lines.append(f"\n祝你{meal_type}愉快！🎉")

    return {
        "reply": "\n".join(lines),
        "action": "confirm",
        "data": deduct_results
    }


def parse_amount(amount_str: str) -> float:
    """解析用量字符串"""
    if not amount_str:
        return 1

    nums = re.findall(r'[\d.]+', str(amount_str))
    if nums:
        return float(nums[0])
    return 1


# ==================== 帮助 ====================

def handle_help() -> Dict:
    """处理帮助请求"""
    return {
        "reply": """🤖 我是你的智能冰箱助手！

我能帮你：

📸 **拍照入库**
拍一张冰箱照片，我帮你识别食材并记录
• 支持手机拍照、相册选择
• 自动识别食材名称、数量、保质期
• 支持批量识别

🧊 **管理库存**
• 问"冰箱有什么"查看全部库存
• 问"快过期的"查看即将过期食材
• 问"蔬菜类"按分类查看
• 支持手动添加、修改、删除

🍽️ **推荐菜谱**
• 说"该做晚饭了"，我根据库存推荐A/B方案
• 优先使用快过期食材，减少浪费
• 考虑家人忌口和营养均衡
• 选方案后自动扣减库存

👤 **管理画像**
• 告诉我家里几口人，谁有什么忌口
• 我会记住每个人的偏好
• 推荐菜谱时自动避开忌口

⏰ **定时提醒**
• 设好用餐时间，我会提前推荐菜谱

试试看吧！""",
        "action": "help"
    }


# ==================== 通用对话 ====================

def handle_general_chat(user_input: str, context: str) -> Dict:
    """处理通用对话"""
    prompt = build_chat_prompt(user_input, context)
    reply = call_mimo_text(prompt)

    return {
        "reply": reply,
        "action": "chat"
    }


# ==================== 测试 ====================

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("Agent Module Test")
    print("=" * 50)

    # 测试意图识别
    test_cases = [
        "家里3口人，爸爸不吃辣",
        "冰箱有什么",
        "该做晚饭了，3个人吃",
        "选A",
        "帮助",
        "今天天气怎么样"
    ]

    print("\nIntent Detection:")
    for text in test_cases:
        intent = detect_intent(text)
        print(f"  [{intent}] {text}")

    # 测试餐次解析
    print("\nMeal Info Parsing:")
    meal_tests = [
        "该做晚饭了",
        "3个人吃早餐",
        "推荐午餐，4人份"
    ]
    for text in meal_tests:
        info = parse_meal_info(text)
        print(f"  {text} -> {info}")

    print("\nDone!")
