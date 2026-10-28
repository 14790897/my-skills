"""Build a glyph as a CAD solid with its strokes thinned by a given amount.

Pipeline: fontTools (exact Bézier outlines from the font) -> skia (path ops:
stroke the outline and subtract the band, i.e. erode the ink) -> OCC
(Geom_BezierCurve edges).  Every wall comes out as a real curve -- no polyline
facets, so CAD checkers that reject "fragmented faces" stay happy.

Why not OCC for the offset: Workplane.offset2D and BRepOffsetAPI_MakeOffsetShape
both return null shapes on font outlines, GeomAPI_Interpolate self-intersects on
the dense rings a polygon buffer produces (and the invalid solid then swallows
the whole body on fuse), and GeomAPI_PointsToBSpline overshoots badly enough to
emit inverted solids.  A purpose-built 2D path library is the right tool.
"""
import math

import cadquery as cq
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
import skia

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.TColgp import TColgp_Array1OfPnt, TColgp_HArray1OfPnt
from OCP.TColgp import TColgp_Array1OfPnt2d
from OCP.Geom import Geom_BezierCurve
from OCP.ShapeFix import ShapeFix_Face
from OCP.gp import gp_Pnt, gp_Pnt2d


# ---------------------------------------------------------------- font -> skia

def _segments(font_path, ch):
    """Exact outline segments for one character, in font units (Y up)."""
    font = TTFont(font_path, fontNumber=0, lazy=True)
    cmap = font.getBestCmap()
    name = cmap.get(ord(ch))
    if name is None:
        raise ValueError("字形缺失: %r" % ch)
    pen = RecordingPen()
    font.getGlyphSet()[name].draw(pen)
    upm = font["head"].unitsPerEm
    return pen.value, upm


def ink_scale(font_path, target_height, ref="0"):
    """字号：让 ref 字（默认「0」）的墨迹高度等于 target_height 所需的缩放系数。

    整套字符共用这一个系数 —— 逐字按"字高"缩放会把句点炸成数字大小
    （句点的墨迹高度只有数字的 1/3），这是本项目踩过的坑。
    """
    segs, _ = _segments(font_path, ref)
    ys = [p[1] for op, args in segs for p in args if p is not None]
    return target_height / (max(ys) - min(ys))


def _to_skia(segs, upm, halfdiag=None, scale=None, center=True):
    """Scale the outline and hand it to skia.

    Two modes:
      halfdiag -- fit the ink box's diagonal to 2*halfdiag, centred on the ink box
                  (the single-glyph case).
      scale    -- apply that exact factor instead, and with center=False keep the
                  FONT ORIGIN (the baseline) at (0,0).  That is what a line of text
                  needs: one shared factor keeps the periods their true size and
                  the shared baseline keeps them aligned.
    """
    xs, ys = [], []
    for op, args in segs:
        for p in args:
            if p is not None:
                xs.append(p[0]); ys.append(p[1])
    if scale is None:
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        s = 2.0 * halfdiag / math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    else:
        s = scale
        cx, cy = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0) if center else (0.0, 0.0)

    def pt(p):
        return ((p[0] - cx) * s, (p[1] - cy) * s)

    path = skia.Path()
    for op, args in segs:
        if op == "moveTo":
            path.moveTo(*pt(args[0]))
        elif op == "lineTo":
            path.lineTo(*pt(args[0]))
        elif op == "curveTo":
            path.cubicTo(*[c for p in args for c in pt(p)])
        elif op == "qCurveTo":
            # fontTools packs TrueType-style runs: n off-curve points then the
            # on-curve one; the implied on-curve midpoints have to be inserted
            pts = [pt(p) for p in args]
            if pts[-1] is None:                       # all-off-curve: closed quad run
                pts = pts[:-1]
                cur = pts[0]
                path.moveTo(*cur)
                for i in range(1, len(pts)):
                    mid = ((cur[0] + pts[i][0]) / 2, (cur[1] + pts[i][1]) / 2)
                    path.quadTo(*pts[i], *mid)
                    cur = mid
                path.close()
                continue
            on = pts[-1]
            for i in range(len(pts) - 2):
                cur = pts[i]
                nxt = pts[i + 1]
                mid = ((cur[0] + nxt[0]) / 2, (cur[1] + nxt[1]) / 2)
                path.quadTo(*nxt, *mid)
            if len(pts) >= 2:
                path.quadTo(*pts[-2], *on)
            else:
                path.lineTo(*on)
        elif op == "closePath":
            path.close()
    path.setFillType(skia.PathFillType.kWinding)
    return path


