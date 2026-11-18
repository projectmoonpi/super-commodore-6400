/*
 * packsim -- two (or more) C64s joined by user-port cables, for testing the Super Commodore 6400 link.
 *
 * Each machine: a 6510 (all documented opcodes, cycle counts with page-cross and branch penalties),
 * 64 KB RAM, the C64 memory map ($01: char ROM, I/O; no BASIC/KERNAL ROMs -- our programs do not use
 * them), colour RAM, the VIC-II registers with raster interrupts (no cycle stealing), CIA 1 timers
 * A/B (chained) and CIA 2 port B.
 * Machine 0 is the leader. Machines 1..N-1 are cores. Port B of the leader and port B of core 1 are
 * wired together as in src/common.asm (PB0-7 straight, PC2 -> FLAG both ways). (One cable for now;
 * more cores need the hub.) A read or write of port B pulses PC2, which sets FLAG (ICR bit 4) on the
 * other machine. If both machines drive a data line to different levels, that is counted as
 * contention -- which the protocol must never cause.
 *
 * The machines run interleaved: the one that is furthest behind in cycles runs the next instruction.
 * The run ends when the leader executes a JMP to itself (the auto build's "halt"), or after the cycle
 * limit. Each machine's memory is then written to OUT.<n>.bin: 64 KB RAM, 1 KB colour RAM, 64 VIC
 * registers, CIA 2 port A.
 *
 * usage: packsim CHARGEN LEADER.prg [CORE.prg] OUT MAXCYCLES
 * Designed and Created by Project Moon Pi.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct {
    uint8_t pra, prb, ddra, ddrb, icr, mask, cra, crb;
    uint16_t ta, tb, tal, tbl;
    uint64_t last;
} Cia;

typedef struct {
    uint8_t ram[65536], colram[1024], vic[64];
    uint8_t port01;
    uint16_t pc;
    uint8_t a, x, y, sp, p;
    uint64_t cyc;
    int lastline;
    uint8_t latch;
    Cia c1, c2;
    int halted;
    uint64_t pulses;
} M;

static M mach[2];
static int nm;
static uint8_t chargen[4096];
static uint64_t contention;
/* scripted key presses for the leader: PACKSIM_KEYS="cycle:key,..." (key 1-8 or s), each held 0.2 s */
static struct { uint64_t at; uint8_t col, row; } keys[16];
static int nkeys;
static void parse_keys(void) {
    const char *e = getenv("PACKSIM_KEYS");
    static const char *names = "12345678s";
    static const uint8_t col[] = {0x7f, 0x7f, 0xfd, 0xfd, 0xfb, 0xfb, 0xf7, 0xf7, 0xfd};
    static const uint8_t row[] = {0x01, 0x08, 0x01, 0x08, 0x01, 0x08, 0x01, 0x08, 0x20};
    while (e && *e && nkeys < 16) {
        unsigned long long at; char k;
        if (sscanf(e, "%llu:%c", &at, &k) != 2) break;
        const char *q = strchr(names, k);
        if (q) { keys[nkeys].at = at; keys[nkeys].col = col[q - names]; keys[nkeys].row = row[q - names]; nkeys++; }
        e = strchr(e, ',');
        if (e) e++;
    }
}

enum { FC = 1, FZ = 2, FI = 4, FD = 8, FB = 16, FU = 32, FV = 64, FN = 128 };

/* ---------------- the cable ---------------- */
static uint8_t pins(void) {
    if (nm < 2) {
        M *m = &mach[0];
        return (uint8_t)((m->c2.prb & m->c2.ddrb) | (~m->c2.ddrb & 0xff));
    }
    uint8_t d0 = mach[0].c2.ddrb, d1 = mach[1].c2.ddrb;
    uint8_t v0 = mach[0].c2.prb, v1 = mach[1].c2.prb;
    if ((v0 ^ v1) & d0 & d1) contention++;
    return (uint8_t)((~(d0 | d1) & 0xff) | (v0 & d0) | (v1 & d1 & ~d0));
}
static void pc2_pulse(M *m) {
    m->pulses++;
    if (nm < 2) return;
    M *o = (m == &mach[0]) ? &mach[1] : &mach[0];
    o->c2.icr |= 0x10;
}

