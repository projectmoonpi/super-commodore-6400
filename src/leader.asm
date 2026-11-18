; =============================================================================================
;  Super Commodore 6400 -- LEADER: load this on the C64 with the monitor you watch.
;  It finds the worker core on the user-port link, uploads the job, then runs the benchmark with as
;  many cores as you choose: a Mandelbrot picture cut into 200 tiles, handed out one at a time to
;  whichever core is free (the leader computes tiles too, it is core 0). Each core paints its tiles in
;  its own colours. The time for each run and the speed-up over one core are shown below the picture.
;  Keys: 1-n = run with that many cores, S = scan the link again.
;  LOAD"PACK LEADER",8 then RUN.
;  Designed and Created by Project Moon Pi.
; =============================================================================================

!cpu 6510
!source "src/defs.asm"
!to "build/leader.prg", cbm
!ifndef AUTO { AUTO = 0 }               ; 1: run 1 core, then all cores, then stop (for the simulator)

SIG     = $0f00                         ; where a core keeps "PACK" + version
NTILES  = 200
TENTH   = 102273                        ; NTSC cycles in 0.1 s (1022727 Hz)

; zero page $60-$8f: the leader
ncores  = $60
nrun    = $61
next    = $62
done    = $63
wtile   = $64
wbusy   = $65
dptr    = $66                           ; 16-bit: local end of a READ / source of a WRITE
k       = $68
tmp     = $69
dv      = $6a                           ; 4 bytes: dividend -> quotient
ds      = $6e                           ; 4 bytes: divisor
dr      = $72                           ; 4 bytes: remainder
nb      = $76                           ; 6 bytes: number text
cyc     = $7c                           ; 4 bytes: cycles of the last run

        * = $0801
        !word +, 6400
        !byte $9e
        !text "2061"
        !byte 0
+       !word 0

start   jsr setup
        lda #0
        sta JOB_CORE                    ; the leader is core 0
        ldx #47
-       sta rten,x                      ; no results yet (rten and rcyc)
        dex
        bpl -
        jsr print
        !word TROW + 4 * 40
        !scr "designed and created by project moon pi", 0
        jsr scan
!if AUTO {
        lda #1
        jsr run
        lda ncores
        jsr run
halt    jmp halt
} else {
menu    jsr title
.key    jsr getkey
        cmp #'s'
        bne +
        jsr scan
        jmp menu
+       cmp ncores                      ; 1 .. ncores
        beq +
        bcs .key
+       jsr run
        jmp menu
}

; ---- title line: "SUPER COMMODORE 6400 CORES n KEYS 1-n,S" -----------------------------------
title   jsr print
        !word TROW
        !scr "super commodore 6400 cores 0 keys 1-0,s", 0
        lda ncores
        ora #$30
        sta TROW + 27
        sta TROW + 36
        rts

; ---- scan: is there a core on the link? If so, give it the job, its number and a status line ----
scan    lda #1
        sta ncores
        jsr print
        !word TROW
        !scr "super commodore 6400 scanning the link ", 0
        jsr l_init
        lda #2
        jsr l_sendt                     ; READ, with a time-out: is anyone there?
        bcc +
        jmp .none
+
        lda #<SIG
        sta lptr
        lda #>SIG
        sta lptr+1
        lda #5
        sta llen
        lda #0
        sta llen+1
        lda #<sigbuf
        sta dptr
        lda #>sigbuf
        sta dptr+1
        jsr l_read2
        ldx #3
-       lda sigbuf,x
        cmp sigtxt,x
        bne .nosig
        dex
        bpl -
        lda #<JOB_START                 ; the job, from the leader's own copy
        sta lptr
        sta dptr
        lda #>JOB_START
        sta lptr+1
        sta dptr+1
        lda #<JOB_LEN
        sta llen
        lda #>JOB_LEN
        sta llen+1
        jsr l_write
        lda #<JOB_CORE                  ; its number: 1
        sta lptr
        lda #>JOB_CORE
        sta lptr+1
        lda #1
        sta llen
        lda #0
        sta llen+1
        lda #<one
        sta dptr
        lda #>one
        sta dptr+1
        jsr l_write
        lda #<(TROW + 40)               ; its status line
        sta lptr
        lda #>(TROW + 40)
        sta lptr+1
        lda #40
        sta llen
        lda #0
        sta llen+1
        lda #<corestat
        sta dptr
        lda #>corestat
        sta dptr+1
        jsr l_write
        lda #2
        sta ncores
