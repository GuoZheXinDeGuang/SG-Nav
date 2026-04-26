# SG-Nav 安装与使用速查

来源：论文 <https://arxiv.org/pdf/2410.08189>，代码 <https://github.com/GuoZheXinDeGuang/SG-Nav/>。流程：RGB-D -> GLIP/Grounded-SAM -> 3D scene graph -> Ollama/H-CoT 选 frontier -> FMM 动作。

## 环境

本机已验证：Ubuntu 24.04，RTX 4090，driver 560.35.05，`/opt/miniforge3`，`SG_Nav`，Python 3.9，`torch==1.9.1+cu111`。已解压 README 清华 val 数据：11 scenes，2195 episodes。

## 安装

```bash
cd /workspace/SG-Nav
source /opt/miniforge3/etc/profile.d/conda.sh
mamba create -y -n SG_Nav python=3.9 pip
conda activate SG_Nav

mamba install -y -c conda-forge -c aihabitat habitat-sim==0.2.4 libopengl
pip install -e habitat-lab
HABITAT_SIM_PATH=$(python -m pip show habitat-sim | awk '/Location:/ {print $2}')
cp tools/agent.py "$HABITAT_SIM_PATH/habitat_sim/agent/agent.py"

pip install torch==1.9.1+cu111 torchvision==0.10.1+cu111 -f https://download.pytorch.org/whl/torch_stable.html
mamba install -y -c pytorch -c conda-forge faiss-gpu=1.8.0
pip install -r requirements.txt
pip install -e segment_anything

mamba install -y -c nvidia -c conda-forge cuda-nvcc=11.8 cuda-cudart-dev=11.8 cuda-cccl=11.8 cuda-libraries-dev=11.8 gcc_linux-64=11 gxx_linux-64=11
pip install setuptools==59.5.0 timm==0.6.13
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CONDA_PREFIX/bin:$PATH"
export CC="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-gcc"
export CXX="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-g++"
export CUDAHOSTCXX="$CXX"
export TORCH_CUDA_ARCH_LIST="8.6+PTX"   # 非 Ampere/Ada GPU 可改
export MAX_JOBS=2
pip install --no-build-isolation -e GroundingDINO
(cd GLIP && python setup.py build develop)
pip install 'git+https://github.com/facebookresearch/pytorch3d.git@v0.6.2'
```

模型下载：

```bash
mkdir -p data/models GLIP/MODEL
wget -c -O data/models/sam_vit_h_4b8939.pth https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
wget -c -O data/models/groundingdino_swint_ogc.pth https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth
wget -c -O GLIP/MODEL/glip_large_model.pth https://huggingface.co/GLIPModel/GLIP/resolve/main/glip_large_model.pth
curl -fsSL https://ollama.com/install.sh | sh
ollama serve                    # 终端 A，常驻
ollama pull llama3.2-vision     # 终端 B
```

## 错误自纠

| 报错 | 修正 |
| --- | --- |
| `conda/mamba` 找不到 | `source /opt/miniforge3/etc/profile.d/conda.sh` |
| `libOpenGL.so.0` | 装 `libopengl` |
| GroundingDINO 报 CUDA/GCC | 用 CUDA 11.8、GCC 11、上面的 `export` |
| GLIP 找不到 `torch` | `pip install setuptools==59.5.0` 后重编 |
| `torch.fx` 报错 | `pip install timm==0.6.13` |
| `segment_anything` 导入失败 | 本仓库已加 `segment_anything/__init__.py` |
| Ollama 无 systemd | 手动开 `ollama serve` |
| 单独 import `_C` 找 `libc10.so` | 先 `import torch` |

## 数据与运行

这个报错：

```text
FileNotFoundError: MatterPort3D/objectnav/mp3d/v1/val/val.json.gz
```

就是缺 README 里的 `MatterPort3D/` 数据。默认配置按当前仓库根目录找：

```text
/workspace/SG-Nav/MatterPort3D/
```

最快方式：用 SG-Nav README 的清华镜像包，约 634MB，解压后约 666MB，包含 11 个 val 场景和 ObjectNav val episodes。

```bash
cd /workspace/SG-Nav
wget -c -O /workspace/MatterPort3D.zip 'https://cloud.tsinghua.edu.cn/f/03e0ca1430a344efa72b/?dl=1'
unzip -q -o /workspace/MatterPort3D.zip -d /workspace/SG-Nav
```

解压后应有：

```text
MatterPort3D/mp3d/2azQ1b91cZZ/2azQ1b91cZZ.glb
MatterPort3D/objectnav/mp3d/v1/val/val.json.gz
MatterPort3D/objectnav/mp3d/v1/val/content/2azQ1b91cZZ.json.gz
```

检查：

```bash
test -f MatterPort3D/objectnav/mp3d/v1/val/val.json.gz
find MatterPort3D/mp3d -name '*.glb' | wc -l    # 清华包应为 11
```

如果不用默认位置，就改 `configs/challenge_objectnav2021.local.rgbd.yaml`：

```yaml
DATA_PATH: /path/to/MatterPort3D/objectnav/mp3d/v1/{split}/{split}.json.gz
SCENES_DIR: /path/to/MatterPort3D/
```

官方完整 MP3D 需要授权：去 <https://niessner.github.io/Matterport/> 申请，用 Matterport3D 官方脚本下载 Habitat `.glb` 场景；ObjectNav episodes 也可用 Habitat 链接下载：`https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/m3d/v1/objectnav_mp3d_v1.zip`。注意这里 URL 里是 `m3d`，不是 `mp3d`。

```bash
source /opt/miniforge3/etc/profile.d/conda.sh
conda activate SG_Nav
cd /workspace/SG-Nav
ollama serve                                  # 终端 A
python SG_Nav.py --split_l 0 --split_r 11     # 终端 B
python SG_Nav.py --visualize --split_l 0 --split_r 11
```

自检：

```bash
python SG_Nav.py --help
python - <<'PY'
import torch, habitat, habitat_sim, faiss, open3d, skfmm, pytorch3d
import groundingdino._C, maskrcnn_benchmark._C
from segment_anything import sam_model_registry
print("ok", torch.__version__, torch.cuda.is_available())
PY
```
