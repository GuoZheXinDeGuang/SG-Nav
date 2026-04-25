# 01 - `SG_Nav.py`

## 定位

`SG_Nav.py` 是主入口和运行时总控。它定义 `SG_Nav_Agent`，负责初始化模型、维护导航状态、接收 Habitat observation、调用场景图/地图/规划模块，并返回动作。

## 关键职责

| 职责 | 函数/字段 |
| --- | --- |
| 启动 Habitat Challenge | `main()` |
| 初始化检测器、地图、先验、scene graph | `SG_Nav_Agent.__init__()` |
| 每个 episode 清状态 | `reset()` |
| 每一步决策 | `act()` |
| GLIP 目标/物体检测 | `detect_objects()` |
| frontier exploration | `fbe()` |
| occupancy/free/room map 更新 | `update_map()`, `update_free_map()`, `update_room_map()` |
| FMM 局部规划 | `_plan()`, `_get_stg()` |
| 可视化和结果视频 | `visualize()`, `save_video()` |

## `__init__()` 做了什么

```text
读取 task_config/args
初始化导航状态变量
选择 cuda/cpu
加载 GLIP config + checkpoint
初始化三套 Semantic_Mapping:
  sem_map_module  -> 障碍 occupancy
  free_map_module -> free/explored area
  room_map_module -> 9 类房间 map
读取 obj.npy / room.npy 共现矩阵
创建 SceneGraph(...)
设置可视化目录
```

注意：`GLIPDemo`、GroundingDINO、SAM、Ollama 都是重量级依赖，主程序初始化阶段就会触发部分模型加载。

## `reset()` 做了什么

`reset()` 是 episode 级状态重置，不重建 GLIP 和 mapping 模型。它会：

1. 清空 step 计数、目标状态、collision/random/fbe 状态。
2. 调 `init_map()` 重置 `full_map`、`room_map`、`fbe_free_map`、`full_pose`。
3. 从当前 Habitat episode 读取 `object_category`。
4. 对目标名做 prompt 友好的改写：`gym_equipment -> treadmill. fitness equipment.`、`chest_of_drawers -> drawers`、`tv_monitor -> tv`。
5. 清空 `obj_locations`、可视化帧、scene graph。

## `act()` 主循环

```text
if total_steps >= 500: STOP
total_steps += 1

首次 step:
  根据目标类别取 room/object 共现向量

预处理:
  depth == 0.5 -> 100
  cache rgb/depth

SceneGraph:
  set agent/map/pose/obs/goal
  update_scenegraph()

Mapping:
  update_map()
  update_free_map()

前 22 步:
  用 LOOK_DOWN / TURN_RIGHT_2 / LOOK_UP 扫视
  detect_objects()
  GLIP room detection -> update_room_map()

常规感知:
  更新移动/卡住状态
  scenegraph.perception()

目标选择:
  found_goal -> 真实目标点
  found_possible_goal -> 远处疑似目标点
  first_fbe / reached goal -> frontier
  no frontier / stuck -> random

规划:
  _plan() -> action
  必要时重新采样 random goal

收尾:
  visualize()
  更新 pointgoal_with_gps_compass
  保存 prev_action / navigate_steps
  return {"action": action}
```

## `detect_objects()` 细节

它用 GLIP 在当前 RGB 上跑 `object_captions`，然后：

1. 把 GLIP 数字 label 转成真实文本 label。
2. 收集目标类别 bbox。
3. 对 21 类导航物体，若深度小于 `distance_threshold=5`，将 bbox 中心投影成 GPS/map 点，写入 `obj_locations[class_idx]`，供 frontier scoring 使用。
4. 小物体目标走 scene graph mask 路径：在 `segment2d_results` 中找与目标 caption 匹配且已变成 goal node 的 mask。
5. 普通目标走 GLIP bbox 路径：将多次近距离检测合并到 `goal_gps_map`，达到 `cfg.obj_min_detections` 后才认为 `found_goal=True`。
6. 若目标距离过远，则设置 `found_possible_goal=True`，先朝它靠近再确认。

## `fbe()` 细节

FBE 是 Frontier-Based Exploration：

```text
fbe_map:
  free_map > 0 -> 1
  obstacle dilation -> 3
unknown/free boundary -> frontier_map
frontier_locations -> FMM distance from current start
filter distance >= 1.6m
score = scenegraph.score(frontiers) + distance_inverse * 2
return best frontier
```

`scenegraph.score()` 又融合了房间共现、物体共现和 LLM scene graph 预测。

## `_plan()` / `_get_stg()`

`_plan()` 做两件事：

1. 如果上一步是前进但实际位移小于 `collision_threshold`，就在 `collision_map` 前方打障碍。
2. 调 `_get_stg()` 拿 short-term goal，再用角度差映射成 `MOVE_FORWARD/TURN_LEFT/TURN_RIGHT/STOP`。

`_get_stg()` 会给 `goal_map` 加边界，必要时把目标连通块缩成中心点，调用 `FMMPlanner.set_multi_goal()` 生成距离场，再用 `get_short_term_goal()` 取局部最优方向。

## 重写关注点

| 点 | 说明 |
| --- | --- |
| 状态太集中 | 地图、目标、感知缓存、可视化、评测指标都在 agent 上 |
| `act()` 过长 | 可拆成 perception、map_update、goal_select、plan、visualize |
| 目标确认逻辑复杂 | 小物体和普通物体两套逻辑，需要单测保持行为 |
| 动作 id 硬编码 | `0..6` 与 Habitat 配置/补丁强绑定 |
| `pslpython` 未走主路径 | `add_predicates/add_rules` 像旧实验残留 |