.none   rts
.nosig  jmp .none

sigbuf  !fill 5
sigtxt  !text "PACK"
one     !byte 1
corestat !scr "core 1: linked to the leader            "

; ---- run the benchmark on A cores ------------------------------------------------------------
run     sta nrun
        jsr print
        !word TROW
        !scr "super commodore 6400 running on 0 cores", 0
        lda nrun
        ora #$30
        sta TROW + 32
        jsr JOB_INIT                    ; clear the picture here ...
        lda nrun
        cmp #2
        bcc +
        lda #<JOB_INIT                  ; ... and on the worker
        sta lptr
        lda #>JOB_INIT
        sta lptr+1
        lda #0
        jsr l_call
        jsr l_wait                      ; until it says "done"
+       lda #0
        sta next
        sta done
        sta wbusy
        lda #<lpoll                     ; the job calls lpoll after every bitmap byte
        sta JOB_HOOKV
        lda #>lpoll
        sta JOB_HOOKV+1
        jsr tstart
        lda nrun
        cmp #2
        bcc .loop
        jsr assign                      ; the worker's first tile
.loop   lda next                        ; the leader takes the next free tile itself
        cmp #NTILES
        bcs .wait
        inc next
        jsr JOB_TILE
        inc done
        jmp .loop
.wait   jsr lpoll                       ; until every tile is back
        lda done
        cmp #NTILES
        bne .wait
        jsr tstop
        lda #<JOB_NOOP                  ; hook off again
        sta JOB_HOOKV
        lda #>JOB_NOOP
        sta JOB_HOOKV+1
        ; keep the result: cycles and tenths of a second
        lda nrun
        sec
        sbc #1
        sta k
        asl
        asl
        tax
        ldy #0
-       lda cyc,y
        sta rcyc,x
        sta dv,y
        inx
        iny
        cpy #4
        bne -
        lda #<TENTH                     ; tenths = (cycles + TENTH/2) / TENTH
        sta ds
        lda #>TENTH
        sta ds+1
        lda #^TENTH
        sta ds+2
        lda #0
        sta ds+3
        lda dv
        clc
        adc #<(TENTH / 2)
        sta dv
        lda dv+1
        adc #>(TENTH / 2)
        sta dv+1
        lda dv+2
        adc #^(TENTH / 2)
        sta dv+2
        bcc +
        inc dv+3
+       jsr div32
        lda k
        asl
        tax
        lda dv
        sta rten,x
        lda dv+1
        sta rten+1,x
        jsr results
        rts

; ---- hand the worker its next tile, or leave it idle --------------------------------------------
assign  lda next
        cmp #NTILES
        bcs .idle
        sta wtile
        inc next
        pha
        lda #<JOB_TILE
        sta lptr
        lda #>JOB_TILE
        sta lptr+1
        pla
        jsr l_call
        lda #1
        sta wbusy
        rts
.idle   lda #0
        sta wbusy
        rts

; ---- poll the link: called by the job after every bitmap byte, and while the leader waits -------
lpoll   pha
        lda $dd0d
        and #$10
        beq +
        txa
        pha
        tya
        pha
        jsr service
        pla
        tay
        pla
        tax
+       pla
        rts

; the worker finished its tile: fetch the 32 bitmap bytes, colour the cells, give it the next one
service lda wtile
        jsr JOB_INFO
        lda JOB_TABM
        sta lptr
        sta dptr
        lda JOB_TABM+1
        sta lptr+1
        sta dptr+1
        lda #32
        sta llen
        lda #0
        sta llen+1
        jsr l_read
        lda JOB_TAOFF                   ; the worker's colours on the tile's cells
        clc
        adc #<SCREEN
        sta dptr
        lda JOB_TAOFF+1
        adc #>SCREEN
        sta dptr+1
        lda JOB_PALS + 1
        ldy #3
-       sta (dptr),y
        dey
        bpl -
        lda JOB_TAOFF
        clc
        adc #<COLRAM
        sta dptr
        lda JOB_TAOFF+1
        adc #>COLRAM
        sta dptr+1
        lda JOB_PALC + 1
        ldy #3
-       sta (dptr),y
        dey
        bpl -
        inc done
        jmp assign

; ---- the link, leader side (see src/common.asm for the wiring and the commands) -----------------
l_init  lda #$ff                        ; the leader drives the data lines
        sta $dd03
        lda $dd0d
        rts

