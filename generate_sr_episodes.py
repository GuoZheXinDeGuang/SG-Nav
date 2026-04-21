"""
Generate SR-ObjectNav-L1 episodes: room-constrained ObjectNav episodes from MP3D.
Output format is compatible with Habitat's ObjectNav dataset loader.
"""

import json
import gzip
import os
import random
import numpy as np
from pathlib import Path
import habitat
from habitat.core.registry import registry
from habitat.tasks.nav.nav import NavigationEpisode

# --- Configuration ---
MP3D_SCENES_DIR = "/path/to/MatterPort3D/mp3d"   # contains e.g. 2azQ1b91cZZ/2azQ1b91cZZ.glb
ORIGINAL_OBJECTNAV_JSON = "/path/to/objectnav/mp3d/v1/val/val.json.gz"
OUTPUT_PATH = "data/sr_objectnav_l1/val.json.gz"

# Target (category, room) pairs — see Section 3.2 of the plan
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

NUM_PER_PAIR_PER_SCENE = 2     # keep small; multiply by pairs × scenes
MIN_START_TO_GOAL_DIST = 5.0   # meters (geodesic)
RANDOM_SEED = 42

# MP3D region label → SG-Nav room string (VERIFY against your .house files)
MP3D_TO_SGNAV_ROOM = {
    'b': 'bedroom',
    'l': 'living room',
    'a': 'bathroom',
    'k': 'kitchen',
    'd': 'dining room',
    'o': 'office room',
    'g': 'gym',
    'r': 'lounge',
    'u': 'laundry room',
}