/* ---------------- CIA timers (CIA 1 only needs them) ---------------- */
static void cia_run(Cia *c, uint64_t now) {
    uint64_t n = now - c->last;
    c->last = now;
    if (!n) return;
    uint64_t uf = 0;
    if (c->cra & 1) {
        if (n <= c->ta) c->ta -= (uint16_t)n;
        else {
            uint64_t n2 = n - c->ta - 1, per = (uint64_t)c->tal + 1;
            uf = 1 + n2 / per;
            c->ta = (uint16_t)(c->tal - (n2 % per));
            c->icr |= 1;
        }
    }
    if (c->crb & 1) {
        uint64_t m = ((c->crb & 0x60) == 0x40) ? uf : ((c->crb & 0x60) == 0 ? n : 0);
        if (m) {
            if (m <= c->tb) c->tb -= (uint16_t)m;
            else {
                uint64_t m2 = m - c->tb - 1, per = (uint64_t)c->tbl + 1;
                c->tb = (uint16_t)(c->tbl - (m2 % per));
                c->icr |= 2;
            }
        }
    }
}
static uint8_t cia_read(M *m, Cia *c, int r, int is2) {
    if (!is2) cia_run(c, m->cyc);
    switch (r) {
    case 0: return is2 ? (uint8_t)((c->pra & c->ddra) | (~c->ddra & 0xff)) : 0xff;
    case 1:
        if (is2) { uint8_t v = (uint8_t)((c->prb & c->ddrb) | (pins() & ~c->ddrb)); pc2_pulse(m); return v; }
        if (m == &mach[0]) {                            /* keyboard: scripted keys */
            uint8_t v = 0xff;
            for (int i = 0; i < nkeys; i++)
                if (m->cyc >= keys[i].at && m->cyc < keys[i].at + 200000 && !(c->pra & ~keys[i].col & 0xff))
                    v &= ~keys[i].row;
            return v;
        }
        return 0xff;
    case 2: return c->ddra;
    case 3: return c->ddrb;
    case 4: return c->ta & 0xff;
    case 5: return c->ta >> 8;
    case 6: return c->tb & 0xff;
    case 7: return c->tb >> 8;
    case 13: { uint8_t v = c->icr | ((c->icr & c->mask) ? 0x80 : 0); c->icr = 0; return v; }
    case 14: return c->cra;
    case 15: return c->crb;
    }
    return 0;
}
static void cia_write(M *m, Cia *c, int r, uint8_t v, int is2) {
    if (!is2) cia_run(c, m->cyc);
    switch (r) {
    case 0: c->pra = v; break;
    case 1: c->prb = v; if (is2) { pins(); pc2_pulse(m); } break;
    case 2: c->ddra = v; break;
    case 3: c->ddrb = v; if (is2) pins(); break;
    case 4: c->tal = (c->tal & 0xff00) | v; break;
    case 5: c->tal = (c->tal & 0xff) | (v << 8); if (!(c->cra & 1)) c->ta = c->tal; break;
    case 6: c->tbl = (c->tbl & 0xff00) | v; break;
    case 7: c->tbl = (c->tbl & 0xff) | (v << 8); if (!(c->crb & 1)) c->tb = c->tbl; break;
    case 13: if (v & 0x80) c->mask |= v & 0x7f; else c->mask &= ~v; break;
    case 14: if (v & 0x10) c->ta = c->tal; c->cra = v & 0xef; break;
    case 15: if (v & 0x10) c->tb = c->tbl; c->crb = v & 0xef; break;
    }
}

/* ---------------- memory map ---------------- */
static int raster(M *m) { return (int)((m->cyc / 65) % 263); }

