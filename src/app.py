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
    对话接口

    请求：
    {
        "message": "用户输入",
        "session_id": "会话ID（可选）"
    }
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "缺少message参数"}), 400

    message = data['message']
    session_id = data.get('session_id', 'default')

    result = chat(message, session_id)
    return jsonify(result)


@app.route('/api/recognize', methods=['POST'])
def api_recognize():
    """
    拍照识别接口

    请求：multipart/form-data，包含图片文件（字段名：image）
    """
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
        # 处理照片
        result = process_photo(tmp_path)
        return jsonify(result)
    finally:
        # 清理临时文件
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
    """
    fmt = request.args.get('format', 'full')

    if fmt == 'summary':
        summary = db.get_inventory_summary()
        return jsonify({"summary": summary})
    else:
        items = db.get_inventory()
        return jsonify({
            "items": items,
            "total": len(items),
            "expiring_soon": [i for i in items if i.get('days_left') is not None and i['days_left'] <= 3]
        })


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
