---
name: kaggle-kernel-runner
description: >
  Push, monitor, debug, and iterate on Kaggle kernel notebooks using the kaggle
  CLI. Covers: nbformat notebook generation, kernel-metadata.json configuration
  (GPU/dataset), push->poll->debug->fix->repush cycle, dataset upload (with .sb3
  rename trick to prevent auto-extraction), papermill timeout avoidance, and
  output download. Use when the user wants to run a notebook on Kaggle cloud
  GPUs and iteratively fix errors until it succeeds.
agent_created: true
disable: false
---

# Kaggle Kernel Runner

Iterative workflow for pushing Python notebooks to Kaggle, monitoring execution, debugging errors, and downloading results.

## Core Commands

```bash
# Push notebook to Kaggle
kaggle kernels push -p <directory>

# Check status
kaggle kernels status <owner>/<kernel-slug>

# View logs (JSON-lines format with stream_name, time, data fields)
kaggle kernels logs <owner>/<kernel-slug>

# Download all output files
kaggle kernels output <owner>/<kernel-slug> -p <output-dir>
```

## Workflow: Push -> Poll -> Debug -> Fix -> Repush

### 1. Project Structure

```
my-kernel/
├── kernel-metadata.json    # Kaggle kernel configuration
├── my-kernel.ipynb         # Generated notebook
└── gen_notebook.py         # Python script that generates the .ipynb
```

### 2. kernel-metadata.json Template

```json
{
  "id": "<username>/<kernel-slug>",
  "title": "<kernel-title>",
  "code_file": "<kernel-slug>.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": true,
  "enable_internet": true,
  "machine_shape": "NvidiaTeslaT4",
  "dataset_sources": ["<username>/<dataset-slug>"],
  "docker_image": "docker.io/kaggle/python-gpu:latest"
}
```

**GPU options for `machine_shape`:**
- `"NvidiaTeslaT4"` - 2x T4 GPUs (16GB each), recommended for most tasks
- `"NvidiaL4x4"` - 4x L4 GPUs (only for competitions)
- Omit field for CPU-only

**Important:** `"dataset_sources"` array attaches Kaggle datasets as read-only input at `/kaggle/input/<dataset-slug>/`.

### 3. Generating Notebooks with nbformat

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()

cell1 = nbf.v4.new_code_cell(
    "import subprocess, sys, os\n"
    "# Install deps\n"
    "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'package'], check=True)\n"
)

cell2 = nbf.v4.new_code_cell("print('Hello from Kaggle!')")

nb.cells = [cell1, cell2]
nb.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3"
}

with open("my-kernel.ipynb", "w") as f:
    nbf.write(nb, f)
```

### 4. Poll Status Loop

```bash
# Check status (returns KernelWorkerStatus.QUEUED/RUNNING/COMPLETE/ERROR)
kaggle kernels status owner/kernel-slug

