"""3D models for the Tidal Link Interface renders (both editions), so a render shows the board as built, without the
VIC: J1 (the plug into the C64's VIC socket) = two 20-pin strips pointing DOWN from the back; J2 (the socket for the
VIC) = two 20-way socket strips on top. KiCad's DIP-40 footprints would draw a whole DIP chip instead. On the SMT
edition SW1 gets our own JS202011JCQN model (KiCad's library has none).
    <KiCad python> tli_models.py board.kicad_pcb        (gen_pcb.py calls apply() too)"""
import sys

import pcbnew

LIB = "${KICAD10_3DMODEL_DIR}/"
HEADER = LIB + "Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x20_P2.54mm_Vertical.step"
SOCKET = LIB + "Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x20_P2.54mm_Vertical.step"
SWITCH = "${KIPRJMOD}/../../../common/3d/SW_DPDT_CK_JS202011JCQN.wrl"   # (from generator/out/ to boards/common/)
BOARD_T = 1.6


def model(path, x=0.0, y=0.0, z=0.0, rot=(0.0, 0.0, 0.0)):
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = path
    m.m_Offset = pcbnew.VECTOR3D(x, y, z)
    m.m_Rotation = pcbnew.VECTOR3D(*rot)
    m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
    m.m_Show = True
    return m


def apply(board):
    for ref, models in (
            # the DIP footprints' own frame: pin 1 at the origin, pins 1-20 down one column, 21-40 up the other at
            # x 15.24. The plug's strips turned over (180 about y keeps the column order) and hung under the board.
            ("J1", [model(HEADER, 0, 0, -BOARD_T, (0, 180, 0)), model(HEADER, 15.24, 0, -BOARD_T, (0, 180, 0))]),
            ("J2", [model(SOCKET, 0, 0, 0), model(SOCKET, 15.24, 0, 0)])):
        fp = board.FindFootprintByReference(ref)
        fp.Models().clear()
        for m in models:
            fp.Add3DModel(m)
    sw = board.FindFootprintByReference("SW1")
    if sw and "JS202011JCQN" in sw.GetFPIDAsString():
        sw.Models().clear()
        sw.Add3DModel(model(SWITCH))


if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    apply(b)
    pcbnew.SaveBoard(sys.argv[1], b)
    print("3D models set:", sys.argv[1])
