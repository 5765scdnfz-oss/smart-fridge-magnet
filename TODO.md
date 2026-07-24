# 智能冰箱贴 — 开发计划 & TODO

> **截止：** 2026-07-30（Demo）
> **展示：** 2026-08-01 ~ 08-02

---

## P0 设备显示路由（7/24 完成）✅

- [x] `POST /api/devices/{id}/display` — Android 上传 .film
- [x] `GET /api/devices/{id}/display/manifest` — ESP32 版本检查
- [x] `GET /api/devices/{id}/display/{ver}.film` — ESP32 下载文件
- [x] `GET /api/devices/{id}/sync-status` — Android 同步状态
- [x] `GET /api/devices` — 设备列表
- [x] `POST /api/devices/{id}/display/force` — 强制刷新
- [x] 设备数据库表（devices, device_display, device_sync_log）
- [x] .film 文件头验证 + SHA-256 校验
- [x] 测试通过：上传/manifest/下载/状态

---

## Day 1（7/26）：搭建基础框架 ✅

- [x] 创建 Flask 主程序骨架（app.py）
- [x] 创建 SQLite 数据库模块（database.py）
- [x] 创建数据库表结构（6张表）
- [x] 创建 MiMo API 客户端（mimo_client.py）
- [x] 创建 Prompt 模板文件（prompts.py）
- [x] 创建食材识别模块（recognition.py）
- [x] 创建 Agent 模块（agent.py）
- [x] 创建定时任务模块（scheduler.py）
- [x] 测试：数据库能读写 ✅
- [x] 测试：MiMo API 连通 ✅（v2.5-pro: 8.8s, v2.5: 6.0s）

## Day 1.5（7/26 晚）：营养数据接入 ✅

- [x] 下载中国食物成分表数据（1657条，来自GitHub开源项目）
- [x] 创建nutrition_data表并导入1635条数据
- [x] 实现营养数据搜索功能
- [x] 菜谱推荐接入营养数据，显示预估热量
- [x] 数据来源：Sanotsu/china-food-composition-data（中国食物成分表第6版）

## Day 2（7/27）：核心功能 — 拍照识别 + 库存管理

- [ ] 实现 `/api/recognize` 接口（拍照识别食材）
- [ ] 实现 `/api/inventory` 接口（查看库存）
- [ ] 实现 `/api/chat` 接口（基础对话）
- [ ] 编写食材识别 Prompt（FOOD_RECOGNITION_PROMPT）
- [ ] 测试：拍照→识别→存入库存→查看库存 完整流程

## Day 3（7/28）：核心功能 — 画像 + 菜谱推荐

- [ ] 实现用户画像提取逻辑（PROFILE_EXTRACTION_PROMPT）
- [ ] 实现 `/api/profile` 接口（查看/更新画像）
- [ ] 实现 `/api/recommend` 接口（菜谱推荐）
- [ ] 实现 A/B 方案生成逻辑
- [ ] 实现忌口分层处理（主材料/配料/口味）
- [ ] 测试：对话建档→推荐菜谱→展示A/B方案 完整流程

## Day 4（7/29）：定时任务 + 扣减 + 联调

- [ ] 实现 `/api/confirm` 接口（确认方案，扣减库存）
- [ ] 实现定时任务调度器（APScheduler）
- [ ] 实现定时推荐逻辑（提前1-2小时推送）
- [ ] 与前端团队联调接口
- [ ] 测试：定时推送→确认→扣减→库存更新 完整流程

## Day 5（7/30）：测试 + 演示准备

- [ ] 端到端完整流程测试
- [ ] 修复 Bug
- [ ] 准备演示数据（食材照片、家庭画像）
- [ ] 编写演示脚本
- [ ] 演示彩排

---

## 里程碑

| 阶段 | 日期 | 产出 | 状态 |
|------|------|------|------|
| M1 | 7/26 | Flask + SQLite + MiMo 跑通 | ✅ 完成 |
| M1.5 | 7/26 | 营养数据接入（1635条） | ✅ 完成 |
| M2 | 7/27 | 拍照识别 + 库存管理 | ⏳ 待开始 |
| M3 | 7/28 | 画像建档 + 菜谱推荐 | ⏳ 待开始 |
| M4 | 7/29 | 定时任务 + 扣减 + 联调 | ⏳ 待开始 |
| M5 | 7/30 | 测试通过 + 演示就绪 | ⏳ 待开始 |

---

## 参考资料

- [王自如100天减肥计划2.0完整文字稿](docs/reference/100天减肥计划2.0_完整文字稿.md)
- [王自如其他视频文字稿](docs/reference/王自如其他视频/)
- [工程文档](docs/工程文档.md)
