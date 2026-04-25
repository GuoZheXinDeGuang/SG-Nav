# 03 - `utils/utils_fmm/mapping.py`

## 定位

`Semantic_Mapping` 是 RGB-D 到 2D 栅格地图的核心投影模块。它被实例化三次：

| 实例 | 参数 | 输出 |
| --- | --- | --- |
| `sem_map_module` | 默认高度范围 | 障碍/occupancy map |
| `free_map_module` | `max_height=10,min_height=-150` | 已探索 free map |
| `room_map_module` | `max_height=200,min_height=-10,num_cats=9` | 9 通道 room map |

## 输入输出

```text
forward(depth, pose_obs, maps_last, type_mask=None, type_prob=None)

depth: H x W，单位米，外部传入前 squeeze 掉最后一维
pose_obs: [x, y, theta]，x/y 单位米，theta 单位度
maps_last: 1/C x map_h x map_w
type_mask: 可选 C x H x W semantic mask
type_prob: 可选 C 类置信度

return:
  更新后的 map tensor
```

## occupancy/free 路径 `forward()`

```text
depth * 100
get_point_cloud_from_z_t()
transform_camera_view_t_multiple()
transform_pose_t()

把点云归一化到 [-1, 1]
splat_feat_nd() 投到局部 3D voxel grid
按高度区间求和:
  agent_height_proj -> 障碍
  all_height_proj   -> explored
clamp 到 [0, 1]

把局部 agent_view 放到全图中心附近
根据 pose 生成 affine grid:
  rotate
  translate
maps_last 和 translated 做 max 融合
阈值 > 0.5 -> 1
```

关键坐标约定：agent 初始在全图中心，`SG_Nav_Agent.update_map()` 把 GPS 转成以地图中心为原点偏移的 `full_pose`。

## semantic/room 路径 `forward_()`

当 `type_mask` 不为空时走 `forward_()`：

1. 与普通路径一样由 depth 生成点云。
2. `type_mask` 作为每个像素的类别特征，被 `AvgPool2d` 后 splat 到 3D grid。
3. 高度投影后得到 C 通道 `agent_view`。
4. 对每个类别通道，所有正值被替换为对应 `type_prob[i]`。
5. 与 `maps_last` 做 max 融合。

`SG_Nav_Agent.update_room_map()` 将 GLIP 房间 bbox 转成 9 通道 mask 和 score，再调用这条路径。

## 依赖函数

| 函数 | 文件 | 作用 |
| --- | --- | --- |
| `get_camera_matrix()` | `depth_utils.py` | 根据宽高/FOV 得到 pinhole 参数 |
| `get_point_cloud_from_z_t()` | `depth_utils.py` | depth 反投影到相机坐标 |
| `transform_camera_view_t_multiple()` | `depth_utils.py` | 修正相机俯仰和传感器高度 |
| `transform_pose_t()` | `depth_utils.py` | 转到地图/世界坐标 |
| `splat_feat_nd()` | `depth_utils.py` | 把点特征 splat 到 voxel grid |
| `get_grid()` | `model.py` | 生成旋转和平移 affine grid |

## 重写关注点

| 点 | 说明 |
| --- | --- |
| 单位混杂 | depth 米转厘米，pose 米转厘米，map resolution 5cm |
| 坐标方向难读 | x/y、图像行列、地图反转在多个地方出现 |
| `view_angles` 列表只有一个值 | 初始化 panorama 时通过修改该值模拟相机 pitch |
| `forward()` 内部定义 helper | `pose_transform` 和 `get_new_pose_batch` 可以抽出或删掉未用部分 |
| `forward_()` 与 `forward()` 重复多 | 可统一成通用 point cloud -> projected feature map |