l_send  sta $dd01                       ; "here is a byte" ...
-       lda $dd0d                       ; ... wait for "got it"
        and #$10
        beq -
        rts

l_sendt sta $dd01                       ; the same, but give up after about a second: C = 1
        ldx #0
        ldy #0
-       lda $dd0d
        and #$10
        bne +
        dex
        bne -
        dey
        bne -
        sec
        rts
+       clc
        rts

l_hdr   lda lptr                        ; address and length
        jsr l_send
        lda lptr+1
        jsr l_send
        lda llen
        jsr l_send
        lda llen+1
        jmp l_send

l_call  sta tmp                         ; CALL lptr with A
        lda #3
        jsr l_send
        lda lptr
        jsr l_send
        lda lptr+1
        jsr l_send
        lda tmp
        jmp l_send

l_wait  lda $dd0d                       ; wait for a core's "done"
        and #$10
        beq l_wait
        rts

l_write lda #1                          ; WRITE llen bytes from dptr to the core's lptr
        jsr l_send
        jsr l_hdr
        ldy #0
-       lda (dptr),y
        jsr l_send
        iny
        bne +
        inc dptr+1
+       lda llen
        bne +
        dec llen+1
+       dec llen
        lda llen
        ora llen+1
        bne -
        rts

l_read  lda #2                          ; READ llen bytes from the core's lptr to dptr
        jsr l_send
l_read2 jsr l_hdr
        lda #0                          ; let go of the data lines ...
        sta $dd03
        lda $dd01                       ; ... and say "line free"
        ldy #0
.lr     lda $dd0d
        and #$10
        beq .lr
        lda $dd01
        sta (dptr),y
        iny
        bne +
        inc dptr+1
+       lda llen
        bne +
        dec llen+1
+       dec llen
        lda llen
        ora llen+1
        bne .lr
-       lda $dd0d                       ; the core lets go and says "line free"
        and #$10
        beq -
        lda #$ff
        sta $dd03
        rts

; ---- timing: CIA 1 timer A counts cycles, timer B counts timer A's underflows -------------------
tstart  lda #0
        sta $dc0e
        sta $dc0f
        lda #$ff
        sta $dc04
        sta $dc05
        sta $dc06
        sta $dc07
        lda #$51                        ; B: start, load, count A's underflows
        sta $dc0f
        lda #$11                        ; A: start, load, count cycles
        sta $dc0e
        rts

tstop   lda #0
        sta $dc0e                       ; stop A (B stops with it)
        lda $dc04                       ; cycles = not(B:A)
        eor #$ff
        sta cyc
        lda $dc05
        eor #$ff
        sta cyc+1
        lda $dc06
        eor #$ff
        sta cyc+2
        lda $dc07
        eor #$ff
        sta cyc+3
        rts

; ---- 32-bit unsigned divide: dv / ds -> dv, remainder dr -----------------------------------------
div32   lda #0
        sta dr
        sta dr+1
        sta dr+2
        sta dr+3
        ldx #32
-       asl dv
        rol dv+1
        rol dv+2
        rol dv+3
        rol dr
        rol dr+1
        rol dr+2
        rol dr+3
        lda dr
        sec
        sbc ds
        sta tmp
        lda dr+1
        sbc ds+1
        pha
        lda dr+2
        sbc ds+2
        pha
        lda dr+3
        sbc ds+3
        bcc +
        sta dr+3
        pla
        sta dr+2
        pla
        sta dr+1
        lda tmp
        sta dr
        inc dv
        jmp ++
+       pla
        pla
++      dex
        bne -
        rts

; ---- the results table: rows 21-24, two columns: "n: tttt.ts x.xxx" ----------------------------
results lda #0
        sta k
.rl     lda k
        asl
        tax
        lda rten,x
        ora rten+1,x
        bne +
        jmp .rnext
+       lda k                           ; screen position -> dptr
        and #3
        tax
        lda k
        cmp #4
        lda resrow_l,x
        bcc +
        adc #19                         ; (carry set: +20)
+       sta dptr
        lda resrow_h,x
        adc #0
        sta dptr+1
        ldy #0
        lda k
        clc
        adc #$31
        sta (dptr),y
        iny
        lda #$3a                        ; ":"
        sta (dptr),y
        lda k                           ; the time: 4 digits, a point, 1 digit, "s"
        asl
        tax
        lda rten,x
        sta dv
        lda rten+1,x
        sta dv+1
        jsr num5                        ; nb = 5 digits, leading spaces
        ldy #2
        ldx #0