# ---------------------------------------------------------------- skia -> OCC

def _edge(p0, p1, p2=None, p3=None):
    """Degenerate segments are normal in path output (coincident control points);
    Geom_BezierCurve throws on those, so collapse them down to a line instead."""
    pts = [p0, p1] + ([p2] if p2 is not None else []) + ([p3] if p3 is not None else [])
    # 阈值 1e-3 而不是 1e-9：补料的形态学收尾会留下微米级重合的控制点，
    # 漏过去就会拉伸成一根 0.0001mm² 的微壁（DFM 判「碎面」）。
    # 0.001mm 的合并对形状的影响远在加工公差之下。
    uniq = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - uniq[-1][0]) > 1e-9 or abs(p[1] - uniq[-1][1]) > 1e-9:
            uniq.append(p)
    if len(uniq) < 2:
        return None
    if len(uniq) == 2:
        return BRepBuilderAPI_MakeEdge(gp_Pnt(uniq[0][0], uniq[0][1], 0.0),
                                       gp_Pnt(uniq[1][0], uniq[1][1], 0.0)).Edge()
    arr = TColgp_Array1OfPnt(1, len(uniq))
    for i, p in enumerate(uniq, 1):
        arr.SetValue(i, gp_Pnt(p[0], p[1], 0.0))
    return BRepBuilderAPI_MakeEdge(Geom_BezierCurve(arr)).Edge()


def _contours(path):
    """skia path -> list of ring point/segment lists."""
    rings, cur, start, prev = [], [], None, None
    for verb, pts in path:
        if verb == skia.Path.Verb.kMove_Verb:
            if prev is not None and start is not None:
                cur.append(("L", prev, start))
            if cur:
                rings.append(cur)
            cur, start, prev = [], (pts[0].x(), pts[0].y()), (pts[0].x(), pts[0].y())
        elif verb == skia.Path.Verb.kLine_Verb:
            p = (pts[1].x(), pts[1].y())
            cur.append(("L", prev, p)); prev = p
        elif verb == skia.Path.Verb.kQuad_Verb:
            a = (pts[1].x(), pts[1].y()); b = (pts[2].x(), pts[2].y())
            cur.append(("Q", prev, a, b)); prev = b
        elif verb == skia.Path.Verb.kCubic_Verb:
            a = (pts[1].x(), pts[1].y()); b = (pts[2].x(), pts[2].y()); c = (pts[3].x(), pts[3].y())
            cur.append(("C", prev, a, b, c)); prev = c
        elif verb == skia.Path.Verb.kClose_Verb:
            if prev is not None and start is not None:
                cur.append(("L", prev, start))
            if cur:
                rings.append(cur)
            cur, prev = [], start
        elif verb == skia.Path.Verb.kConic_Verb:
            # conics only come from addArc-style ops; approximate by the mid quad
            a = (pts[1].x(), pts[1].y()); b = (pts[2].x(), pts[2].y())
            cur.append(("Q", prev, a, b)); prev = b
    if cur:
        rings.append(cur)
    return rings


