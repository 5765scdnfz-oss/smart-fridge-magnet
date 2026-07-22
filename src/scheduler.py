"""
定时任务调度器 — 增强版
支持：定时推荐、过期检查、库存提醒、任务管理
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from . import database as db
from .agent import generate_recommendation
from .notification import (
    add_recipe_notification,
    add_expiring_notification,
    add_inventory_low_notification,
    add_system_notification
)


class TaskScheduler:
    """任务调度器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._running = False
        self._task_history: List[Dict] = []

    def start(self):
        """启动调度器"""
        if self._running:
            return

        # 添加定时任务
        self._add_recipe_check_task()
        self._add_expiring_check_task()
        self._add_inventory_check_task()

        self.scheduler.start()
        self._running = True
        print("⏰ 定时任务调度器已启动")

    def stop(self):
        """停止调度器"""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            print("⏰ 定时任务调度器已停止")

    def is_running(self) -> bool:
        """是否运行中"""
        return self._running

    def get_tasks(self) -> List[Dict]:
        """获取所有任务"""
        tasks = []
        for job in self.scheduler.get_jobs():
            tasks.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return tasks

    def get_task_history(self) -> List[Dict]:
        """获取任务执行历史"""
        return self._task_history.copy()

    # ==================== 定时任务配置 ====================

    def _add_recipe_check_task(self):
        """添加菜谱推荐检查任务"""
        self.scheduler.add_job(
            func=self._check_and_recommend,
            trigger=IntervalTrigger(minutes=10),
            id='recipe_check',
            name='菜谱推荐检查',
            replace_existing=True
        )

    def _add_expiring_check_task(self):
        """添加过期检查任务"""
        # 每天早上 8 点检查
        self.scheduler.add_job(
            func=self._check_expiring,
            trigger=CronTrigger(hour=8, minute=0),
            id='expiring_check',
            name='过期食材检查',
            replace_existing=True
        )

    def _add_inventory_check_task(self):
        """添加库存检查任务"""
        # 每天中午 12 点检查
        self.scheduler.add_job(
            func=self._check_inventory,
            trigger=CronTrigger(hour=12, minute=0),
            id='inventory_check',
            name='库存检查',
            replace_existing=True
        )

    # ==================== 任务执行逻辑 ====================

    def _check_and_recommend(self):
        """
        检查是否需要推荐菜谱

        逻辑：
        1. 获取用餐时间配置
        2. 检查当前时间是否在用餐前1-2小时
        3. 如果是，生成推荐并发送通知
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
                    if not self._has_recent_recommendation(meal_type):
                        # 获取家庭成员数量作为默认人数
                        members = db.get_all_members()
                        people_count = len(members) if members else 3

                        # 生成推荐
                        result = generate_recommendation(meal_type, people_count)

                        # 发送通知
                        add_recipe_notification(
                            meal_type=meal_type,
                            message=result.get('reply', ''),
                            data=result.get('data', {})
                        )

                        # 记录历史
                        self._record_task('recipe_check', f'生成{meal_type}推荐', True)

                        print(f"🔔 已生成{meal_type}推荐")

            except Exception as e:
                self._record_task('recipe_check', f'检查{meal_type}', False, str(e))
                print(f"检查{meal_type}时出错：{e}")

    def _check_expiring(self):
        """
        检查即将过期的食材

        逻辑：
        1. 查询3天内过期的食材
        2. 如果有，发送通知
        """
        try:
            expiring = db.get_expiring_items(days=3)

            if expiring:
                add_expiring_notification(expiring)
                self._record_task('expiring_check', f'发现{len(expiring)}种即将过期食材', True)
                print(f"⚠️ 发现 {len(expiring)} 种食材即将过期")
            else:
                self._record_task('expiring_check', '没有即将过期食材', True)

        except Exception as e:
            self._record_task('expiring_check', '检查过期食材', False, str(e))
            print(f"检查过期食材时出错：{e}")

    def _check_inventory(self):
        """
        检查库存情况

        逻辑：
        1. 按分类统计库存
        2. 如果某分类库存不足，发送通知
        """
        try:
            categories = db.get_inventory_categories()

            # 定义最低库存阈值
            thresholds = {
                '蔬菜': 2,
                '水果': 2,
                '肉类': 1,
                '蛋类': 1,
                '乳制品': 1,
                '主食': 1
            }

            for cat, threshold in thresholds.items():
                # 查找该分类的库存数量
                cat_data = next((c for c in categories if c['name'] == cat), None)
                count = cat_data['count'] if cat_data else 0

                if count < threshold:
                    add_inventory_low_notification(cat, count)
                    self._record_task('inventory_check', f'{cat}库存不足({count})', True)
                    print(f"📦 {cat}库存不足：{count}种")

        except Exception as e:
            self._record_task('inventory_check', '检查库存', False, str(e))
            print(f"检查库存时出错：{e}")

    # ==================== 辅助方法 ====================

    def _has_recent_recommendation(self, meal_type: str) -> bool:
        """
        检查是否已有最近的推荐（避免重复）

        Args:
            meal_type: 餐次类型

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

    def _record_task(self, task_id: str, description: str, success: bool, error: str = None):
        """
        记录任务执行历史

        Args:
            task_id: 任务ID
            description: 任务描述
            success: 是否成功
            error: 错误信息
        """
        record = {
            'task_id': task_id,
            'description': description,
            'success': success,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }

        self._task_history.append(record)

        # 只保留最近 100 条记录
        if len(self._task_history) > 100:
            self._task_history = self._task_history[-100:]


