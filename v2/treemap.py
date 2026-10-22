"""Squarified treemap layout (Bruls, Huizing and van Wijk, 2000) for the basket by CPI weight. Plain Python, so the
app draws it with Altair rectangles and needs no extra package."""


def _worst(row, side):
    s = sum(row)
    return max(max(side * side * r / (s * s), s * s / (side * side * r)) for r in row) if s else float("inf")


def squarify(values, x, y, w, h):
    """values (positive, any order) -> [(x0, y0, x1, y1)] in the same order, filling the rectangle."""
    order = sorted(range(len(values)), key=lambda i: -values[i])
    total = sum(values)
    scale = (w * h) / total if total else 0
    areas = [values[i] * scale for i in order]
    out = [None] * len(values)
    k = 0
    while k < len(areas):
        side = min(w, h)
        row = [areas[k]]
        k += 1
        while k < len(areas) and _worst(row + [areas[k]], side) <= _worst(row, side):
            row.append(areas[k])
            k += 1
        s = sum(row)
        if w >= h:                                   # lay the row as a column on the left
            col = s / h
            yy = y
            for j, a in enumerate(row):
                hh = a / col
                out[order[k - len(row) + j]] = (x, yy, x + col, yy + hh)
                yy += hh
            x, w = x + col, w - col
        else:                                        # lay the row along the top
            rowh = s / w
            xx = x
            for j, a in enumerate(row):
                ww = a / rowh
                out[order[k - len(row) + j]] = (xx, y, xx + ww, y + rowh)
                xx += ww
            y, h = y + rowh, h - rowh
    return out


def layout(groups, width=100.0, height=60.0):
    """groups: [{'code', 'name', 'weight', 'items': [{'code', 'name', 'weight'}]}] -> flat list of tiles
    {'code', 'name', 'group', 'weight', 'x0', 'y0', 'x1', 'y1'}; a group's items sit inside the group's rectangle and
    the rest of the group is its residual tile."""
    tiles = []
    boxes = squarify([g["weight"] for g in groups], 0.0, 0.0, width, height)
    for g, (x0, y0, x1, y1) in zip(groups, boxes):
        parts = [dict(i, group=g["code"]) for i in g.get("items", [])]
        rest = g["weight"] - sum(i["weight"] for i in parts)
        if rest > 1e-9:
            parts.append({"code": g["code"] + "#rest", "name": g["name"], "weight": rest, "group": g["code"]})
        for p, (a, b, c, d) in zip(parts, squarify([p["weight"] for p in parts], x0, y0, x1 - x0, y1 - y0)):
            tiles.append({**p, "x0": a, "y0": b, "x1": c, "y1": d})
    return tiles
