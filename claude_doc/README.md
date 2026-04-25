# SG-Nav 代码理解总览

本文档集用于重写本 repo 前的代码考古。当前仓库实现的是零样本 ObjectNav：机器人在 Habitat/Matterport3D 环境中接收 RGB-D、GPS、Compass 和目标类别，在线构建 2D/3D 地图与 3D scene graph，再用统计共现、LLM/VLM 和 FMM 规划决定下一步动作。

## 一句话架构

```text
Habitat episode
  -> SG_Nav_Agent.act(observations)
  -> GLIP/Grounded-SAM/Ollama 感知与推理
  -> 2D occupancy/free/room map + 3D scene graph
  -> frontier score / goal map
  -> FMMPlanner short-term goal
  -> Habitat action id
```

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [01_terms_verbs_engines_keys.md](01_terms_verbs_engines_keys.md) | 名词、动词、引擎、点火钥匙 |
| [02_modules_and_call_graph.md](02_modules_and_call_graph.md) | 主要模块与 call graph |
| [03_rewrite_notes.md](03_rewrite_notes.md) | 重写时应保留/替换的边界 |
| [top10/01_SG_Nav_py.md](top10/01_SG_Nav_py.md) | 主 agent、主循环、目标选择、局部规划 |
| [top10/02_scenegraph_py.md](top10/02_scenegraph_py.md) | 在线 3D scene graph 与 LLM/VLM 推理 |
| [top10/03_utils_fmm_mapping_py.md](top10/03_utils_fmm_mapping_py.md) | RGB-D 到 2D 栅格地图的投影 |
| [top10/04_utils_fmm_fmm_planner_py.md](top10/04_utils_fmm_fmm_planner_py.md) | FMM 距离场与短期目标 |
| [top10/05_utils_scenegraph_utils_py.md](top10/05_utils_scenegraph_utils_py.md) | 2D mask 到 3D object 的转换/合并 |
| [top10/06_utils_scenegraph_mapping_py.md](top10/06_utils_scenegraph_mapping_py.md) | 3D 检测和已有物体的匹配 |
| [top10/07_utils_scenegraph_slam_classes_py.md](top10/07_utils_scenegraph_slam_classes_py.md) | DetectionList/MapObjectList 数据容器 |
| [top10/08_utils_glip_py.md](top10/08_utils_glip_py.md) | 类别词表、prompt 和 category projection |
| [top10/09_habitat_benchmark_py.md](top10/09_habitat_benchmark_py.md) | 本地评测循环和结果落盘 |
| [top10/10_action_stack_tools_agent_py.md](top10/10_action_stack_tools_agent_py.md) | Habitat 动作栈和额外 60 度右转 |

## 当前功能分层

| 层 | 主要文件 | 做什么 |
| --- | --- | --- |
| 启动/评测 | `SG_Nav.py`, `habitat-lab/habitat/core/benchmark.py` | 解析参数、创建 agent、跑 episode、汇总指标 |
| 感知 | `GLIP`, `GroundingDINO`, `segment_anything`, `scenegraph.py` | 目标框、2D mask、caption、关系判断 |
| 语义图 | `scenegraph.py`, `utils/utils_scenegraph/*` | 2D mask 投影成 3D object，维护节点、边、房间和组 |
| 地图 | `utils/utils_fmm/mapping.py`, `depth_utils.py` | 深度图投影到 occupancy/free/room 栅格 |
| 决策 | `SG_Nav.py`, `scenegraph.py` | 选择真实目标、疑似目标、frontier 或随机目标 |
| 规划控制 | `utils/utils_fmm/fmm_planner.py`, `control_helper.py` | 栅格距离场、短期目标、转向/前进动作 |
| 可视化 | `utils/image_process.py`, `SG_Nav.py` | 拼 RGB、地图、节点、边、解释并保存视频 |

## 最核心循环

```text
reset:
  清空地图/场景图/导航状态，读取当前 episode 目标类别

act:
  1. 更新 scenegraph 输入
  2. scenegraph.update_scenegraph()
  3. 更新 occupancy/free map
  4. 初始化阶段做抬头/低头/旋转以收集 panorama
  5. GLIP 检测目标和房间
  6. scenegraph.perception()
  7. 计算 traversible map
  8. 选择 goal_map: found_goal / found_possible_goal / frontier / random
  9. FMM 规划短期目标
 10. 输出 Habitat action
```

## 重写时优先看懂的事实

1. 这个 repo 的智能不是一个模型，而是很多弱模块串起来：GLIP 检测、Grounded-SAM mask、深度投影、Open3D 合并、共现矩阵、Ollama 问答、FMM 规划。
2. `SG_Nav_Agent.act()` 是唯一真正的运行时总控；几乎所有状态都挂在 agent 上。
3. `SceneGraph` 既做感知，又做推理，又回头影响 frontier 评分，是重写时最需要拆边界的模块。
4. Habitat 动作 6 依赖多处补丁：配置、HabitatSimActions、TaskAction，以及手工复制到 habitat-sim 的 `tools/agent.py`。
5. 文档中的“点火钥匙”不是可选项：没有数据集、checkpoint、Ollama 模型、Habitat 补丁，主程序无法完整跑通。