# ==================== 全局实例 ====================

task_scheduler = TaskScheduler()


# ==================== 便捷函数 ====================

def init_scheduler():
    """初始化调度器"""
    task_scheduler.start()


def stop_scheduler():
    """停止调度器"""
    task_scheduler.stop()


def is_scheduler_running() -> bool:
    """调度器是否运行中"""
    return task_scheduler.is_running()


def get_scheduler_tasks() -> List[Dict]:
    """获取所有任务"""
    return task_scheduler.get_tasks()


def get_task_history() -> List[Dict]:
    """获取任务历史"""
    return task_scheduler.get_task_history()


def trigger_recommendation(meal_type: str = None, people_count: int = None) -> Dict:
    """
    手动触发推荐

    Args:
        meal_type: 餐次（默认根据当前时间判断）
        people_count: 人数（默认家庭成员数）

    Returns:
        dict: 推荐结果
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

    # 发送通知
    add_recipe_notification(
        meal_type=meal_type,
        message=result.get('reply', ''),
        data=result.get('data', {})
    )

    return result


def trigger_expiring_check() -> Dict:
    """
    手动触发过期检查

    Returns:
        dict: 检查结果
    """
    expiring = db.get_expiring_items(days=3)

    if expiring:
        add_expiring_notification(expiring)

    return {
        'expiring_count': len(expiring),
        'items': expiring
    }


def trigger_inventory_check() -> Dict:
    """
    手动触发库存检查

    Returns:
        dict: 检查结果
    """
    categories = db.get_inventory_categories()
    low_inventory = []

    thresholds = {
        '蔬菜': 2,
        '水果': 2,
        '肉类': 1,
        '蛋类': 1,
        '乳制品': 1,
        '主食': 1
    }

    for cat, threshold in thresholds.items():
        cat_data = next((c for c in categories if c['name'] == cat), None)
        count = cat_data['count'] if cat_data else 0

        if count < threshold:
            low_inventory.append({'category': cat, 'count': count, 'threshold': threshold})
            add_inventory_low_notification(cat, count)

    return {
        'low_inventory_count': len(low_inventory),
        'low_inventory': low_inventory
    }


# ==================== 测试 ====================

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("TaskScheduler Module Test")
    print("=" * 50)

    # 测试启动
    init_scheduler()
    print(f"Running: {is_scheduler_running()}")

    # 测试获取任务
    tasks = get_scheduler_tasks()
    print(f"\nTasks ({len(tasks)}):")
    for task in tasks:
        print(f"  - {task['name']} ({task['id']})")

    # 测试手动触发
    print("\nManual trigger: expiring check")
    result = trigger_expiring_check()
    print(f"  Expiring: {result['expiring_count']} items")

    # 测试任务历史
    history = get_task_history()
    print(f"\nTask history: {len(history)} records")

    # 停止
    stop_scheduler()
    print(f"\nRunning: {is_scheduler_running()}")

    print("\nDone!")
