"""
API 测试脚本
"""
import requests
import json

BASE_URL = 'http://localhost:5000/api'


def test_health():
    """测试健康检查"""
    print("=== 测试健康检查 ===")
    resp = requests.get(f'{BASE_URL}/health')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_chat():
    """测试对话"""
    print("=== 测试对话 ===")
    resp = requests.post(f'{BASE_URL}/chat', json={
        "message": "我家3口人，爸爸不吃辣，孩子不吃苦瓜",
        "session_id": "test"
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_profile():
    """测试画像查询"""
    print("=== 测试画像查询 ===")
    resp = requests.get(f'{BASE_URL}/profile')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
    print()


def test_inventory():
    """测试库存查询"""
    print("=== 测试库存查询 ===")
    resp = requests.get(f'{BASE_URL}/inventory')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
    print()


def test_inventory_summary():
    """测试库存摘要"""
    print("=== 测试库存摘要 ===")
    resp = requests.get(f'{BASE_URL}/inventory?format=summary')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_recommend():
    """测试菜谱推荐"""
    print("=== 测试菜谱推荐 ===")
    resp = requests.post(f'{BASE_URL}/recommend', json={
        "meal_type": "晚餐",
        "people_count": 3
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_chat_recommend():
    """测试通过对话推荐菜谱"""
    print("=== 测试对话推荐菜谱 ===")
    resp = requests.post(f'{BASE_URL}/chat', json={
        "message": "该做晚饭了，3个人吃",
        "session_id": "test"
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_notifications():
    """测试通知"""
    print("=== 测试通知 ===")
    resp = requests.get(f'{BASE_URL}/notifications')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_inventory_add():
    """测试添加库存项"""
    print("=== 测试添加库存项 ===")
    resp = requests.post(f'{BASE_URL}/inventory', json={
        "name": "测试鸡蛋",
        "category": "蛋类",
        "quantity": 10,
        "unit": "个",
        "expiry_date": "2026-08-20"
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()
    return resp.json().get('item_id')


def test_inventory_batch_add():
    """测试批量添加库存项"""
    print("=== 测试批量添加库存项 ===")
    resp = requests.post(f'{BASE_URL}/inventory/batch', json={
        "items": [
            {"name": "测试牛奶", "category": "乳制品", "quantity": 2, "unit": "盒"},
            {"name": "测试面包", "category": "主食", "quantity": 1, "unit": "袋"}
        ]
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
    print()


def test_inventory_update(item_id):
    """测试更新库存项"""
    print("=== 测试更新库存项 ===")
    resp = requests.put(f'{BASE_URL}/inventory/{item_id}', json={
        "quantity": 8,
        "expiry_date": "2026-08-25"
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_inventory_delete(item_id):
    """测试删除库存项"""
    print("=== 测试删除库存项 ===")
    resp = requests.delete(f'{BASE_URL}/inventory/{item_id}')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_inventory_deduct():
    """测试扣减库存"""
    print("=== 测试扣减库存 ===")
    resp = requests.post(f'{BASE_URL}/inventory/deduct', json={
        "items": [
            {"name": "测试牛奶", "quantity": 1}
        ]
    })
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
    print()


def test_inventory_expiring():
    """测试即将过期查询"""
    print("=== 测试即将过期查询 ===")
    resp = requests.get(f'{BASE_URL}/inventory/expiring?days=30')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
    print()


def test_inventory_categories():
    """测试获取分类列表"""
    print("=== 测试获取分类列表 ===")
    resp = requests.get(f'{BASE_URL}/inventory/categories')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    print()


def test_inventory_filter_by_category():
    """测试按分类筛选"""
    print("=== 测试按分类筛选 ===")
    resp = requests.get(f'{BASE_URL}/inventory?category=乳制品')
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
    print()


def run_all_tests():
    """运行所有测试"""
    print("🧪 开始测试...\n")

    try:
        test_health()
        test_chat()
        test_profile()
        test_inventory()
        test_inventory_summary()
        test_recommend()
        test_chat_recommend()
        test_notifications()

        # 库存管理测试
        print("\n📦 库存管理测试...\n")
        item_id = test_inventory_add()
        test_inventory_batch_add()
        test_inventory_update(item_id)
        test_inventory_categories()
        test_inventory_filter_by_category()
        test_inventory_expiring()
        test_inventory_deduct()
        test_inventory_delete(item_id)

        print("✅ 所有测试完成")

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保服务已启动")
        print("   运行: python -m src.app")
    except Exception as e:
        print(f"❌ 测试出错: {e}")


if __name__ == '__main__':
    run_all_tests()
