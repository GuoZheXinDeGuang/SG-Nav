# 07 - `utils/utils_scenegraph/slam_classes.py`

## 定位

`DetectionList` 和 `MapObjectList` 是 scene graph 3D object 的轻量容器。它们继承 Python `list`，内部元素是 dict。

## `DetectionList`

| 方法 | 作用 |
| --- | --- |
| `get_values(key, idx=None)` | 取每个 detection 的某字段 |
| `get_stacked_values_torch(key, idx=None)` | 将字段堆成 torch tensor，bbox 会转成 box points |
| `get_stacked_values_numpy()` | torch 堆叠后转 numpy |
| `slice_by_indices()` | 按索引返回同类型子列表 |
| `slice_by_mask()` | 按 bool mask 返回同类型子列表 |
| `get_most_common_class()` | 每个 object 的 `class_id` 众数 |
| `color_by_most_common_classes()` | 按类别给点云/bbox 上色 |
| `color_by_instance()` | 按实例给点云/bbox 上色 |

最关键的是 `get_stacked_values_torch('bbox')`：它把 Open3D bbox 转成 8 个角点，再 stack，供 IoU/overlap 计算。

## `MapObjectList`

`MapObjectList` 继承 `DetectionList`，新增：

| 方法 | 作用 |
| --- | --- |
| `compute_similarities(new_clip_ft)` | 与已有 object 的 CLIP 特征做余弦相似 |
| `to_serializable()` | 把 tensor/Open3D 对象转成 numpy 字段 |
| `load_serializable()` | 从可序列化结构恢复 Open3D 点云和 bbox |

当前 SG-Nav 主路径里 CLIP 特征相关字段大多被注释掉，`compute_similarities()` 不是核心路径。

## 数据结构隐含约束

容器没有 schema 校验，但下游默认每个 object 至少有：

```text
pcd: open3d.geometry.PointCloud
bbox: Open3D bbox
class_id: list[int]
num_detections: int
image_idx/mask_idx/conf/xyxy/mask: list
```

`SceneGraph.update_node()` 还会向 object dict 写入 `node` 字段，形成 object <-> node 双向引用。

## 重写关注点

| 点 | 说明 |
| --- | --- |
| list + dict 灵活但脆弱 | 建议重写成 dataclass 或 pydantic-like schema |
| Open3D 不易序列化 | 现有 `to_serializable` 已提供转换方向，可作为迁移参考 |
| 图节点引用混入 object | `object['node']` 把 SLAM object 和 graph node 耦合 |
| CLIP 路径半废弃 | 如果不用视觉语义匹配，可以删掉；如果要用，需要补字段 |
