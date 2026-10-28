# cadquery / OCC 常用模式

## 开头

```python
import math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I 会去掉脚本目录
import cadquery as cq
from cadquery import exporters
```

`python -I` 会同时去掉**脚本所在目录**和 user site-packages —— 本地模块会导不进来，
所以要么自己插 sys.path，要么别用 `-I`。

## 旋转体：别用一堆布尔拼

一个回转体用**一条剖面线**转出来，比"圆柱 ∪ 圆锥 ∪ 圆环再切"可靠得多，
而且出来的全是解析曲面（平面/圆柱/圆锥），STEP 干净。

```python
prof = [(0, 2.0), (34.2857, 2.0),          # 凹面底
        (34.2857, 3.5), (34.7857, 4.0),    # 凹面口 45° 倒角
        (39.5, 4.0), (40.0, 3.5),          # 外圈环 + 外倒角
        (40.0, -3.5), (39.5, -4.0),        # 背面
        (34.7857, -4.0), (34.2857, -3.5),
        (34.2857, -2.0), (0, -2.0)]
wp = cq.Workplane("XZ").moveTo(*prof[0])
for p in prof[1:]:
    wp = wp.lineTo(*p)
body = wp.close().revolve(360, (0, 0), (0, 1)).val()   # 轴 = 本地 (0,0)→(0,1)
```

**Workplane("XZ")** 的局部 (x,y) 映射到世界 (X,Z)；`revolve` 的轴给**局部坐标**。

## 文字

```python
# 中文字体直接给路径（.otf / .ttf / .ttc 都行）
FONT = "C:/Windows/Fonts/msyhbd.ttc"

# 按"外接圆半径"缩放最稳（方字/窄高字都适用）
bb = cq.Workplane("XY").text(txt, 10.0, 1.0, fontPath=FONT).val().BoundingBox()
size = 10.0 * target_halfdiag / math.hypot(bb.xlen / 2, bb.ylen / 2)
solid = cq.Workplane("XY").text(txt, size, thickness, fontPath=FONT).val()
# 结果：以原点为中心，z 从 0 到 thickness
```

- **cadquery 的文字是基线对齐的** → 整串字符用同一个字号，标点比例才对
- 逐字按"字高"缩放会把句点放大到数字大小
- `distance=0` 只出"面"不出"线"，后续 `offset2D` 会报 "No pending wires"

## 摆到圆环上 / 沿圆弧排字

```python
def rotate_on_ring(shape, phi_deg):
    """形状已经摆在 12 点 (0, R) 上 → 转到角度 phi"""
    return shape.rotate((0, 0, 0), (0, 0, 1), -phi_deg)

def place_on_bottom(shape, phi_deg):
    """居中的形状 → 摆到圆环底部，字头朝圆心（外圈日期用）"""
    phi = math.radians(phi_deg)
    return shape.rotate((0, 0, 0), (0, 0, 1), phi_deg).translate(
        (R * math.sin(phi), -R * math.cos(phi), 0))
```

文字沿弧排：每个字按自己的 ink 宽度 + 间距沿弧长推进，再 `place_on_bottom`。

## 圆环带（藤蔓/边框）

```python
def ring_block(z0, h, r_in, r_out):
    return (cq.Workplane("XY", origin=(0, 0, z0))
            .circle(r_out).circle(r_in).extrude(h))     # 同心双圆 → 管状环
```

**挖掉一段用"扇形刀"，扇形必须把圆心写进点列表**：

```python
def pie(a0, a1, z0, h, r=46.0):
    # matplotlib/cadquery 的 polyline 默认不包含当前点，
    # 用 moveTo(0,0)+polyline() 会丢掉圆心 → 出来的是"圆弧与弦之间的月牙"，
    # 内边界落在零件外面 → 这一刀等于没切
    pts = [(0.0, 0.0)] + [(r * math.sin(math.radians(a)), r * math.cos(math.radians(a)))
                          for a in [a0 + (a1 - a0) * i / 24 for i in range(25)]]
    return cq.Workplane("XY", origin=(0, 0, z0)).polyline(pts).close().extrude(h).val()
```

## 布尔

```python
result = body.fuse(*blobs)          # 一次 fuse 多个，比逐个 union 快
result = result.cut(cutter)
result = result.clean()

# 多个不相交的形状要合成一个"刀"再 cut
cut = shapes[0]
for s in shapes[1:]:
    cut = cut.fuse(s)
result = result.cut(cut)
```

**OCC 的布尔比 Blender 的网格布尔可靠得多**（共面相切也能处理），
但**必须检查结果**：`len(r.Solids()) == 1`。

## 导出

```python
exporters.export(result, "part.step")                      # 真 CAD
exporters.export(result, "part.stl", tolerance=0.02)       # 网格（给预览/3D 打印）
```

STEP 文件大小 ≈ 面数 × 4KB。**面数上万就说明轮廓采样太密** →
用 `shapely.simplify()` 压直线段上的冗余点（见 `thin-glyph.py`）。

## 验证

```python
w = importers.importStep("part.step").val()
bb = w.BoundingBox()
len(w.Solids()), len(w.Faces()), w.Volume()
import collections
collections.Counter(f.geomType() for f in w.Faces())
# {'PLANE': ..., 'CYLINDER': ..., 'CONE': ..., 'EXTRUSION': ...}
# 出现大量 PLANE 之外的东西要警惕——可能是被面片化了
```
