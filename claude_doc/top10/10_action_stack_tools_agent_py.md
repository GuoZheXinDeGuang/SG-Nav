# 10 - 动作栈与 `tools/agent.py`

## 定位

SG-Nav 使用 7 个离散动作：

```text
0 STOP
1 MOVE_FORWARD
2 TURN_LEFT
3 TURN_RIGHT
4 LOOK_UP
5 LOOK_DOWN
6 TURN_RIGHT_2
```

其中动作 6 是项目额外需要的 60 度右转，用于初始化 panorama 阶段快速旋转。它不是单个文件完成的，而是分散在配置、Habitat-Lab 和需要手工复制的 Habitat-Sim agent 文件里。

## 相关文件

| 文件 | 作用 |
| --- | --- |
| `configs/challenge_objectnav2021.local.rgbd.yaml` | `POSSIBLE_ACTIONS` 加入 `TURN_RIGHT_2` |
| `habitat-lab/habitat/config/default.py` | `ACTIONS.TURN_RIGHT_2.TYPE = "TurnRightAction2"` |
| `habitat-lab/habitat/sims/habitat_simulator/actions.py` | `HabitatSimActions.TURN_RIGHT_2 = 6` |
| `habitat-lab/habitat/tasks/nav/nav.py` | `TurnRightAction2.step()` 调 `self._sim.step(HabitatSimActions.TURN_RIGHT_2)` |
| `tools/agent.py` | 复制到安装的 habitat-sim 后，把 sim agent action id 6 映射成 60 度 `turn_right` |

## `tools/agent.py` 的关键改动

在 `Agent.__init__()` 中：

```text
self.agent_config = agent_config if agent_config else AgentConfiguration()
self.agent_config.action_space[6] =
  ActionSpec("turn_right", ActuationSpec(amount=60.0))
```

README 要求执行：

```text
HABITAT_SIM_PATH=$(pip show habitat_sim | grep 'Location:' | awk '{print $2}')
cp tools/agent.py ${HABITAT_SIM_PATH}/habitat_sim/agent/
```

也就是说，仓库里的 `tools/agent.py` 不是被 Python import 的普通项目文件，而是给外部安装包打补丁的文件。

## 动作 6 在主循环中的使用

`SG_Nav_Agent.act()` 初始化阶段：

```text
step 1:  LOOK_DOWN
step 2-7: TURN_RIGHT_2
step 8:  LOOK_DOWN
step 9-14: TURN_RIGHT_2
step 15: LOOK_UP
step 16: LOOK_UP
step 17-22: TURN_RIGHT_2 + panorama/object/room detection
```

目的：用 pitch 和 60 度右转覆盖更多视角，给 GLIP/room map/scene graph 初始观测。

## 风险

| 风险 | 说明 |
| --- | --- |
| 补丁不在 repo import 路径 | 用户忘记复制 `tools/agent.py` 时，动作 6 可能无效 |
| Habitat-Lab 和 Habitat-Sim 双栈都要认识动作 6 | 只改一边不够 |
| `actions.py` 的 v1 action config 未显式加入 `TURN_RIGHT_2` | 实际能否走通依赖 sim agent action_space 补丁和当前版本行为 |
| 动作 id 硬编码 | 重写时应将动作名作为协议，而不是散落数字 |

## 重写建议

1. 把动作定义集中成一个 `ActionSpec` 枚举。
2. 初始化 panorama 用动作名而不是数字。
3. 在启动时做 smoke test：`TURN_RIGHT_2` 是否存在、是否约等于 60 度。
4. 如果升级 Habitat，优先用官方 action space extension，而不是覆盖安装包文件。
