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

    # 预设分类表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            icon TEXT DEFAULT '📦',
            sort_order INTEGER DEFAULT 0
        )
    ''')

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

    # 冰箱库存表（带乐观锁）
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
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 索引优化
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_inventory_category
        ON fridge_inventory(category)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_inventory_expiry
        ON fridge_inventory(expiry_date)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_inventory_name_qty
        ON fridge_inventory(name, quantity)
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

    # 营养成分表（中国食物成分表）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nutrition_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_code TEXT,
            food_name TEXT NOT NULL,
            category TEXT,
            edible REAL,
            water REAL,
            energy_kcal REAL,
            energy_kj REAL,
            protein REAL,
            fat REAL,
            cho REAL,
            dietary_fiber REAL,
            cholesterol REAL,
            vitamin_a REAL,
            vitamin_c REAL,
            ca REAL,
            fe REAL,
            zn REAL,
            UNIQUE(food_name)
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

    # 初始化预设分类（如果为空）
    cursor.execute('SELECT COUNT(*) FROM inventory_categories')
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ('蔬菜', '🥬', 1),
            ('水果', '🍎', 2),
            ('肉类', '🥩', 3),
            ('海鲜', '🐟', 4),
            ('蛋类', '🥚', 5),
            ('乳制品', '🥛', 6),
            ('豆制品', '🫘', 7),
            ('主食', '🍚', 8),
            ('调味品', '🧂', 9),
            ('饮料', '🥤', 10),
            ('零食', '🍪', 11),
            ('冷冻食品', '🧊', 12),
            ('其他', '📦', 99),
        ]
        cursor.executemany(
            'INSERT INTO inventory_categories (name, icon, sort_order) VALUES (?, ?, ?)',
            default_categories
        )

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

# 预设分类（与数据库同步）
DEFAULT_CATEGORIES = [
    '蔬菜', '水果', '肉类', '海鲜', '蛋类', '乳制品',
    '豆制品', '主食', '调味品', '饮料', '零食', '冷冻食品', '其他'
]


def validate_date(date_str):
    """
    校验日期格式

    Args:
        date_str: 日期字符串

    Returns:
        str: 格式化后的日期 (YYYY-MM-DD)

    Raises:
        ValueError: 日期格式错误
    """
    if not date_str:
        return None

    # 支持的格式
    formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    raise ValueError(f"日期格式错误: {date_str}，支持格式: YYYY-MM-DD")


def validate_category(category):
    """
    校验分类是否在预设列表中

    Args:
        category: 分类名称

    Returns:
        str: 校验后的分类

    Raises:
        ValueError: 分类不在预设列表中
    """
    if category not in DEFAULT_CATEGORIES:
        raise ValueError(f"分类 '{category}' 不在预设列表中，可选: {', '.join(DEFAULT_CATEGORIES)}")
    return category


def add_inventory_item(name, category, quantity, unit='个',
                       production_date=None, expiry_date=None,
                       confidence='高', photo_path=None):
    """
    添加库存项

    Args:
        name: 食材名称
        category: 分类（必须在预设列表中）
        quantity: 数量
        unit: 单位
        production_date: 生产日期（可选，格式 YYYY-MM-DD）
        expiry_date: 保质期（可选，格式 YYYY-MM-DD）
        confidence: 识别置信度
        photo_path: 照片路径

    Returns:
        int: 新增项ID

    Raises:
        ValueError: 参数校验失败
    """
    # 校验
    validate_category(category)
    production_date = validate_date(production_date)
    expiry_date = validate_date(expiry_date)

    # 日期逻辑校验
    if production_date and expiry_date:
        if production_date > expiry_date:
            raise ValueError("生产日期不能晚于保质期")

    if quantity <= 0:
        raise ValueError("数量必须大于0")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO fridge_inventory
        (name, category, quantity, unit, production_date, expiry_date,
         confidence, photo_path, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (name, category, quantity, unit, production_date, expiry_date,
          confidence, photo_path))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


def batch_add_inventory_items(items):
    """
    批量添加库存项（原子操作）

    Args:
        items: 库存项列表 [{"name": "...", "category": "...", "quantity": ...}, ...]

    Returns:
        dict: {"success": [...], "failed": [...]}

    Raises:
        ValueError: 任何一项校验失败时回滚全部
    """
    success_items = []
    failed_items = []

    conn = get_connection()
    try:
        conn.execute('BEGIN')
        cursor = conn.cursor()

        for item in items:
            try:
                # 校验
                category = validate_category(item.get('category', '其他'))
                production_date = validate_date(item.get('production_date'))
                expiry_date = validate_date(item.get('expiry_date'))
                quantity = float(item.get('quantity', 0))

                if quantity <= 0:
                    raise ValueError("数量必须大于0")

                if production_date and expiry_date and production_date > expiry_date:
                    raise ValueError("生产日期不能晚于保质期")

                cursor.execute('''
                    INSERT INTO fridge_inventory
                    (name, category, quantity, unit, production_date, expiry_date,
                     confidence, photo_path, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (
                    item['name'],
                    category,
                    quantity,
                    item.get('unit', '个'),
                    production_date,
                    expiry_date,
                    item.get('confidence', '高'),
                    item.get('photo_path')
                ))

                success_items.append({
                    "item_id": cursor.lastrowid,
                    "name": item['name'],
                    "success": True
                })

            except Exception as e:
                failed_items.append({
                    "name": item.get('name', '未知'),
                    "success": False,
                    "error": str(e)
                })

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise ValueError(f"批量添加失败，已回滚: {str(e)}")

    finally:
        conn.close()

    return {"success": success_items, "failed": failed_items}


