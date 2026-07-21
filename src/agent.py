"""
Agent 模块 — 处理对话、提取画像、推荐菜谱
"""
import json
from datetime import datetime
from .mimo_client import call_mimo_text, call_mimo_text_with_json
from .prompts import (
    PROFILE_EXTRACTION_SYSTEM,
    build_profile_extraction_prompt,
    RECIPE_SYSTEM,
    build_recipe_prompt,
    build_chat_prompt
)
from . import database as db


# ==================== 对话处理 ====================

def chat(user_input, session_id="default"):
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
        result = handle_inventory_query()
    elif intent == "recommend":
        result = handle_recommend_request(user_input)
    elif intent == "help":
        result = handle_help()
    else:
        result = handle_general_chat(user_input, context)

    # 保存助手回复
    db.add_conversation(session_id, "assistant", result["reply"], result.get("action"))

    return result


def detect_intent(user_input):
    """
    检测用户意图

    Returns:
        str: intent类型
    """
    keywords = {
        "profile": ["家里", "几口人", "不吃", "忌口", "身高", "体重", "过敏", "减肥", "忌口"],
        "inventory": ["冰箱", "库存", "有什么", "还有什么", "看看"],
        "recommend": ["吃什么", "做饭", "做菜", "菜谱", "推荐", "晚饭", "午饭", "早饭", "晚餐", "午餐", "早餐"],
        "help": ["帮助", "怎么用", "功能", "你能做什么"]
    }

    user_lower = user_input.lower()

    scores = {}
    for intent, words in keywords.items():
        score = sum(1 for word in words if word in user_input)
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)

    return "general"


def get_context():
    """获取当前上下文"""
    members = db.get_all_members()
    inventory = db.get_inventory()

    context_parts = []

    if members:
        context_parts.append(f"家庭成员：{len(members)}人")
        for m in members:
            parts = [m['member_name']]
            if m.get('dislikes_main'):
                parts.append(f"不吃{','.join(m['dislikes_main'])}")
            if m.get('dislikes_taste'):
                parts.append(f"不吃{','.join(m['dislikes_taste'])}")
            context_parts.append("  " + "，".join(parts))

    if inventory:
        context_parts.append(f"冰箱库存：{len(inventory)}种食材")
    else:
        context_parts.append("冰箱库存：空")

    return "\n".join(context_parts)


# ==================== 画像处理 ====================

