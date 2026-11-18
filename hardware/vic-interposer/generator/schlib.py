"""What both schematic pages share: KiCad's own symbols read from its library, and the bits every item needs."""
import math
import os
import uuid

import sexpr
from sexpr import Sym, find, first

SYMDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
_libs = {}


def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    if lib not in _libs:
        path = (os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub.kicad_sym") if lib == "Hub"
                else f"{SYMDIR}/{lib}.kicad_sym")
        tree = sexpr.parse(open(path).read())
        _libs[lib] = {s[1]: s for s in find(tree, "symbol")}
    syms = _libs[lib]
    s = syms[name]
    ext = first(s, "extends")
    if ext:   # flatten: parent's drawing + child's properties
        parent = syms[ext[1]]
        props = {p[1]: p for p in find(s, "property")}
        flat = [Sym("symbol"), name]
        for c in parent[2:]:
            if isinstance(c, list) and c[0] == "property" and c[1] in props:
                flat.append(props.pop(c[1]))
            elif isinstance(c, list) and c[0] == "symbol":
                flat.append([c[0], c[1].replace(ext[1], name, 1)] + c[2:])
            else:
                flat.append(c)
        at = max(i for i, c in enumerate(flat) if isinstance(c, list) and c[0] == "property") + 1
        flat[at:at] = list(props.values())          # child-only properties (e.g. ki_fp_filters)
        s = flat
    return [s[0], lib_id] + s[2:]


def pins_of(sym, unit=None):
    """{pin number: (x, y)}; with unit, only that unit's pins (a sub-symbol NAME_<unit>_<style>; unit 0 is shared)."""
    out = {}

    def walk(node):
        for c in node:
            if isinstance(c, list) and c and c[0] == "pin":
                at = first(c, "at")
                out[first(c, "number")[1]] = (float(at[1]), float(at[2]))
            elif isinstance(c, list) and c and c[0] == "symbol":
                if unit is not None and c[1].rsplit("_", 2)[-2] not in ("0", str(unit)):
                    continue
                walk(c)
    walk(sym)
    return out


def U():
    return [Sym("uuid"), str(uuid.uuid4())]


def eff(size=1.27, hide=False, justify=None, bold=False):
    font = [Sym("font"), [Sym("size"), size, size]] + ([[Sym("bold"), Sym("yes")]] if bold else [])
    e = [Sym("effects"), font]
    js = [j for j in (justify or "").split() if j != "center"]      # centred is KiCad's default (no keyword)
    if js:
        e.append([Sym("justify")] + [Sym(j) for j in js])
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    return e


def R4(v):
    return round(v + 0.0, 4)


def pt(x, y):
    return (R4(x), R4(y))


def sym_box(sym):
    """What a library symbol covers (its own coordinates, y up): its drawing as one box, and each pin's line as
    its own thin box (a chip's long pins don't block the space between them)."""
    xs, ys, pins_ = [], [], []

    def walk(node):
        for c in node:
            if not (isinstance(c, list) and c):
                continue
            if c[0] == "symbol":
                walk(c)
            elif c[0] == "rectangle":
                for k in ("start", "end"):
                    a = first(c, k); xs.append(float(a[1])); ys.append(float(a[2]))
            elif c[0] == "polyline":
                for q in find(first(c, "pts"), "xy"):
                    xs.append(float(q[1])); ys.append(float(q[2]))
            elif c[0] == "circle":
                a, rr = first(c, "center"), float(first(c, "radius")[1])
                xs.extend([float(a[1]) - rr, float(a[1]) + rr]); ys.extend([float(a[2]) - rr, float(a[2]) + rr])
            elif c[0] == "arc":
                for k in ("start", "mid", "end"):
                    a = first(c, k); xs.append(float(a[1])); ys.append(float(a[2]))
            elif c[0] == "pin":
                a, ln = first(c, "at"), float(first(c, "length")[1])
                px, py, ang = float(a[1]), float(a[2]), math.radians(float(a[3]) if len(a) > 3 else 0)
                qx, qy = px + ln * math.cos(ang), py + ln * math.sin(ang)
                pins_.append((min(px, qx) - 0.3, min(py, qy) - 0.3, max(px, qx) + 0.3, max(py, qy) + 0.3))
    walk(sym)
    return ([(min(xs), min(ys), max(xs), max(ys))] if xs else []) + pins_
