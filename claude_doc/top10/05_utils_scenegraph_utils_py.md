# 05 - `utils/utils_scenegraph/utils.py`

## 定位

这个文件是 scene graph 3D fusion 的工具箱：过滤 2D detections，把 mask + depth 变成 Open3D 点云，计算 overlap，合并 object。

## 主要函数

| 函数 | 作用 |
| --- | --- |
| `filter_objects()` | 过滤太小、检测次数不足、空间尺寸不足的 3D object |
| `filter_gobs()` | 过滤 2D mask：小 mask、背景、大框、低置信度 |
| `resize_gobs()` | mask 和 image 尺寸不一致时重采样 |
| `create_object_pcd()` | mask 内 depth 反投影成点云 |
| `gobs_to_detection_list()` | 2D segmentation result -> foreground/background DetectionList |
| `compute_overlap_matrix_2set()` | 用 FAISS 点近邻估计已有物体和新检测的重叠比例 |
| `process_pcd()` | voxel downsample + DBSCAN 去噪 |
| `get_bounding_box()` | 点云 bbox，优先 oriented bbox |
| `merge_obj2_into_obj1()` | 把新检测合并进已有 3D object |
| `text2value()` | LLM 文本转 float |

## `gobs_to_detection_list()` 流程

```text
resize_gobs()
filter_gobs()
mask_subtract_contained()

for each mask:
  class_name / class_id
  create_object_pcd(depth, mask, cam_K, image)
  if points too few: skip
  if trans_pose: transform to global frame
  process_pcd()
  get_bounding_box()
  if bbox volume too small: skip
  build detected_object dict
  append to fg or bg DetectionList
```

`detected_object` 是重写时必须稳定下来的数据结构，当前字段包括：

```text
image_idx, mask_idx, class_name, class_id,
num_detections, mask, xyxy, conf,
n_points, pixel_area, contain_number,
inst_color, is_background,
pcd, bbox
```

## `create_object_pcd()` 坐标

导航模式下使用 `utils_fmm.depth_utils.get_camera_matrix()` 返回的 `Namespace(f, xc, zc)`：

```text
x = (u - cx) * depth / f
y = depth
z = (v - cz) * depth / f
```

非导航模式走标准 intrinsics matrix。SG-Nav 当前传 `is_navigation=True`。

## `compute_overlap_matrix_2set()`

```text
objects_map: 已有 m 个 3D object
objects_new: 新 n 个 detection

对每个已有 object:
  点数超过 max_num_points 就随机采样
  建 FAISS IndexFlatL2

先算 bbox IoU:
  IoU 太小 -> overlap 保持 0
  否则对新点云每个点找旧点云最近邻
  D < voxel_size^2 的比例作为 overlap

return m x n matrix
```

`utils_scenegraph/mapping.py` 会转置该矩阵，使 shape 变成 new x existing。

## `merge_obj2_into_obj1()`

合并时：

1. list/int 字段相加，比如 `image_idx`、`mask_idx`、`num_detections`。
2. `inst_color` 保留旧 object 颜色。
3. 点云直接相加，再 `process_pcd()`。
4. 重新计算 bbox。
5. 跳过 `node`、`captions` 等 scene graph 附加字段，避免破坏图节点绑定。

## 重写关注点

| 点 | 说明 |
| --- | --- |
| dict schema 隐式 | 没有 dataclass，字段增删靠约定 |
| 随机性 | 点云采样、点扰动、inst_color 都有随机性 |
| filter 阈值硬编码在 cfg | 行为强依赖 `SceneGraph.set_cfg()` |
| Open3D 原地行为 | `pcd.transform()` 会修改对象，重写时要注意复制/引用 |
| `text2value()` 容错粗糙 | 非纯数字 LLM 输出直接变 0 |
