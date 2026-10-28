"""Read-only STEP inventory, selected horizontal-face gaps and edit-mask comparison.

Dependencies: cadquery (with OCP). Coordinates use the importer's units.
This is not a whole-part DFM, narrow-channel or wall-thickness detector.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape


def bounds(shape):
    b = shape.BoundingBox()
    return [b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax]


def load_step(path):
    path = Path(path).resolve(strict=True)
    shape = cq.importers.importStep(str(path)).val()
    if not shape.Solids():
        raise ValueError(f"No solid found: {path}")
    b = shape.BoundingBox()
    info = {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "valid": shape.isValid(),
        "solid_count": len(shape.Solids()),
        "volume": shape.Volume(),
        "bounds": bounds(shape),
        "dimensions": [b.xlen, b.ylen, b.zlen],
    }
    return shape, info


def box_distance(a, b):
    """AABB distance is a lower bound, so it only excludes distant pairs."""
    return math.sqrt(sum(max(a[k] - b[k + 3], b[k] - a[k + 3], 0) ** 2
                         for k in range(3)))


def inspect_step(args):
    shape, info = load_step(args.input)
    inventory, horizontal = [], {}
    for i, face in enumerate(shape.Faces()):
        if face.geomType() != "PLANE":
            continue
        normal = face.normalAt()
        if abs(normal.z) < 1 - 1e-7:
            continue
        horizontal[i] = face
        inventory.append({
            "id": i, "z": face.Center().z, "area": face.Area(),
            "center": list(face.Center().toTuple()),
            "normal": list(normal.toTuple()), "bounds": bounds(face),
            "wire_count": len(face.Wires()), "edge_count": len(face.Edges()),
        })

    if args.face_ids is not None:
        selected = sorted(set(args.face_ids))
        missing = set(selected) - set(horizontal)
        if missing:
            raise ValueError(f"Not horizontal planar face IDs: {sorted(missing)}")
    elif args.z is not None:
        selected = [r["id"] for r in inventory
                    if any(abs(r["z"] - z) <= args.z_tolerance for z in args.z)
                    and (args.max_area is None or r["area"] <= args.max_area)]
    else:
        selected = []  # Inventory only; do not silently compare every face.

    bb = {i: bounds(horizontal[i]) for i in selected}
    gaps = []
    for k, i in enumerate(selected):
        for j in selected[k + 1:]:
            if box_distance(bb[i], bb[j]) > args.near_gap:
                continue
            d = BRepExtrema_DistShapeShape(horizontal[i].wrapped,
                                           horizontal[j].wrapped)
            if not d.IsDone() or not d.NbSolution():
                raise RuntimeError(f"Distance operation failed: {i}, {j}")
            value = d.Value()
            if value <= args.near_gap:
                gaps.append({
                    "faces": [i, j], "distance": value,
                    "point_a": list(d.PointOnShape1(1).Coord()),
                    "point_b": list(d.PointOnShape2(1).Coord()),
                })
    gaps.sort(key=lambda r: r["distance"])
    return {
        "mode": "inspect", "model": info,
        "coordinate_units": "Imported coordinates; verify STEP/import units before using mm thresholds.",
        "scope": "Exact distances between selected horizontal planar faces only. No whole-part groove or wall-thickness certification.",
        "face_id_warning": "IDs apply to this import/hash; re-identify after geometry edits or export.",
        "horizontal_faces": inventory, "selected_face_ids": selected,
        "near_gap_limit": args.near_gap, "nearby_face_pairs": gaps,
    }


def read_edit_mask(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, list) or not data:
        raise ValueError("Edit boxes must be a nonempty JSON array.")
    boxes = []
    for row in data:
        if (not isinstance(row, list) or len(row) != 6
                or any(isinstance(x, bool) or not isinstance(x, (int, float))
                       or not math.isfinite(x) for x in row)):
            raise ValueError("Each edit box must contain six finite numbers.")
        x0, y0, z0, x1, y1, z1 = row
        if not (x0 < x1 and y0 < y1 and z0 < z1):
            raise ValueError(f"Edit box must have positive dimensions: {row}")
        boxes.append(cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0,
                                       cq.Vector(x0, y0, z0)))
    # A compound with overlapping children can fail BRep booleans. Union first.
    mask = boxes[0].fuse(*boxes[1:]).clean() if len(boxes) > 1 else boxes[0]
    if not mask.isValid():
        raise ValueError("Invalid edit mask union.")
    return mask, data


def compare_steps(args):
    ref, ref_info = load_step(args.reference)
    candidate, candidate_info = load_step(args.candidate)
    if not ref_info["valid"] or not candidate_info["valid"]:
        raise ValueError("Comparison requires two valid solid models.")
    mask, data = read_edit_mask(args.edit_boxes)
    a, b = ref.cut(mask), candidate.cut(mask)
    if not a.Solids() or not b.Solids():
        raise ValueError("Edit mask removes all remaining solid in a model; no useful outside-region validation.")
    if not a.isValid() or not b.isValid():
        raise RuntimeError("Invalid geometry after edit-mask subtraction.")
    # Exceptions are intentionally propagated. Boolean failure is not zero volume.
    removed, added = a.cut(b).Volume(), b.cut(a).Volume()
    consistent = abs(removed) <= args.volume_tolerance and abs(added) <= args.volume_tolerance
    return {
        "mode": "compare", "reference": ref_info, "candidate": candidate_info,
        "coordinate_units": "Imported coordinates; volume tolerance uses cubic coordinate units.",
        "edit_boxes": data,
        "outside_edit_regions_removed_volume": removed,
        "outside_edit_regions_added_volume": added,
        "volume_tolerance": args.volume_tolerance,
        "outside_edit_regions_consistent": consistent,
        "dimension_delta": [v - u for u, v in zip(ref_info["dimensions"], candidate_info["dimensions"])],
        "solid_count_changed": ref_info["solid_count"] != candidate_info["solid_count"],
        "scope": "Outside-mask comparison only. Masked features, intended dimensions, gaps and wall thickness require separate verification.",
    }


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive finite number.")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect", help="Inventory and exact selected-face gaps.")
    p.add_argument("input")
    selection = p.add_mutually_exclusive_group()
    selection.add_argument("--face-ids", nargs="+", type=int)
    selection.add_argument("--z", nargs="+", type=float)
    p.add_argument("--z-tolerance", type=positive_float, default=1e-5)
    p.add_argument("--max-area", type=positive_float)
    p.add_argument("--near-gap", type=positive_float, default=1.6)
    p.add_argument("--out", required=True)
    p = sub.add_parser("compare", help="Compare solids outside declared edit boxes.")
    p.add_argument("reference")
    p.add_argument("candidate")
    p.add_argument("--edit-boxes", required=True)
    p.add_argument("--volume-tolerance", type=positive_float, default=1e-6)
    p.add_argument("--out", required=True)
    args = parser.parse_args()
    # Reports may be replaced, but never overwrite either input model or the mask.
    inputs = ([args.input] if args.command == "inspect" else
              [args.reference, args.candidate, args.edit_boxes])
    if Path(args.out).resolve() in {Path(p).resolve() for p in inputs}:
        parser.error("Report output must differ from input files.")
    try:
        report = inspect_step(args) if args.command == "inspect" else compare_steps(args)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                             allow_nan=False) + "\n", encoding="utf-8")
    except Exception as exc:
        parser.exit(2, f"STEP audit failed: {exc}\n")
    if args.command == "inspect":
        print(f"Valid={report['model']['valid']}; {len(report['selected_face_ids'])} selected faces; {len(report['nearby_face_pairs'])} nearby pairs. Report: {args.out}")
        return 0 if report["model"]["valid"] else 2
    print(f"Outside edit regions consistent={report['outside_edit_regions_consistent']}. Report: {args.out}")
    return 0 if report["outside_edit_regions_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