-       lda nb,x
        sta (dptr),y
        iny
        inx
        cpx #4
        bne -
        lda #$2e
        sta (dptr),y
        iny
        lda nb+4
        sta (dptr),y
        iny
        lda #$13                        ; "s"
        sta (dptr),y
        lda rten                        ; the speed-up: needs the 1-core time
        ora rten+1
        beq .rnext
        lda rten                        ; (t1 * 100) / tk
        sta dv
        lda rten+1
        sta dv+1
        lda #0
        sta dv+2
        sta dv+3
        jsr mul100
        lda k
        asl
        tax
        lda rten,x
        sta ds
        lda rten+1,x
        sta ds+1
        lda #0
        sta ds+2
        sta ds+3
        jsr div32
        jsr num5                        ; "x.xx"
        ldy #11
        lda nb+2
        cmp #$20
        bne +
        lda #$30
+       sta (dptr),y
        iny
        lda #$2e
        sta (dptr),y
        iny
        lda nb+3
        cmp #$20
        bne +
        lda #$30
+       sta (dptr),y
        iny
        lda nb+4
        sta (dptr),y
        iny
        lda #$18                        ; "x"
        sta (dptr),y
.rnext  inc k
        lda k
        cmp #8
        beq +
        jmp .rl
+       rts

resrow_l !for r, 0, 3 { !byte <(TROW + (r + 1) * 40) }
resrow_h !for r, 0, 3 { !byte >(TROW + (r + 1) * 40) }

; dv (16-bit used) * 100 -> dv (32-bit)
mul100  ldx #0                          ; dv*100 = dv*64 + dv*32 + dv*4
        lda #0
        sta dv+2
        sta dv+3
        jsr .x4
        lda dv
        sta dr
        lda dv+1
        sta dr+1
        lda dv+2
        sta dr+2
        jsr .x8                         ; now dv*32
        lda dv
        clc
        adc dr
        sta dr
        lda dv+1
        adc dr+1
        sta dr+1
        lda dv+2
        adc dr+2
        sta dr+2
        asl dv                          ; dv*64
        rol dv+1
        rol dv+2
        lda dv
        clc
        adc dr
        sta dv
        lda dv+1
        adc dr+1
        sta dv+1
        lda dv+2
        adc dr+2
        sta dv+2
        rts
.x8     asl dv
        rol dv+1
        rol dv+2
.x4     asl dv
        rol dv+1
        rol dv+2
        asl dv
        rol dv+1
        rol dv+2
        rts

; dv (16-bit) -> nb: 5 screen-code digits, leading zeros as spaces (the last digit always shown)
num5    ldx #0
.nd     ldy #$30
-       lda dv
        sec
        sbc p10l,x
        sta tmp
        lda dv+1
        sbc p10h,x
        bcc +
        sta dv+1
        lda tmp
        sta dv
        iny
        bne -
+       tya
        sta nb,x
        inx
        cpx #5
        bne .nd
        ldx #0                          ; blank the leading zeros
-       lda nb,x
        cmp #$30
        bne +
        lda #$20
        sta nb,x
        inx
        cpx #4
        bne -
+       rts
p10l    !byte <10000, <1000, <100, <10, <1
p10h    !byte >10000, >1000, >100, >10, >1

; ---- keyboard: wait for 1-8 or S, then for the key to be let go; A = '1'..'8' or 's' -----------
getkey  ldx #8
-       lda keycol,x
        sta $dc00
        lda $dc01
        and keyrow,x
        beq .got
        dex
        bpl -
        bmi getkey
.got    lda keycode,x
        pha
-       lda $dc01                       ; wait for release
        and keyrow,x
        beq -
        lda #$ff
        sta $dc00
        pla
        rts
keycol  !byte $7f, $7f, $fd, $fd, $fb, $fb, $f7, $f7, $fd
keyrow  !byte $01, $08, $01, $08, $01, $08, $01, $08, $20
keycode !byte 1, 2, 3, 4, 5, 6, 7, 8, 's'

; ---- results (the simulator reads these) -----------------------------------------------------
rten    !fill 16                        ; tenths of a second for 1..8 cores
rcyc    !fill 32                        ; cycles for 1..8 cores

!source "src/common.asm"

        !if * > JOB_START { !error "leader runs into the job" }
        * = JOB_START
        !binary "build/job.bin"
