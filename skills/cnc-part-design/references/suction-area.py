"""量一个 STEP 的真空吸附面：自动认厚度轴，按高度层汇总共面平面面积。

用法:  python suction-area.py 零件.step

为什么必须自动认厚度轴：原版 B站硬币的 STEP 是 **Y 轴**为厚度轴（80 x 8 x 80），
自建件是 Z 轴。写死 Z 会把直径方向当成厚度方向去汇总，量出 640 mm² 这种明显不对的数。

判据口径（嘉立创 DFM 原文）：底部可吸附面积 >= 包围盒面积的 35%。
- **包围盒是下料尺寸**，Ø80 的件按 90x90 = 8100mm² 算，不是零件本身的 80x80。
  拿用户 DFM 报告里已报出的数反推最稳（报 5021mm² -> 62.0%，5021/8100 ✓）。
- 只有**和最低面齐平的**平面才算接触面：凹底低 2mm 就碰不到吸盘；
  凸起浮雕会把平面顶起来。
- 吸附面积的唯一杠杆是**加宽圆环**（见 SKILL.md），不是缩字、更不是把凹面做浅。
"""
import sys

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps


def report(path, envelope=None):
    sh = cq.importers.importStep(path).val()
    bb = sh.BoundingBox()
    dims = {"X": bb.xlen, "Y": bb.ylen, "Z": bb.zlen}
    axis = min(dims, key=dims.get)                     # 厚度轴 = 跨度最小的轴
    ai = {"X": 0, "Y": 1, "Z": 2}[axis]
    lo, hi = {"X": (bb.xmin, bb.xmax),
              "Y": (bb.ymin, bb.ymax),
              "Z": (bb.zmin, bb.zmax)}[axis]

    part = 1.0
    for k, v in dims.items():
        if k != axis:
            part *= v
    env = envelope or part

    print(path)
    print("  厚度轴 %s   %.3f..%.3f  (厚 %.2f)   零件面 %.0f  下料包络 %s mm²"
          "   面 %d  壳 %d  实体 %d"
          % (axis, lo, hi, hi - lo, part,
             "%.0f" % env if envelope else "(未给, 暂用零件面; Ø80 件应为 90x90=8100)",
             len(sh.Faces()), len(sh.Shells()), len(sh.Solids())))

    levels = {}
    for f in sh.Faces():
        s = BRepAdaptor_Surface(f.wrapped)
        if s.GetType() != GeomAbs_SurfaceType.GeomAbs_Plane:
            continue
        # 只算垂直于厚度轴的平面 —— 柱面、锥面、倒角面都碰不到吸盘
        d = s.Plane().Axis().Direction()
        if abs(abs([d.X(), d.Y(), d.Z()][ai]) - 1.0) > 1e-6:
            continue
        p = s.Plane().Location()
        pr = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f.wrapped, pr)
        k = round([p.X(), p.Y(), p.Z()][ai], 4)
        levels[k] = levels.get(k, 0.0) + pr.Mass()

    for label, order in (("高端面（该面朝下贴吸盘）", sorted(levels, reverse=True)),
                         ("低端面", sorted(levels))):
        print("  --- %s ---" % label)
        for z in order[:6]:
            a = levels[z]
            print("    %s=%7.3f  共面 %8.1f mm²   占零件面 %5.1f%%   占下料包络 %5.1f%%%s"
                  % (axis, z, a, 100.0 * a / part, 100.0 * a / env,
                     "   <== 过 35%" if a / env >= 0.35 else ""))
    print("  缺口径以 DFM 报告为准 —— 这张表只能排序、不能下结论。")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    report(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else None)
