# 重写建议和风险清单

## 建议保留的行为边界

| 边界 | 当前位置 | 重写建议 |
| --- | --- | --- |
| 仿真 I/O | `SG_Nav_Agent.act()` 只收 observation、回 action dict | 保持这个接口，方便继续用 Habitat Challenge |
| 地图更新 | `Semantic_Mapping.forward()` | 可替换实现，但输入/输出最好保持 depth + pose + map -> map |
| 场景图更新 | `SceneGraph.update_scenegraph()` | 拆成 perception、3D fusion、graph reasoning 三层 |
| 长期目标选择 | `found_goal` / `possible_goal` / frontier / random | 明确保留优先级，避免重写后策略漂移 |
| 局部规划 | `_plan()` + `FMMPlanner` | 可替换为导航库，但应保留 collision map 和 stop 语义 |
| 评测记录 | `Benchmark.local_evaluate()` | 保留 txt/json 输出，便于对比重写前后结果 |

## 当前强耦合点

```text
SG_Nav_Agent
  owns maps, goal state, object priors, metrics, visualization
  calls SceneGraph
    SceneGraph calls back agent.detect_objects/update_room_map
    SceneGraph reads agent room_map/fbe_free_map/prob arrays
```

最需要解开的耦合是 `SceneGraph.perception()`：它看起来属于 scene graph，但实际调用 agent 的 GLIP 检测、房间地图更新，并依赖 agent 状态。重写时可拆为：

1. `PerceptionService`: GLIP/Grounded-SAM/Ollama wrappers。
2. `MapState`: occupancy/free/room/visited/collision。
3. `SceneGraphState`: nodes/edges/groups/objects。
4. `GoalSelector`: 目标可见性、frontier scoring、random fallback。
5. `LocalPlanner`: traversible -> short-term goal -> discrete action。

## 需要特别验证的行为

| 行为 | 风险 |
| --- | --- |
| `goal_gps_map` 使用 numpy view 指向 `full_map[0,0].cpu().numpy()` | reset 后如果 tensor/device 变化，语义可能不明显 |
| `room_label = first nonzero channel` | 多房间重叠时丢弃置信度排序 |
| `caption in self.obj_goal_sg` | 字符串包含判断可能把短词误匹配 |
| `SceneGraph.update_edge()` 对所有新旧节点连边 | 节点多时 LLM/VLM 调用量会爆炸 |
| `FMMPlanner.set_multi_goal()` 中 `self.traversible[goal_x, goal_y] == 0.` | 多目标数组场景下条件判断可能依赖 numpy 行为，值得单测 |
| `action 6` 的定义分散在配置、habitat-lab 和 copied habitat-sim 文件 | 环境稍变就会出现动作不可用 |
| `pslpython` 相关函数未被主循环调用 | 可能是旧方案残留，不应在重写中误当主路径 |

## 最小可重写骨架

```text
class Agent:
  reset()
  act(obs):
    perception = perception_service.step(obs)
    maps = mapper.update(obs, perception)
    graph = graph_builder.update(obs, perception, maps)
    goal = goal_selector.select(obs, maps, graph)
    action = planner.next_action(maps, goal, obs.pose)
    return action
```

## 建议先补的测试

| 测试 | 覆盖点 |
| --- | --- |
| depth -> occupancy map 小尺寸 fixture | 坐标方向、单位、地图中心 |
| goal GPS/map 互转 | `get_goal_gps()` 和 `get_relative_goal_gps()` |
| frontier 提取 | free/unknown/obstacle 的边界逻辑 |
| FMM stop/action | 目标在前/左/右/当前位置时的动作 |
| 3D object merge | 两个重叠点云是否合并，不重叠是否新增 |
| room map projection | GLIP bbox 到 9 通道 room map |
| action id 6 smoke test | Habitat 环境里 `TURN_RIGHT_2` 是否真的转 60 度 |