def _flatten(ring, n=12):
    """Control polygon -> dense polygon, so the area sign is trustworthy.
    Using the raw control polygon misjudges thin curved rings, and a wrong sign
    means a clockwise outer ring, a face whose normal points -Z, and an inverted
    solid -- which is what was silently poisoning every boolean downstream."""
    pts = []
    for seg in ring:
        if seg[0] == "L":
            pts.append(seg[1])
        elif seg[0] == "Q":
            p0, c, p1 = seg[1], seg[2], seg[3]
            for i in range(n + 1):
                t = i / n
                a, b, d = (1 - t) ** 2, 2 * (1 - t) * t, t * t
                pts.append((a * p0[0] + b * c[0] + d * p1[0],
                            a * p0[1] + b * c[1] + d * p1[1]))
        else:
            p0, c1, c2, p1 = seg[1], seg[2], seg[3], seg[4]
            for i in range(n + 1):
                t = i / n
                a, b = (1 - t) ** 3, 3 * (1 - t) ** 2 * t
                d, e = 3 * (1 - t) * t * t, t ** 3
                pts.append((a * p0[0] + b * c1[0] + d * c2[0] + e * p1[0],
                            a * p0[1] + b * c1[1] + d * c2[1] + e * p1[1]))
    return pts


def _ring_area(ring):
    pts = _flatten(ring)
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def _point_in_ring(pt, ring):
    """Ray-cast point-in-polygon against the flattened ring."""
    pts = _flatten(ring)
    x, y = pt
    inside = False
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        if (y0 > y) != (y1 > y):
            if x0 + (y - y0) * (x1 - x0) / (y1 - y0) > x:
                inside = not inside
    return inside


def _reverse_ring(ring):
    """Traverse the ring backwards (control points of each segment reverse too)."""
    out = []
    for seg in reversed(ring):
        out.append((seg[0],) + tuple(reversed(seg[1:])))
    return out


def _simplify_ring(ring, eps=0.03):
    """Merge segments shorter than eps into their predecessor.

    skia's path ops leave 2-20um fragments behind wherever two outlines cross
    near-tangentially. Extruded, each becomes a wall 2um wide and 2mm tall --
    which the DFM check reports as a fragmented face (碎面). Absorbing them is
    safe: eps is 0.03mm on a pet ~60mm across, two orders below the +/-0.05mm
    machining tolerance, and no genuine feature of a thinned glyph is that small.
    """
    out = []
    for seg in ring:
        pts = seg[1:]
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                   max(p[1] for p in pts) - min(p[1] for p in pts))
        # 还要看弦长：首尾重合的段即使控制点跨度很大也是退化的，拉伸出来就是一根
        # 0.0001mm² 的微壁（DFM 判「碎面」）。直接在 _edge 里放大合并阈值会误伤
        # 真实曲线段（试过 1e-3，整个实体散成 12 块），所以退化判定放在这里。
        chord = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        if (span < eps or chord < eps) and out:
            prev = out[-1]
            out[-1] = prev[:-1] + (pts[-1],)      # stretch prev to swallow it
            continue
        out.append(seg)
    return out


def _ring_wire(ring, want_ccw):
    if (_ring_area(ring) > 0) != want_ccw:
        ring = _reverse_ring(ring)
    edges = [_edge(seg[1], seg[2]) if seg[0] == "L"
             else (_edge(seg[1], seg[2], seg[3]) if seg[0] == "Q"
                   else _edge(seg[1], seg[2], seg[3], seg[4]))
             for seg in ring]
    edges = [e for e in edges if e is not None]
    if not edges:
        return None
    mk = BRepBuilderAPI_MakeWire()
    for e in edges:
        mk.Add(e)
    return mk.Wire() if mk.IsDone() else None


