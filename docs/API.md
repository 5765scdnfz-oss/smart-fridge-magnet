# 智能冰箱贴 API 文档

## 基础信息

- 基础URL: `http://localhost:5000/api`
- 请求格式: JSON
- 响应格式: JSON
- 字符编码: UTF-8

---

## 目录

1. [对话接口](#对话接口)
2. [拍照识别](#拍照识别)
3. [库存管理](#库存管理)
4. [智能查询](#智能查询)
5. [家庭画像](#家庭画像)
6. [菜谱推荐](#菜谱推荐)
7. [通知系统](#通知系统)
8. [定时任务](#定时任务)
9. [库存历史](#库存历史)
10. [健康检查](#健康检查)

---

## 对话接口

### POST /chat

智能对话接口，支持本地语义理解优先。

**请求:**
```json
{
    "message": "用户输入",
    "session_id": "会话ID（可选）"
}
```

**响应:**
```json
{
    "handled_locally": true,
    "intent": {...},
    "response": "回复文本",
    "results": [...]
}
```

**示例:**
```bash
# 营养查询（本地处理）
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "蛋白质高的食物"}'

# 菜谱推荐（调用AI）
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "推荐晚餐，3个人吃"}'
```

---

## 拍照识别

### POST /recognize

拍照识别食材。

**请求:**
```
Content-Type: multipart/form-data

image: 文件（必需）
auto_save: true/false（可选，默认true）
```

**响应:**
```json
{
    "success": true,
    "items": [...],
    "duplicates": [...],
    "new_items": [...],
    "message": "识别结果消息",
    "quality_info": {...},
    "need_confirm": false
}
```

**示例:**
```bash
# 自动保存
curl -X POST http://localhost:5000/api/recognize \
  -F "image=@photo.jpg"

# 需要确认
curl -X POST http://localhost:5000/api/recognize \
  -F "image=@photo.jpg" \
  -F "auto_save=false"
```

### POST /recognize/confirm

确认识别结果。

**请求:**
```json
{
    "items": [
        {
            "name": "鸡蛋",
            "category": "蛋类",
            "quantity": 6,
            "unit": "个",
            "expiry_date": "2026-08-20"
        }
    ],
    "photo_path": "/tmp/xxx.jpg"
}
```

### POST /recognize/check

仅检查图片质量。

**请求:**
```
Content-Type: multipart/form-data

image: 文件
```

**响应:**
```json
{
    "valid": true,
    "errors": [],
    "warnings": [],
    "info": {
        "file_size_mb": 2.5,
        "width": 1920,
        "height": 1080,
        "brightness": 128.5,
        "is_blurry": false
    }
}
```

---

## 库存管理

### GET /inventory

获取库存列表。

**查询参数:**
- `format`: "summary" 或 "full"（默认full）
- `category`: 按分类筛选
- `page`: 页码（默认1）
- `page_size`: 每页数量（默认50，最大200）

**响应:**
```json
{
    "items": [...],
    "total": 45,
    "page": 1,
    "page_size": 50,
    "total_pages": 1,
    "expiring_soon": [...]
}
```

### POST /inventory

添加库存项。

**请求:**
```json
{
    "name": "鸡蛋",
    "category": "蛋类",
    "quantity": 10,
    "unit": "个",
    "production_date": "2026-07-20",
    "expiry_date": "2026-08-20"
}
```

**分类枚举:**
蔬菜/水果/肉类/海鲜/蛋类/乳制品/豆制品/主食/调味品/饮料/零食/冷冻食品/其他

### POST /inventory/batch

批量添加库存项。

**请求:**
```json
{
    "items": [
        {"name": "鸡蛋", "category": "蛋类", "quantity": 10},
        {"name": "牛奶", "category": "乳制品", "quantity": 2}
    ]
}
```

### PUT /inventory/:id

更新库存项（支持乐观锁）。

**请求:**
```json
{
    "quantity": 8,
    "expiry_date": "2026-08-25",
    "version": 1
}
```

### DELETE /inventory/:id

删除库存项（软删除）。

### POST /inventory/deduct

扣减库存（FIFO先进先出）。

**请求:**
```json
{
    "items": [
        {"name": "鸡蛋", "quantity": 2},
        {"name": "牛奶", "quantity": 1}
    ]
}
```

### GET /inventory/expiring

获取即将过期的食材。

**查询参数:**
- `days`: 天数（默认3）

### GET /inventory/categories

获取分类列表。

**查询参数:**
- `type`: "preset" 或 "used"（默认preset）

---

## 智能查询

### POST /smart/query

智能查询接口。

**请求:**
```json
{
    "query": "蛋白质高的食物"
}
```

**响应:**
```json
{
    "type": "nutrition",
    "intent": {"field": "protein", "order": "DESC", "label": "高蛋白"},
    "keywords": ["蛋白质"],
    "confidence": "high",
    "handled_locally": true,
    "results": [...],
    "suggestions": [...]
}
```

### GET /smart/nutrition

营养排序查询。

**查询参数:**
- `field`: 排序字段（protein/fat/energy_kcal/fe/ca/vitamin_a/vitamin_c）
- `order`: 排序方向（ASC/DESC，默认DESC）
- `limit`: 返回数量（默认5）

### POST /smart/parse

仅解析意图。

---

## 家庭画像

### GET /profile

获取家庭画像。

**响应:**
```json
{
    "members": [...],
    "meal_schedule": [...],
    "summary": "画像摘要"
}
```

### POST /profile

更新家庭画像。

**请求:**
```json
{
    "message": "家里3口人，爸爸不吃辣，孩子不吃苦瓜"
}
```

---

## 菜谱推荐

### POST /recommend

请求菜谱推荐。

**请求:**
```json
{
    "meal_type": "晚餐",
    "people_count": 3
}
```

### POST /confirm

确认菜谱方案。

**请求:**
```json
{
    "plan_id": 1,
    "selected_plan": "A"
}
```

---

## 通知系统

### GET /notifications

获取通知。

**查询参数:**
- `unread_only`: true/false（默认true）
- `type`: 按类型筛选（recipe/expiring/inventory_low/system）

### POST /notifications/:id/read

标记通知为已读。

### POST /notifications/read-all

标记所有通知为已读。

### POST /notifications/clear

清空通知。

**请求:**
```json
{
    "type": "recipe"  // 可选
}
```

### GET /notifications/stats

获取通知统计。

---

## 定时任务

### GET /scheduler/status

获取调度器状态。

### GET /scheduler/tasks

获取所有任务。

### GET /scheduler/history

获取执行历史。

### POST /scheduler/trigger/recommend

手动触发推荐。

**请求:**
```json
{
    "meal_type": "晚餐",
    "people_count": 3
}
```

### POST /scheduler/trigger/expiring

手动触发过期检查。

### POST /scheduler/trigger/inventory

手动触发库存检查。

---

## 库存历史

### GET /inventory/history

获取历史记录。

**查询参数:**
- `item_id`: 按库存项筛选
- `action`: 按动作筛选（add/deduct/update/delete）
- `days`: 查询最近N天（默认7）
- `limit`: 返回数量（默认100）

### GET /inventory/history/:id

获取特定库存项的历史。

### GET /inventory/history/statistics

获取统计信息。

**响应:**
```json
{
    "days": 7,
    "total_records": 50,
    "by_action": {
        "add": {"count": 20, "total_quantity": 100},
        "deduct": {"count": 30, "total_quantity": 50}
    },
    "by_source": {"manual": 30, "recipe": 20},
    "top_deducted": [...],
    "top_added": [...]
}
```

### GET /inventory/history/daily

获取每日摘要。

---

## 健康检查

### GET /health

健康检查。

**查询参数:**
- `full`: true/false（默认false，只做快速检查）

**响应（快速）:**
```json
{
    "timestamp": "2026-07-22T10:30:00",
    "overall_status": "ok",
    "checks": {
        "database": {"status": "ok", ...},
        "scheduler": {"status": "ok", ...},
        "inventory": {"status": "ok", ...}
    },
    "duration_ms": 50
}
```

**响应（完整）:**
```json
{
    "timestamp": "2026-07-22T10:30:00",
    "overall_status": "ok",
    "checks": {
        "database": {...},
        "api": {...},
        "scheduler": {...},
        "inventory": {...},
        "profile": {...},
        "nutrition": {...}
    },
    "system": {
        "platform": "Windows-10",
        "python_version": "3.13.0",
        "cpu_percent": 25.0,
        "memory_percent": 60.0
    },
    "duration_ms": 1500
}
```

### GET /health/database

数据库检查。

### GET /health/api

API检查（MiMo连通性）。

### GET /health/scheduler

定时任务检查。

### GET /health/inventory

库存检查。

### GET /health/profile

画像检查。

### GET /health/nutrition

营养数据检查。

---

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 版本冲突 |
| 500 | 服务器内部错误 |

**错误响应格式:**
```json
{
    "error": "错误描述",
    "code": "ERROR_CODE"  // 可选
}
```

---

## 使用示例

### 完整工作流

```bash
# 1. 添加家庭成员
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "家里3口人，爸爸不吃辣"}'

# 2. 拍照识别
curl -X POST http://localhost:5000/api/recognize \
  -F "image=@fridge.jpg"

# 3. 查看库存
curl http://localhost:5000/api/inventory

# 4. 推荐菜谱
curl -X POST http://localhost:5000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"meal_type": "晚餐", "people_count": 3}'

# 5. 确认方案
curl -X POST http://localhost:5000/api/confirm \
  -H "Content-Type: application/json" \
  -d '{"plan_id": 1, "selected_plan": "A"}'

# 6. 查看通知
curl http://localhost:5000/api/notifications

# 7. 健康检查
curl http://localhost:5000/api/health?full=true
```