def get_inventory(category=None, page=1, page_size=50):
    """
    获取库存（分页）

    Args:
        category: 按分类筛选（可选）
        page: 页码（从1开始）
        page_size: 每页数量（默认50）

    Returns:
        dict: {"items": [...], "total": int, "page": int, "page_size": int, "total_pages": int}
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 计算总数
    if category:
        cursor.execute(
            'SELECT COUNT(*) FROM fridge_inventory WHERE quantity > 0 AND category = ?',
            (category,)
        )
    else:
        cursor.execute('SELECT COUNT(*) FROM fridge_inventory WHERE quantity > 0')

    total = cursor.fetchone()[0]

    # 分页查询
    offset = (page - 1) * page_size
    if category:
        cursor.execute('''
            SELECT * FROM fridge_inventory
            WHERE quantity > 0 AND category = ?
            ORDER BY expiry_date, created_at
            LIMIT ? OFFSET ?
        ''', (category, page_size, offset))
    else:
        cursor.execute('''
            SELECT * FROM fridge_inventory
            WHERE quantity > 0
            ORDER BY expiry_date, created_at
            LIMIT ? OFFSET ?
        ''', (page_size, offset))

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

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


def update_inventory_item(item_id, version=None, **kwargs):
    """
    更新库存项（带乐观锁）

    Args:
        item_id: 库存项ID
        version: 版本号（乐观锁，不传则跳过锁检查）
        **kwargs: 要更新的字段

    Raises:
        ValueError: 库存项不存在或版本冲突
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 检查是否存在
    cursor.execute('SELECT id, version FROM fridge_inventory WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"库存项 #{item_id} 不存在")

    # 乐观锁检查
    if version is not None and row['version'] != version:
        conn.close()
        raise ValueError(f"版本冲突：当前版本 {row['version']}，传入版本 {version}，请刷新后重试")

    # 校验日期
    if 'production_date' in kwargs:
        kwargs['production_date'] = validate_date(kwargs['production_date'])
    if 'expiry_date' in kwargs:
        kwargs['expiry_date'] = validate_date(kwargs['expiry_date'])
    if 'category' in kwargs:
        validate_category(kwargs['category'])

    # 构建更新语句
    allowed_fields = {'name', 'category', 'quantity', 'unit', 'production_date',
                      'expiry_date', 'confidence', 'photo_path'}
    set_clauses = []
    values = []

    for key, value in kwargs.items():
        if key in allowed_fields:
            set_clauses.append(f"{key} = ?")
            values.append(value)

    if not set_clauses:
        conn.close()
        raise ValueError("没有有效的更新字段")

    # 更新版本号和时间
    set_clauses.append("version = version + 1")
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(item_id)

    sql = f"UPDATE fridge_inventory SET {', '.join(set_clauses)} WHERE id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()


def delete_inventory_item(item_id):
    """
    删除库存项（软删除，设为quantity=0）

    Args:
        item_id: 库存项ID

    Raises:
        ValueError: 库存项不存在
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 检查是否存在
    cursor.execute('SELECT id FROM fridge_inventory WHERE id = ?', (item_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"库存项 #{item_id} 不存在")

    cursor.execute('''
        UPDATE fridge_inventory
        SET quantity = 0, version = version + 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (item_id,))
    conn.commit()
    conn.close()


def get_preset_categories():
    """获取预设分类列表（从数据库）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, icon, sort_order FROM inventory_categories ORDER BY sort_order')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_inventory_categories():
    """获取库存中实际使用的分类"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM fridge_inventory
        WHERE quantity > 0
        GROUP BY category
        ORDER BY category
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [{"name": row['category'], "count": row['count']} for row in rows]


def get_inventory_summary():
    """获取库存摘要（用于Prompt）"""
    result = get_inventory(page_size=1000)  # 摘要不分页
    items = result['items']

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
    扣减库存（FIFO 先进先出 + 事务）

    Args:
        items_to_deduct: [{"name": "鸡蛋", "quantity": 2}, ...]

    Returns:
        list: 扣减结果

    Raises:
        ValueError: 库存不足时回滚
    """
    conn = get_connection()
    try:
        conn.execute('BEGIN')
        cursor = conn.cursor()

        results = []
        for item in items_to_deduct:
            name = item['name']
            qty_needed = float(item['quantity'])

            if qty_needed <= 0:
                results.append({"name": name, "error": "数量必须大于0"})
                continue

            # FIFO: 按生产日期排序（先买的先用）
            cursor.execute('''
                SELECT id, quantity, production_date, version
                FROM fridge_inventory
                WHERE name = ? AND quantity > 0
                ORDER BY
                    CASE WHEN production_date IS NOT NULL THEN 0 ELSE 1 END,
                    production_date ASC,
                    created_at ASC
            ''', (name,))

            rows = cursor.fetchall()
            remaining = qty_needed
            deduct_details = []

            for row in rows:
                if remaining <= 0:
                    break

                available = row['quantity']
                deduct_qty = min(available, remaining)
                new_qty = available - deduct_qty

                cursor.execute('''
                    UPDATE fridge_inventory
                    SET quantity = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND version = ?
                ''', (new_qty, row['id'], row['version']))

                # 检查是否更新成功（乐观锁）
                if cursor.rowcount == 0:
                    conn.rollback()
                    raise ValueError(f"并发冲突：{name} 在扣减过程中被修改，请重试")

                deduct_details.append({
                    "id": row['id'],
                    "deducted": deduct_qty,
                    "remaining": new_qty
                })
                remaining -= deduct_qty

            if remaining > 0:
                conn.rollback()
                raise ValueError(f"库存不足：{name} 需要 {qty_needed}，实际只有 {qty_needed - remaining}")

            results.append({
                "name": name,
                "requested": qty_needed,
                "deducted": qty_needed,
                "details": deduct_details
            })

        conn.commit()
        return results

    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_expiring_items(days=3):
    """
    获取即将过期的食材

    Args:
        days: 天数（默认3天）

    Returns:
        list: 即将过期的食材列表
    """
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

    items = []
    for row in rows:
        item = dict(row)
        if item.get('expiry_date'):
            try:
                exp = datetime.strptime(item['expiry_date'], '%Y-%m-%d')
                item['days_left'] = (exp - datetime.now()).days
            except:
                item['days_left'] = None
        items.append(item)

    return items


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


# ==================== 营养数据操作 ====================

def import_nutrition_data(json_path):
    """
    从JSON文件导入营养数据

    Args:
        json_path: JSON文件路径

    Returns:
        int: 导入的记录数
    """
    conn = get_connection()
    cursor = conn.cursor()

    with open(json_path, 'r', encoding='utf-8') as f:
        foods = json.load(f)

    imported = 0
    for food in foods:
        try:
            # 提取分类（从foodCode推断或使用默认）
            food_name = food.get('foodName', '')
            food_code = food.get('foodCode', '')

            # 解析数值，处理 "—" 和 "Tr" 等非数字值
            def parse_num(val):
                if val is None or val == '—' or val == 'Tr' or val == '':
                    return None
                try:
                    return float(val)
                except:
                    return None

            cursor.execute('''
                INSERT OR IGNORE INTO nutrition_data
                (food_code, food_name, edible, water, energy_kcal, energy_kj,
                 protein, fat, cho, dietary_fiber, cholesterol,
                 vitamin_a, vitamin_c, ca, fe, zn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                food_code,
                food_name,
                parse_num(food.get('edible')),
                parse_num(food.get('water')),
                parse_num(food.get('energyKCal')),
                parse_num(food.get('energyKJ')),
                parse_num(food.get('protein')),
                parse_num(food.get('fat')),
                parse_num(food.get('CHO')),
                parse_num(food.get('dietaryFiber')),
                parse_num(food.get('cholesterol')),
                parse_num(food.get('vitaminA')),
                parse_num(food.get('vitaminC')),
                parse_num(food.get('Ca')),
                parse_num(food.get('Fe')),
                parse_num(food.get('Zn'))
            ))
            imported += 1
        except Exception as e:
            print(f"导入失败: {food.get('foodName', '未知')} - {e}")

    conn.commit()
    conn.close()
    return imported


def search_nutrition(keyword, limit=5):
    """
    搜索营养数据

    Args:
        keyword: 搜索关键词
        limit: 返回数量

    Returns:
        list: 匹配的营养数据
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM nutrition_data
        WHERE food_name LIKE ?
        ORDER BY
            CASE WHEN food_name = ? THEN 0
                 WHEN food_name LIKE ? THEN 1
                 ELSE 2 END,
            food_name
        LIMIT ?
    ''', (f'%{keyword}%', keyword, f'{keyword}%', limit))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_nutrition_by_field(order_by='protein', order='DESC', limit=5, exclude_null=True):
    """
    按营养字段排序查询

    Args:
        order_by: 排序字段 (protein/fat/energy_kcal/fe/ca/vitamin_a/vitamin_c/dietary_fiber/cholesterol/cho)
        order: 排序方向 (ASC/DESC)
        limit: 返回数量
        exclude_null: 是否排除空值

    Returns:
        list: 营养数据列表
    """
    # 允许的排序字段（防止 SQL 注入）
    allowed_fields = {
        'protein', 'fat', 'energy_kcal', 'energy_kj', 'fe', 'ca',
        'vitamin_a', 'vitamin_c', 'dietary_fiber', 'cholesterol', 'cho',
        'water', 'edible'
    }

    if order_by not in allowed_fields:
        raise ValueError(f"不允许的排序字段: {order_by}")

    if order not in ('ASC', 'DESC'):
        raise ValueError(f"排序方向必须是 ASC 或 DESC")

    conn = get_connection()
    cursor = conn.cursor()

    # 构建查询
    where_clause = f"WHERE {order_by} IS NOT NULL" if exclude_null else ""
    sql = f'''
        SELECT food_name, {order_by}, energy_kcal, protein, fat, cho
        FROM nutrition_data
        {where_clause}
        ORDER BY {order_by} {order}
        LIMIT ?
    '''

    cursor.execute(sql, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_inventory_by_category(category):
    """
    按分类获取库存

    Args:
        category: 分类名称

    Returns:
        list: 库存项列表
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM fridge_inventory
        WHERE category = ? AND quantity > 0
        ORDER BY expiry_date
    ''', (category,))

    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        if item.get('expiry_date'):
            try:
                from datetime import datetime
                exp = datetime.strptime(item['expiry_date'], '%Y-%m-%d')
                item['days_left'] = (exp - datetime.now()).days
            except:
                item['days_left'] = None
        items.append(item)

    return items


def get_nutrition_by_name(food_name):
    """
    精确获取营养数据

    Args:
        food_name: 食物名称

    Returns:
        dict: 营养数据或None
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 先精确匹配
    cursor.execute('SELECT * FROM nutrition_data WHERE food_name = ?', (food_name,))
    row = cursor.fetchone()

    if not row:
        # 模糊匹配
        cursor.execute('SELECT * FROM nutrition_data WHERE food_name LIKE ? LIMIT 1', (f'%{food_name}%',))
        row = cursor.fetchone()

    conn.close()
    return dict(row) if row else None


def get_nutrition_summary(food_name):
    """
    获取食物营养摘要（用于Prompt）

    Args:
        food_name: 食物名称

    Returns:
        str: 营养摘要文本
    """
    data = get_nutrition_by_name(food_name)
    if not data:
        return None

    parts = [data['food_name']]
    if data.get('energy_kcal'):
        parts.append(f"{data['energy_kcal']}kcal/100g")
    if data.get('protein'):
        parts.append(f"蛋白质{data['protein']}g")
    if data.get('fat'):
        parts.append(f"脂肪{data['fat']}g")
    if data.get('cho'):
        parts.append(f"碳水{data['cho']}g")

    return "，".join(parts)


def get_nutrition_count():
    """获取营养数据总数"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM nutrition_data')
    count = cursor.fetchone()[0]
    conn.close()
    return count


if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 初始化数据库
    init_db()
    print("数据库初始化完成")

    # 导入营养数据
    nutrition_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'nutrition', 'china_food_composition.json')
    if os.path.exists(nutrition_path):
        count = import_nutrition_data(nutrition_path)
        print(f"营养数据导入完成: {count}条")
        print(f"营养数据总数: {get_nutrition_count()}条")
    else:
        print(f"营养数据文件不存在: {nutrition_path}")

    # 测试搜索
    print("\n搜索'鸡蛋':")
    results = search_nutrition("鸡蛋")
    for r in results:
        print(f"  {r['food_name']}: {r['energy_kcal']}kcal, 蛋白质{r['protein']}g, 脂肪{r['fat']}g")
