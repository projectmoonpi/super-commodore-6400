; =============================================================================================
;  Tidal Array 6400 -- shared by the leader and the cores: machine set-up, the screen split
;  (multicolour bitmap rows 0-19, text rows 20-24), text printing, and the user-port link.
;  Designed and Created by Project Moon Pi.
;
;  THE LINK (two C64s, user port to user port):
;    PB0-PB7 (pins C,D,E,F,H,J,K,L) straight through, data both ways, one side drives at a time.
;    PC2 (pin 8) of each machine -> FLAG (pin B) of the other: every read or write of port B pulses
;    PC2, so writing a byte says "here is a byte" and reading it says "got it".
;    GND (pins 1, 12, A, N) together. Nothing else is connected.
;  The leader drives the data lines except while a core is answering a READ. Hand-overs are signalled
;  with a "line free" pulse, so the two sides never drive at the same time.
;  Commands from the leader (a core only ever answers, or pulses once when a CALL finishes):
;    $01 WRITE  addr(2) len(2) data...     store into the core's memory
;    $02 READ   addr(2) len(2)             the core sends len bytes back
;    $03 CALL   addr(2) A                  the core runs JSR addr with A, then pulses "done"
; =============================================================================================

; (the constants and zero page are in src/defs.asm, included first)

; ---- print: jsr print / !word screen address / !scr "text", 0 ---------------------------------
print   pla
        sta sptr
        pla
        sta sptr+1
        ldy #1
        lda (sptr),y
        sta .pd+1
        iny
        lda (sptr),y
        sta .pd+2
        ldx #0
-       iny
        lda (sptr),y
        beq +
.pd     sta $ffff,x
        inx
        bne -
+       tya                             ; return past the zero
        clc
        adc sptr
        sta sptr
        bcc +
        inc sptr+1
+       lda sptr+1
        pha
        lda sptr
        pha
        rts

; ---- machine set-up: RAM + I/O, our own interrupts, VIC bank 1, the split screen ---------------
setup   sei
        cld
        lda #$7f                        ; no CIA interrupts (the link is polled, never an NMI)
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$33                        ; character ROM in: copy the first 2 KB (upper case + graphics)
        sta $01
        ldx #0
-       !for p, 0, 7 {
        lda $d000 + p * $100,x
        sta CHARS + p * $100,x
        }
        inx
        bne -
        lda #$35                        ; RAM everywhere, I/O at $d000, no BASIC or KERNAL
        sta $01
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda $dd02                       ; VIC bank 1 ($4000-$7fff)
        ora #3
        sta $dd02
        lda $dd00
        and #$fc
        ora #2
        sta $dd00
        lda #0
        sta $d020
        sta $d021
        sta $d015
        ldx #0                          ; text screen: spaces, white
-       lda #$20
        sta TXT,x
        sta TXT+$100,x
        sta TXT+$200,x
        sta TXT+$2e8,x
        lda #1
        sta COLRAM+$300,x               ; (the text rows' colour RAM: $db20-$dbe7)
        inx
        bne -
        jsr clrpic
        lda #0
        sta irqst
        lda #$3b                        ; bitmap on, raster compare high bit clear
        sta $d011
        lda #$18
        sta $d016
        lda #$78                        ; screen $5c00, bitmap $6000
        sta $d018
        lda #SPLIT - 1
        sta $d012
        lda #1
        sta $d01a
        lda #$ff
        sta $d019
        cli
        rts

; ---- clear the picture: bitmap rows 0-19 and their colours ------------------------------------
clrpic  lda #<BITMAP
        sta lptr
        lda #>BITMAP
        sta lptr+1
        ldx #25
        lda #0
        tay
-       sta (lptr),y
        iny
        bne -
        inc lptr+1
        dex
        bne -
-       sta SCREEN,y
        sta SCREEN+$100,y
        sta SCREEN+$200,y
        sta COLRAM,y
        sta COLRAM+$100,y
        sta COLRAM+$200,y
        iny
        bne -
        ldy #$1f
-       sta SCREEN+$300,y
        sta COLRAM+$300,y
        dey
        bpl -
        rts

; ---- the split: bitmap above, text below ------------------------------------------------------
irq     pha
        txa
        pha
        lda #$ff
        sta $d019
        lda irqst
        bne .bot
        lda #SPLIT                      ; wait for the last bitmap line, then for its right border
-       cmp $d012
        bne -
        ldx #8
-       dex
        bne -
        lda #$1b                        ; text mode, hires
        sta $d011
        lda #$08
        sta $d016
        lda #$62                        ; screen $5800, characters $4800
        sta $d018
        lda #252                        ; below the last text line (250)
        sta $d012
        inc irqst
        bne .out
.bot    lda #$3b                        ; bitmap, multicolour
        sta $d011
        lda #$18
        sta $d016
        lda #$78
        sta $d018
        lda #SPLIT - 1
        sta $d012
        lda #0
        sta irqst
.out    pla
        tax
        pla
nmi     rti

; ---- the link, core side (the leader's side is in leader.asm) -----------------------------------
c_recv  lda $dd0d                       ; wait for "here is a byte"
        and #$10
        beq c_recv
        lda $dd01                       ; read it: that pulses "got it"
        rts

; the kernel: wait for commands for ever
kernel  lda #0
        sta $dd03                       ; listen
        lda $dd0d
.kl     jsr c_recv
        cmp #1
        beq k_write
        cmp #2
        beq k_read
        cmp #3
        bne .kl
k_call  jsr c_recv
        sta jvec
        jsr c_recv
        sta jvec+1
        jsr c_recv
        sta jarg
        jsr .jump
        lda $dd01                       ; "done"
        jmp .kl
.jump   lda jarg
        jmp (jvec)

k_hdr   jsr c_recv                      ; address and length -> lptr, llen
        sta lptr
        jsr c_recv
        sta lptr+1
        jsr c_recv
        sta llen
        jsr c_recv
        sta llen+1
        rts

k_write jsr k_hdr
        ldy #0
-       lda $dd0d
        and #$10
        beq -
        lda $dd01
        sta (lptr),y
        iny
        bne +
        inc lptr+1
+       lda llen
        bne +
        dec llen+1
+       dec llen
        lda llen
        ora llen+1
        bne -
        jmp .kl

k_read  jsr k_hdr
-       lda $dd0d                       ; wait for "line free"
        and #$10
        beq -
        lda #$ff
        sta $dd03                       ; talk
        ldy #0
.kr     lda (lptr),y
        sta $dd01                       ; "here is a byte"
-       lda $dd0d                       ; wait for "got it"
        and #$10
        beq -
        iny
        bne +
        inc lptr+1
+       lda llen
        bne +
        dec llen+1
+       dec llen
        lda llen
        ora llen+1
        bne .kr
        lda #0
        sta $dd03                       ; listen again
        lda $dd01                       ; "line free"
        jmp .kl
