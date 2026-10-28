"""Measure the slots a cutter actually sees, on one horizontal pocket floor.

Why this and not "distance between side-wall faces": a relief's side walls meet
at Bezier corners, so a naive face-pair scan reports hundreds of false zero
gaps and, worse, the vertex-proximity filter that removes them also throws away
real slots.  The floor face already has the correct structure -- every wire is
the footprint of one raised feature (plus the outer boundary), and the distance
between two wires IS the slot width between those features.  This metric was
checked against the platform: 0.731 mm -> "存在窄槽", widened to 1.331 mm ->
verdict flipped to "存在薄壁".  So it also covers glyph-to-glyph, glyph-to-wall
and hole-to-everything in one pass.

It is still a per-face measure: run it on each machined floor, not once for the
whole part.

    python dish_slots.py part.step --z 1.5 --limit 1.1
    python dish_slots.py part.step --z 1.5 --limit 1.4 --all
"""

import argparse
import math
import sys

import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.TopoDS import TopoDS

def load(path):
    shape = cq.importers.importStep(path).val()
    if not shape.Solids():
        sys.exit("no solid in %s" % path)
    return shape

def floor_face(shape, z, tol=1e-6):
    """The largest upward-facing planar face at height z."""
    best = None
    for f in shape.Faces():
        if f.geomType() != "PLANE":
            continue
        if f.normalAt().z < 0.99:
            continue
        if abs(f.Center().z - z) > tol:
            continue
        if best is None or f.Area() > best.Area():
            best = f
    return best

def aabb_gap(a, b):
    dx = max(a.xmin - b.xmax, b.xmin - a.xmax, 0.0)
    dy = max(a.ymin - b.ymax, b.ymin - a.ymax, 0.0)
    dz = max(a.zmin - b.zmax, b.zmin - a.zmax, 0.0)
    return math.sqrt(dx * dx + dy * dy + dz * dz)

def slots(face, limit, show_all=False):
    wires = list(face.Wires())
    boxes = [w.BoundingBox() for w in wires]
    hits = []
    for i in range(len(wires)):
        for j in range(i + 1, len(wires)):
            # AABB is a lower bound: skip only pairs that cannot possibly be close
            if aabb_gap(boxes[i], boxes[j]) > limit:
                continue
            d = BRepExtrema_DistShapeShape(wires[i].wrapped, wires[j].wrapped)
            d.Perform()
            if not d.IsDone() or d.Value() >= limit:
                continue
            p1 = d.PointOnShape1(1)
            p2 = d.PointOnShape2(1)
            hits.append((d.Value(), i, j,
                         (p1.X() + p2.X()) / 2.0, (p1.Y() + p2.Y()) / 2.0))
    hits.sort()
    return wires, hits

def topology_report(shape):
    """Edges that do not belong to exactly two faces.

    OCC reports valid=True for a solid carrying a zero-length edge; a mesh
    exporter then emits open edges and some DFM back-ends choke.  This is a
    cheap independent check.
    """
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape.wrapped, TopAbs_EDGE, TopAbs_FACE, m)
    bad = []
    for i in range(1, m.Extent() + 1):
        lst = m.FindFromIndex(i)
        if lst.Extent() == 2:
            continue
        e = TopoDS.Edge_s(m.FindKey(i))
        c = BRepAdaptor_Curve(e)
        p = GCPnts_QuasiUniformDeflection(c, 0.05)
        pt = p.Value(1) if p.IsDone() and p.NbPoints() else None
        bad.append((lst.Extent(),
                    None if pt is None else (pt.X(), pt.Y(), pt.Z())))
    return bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--z", type=float, required=True,
                    help="height of the pocket floor to inspect")
    ap.add_argument("--limit", type=float, default=1.1,
                    help="report gaps below this (the platform's slot rule)")
    ap.add_argument("--all", action="store_true", help="list every reported gap")
    args = ap.parse_args()

    shape = load(args.step)
    face = floor_face(shape, args.z)
    if face is None:
        sys.exit("no upward planar face at z=%g -- check the height, or the "
                 "part may be modelled with the relief on the other side" % args.z)

    wires, hits = slots(face, args.limit)
    print("%s" % args.step)
    print("  floor z=%.3f  area=%.1f mm^2  wires=%d" % (args.z, face.Area(), len(wires)))
    print("  gaps < %.2f mm: %d" % (args.limit, len(hits)))
    for v, i, j, x, y in (hits if args.all else hits[:12]):
        print("    %.3f mm  wire%d<->wire%d  at (%.2f, %.2f)" % (v, i, j, x, y))

    bad = topology_report(shape)
    if bad:
        print("  WARNING: %d edge(s) not shared by two faces" % len(bad))
        for n, pt in bad[:6]:
            where = "" if pt is None else " at (%.2f, %.2f, %.2f)" % pt
            print("    faces=%d%s" % (n, where))
    else:
        print("  topology: every edge shared by two faces")

if __name__ == "__main__":
    main()