static uint8_t io_read(M *m, uint16_t a) {
    if (a < 0xd400) {
        int r = a & 0x3f, line = raster(m);
        if (r == 0x11) return (uint8_t)((m->vic[0x11] & 0x7f) | ((line & 0x100) >> 1));
        if (r == 0x12) return (uint8_t)line;
        if (r == 0x19) return (uint8_t)(m->latch | ((m->latch & m->vic[0x1a] & 15) ? 0x80 : 0) | 0x70);
        return m->vic[r];
    }
    if (a < 0xd800) return 0;
    if (a < 0xdc00) return (uint8_t)(m->colram[a & 0x3ff] | 0xf0);
    if (a < 0xdd00) return cia_read(m, &m->c1, a & 15, 0);
    if (a < 0xde00) return cia_read(m, &m->c2, a & 15, 1);
    return 0xff;
}
static void io_write(M *m, uint16_t a, uint8_t v) {
    if (a < 0xd400) {
        int r = a & 0x3f;
        if (r == 0x19) { m->latch &= ~v; return; }
        m->vic[r] = v;
        return;
    }
    if (a < 0xd800) return;
    if (a < 0xdc00) { m->colram[a & 0x3ff] = v & 15; return; }
    if (a < 0xdd00) { cia_write(m, &m->c1, a & 15, v, 0); return; }
    if (a < 0xde00) { cia_write(m, &m->c2, a & 15, v, 1); return; }
}
static uint8_t rd(M *m, uint16_t a) {
    if (a == 1) return m->port01;
    if (a >= 0xd000 && a < 0xe000 && (m->port01 & 3)) {
        if (m->port01 & 4) return io_read(m, a);
        return chargen[a & 0xfff];
    }
    if (a >= 0xa000 && a < 0xc000 && (m->port01 & 3) == 3) return 0;
    if (a >= 0xe000 && (m->port01 & 2)) return 0;
    return m->ram[a];
}
static void wr(M *m, uint16_t a, uint8_t v) {
    if (a == 1) { m->port01 = v; return; }
    if (a >= 0xd000 && a < 0xe000 && (m->port01 & 3) && (m->port01 & 4)) { io_write(m, a, v); return; }
    m->ram[a] = v;
}

/* ---------------- the 6510 ---------------- */
#define SETNZ(v) (m->p = (uint8_t)((m->p & ~(FN | FZ)) | ((v) & 0x80) | ((v) ? 0 : FZ)))
static void push(M *m, uint8_t v) { m->ram[0x100 + m->sp--] = v; }
static uint8_t pull(M *m) { return m->ram[0x100 + ++m->sp]; }
static uint16_t rd16(M *m, uint16_t a) { return rd(m, a) | (rd(m, (uint16_t)(a + 1)) << 8); }

static void adc(M *m, uint8_t v) {
    if (m->p & FD) { fprintf(stderr, "decimal mode at $%04x\n", m->pc); exit(2); }
    unsigned s = m->a + v + (m->p & FC);
    m->p &= ~(FC | FV);
    if (s > 255) m->p |= FC;
    if (~(m->a ^ v) & (m->a ^ s) & 0x80) m->p |= FV;
    m->a = (uint8_t)s;
    SETNZ(m->a);
}
static void cmp(M *m, uint8_t r, uint8_t v) {
    unsigned d = r - v;
    m->p &= ~FC;
    if (r >= v) m->p |= FC;
    SETNZ((uint8_t)d);
}

