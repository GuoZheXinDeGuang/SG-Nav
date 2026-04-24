"""
Evaluation loop for SR-ObjectNav-L1.
Reports Room-Success (main), Object-Success, Room-Accuracy, SPL.
"""

import argparse
import gzip
import json
import os
import numpy as np
import habitat
import habitat_sim  

from SG_Nav import SG_Nav_Agent


def is_point_in_bbox(point, bbox):
    """Check if a 3D point is inside a bbox dict with 'min' and 'max'."""
    mn, mx = bbox['min'], bbox['max']
    return all(mn[i] <= point[i] <= mx[i] for i in range(3))


def is_point_in_any_bbox(point, bbox_or_list):
    """[SR-L1 P1-B] Accept either the legacy single-bbox dict OR a list of
    bbox dicts (new format from generate_sr_episodes.py). Returns True iff
    the point is inside at least one bbox. A scene can have multiple rooms
    of the target type (two bedrooms, two bathrooms) and stopping near a
    target in any of them should count as Room-Success."""
    if bbox_or_list is None:
        return False
    if isinstance(bbox_or_list, dict):
        return is_point_in_bbox(point, bbox_or_list)
    if isinstance(bbox_or_list, list):
        return any(is_point_in_bbox(point, b) for b in bbox_or_list)
    return False


def compute_geodesic_distance(sim, pos_a, pos_b):
    """Compute geodesic (navigable) distance between two 3D points."""
    path = habitat_sim.ShortestPath() 
    
    path.requested_start = pos_a
    path.requested_end = pos_b
    found = sim.pathfinder.find_path(path)
    return path.geodesic_distance if found else np.inf


