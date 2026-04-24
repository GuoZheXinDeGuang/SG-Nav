"""
SR-ObjectNav-L1: room-constrained ObjectNav, built on top of Habitat MP3D episodes.
Uses .house file ONLY to look up which region each goal object is in.
"""
import json, gzip, os, glob, random
from pathlib import Path
from collections import defaultdict

# --- Config ---
MP3D_SCENES_DIR = "MatterPort3D/mp3d"
ORIGINAL_OBJECTNAV_DIR = "MatterPort3D/objectnav/mp3d/v1/val"
OUTPUT_PATH = "data/sr_objectnav_l1/val.json.gz"

TARGET_PAIRS = [
    ("chair",  "bedroom"),
    ("chair",  "living room"),
    ("sink",   "kitchen"),
    ("sink",   "bathroom"),
    ("bed",    "bedroom"),
    ("toilet", "bathroom"),
    ("sofa",   "living room"),
    ("table",  "dining room"),
]

NUM_PER_PAIR_PER_SCENE = 2
RANDOM_SEED = 42

# MP3D region label → room name. Full list per MP3D docs:
# https://github.com/niessner/Matterport/blob/master/data_organization.md#house-file-format
MP3D_TO_ROOM = {
    'a': 'bathroom',
    'b': 'bedroom',
    'c': 'closet',
    'd': 'dining room',
    'e': 'entryway',          # foyer/lobby
    'f': 'family room',
    'g': 'garage',
    'h': 'hallway',
    'i': 'library',
    'j': 'laundry room',
    'k': 'kitchen',
    'l': 'living room',
    'm': 'meeting room',
    'n': 'lounge',
    'o': 'office',
    'p': 'porch',             # terrace/deck
    'r': 'recreation',        # game room
    's': 'stairs',
    't': 'toilet',            # note: separate from bathroom in MP3D
    'u': 'utility room',
    'v': 'tv room',
    'w': 'workout room',      # gym
    'x': 'outdoor',
    'y': 'balcony',
    'z': 'other room',
}


