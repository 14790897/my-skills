---
name: kaggle-notebook-format
description: >
  Use this skill when creating Python scripts that target Kaggle Notebooks. This
  skill ensures correct cell separator format (# %% [code] and # %% [markdown]),
  proper markdown cell formatting (each line prefixed with #, no triple quotes),
  and Kaggle-specific conventions (Chinese comments, English output, %pip
  install). Also covers common pitfalls: OpenCV video decoding limits and Chinese text rendering with PIL.
agent_created: true
disable: false
---

# Kaggle Notebook Format Rules

## Cell Separators

- Code cells: `# %% [code]`
- Markdown cells: `# %% [markdown]`

## Markdown Cell Formatting

**CRITICAL RULES:**

1. **Every line** must start with `# ` (hash + space)
2. **NEVER** use triple quotes (`"""` or `'''`) for markdown cells
3. **NO empty lines** with only `# ` - they create extra whitespace in rendered notebook

Correct markdown cell:
```python
# %% [markdown]
# # Title
# Content line 1
# Content line 2
# - Bullet point 1
# - Bullet point 2
```

## Code Cell Conventions

- Printed output in English
- File extension: `.py` (not `.ipynb`)
- Dataset paths: `/kaggle/input/dataset-name/`

## Package Installation

- Only install packages NOT pre-installed on Kaggle
- Use `%pip install -q package-name` (not `!pip install`)
- Common libraries (pandas, numpy, scipy, scikit-learn, torch, torchvision) are already available

## Common Mistakes to Avoid

1. Triple quotes in markdown cells → Use `# ` prefix on every line
2. Empty `# ` lines → Remove them
3. Missing `# ` prefix → Every line must start with `# `
4. Using `## Title` → Use `# Title` only
5. Using `!pip` → Use `%pip`

## process video(always use ffmpeg)
example:
```
from IPython.display import Image, Video
import os
output_video_path='/kaggle/working/runs/detect/predict/650-1-y1_particle_video.avi'
# Using ffmpeg to compress the video to display
compressed_output_path = 'compressed_output_particle.mp4'
os.system(f'ffmpeg -i {output_video_path} -vcodec libx264 -crf 28 {compressed_output_path}')
display(Video(compressed_output_path, embed=True))
```

## Common Pitfalls on Kaggle (实战踩坑记录)

### 1. 视频解码：OpenCV 读不了某些编码格式

**问题**: `cv2.VideoCapture` 在 Kaggle 上对 H.265/HEVC 等编码格式支持很差，`cap.read()` 返回 `(False, None)`。

**解决方案**: 用 ffmpeg 解码为 raw BGR24 格式，再用 numpy 逐帧读取：
```python
raw_video_path = "/kaggle/working/video_raw.rgb"
subprocess.run([
    "ffmpeg", "-y", "-i", VIDEO_PATH,
    "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-v", "quiet", raw_video_path
], capture_output=True)

frame_bytes = width * height * 3
actual_frames = os.path.getsize(raw_video_path) // frame_bytes

with open(raw_video_path, "rb") as f:
    for frame_idx in range(actual_frames):
        raw_data = f.read(frame_bytes)
        frame = np.frombuffer(raw_data, dtype=np.uint8).reshape((height, width, 3))
```

获取视频元信息用 ffprobe 而非 cv2：
```python
probe = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json",
     "-show_streams", "-select_streams", "v:0", VIDEO_PATH],
    capture_output=True, text=True
)
probe_data = json.loads(probe.stdout)
vstream = probe_data["streams"][0]
width = int(vstream["width"])
height = int(vstream["height"])
fps_num, fps_den = map(int, vstream["r_frame_rate"].split("/"))
fps = fps_num / fps_den
```


### 2. OpenCV putText 不支持中文

**问题**: `cv2.putText()` 只支持 ASCII 字符，中文会显示为乱码或方块。

**解决方案**: 使用 PIL 绘制中文文字：
```python
from PIL import Image, ImageDraw, ImageFont

# 字体加载（使用wget从网络下载）
font_url = "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf"
font_path = "/kaggle/working/fonts/SourceHanSansSC-Regular.otf"
subprocess.run(["wget", "-q", "-O", font_path, font_url], capture_output=True)
pil_font = ImageFont.truetype(font_path, font_size)

def put_text_pil(frame_bgr, text, font_color, stroke_color, stroke_width):
    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    # 计算位置、绘制描边+正文...
    draw.text((text_x, text_y), text, fill=font_color, font=pil_font)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
```
