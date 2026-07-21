"""
数据库模块 — SQLite 操作
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'fridge.db')


def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    cursor = conn.cursor()

    # 家庭画像表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS family_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_name TEXT NOT NULL,
            height REAL,
            weight REAL,
            age INTEGER,
            allergies TEXT DEFAULT '[]',
            dislikes_main TEXT DEFAULT '[]',
            dislikes_ingredient TEXT DEFAULT '[]',
            dislikes_taste TEXT DEFAULT '[]',
            health_notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 冰箱库存表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fridge_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT DEFAULT '个',
            production_date TEXT,
            expiry_date TEXT,
            confidence TEXT DEFAULT '高',
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 用餐计划表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meal_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_type TEXT NOT NULL,
            meal_time TEXT NOT NULL,
            people_count INTEGER NOT NULL,
            plan_a TEXT,
            plan_b TEXT,
            selected_plan TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 对话历史表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 用餐时间配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meal_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_type TEXT NOT NULL UNIQUE,
            meal_time TEXT NOT NULL,
            enabled INTEGER DEFAULT 1
        )
    ''')

    conn.commit()
    conn.close()


# ==================== 家庭画像操作 ====================

def add_member(member_name, height=None, weight=None, age=None,
               allergies=None, dislikes_main=None, dislikes_ingredient=None,
               dislikes_taste=None, health_notes=''):
    """添加家庭成员"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO family_profile
        (member_name, height, weight, age, allergies, dislikes_main,
         dislikes_ingredient, dislikes_taste, health_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        member_name, height, weight, age,
        json.dumps(allergies or [], ensure_ascii=False),
        json.dumps(dislikes_main or [], ensure_ascii=False),
        json.dumps(dislikes_ingredient or [], ensure_ascii=False),
        json.dumps(dislikes_taste or [], ensure_ascii=False),
        health_notes
    ))
    conn.commit()
    member_id = cursor.lastrowid
    conn.close()
    return member_id


def update_member(member_id, **kwargs):
    """更新家庭成员信息"""
    conn = get_connection()
    cursor = conn.cursor()

    set_clauses = []
    values = []
    for key, value in kwargs.items():
        if key in ('allergies', 'dislikes_main', 'dislikes_ingredient', 'dislikes_taste'):
            value = json.dumps(value, ensure_ascii=False)
        set_clauses.append(f"{key} = ?")
        values.append(value)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(member_id)

    sql = f"UPDATE family_profile SET {', '.join(set_clauses)} WHERE id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()


def get_all_members():
    """获取所有家庭成员"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM family_profile ORDER BY id')
    rows = cursor.fetchall()
    conn.close()

    members = []
    for row in rows:
        member = dict(row)
        for field in ('allergies', 'dislikes_main', 'dislikes_ingredient', 'dislikes_taste'):
            member[field] = json.loads(member[field])
        members.append(member)
    return members


def get_profile_summary():
    """获取家庭画像摘要（用于Prompt）"""
    members = get_all_members()
    if not members:
        return "暂无家庭成员信息"

    lines = []
    for m in members:
        parts = [f"{m['member_name']}"]
        if m.get('height') and m.get('weight'):
            parts.append(f"身高{m['height']}cm/体重{m['weight']}kg")
        if m.get('age'):
            parts.append(f"{m['age']}岁")
        if m.get('dislikes_main'):
            parts.append(f"不吃{','.join(m['dislikes_main'])}")
        if m.get('dislikes_ingredient'):
            parts.append(f"不要{','.join(m['dislikes_ingredient'])}")
        if m.get('dislikes_taste'):
            parts.append(f"不吃{','.join(m['dislikes_taste'])}")
        if m.get('health_notes'):
            parts.append(m['health_notes'])
        lines.append("，".join(parts))

    return "\n".join(lines)


def clear_profile():
    """清空家庭画像"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM family_profile')
    conn.commit()
    conn.close()


# ==================== 冰箱库存操作 ====================

def add_inventory_item(name, category, quantity, unit='个',
                       production_date=None, expiry_date=None,
                       confidence='高', photo_path=None):
    """添加库存项"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO fridge_inventory
        (name, category, quantity, unit, production_date, expiry_date,
         confidence, photo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, category, quantity, unit, production_date, expiry_date,
          confidence, photo_path))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


def get_inventory():
    """获取所有库存"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM fridge_inventory WHERE quantity > 0 ORDER BY expiry_date')
    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        # 计算剩余天数
        if item.get('expiry_date'):
            try:
                exp = datetime.strptime(item['expiry_date'], '%Y-%m-%d')
                item['days_left'] = (exp - datetime.now()).days
            except:
                item['days_left'] = None
        else:
            item['days_left'] = None
        items.append(item)
    return items


