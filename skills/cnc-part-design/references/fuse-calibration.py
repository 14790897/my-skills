"""布尔失败时的最小算例校准 —— 报 IsDone=False 时先做这个，别直接上真实模型。

关键技术：拿一个**体积可以手算**的对照件（这里是币体 + 20x20x2.3 方块），
把"结果必须等于多少"先写死，再换调用方式去试。
一个数不差才算通过 —— 这样 5 分钟就能定位是"调用错"还是"几何错"。

本项目实测结论（2026-10-15）：
    SetArguments([body, box])                    -> IsDone=False      ✗
    SetArguments([body]) + SetTools([box])       -> 25444 mm³ 精确正确 ✓
    期望值 = 25324(币体) + 920(方块) - 800(重叠 20x20x2.0) = 25444

所以「OCC 布尔吃不下去」那堵墙不存在，是 SetArguments/SetTools 用反了。

用法:  python fuse-calibration.py
"""
import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.TopTools import TopTools_ListOfShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

R_FIELD, R_CHAMF, R_RIM, R_OUT = 34.2857, 34.7857, 39.5, 40.0
Z_FACE, Z_FIELD, WALL_Z = 4.0, 2.0, 3.5


def vol(s):
    pr = GProp_GProps()
    BRepGProp.VolumeProperties_s(s.wrapped, pr)
    return pr.Mass()


def lst(shapes):
    l = TopTools_ListOfShape()
    for s in shapes:
        l.Append(s.wrapped)
    return l


def fuse(a, b, mode, fuzzy=1e-4):
    op = BRepAlgoAPI_Fuse()
    if mode == "args":                       # ✗ 全塞进 Arguments
        op.SetArguments(lst([a, b]))
    else:                                    # ✓ arg + tools
        op.SetArguments(lst([a]))
        op.SetTools(lst([b]))
    if fuzzy:
        op.SetFuzzyValue(fuzzy)
    op.Build()
    if not op.IsDone():
        return None
    return cq.Shape.cast(op.Shape())


def body_solid():
    prof = [(0, Z_FIELD), (R_FIELD, Z_FIELD), (R_FIELD, WALL_Z), (R_CHAMF, Z_FACE),
            (R_RIM, Z_FACE), (R_OUT, WALL_Z), (R_OUT, -WALL_Z), (R_RIM, -Z_FACE),
            (R_CHAMF, -Z_FACE), (R_FIELD, -WALL_Z), (R_FIELD, -Z_FIELD), (0, -Z_FIELD)]
    wp = cq.Workplane("XZ").moveTo(*prof[0])
    for p in prof[1:]:
        wp = wp.lineTo(*p)
    return wp.close().revolve(360, (0, 0), (0, 1)).val()


if __name__ == "__main__":
    body = body_solid()
    box = cq.Workplane("XY").box(20, 20, 2.3, centered=(True, True, False)).val()
    expect = vol(body) + vol(box) - 20 * 20 * 2.0
    print("币体 %.0f   方块 %.0f   期望结果 %.0f" % (vol(body), vol(box), expect))

    for mode in ("args", "argstools"):
        r = fuse(body, box, mode)
        if r is None:
            print("  %-10s -> FAILED" % mode)
            continue
        got = abs(vol(r))
        print("  %-10s -> %.0f  %s" % (mode, got, "✓ 与期望一致" if abs(got - expect) < 1e-3 else "✗ 差 %.3f" % (got - expect)))
