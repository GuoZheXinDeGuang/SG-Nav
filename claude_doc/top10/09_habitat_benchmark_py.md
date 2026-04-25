# 09 - `habitat-lab/habitat/core/benchmark.py`

## 定位

这是仓库内 Habitat-Lab 的评测循环文件，已被项目改过。它负责创建 Env、循环 episode、把 observations 喂给 agent、收集指标、落盘结果。

## 初始化

```text
Benchmark.__init__(config_paths, eval_remote=False, split_l=-1, split_r=-1)
  config_env = get_config(config_paths)
  config_env.DATASET.defrost()
  config_env.DATASET.SPLIT_L = split_l
  config_env.DATASET.SPLIT_R = split_r
  config_env.DATASET.freeze()
  if local:
    self._env = Env(config_env)
```

`split_l/split_r` 会继续影响 dataset loader。`pointnav_dataset.py` 里有 `scenes[config.SPLIT_L:config.SPLIT_R]` 的修改；ObjectNav loader 当前没有同样显式 slicing，重写时要确认实际数据集路径和 split 行为。

## `local_evaluate()`

```text
if num_episodes is None:
  num_episodes = len(env.episodes)

agent.simulator = self

while count_episodes < num_episodes:
  observations = env.reset()
  agent.reset()
  while not env.episode_over:
    action = agent.act(observations)
    if agent.total_steps == 500:
      metrics = env.get_metrics()
    observations = env.step(action)
    agent.update_metrics(env.get_metrics())

  metrics = env.get_metrics()
  metrics["goal"] = agent.obj_goal
  aggregate metrics
  write results.txt / results_0.txt / results_avg.txt / benchmark.json
```

## 输出文件

路径：

```text
data/results/{agent.experiment_name}/
  results.txt
  results_0.txt
  results_avg.txt
  benchmark.json
```

`benchmark.json` 包含：

| 字段 | 内容 |
| --- | --- |
| `total_episodes` | 已跑 episode 数 |
| `overall` | 当前平均指标 |
| `per_category` | 每个目标类别的成功率、SPL、SoftSPL、距离 |
| `per_episode` | 每个 episode 的指标 |

## 和 agent 的特殊关系

`agent.simulator = self` 是一个关键注入点。`SG_Nav_Agent.reset()` 后面通过：

```text
self.simulator._env.current_episode.object_category
```

读取当前目标类别。这让 agent 依赖 Benchmark 的内部结构，而不只是 Habitat 的标准 Agent API。

## 重写关注点

| 点 | 说明 |
| --- | --- |
| local loop 可保留 | 这是对比实验的稳定外壳 |
| agent 反向读取 Benchmark | 建议改成在 reset 时显式传 episode/context |
| 结果每 episode 重写 | 当前每个 episode 都覆盖 txt/json，便于中断恢复但 I/O 多 |
| remote_evaluate 基本原版 | 主项目默认 `eval_remote=False`，远程路径不是重点 |
