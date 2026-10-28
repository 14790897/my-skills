# Blender 无头渲染与拼图

## 调用

```bash
"/c/Program Files/Blender Foundation/Blender 4.5/blender.exe" \
  --background --factory-startup --python render.py -- <参数...>
```

- `--factory-startup` 跳过用户配置，结果可复现
- `--` 之后的参数用 `sys.argv[sys.argv.index("--")+1:]` 取
- **脚本里的路径用正斜杠或 Windows 路径**；在 Git Bash 里用 `$T\xxx` 拼出来的
  MSYS 风格路径（`/c/...`）Python 认不了

## 导入导出

```python
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.stl_import(filepath=STL)          # 4.5 的名字
o = [x for x in bpy.context.scene.objects if x.type == "MESH"][0]
...
bpy.ops.wm.stl_export(filepath=OUT, export_selected_objects=True)   # 4.5 的名字
# 旧名字 export_mesh.stl / import_mesh.stl 在 4.5 已经没有
```

导入时会自动焊接重合顶点（gmsh 写的 STL 有共享顶点，导入后数量和节点数一致）。

## 朝向

STL 没有统一朝向。**别假设 Y 是厚度**——按包围盒自动找最薄轴：

```python
d = list(obj.dimensions)
thin = min(range(3), key=lambda i: d[i])
obj.rotation_euler = {0: (0, -math.pi/2, 0), 1: (math.pi/2, 0, 0), 2: (0, 0, 0)}[thin]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
```

## 相机与灯光

正面正交视图（看设计）：
```python
cd.type = "ORTHO"; cd.ortho_scale = S * 1.12
cam.location = (0, 0, S * 2); cam.rotation_euler = (0, 0, 0)
```

背面（**左右翻转，像把硬币翻过来**，这样背面的字读向才正确）：
```python
cam.location = (0, 0, -S * 2); cam.rotation_euler = (0, math.pi, 0)
# 灯也要跟着翻到 -Z 侧，否则背面全黑
for o, loc in lights: p = Vector((loc.x, loc.y, loc.z * -1)); o.location = p
```

三点布光（区域光），朝原点：
```python
o.rotation_euler = (Vector((0,0,0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
```

金属材质：`Base Color` 暖金、`Metallic 0.7`、`Roughness 0.28`；
`for p in obj.data.polygons: p.use_smooth = False` 保持硬边。

## 多张图拼成一张

渲染成多个 PNG 后，用 Blender 自己的图像 API 拼（不需要 PIL）：

```python
im = bpy.data.images.load(path)
w, h = im.size
px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)   # 注意是 **bottom-up**
imgs.append(px)

rows = (len(imgs) + COLS - 1) // COLS
sheet = np.zeros((h * rows, w * COLS, 4), dtype=np.float32)
for i, p in enumerate(imgs):
    r, c = divmod(i, COLS)
    y0 = sheet.shape[0] - (r + 1) * h        # bottom-up 存法，所以从下往上摆
    sheet[y0:y0 + h, c*w:(c+1)*w] = p

out = bpy.data.images.new("sheet", w*COLS, h*rows, alpha=True)
out.pixels = sheet.ravel()
out.filepath_raw = OUT; out.file_format = "PNG"; out.save()
```

**网格别太长条**：6 张图排成 1 列 6 行 → 760×4560，看的时候被压得看不清；
3 列 2 行（2280×1520）才读得出来。

## ⚠️ 渲染会骗人

本项目里渲染出过这些假象，**每一个都导致过错误结论**：

| 假象 | 真相 |
|---|---|
| 字看起来"正常浮雕" | 布尔静默失败，字其实埋在实心内部，渲染的是破面 |
| 表面看着挺光滑 | 轮廓被面片化 |
| 大图里看到"细缝" | 只是笔画末端的圆头和阴影，放大才确认没缝 |
| 尺寸看着对 | 包围盒差 0.14mm（超出币的边缘） |

**规则：渲染用来"给用户看"，判断对错一律用数字。**
体积、包围盒、开边数、各高度层平面面积、浮雕外接半径——全都能量。

## 小图放大看细部

正交相机 + 小 `ortho_scale` + 偏移到目标位置即可：

```python
cd.type = "ORTHO"; cd.ortho_scale = 32; cam.location = (0, 14, 200)   # 看顶部 32mm 见方
```