# Tail logs while running
kaggle kernels logs owner/kernel-slug 2>&1 | tail -c 3000
```

### 5. Log Parsing

Logs are JSON-lines with leading `[` on first line and `,` prefix on subsequent lines:
```python
import json
with open('kernel.log', 'r', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line.startswith(','): continue
        try:
            d = json.loads(line[1:])
            t = d.get('time', 0)
            data = d.get('data', '').strip()
            stream = d.get('stream_name', 'stdout')
            if data:
                print(f'[{t:8.2f}s] [{stream}] {data[:200]}')
        except: pass
```

### 6. Download Output

```bash
# Download all output files (videos, models, etc.)
kaggle kernels output owner/kernel-slug -p ./output/

# Only files in /kaggle/working/ are saved as output
```

## Critical Pitfalls

### Papermill IOPub Timeout

**Problem:** Kaggle uses papermill which kills the kernel if no output is produced for ~4 seconds (IOPub timeout).

**Solution:** For long-running training loops:
```python
from stable_baselines3 import PPO
model = PPO("CnnPolicy", env, verbose=1)
model.learn(
    total_timesteps=1_000_000,
    progress_bar=False,     # CRITICAL: disable tqdm (triggers timeout)
    log_interval=10         # print every 10 iterations to keep papermill alive
)
```

### Dataset Auto-Extraction (.zip files)

**Problem:** Kaggle automatically extracts `.zip`, `.tar.gz`, `.tar`, `.7z` files when uploaded as datasets. If you upload multiple model `.zip` files, they all get extracted into the same directory and overwrite each other.

**Solution:** Rename to a non-standard extension before uploading:
```bash
# Rename .zip -> .sb3 (or any custom extension)
for f in *.zip; do mv "$f" "${f%.zip}.sb3"; done

# Upload dataset
kaggle datasets version -p dataset-upload/ -m "description"

# In notebook, copy back to .zip:
import shutil
for src in glob.glob('/kaggle/input/**/*.sb3', recursive=True):
    dst = os.path.join(WORK_DIR, os.path.basename(src).replace('.sb3', '.zip'))
    shutil.copy2(src, dst)
```

### Dataset Upload Structure

```
dataset-upload/
├── dataset-metadata.json   # Required metadata
├── file1.sb3               # Files at root level (NO subdirectories!)
├── file2.sb3
└── file3.sb3
```

**dataset-metadata.json:**
```json
{
  "id": "<username>/<dataset-slug>",
  "title": "<dataset-title>",
  "licenses": [{"name": "other"}]
}
```

**Commands:**
```bash
# Create new dataset
kaggle datasets create -p dataset-upload/

# Update existing dataset (new version)
kaggle datasets version -p dataset-upload/ -m "version message"

# With subdirectories (zips them):
kaggle datasets version -p dataset-upload/ --dir-mode zip -m "msg"
```

**Important:** Flat file structure is preferred. Subdirectories get skipped unless `--dir-mode zip` is used.

### Kaggle CLI Auth Inside Kernels

**Problem:** `kaggle kernels output` and other API calls don't work inside a Kaggle kernel because there's no CLI authentication.

**Solution:** Use datasets as the transfer mechanism between kernels instead of the API.

### GPU Detection

```python
import torch
print(f'GPU count: {torch.cuda.device_count()}')
for i in range(torch.cuda.device_count()):
    print(f'  GPU {i}: {torch.cuda.get_device_name(i)}')
# With NvidiaTeslaT4: shows 2x Tesla T4 GPUs
```

## RL/Atari-Specific Notes

### Stable Baselines3 Obs Shape Mismatch

**Problem:** During recording, `model.predict(obs)` fails with:
```
ValueError: Unexpected observation shape (84, 84, 1) for Box environment,
please use (4, 84, 84) or (n_env, 4, 84, 84)
```

**Cause:** Raw gym env produces `(84, 84, 1)` observations, but the model expects `(4, 84, 84)` (4-frame stack, channel-first from VecTransposeImage).

**Solution:** Use separate environments for rendering and prediction:
```python
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack, VecTransposeImage
from stable_baselines3.common.atari_wrappers import AtariWrapper

def make_vec_env():
    def _make():
        e = gym.make(ENV_ID, render_mode='rgb_array')
        e = AtariWrapper(e, frame_skip=4, terminal_on_life_loss=True, clip_reward=True)
        return e
    vec = DummyVecEnv([_make])
    vec = VecFrameStack(vec, n_stack=4)
    vec = VecTransposeImage(vec)
    return vec

# Raw env for frame capture
raw_env = gym.make(ENV_ID, render_mode='rgb_array')
raw_env = AtariWrapper(raw_env, ...)

# VecEnv for model prediction (correct obs shape)
vec_env = make_vec_env()
vec_obs = vec_env.reset()

while not done:
    frame = raw_env.render()          # Get visual frame from raw env
    action, _ = model.predict(vec_obs) # Predict with VecEnv obs
    raw_env.step(action[0])            # Step raw env (for rendering)
    vec_obs, _, _, _ = vec_env.step(action)  # Step vec env (for next prediction)
```

### Video Recording with imageio

```python
import imageio
import numpy as np

frames = []
for step in range(max_steps):
    frame = raw_env.render()  # Returns (H, W, 3) uint8
    # Optional 2x upscale for visibility
    frame = np.repeat(np.repeat(frame, 2, axis=0), 2, axis=1)
    frames.append(frame)

imageio.mimsave('output.mp4', frames, fps=30, quality=8)
```

### AutoROM Installation

```python
# Install Atari ROMs (required for ALE environments)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
    'gymnasium[atari,accept-rom-license]', 'ale-py==0.11.2',
    'AutoROM.accept-rom-license'], check=True)

