; =============================================================================================
;  Tidal Array 6400 -- the benchmark job: one Mandelbrot tile.
;  This block ($2C00-$3FFF, entry points at $3000) is the same on every core. The leader runs it from its own memory and
;  uploads it to each worker core over the link, so a core needs nothing but the small kernel.
;
;  The picture is 160x160 multicolour pixels (character rows 0-19 of the bitmap), cut into 200 tiles of
;  16x8 pixels (4 character cells side by side): 10 across, 20 down. A tile is 32 bitmap bytes in a row.
;  Each core colours its tiles with its own palette, so you can see which core did what.
;
;  View: x -2.9 .. 1.7, y -1.15 .. 1.15 (the whole set), up to MAXIT iterations a point.
;  Fixed point 8.8 (1.0 = 256). While a point is still in play |z| < 2, so every value's high byte is
;  0 or 1: a square is a table look-up plus a small correction, and the product needs one 8x8 multiply
;  (quarter squares, f(a+b) - f(a-b), f(x) = x*x/4, from page-aligned tables). About 200 cycles an
;  iteration.
;  Designed and Created by Project Moon Pi.
; =============================================================================================

!cpu 6510
!to "build/job.bin", plain

!ifndef MAXIT { MAXIT = 32 }    ; iterations before a point counts as inside the set
X0      = -742                  ; -2.9 * 256
XW      = 1178                  ;  4.6 * 256 (the picture's width)
Y0      = -294                  ; -1.15 * 256
YH      = 589                   ;  2.3 * 256 (the picture's height)

BITMAP  = $6000
SCREEN  = $5c00
COLRAM  = $d800

; zero page $02-$3f belongs to the job
zxl = $02
zxh = $03
zyl = $04
zyh = $05
cxl = $06
cxh = $07
cyl = $08
cyh = $09
axl = $0a
axh = $0b
ayl = $0c
ayh = $0d
x2l = $0e
x2h = $0f
y2l = $10
y2h = $11
pl  = $12
ph  = $13
it  = $14
sgn = $15
p1  = $16                       ; quarter-square pointers (lo bytes change, hi bytes fixed)
p2  = $18
p3  = $1a
p4  = $1c
out = $29                       ; 16-bit: bitmap byte of this cell row
line = $2b
cell = $2c
bits = $2d
pcnt = $2e
px  = $2f                       ; pixel column 0-159
py  = $30                       ; pixel row 0-159
px0 = $31                       ; the tile's first column
tbl = $32                       ; 16-bit: the tile's first bitmap byte
tix = $34
ttx = $35
tty = $36
titmp = $37                     ; tileinfo only: the leader calls it in the middle of its own tile

SQH  = $3500                    ; l*l / 256
DBLL = $3600                    ; (2l + 256) low byte
DBLH = $3700                    ; (2l + 256) high byte
SQ1L = $3800
SQ1H = $3a00
SQ2L = $3c00
SQ2H = $3e00

; ---- pixel coordinates (page-aligned, below the entry points) ------------------------------------
        * = $2c00
cxl_t   !for x, 0, 159 { !byte <(X0 + (x * XW) DIV 160) }
        * = $2d00
cxh_t   !for x, 0, 159 { !byte >((X0 + (x * XW) DIV 160) & $ffff) }
        * = $2e00
cyl_t   !for y, 0, 159 { !byte <(Y0 + (y * YH) DIV 160) }
        * = $2f00
cyh_t   !for y, 0, 159 { !byte >((Y0 + (y * YH) DIV 160) & $ffff) }

        * = $3000
; ---- entry points: the same addresses on every core ------------------------------------------
        jmp init                        ; $3000  clear the picture
        jmp tile                        ; $3003  A = tile 0-199: compute it into this core's bitmap
        jmp tileinfo                    ; $3006  A = tile: ta_bm, ta_off for it
hook    jmp (hookvec)                   ; $3009  called after every bitmap byte (the leader polls here)
hookvec !word noop                      ; $300c
coreid  !byte 0                         ; $300e  this core's number (palette)
ta_bm   !word 0                         ; $300f  tileinfo: first bitmap byte
ta_off  !word 0                         ; $3011  tileinfo: offset of the first cell (screen / colour RAM)
palscr  !byte $6e, $28, $5d, $4a, $98, $bc, $64, $53   ; $3013  per core: colours for pixel values 1 and 2
palcol  !byte $03, $07, $01, $0f, $0f, $0f, $0a, $01   ; $301b  per core: colour for pixel value 3
noop    rts                             ; $3023

; ---- clear bitmap rows 0-19 and their colours ------------------------------------------------
init    lda #<BITMAP
        sta out
        lda #>BITMAP
        sta out+1
        ldx #25                         ; 25 pages ($6000-$78ff) covers rows 0-19 ($6000-$78ff)
        lda #0
        tay
-       sta (out),y
        iny
        bne -
        inc out+1
        dex
        bne -
        ldx #0
-       sta SCREEN,x
        sta SCREEN+$100,x
        sta SCREEN+$200,x
        sta COLRAM,x
        sta COLRAM+$100,x
        sta COLRAM+$200,x
        inx
        bne -
        ldx #$1f
-       sta SCREEN+$300,x
        sta COLRAM+$300,x
        dex
        bpl -
        rts

; ---- tileinfo: A = tile -> ttx, tty, ta_bm = bitmap address, ta_off = cell offset --------------
tileinfo
        ldx #0
-       cmp #10
        bcc +
        sbc #10
        inx
        bne -
+       sta ttx
        stx tty
        asl                             ; tx * 4 (cells)
        asl
        clc
        adc rowoff_l,x
        sta ta_off
        lda rowoff_h,x
        adc #0
        sta ta_off+1
        lda ttx                         ; tx * 32 (bitmap bytes)
        lsr
        lsr
        lsr
        sta titmp
        lda ttx
        asl
        asl
        asl
        asl
        asl
        clc
        adc bmrow_l,x
        sta ta_bm
        lda bmrow_h,x
        adc titmp
        sta ta_bm+1
        rts

; ---- tile: A = tile 0-199 ---------------------------------------------------------------------
tile    sta tix
        jsr tileinfo
        lda ta_bm
        sta tbl
        lda ta_bm+1
        sta tbl+1
        lda #>SQ1L                      ; pointer high bytes
        sta p1+1
        lda #>SQ1H
        sta p2+1
        lda #>SQ2L
        sta p3+1
        lda #>SQ2H
        sta p4+1
        ldx coreid                      ; this core's colours on the tile's 4 cells
        lda ta_off
        clc
        adc #<SCREEN
        sta out
        lda ta_off+1
        adc #>SCREEN
        sta out+1
        lda palscr,x
        ldy #3
-       sta (out),y
        dey
        bpl -
        lda ta_off
        clc
        adc #<COLRAM
        sta out
        lda ta_off+1
        adc #>COLRAM
        sta out+1
        lda palcol,x
        ldy #3
-       sta (out),y
        dey
        bpl -
        lda tty                         ; first row: ty * 8
        asl
        asl
        asl
        sta py
        lda ttx                         ; first column: tx * 16
        asl
        asl
        asl
        asl
        sta px0
        lda #0
        sta line
.line   ldx py
        lda cyl_t,x
        sta cyl
        lda cyh_t,x
        sta cyh
        lda px0
        sta px
        lda tbl                         ; out = tile start + line (cells are 8 bytes apart)
        clc
        adc line
        sta out
        lda tbl+1
        adc #0
        sta out+1
        lda #0
        sta cell
.cell   lda #4
        sta pcnt
        lda #0
        sta bits
.pix    ldx px
        lda cxl_t,x
        sta cxl
        lda cxh_t,x
        sta cxh
        jsr mandel
        asl bits
        asl bits
        ora bits
        sta bits
        inc px
        dec pcnt
        bne .pix
        ldy #0
        lda bits
        sta (out),y
        jsr hook
        lda out                         ; next cell: 8 bytes on
        clc
        adc #8
        sta out
        bcc +
        inc out+1
+       inc cell
        lda cell
        cmp #4
        bne .cell
        inc py
        inc line
        lda line
        cmp #8
        bne .line
        rts

; ---- one point: c = (cx, cy) -> A = pixel value 0-3 (0 = inside the set) ----------------------
!macro seta {                           ; A = the multiplicand for the next multiply
        sta p1
        sta p2
        eor #$ff
        sta p3
        sta p4
}
!macro square .al, .ah, .rl, .rh {      ; (.ah:.al)^2 / 256 -> .rh:.rl   (.ah is 0 or 1)
        ldx .al
        lda .ah
        bne .big
        lda SQH,x                       ; l*l/256
        sta .rl
        lda #0
        sta .rh
        beq .done
.big    lda SQH,x                       ; (256 + l)^2 / 256 = l*l/256 + 2l + 256
        clc
        adc DBLL,x
        sta .rl
        lda DBLH,x
        adc #0
        sta .rh
.done
}

mandel  lda cxl                         ; z = c, first iteration done
        sta zxl
        lda cxh
        sta zxh
        lda cyl
        sta zyl
        lda cyh
        sta zyh
        lda #1
        sta it
.iter   lda zxh                         ; ax = |zx|
        bpl +
        lda #0
        sec
        sbc zxl
        sta axl
        lda #0
        sbc zxh
        sta axh
        jmp ++
+       sta axh
        lda zxl
        sta axl
++      lda axh
        cmp #2                          ; |zx| >= 2: out
        bcc +
        jmp .esc
+       lda zyh                         ; ay = |zy|
        bpl +
        lda #0
        sec
        sbc zyl
        sta ayl
        lda #0
        sbc zyh
        sta ayh
        jmp ++
+       sta ayh
        lda zyl
        sta ayl
++      lda ayh
        cmp #2
        bcc +
        jmp .esc
+
        +square axl, axh, x2l, x2h
        +square ayl, ayh, y2l, y2h

        lda x2l                         ; |z|^2 >= 4: out
        clc
        adc y2l
        lda x2h
        adc y2h
        cmp #4
        bcc +
        jmp .esc
+
        ; p = ax*ay / 256 = (axl*ayl)/256 + axh*ayl + ayh*axl + 256*axh*ayh
        lda axl
        +seta
        ldy ayl
        sec
        lda (p1),y
        sbc (p3),y
        lda (p2),y
        sbc (p4),y
        sta pl
        lda #0
        sta ph
        lda axh
        beq +
        lda pl
        clc
        adc ayl
        sta pl
        bcc ++
        inc ph
++      lda ayh
        beq +
        inc ph
+       lda ayh
        beq +
        lda pl
        clc
        adc axl
        sta pl
        bcc +
        inc ph
+
        ; zy = +-2p + cy  (sign of zx*zy)
        lda zxh
        eor zyh
        sta sgn
        asl pl
        rol ph
        bit sgn
        bpl +
        lda #0
        sec
        sbc pl
        sta pl
        lda #0
        sbc ph
        sta ph
+       lda pl
        clc
        adc cyl
        sta zyl
        lda ph
        adc cyh
        sta zyh
        ; zx = x2 - y2 + cx
        lda x2l
        sec
        sbc y2l
        tax
        lda x2h
        sbc y2h
        tay
        txa
        clc
        adc cxl
        sta zxl
        tya
        adc cxh
        sta zxh

        inc it
        lda it
        cmp #MAXIT
        beq .inside
        jmp .iter
.inside lda #0
        rts
.esc    ldx it
        lda modtab,x
        rts

modtab  !for i, 0, 63 { !byte 1 + (i % 3) }
rowoff_l !for r, 0, 19 { !byte <(r * 40) }
rowoff_h !for r, 0, 19 { !byte >(r * 40) }
bmrow_l !for r, 0, 19 { !byte <(BITMAP + r * 320) }
bmrow_h !for r, 0, 19 { !byte >(BITMAP + r * 320) }
code_end
        !if code_end > SQH { !error "job code runs into its tables" }

; ---- tables -----------------------------------------------------------------------------------
        * = SQH
        !for x, 0, 255 { !byte (x * x) >> 8 }
        * = DBLL
        !for x, 0, 255 { !byte <(2 * x + 256) }
        * = DBLH
        !for x, 0, 255 { !byte >(2 * x + 256) }
        * = SQ1L
        !for x, 0, 511 { !byte <((x * x) >> 2) }
        * = SQ1H
        !for x, 0, 511 { !byte >((x * x) >> 2) }
        * = SQ2L
        !for x, 0, 511 { !byte <(((x - 255) * (x - 255)) >> 2) }
        * = SQ2H
        !for x, 0, 511 { !byte >(((x - 255) * (x - 255)) >> 2) }
