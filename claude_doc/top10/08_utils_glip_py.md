# 08 - `utils/utils_glip.py`

## 定位

这个文件准备 GLIP prompt 和 ObjectNav 类别映射。它在 import 时读取文件，因此是启动阶段的隐式依赖。

## import 时执行的工作

```text
读取 tools/matterport_category_mappings.tsv
  categories
  categories_40
  categories_map
  categories_doors

定义 ObjectNav 21 类:
  categories_21
  categories_21_origin

给 GLIP 增加额外检测词:
  heater, window, treadmill, exercise machine

object_captions = ". ".join(categories_21) + "."
rooms = 9 类房间
rooms_captions = ". ".join(rooms) + "."

读取 tools/val.json.gz
  projection_reverse = category_to_task_category_id
  projection = id -> category
```

## 关键常量

| 常量 | 作用 |
| --- | --- |
| `categories_21` | ObjectNav 任务类别，加上辅助类别后用于 GLIP prompt |
| `categories_21_origin` | 原始 21 类，用于 `obj_locations` 索引 |
| `object_captions` | 物体检测 prompt |
| `rooms` | 9 类房间固定顺序，必须和 room map 通道一致 |
| `rooms_captions` | 房间检测 prompt |
| `projection` | Habitat task category id 转类别名 |

## `get_iou()`

普通 2D bbox IoU 工具函数。当前核心主路径中没有明显使用，可能是旧逻辑残留或调试工具。

## 对主流程的影响

| 使用者 | 用法 |
| --- | --- |
| `SG_Nav_Agent.__init__()` | 根据 `projection` 建 `goal_idx`，从 co-occurrence matrix 取目标行 |
| `detect_objects()` | 用 `object_captions` 跑 GLIP；用 `categories_21_origin` 记录物体位置 |
| `update_room_map()` | 用 `rooms` 将 GLIP room label 映射到 room map 通道 |
| `SceneGraph` | 另有自己的 `node_space`，和这里类别名相似但不完全同源 |

## 重写关注点

| 点 | 说明 |
| --- | --- |
| import 有副作用 | 文件读取发生在 import 时，缺文件会直接崩 |
| `is not 'objects'` | Python 字符串比较应使用 `!=`，当前写法有潜在警告/风险 |
| 类别名多处维护 | `categories_21`、`node_space`、`threshold_list`、`projection` 应统一 |
| room 顺序是隐式协议 | `rooms` 顺序必须和 `room_map` 9 通道、共现矩阵一致 |