def evaluate(config_path, output_path, use_room_constraint):
    """
    use_room_constraint: 
        True  → use the episode's room_constraint (our method)
        False → force agent.goal_room = None (baseline)
    """
    os.environ["CHALLENGE_CONFIG_FILE"] = config_path
    config = habitat.get_config(config_path)
    
    # Build an args namespace the agent expects
    class Args:
        visualize = False
        split_l = -1
        split_r = -1
    
    agent = SG_Nav_Agent(task_config=config, args=Args())
    env = habitat.Env(config=config)
    agent.simulator = env  # SG-Nav reads from self.simulator._env.current_episode
    
    results = []
    num_episodes = len(env.episodes)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"Directory {output_dir} ensures exists.")
    
    for ep_idx in range(num_episodes):
        obs = env.reset()
        agent.reset()
        
        # Baseline: forcibly wipe room constraint to get vanilla SG-Nav behavior
        if not use_room_constraint:
            agent.goal_room = None
            agent.scenegraph.goal_room = None
        
        episode = env.current_episode
        info = getattr(episode, 'info', {}) or {}
        
        start_pos = np.array(episode.start_position)
        goal_positions = [np.array(g['position']) for g in episode.goals]
        # input(goal_positions)
        goal_room_bbox = info.get('goal_room_bbox')
        
        # Shortest-path reference length (min over all targets)
        # sim.pathfinder must be available
        sim = env.sim
        shortest_path_lens = [
            compute_geodesic_distance(sim, start_pos, g) for g in goal_positions
        ]
        best_sp = min(shortest_path_lens) if shortest_path_lens else np.inf
        
        path_length = 0.0
        prev_pos = start_pos
        stopped = False
        step = 0

        # [SR-L1 P1-E] Per-step distance-to-nearest-goal trace. Useful for
        # distinguishing "agent was walking straight at the goal but stopped
        # too early" from "agent was orbiting distractors and never got
        # close". Also embedded into per-episode record so the .tmp file
        # captures the full trajectory signal, not just the final snapshot.
        def dist_to_nearest_goal(pos):
            if not goal_positions:
                return float('inf')
            return float(min(np.linalg.norm(pos - g) for g in goal_positions))

        dist_trace = []  # list of (step, dist_to_nearest_goal_in_meters)
        start_dist = dist_to_nearest_goal(start_pos)
        dist_trace.append((0, start_dist))
        print(f"[SR-L1 dist] ep_{ep_idx} step=0 dist_to_nearest_goal={start_dist:.2f}m (start)")

        while not env.episode_over and step < 500:
            action_dict = agent.act(obs)
            action = action_dict['action']
            if action == 0:  # STOP
                stopped = True
                break
            obs = env.step(action)
            cur_pos = np.array(env.sim.get_agent_state().position)
            path_length += np.linalg.norm(cur_pos - prev_pos)
            prev_pos = cur_pos
            step += 1

            # [SR-L1 P1-E] log every step; to keep stdout manageable we print
            # only every 25 steps, but we record every step in dist_trace so
            # the .tmp file carries the full signal.
            d = dist_to_nearest_goal(cur_pos)
            dist_trace.append((step, d))
            if step % 25 == 0:
                print(f"[SR-L1 dist] ep_{ep_idx} step={step} "
                      f"dist_to_nearest_goal={d:.2f}m path_len={path_length:.2f}m")
        
        agent_pos = np.array(env.sim.get_agent_state().position)
        
        # Compute metrics
        close_to_goal = any(
            np.linalg.norm(agent_pos - g) < 1.0 for g in goal_positions
        )
        in_correct_room = (is_point_in_any_bbox(agent_pos, goal_room_bbox)
                           if goal_room_bbox else False)
        room_success = close_to_goal and in_correct_room

        # [SR-L1 P1-D] stop-position diagnostic: when agent STOPs but misses,
        # print per-goal distances and whether it was a near miss. Helps
        # distinguish "wrong object entirely" (>3m) from "close but not
        # within 1m threshold" (1.0-1.5m) from "depth/mask error" (<1m but
        # still registers False due to floating point).
        goal_dists = [float(np.linalg.norm(agent_pos - g)) for g in goal_positions]
        min_goal_dist = min(goal_dists) if goal_dists else float('inf')
        print(f"[SR-L1 stop] ep_{ep_idx} agent_pos={agent_pos.tolist()} "
              f"min_goal_dist={min_goal_dist:.2f}m "
              f"all_dists={[round(d,2) for d in goal_dists]} "
              f"in_room={in_correct_room} close={close_to_goal}")
        
        spl = 0.0
        if room_success and path_length > 0 and best_sp != np.inf:
            spl = best_sp / max(path_length, best_sp)
        
        results.append({
            "episode_id": info.get("episode_id", f"ep_{ep_idx}"),
            "scene": episode.scene_id,
            "object_category": episode.object_category,
            "room_constraint": info.get("room_constraint"),
            "close_to_goal": bool(close_to_goal),
            "in_correct_room": bool(in_correct_room),
            "room_success": bool(room_success),
            "spl": float(spl),
            "steps": step,
            "path_length": float(path_length),
            "shortest_path": float(best_sp) if best_sp != np.inf else None,
            # [SR-L1 P1-E] distance-to-nearest-goal telemetry
            "dist_at_start": float(start_dist),
            "dist_at_stop": float(min_goal_dist),
            "dist_min_over_trajectory": float(min(d for _, d in dist_trace)),
            "dist_trace": [[s, round(d, 3)] for s, d in dist_trace],
        })

        # realtime updates:
        tmp_output_path = output_path + ".tmp"
        with open(tmp_output_path, 'w') as tmp_f:
            json.dump({
                "current_progress": f"{ep_idx + 1}/{num_episodes}",
                "per_episode": results 
            }, tmp_f, indent=2)
        
        print(f"[{ep_idx+1}/{num_episodes}] {episode.object_category} in "
              f"{info.get('room_constraint')}: "
              f"RoomSR={room_success} ObjSR={close_to_goal} "
              f"InRoom={in_correct_room} steps={step}")
    
    env.close()
    
    # Aggregate
    summary = {
        "num_episodes": len(results),
        "room_success_rate": np.mean([r["room_success"] for r in results]),
        "object_success_rate": np.mean([r["close_to_goal"] for r in results]),
        "room_accuracy": np.mean([r["in_correct_room"] for r in results]),
        "spl": np.mean([r["spl"] for r in results]),
    }
    
    output = {"summary": summary, "per_episode": results}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nSaved detailed results to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/sr_objectnav_l1.yaml")
    parser.add_argument("--output", required=True)
    parser.add_argument("--baseline", action="store_true",
                        help="If set, disable room constraint (run as vanilla SG-Nav)")
    args = parser.parse_args()
    
    evaluate(
        config_path=args.config,
        output_path=args.output,
        use_room_constraint=not args.baseline,
    )