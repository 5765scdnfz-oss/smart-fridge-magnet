"""
智能冰箱贴 — Flask 主程序
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile

from . import database as db
from .recognition import process_photo
from .agent import chat, confirm_plan, handle_inventory_query
from .intent_parser import parse_query, build_nutrition_query, build_category_query, get_suggestions, is_simple_query, extract_food_name
from .scheduler import (
    init_scheduler, stop_scheduler,
    get_notifications, mark_notification_read, clear_notifications,
    trigger_recommendation
)

app = Flask(__name__)
CORS(app)

# 初始化数据库
db.init_db()


# ==================== API 接口 ====================

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    对话接口 — 支持本地语义理解优先

    请求：
    {
        "message": "用户输入",
        "session_id": "会话ID（可选）"
    }

    响应：
    {
        "response": "回复文本",
        "handled_locally": true/false,
        "intent": {...},
        "results": [...]
    }
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "缺少message参数"}), 400

    message = data['message']
    session_id = data.get('session_id', 'default')

    # 1. 先尝试本地语义理解
    parsed = parse_query(message)

    if is_simple_query(message):
        # 简单查询，本地处理
        response = {
            "handled_locally": True,
            "intent": parsed,
            "response": "",
            "results": []
        }

        if parsed["type"] == "nutrition":
            try:
                nutrition_query = build_nutrition_query(parsed["intent"])
                results = db.get_nutrition_by_field(
                    order_by=nutrition_query["order_by"],
                    order=nutrition_query["order"],
                    limit=nutrition_query["limit"]
                )
                response["results"] = results
                label = parsed["intent"].get("label", "相关")
                response["response"] = f"找到 {len(results)} 个{label}食物：\n"
                for i, r in enumerate(results, 1):
                    response["response"] += f"{i}. {r['food_name']}: {r.get(parsed['intent']['field'], '?')}g\n"
            except Exception as e:
                response["response"] = f"查询出错: {str(e)}"

        elif parsed["type"] == "category":
            category = parsed["intent"].get("category", "")
            results = db.get_inventory_by_category(category)
            response["results"] = results
            if results:
                response["response"] = f"找到 {len(results)} 个{category}类食材：\n"
                for r in results:
                    response["response"] += f"- {r['name']} × {r['quantity']}{r['unit']}\n"
            else:
                response["response"] = f"库存中没有{category}类食材"

        elif parsed["type"] == "inventory":
            if parsed["intent"].get("filter") == "expiring_soon":
                results = db.get_expiring_items(days=3)
                response["results"] = results
                if results:
                    response["response"] = f"有 {len(results)} 个食材即将过期：\n"
                    for r in results:
                        days = r.get('days_left', '?')
                        response["response"] += f"- {r['name']}: {days}天后过期\n"
                else:
                    response["response"] = "没有即将过期的食材"

        elif parsed["type"] == "action" and parsed["intent"].get("action") == "query":
            food_name = extract_food_name(message)
            if food_name:
                inventory = db.get_inventory(page_size=1000)["items"]
                matched = [i for i in inventory if food_name in i.get("name", "")]
                if matched:
                    response["results"] = matched
                    response["response"] = f"库存中有 {food_name}：\n"
                    for r in matched:
                        response["response"] += f"- {r['name']} × {r['quantity']}{r['unit']}\n"
                else:
                    response["response"] = f"库存中没有找到 {food_name}"

        return jsonify(response)

    # 2. 复杂查询，调用 AI
    result = chat(message, session_id)
    result["handled_locally"] = False
    return jsonify(result)


@app.route('/api/recognize', methods=['POST'])
def api_recognize():
    """
    拍照识别接口

    请求：multipart/form-data
    - image: 图片文件（必需）
    - auto_save: 是否自动保存（可选，默认true）

    响应：
    {
        "success": true,
        "items": [...],
        "duplicates": [...],
        "new_items": [...],
        "message": "识别结果消息",
        "quality_info": {...},
        "need_confirm": false
    }
    """
    if 'image' not in request.files:
        return jsonify({"error": "请上传图片"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    # 获取参数
    auto_save = request.form.get('auto_save', 'true').lower() == 'true'

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # 处理照片
        result = process_photo(tmp_path, auto_save=auto_save)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": f"识别失败：{str(e)}"
        }), 500
    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except:
            pass


@app.route('/api/recognize/confirm', methods=['POST'])
def api_recognize_confirm():
    """
    确认识别结果（用户修改后提交）

    请求：
    {
        "items": [
            {
                "name": "鸡蛋",
                "category": "蛋类",
                "quantity": 6,
                "unit": "个",
                "expiry_date": "2026-08-20",
                "confidence": "高",
                "id": null  // 如果是更新已有项，传id
            }
        ],
        "photo_path": "/tmp/xxx.jpg"  // 可选
    }
    """
    from .recognition import confirm_and_save

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({"error": "缺少items数组"}), 400

    try:
        result = confirm_and_save(
            items=data['items'],
            photo_path=data.get('photo_path')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/recognize/check', methods=['POST'])
def api_recognize_check():
    """
    仅检查图片质量（不识别）

    请求：multipart/form-data
    - image: 图片文件
    """
    from .image_processor import check_image_quality

    if 'image' not in request.files:
        return jsonify({"error": "请上传图片"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = check_image_quality(tmp_path)
        return jsonify(result)
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


@app.route('/api/inventory', methods=['GET'])
def api_inventory():
    """
    查看库存接口

    查询参数：
    - format: "summary" 返回摘要文本，"full" 返回完整数据（默认full）
    - category: 按分类筛选（可选）
    - page: 页码（默认1）
    - page_size: 每页数量（默认50，最大200）
    """
    fmt = request.args.get('format', 'full')
    category = request.args.get('category')
    page = int(request.args.get('page', 1))
    page_size = min(int(request.args.get('page_size', 50)), 200)

    if fmt == 'summary':
        summary = db.get_inventory_summary()
        return jsonify({"summary": summary})
    else:
        result = db.get_inventory(category=category, page=page, page_size=page_size)
        result['expiring_soon'] = [
            i for i in result['items']
            if i.get('days_left') is not None and i['days_left'] <= 3
        ]
        return jsonify(result)


@app.route('/api/inventory', methods=['POST'])
def api_inventory_add():
    """
    添加库存项

    请求：
    {
        "name": "鸡蛋",
        "category": "蛋类",         // 必须在预设分类中
        "quantity": 10,
        "unit": "个",
        "production_date": "2026-07-20",  // 可选，格式 YYYY-MM-DD
        "expiry_date": "2026-08-20",      // 可选，格式 YYYY-MM-DD
        "confidence": "高"                // 可选，默认"高"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求数据"}), 400

    # 必填字段校验
    required = ['name', 'category', 'quantity']
    for field in required:
        if field not in data:
            return jsonify({"error": f"缺少必填字段: {field}"}), 400

    try:
        item_id = db.add_inventory_item(
            name=data['name'],
            category=data['category'],
            quantity=float(data['quantity']),
            unit=data.get('unit', '个'),
            production_date=data.get('production_date'),
            expiry_date=data.get('expiry_date'),
            confidence=data.get('confidence', '高'),
            photo_path=data.get('photo_path')
        )
        return jsonify({
            "success": True,
            "item_id": item_id,
            "message": f"已添加: {data['name']} × {data['quantity']}{data.get('unit', '个')}"
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/inventory/batch', methods=['POST'])
def api_inventory_batch_add():
    """
    批量添加库存项（原子操作，任一失败则全部回滚）

    请求：
    {
        "items": [
            {"name": "鸡蛋", "category": "蛋类", "quantity": 10},
            {"name": "牛奶", "category": "乳制品", "quantity": 2, "unit": "盒"}
        ]
    }
    """
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({"error": "缺少items数组"}), 400

    try:
        result = db.batch_add_inventory_items(data['items'])
        success_count = len(result['success'])
        failed_count = len(result['failed'])

        if failed_count > 0:
            return jsonify({
                "success": False,
                "message": f"批量添加部分失败：{success_count}成功，{failed_count}失败",
                "total": len(data['items']),
                "added": success_count,
                "failed": failed_count,
                "results": result
            }), 400
        else:
            return jsonify({
                "success": True,
                "message": f"批量添加成功：{success_count}项",
                "total": len(data['items']),
                "added": success_count,
                "results": result
            }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def api_inventory_update(item_id):
    """
    更新库存项（支持乐观锁）

    请求（所有字段可选）：
    {
        "name": "土鸡蛋",
        "quantity": 8,
        "expiry_date": "2026-08-25",
        "version": 1             // 可选，乐观锁版本号
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求数据"}), 400

    try:
        version = data.pop('version', None)
        db.update_inventory_item(item_id, version=version, **data)
        return jsonify({"success": True, "message": f"已更新库存项 #{item_id}"})
    except ValueError as e:
        error_msg = str(e)
        if "版本冲突" in error_msg:
            return jsonify({"error": error_msg, "code": "VERSION_CONFLICT"}), 409
        elif "不存在" in error_msg:
            return jsonify({"error": error_msg}), 404
        else:
            return jsonify({"error": error_msg}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def api_inventory_delete(item_id):
    """
    删除库存项（软删除，设为quantity=0）
    """
    try:
        db.delete_inventory_item(item_id)
        return jsonify({"success": True, "message": f"已删除库存项 #{item_id}"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/inventory/deduct', methods=['POST'])
def api_inventory_deduct():
    """
    扣减库存（FIFO先进先出，事务保护）

    请求：
    {
        "items": [
            {"name": "鸡蛋", "quantity": 2},
            {"name": "牛奶", "quantity": 1}
        ]
    }
    """
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({"error": "缺少items数组"}), 400

    try:
        results = db.deduct_inventory(data['items'])
        return jsonify({
            "success": True,
            "message": "扣减成功",
            "results": results
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/inventory/expiring', methods=['GET'])
def api_inventory_expiring():
    """
    获取即将过期的食材

    查询参数：
    - days: 天数（默认3天）
    """
    days = int(request.args.get('days', 3))
    items = db.get_expiring_items(days=days)
    return jsonify({
        "items": items,
        "count": len(items),
        "days": days
    })


@app.route('/api/inventory/categories', methods=['GET'])
def api_inventory_categories():
    """
    获取分类列表

    查询参数：
    - type: "preset" 返回预设分类，"used" 返回实际使用的分类（默认preset）
    """
    category_type = request.args.get('type', 'preset')

    if category_type == 'used':
        categories = db.get_inventory_categories()
    else:
        categories = db.get_preset_categories()

    return jsonify({
        "categories": categories,
        "count": len(categories)
    })


# ==================== 智能查询接口 ====================

@app.route('/api/smart/query', methods=['POST'])
def api_smart_query():
    """
    智能查询接口 — 本地语义理解，减少 AI 调用

    请求：
    {
        "query": "蛋白质高的食物"
    }

    返回：
    {
        "type": "nutrition",
        "intent": {"field": "protein", "order": "DESC", "label": "高蛋白"},
        "keywords": ["蛋白质"],
        "confidence": "high",
        "results": [...],
        "suggestions": [...],
        "handled_locally": true
    }
    """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "缺少query参数"}), 400

    query = data['query']

    # 本地语义解析
    parsed = parse_query(query)

    response = {
        "type": parsed["type"],
        "intent": parsed["intent"],
        "keywords": parsed["keywords"],
        "confidence": parsed["confidence"],
        "original": parsed["original"],
        "handled_locally": False,
        "results": [],
        "suggestions": []
    }

    # 根据意图类型处理
    if parsed["type"] == "nutrition":
        # 营养查询：按字段排序
        try:
            nutrition_query = build_nutrition_query(parsed["intent"])
            results = db.get_nutrition_by_field(
                order_by=nutrition_query["order_by"],
                order=nutrition_query["order"],
                limit=nutrition_query["limit"]
            )
            response["results"] = results
            response["handled_locally"] = True
            response["message"] = f"找到 {len(results)} 个{parsed['intent'].get('label', '')}食物"
        except Exception as e:
            response["error"] = str(e)

    elif parsed["type"] == "category":
        # 分类查询
        category_query = build_category_query(parsed["intent"])
        results = db.get_inventory_by_category(category_query["category"])
        response["results"] = results
        response["handled_locally"] = True
        response["message"] = f"找到 {len(results)} 个{category_query['category']}类食材"

    elif parsed["type"] == "inventory":
        # 库存查询
        if parsed["intent"].get("filter") == "expiring_soon":
            results = db.get_expiring_items(days=3)
            response["results"] = results
            response["handled_locally"] = True
            response["message"] = f"找到 {len(results)} 个即将过期的食材"
        elif parsed["intent"].get("sort") == "quantity":
            order = parsed["intent"].get("order", "ASC")
            all_items = db.get_inventory(page_size=1000)["items"]
            all_items.sort(key=lambda x: x.get("quantity", 0), reverse=(order == "DESC"))
            response["results"] = all_items[:10]
            response["handled_locally"] = True

    elif parsed["type"] == "action":
        action = parsed["intent"].get("action", "")
        if action == "query":
            # 查询类动作，提取食材名
            food_name = extract_food_name(query)
            if food_name:
                # 先查库存
                inventory = db.get_inventory(page_size=1000)["items"]
                matched = [i for i in inventory if food_name in i.get("name", "")]
                if matched:
                    response["results"] = matched
                    response["handled_locally"] = True
                    response["message"] = f"找到 {len(matched)} 个匹配的库存项"
                else:
                    # 查营养数据
                    nutrition = db.search_nutrition(food_name, limit=5)
                    if nutrition:
                        response["results"] = nutrition
                        response["handled_locally"] = True
                        response["message"] = f"找到 {len(nutrition)} 个匹配的食物"

    # 生成建议
    inventory = db.get_inventory(page_size=1000)["items"] if parsed["type"] in ["action", "scene"] else None
    response["suggestions"] = get_suggestions(query, inventory)

    return jsonify(response)


@app.route('/api/smart/nutrition', methods=['GET'])
def api_smart_nutrition():
    """
    营养排序查询

    查询参数：
    - field: 排序字段 (protein/fat/energy_kcal/fe/ca/vitamin_a/vitamin_c)
    - order: 排序方向 (ASC/DESC，默认DESC)
    - limit: 返回数量（默认5）
    """
    field = request.args.get('field', 'protein')
    order = request.args.get('order', 'DESC').upper()
    limit = int(request.args.get('limit', 5))

    try:
        results = db.get_nutrition_by_field(order_by=field, order=order, limit=limit)
        return jsonify({
            "field": field,
            "order": order,
            "results": results,
            "count": len(results)
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/smart/parse', methods=['POST'])
def api_smart_parse():
    """
    仅解析意图（不执行查询）

    请求：
    {
        "query": "蛋白质高的食物"
    }

    返回：
    {
        "type": "nutrition",
        "intent": {...},
        "keywords": [...],
        "confidence": "high",
        "is_simple": true
    }
    """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "缺少query参数"}), 400

    query = data['query']
    parsed = parse_query(query)
    parsed["is_simple"] = is_simple_query(query)

    return jsonify(parsed)


@app.route('/api/profile', methods=['GET'])
def api_profile_get():
    """查看家庭画像"""
    members = db.get_all_members()
    schedule = db.get_meal_schedule()

    return jsonify({
        "members": members,
        "meal_schedule": schedule,
        "summary": db.get_profile_summary()
    })


@app.route('/api/profile', methods=['POST'])
def api_profile_update():
    """
    更新家庭画像

    请求：
    {
        "message": "描述家庭信息的自然语言"
    }
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "缺少message参数"}), 400

    result = chat(data['message'], session_id='profile')
    return jsonify(result)


@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    """
    请求菜谱推荐

    请求：
    {
        "meal_type": "晚餐（可选）",
        "people_count": 3（可选）
    }
    """
    data = request.get_json() or {}

    meal_type = data.get('meal_type')
    people_count = data.get('people_count')

    # 如果没有指定，通过对话处理
    if not meal_type:
        message = "该做饭了"
    else:
        message = f"推荐{meal_type}"
        if people_count:
            message += f"，{people_count}人"

    result = chat(message)
    return jsonify(result)


@app.route('/api/confirm', methods=['POST'])
def api_confirm():
    """
    确认菜谱方案

    请求：
    {
        "plan_id": 1,
        "selected_plan": "A"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少参数"}), 400

    plan_id = data.get('plan_id')
    selected_plan = data.get('selected_plan')

    if not plan_id or not selected_plan:
        return jsonify({"error": "缺少plan_id或selected_plan"}), 400

    result = confirm_plan(plan_id, selected_plan)
    return jsonify(result)


# ==================== 通知接口 ====================

@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    """获取通知"""
    unread_only = request.args.get('unread_only', 'true').lower() == 'true'
    notifications = get_notifications(unread_only)
    return jsonify({
        "notifications": notifications,
        "count": len(notifications)
    })


@app.route('/api/notifications/read', methods=['POST'])
def api_notification_read():
    """标记通知为已读"""
    data = request.get_json()
    index = data.get('index', 0)
    mark_notification_read(index)
    return jsonify({"success": True})


@app.route('/api/notifications/clear', methods=['POST'])
def api_notification_clear():
    """清空通知"""
    clear_notifications()
    return jsonify({"success": True})


# ==================== 定时任务接口 ====================

@app.route('/api/scheduler/trigger', methods=['POST'])
def api_trigger_recommendation():
    """手动触发推荐（测试用）"""
    data = request.get_json() or {}
    meal_type = data.get('meal_type')
    people_count = data.get('people_count')

    result = trigger_recommendation(meal_type, people_count)
    return jsonify(result)


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "smart-fridge-magnet",
        "version": "1.0.0"
    })


# ==================== 启动 ====================

def start_app(host='0.0.0.0', port=5000, debug=True):
    """启动应用"""
    # 初始化数据库
    db.init_db()

    # 启动定时任务
    init_scheduler()

    print(f"🧊 智能冰箱贴服务启动")
    print(f"📡 地址: http://{host}:{port}")
    print(f"📋 API: http://{host}:{port}/api/health")

    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        stop_scheduler()


if __name__ == '__main__':
    start_app()
