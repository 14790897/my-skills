---
name: kaggle-kernel-runner
description: >
  Push, monitor, debug, and iterate on Kaggle kernel notebooks using the kaggle CLI.
  Covers: nbformat notebook generation, kernel-metadata.json configuration (GPU/dataset),
  push→poll→debug→fix→repush cycle, papermill timeout avoidance, and output download. Use when the user
  wants to run a notebook on Kaggle cloud GPUs and iteratively fix errors until it succeeds.
agent_created: true
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

## Workflow: Push → Poll → Debug → Fix → Repush

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
- `"NvidiaTeslaT4"` — 2x T4 GPUs (16GB each), recommended for most tasks
- `"NvidiaL4x4"` — 4x L4 GPUs (only for competitions)
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

## Web UI vs CLI Created Kernels

### "Notebook not found" Push Error

**Problem:** `kaggle kernels push` fails with `"Kernel push error: Notebook not found"` even though `kaggle kernels pull` works.

**Cause:** Kernel was created via Kaggle **web UI** but never "committed" (saved/run). The push API can't find uncommitted web-created kernels.

**Solution:**
1. Go to the kernel page on Kaggle web
2. Click **"Save & Run All"** (or "Save Version")
3. Wait for it to save
4. THEN use `kaggle kernels pull -m` + modify + `kaggle kernels push`

**Alternative:** Push to a **new kernel slug** that doesn't exist yet — the API creates it automatically:
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

**Solution — use `kagglehub` as fallback (requires `enable_internet: true`):**
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

1. **Kernel fails immediately** → Check `kaggle kernels logs`, look for import errors or pip failures
2. **Kernel times out** → Likely papermill IOPub timeout. Add `progress_bar=False` and `log_interval=N`
3. **Files not found in /kaggle/input/** → Verify `dataset_sources`/`competition_sources` in metadata; user must join competition; use `kagglehub` fallback
4. **Output empty** → Only files in `/kaggle/working/` are saved. Check paths.
5. **Dataset files auto-extracted** → Rename to `.sb3` or other non-standard extension before upload
6. **GPU not detected** → Check `machine_shape` is `"NvidiaTeslaT4"` (not `"gpuT4x2"` or similar)
7. **Push fails "Notebook not found"** → Kernel was web-created but never saved/run. Save from web UI first, or push to a new slug.
8. **Kernel RUNNING forever, no logs** → Likely `subprocess.run(['kaggle', ...])` hanging. Use `kagglehub` instead.
