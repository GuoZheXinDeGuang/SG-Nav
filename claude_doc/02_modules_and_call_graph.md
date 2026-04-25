# 主要模块和 Call Graph

## 模块图

```text
                           +--------------------+
                           | configs/*.yaml     |
                           | Matterport/ObjectNav|
                           +----------+---------+
                                      |
                                      v
+--------------------+      +--------------------+      +-------------------+
| habitat Challenge  | ---> | SG_Nav_Agent       | ---> | Habitat action id |
| Benchmark/Env      |      | SG_Nav.py          |      | 0..6             |
+--------------------+      +----+----------+----+      +-------------------+
                                |          |
                                |          |
                 +--------------+          +----------------+
                 v                                      v
      +---------------------+              +-------------------------+
      | Semantic_Mapping    |              | SceneGraph              |
      | occupancy/free/room |              | 2D seg -> 3D graph      |
      +----------+----------+              +-----+--------+----------+
                 |                               |        |
                 v                               v        v
      +---------------------+             GLIP/GDINO/SAM  Ollama
      | FBE + FMMPlanner    |             Open3D/FAISS    LLM/VLM
      +---------------------+
```

## 启动 Call Graph

```text
main()
  parser: --visualize --split_l --split_r
  os.environ["CHALLENGE_CONFIG_FILE"] = configs/challenge_objectnav2021.local.rgbd.yaml
  habitat.get_config(config_paths)
  SG_Nav_Agent(config, args)
    init GLIPDemo
    init occupancy/free/room Semantic_Mapping
    load obj.npy / room.npy co-occurrence priors
    SceneGraph(...)
      init GroundingDINO + SAM
      init room nodes / prompts / cfg
  habitat.Challenge(eval_remote=False, split_l, split_r)
    Benchmark(config_paths, split_l, split_r)
    Env(config)
  challenge.submit(agent)
    Benchmark.local_evaluate(agent)
```

## Episode Call Graph

```text
Benchmark.local_evaluate
  while count_episodes < num_episodes:
    observations = env.reset()
    agent.reset()
      init_map()
      scenegraph.reset()
      read current_episode.object_category
    while not env.episode_over:
      action = agent.act(observations)
      observations = env.step(action)
      agent.update_metrics(env.get_metrics())
```

## 每步 `act()` Call Graph

```text
SG_Nav_Agent.act(observations)
  guard total_steps >= 500 -> STOP
  normalize depth / cache rgb

  scenegraph.set_*()
  scenegraph.update_scenegraph()
    segment2d()
    mapping3d()
    get_caption()
    update_node()
    update_edge()

  update_map()
    sem_map_module.forward(depth, full_pose, full_map)
  update_free_map()
    free_map_module.forward(depth, full_pose, fbe_free_map)

  initial panorama steps:
    LOOK_DOWN / TURN_RIGHT_2 / LOOK_UP
    detect_objects()
    update_room_map()

  scenegraph.perception()
    detect_objects()
    every 2 steps: GLIP room detection -> update_room_map()

  traversible, start, orientation = get_traversible()

  choose long-term goal:
    if found_goal:
      goal_map <- goal_gps
    elif found_possible_goal:
      goal_map <- possible_goal_temp_gps
    elif first_fbe or reached previous goal:
      goal_loc = fbe(traversible, start)
      if no frontier: set_random_goal()

  _plan(traversible, goal_map, full_pose, start, start_o, found_goal)
    collision update
    _get_stg()
      FMMPlanner.set_multi_goal()
      FMMPlanner.get_short_term_goal()
    deterministic local policy:
      STOP / MOVE_FORWARD / TURN_LEFT / TURN_RIGHT

  visualize()
  pointgoal_with_gps_compass <- get_relative_goal_gps()
  return {"action": number_action}
```

## Scene Graph Call Graph

```text
SceneGraph.update_scenegraph()
  segment2d()
    get_sam_segmentation_dense("groundedsam")
      GroundingDINO: boxes + captions from node_space
      SAM: masks from boxes
    append segment2d_results

  mapping3d()
    gobs_to_detection_list()
      resize/filter masks
      mask_subtract_contained()
      create_object_pcd(depth, mask, camera_matrix)
      transform pose into global frame
      process_pcd()
      get_bounding_box()
    compute_spatial_similarities()
    merge_detections_to_objects()
    filter_objects()

  get_caption()
    collect captions over detections
    mode caption -> object["captions"]

  update_node()
    existing object caption changed -> reset node edges
    object without node -> ObjectNode
    point cloud mean -> node.center
    room_map lookup -> node.room_node
    caption matches goal -> is_goal_node

  update_edge()
    connect new nodes to old/new nodes
    if same image: VLM relation query
    else: LLM relation proposal
    discriminate_relation()
```

## Frontier Scoring Call Graph

```text
SG_Nav_Agent.fbe()
  fbe_map <- free/unknown/obstacle map
  frontier_map <- boundary(free, unknown)
  FMMPlanner.set_goal(start)
  distances <- fmm_dist(frontiers)
  filter distance >= 1.6m
  scores <- scenegraph.score(frontier_locations)
    room score: room_map near frontier x room co-occurrence
    object score: obj_locations near frontier x object co-occurrence
    graph score:
      insert_goal()
        update_group()
        LLM predicts target room
        graph_corr(goal, group)
      boost frontiers near predicted group center
  scores += distance_inverse
  return best frontier
```

## 数据归属

| 数据 | 拥有者 | 生产者 | 消费者 |
| --- | --- | --- | --- |
| `observations` | Habitat Env | `env.reset/step` | agent、scenegraph、mapping |
| `full_map` | agent | `Semantic_Mapping.forward` | traversible、visualize、random goal |
| `fbe_free_map` | agent | `free_map_module.forward` | frontier、edge discrimination、visualize |
| `room_map` | agent | GLIP room detection + `room_map_module` | scenegraph room assignment、frontier score |
| `obj_locations` | agent | GLIP object detection | frontier object co-occurrence score |
| `segment2d_results` | scenegraph | GroundingDINO + SAM | mapping3d、goal mask lookup、joint image |
| `objects/objects_post` | scenegraph | 3D mapping/merge | node update |
| `nodes/edges` | scenegraph | update_node/update_edge | graph correlation、visualization |
| `goal_map` | agent | goal/fbe/random selection | FMMPlanner |
| metrics/results | Benchmark | Habitat measurements | logs、txt、json |
