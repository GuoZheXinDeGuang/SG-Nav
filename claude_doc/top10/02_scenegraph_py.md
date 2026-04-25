# 02 - `scenegraph.py`

## 定位

`scenegraph.py` 负责在线构建 3D scene graph，并把它反向用于导航：目标在哪个房间、哪个物体组附近，frontier 应该优先探索哪里。

## 核心类

| 类 | 作用 |
| --- | --- |
| `RoomNode` | 固定 9 类房间节点，持有该房间内 object nodes 和 group nodes |
| `GroupNode` | 同房间内 DBSCAN 聚成的一组 object nodes，生成局部图文本 |
| `ObjectNode` | 一个 3D object 的图节点，包含 caption、center、room、edges、goal 标记 |
| `Edge` | 两个 ObjectNode 的空间关系边 |
| `SceneGraph` | 感知、3D fusion、图更新、LLM/VLM 推理、frontier 评分 |

## 初始化

```text
SceneGraph.__init__()
  保存 map/camera/agent 参数
  初始化 objects / objects_post / nodes / edges
  init_room_nodes()
  定义目标词表 node_space
  定义 LLM/VLM prompts
  get_sam_mask_generator("groundedsam")
    load GroundingDINO
    load SAM predictor
  set_cfg()
```

`set_cfg()` 是硬编码配置，重写时应该外置。导航模式会把 `sim_threshold` 和 `sim_threshold_spatial` 改低，以便更多检测能被合并。

## `update_scenegraph()` 主路径

```text
segment2d()
  GroundingDINO + SAM 产生 mask/box/caption

mapping3d()
  mask + depth + pose -> DetectionList
  与已有 MapObjectList 按空间重叠合并

get_caption()
  统计同一个 3D object 多次检测的 caption 众数

update_node()
  3D object -> ObjectNode
  点云中心 -> map center
  room_map lookup -> RoomNode
  caption 匹配目标 -> is_goal_node

update_edge()
  新节点和旧节点建边
  VLM/LLM 推断空间关系
  discriminate_relation() 过滤不可信边
```

## 2D segmentation

`segment2d()` 调 `get_sam_segmentation_dense()`：

1. GroundingDINO 用 `node_space` 文本找候选 box 和 caption。
2. SAM predictor 使用 box 作为 prompt 生成 mask。
3. 结果保存到 `segment2d_results`：`xyxy/confidence/mask/image_rgb/caption`。

这个结果还被 `SG_Nav_Agent.detect_objects()` 用来处理小物体目标。

## 3D mapping

`mapping3d()`：

```text
gobs = segment2d_results[-1]
fg_detection_list = gobs_to_detection_list(...)
if objects empty:
  append all foreground detections
else:
  spatial_sim = compute_spatial_similarities(fg_detection_list, objects)
  below threshold -> -inf
  merge_detections_to_objects()
objects_post = filter_objects()
```

这里的 3D object 本质是 dict，至少包含点云、bbox、图像索引、mask 索引、置信度、检测次数等。

## 边的更新

`update_edge()` 只处理新节点产生的新边：

```text
new node x old node -> Edge
new node x new node -> Edge

for relation-less edges:
  if two nodes appear in same image:
    ask VLM: "What is the spatial relationship..."
  else:
    batch ask LLM for relation proposals

for proposed edges:
  discriminate_relation()
```

`discriminate_relation()` 优先用同图 VLM 判断 yes/no；没有 joint image 时，用房间一致、距离阈值、轴向关系、两点间 free map 连通做几何过滤。

## 用 graph 影响导航

`score(frontier_locations_16, num_16_frontiers)` 汇总三种分数：

1. 房间共现：frontier 周围 25x25 的 `room_map` 是否有与目标高共现的房间。
2. 物体共现：frontier 附近是否有 GLIP 记录的高共现物体。
3. graph/LLM：`insert_goal()` 先预测目标最可能在哪个已有房间，再对该房间中的物体组调用 `graph_corr()`，最后提高靠近预测 group center 的 frontier 分数。

## Ollama 调用

| 函数 | 用途 |
| --- | --- |
| `get_llm_response()` | 文本 prompt，一般用于房间预测、关系提案、概率判断 |
| `get_vlm_response()` | 文本 + PNG 图像，用于空间关系判断 |
| `graph_corr()` | 四轮 LLM 对话，估计某个 group 和目标共现概率 |

## 重写关注点

| 点 | 说明 |
| --- | --- |
| 单类过大 | 模型加载、数据融合、图推理、导航评分都在一个类里 |
| prompt 硬编码 | prompt、模型名、checkpoint、阈值都写死 |
| LLM 调用无缓存 | 同类关系/图相关性可能重复问，运行成本高 |
| 边数量增长快 | 新节点和所有旧节点连边，复杂度接近 O(N^2) |
| 回调 agent | `perception()` 调 agent 的检测/房间地图更新，边界不清 |