import AutoROM
subprocess.run([sys.executable, '-m', 'AutoROM', '--accept-license'], check=True)
# NOTE: Do NOT add -q flag to AutoROM (not supported)
```

## Web UI vs CLI Created Kernels

### "Notebook not found" Push Error

**Problem:** `kaggle kernels push` fails with `"Kernel push error: Notebook not found"` even though `kaggle kernels pull` works.

**Cause:** Kernel was created via Kaggle **web UI** but never "committed" (saved/run). The push API can't find uncommitted web-created kernels.

**Solution:**
1. Go to the kernel page on Kaggle web
2. Click **"Save & Run All"** (or "Save Version")
3. Wait for it to save
4. THEN use `kaggle kernels pull -m` + modify + `kaggle kernels push`

**Alternative:** Push to a **new kernel slug** that doesn't exist yet - the API creates it automatically:
```json
{ "id": "username/my-new-kernel-slug", ... }
```

### Correct Push Workflow for Existing Kernels

```bash
# 1. Pull with metadata (gets id_no and correct format)
kaggle kernels pull owner/kernel-slug -p . -m

# 2. Replace the .ipynb with your generated notebook
python gen_notebook.py

# 3. Push back
kaggle kernels push -p .
```

## Competition Data Access

### competition_sources Not Mounting

**Problem:** `"competition_sources": ["comp-slug"]` in metadata but `/kaggle/input/comp-slug/` doesn't exist at runtime.

**Common causes:**
- User hasn't clicked **"Join Competition"** button on Kaggle web
- Competition rules not accepted
- For Playground Series: need to join even if rules are simple

**Solution - use `kagglehub` as fallback (requires `enable_internet: true`):**
```python
import os
DATA_DIR = '/kaggle/input/playground-series-s6e6'
if not os.path.exists(DATA_DIR):
    print('Data not mounted, using kagglehub...', flush=True)
    import kagglehub
    DATA_DIR = kagglehub.competition_download('playground-series-s6e6')
    print(f'Downloaded to: {DATA_DIR}', flush=True)

train = pd.read_csv(DATA_DIR + '/train.csv')
```

### NEVER Use subprocess kaggle CLI Inside Kernel

**Problem:** `subprocess.run(['kaggle', 'competitions', 'download', ...])` hangs indefinitely inside Kaggle kernels (no credentials, no tty).

**Solution:** Use `kagglehub` library instead (pre-installed, auto-authenticated):
```python
import kagglehub
# Download competition data
path = kagglehub.competition_download('competition-slug')
# Download dataset
path = kagglehub.dataset_download('owner/dataset-slug')
```

## Debugging Checklist

1. **Kernel fails immediately** -> Check `kaggle kernels logs`, look for import errors or pip failures
2. **Kernel times out** -> Likely papermill IOPub timeout. Add `progress_bar=False` and `log_interval=N`
3. **Files not found in /kaggle/input/** -> Verify `dataset_sources`/`competition_sources` in metadata; user must join competition; use `kagglehub` fallback
4. **Output empty** -> Only files in `/kaggle/working/` are saved. Check paths.
5. **Dataset files auto-extracted** -> Rename to `.sb3` or other non-standard extension before upload
6. **GPU not detected** -> Check `machine_shape` is `"NvidiaTeslaT4"` (not `"gpuT4x2"` or similar)
7. **Push fails "Notebook not found"** -> Kernel was web-created but never saved/run. Save from web UI first, or push to a new slug.
8. **Kernel RUNNING forever, no logs** -> Likely `subprocess.run(['kaggle', ...])` hanging. Use `kagglehub` instead.

## Accessing Historical Kernel Versions (critical for reproducing old experiments)

`kaggle kernels pull owner/slug` only gets the LATEST version. Old versions are still fully accessible via the kagglesdk API — the trick is the `version_label` format: **`'v' + version number`** (e.g. `'v22'`).

```python
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
import json

api = KaggleApi(); api.authenticate()
with api.build_kaggle_client() as kaggle:
    kc = kaggle.kernels.kernels_api_client

    # 1) Current version number (no version_label):
    req = ApiGetKernelRequest()
    req.user_name = '<owner>'; req.kernel_slug = '<slug>'
    resp = kc.get_kernel(req)
    print('currentVersionNumber:', resp.metadata.to_dict()['currentVersionNumber'])

    # 2) Fetch ANY historical version's source (notebook JSON as string):
    req = ApiGetKernelRequest()
    req.user_name = '<owner>'; req.kernel_slug = '<slug>'
    req.version_label = 'v22'          # ← 'v' + NUMBER, NOT scriptVersionId!
    resp = kc.get_kernel(req)
    blob = json.loads(resp.blob.source)   # dict with 'cells', 'metadata'
