import sys
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

sh = cq.importers.importStep(sys.argv[1]).val()
faces = sh.Faces()
print("总面数 %d   实体 %d   valid=%s" % (len(faces), len(sh.Solids()), sh.isValid()))

TYPES = {}
tiny = []
areas = []
for f in faces:
    ad = BRepAdaptor_Surface(f.wrapped)
    t = ad.GetType()
    name = {GeomAbs_SurfaceType.GeomAbs_Plane: "PLANE",
            GeomAbs_SurfaceType.GeomAbs_Cylinder: "CYLINDER",
            GeomAbs_SurfaceType.GeomAbs_Cone: "CONE",
            GeomAbs_SurfaceType.GeomAbs_Sphere: "SPHERE",
            GeomAbs_SurfaceType.GeomAbs_Torus: "TORUS",
            GeomAbs_SurfaceType.GeomAbs_BezierSurface: "BEZIER",
            GeomAbs_SurfaceType.GeomAbs_BSplineSurface: "BSPLINE",
            GeomAbs_SurfaceType.GeomAbs_SurfaceOfRevolution: "REVOLUTION",
            GeomAbs_SurfaceType.GeomAbs_SurfaceOfExtrusion: "EXTRUSION",
            GeomAbs_SurfaceType.GeomAbs_OffsetSurface: "OFFSET",
            GeomAbs_SurfaceType.GeomAbs_OtherSurface: "OTHER"}.get(t, "?%s" % t)
    TYPES[name] = TYPES.get(name, 0) + 1
    pr = GProp_GProps(); BRepGProp.SurfaceProperties_s(f.wrapped, pr)
    a = pr.Mass(); areas.append(a)
    if a < 0.02:
        tiny.append((a, name))
print("\n面类型分布：")
for k, v in sorted(TYPES.items(), key=lambda x: -x[1]):
    print("  %-11s %5d" % (k, v))
areas.sort()
print("\n面积: 最小 %.6f  中位 %.3f  最大 %.1f mm2" % (areas[0], areas[len(areas)//2], areas[-1]))
print("面积<0.02mm2 的碎片面: %d  (%.1f%%)" % (len(tiny), 100.0*len(tiny)/len(areas)))
for a, n in tiny[:12]:
    print("    %.5f mm2  %s" % (a, n))
