# SG-Nav 环境安装与阅读日志

## 2026-04-25 01:48:31 UTC

### 阅读/确认

- 本地工作目录：`/workspace/SG-Nav`。
- 本地 remote：`origin https://github.com/GuoZheXinDeGuang/SG-Nav`。
- 已打开并开始阅读论文 `https://arxiv.org/pdf/2410.08189`、上游项目 `https://github.com/bagh2178/SG-Nav`、我们的仓库 `https://github.com/GuoZheXinDeGuang/SG-Nav`。
- 论文方法主线：在线构建 hierarchical 3D scene graph，把 object/group/room 级上下文交给 LLM 做 frontier 评分，并用 graph-based re-perception 降低误检目标带来的失败。
- README 安装要求：Python 3.9 conda 环境、`habitat-sim==0.2.4`、editable `habitat-lab`、复制 `tools/agent.py` 到安装后的 `habitat_sim/agent/`、安装 PyTorch/FAISS/PyTorch3D、Grounded-SAM、GLIP checkpoint、Ollama `llama3.2-vision`。

### 当前终端可见环境

- CPU：AMD Ryzen Threadripper PRO 5955WX 16 核 32 线程。
- 内存：约 94GiB。
- GPU：NVIDIA GeForce RTX 5070 Ti，约 16GiB 显存，driver `570.133.07`。
- OS：Ubuntu Linux，kernel `5.15.0-171-generic`。
- 当前 shell 中未发现 `python`、`conda`、`mamba`、`micromamba`；系统 `pip` 指向 Python 3.12。

### 环境操作计划

1. 安装一个本地隔离的 conda 兼容工具 `micromamba`，避免污染系统 Python 3.12。
2. 创建 `SG_Nav` Python 3.9 环境。
3. 按 README 安装 Habitat-Sim/Habitat-Lab 和项目 Python 依赖。
4. 对 README 中可能与 RTX 5070 Ti 不兼容的旧 CUDA/PyTorch 组合做记录；如果安装失败，记录失败命令和原因，再选择最接近项目要求的可运行方案。

### 环境更新