```

**Historical run outputs** (the /kaggle/working files of a specific past run — results.csv, args.yaml, split directories, everything) are also retrievable:

```python
from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
req = ApiListKernelSessionOutputRequest()
req.user_name = '<owner>'; req.kernel_slug = '<slug>'
req.version_label = 'v22'    # same 'vN' format
resp = kc.list_kernel_session_output(req)   # resp.files[].file_name / .url
# URLs are signed (kaggleusercontent.com) — download with curl --retry -C - for flaky networks
```

### What does NOT work (verified failures)

| Attempt | Result |
|---|---|
| `kaggle kernels pull owner/slug/22` (CLI version suffix) | 403 Forbidden |
| `version_label='347347457'` (scriptVersionId from the ?scriptVersionId= URL param) | 404 Not Found |
| `GetKernelSessionLogsStream` with `kernel_session_id` | 404 |
| WebFetch on a `?scriptVersionId=...` notebook URL | page is JS-rendered, no code |

### Pitfalls when mining historical versions

- **Rate limit**: bulk GetKernel scans (100+ rapid calls) hit `429 Too Many Requests`. Add `time.sleep(1-2)` between calls and handle retries; wait ~2 min after a burst.
- **The user's memory of "which version" may be wrong** — scan ALL versions and diff the relevant code (e.g., data-loading cells, model line) instead of trusting a version number. A `scriptVersionId` URL can also be mapped to a version number by scanning `blob['metadata']['kaggle']['scriptVersionId']` across versions.
- **Version labels are per-kernel local numbers**, not global IDs. A kernel with 89 versions has labels v1..v89.
- **Old runs may predate seed-fixing cells**: check whether the version actually seeds RNG before its random split. Unseeded `random.shuffle` in an old version means that split can never be reproduced from a seed — but the session output (see above) still preserves the exact assignment.
- **Reproducing an old experiment**: fetch the exact version's source FIRST, diff against your re-run code line by line, and note environment drift (old default Docker images get retired and cannot be restored; a pinned BYOD image digest in kernel-metadata.json is the reproducibility anchor).

## Additional Practical Lessons

### Parallel Notebooks on Kaggle

**Kaggle allows running 2 GPU notebooks concurrently** if you use **different kernel slugs**.

```python
# Kernel A (slug: my-project-training)
{ "id": "username/my-project-training", ... }

# Kernel B (slug: my-project-eval) - runs in parallel, doesn't cancel Kernel A!
{ "id": "username/my-project-eval", ... }
```

Both can run simultaneously with separate T4x2 allocations. This is critical for:
- Parallel training experiments (different models/datasets)
- Running eval while new training starts
- Avoiding the "push kills running version" problem

**WARNING:** Pushing to the SAME slug cancels the currently running version of that slug. Always use different slugs for parallel work.

### Real-Time Logs: API vs Web UI

`kaggle kernels logs` returns **empty** (`[]`) while the kernel is RUNNING. Logs are only available after COMPLETE or ERROR.

For real-time progress, use the **Kaggle Web UI** (https://www.kaggle.com/code/owner/slug).

### Notebook Generation: f-string Escaping in heredocs

When generating notebook code via bash heredocs, `\\n` gets double-escaped:
- Bash heredoc `python -c '...'` -> Python gets literal `\n` -> becomes real newline in f-strings -> SyntaxError

**Fix:** Use standalone `.py` files for complex code generation, avoid heredocs for scripts with f-strings.

### Unsloth FastModel device_map Rules

Critical `device_map` settings for Unsloth's `FastModel.from_pretrained`:

| Model | device_map | Reason |
|-------|-----------|--------|
| **E2B (5B)** | `cuda:0` | Small, fits one T4 (14.6GB) easily |
| **E4B (8B)** | `cuda:0` | Fits one T4 |
| **31B** | **`auto`** :warning: | **MUST use auto** - `cuda:0` causes empty model output (silent generation failure). Model trains fine but generates only whitespace/special tokens |
| 12B Unified | N/A | NOT supported by Unsloth (bf16/dtype bug) |

**31B with `cuda:0` failure mode:** Model loads in 4-bit (~8GB, fits T4), trains with normal Loss, but `model.generate()` produces empty output. The generation pipeline breaks silently - no OOM error, no crash, just empty strings. Using `device_map="auto"` fixes this (splits across T4x2).

### Dataset Path Resolution in Notebooks

Kaggle mounts datasets at `/kaggle/input/<dataset-name>/`. Include fallback paths:

```python
import os
DS_NAME = "owner/dataset-slug"
candidates = [
    f"/kaggle/input/{DS_NAME.split('/')[1]}/train.jsonl",
    f"/kaggle/input/datasets/{DS_NAME}/train.jsonl",
]
ds_path = next((p for p in candidates if os.path.exists(p)), None)
if not ds_path:
    import kagglehub
    ds_path = kagglehub.dataset_download(DS_NAME) + "/train.jsonl"
```