static void step(M *m) {
    /* raster interrupt */
    int line = raster(m);
    if (line != m->lastline) {
        m->lastline = line;
        int cmpl = m->vic[0x12] | ((m->vic[0x11] & 0x80) << 1);
        if (line == cmpl) m->latch |= 1;
    }
    if ((m->latch & m->vic[0x1a] & 15) && !(m->p & FI)) {
        push(m, m->pc >> 8); push(m, m->pc & 0xff); push(m, (m->p & ~FB) | FU);
        m->p |= FI;
        m->pc = rd16(m, 0xfffe);
        m->cyc += 7;
        return;
    }
    uint16_t pc0 = m->pc;
    uint8_t op = rd(m, m->pc++);
    uint16_t ea = 0;
    int cyc = 0, pen = 0;
    uint8_t v;
#define IMM  ea = m->pc++
#define ZP   ea = rd(m, m->pc++)
#define ZPX  ea = (uint8_t)(rd(m, m->pc++) + m->x)
#define ZPY  ea = (uint8_t)(rd(m, m->pc++) + m->y)
#define ABS  do { ea = rd16(m, m->pc); m->pc += 2; } while (0)
#define ABX  do { uint16_t b = rd16(m, m->pc); m->pc += 2; ea = b + m->x; pen = (b ^ ea) >> 8 ? 1 : 0; } while (0)
#define ABY  do { uint16_t b = rd16(m, m->pc); m->pc += 2; ea = b + m->y; pen = (b ^ ea) >> 8 ? 1 : 0; } while (0)
#define IZX  do { uint8_t z = rd(m, m->pc++) + m->x; ea = m->ram[z] | (m->ram[(uint8_t)(z + 1)] << 8); } while (0)
#define IZY  do { uint8_t z = rd(m, m->pc++); uint16_t b = m->ram[z] | (m->ram[(uint8_t)(z + 1)] << 8); ea = b + m->y; pen = (b ^ ea) >> 8 ? 1 : 0; } while (0)
#define BR(c) do { int8_t o = (int8_t)rd(m, m->pc++); cyc = 2; if (c) { uint16_t t = m->pc + o; cyc += 1 + (((t ^ m->pc) >> 8) ? 1 : 0); m->pc = t; } } while (0)
#define LD(r, mode, c) do { mode; r = rd(m, ea); SETNZ(r); cyc = c + pen; } while (0)
#define ST(r, mode, c) do { mode; wr(m, ea, r); cyc = c; } while (0)
#define ALU(fn, mode, c) do { mode; v = rd(m, ea); fn; cyc = c + pen; } while (0)
#define RMW(fn, mode, c) do { mode; v = rd(m, ea); fn; wr(m, ea, v); cyc = c; } while (0)
#define ORA  { m->a |= v; SETNZ(m->a); }
#define AND  { m->a &= v; SETNZ(m->a); }
#define EOR  { m->a ^= v; SETNZ(m->a); }
#define ADC  adc(m, v)
#define SBC  adc(m, (uint8_t)~v)
#define CMP  cmp(m, m->a, v)
#define CPX  cmp(m, m->x, v)
#define CPY  cmp(m, m->y, v)
#define BIT  m->p = (m->p & ~(FN | FV | FZ)) | (v & 0xc0) | ((m->a & v) ? 0 : FZ)
#define ASL  { m->p = (uint8_t)((m->p & ~FC) | (v >> 7)); v <<= 1; SETNZ(v); }
#define LSR  { m->p = (uint8_t)((m->p & ~FC) | (v & 1)); v >>= 1; SETNZ(v); }
#define ROL  do { uint8_t c0 = m->p & FC; m->p = (m->p & ~FC) | (v >> 7); v = (uint8_t)((v << 1) | c0); SETNZ(v); } while (0)
#define ROR  do { uint8_t c0 = m->p & FC; m->p = (m->p & ~FC) | (v & 1); v = (uint8_t)((v >> 1) | (c0 << 7)); SETNZ(v); } while (0)
#define INC  { v++; SETNZ(v); }
#define DEC  { v--; SETNZ(v); }
#define GRP(base, fn) \
    case base + 0x01: ALU(fn, IZX, 6); break; case base + 0x05: ALU(fn, ZP, 3); break; \
    case base + 0x09: ALU(fn, IMM, 2); break; case base + 0x0d: ALU(fn, ABS, 4); break; \
    case base + 0x11: ALU(fn, IZY, 5); break; case base + 0x15: ALU(fn, ZPX, 4); break; \
    case base + 0x19: ALU(fn, ABY, 4); break; case base + 0x1d: ALU(fn, ABX, 4); break;
#define SHF(base, fn) \
    case base + 0x06: RMW(fn, ZP, 5); break; case base + 0x0e: RMW(fn, ABS, 6); break; \
    case base + 0x16: RMW(fn, ZPX, 6); break; case base + 0x1e: RMW(fn, ABX, 7); break; \
    case base + 0x0a: v = m->a; fn; m->a = v; cyc = 2; break;
    switch (op) {
    GRP(0x00, ORA) GRP(0x20, AND) GRP(0x40, EOR) GRP(0x60, ADC) GRP(0xc0, CMP) GRP(0xe0, SBC)
    SHF(0x00, ASL) SHF(0x20, ROL) SHF(0x40, LSR) SHF(0x60, ROR)
    case 0x81: ST(m->a, IZX, 6); break; case 0x85: ST(m->a, ZP, 3); break;
    case 0x8d: ST(m->a, ABS, 4); break; case 0x91: ST(m->a, IZY, 6); break;
    case 0x95: ST(m->a, ZPX, 4); break; case 0x99: ST(m->a, ABY, 5); break;
    case 0x9d: ST(m->a, ABX, 5); break;
    case 0x86: ST(m->x, ZP, 3); break; case 0x8e: ST(m->x, ABS, 4); break; case 0x96: ST(m->x, ZPY, 4); break;
    case 0x84: ST(m->y, ZP, 3); break; case 0x8c: ST(m->y, ABS, 4); break; case 0x94: ST(m->y, ZPX, 4); break;
    case 0xa1: LD(m->a, IZX, 6); break; case 0xa5: LD(m->a, ZP, 3); break; case 0xa9: LD(m->a, IMM, 2); break;
    case 0xad: LD(m->a, ABS, 4); break; case 0xb1: LD(m->a, IZY, 5); break; case 0xb5: LD(m->a, ZPX, 4); break;
    case 0xb9: LD(m->a, ABY, 4); break; case 0xbd: LD(m->a, ABX, 4); break;
    case 0xa2: LD(m->x, IMM, 2); break; case 0xa6: LD(m->x, ZP, 3); break; case 0xae: LD(m->x, ABS, 4); break;
    case 0xb6: LD(m->x, ZPY, 4); break; case 0xbe: LD(m->x, ABY, 4); break;
    case 0xa0: LD(m->y, IMM, 2); break; case 0xa4: LD(m->y, ZP, 3); break; case 0xac: LD(m->y, ABS, 4); break;
    case 0xb4: LD(m->y, ZPX, 4); break; case 0xbc: LD(m->y, ABX, 4); break;
    case 0xe0: ALU(CPX, IMM, 2); break; case 0xe4: ALU(CPX, ZP, 3); break; case 0xec: ALU(CPX, ABS, 4); break;
    case 0xc0: ALU(CPY, IMM, 2); break; case 0xc4: ALU(CPY, ZP, 3); break; case 0xcc: ALU(CPY, ABS, 4); break;
    case 0x24: ALU(BIT, ZP, 3); break; case 0x2c: ALU(BIT, ABS, 4); break;
    case 0xe6: RMW(INC, ZP, 5); break; case 0xee: RMW(INC, ABS, 6); break;
    case 0xf6: RMW(INC, ZPX, 6); break; case 0xfe: RMW(INC, ABX, 7); break;
    case 0xc6: RMW(DEC, ZP, 5); break; case 0xce: RMW(DEC, ABS, 6); break;
    case 0xd6: RMW(DEC, ZPX, 6); break; case 0xde: RMW(DEC, ABX, 7); break;
    case 0xe8: m->x++; SETNZ(m->x); cyc = 2; break;
    case 0xca: m->x--; SETNZ(m->x); cyc = 2; break;
    case 0xc8: m->y++; SETNZ(m->y); cyc = 2; break;
    case 0x88: m->y--; SETNZ(m->y); cyc = 2; break;
    case 0xaa: m->x = m->a; SETNZ(m->x); cyc = 2; break;
    case 0x8a: m->a = m->x; SETNZ(m->a); cyc = 2; break;
    case 0xa8: m->y = m->a; SETNZ(m->y); cyc = 2; break;
    case 0x98: m->a = m->y; SETNZ(m->a); cyc = 2; break;
    case 0xba: m->x = m->sp; SETNZ(m->x); cyc = 2; break;
    case 0x9a: m->sp = m->x; cyc = 2; break;
    case 0x48: push(m, m->a); cyc = 3; break;
    case 0x68: m->a = pull(m); SETNZ(m->a); cyc = 4; break;
    case 0x08: push(m, m->p | FB | FU); cyc = 3; break;
    case 0x28: m->p = (pull(m) & ~FB) | FU; cyc = 4; break;
    case 0x18: m->p &= ~FC; cyc = 2; break; case 0x38: m->p |= FC; cyc = 2; break;
    case 0x58: m->p &= ~FI; cyc = 2; break; case 0x78: m->p |= FI; cyc = 2; break;
    case 0xd8: m->p &= ~FD; cyc = 2; break; case 0xf8: m->p |= FD; cyc = 2; break;
    case 0xb8: m->p &= ~FV; cyc = 2; break;
    case 0xea: cyc = 2; break;
    case 0x10: BR(!(m->p & FN)); break; case 0x30: BR(m->p & FN); break;
    case 0x50: BR(!(m->p & FV)); break; case 0x70: BR(m->p & FV); break;
    case 0x90: BR(!(m->p & FC)); break; case 0xb0: BR(m->p & FC); break;
    case 0xd0: BR(!(m->p & FZ)); break; case 0xf0: BR(m->p & FZ); break;
    case 0x4c: ABS; if (ea == pc0) m->halted = 1; m->pc = ea; cyc = 3; break;
    case 0x6c: { uint16_t b = rd16(m, m->pc); ea = rd(m, b) | (rd(m, (uint16_t)((b & 0xff00) | ((b + 1) & 0xff))) << 8); m->pc = ea; cyc = 5; break; }
    case 0x20: ABS; m->pc--; push(m, m->pc >> 8); push(m, m->pc & 0xff); m->pc = ea; cyc = 6; break;
    case 0x60: m->pc = pull(m); m->pc |= pull(m) << 8; m->pc++; cyc = 6; break;
    case 0x40: m->p = (pull(m) & ~FB) | FU; m->pc = pull(m); m->pc |= pull(m) << 8; cyc = 6; break;
    case 0x00:
        fprintf(stderr, "machine %d: BRK at $%04x\n", (int)(m - mach), pc0);
        exit(3);
    default:
        fprintf(stderr, "machine %d: illegal opcode $%02x at $%04x\n", (int)(m - mach), op, pc0);
        exit(3);
    }
    m->cyc += cyc;
}

