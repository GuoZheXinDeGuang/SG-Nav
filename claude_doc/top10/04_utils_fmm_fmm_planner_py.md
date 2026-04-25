# 04 - `utils/utils_fmm/fmm_planner.py`

## 定位

`FMMPlanner` 用 scikit-fmm 从目标栅格生成距离场，再在当前位置附近找距离下降最快的短期目标。它是全局 goal map 和离散动作之间的核心桥梁。

## 数据约定

| 数据 | 含义 |
| --- | --- |
| `traversible` | 1 表示可通行，0 表示不可通行 |
| `goal_map` | 1 表示目标位置 |
| `state` | `[row, col]`，通常 agent start 加 1，因为外部加了边界 |
| `fmm_dist` | 到目标的距离场，不可达位置被填成最大值 |

## `set_goal(goal)`

单目标版本：

```text
traversible_ma = masked_values(traversible, 0)
if goal cell not traversible:
  goal <- _find_nearest_goal()
traversible_ma[goal] = 0
fmm_dist = skfmm.distance(traversible_ma)
masked values -> max + 1
```

`SG_Nav_Agent.fbe()` 用它计算所有 frontier 到当前 start 的距离。

## `set_multi_goal(goal_map, state)`

多目标版本：

```text
goal_x, goal_y = where(goal_map == 1)
if selected goal not traversible:
  goal <- _find_nearest_goal(goal, state)
traversible_ma[goal] = 0
fmm_dist = skfmm.distance(traversible_ma)
if current state unreachable:
  add fallback distance from goal map
```

`SG_Nav_Agent._get_stg()` 用它对目标点、frontier 或 random goal 规划。

## `get_short_term_goal(state)`

```text
state 转成 planner scale 下的坐标
mask = get_mask(dx, dy, step_size)
dist_mask = get_dist(...)

从 fmm_dist 取当前位置周围窗口
moving_avg() 平滑局部距离
如果中心距离 < stop_condition: stop=True

subset -= center_distance
边界方向按几何距离归一化
stg = argmin(subset)
replan = subset[stg] 没有明显下降
return stg, replan, stop
```

短期目标不是下一格，而是以 `step_size=5` 为半径的局部窗口边界/中心点。

## `get_mask()` 和 `moving_avg()`

`get_mask()` 把局部窗口的边界和中心设为可选点，因此 planner 倾向于选一个朝向边界的点作为 STG。

`moving_avg()` 对距离场做手写平滑，减少局部噪声导致的方向抖动。

## `_find_nearest_goal()`

当目标落在不可通行处时，在目标附近 80 像素范围内构造临时全通行 planner，按距离排序，找原 `traversible` 中最近的可通行格。

## 重写关注点

| 点 | 说明 |
| --- | --- |
| 行列命名混乱 | `goal_x, goal_y` 实际来自 `np.where`，是 row/col |
| 多目标条件判断脆弱 | `self.traversible[goal_x, goal_y] == 0.` 对数组结果应显式处理 |
| stop 条件绑定 resolution | `stop_cond * 100 / 5` 隐含 5cm 分辨率 |
| smoothing magic number | `800`、`1+n/200` 没有配置来源 |
| 与 `_plan()` 耦合 | planner 只给 STG，动作决策在 `SG_Nav.py` |
