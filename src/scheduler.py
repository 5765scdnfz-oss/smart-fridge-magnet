"""
定时任务调度器 — 在用餐前1-2小时自动推荐菜谱
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import threading

from . import database as db
from .agent import generate_recommendation

# 全局调度器
scheduler = BackgroundScheduler()
notification_queue = []  # 通知队列，前端轮询获取
lock = threading.Lock()


def init_scheduler():
    """初始化调度器"""
    # 每10分钟检查一次是否需要推荐
    scheduler.add_job(
        func=check_and_recommend,
        trigger=IntervalTrigger(minutes=10),
        id='recipe_check',
        replace_existing=True
    )
    scheduler.start()
    print("⏰ 定时任务调度器已启动")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        print("⏰ 定时任务调度器已停止")


def check_and_recommend():
    """
    检查是否需要推荐菜谱

    逻辑：
    1. 获取用餐时间配置
    2. 检查当前时间是否在用餐前1-2小时
    3. 如果是，生成推荐并加入通知队列
    """
    schedule = db.get_meal_schedule()
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    for meal in schedule:
        meal_type = meal['meal_type']
        meal_time_str = meal['meal_time']

        try:
            # 解析用餐时间
            meal_hour, meal_minute = map(int, meal_time_str.split(':'))
            meal_total_minutes = meal_hour * 60 + meal_minute
            current_total_minutes = current_hour * 60 + current_minute

            # 计算时间差（分钟）
            diff = meal_total_minutes - current_total_minutes

            # 如果在用餐前60-120分钟之间
            if 60 <= diff <= 120:
                # 检查是否已经推荐过
                if not has_recent_recommendation(meal_type):
                    # 获取家庭成员数量作为默认人数
                    members = db.get_all_members()
                    people_count = len(members) if members else 3

                    # 生成推荐
                    result = generate_recommendation(meal_type, people_count)

                    # 加入通知队列
                    with lock:
                        notification_queue.append({
                            'type': 'recipe_recommendation',
                            'meal_type': meal_type,
                            'message': result.get('reply', ''),
                            'data': result.get('data', {}),
                            'timestamp': now.isoformat(),
                            'read': False
                        })

                    print(f"🔔 已生成{meal_type}推荐")

        except Exception as e:
            print(f"检查{meal_type}时出错：{e}")


def has_recent_recommendation(meal_type):
    """
    检查是否已有最近的推荐（避免重复）

    Returns:
        bool: 是否已有推荐
    """
    plans = db.get_pending_plans()
    today = datetime.now().strftime('%Y-%m-%d')

    for plan in plans:
        if (plan.get('meal_type') == meal_type and
            plan.get('created_at', '').startswith(today)):
            return True

    return False


# ==================== 通知管理 ====================

def get_notifications(unread_only=True):
    """
    获取通知

    Args:
        unread_only: 是否只返回未读通知

    Returns:
        list: 通知列表
    """
    with lock:
        if unread_only:
            return [n for n in notification_queue if not n['read']]
        return notification_queue.copy()


def mark_notification_read(index):
    """
    标记通知为已读

    Args:
        index: 通知索引
    """
    with lock:
        if 0 <= index < len(notification_queue):
            notification_queue[index]['read'] = True


def clear_notifications():
    """清空通知"""
    with lock:
        notification_queue.clear()


# ==================== 手动触发 ====================

def trigger_recommendation(meal_type=None, people_count=None):
    """
    手动触发推荐（用于测试或用户主动请求）

    Args:
        meal_type: 餐次（默认根据当前时间判断）
        people_count: 人数（默认家庭成员数）
    """
    if not meal_type:
        hour = datetime.now().hour
        if hour < 10:
            meal_type = '早餐'
        elif hour < 14:
            meal_type = '午餐'
        else:
            meal_type = '晚餐'

    if not people_count:
        members = db.get_all_members()
        people_count = len(members) if members else 3

    result = generate_recommendation(meal_type, people_count)

    with lock:
        notification_queue.append({
            'type': 'recipe_recommendation',
            'meal_type': meal_type,
            'message': result.get('reply', ''),
            'data': result.get('data', {}),
            'timestamp': datetime.now().isoformat(),
            'read': False
        })

    return result


if __name__ == '__main__':
    print("定时任务调度器模块")
    print("通过 init_scheduler() 启动")