- 准备安装本地 `micromamba`：下载 `https://micro.mamba.pm/api/micromamba/linux-64/latest`，解压到 `/workspace/.local/bin/micromamba`，后续 conda 环境根目录使用 `/workspace/.micromamba`。
- 结果：`micromamba 2.5.0` 已安装到 `/workspace/.local/bin/micromamba`。
- 准备创建项目环境：`MAMBA_ROOT_PREFIX=/workspace/.micromamba /workspace/.local/bin/micromamba create -y -n SG_Nav python=3.9 -c conda-forge`。
- 结果：`SG_Nav` 环境创建成功，实际环境路径为 `/venv/SG_Nav`，Python 版本为 `3.9.23`。`micromamba info` 显示 envs directories 优先包含 `/venv`，所以虽然 root prefix 是 `/workspace/.micromamba`，命名环境落在 `/venv/SG_Nav`。
- 准备按 README 安装模拟器：`micromamba install -n SG_Nav -y habitat-sim==0.2.4 -c conda-forge -c aihabitat`。
- 结果：`habitat-sim==0.2.4` 安装成功，包来自 `aihabitat`，环境路径 `/venv/SG_Nav`。
- 验证：执行 `import habitat_sim` 失败，错误为 `ImportError: libOpenGL.so.0: cannot open shared object file`。这是运行库缺失，不是 Python 包本身缺失。
- 准备修复 OpenGL 运行库：`micromamba install -n SG_Nav -y libopengl libglvnd -c conda-forge`。
- 结果：`libopengl 1.7.0` 和 `libglvnd 1.7.0` 安装成功。
- 验证：`import habitat_sim` 成功，模块路径为 `/venv/SG_Nav/lib/python3.9/site-packages/habitat_sim-0.2.4-py3.9-linux-x86_64.egg/habitat_sim/__init__.py`。
- 准备按 README 安装本地 Habitat-Lab：`micromamba run -n SG_Nav pip install -e habitat-lab`。
- 结果：`habitat-lab` editable 安装成功，安装包名/版本显示为 `habitat==0.2.1`，同时安装 `gym 0.26.2`、`opencv-python 4.11.0.86`、`yacs 0.1.8` 等依赖。
- 准备按 README 替换 Habitat-Sim agent：先定位 `habitat_sim` 安装目录，备份原始 `habitat_sim/agent/agent.py`，再用仓库的 `tools/agent.py` 覆盖，以支持动作 id `6` 的 60 度右转。
- 结果：已备份原始文件到 `habitat_sim/agent/agent.py.bak_sgnav_20260425`，并用 `tools/agent.py` 覆盖。验证 `Agent.__init__` 中存在 `action_space[6]` 和 `60.0`，补丁生效。
- 准备按 README 安装 FAISS GPU：`micromamba install -n SG_Nav -y -c pytorch faiss-gpu=1.8.0`。
- 结果：`faiss-gpu 1.8.0` 安装成功，同时安装 `cudatoolkit 11.8.0`、`libfaiss 1.8.0` 等包。安装过程中出现 NVIDIA CUDA Toolkit EULA 提示，属于 conda 包说明。
- 准备按 README 安装旧版 PyTorch wheel：`pip install torch==1.9.1+cu111 torchvision==0.10.1+cu111 -f https://download.pytorch.org/whl/torch_stable.html`。注意：这与后续 README 中 `pytorch-cuda=11.8` 命令存在版本冲突，且 RTX 5070 Ti 较新，旧 CUDA/PyTorch 可能不能充分支持该 GPU；先按项目要求尝试并记录结果。
- 结果：`torch 1.9.1+cu111` 和 `torchvision 0.10.1+cu111` 安装成功。
- 验证：`torch.cuda.is_available()` 返回 `True`，设备名为 `NVIDIA GeForce RTX 5070 Ti`，但 PyTorch 警告该 GPU 的 `sm_120` 不被当前 PyTorch 支持；当前 wheel 只支持 `sm_37 sm_50 sm_60 sm_70 sm_75 sm_80 sm_86`。一次简单 CUDA tensor 测试长时间无返回，已手动终止对应测试进程。因此旧版 README torch 组合不适合这张 RTX 5070 Ti 做 GPU 计算。
- 准备继续按 README 安装通用 Python 依赖：`pip install -r requirements.txt`。
- 结果：`requirements.txt` 安装成功。主要新增包括 `transformers 4.30.0`、`pslpython 2.3.3`、`open3d 0.19.0`、`ollama 0.6.1`、`scikit-image 0.24.0`、`scikit-learn 1.6.1`、`scikit-fmm 2025.1.29`、`pandas 2.3.3`、`omegaconf 2.3.0` 等。`scikit-fmm` 和 `antlr4-python3-runtime` 均已成功本地构建 wheel。
- 准备执行 README 中后续 PyTorch/PyTorch3D conda 命令：`micromamba install -n SG_Nav -y pytorch::pytorch pytorch::torchvision pytorch::pytorch-cuda=11.8 pytorch3d::pytorch3d -c pytorch -c nvidia -c pytorch3d -c conda-forge`。该命令预计会覆盖前面 pip 安装的旧版 PyTorch。
- 结果：该 conda transaction 解析到 `pytorch 2.4.1 + CUDA 11.8 + torchvision 0.19.1 + pytorch3d 0.7.8`，但链接 `torch/lib/libcudnn_engines_precompiled.so.9` 时失败：`No space left on device`。失败时根分区 32G 已满。
- 清理：删除 `/workspace/.micromamba/pkgs`、`/root/.cache/pip`、`/tmp/pip-*` 后，根分区恢复到约 19G 可用。当前环境中残留一个不完整的 `/venv/SG_Nav/lib/python3.9/site-packages/torch`，大小约 4.9G，`import torch` 失败：`ModuleNotFoundError: No module named 'torch.torch_version'`。
- 准备删除不完整的 torch/torchvision 目录并重试同一个 conda PyTorch/PyTorch3D 命令。
- 清理结果：删除残留 torch/torchvision 后，环境大小从约 12G 降到约 7.1G，根分区可用空间约 24G。
- 重试结果：README 的 conda PyTorch/PyTorch3D 命令安装成功。最终版本：`torch 2.4.1`、CUDA build `11.8`、`torchvision 0.19.1`、`pytorch3d 0.7.8`。
- 验证：`torch`、`torchvision`、`pytorch3d` 均可 import；`torch.cuda.is_available()` 为 `True`，简单 `torch.ones(1, device="cuda")` 成功。但 PyTorch 仍警告 RTX 5070 Ti 的 `sm_120` 不在该构建支持列表中；当前构建支持到 `sm_90/compute_37`。因此基础 CUDA tensor 可跑，但后续复杂 CUDA kernel 仍可能遇到架构兼容问题。
- 系统 CUDA 编译器：`/usr/local/cuda/bin/nvcc` 存在，版本 `12.8.93`；这与当前 PyTorch CUDA build `11.8` 不一致，编译 GroundingDINO CUDA extension 时可能触发 CUDA 版本不匹配。
- 准备按 README 安装 Segment Anything：`pip install -e segment_anything`。
- 结果：`segment_anything 1.0` editable 安装成功。
- 准备按 README 安装 GroundingDINO：`pip install --no-build-isolation -e GroundingDINO`。预期风险：GroundingDINO `setup.py` 会在 `torch.cuda.is_available()` 且 `CUDA_HOME` 存在时编译 CUDA extension；本机 `nvcc 12.8` 与 PyTorch `cu118` 可能不匹配。
- 结果：GroundingDINO 原命令失败。失败原因：`RuntimeError: The detected CUDA version (12.8) mismatches the version that was used to compile PyTorch (11.8)`。
- 准备修复 GroundingDINO 编译器版本：安装与 PyTorch `cu118` 匹配的环境内 nvcc：`micromamba install -n SG_Nav -y cuda-nvcc=11.8 -c nvidia -c conda-forge`，之后用 `CUDA_HOME=/venv/SG_Nav` 和 `/venv/SG_Nav/bin` 优先的 `PATH` 重试 GroundingDINO。
- 结果：`cuda-nvcc 11.8.89` 安装成功。
- 准备重试 GroundingDINO：使用 `CUDA_HOME=/venv/SG_Nav`、`PATH=/venv/SG_Nav/bin:$PATH`，并设置 `TORCH_CUDA_ARCH_LIST="8.6;9.0+PTX"`，避免 nvcc 11.8 尝试编译不支持的 `sm_120` 架构。
- 结果：GroundingDINO 第二次编译失败，但已越过 CUDA 版本不匹配。新错误为缺少 CUDA headers：`fatal error: cuda_runtime.h: No such file or directory` 和 `cuda_runtime_api.h: No such file or directory`。
- 准备补 CUDA runtime headers：`micromamba install -n SG_Nav -y cuda-cudart-dev=11.8 -c nvidia -c conda-forge`。
- 结果：`cuda-cudart-dev 11.8.89` 安装成功，同时安装 `cuda-cccl 12.4.127`。
- 准备第三次重试 GroundingDINO，仍使用 `CUDA_HOME=/venv/SG_Nav`、环境内 `nvcc 11.8` 和 `TORCH_CUDA_ARCH_LIST="8.6;9.0+PTX"`。
- 结果：GroundingDINO 第三次编译失败。新错误包括：`cusparse.h: No such file or directory`，以及 nvcc 11.8 拒绝当前系统 GCC：`unsupported GNU version! gcc versions later than 11 are not supported`。
- 准备继续补编译环境：安装 CUDA 11.8 dev libraries 和 GCC/G++ 11：`micromamba install -n SG_Nav -y cuda-libraries-dev=11.8 gcc_linux-64=11 gxx_linux-64=11 -c nvidia -c conda-forge`。
- 结果：`cuda-libraries-dev 11.8.0`、CUDA 11.8 的 cuBLAS/cuSPARSE/cuRAND/cuSOLVER/cuFFT 等 dev headers/libraries，以及 conda GCC/G++ 11 安装成功。环境中已有 `/venv/SG_Nav/bin/nvcc` 11.8 和 `/venv/SG_Nav/bin/x86_64-conda-linux-gnu-cc/c++`。
- 磁盘状态：根分区约 32G，总可用约 6.3G；`/workspace/.micromamba` 包缓存约 11G，`/venv/SG_Nav` 环境约 14G。准备先清理 micromamba/pip 缓存再继续编译 GroundingDINO。
- 清理结果：执行 `micromamba clean -a -y` 并删除 `/root/.cache/pip`、`/tmp/pip-*` 后，根分区可用空间从约 6.3G 恢复到约 18G；`/workspace/.micromamba` 包缓存降到约 4K，`/venv/SG_Nav` 环境约 14G。
- 准备第四次重试 GroundingDINO：使用环境内 CUDA 11.8、conda GCC/G++ 11，设置 `CUDA_HOME=/venv/SG_Nav`、`CC=/venv/SG_Nav/bin/x86_64-conda-linux-gnu-cc`、`CXX=/venv/SG_Nav/bin/x86_64-conda-linux-gnu-c++`、`TORCH_CUDA_ARCH_LIST="8.6;9.0+PTX"`、`MAX_JOBS=4`。
- 结果：GroundingDINO editable 安装成功，版本 `groundingdino 0.1.0`。本次新增/更新依赖包括 `timm 1.0.26`、`supervision 0.27.0.post2`、`pycocotools 2.0.11`、`yapf 0.43.0`、`matplotlib 3.9.4` 等；此前由系统 `nvcc 12.8`、缺 CUDA headers、缺 cuSPARSE headers、系统 GCC 13 引起的问题均已解决。
- 准备验证关键 Python 包 import：`torch`/CUDA、`pytorch3d`、`habitat_sim`、`habitat`、`segment_anything`、`groundingdino`。
- 验证结果：`torch 2.4.1`、`torchvision 0.19.1`、`pytorch3d 0.7.8`、`habitat_sim 0.2.4`、`habitat 0.2.1`、`segment_anything`、`groundingdino` 均可 import；`groundingdino._C` CUDA/C++ 扩展可 import；简单 CUDA tensor 可创建。仍保留 PyTorch 对 RTX 5070 Ti `sm_120` 的兼容性警告，说明当前 cu118 构建可做基础 CUDA 调用，但不保证所有新架构 kernel 都完全兼容。
- 准备处理 README 的 GLIP 安装：检查 `GLIP/setup.py` 和相关依赖，优先安装到 `SG_Nav` 环境内，而不是污染系统 Python。
- GLIP 依赖确认：`GLIP/README.md` 要求 `einops shapely timm yacs tensorboardX ftfy prettytable pymongo transformers`，并执行 `python setup.py build develop --user`；本仓库 README 还要求下载 `GLIP/MODEL/glip_large_model.pth`。
- 准备安装 GLIP Python 依赖：在 `SG_Nav` 环境中执行 `pip install einops shapely timm yacs tensorboardX ftfy prettytable pymongo transformers`。
- 结果：GLIP Python 依赖安装成功；新增 `shapely 2.0.7`、`tensorboardX 2.6.5`、`pymongo 4.17.0`、`dnspython 2.7.0`、`protobuf 6.33.6`，其余依赖已存在。
- 准备编译/安装 GLIP：README 使用 `python setup.py build develop --user`，但当前使用隔离的 `SG_Nav` 环境，因此改为在环境内执行 `python setup.py build develop`，避免安装到 root 用户 site-packages；编译环境沿用 CUDA 11.8、conda GCC/G++ 11 和 `TORCH_CUDA_ARCH_LIST="8.6;9.0+PTX"`。
- 结果：GLIP 第一次编译失败。失败点为 `GLIP/maskrcnn_benchmark/csrc/cuda/ROIAlign_cuda.cu` 中 `#include <THC/THC.h>`；PyTorch 2.4 已移除旧 THC 头文件，错误为 `fatal error: THC/THC.h: No such file or directory`。
- 兼容性修补：新增 `GLIP/maskrcnn_benchmark/csrc/cuda/thc_compat.h`，用 `C10_CUDA_CHECK` 和 `cuda_runtime.h` 替代旧 THC 的 `THCudaCheck`/`THCCeilDiv`；移除 GLIP CUDA 源码里的 `THC/THC.h`、`THCAtomics.cuh`、`THCDeviceUtils.cuh` include；把 `nms.cu`/`ml_nms.cu` 中的旧 `THCudaMalloc/THCudaFree` 改为 `cudaMalloc/cudaFree`。
- 准备清理 GLIP 上次失败留下的 `build/` 后再次编译。
- 结果：GLIP 第二次编译越过 THC include 问题，但在 `deform_conv_kernel_cuda.cu` 失败：`atomicAdd(c10::Half*, c10::Half)` 无匹配重载。原因是该文件用 `AT_DISPATCH_FLOATING_TYPES_AND_HALF` 生成 half 特化，而当前 kernel 中的 half atomic add 不兼容。
- 兼容性修补：将 GLIP deformable conv/pool CUDA kernel 中的 `AT_DISPATCH_FLOATING_TYPES_AND_HALF` 改为 `AT_DISPATCH_FLOATING_TYPES`，不编译 half 特化；这保持 float/double 可用，规避当前 half atomic 编译失败。
- 准备再次清理 `GLIP/build/` 后重编译 GLIP。
- 结果：GLIP 第三次编译和链接成功，生成 `GLIP/maskrcnn_benchmark/_C.cpython-39-x86_64-linux-gnu.so`。但 `python setup.py build develop` 的最后安装步骤失败：新版 setuptools `develop` 调用 `pip install -e . --use-pep517`，PEP517 隔离构建环境中没有 `torch`，因此在读取 `setup.py` 时 `ModuleNotFoundError: No module named 'torch'`。
- 准备使用 legacy editable 安装方式：`pip install --no-build-isolation --no-use-pep517 -e GLIP`，避免 PEP517 隔离环境。
- 结果：legacy editable 安装仍失败；`setup.py develop` 内部继续调用 `pip install -e . --use-pep517 --no-deps`，再次因为隔离环境没有 `torch` 失败。
- 处理方式：由于 GLIP 的 `_C.cpython-39-x86_64-linux-gnu.so` 已成功生成在源码目录，准备在 `SG_Nav` 环境的 `site-packages` 中添加 `.pth` 文件，把 `/workspace/SG-Nav/GLIP` 加入 Python 搜索路径，达到开发态可 import 的效果。
- 结果：已添加 `/venv/SG_Nav/lib/python3.9/site-packages/sg_nav_glip_editable.pth`，内容为 `/workspace/SG-Nav/GLIP`。
- 发现：源码目录原有一个旧的 `GLIP/maskrcnn_benchmark/_C.cpython-39-x86_64-linux-gnu.so`，Python 优先加载它，导致缺 `libtorch_cuda_cu.so/libtorch_cuda_cpp.so`。已备份旧文件为 `_C.cpython-39-x86_64-linux-gnu.so.bak_sgnav_20260425`，并把本次编译生成的 `build/lib.linux-x86_64-cpython-39/maskrcnn_benchmark/_C.cpython-39-x86_64-linux-gnu.so` 复制到源码包目录。
- 验证结果：先 `import torch` 后，`maskrcnn_benchmark`、`maskrcnn_benchmark._C`、`maskrcnn_benchmark.config.cfg` 均可 import。GLIP 代码已可在 `SG_Nav` 环境中以开发态使用。
- 磁盘状态：根分区约 18G 可用；`GLIP/build` 约 12M，pip cache 约 25M。准备按 README 下载模型权重：SAM ViT-H 到 `data/models/sam_vit_h_4b8939.pth`、GroundingDINO Swin-T 到 `data/models/groundingdino_swint_ogc.pth`、GLIP-L 到 `GLIP/MODEL/glip_large_model.pth`。
- 结果：SAM ViT-H checkpoint 下载成功：`data/models/sam_vit_h_4b8939.pth`，大小 `2564550879` bytes。
- 结果：GroundingDINO Swin-T OGC checkpoint 下载成功：`data/models/groundingdino_swint_ogc.pth`，大小 `693997677` bytes。
- 准备下载 GLIP-L checkpoint：`GLIP/MODEL/glip_large_model.pth`，来源为 README 指定的 HuggingFace URL。
- 结果：GLIP-L checkpoint 下载成功：`GLIP/MODEL/glip_large_model.pth`，大小 `6896153761` bytes。
- 磁盘状态：项目目录约 9.7G，`SG_Nav` 环境约 14G；当前 overlay 根分区约 32G，总可用约 7.6G。宿主机可见 `nvme0n1 1.7T` 和 `sda 3.6T`，但当前容器可写工作区仍受 32G overlay 限制。
- Ollama 状态：`requirements.txt` 已安装 Python `ollama` 包，但系统中还没有 `ollama` CLI。准备按 README 执行 `curl -fsSL https://ollama.com/install.sh | sh` 安装 CLI。
- 结果：Ollama CLI 安装成功，版本 `0.21.2`。安装脚本提示 systemd 未运行，所以不会自动常驻服务；需要手动执行 `ollama serve`。安装目录 `/usr/local/lib/ollama` 约 4.9G，包含 CUDA/vulkan/MLX 后端库。
- 磁盘限制：Ollama 安装后 overlay 根分区只剩约 2.7G，不够把 `llama3.2-vision` 持久拉到默认 `/root/.ollama`。准备临时使用 `/dev/shm/ollama_models` 作为 `OLLAMA_MODELS`，以完成 README 的模型 pull；该目录在当前容器会话内可用，但不是持久磁盘。
- 结果：手动启动 `OLLAMA_MODELS=/dev/shm/ollama_models OLLAMA_HOST=127.0.0.1:11434 ollama serve` 成功；Ollama 检测到 `NVIDIA GeForce RTX 5070 Ti`，CUDA compute `12.0`，可用显存约 15.5GiB。
- 结果：`ollama pull llama3.2-vision` 成功；`ollama list` 显示 `llama3.2-vision:latest`，ID `6f2f9757ae97`，大小约 `7.8 GB`。模型实际存储在 `/dev/shm/ollama_models`，目录占用约 7.3G；这是临时内存文件系统，当前容器会话结束后可能丢失。
- 清理：已停止本次临时启动的 `ollama serve` 进程。后续若要使用临时模型目录，需要重新执行 `OLLAMA_MODELS=/dev/shm/ollama_models OLLAMA_HOST=127.0.0.1:11434 ollama serve`。
- 集中验证：`torch 2.4.1`、CUDA `11.8`、`habitat_sim 0.2.4`、`habitat 0.2.1`、`faiss 1.8.0`、`pytorch3d 0.7.8`、`segment_anything`、`groundingdino._C`、`maskrcnn_benchmark._C`、Python `ollama` 包均可 import；简单 CUDA tensor 成功；三个视觉 checkpoint 文件存在且大小正确。
- 注意：PyTorch 仍对 RTX 5070 Ti 的 `sm_120` 给出兼容性警告，当前 cu118 构建支持列表到 `sm_90/compute_37`；基础 CUDA 调用可用，但后续自定义/复杂 kernel 仍需实测。
- 数据集状态：Matterport3D scene dataset 和 ObjectNav episodes 属于项目运行数据，README 给出下载入口，但 Matterport3D 通常涉及许可/账号且体积较大；当前未自动下载数据集。后续运行 SG-Nav 前需要按 README 配置 `data/scene_datasets/mp3d` 和 episodes 路径。