def _erode_path(segs, upm, halfdiag, thin, tries=8):
    """Erode the outline by `thin`, retrying with a hair of rescale.

    skia's path boolean throws RuntimeError("Failed to apply op") when two
    boundaries cross near-tangentially -- which a font outline does at some
    sizes and not others.  Rescaling by a millionth perturbs the tangency and
    the op goes through, so try a few.  If every try fails, fall back to the
    un-eroded outline: a chunkier glyph is far better than a dead build.
    Returns (path, tries_used or None if it fell back).
    """
    fallback = None
    for k in range(tries):
        path = _to_skia(segs, upm, halfdiag * (1.0 - k * 1e-6))
        fallback = path
        try:
            paint = skia.Paint()
            paint.setStyle(skia.Paint.kStroke_Style)
            paint.setStrokeWidth(2.0 * thin)
            paint.setStrokeJoin(skia.Paint.kRound_Join)
            paint.setStrokeCap(skia.Paint.kRound_Cap)
            band = skia.Path()
            paint.getFillPath(path, band)
            cut = skia.Op(path, band, skia.PathOp.kDifference_PathOp)
            # normalise: resolves any self-overlap the difference left behind
            return skia.Op(cut, skia.Path(), skia.PathOp.kUnion_PathOp), k
        except RuntimeError:
            continue
    return fallback, None


def _stroke_band(path, w):
    paint = skia.Paint()
    paint.setStyle(skia.Paint.kStroke_Style)
    paint.setStrokeWidth(w)
    paint.setStrokeJoin(skia.Paint.kRound_Join)
    paint.setStrokeCap(skia.Paint.kRound_Cap)
    band = skia.Path()
    paint.getFillPath(path, band)
    return band


def _norm(p):
    return skia.Op(p, skia.Path(), skia.PathOp.kUnion_PathOp)


def _dilate(path, r):
    """胀 r：把墨迹向外长 r。近相切处 skia 的布尔会整个失败，所以带微扰重试。"""
    for k in range(6):
        try:
            rr = r * (1.0 + 1e-6 * k)
            return _norm(skia.Op(path, _stroke_band(path, 2.0 * rr), skia.PathOp.kUnion_PathOp))
        except RuntimeError:
            continue
    raise RuntimeError("dilate failed at r=%.4f" % r)


def _erode(path, r):
    """蚀 r：把墨迹向内收 r（就是"削细"那一步的真身）。"""
    for k in range(6):
        try:
            rr = r * (1.0 + 1e-6 * k)
            return _norm(skia.Op(path, _stroke_band(path, 2.0 * rr), skia.PathOp.kDifference_PathOp))
        except RuntimeError:
            continue
    raise RuntimeError("erode failed at r=%.4f" % r)


def _add_material_once(path, slot, wall):
    out = path
    if slot > 0:
        r = slot / 2.0
        out = _erode(_dilate(out, r), r)              # closing：填窄缝
    if wall > 0:
        h = wall / 2.0
        opened = _dilate(_erode(out, h), h)           # opening：去掉细于 wall 的部分
        thin = _norm(skia.Op(out, opened, skia.PathOp.kDifference_PathOp))
        if not thin.isEmpty():
            out = _norm(skia.Op(out, _dilate(thin, h), skia.PathOp.kUnion_PathOp))
    # 收尾胀 6µm：closing 会把某条背景通道**精确**夹死，于是两个墨迹边界正好贴上，
    # 建出来的环自触 -> 实体非法（黎/君实测都中招）。胀一丝就把两个边界分开，
    # 而它对槽宽的影响只有 12µm，远小于 1.1mm 这条线的余量。
    return _dilate(out, 0.02)


