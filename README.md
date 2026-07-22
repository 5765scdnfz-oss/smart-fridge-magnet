# 🧊 智能冰箱贴

> 黑客松项目 — AI 驱动的家庭食材管理助手

**Demo截止**: 2026-07-30
**展示时间**: 2026-08-01 ~ 08-02

---

## ✨ 核心功能

### 📸 拍照识别
- 拍照自动识别食材（MiMo v2.5 视觉模型）
- 支持识别：蔬菜/水果/肉类/海鲜/蛋类/乳制品等
- 自动提取：名称、数量、保质期、分类
- 图片质量检查：模糊检测、亮度检测、自动压缩

### 🧠 智能理解
- 本地语义理解：60-70% 查询无需调用 AI
- 支持：营养查询、分类筛选、库存查询
- 意图识别：20+ 关键词映射

### 👨‍👩‍👧 家庭画像
- 记录家庭成员信息
- 忌口分层：主材料/配料/口味
- 健康备注：减肥/糖尿病/怀孕/健身等
- 自动避忌推荐

### 🍽️ 菜谱推荐
- 基于库存推荐 A/B 方案
- 优先使用快过期食材
- 营养均衡考虑
- 选方案自动扣减库存

### ⏰ 定时提醒
- 用餐前 1-2 小时自动推荐
- 过期食材提醒
- 库存不足提醒

### 📊 数据管理
- 库存历史记录
- 扣减追溯
- 统计分析

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端（未来）                         │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Flask API 服务                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ 对话    │ │ 识别    │ │ 库存    │ │ 推荐    │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  MiMo v2.5   │   │    SQLite     │   │  定时任务     │
│  (视觉/文本)  │   │   (数据库)    │   │  (APScheduler)│
└───────────────┘   └───────────────┘   └───────────────┘
```

### 模块化设计

```
src/
├── app.py               # Flask 主程序
├── database.py          # 数据库操作
├── agent.py             # 对话代理
├── recognition.py       # 拍照识别
├── intent_parser.py     # 语义理解
├── image_processor.py   # 图片处理
├── notification.py      # 通知系统
├── scheduler.py         # 定时任务
├── inventory_history.py # 库存历史
├── health.py            # 健康检查
├── mimo_client.py       # MiMo API
└── prompts.py           # Prompt 模板
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 MIMO_API_KEY
```

### 3. 启动服务

```bash
python -m src.app
```

### 4. 运行演示

```bash
python scripts/demo.py
```

### 5. 运行测试

```bash
# 端到端测试
python tests/test_e2e.py

# API 测试
python tests/test_api.py
```

---

## 📡 API 接口

| 模块 | 接口 | 功能 |
|------|------|------|
| 对话 | POST /chat | 智能对话 |
| 识别 | POST /recognize | 拍照识别 |
| 识别 | POST /recognize/confirm | 确认识别 |
| 库存 | GET/POST /inventory | 库存管理 |
| 库存 | POST /inventory/batch | 批量添加 |
| 库存 | POST /inventory/deduct | 扣减库存 |
| 查询 | POST /smart/query | 智能查询 |
| 画像 | GET/POST /profile | 家庭画像 |
| 推荐 | POST /recommend | 菜谱推荐 |
| 推荐 | POST /confirm | 确认方案 |
| 通知 | GET /notifications | 获取通知 |
| 任务 | GET /scheduler/status | 任务状态 |
| 历史 | GET /inventory/history | 库存历史 |
| 健康 | GET /health | 健康检查 |

完整文档：[docs/API.md](docs/API.md)

---

## 📁 项目结构

```
smart-fridge-magnet/
├── src/                    # 源代码
│   ├── __init__.py
│   ├── app.py
│   ├── database.py
│   ├── agent.py
│   ├── recognition.py
│   ├── intent_parser.py
│   ├── image_processor.py
│   ├── notification.py
│   ├── scheduler.py
│   ├── inventory_history.py
│   ├── health.py
│   ├── mimo_client.py
│   └── prompts.py
├── tests/                  # 测试
│   ├── test_api.py
│   └── test_e2e.py
├── scripts/                # 脚本
│   └── demo.py
├── docs/                   # 文档
│   └── API.md
├── data/                   # 数据
│   └── nutrition/
│       └── china_food_composition.json
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.13 | 主语言 |
| Flask | Web 框架 |
| SQLite | 数据库 |
| MiMo v2.5 | 视觉识别 |
| MiMo v2.5-pro | 文本推理 |
| APScheduler | 定时任务 |
| Pillow | 图片处理 |

---

## 📊 数据库表

| 表名 | 用途 |
|------|------|
| fridge_inventory | 冰箱库存 |
| family_profile | 家庭画像 |
| meal_plan | 用餐计划 |
| meal_schedule | 用餐时间 |
| conversation_history | 对话历史 |
| nutrition_data | 营养数据 |
| inventory_categories | 预设分类 |
| inventory_history | 库存历史 |

---

## 🎯 演示流程

1. **健康检查** — 展示系统状态
2. **家庭画像** — 添加家庭成员和忌口
3. **库存管理** — 批量添加食材
4. **智能查询** — 营养/分类/过期查询
5. **菜谱推荐** — 基于库存和画像推荐
6. **通知系统** — 查看提醒
7. **库存历史** — 查看变动记录
8. **定时任务** — 查看调度状态

运行演示：`python scripts/demo.py`

---

## 📈 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| 库存查询 | < 100ms | ✅ ~50ms |
| 智能查询 | < 100ms | ✅ ~30ms |
| 图片识别 | < 10s | ✅ ~5s |
| 菜谱推荐 | < 10s | ✅ ~8s |
| 健康检查 | < 2s | ✅ ~1.5s |

---

## 🔒 安全特性

- 乐观锁防并发冲突
- FIFO 扣减保证公平
- 事务保护数据一致性
- 图片大小限制（10MB）
- 输入参数校验

---

## 📝 开发日志

- **Day 1**: Flask 骨架 + 数据库 + MiMo 集成
- **Day 2**: 拍照识别 + 图片处理 + 重试机制
- **Day 3**: 画像建档 + 菜谱推荐优化
- **Day 4**: 通知系统 + 定时任务 + 库存历史 + 健康检查
- **Day 5**: 测试 + 文档 + 演示准备

---

## 🤝 贡献者

- **YUAN** — 后端逻辑、AI 集成
- **Claude** — 代码生成、架构设计

---

## 📄 许可证

MIT License

---

## 🔗 链接

- **GitHub**: https://github.com/5765scdnfz-oss/smart-fridge-magnet
- **API文档**: [docs/API.md](docs/API.md)