def load_house(scene_id):
    """Returns dict: object_id -> region_label_string (e.g. 'bedroom')."""
    p = Path(MP3D_SCENES_DIR) / scene_id / f"{scene_id}.house"
    if not p.exists():
        return None

    regions = {}   # region_idx -> (label, bbox_min, bbox_max)
    obj_to_region = {}   # object_idx -> region_idx

    with open(p, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            tag = parts[0]
            if tag == 'R' and len(parts) >= 15:
                idx = int(parts[1])
                label = parts[5].strip('"')
                bmin = [float(parts[9]), float(parts[10]), float(parts[11])]
                bmax = [float(parts[12]), float(parts[13]), float(parts[14])]
                regions[idx] = (label, bmin, bmax)
            elif tag == 'O' and len(parts) >= 14:
                obj_idx = int(parts[1])
                reg_idx = int(parts[2])
                obj_to_region[obj_idx] = reg_idx
    return regions, obj_to_region


def point_in_bbox(p, bmin, bmax, margin=0.0):
    return all(bmin[i] - margin <= p[i] <= bmax[i] + margin for i in range(3))


def find_region_by_position(position, regions, xz_margin=0.3):
    """Fallback: match a 3D point to a region by bbox. Used when object_id mapping fails.
    We relax the Y (height) check because MP3D region bboxes sometimes don't include floor/ceiling cleanly.
    """
    candidates = []
    for ridx, (label, bmin, bmax) in regions.items():
        # XZ check with margin; Y check loose
        if (bmin[0] - xz_margin <= position[0] <= bmax[0] + xz_margin and
            bmin[2] - xz_margin <= position[2] <= bmax[2] + xz_margin and
            bmin[1] - 1.0 <= position[1] <= bmax[1] + 1.0):
            candidates.append(ridx)
    return candidates[0] if len(candidates) == 1 else None  # ambiguous → reject


def generate():
    random.seed(RANDOM_SEED)

    # Load original episode files
    content_files = sorted(glob.glob(os.path.join(ORIGINAL_OBJECTNAV_DIR, 'content', '*.json.gz')))
    print(f"Found {len(content_files)} scene files")

    with gzip.open(os.path.join(ORIGINAL_OBJECTNAV_DIR, 'val.json.gz'), 'rt') as f:
        top_level = json.load(f)

    all_new_episodes = []
    stats = defaultdict(int)        # (cat, room) -> count
    scene_stats = defaultdict(int)  # scene -> num episodes generated

    for cf in content_files:
        scene_id = Path(cf).stem.replace('.json', '')  # 2azQ1b91cZZ
        with gzip.open(cf, 'rt') as f:
            scene_data = json.load(f)

        house_info = load_house(scene_id)
        if house_info is None:
            print(f"[WARN] No .house for {scene_id}, skip")
            continue
        regions, obj_to_region = house_info

        # Build: (category, room) -> list of goal instances
        goals_by_cat_room = defaultdict(list)
        goals_by_category = scene_data.get('goals_by_category', {})

        for gkey, goal_list in goals_by_category.items():
            # gkey looks like "2azQ1b91cZZ.glb_cabinet"
            if not isinstance(goal_list, list):
                goal_list = [goal_list]
            for goal in goal_list:
                cat = goal['object_category']
                # Find region for this goal
                obj_id = goal.get('object_id')
                reg_idx = obj_to_region.get(obj_id) if obj_id is not None else None
                if reg_idx is None:
                    # Fallback: match by position
                    reg_idx = find_region_by_position(goal['position'], regions)
                if reg_idx is None or reg_idx not in regions:
                    continue
                label_char = regions[reg_idx][0]
                room = MP3D_TO_ROOM.get(label_char)
                if room is None:
                    continue
                goals_by_cat_room[(cat, room)].append({
                    'goal': goal,
                    'region_idx': reg_idx,
                    'region_bbox': (regions[reg_idx][1], regions[reg_idx][2]),
                })

        # Index episodes by category for quick start-position lookup
        eps_by_cat = defaultdict(list)
        for ep in scene_data['episodes']:
            eps_by_cat[ep['object_category']].append(ep)

        # For each (category, room) pair we want, generate episodes
        for cat, room in TARGET_PAIRS:
            matches = goals_by_cat_room.get((cat, room), [])
            if not matches:
                continue
            src_eps = eps_by_cat.get(cat, [])
            if not src_eps:
                continue

            # Target goal positions (all goals of THIS cat in THIS room)
            target_positions = [m['goal']['position'] for m in matches]
            # [SR-L1 P1-B] Collect bboxes for ALL matching rooms, not just the
            # first. A scene can have e.g. 2 bedrooms, each with a chair — the
            # old code recorded only bedroom #1's bbox as goal_room_bbox, so
            # stopping near a chair in bedroom #2 would be counted as
            # "wrong room" and Room-Accuracy was systematically underestimated.
            target_region_indices = list({m['region_idx'] for m in matches})
            target_room_bboxes = [
                (regions[idx][1], regions[idx][2]) for idx in target_region_indices
            ]

            # Distractors: same category, different room
            all_cat_goals = []
            for gkey, glist in goals_by_category.items():
                if isinstance(glist, list):
                    all_cat_goals.extend(g for g in glist if g['object_category'] == cat)
            distractor_positions = []
            for g in all_cat_goals:
                if g['position'] not in target_positions:
                    distractor_positions.append(g['position'])

            # Pick start positions from original episodes where start is NOT in
            # ANY of the target rooms (else episode is trivial).
            valid_starts = []
            for ep in src_eps:
                sp = ep['start_position']
                in_target = any(
                    point_in_bbox(sp, bmin, bmax, margin=0.3)
                    for bmin, bmax in target_room_bboxes
                )
                if not in_target:
                    valid_starts.append(ep)
            if not valid_starts:
                continue

            random.shuffle(valid_starts)
            for i, ep in enumerate(valid_starts[:NUM_PER_PAIR_PER_SCENE]):
                new_ep = {
                    "episode_id": f"sr_l1_{scene_id}_{cat}_{room}_{i}".replace(' ', '_'),
                    "scene_id": ep['scene_id'],
                    "start_position": ep['start_position'],
                    "start_rotation": ep['start_rotation'],
                    "object_category": cat,
                    "goals": [{"position": p, "radius": None} for p in target_positions],
                    "info": {
                        "room_constraint": room,
                        # [SR-L1 P1-B] goal_room_bbox is now a LIST of bboxes,
                        # one per target-room instance. Evaluation must check
                        # point-in-ANY-bbox. Single-bbox dict format is kept
                        # as `goal_room_bbox_legacy` for any older scripts.
                        "goal_room_bbox": [
                            {"min": list(bmin), "max": list(bmax)}
                            for bmin, bmax in target_room_bboxes
                        ],
                        "goal_room_bbox_legacy": {
                            "min": list(target_room_bboxes[0][0]),
                            "max": list(target_room_bboxes[0][1]),
                        },
                        "distractor_positions": distractor_positions,
                        "geodesic_distance": ep['info'].get('geodesic_distance'),
                    },
                }
                all_new_episodes.append(new_ep)
                stats[(cat, room)] += 1
                scene_stats[scene_id] += 1

    print(f"\nTotal episodes: {len(all_new_episodes)}")
    print("\nPer-pair counts:")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print("\nPer-scene counts:")
    for k, v in sorted(scene_stats.items()):
        print(f"  {k}: {v}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    output = {
        "episodes": all_new_episodes,
        "category_to_task_category_id": top_level.get("category_to_task_category_id", {}),
        "category_to_mp3d_category_id": top_level.get("category_to_mp3d_category_id", {}),
    }
    with gzip.open(OUTPUT_PATH, 'wt') as f:
        json.dump(output, f)
    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    generate()