/* ---------------- set-up and run ---------------- */
static void load(M *m, const char *fn) {
    FILE *f = fopen(fn, "rb");
    if (!f) { perror(fn); exit(1); }
    int lo = fgetc(f), hi = fgetc(f);
    uint16_t a = (uint16_t)(lo | (hi << 8));
    size_t n = fread(m->ram + a, 1, 65536 - a, f);
    fclose(f);
    memset(m->vic, 0, sizeof m->vic);
    m->port01 = 0x37;
    m->pc = 2061;                                   /* SYS 2061 */
    m->sp = 0xfd;
    m->p = FI | FU;
    m->lastline = -1;
    m->c2.ddra = 0x3f;
    m->c2.pra = 0x17;
    m->c1.tal = m->c1.ta = m->c1.tbl = m->c1.tb = 0xffff;
    m->ram[0xfffe] = m->ram[0xffff] = 0;
    (void)n;
}
static void dump(M *m, const char *out, int n) {
    char fn[1024];
    snprintf(fn, sizeof fn, "%s.%d.bin", out, n);
    FILE *f = fopen(fn, "wb");
    fwrite(m->ram, 1, 65536, f);
    fwrite(m->colram, 1, 1024, f);
    fwrite(m->vic, 1, 64, f);
    fputc(m->c2.pra, f);
    fclose(f);
}