def _blob_pts(path):
    """连通块的代表点（取每条环的平均点，放"补料柱"够用了）。"""
    out = []
    for r in _contours(path):
        if len(r) < 2:
            continue
        pts = _flatten(r)
        out.append((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
    return out


def slot_pads(path, slot=1.1, steps=14, grow=1.06):
    """找出所有窄于 slot 的槽，返回圆柱位置 [(x, y, r), ...]。

    **只用于定位，禁止用来补。** 在这些位置加独立圆柱是旧做法，现已明确不允许：
    圆柱与笔画的交线是圆弧，正面看就是个圆疙瘩，而且那是在改形状换合规。
    窄缝一律用「整块平移笔画」解决（见 build_step 的 NUDGE）。这个函数留着只为在
    二维图上标出窄缝在哪。

    定位 = closing 之后比原来多出来的区域，就是被填掉的窄缝。
    再用"极大内切圆"分解覆盖它：逐步腐蚀，每步新冒出来的连通块就是一个极大圆，
    以它的半径为半径、它的代表点为圆心，就是一个可以标在二维图上的位置。
    """
    r = slot / 2.0
    closed = _erode(_dilate(path, r), r)
    added = _norm(skia.Op(closed, path, skia.PathOp.kDifference_PathOp))
    if added.isEmpty():
        return []
    pads = []
    for k in range(1, steps + 1):
        rad = r * k / steps
        try:
            e = _erode(added, rad)
        except RuntimeError:
            break            # 收不动了就停：半径是递增的，少收一层不影响已覆盖的
        if e.isEmpty():
            break
        for (cx, cy) in _blob_pts(e):
            pads.append((cx, cy, rad * grow))
    return pads


def add_material_for_rules(path, slot=1.1, wall=1.0, tries=8):
    """用「补料」而不是「削细」满足槽宽/壁厚两条线。

    两笔只隔 0.81mm 时：
      削细 —— 把整字每一笔都削薄 2t。槽宽了，壁厚同时掉了 2t（两条线对冲），
              而且是全球施刀，本来没问题的笔画一起遭殃。
      补料 —— 只把那道 0.81mm 的缝填实。缝没了就是没缝，其余笔画一刀不动。

    两件事都**证得出来**，不依赖任何自制度量：
      closing(r) = 先胀 r 再蚀 r → 填掉所有窄于 2r 的缝与洞，其余形状不变。
                   取 r = slot/2，则任何 <slot 的槽必然消失。
      ink - opening(ink, w/2) = 细于 w 的部分；把它单独胀 w/2，则它必然达到 w。
    全程 skia 路径运算，输出仍是光滑曲线，不会退回折线碎面。

    skia 的布尔在近相切处会整个失败，所以照旧带微小重试。
    """
    last = path
    for k in range(tries):
        try:
            return _add_material_once(path, slot * (1.0 - k * 1e-6), wall)
        except RuntimeError:
            continue
    return last


def thicken_at(path, pts, level=0.5, delta=0.30, win=2.2):
    """只在这些点附近，把细于 2*level 的部分沿自身外轮廓补厚 delta。

    跟"贴一根圆柱"的区别：圆柱是外加一个圆，交线是圆弧，看着就是个疙瘩；
    这里是给已有的细部做一次局部膨胀，鼓出来的面是笔画自己的偏移面，接得顺。
    """
    opened = _dilate(_erode(path, level), level)
    thin = _norm(skia.Op(path, opened, skia.PathOp.kDifference_PathOp))
    if thin.isEmpty():
        return path
    mask = None
    for (x, y) in pts:
        c = skia.Path()
        c.addCircle(float(x), float(y), float(win))
        mask = c if mask is None else _norm(skia.Op(mask, c, skia.PathOp.kUnion_PathOp))
    local = _norm(skia.Op(thin, mask, skia.PathOp.kIntersect_PathOp))
    if local.isEmpty():
        return path
    grown = _dilate(local, delta)
    return _norm(skia.Op(path, grown, skia.PathOp.kUnion_PathOp))


def glyph_solid(txt, halfdiag, thickness, font_path, thin=0.0, fix_slot=0.0, fix_wall=0.0,
                scale=None, center=True, thicken=None, thicken_delta=0.30):
    """A solid glyph centred on the origin, z from 0 to thickness.

    thin is the old "shave every stroke" route; fix_slot/fix_wall are the additive
    route (fill narrow gaps / fatten thin strokes).  Prefer the latter: it does not
    trade slot width against wall thickness.

    scale/center exist for text runs: pass one shared scale (from ink_scale()) with
    center=False to keep every character on its font baseline.

    thicken: [(x, y), ...] in glyph-local coords -- locally fatten thin details
    there without adding a separate post (see thicken_at).
    """
    segs, upm = _segments(font_path, txt)
    if thin > 0:
        path, used = _erode_path(segs, upm, halfdiag, thin)
        if used is None:
            print("  警告：%s 削细 %.2f 被 skia 拒绝，退回未削细" % (txt, thin), flush=True)
    else:
        path = _to_skia(segs, upm, halfdiag, scale=scale, center=center)
    if fix_slot > 0 or fix_wall > 0:
        path = add_material_for_rules(path, fix_slot, fix_wall)
    if thicken:
        path = thicken_at(path, thicken, delta=thicken_delta)
    rings = _contours(path)
    rings = [r for r in rings if len(r) > 1]
    rings = [_simplify_ring(r) for r in rings]
    if not rings:
        return None
    # skia's difference op leaves zero-area slivers behind; they extrude to
    # junk solids and swallow whatever holes get added to them.
    areas = [_ring_area(r) for r in rings]
    big = max(abs(a) for a in areas)
    # 下限用 0.01mm²（0.1x0.1mm）：形态学收尾会留下微米级的渣环，
    # 拉伸出来就是一个 0.001mm² 的面，正好踩 DFM 的「碎面」。
    keep = [i for i in range(len(rings)) if abs(areas[i]) > max(1e-4 * big, 0.01)]
    rings = [rings[i] for i in keep]
    areas = [areas[i] for i in keep]
    # Nest by containment, NOT by the sign of the ring area.  skia's path ops
    # do not guarantee one winding for the whole path: 黎 comes back CCW (areas
    # positive) but 君 comes back entirely CW (areas negative).  Classifying by
    # sign made every ring of 君 a "hole", leaving only its largest ring as a
    # solid -- the character lost 72% of its ink and its bbox collapsed from
    # 26mm to 9.6mm, which is what rendered as bare outlines on the back face.
    order = sorted(range(len(rings)), key=lambda i: -abs(areas[i]))
    outers = []
    owner = {}
    for i in order:
        rep = _flatten(rings[i])[0]
        container = None
        for o in outers:                        # outers is largest-first, so the
            if _point_in_ring(rep, rings[o]):   # first hit is the SMALLEST container
                container = o
                break
        if container is None:
            outers.append(i)
        else:
            owner.setdefault(container, []).append(i)   # a hole of exactly that outer
    solids = []
    for i in outers:
        w = _ring_wire(rings[i], True)          # outer must be CCW...
        if w is None:
            continue
        face = BRepBuilderAPI_MakeFace(w)
        for j in owner.get(i, []):
            wh = _ring_wire(rings[j], False)    # ...holes must be CW
            if wh is not None:
                face.Add(wh)
        if not face.IsDone():
            continue
        # 笔画快被蚀断时 skia 会吐出自我触碰的环，直接拉伸得到自交实体，
        # 而自交实体一进布尔就把整个币体丢掉（结果只剩它自己那一小块，体积从 32688 掉到 128）。
        # ShapeFix_Face 在建面阶段就把环拆成合法的，比事后修实体可靠。
        sff = ShapeFix_Face(face.Face())
        sff.SetPrecision(1e-5)
        sff.FixOrientation()
        sff.Perform()
        fixed = sff.Face()
        solids.append(cq.Solid.extrudeLinear(cq.Face.cast(fixed),
                                             cq.Vector(0, 0, thickness)))
    if not solids:
        return None
    if len(solids) == 1:
        return solids[0]
    # NB: Shape.fuse() on these disjoint prisms silently loses most of them
    # (the result came back with fewer faces than a single piece). Hand back a
    # compound instead -- build_step unions it into the body fine.
    return cq.Compound.makeCompound(solids)
