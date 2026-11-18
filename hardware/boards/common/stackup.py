"""Write the board's layer stack-up, solder mask colour included, into a .kicad_pcb (replacing any already there).
The mask colour is what the renders show and what the shop is asked for: blue = the SMT editions, green = the
through-hole editions, so the two can never be mixed up on the bench.
    python3 stackup.py board.kicad_pcb Blue|Green
Plain Python (no KiCad needed): it edits the file's text."""
import re
import sys

TWO = [("F.Cu", "copper", 0.035), ("dielectric 1", "core", 1.51), ("B.Cu", "copper", 0.035)]
FOUR = [("F.Cu", "copper", 0.035), ("dielectric 1", "prepreg", 0.2104), ("In1.Cu", "copper", 0.0175),
        ("dielectric 2", "core", 1.065), ("In2.Cu", "copper", 0.0175), ("dielectric 3", "prepreg", 0.2104),
        ("B.Cu", "copper", 0.035)]


def stackup(layers, mask):
    out = ['\t\t(stackup',
           '\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))',
           '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))',
           f'\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "{mask}") (thickness 0.01))']
    for name, kind, t in layers:
        if kind == "copper":
            out.append(f'\t\t\t(layer "{name}" (type "copper") (thickness {t}))')
        else:
            er = 4.6 if kind == "core" else 4.4
            out.append(f'\t\t\t(layer "{name}" (type "{kind}") (thickness {t}) (material "FR4") (epsilon_r {er}) '
                       '(loss_tangent 0.02))')
    out += [f'\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "{mask}") (thickness 0.01))',
            '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))',
            '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))',
            '\t\t\t(copper_finish "ENIG")', '\t\t\t(dielectric_constraints no)', '\t\t)']
    return "\n".join(out) + "\n"


def apply(path, mask):
    text = open(path).read()
    layers = FOUR if '"In1.Cu"' in text.split("(setup", 1)[0] else TWO
    text = re.sub(r"\t\t\(stackup\n.*?\n\t\t\)\n", "", text, flags=re.S)
    i = text.index("\t(setup\n") + len("\t(setup\n")
    open(path, "w").write(text[:i] + stackup(layers, mask) + text[i:])


if __name__ == "__main__":
    apply(sys.argv[1], sys.argv[2])
    print(f"stack-up written, {sys.argv[2].lower()} solder mask:", sys.argv[1])