int main(int argc, char **argv) {
    if (argc != 5 && argc != 6) {
        fprintf(stderr, "usage: packsim CHARGEN LEADER.prg [CORE.prg] OUT MAXCYCLES\n");
        return 1;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f || fread(chargen, 1, 4096, f) != 4096) { fprintf(stderr, "chargen?\n"); return 1; }
    fclose(f);
    nm = argc == 6 ? 2 : 1;
    parse_keys();
    load(&mach[0], argv[2]);
    if (nm == 2) load(&mach[1], argv[3]);
    const char *out = argv[argc - 2];
    uint64_t maxc = strtoull(argv[argc - 1], 0, 10);
    /* the core is switched on a little earlier, as in real life */
    if (nm == 2) mach[0].cyc = 2000000;
    while (!mach[0].halted && mach[0].cyc < maxc) {
        M *m = (nm == 2 && mach[1].cyc < mach[0].cyc) ? &mach[1] : &mach[0];
        step(m);
    }
    for (int i = 0; i < nm; i++) dump(&mach[i], out, i);
    printf("leader %s at %llu cycles; contention %llu; PC2 pulses leader %llu core %llu\n",
           mach[0].halted ? "halted" : "stopped (cycle limit)", (unsigned long long)mach[0].cyc,
           (unsigned long long)contention, (unsigned long long)mach[0].pulses,
           (unsigned long long)(nm == 2 ? mach[1].pulses : 0));
    return mach[0].halted ? 0 : 4;
}
