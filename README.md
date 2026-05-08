# DS-GA 3001 Project: Using Scene Graph for VLM-based Zero-shot Object Navigation

Original Paper: https://arxiv.org/abs/2410.08189

## Installation

**Step 1 (Dataset)**

Download [Matterport3D scene dataset](https://niessner.github.io/Matterport/) and [object-goal navigation episodes dataset](https://github.com/facebookresearch/habitat-lab/blob/main/DATASETS.md) from [here](https://cloud.tsinghua.edu.cn/f/03e0ca1430a344efa72b/?dl=1).

Set your scene dataset path `SCENES_DIR` and episode dataset path `DATA_PATH` in config file `configs/challenge_objectnav2021.local.rgbd.yaml`.

The structure of the dataset is outlined as follows:
```
MatterPort3D/
├── mp3d/
│   ├── 2azQ1b91cZZ/
│   │   └── 2azQ1b91cZZ.glb
│   ├── 8194nk5LbLH/
│   │   └── 8194nk5LbLH.glb
│   └── ...
└── objectnav/
    └── mp3d/
        └── v1/
            └── val/
                ├── content/
                │   ├── 2azQ1b91cZZ.json.gz
                │   ├── 8194nk5LbLH.json.gz
                │   └── ...
                └── val.json.gz
```

**Step 2 (Environment)**

Create conda environment with python==3.9.
```
conda create -n SG_Nav python==3.9
```

**Step 3 (Simulator)**

Install habitat-sim==0.2.4 and habitat-lab.
```
conda install habitat-sim==0.2.4 -c conda-forge -c aihabitat
pip install -e habitat-lab
```
Then replace the `agent/agent.py` in the installed habitat-sim package with `tools/agent.py` in our repository.
```
HABITAT_SIM_PATH=$(pip show habitat_sim | grep 'Location:' | awk '{print $2}')
cp tools/agent.py ${HABITAT_SIM_PATH}/habitat_sim/agent/
```

**Step 4 (Package)**

Install pytorch<=1.9, pytorch3d and faiss. Install other packages.
```
conda install -c pytorch faiss-gpu=1.8.0
pip install torch==1.9.1+cu111 torchvision==0.10.1+cu111 -f https://download.pytorch.org/whl/torch_stable.html
pip install -r requirements.txt
conda install pytorch::pytorch pytorch::torchvision pytorch::pytorch-cuda=11.8 pytorch3d::pytorch3d -c pytorch -c nvidia -c pytorch3d -c conda-forge
```

Install Grounded SAM.
```
pip install -e segment_anything
pip install --no-build-isolation -e GroundingDINO
wget -O data/models/sam_vit_h_4b8939.pth https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
wget -O data/models/groundingdino_swint_ogc.pth https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth
```

Install GLIP model and download GLIP checkpoint.
```
cd GLIP
python setup.py build develop --user
mkdir MODEL
cd MODEL
wget https://huggingface.co/GLIPModel/GLIP/resolve/main/glip_large_model.pth
cd ../../
```

Install Ollama.
```
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2-vision
```

## Evaluation

Run SG-Nav:
```
python SG_Nav.py --visualize
```
