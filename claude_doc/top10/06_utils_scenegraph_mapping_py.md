# 06 - `utils/utils_scenegraph/mapping.py`

## 定位

这个文件很小，但它决定新 3D detection 如何和已有 `MapObjectList` 合并。它是 scene graph 物体持久化的关键胶水。

## `compute_spatial_similarities()`

输入：

```text
detection_list: M 个新 detection
objects: N 个已有 map object
cfg.spatial_sim_type: iou / giou / iou_accurate / giou_accurate / overlap
```

输出：

```text
M x N torch.Tensor
```

当前 `SceneGraph.set_cfg()` 中 `spatial_sim_type='overlap'`，因此实际路径是：

```text
compute_overlap_matrix_2set(cfg, objects, detection_list)
  -> m x n numpy
transpose
  -> n x m torch
```

## `merge_detections_to_objects()`

```text
for each new detection i:
  if agg_sim[i].max() == -inf:
    objects.append(detection_list[i])
  else:
    j = argmax(agg_sim[i])
    matched_obj = objects[j]
    merged_obj = merge_obj2_into_obj1(cfg, matched_obj, detection_i)
    objects[j] = merged_obj
return objects
```

在 `scenegraph.mapping3d()` 中，低于 `cfg.sim_threshold_spatial` 的 similarity 会先被置为 `-inf`，因此这里不再判断阈值。

## 它对行为的影响

| 情况 | 结果 |
| --- | --- |
| 新 mask 和已有物体重叠 | 合并到已有 object，保留同一个 ObjectNode |
| 新 mask 不重叠 | 新增 object，后续 `update_node()` 建新 ObjectNode |
| 相似度错配 | 可能把两个物体合并成一个，或导致重复节点 |
| 检测短暂丢失 | 已有 object 留在 `objects` 中，不会自动删除 |

## 重写关注点

| 点 | 说明 |
| --- | --- |
| 缺少语义相似 | 代码中 clip/visual/text similarity 被注释掉，当前主要靠空间 |
| 阈值位置分散 | 阈值在 caller 里置 `-inf`，merge 函数本身不知道阈值 |
| 一对多简单贪心 | 每个 detection 独立选最大相似 object，没有全局匹配 |
| `compute_giou_*` 未导入 | 如果 cfg 改成 giou 路径会报错，当前默认避开了 |
