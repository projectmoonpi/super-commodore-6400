"""A simple 3D model of the C&K JS202011JCQN (SMT DPDT slide switch) for renders: KiCad's library has the footprint
but no model. Metal-covered body 8.6 x 4.4 x 3.5 mm, slider 1.5 x 1.5 x 2.0 mm on top (at the INT end), six J-bend
legs down to the pads (x -2.5 / 0 / +2.5, y +-1.2 per the footprint). VRML units: 1 = 0.1 inch (KiCad's convention).
    python3 make_switch_wrl.py  ->  3d/SW_DPDT_CK_JS202011JCQN.wrl"""
import os

U = 1 / 2.54                                   # mm -> VRML units


def box(cx, cy, cz, sx, sy, sz, rgb, shine=0.3):
    return (f"Transform {{ translation {cx*U:.4f} {cy*U:.4f} {cz*U:.4f} children [ Shape {{ appearance Appearance {{ "
            f"material Material {{ diffuseColor {rgb} specularColor 0.5 0.5 0.5 shininess {shine} }} }} "
            f"geometry Box {{ size {sx*U:.4f} {sy*U:.4f} {sz*U:.4f} }} }} ] }}\n")


METAL, BLACK, TIN = "0.72 0.73 0.75", "0.08 0.08 0.08", "0.82 0.82 0.84"
out = ["#VRML V2.0 utf8\n"]
H = 3.5
out.append(box(0, 0, 0.15 + H / 2, 8.6, 4.4, H, METAL, 0.6))          # the body, sitting 0.15 mm above the board
out.append(box(0, 0, 0.15 + H - 0.05, 5.2, 1.6, 0.12, BLACK))           # the slot in the cover
out.append(box(-1.0, 0, 0.15 + H + 1.0, 1.5, 1.5, 2.0, BLACK))         # the slider (INT end, the pin-1 side)
for x in (-2.5, 0.0, 2.5):                                             # J-bend legs onto the pads
    for y in (-1.2, 1.2):
        out.append(box(x, y, 0.1, 0.5, 1.0, 0.2, TIN))                 # (model y is up the page: pads at +-1.2)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "3d"), exist_ok=True)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "3d", "SW_DPDT_CK_JS202011JCQN.wrl"), "w").writelines(out)
print("3d/SW_DPDT_CK_JS202011JCQN.wrl written")