def handle_profile_update(user_input):
    """处理画像更新"""
    # 调用 MiMo 提取结构化数据
    prompt = build_profile_extraction_prompt(user_input)
    result = call_mimo_text_with_json(prompt, PROFILE_EXTRACTION_SYSTEM)

    if isinstance(result, dict) and 'error' in result:
        return {
            "reply": "抱歉，我没有完全理解你说的内容，能再描述一下吗？比如：家里几口人？谁有什么忌口？",
            "action": "profile_error"
        }

    # 处理提取结果
    action = result.get('action', 'create')
    members = result.get('members', [])
    meal_times = result.get('meal_times')

    if not members:
        return {
            "reply": "我没有识别到家庭成员信息，能再说一遍吗？比如：\n- 家里几口人\n- 每个人有什么忌口\n- 身高体重",
            "action": "profile_error"
        }

    # 保存到数据库
    saved_members = []
    for member in members:
        if action == 'create':
            member_id = db.add_member(
                member_name=member.get('name', '未知'),
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
        elif action == 'update':
            # 查找已有成员并更新
            existing = db.get_all_members()
            for ex in existing:
                if ex['member_name'] == member.get('name'):
                    db.update_member(
                        ex['id'],
                        height=member.get('height') or ex.get('height'),
                        weight=member.get('weight') or ex.get('weight'),
                        age=member.get('age') or ex.get('age'),
                        allergies=member.get('allergies') or ex.get('allergies'),
                        dislikes_main=member.get('dislikes_main') or ex.get('dislikes_main'),
                        dislikes_ingredient=member.get('dislikes_ingredient') or ex.get('dislikes_ingredient'),
                        dislikes_taste=member.get('dislikes_taste') or ex.get('dislikes_taste'),
                        health_notes=member.get('health_notes') or ex.get('health_notes')
                    )
                    saved_members.append(member)
                    break
            else:
                # 没找到，新建
                db.add_member(
                    member_name=member.get('name', '未知'),
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
    reply_parts = ["好的，已记录：\n"]
    for m in saved_members:
        line = f"👤 {m.get('name', '未知')}"
        details = []
        if m.get('dislikes_main'):
            details.append(f"不吃{','.join(m['dislikes_main'])}")
        if m.get('dislikes_ingredient'):
            details.append(f"不要{','.join(m['dislikes_ingredient'])}")
        if m.get('dislikes_taste'):
            details.append(f"不吃{','.join(m['dislikes_taste'])}")
        if m.get('health_notes'):
            details.append(m['health_notes'])
        if details:
            line += "：" + "，".join(details)
        reply_parts.append(line)

    if meal_times:
        reply_parts.append("\n⏰ 用餐时间：")
        for meal_type, time in meal_times.items():
            if time:
                meal_names = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}
                reply_parts.append(f"  {meal_names.get(meal_type, meal_type)}：{time}")

    reply_parts.append("\n还有什么需要补充的吗？")

    return {
        "reply": "\n".join(reply_parts),
        "action": "profile_update",
        "data": saved_members
    }


# ==================== 库存查询 ====================

def handle_inventory_query():
    """处理库存查询"""
    items = db.get_inventory()

    if not items:
        return {
            "reply": "🧊 冰箱是空的哦！\n\n你可以拍一张冰箱照片，我来帮你识别食材。",
            "action": "inventory_empty"
        }

    lines = [f"🧊 冰箱里有 {len(items)} 种食材：\n"]

    # 按分类分组
    categories = {}
    for item in items:
        cat = item.get('category', '其他')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    for cat, cat_items in categories.items():
        lines.append(f"【{cat}】")
        for item in cat_items:
            line = f"  • {item['name']} × {item['quantity']}{item.get('unit', '个')}"
            if item.get('days_left') is not None:
                if item['days_left'] < 0:
                    line += " ❌已过期"
                elif item['days_left'] <= 3:
                    line += f" ⚠️{item['days_left']}天后过期"
            lines.append(line)

    # 检查快过期的食材
    expiring = db.get_expiring_items(days=3)
    if expiring:
        lines.append(f"\n⚠️ 有 {len(expiring)} 种食材即将过期，建议优先使用！")

    return {
        "reply": "\n".join(lines),
        "action": "inventory_query",
        "data": items
    }


# ==================== 菜谱推荐 ====================

def handle_recommend_request(user_input):
    """处理菜谱推荐请求"""
    # 解析餐次和人数
    meal_info = parse_meal_info(user_input)
    meal_type = meal_info.get('meal_type', '晚餐')
    people_count = meal_info.get('people_count')

    # 如果没有指定人数，询问
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
    return generate_recommendation(meal_type, people_count)


def parse_meal_info(user_input):
    """解析用餐信息"""
    info = {}

    # 解析餐次
    if any(word in user_input for word in ['早餐', '早饭', '早上']):
        info['meal_type'] = '早餐'
    elif any(word in user_input for word in ['午餐', '午饭', '中午']):
        info['meal_type'] = '午餐'
    elif any(word in user_input for word in ['晚餐', '晚饭', '晚上']):
        info['meal_type'] = '晚餐'
    else:
        # 根据时间判断
        hour = datetime.now().hour
        if hour < 10:
            info['meal_type'] = '早餐'
        elif hour < 14:
            info['meal_type'] = '午餐'
        else:
            info['meal_type'] = '晚餐'

    # 解析人数
    import re
    numbers = re.findall(r'(\d+)\s*[个人人]', user_input)
    if numbers:
        info['people_count'] = int(numbers[0])

    return info


def generate_recommendation(meal_type, people_count):
    """
    生成菜谱推荐

    Args:
        meal_type: 餐次
        people_count: 人数

    Returns:
        dict: 推荐结果
    """
    # 获取库存和画像
    inventory_summary = db.get_inventory_summary()
    profile_summary = db.get_profile_summary()

    if inventory_summary == "冰箱为空":
        return {
            "reply": "🧊 冰箱是空的，没法推荐菜谱哦！\n\n请先拍一张冰箱照片，识别食材后再来问我。",
            "action": "inventory_empty"
        }

    # 构建 Prompt
    prompt = build_recipe_prompt(inventory_summary, profile_summary, meal_type, people_count)

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
    reply = format_recommendation(meal_type, people_count, result, plan_id)

    return {
        "reply": reply,
        "action": "recommend",
        "data": {
            "plan_id": plan_id,
            "plan_a": result.get('plan_a'),
            "plan_b": result.get('plan_b')
        }
    }


def format_recommendation(meal_type, people_count, plans, plan_id):
    """格式化推荐结果"""
    lines = [f"🍽️ {meal_type}推荐（{people_count}人份）\n"]

    for plan_name, plan_key in [('A方案', 'plan_a'), ('B方案', 'plan_b')]:
        plan = plans.get(plan_key)
        if not plan:
            continue

        lines.append(f"━━━ {plan_name} ━━━")

        for dish in plan.get('dishes', []):
            lines.append(f"\n🥘 {dish['name']}")
            lines.append(f"   ⏱️ {dish.get('cooking_time', '未知')}")

            # 食材
            ingredients = dish.get('ingredients', [])
            if ingredients:
                ing_strs = []
                for ing in ingredients:
                    if isinstance(ing, dict):
                        ing_strs.append(f"{ing.get('name', '')}{ing.get('amount', '')}")
                    else:
                        ing_strs.append(str(ing))
                lines.append(f"   🥬 {', '.join(ing_strs)}")

            # 忌口处理
            if dish.get('skip_ingredients'):
                lines.append(f"   ⚠️ 不放：{','.join(dish['skip_ingredients'])}")
                if dish.get('skip_reason'):
                    lines.append(f"      原因：{dish['skip_reason']}")

        if plan.get('total_time'):
            lines.append(f"\n   ⏰ 总用时：{plan['total_time']}")

        lines.append("")

    lines.append(f"💡 回复「选A」或「选B」确认方案，我会自动扣减库存")

    return "\n".join(lines)


# ==================== 确认方案 ====================

def confirm_plan(plan_id, selected_plan):
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
                # 简单解析数量
                qty = parse_amount(amount)
                if name:
                    items_to_deduct.append({"name": name, "quantity": qty})

    # 扣减库存
    deduct_results = db.deduct_inventory(items_to_deduct)

    # 更新计划状态
    db.confirm_meal_plan(plan_id, selected_plan)

    # 格式化回复
    lines = [f"✅ 已选择{selected_plan}方案\n", "📦 库存更新："]
    for r in deduct_results:
        if 'error' in r:
            lines.append(f"  • {r['name']}：库存不足")
        else:
            lines.append(f"  • {r['name']}：{r['old']}→{r['new']}")

    lines.append(f"\n祝你{plan['meal_type']}愉快！🎉")

    return {
        "reply": "\n".join(lines),
        "action": "confirm",
        "data": deduct_results
    }


def parse_amount(amount_str):
    """解析用量字符串"""
    if not amount_str:
        return 1

    import re
    nums = re.findall(r'[\d.]+', str(amount_str))
    if nums:
        return float(nums[0])
    return 1


# ==================== 帮助 ====================

def handle_help():
    """处理帮助请求"""
    return {
        "reply": """🤖 我是你的智能冰箱助手！

我能帮你：

📸 **拍照入库**
拍一张冰箱照片，我帮你识别食材并记录

🧊 **查看库存**
问"冰箱有什么"，我告诉你库存情况

🍽️ **推荐菜谱**
说"该做晚饭了"，我根据库存推荐A/B方案

👤 **管理画像**
告诉我家人的忌口和偏好，我会记住

⏰ **定时提醒**
设好用餐时间，我会提前推荐菜谱

试试看吧！""",
        "action": "help"
    }


# ==================== 通用对话 ====================

def handle_general_chat(user_input, context):
    """处理通用对话"""
    prompt = build_chat_prompt(user_input, context)
    reply = call_mimo_text(prompt)

    return {
        "reply": reply,
        "action": "chat"
    }