def get_inventory_summary():
    """获取库存摘要（用于Prompt）"""
    items = get_inventory()
    if not items:
        return "冰箱为空"

    lines = []
    for item in items:
        line = f"- {item['name']} × {item['quantity']}{item['unit']}"
        if item.get('days_left') is not None:
            if item['days_left'] < 0:
                line += f"（已过期）"
            elif item['days_left'] <= 3:
                line += f"（{item['days_left']}天后过期⚠️）"
            elif item['days_left'] <= 7:
                line += f"（{item['days_left']}天后过期）"
        lines.append(line)

    return "\n".join(lines)


def deduct_inventory(items_to_deduct):
    """
    扣减库存
    items_to_deduct: [{"name": "鸡蛋", "quantity": 2}, ...]
    """
    conn = get_connection()
    cursor = conn.cursor()

    results = []
    for item in items_to_deduct:
        name = item['name']
        qty = item['quantity']

        # 查找库存
        cursor.execute(
            'SELECT id, quantity FROM fridge_inventory WHERE name = ? AND quantity > 0',
            (name,)
        )
        row = cursor.fetchone()

        if row:
            old_qty = row['quantity']
            new_qty = max(0, old_qty - qty)
            cursor.execute(
                'UPDATE fridge_inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_qty, row['id'])
            )
            results.append({"name": name, "old": old_qty, "new": new_qty})
        else:
            results.append({"name": name, "old": 0, "new": 0, "error": "库存不足"})

    conn.commit()
    conn.close()
    return results


def get_expiring_items(days=3):
    """获取即将过期的食材"""
    conn = get_connection()
    cursor = conn.cursor()

    future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')

    cursor.execute('''
        SELECT * FROM fridge_inventory
        WHERE expiry_date IS NOT NULL
        AND expiry_date <= ? AND expiry_date >= ?
        AND quantity > 0
        ORDER BY expiry_date
    ''', (future, today))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==================== 用餐计划操作 ====================

def add_meal_plan(meal_type, meal_time, people_count, plan_a, plan_b):
    """添加用餐计划"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO meal_plan (meal_type, meal_time, people_count, plan_a, plan_b)
        VALUES (?, ?, ?, ?, ?)
    ''', (meal_type, meal_time, people_count,
          json.dumps(plan_a, ensure_ascii=False),
          json.dumps(plan_b, ensure_ascii=False)))
    conn.commit()
    plan_id = cursor.lastrowid
    conn.close()
    return plan_id


def confirm_meal_plan(plan_id, selected_plan):
    """确认用餐计划"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE meal_plan
        SET selected_plan = ?, status = 'confirmed'
        WHERE id = ?
    ''', (selected_plan, plan_id))
    conn.commit()
    conn.close()


def get_pending_plans():
    """获取待确认的计划"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meal_plan WHERE status = 'pending' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    plans = []
    for row in rows:
        plan = dict(row)
        plan['plan_a'] = json.loads(plan['plan_a']) if plan['plan_a'] else None
        plan['plan_b'] = json.loads(plan['plan_b']) if plan['plan_b'] else None
        plans.append(plan)
    return plans


# ==================== 用餐时间配置 ====================

def set_meal_schedule(meal_type, meal_time):
    """设置用餐时间"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO meal_schedule (meal_type, meal_time)
        VALUES (?, ?)
    ''', (meal_type, meal_time))
    conn.commit()
    conn.close()


def get_meal_schedule():
    """获取用餐时间配置"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM meal_schedule WHERE enabled = 1')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==================== 对话历史 ====================

def add_conversation(session_id, role, content, action=None):
    """添加对话记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conversation_history (session_id, role, content, action)
        VALUES (?, ?, ?, ?)
    ''', (session_id, role, content, action))
    conn.commit()
    conn.close()


def get_recent_conversations(session_id, limit=10):
    """获取最近的对话"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM conversation_history
        WHERE session_id = ?
        ORDER BY created_at DESC LIMIT ?
    ''', (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


if __name__ == '__main__':
    # 初始化数据库
    init_db()
    print("数据库初始化完成")

    # 测试添加成员
    add_member("爸爸", dislikes_taste=["辣"])
    add_member("孩子", dislikes_main=["苦瓜"], dislikes_ingredient=["葱"])
    print("添加成员完成")

    # 测试添加库存
    add_inventory_item("鸡蛋", "蛋类", 6, "个", expiry_date="2026-08-15")
    add_inventory_item("西红柿", "蔬菜", 3, "个", expiry_date="2026-08-05")
    print("添加库存完成")

    # 测试查询
    print("\n家庭画像：")
    print(get_profile_summary())

    print("\n冰箱库存：")
    print(get_inventory_summary())