def load_house_file(scene_id, mp3d_scenes_dir):
    """Parse the .house file for a scene. Returns regions and objects."""
    house_path = Path(mp3d_scenes_dir) / scene_id / f"{scene_id}.house"
    if not house_path.exists():
        return None, None
    
    regions = []   # list of dicts with fields: idx, label, bbox_min, bbox_max, level
    objects = []   # list of dicts with fields: idx, category, bbox_min, bbox_max, region_idx
    
    with open(house_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            tag = parts[0]
            # Region line: R region_idx level_idx 0 0 label px py pz x0 y0 z0 x1 y1 z1 ...
            if tag == 'R' and len(parts) >= 15:
                regions.append({
                    'idx': int(parts[1]),
                    'level': int(parts[2]),
                    'label': parts[5].strip('"'),
                    'bbox_min': [float(parts[9]), float(parts[10]), float(parts[11])],
                    'bbox_max': [float(parts[12]), float(parts[13]), float(parts[14])],
                })
            # Object line: O object_idx region_idx 0 category_idx px py pz x0 y0 z0 x1 y1 z1 ...
            elif tag == 'O' and len(parts) >= 14:
                objects.append({
                    'idx': int(parts[1]),
                    'region_idx': int(parts[2]),
                    'category_idx': int(parts[4]),
                    'position': [float(parts[5]), float(parts[6]), float(parts[7])],
                    'bbox_min': [float(parts[8]), float(parts[9]), float(parts[10])],
                    'bbox_max': [float(parts[11]), float(parts[12]), float(parts[13])],
                })
    
    return regions, objects


def load_category_mapping(scene_id, mp3d_scenes_dir):
    """MP3D has a category_mapping.tsv that maps category_idx to category name."""
    # Each scene's category index maps to human-readable category via a global mapping.
    # You need matterport3d's category_mapping.tsv (ships with the dataset).
    # This is dataset-specific. Placeholder — adapt to your data layout.
    mapping_path = Path(mp3d_scenes_dir).parent / "category_mapping.tsv"
    mapping = {}
    if mapping_path.exists():
        with open(mapping_path, 'r') as f:
            next(f)  # header
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    idx = int(parts[0])
                    name = parts[1].lower()
                    mapping[idx] = name
    return mapping


def get_objects_in_room_of_type(regions, objects, cat_mapping, obj_category, room_type):
    """Return list of (obj, region) tuples matching (category, room_type)."""
    matches = []
    for region in regions:
        mp3d_label = region['label']
        sg_room = MP3D_TO_SGNAV_ROOM.get(mp3d_label)
        if sg_room != room_type:
            continue
        # Find objects in this region with the target category
        for obj in objects:
            if obj['region_idx'] != region['idx']:
                continue
            cat_name = cat_mapping.get(obj['category_idx'], '')
            if obj_category in cat_name:
                matches.append((obj, region))
    return matches


def point_in_bbox(point, bbox_min, bbox_max):
    return all(bbox_min[i] <= point[i] <= bbox_max[i] for i in range(3))


def sample_start_position(regions, avoid_region_idx, sim=None):
    """Sample a navigable point NOT in the target room.
    
    For a full implementation, use habitat_sim.PathFinder to sample navigable points.
    Placeholder here: sample inside another room's bbox center with small perturbation.
    """
    candidate_regions = [r for r in regions 
                         if r['idx'] != avoid_region_idx 
                         and MP3D_TO_SGNAV_ROOM.get(r['label']) is not None]
    if not candidate_regions:
        return None
    chosen = random.choice(candidate_regions)
    center = [(chosen['bbox_min'][i] + chosen['bbox_max'][i]) / 2 for i in range(3)]
    # Add small noise
    center[0] += random.uniform(-0.5, 0.5)
    center[2] += random.uniform(-0.5, 0.5)
    return center


def generate_episodes(scene_list):
    random.seed(RANDOM_SEED)
    episodes = []
    episode_id = 0
    
    for scene_id in scene_list:
        regions, objects = load_house_file(scene_id, MP3D_SCENES_DIR)
        if regions is None:
            print(f"[WARN] No .house file for {scene_id}, skipping.")
            continue
        
        cat_mapping = load_category_mapping(scene_id, MP3D_SCENES_DIR)
        
        for obj_category, room_type in TARGET_PAIRS:
            matches = get_objects_in_room_of_type(
                regions, objects, cat_mapping, obj_category, room_type
            )
            if not matches:
                continue
            
            # Collect all target positions (any of these counts as success)
            all_target_positions = [m[0]['position'] for m in matches]
            target_region = matches[0][1]   # use first match's region as the "target room"
            
            # Collect distractors (same category, different rooms)
            distractors = []
            for obj in objects:
                cat_name = cat_mapping.get(obj['category_idx'], '')
                if obj_category in cat_name and obj['region_idx'] != target_region['idx']:
                    distractors.append(obj['position'])
            
            for k in range(min(NUM_PER_PAIR_PER_SCENE, len(matches))):
                start_pos = sample_start_position(regions, target_region['idx'])
                if start_pos is None:
                    continue
                
                episodes.append({
                    "episode_id": f"sr_l1_{episode_id:05d}",
                    "scene_id": f"mp3d/{scene_id}/{scene_id}.glb",
                    "start_position": start_pos,
                    "start_rotation": [0, 0, 0, 1],
                    "object_category": obj_category,
                    "info": {
                        "room_constraint": room_type,              
                        "goal_positions": all_target_positions,
                        "goal_room_bbox": {
                            "min": target_region['bbox_min'],
                            "max": target_region['bbox_max'],
                        },
                        "distractor_positions": distractors,
                    },
                    "goals": [{"position": p, "radius": None} 
                            for p in all_target_positions],
                })
                episode_id += 1
    
    return episodes


if __name__ == "__main__":
    # Read original val.json.gz to get list of MP3D scenes used for ObjectNav val
    with gzip.open(ORIGINAL_OBJECTNAV_JSON, 'rt') as f:
        original = json.load(f)
    
    val_scenes = list(set([ep['scene_id'].split('/')[-1].replace('.glb', '') 
                           for ep in original['episodes']]))
    print(f"Found {len(val_scenes)} val scenes")
    
    episodes = generate_episodes(val_scenes[:10])  # start small!
    print(f"Generated {len(episodes)} SR-ObjectNav-L1 episodes")
    
    # Save in Habitat-compatible format
    output = {
        "episodes": episodes,
        "category_to_task_category_id": original.get("category_to_task_category_id", {}),
        "category_to_mp3d_category_id": original.get("category_to_mp3d_category_id", {}),
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with gzip.open(OUTPUT_PATH, 'wt') as f:
        json.dump(output, f)
    print(f"Saved to {OUTPUT_PATH}")