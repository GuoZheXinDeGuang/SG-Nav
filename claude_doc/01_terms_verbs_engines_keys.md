# 名词、动词、引擎、点火钥匙

## 名词

| 名词 | 在代码中的形态 | 含义 |
| --- | --- | --- |
| episode | `self.simulator._env.current_episode` | Habitat ObjectNav 的一个任务实例，包含场景、起点和目标类别 |
| observation | `observations` | 每一步输入，含 `rgb`、`depth`、`gps`、`compass`、`objectgoal` |
| object goal | `self.obj_goal` | 当前 episode 的目标类别，如 `chair`、`tv_monitor` |
| scene graph goal | `self.obj_goal_sg` | 给 scene graph/LLM 使用的目标文本，修正了 `gym_equipment`、`chest_of_drawers`、`tv_monitor` 等别名 |
| full map | `self.full_map` | 1 通道 occupancy map，1 表示障碍/占用 |
| free map | `self.fbe_free_map` | 1 通道探索/可达空闲区域，frontier 由它和 unknown 区域相交得到 |
| room map | `self.room_map` | 9 通道房间语义地图，来自 GLIP 房间检测 + 深度投影 |
| goal map | `self.goal_map` | 给 FMMPlanner 的二值目标栅格 |
| goal GPS | `self.goal_gps` | 目标在 Habitat GPS 坐标系中的估计位置 |
| possible goal | `self.found_possible_goal` | 看到疑似目标但距离过远或确认不足时的临时目标 |
| frontier | `frontier_locations_16` | 已知 free 和 unknown 的边界候选点，用于主动探索 |
| SceneGraph | `SceneGraph` | 在线 3D 场景图，包含 object nodes、room nodes、edges、groups |
| ObjectNode | `ObjectNode` | 一个 3D 物体节点，指向 `MapObjectList` 中的 3D object |
| Edge | `Edge` | 两个物体节点之间的空间关系，如 `next to`、`on` |
| GroupNode | `GroupNode` | 同一房间内局部聚类的一组物体，用于问 LLM 目标更可能在哪个区域 |
| co-occurrence | `tools/obj.npy`, `tools/room.npy` | 目标类别和其他物体/房间的共现先验 |
| traversible | `traversible` | FMM 可通行地图，1 表示可通行，外围加了一圈边界 |
| STG | `short-term goal` | FMM 距离场上下一步要朝向的局部栅格点 |

## 动词

| 动词 | 主要函数 | 做什么 |
| --- | --- | --- |
| reset | `SG_Nav_Agent.reset()` | 清空每个 episode 的地图、目标、场景图、可视化和统计 |
| act | `SG_Nav_Agent.act()` | 每步主循环，输入 observation，输出 action |
| detect | `detect_objects()` | GLIP 检测物体，判断是否看到目标，并记录邻近物体位置 |
| segment | `SceneGraph.segment2d()` | GroundingDINO + SAM 生成 2D mask、box、caption |
| map3d | `SceneGraph.mapping3d()` | 2D mask + depth + pose 转成 3D object，并合并到全局物体表 |
| caption | `SceneGraph.get_caption()` | 从多帧 mask caption 中取众数作为 object caption |
| update node | `SceneGraph.update_node()` | 将 3D object 同步成 ObjectNode，定位中心和房间 |
| update edge | `SceneGraph.update_edge()` | 为新节点和旧节点建边，用 VLM/LLM 判断关系 |
| group | `SceneGraph.update_group()` | 按房间内 2D 中心点 DBSCAN 聚类局部物体组 |
| score frontier | `SceneGraph.score()` | 用房间/物体共现和 graph-LLM 结果给 frontier 打分 |
| fbe | `SG_Nav_Agent.fbe()` | Frontier-Based Exploration，选择长期探索目标 |
| plan | `_plan()`, `_get_stg()` | FMM 距离场求短期目标，再映射成前进/左转/右转/停 |
| visualize | `visualize()`, `save_video()` | 拼接观测、地图、节点/边和解释，episode 结束存视频 |

## 引擎

| 引擎 | 入口 | 用途 |
| --- | --- | --- |
| Habitat / Habitat-Sim | `habitat.Challenge`, `Env`, `Simulator` | 提供仿真、传感器、导航任务、指标 |
| GLIP | `GLIPDemo.inference()` | open-vocabulary 物体/房间检测 |
| GroundingDINO + SAM | `get_sam_segmentation_dense()` | 根据目标词表产生检测框和高质量 mask |
| Semantic_Mapping | `utils/utils_fmm/mapping.py` | 把 RGB-D 投影成 occupancy/free/room 栅格 |
| Open3D | `create_object_pcd()`, `get_bounding_box()` | 建点云、降采样、bbox、DBSCAN 去噪 |
| FAISS | `compute_overlap_matrix_2set()` | 用近邻搜索估计两个 3D object 的点云重叠 |
| scikit-fmm | `FMMPlanner.set_goal/set_multi_goal()` | 从目标栅格构造距离场 |
| Ollama LLM/VLM | `get_llm_response()`, `get_vlm_response()` | 预测房间、图相关性、空间关系和关系真伪 |
| 统计先验 | `tools/obj.npy`, `tools/room.npy` | 无训练导航时的物体/房间共现概率 |

## 点火钥匙

| 钥匙 | 位置 | 缺了会怎样 |
| --- | --- | --- |
| 启动命令 | `python SG_Nav.py --visualize` | 进入本地 Habitat challenge 评测循环 |
| 主配置 | `configs/challenge_objectnav2021.local.rgbd.yaml` | 定义 RGB-D 尺寸、动作、数据路径、ObjectNav 任务 |
| Matterport3D 数据 | `DATASET.SCENES_DIR`, `DATASET.DATA_PATH` | 没有场景和 episode，Habitat 无法 reset |
| GLIP checkpoint | `GLIP/MODEL/glip_large_model.pth` | `SG_Nav_Agent.__init__` 初始化检测器失败 |
| GroundingDINO checkpoint | `data/models/groundingdino_swint_ogc.pth` | scene graph 的 2D segmentation 无法启动 |
| SAM checkpoint | `data/models/sam_vit_h_4b8939.pth` | mask predictor 无法初始化 |
| Ollama 模型 | `llama3.2-vision` | LLM/VLM 关系判断、房间预测和 graph correlation 失败 |
| Habitat-Sim agent 补丁 | `cp tools/agent.py ${HABITAT_SIM_PATH}/habitat_sim/agent/` | 动作 id 6 的 60 度右转可能不可用 |
| 类别/先验文件 | `tools/val.json.gz`, `obj.npy`, `room.npy`, `matterport_category_mappings.tsv` | 类别映射、GLIP prompt、frontier score 失效 |
| split 参数 | `--split_l`, `--split_r` | 控制评测场景范围，影响结果目录名 |

## 状态机速写

```text
未找到目标
  -> 先做抬头/旋转 panorama
  -> GLIP/scenegraph 持续感知
  -> 若看到近目标: found_goal
  -> 若看到远目标: found_possible_goal
  -> 否则: fbe frontier
  -> frontier 不可达或卡住: random goal

found_goal
  -> goal_gps -> goal_map -> FMM -> 接近后 STOP

found_possible_goal
  -> possible_goal_temp_gps -> goal_map
  -> 若到达但未确认: 取消疑似目标，回到探索
```
