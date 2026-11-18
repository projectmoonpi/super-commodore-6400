; =============================================================================================
;  Tidal Array 6400 -- cartridge boot (Magic Desk type: 8 KB banks at $8000, bank select at
;  $de00, bit 7 switches the cartridge off).
;  Bank 0 is this code. Banks 1..NB hold the program (leader.prg or core.prg without its
;  load address). At power-on the boot code sets the machine up as the KERNAL would, copies a small
;  copier to the cassette buffer and runs it: the copier pages the banks in one by one, copies them
;  to $0801, switches the cartridge off and starts the program as RUN would (SYS 2061).
;  The reset button switches the cartridge back on, so it starts the program again.
;  Built by tools/make_crt.py.  Designed and Created by Project Moon Pi.
; =============================================================================================

!cpu 6510
!to "build/cart0.bin", plain
!ifndef NB { NB = 3 }

src     = $fb
dst     = $fd
bank    = $02
TR      = $0340

        * = $8000
        !word cold                      ; cold start
        !word cold                      ; warm start (RESTORE)
        !byte $c3, $c2, $cd, $38, $30   ; "CBM80"

cold    sei
        ldx #$ff
        txs
        cld
        stx $d016
        jsr $fda3                       ; IOINIT: CIAs, SID, $00/$01
        jsr $fd50                       ; RAMTAS: clear pages 0, 2, 3; find the top of RAM
        jsr $fd15                       ; RESTOR: KERNAL vectors
        jsr $ff5b                       ; CINT: screen editor, VIC
        lda #0                          ; black, screen off while it copies
        sta $d020
        sta $d021
        lda #$0b
        sta $d011
        ldx #tr_end - tr_src - 1
-       lda tr_src,x
        sta TR,x
        dex
        bpl -
        jmp TR

tr_src
!pseudopc TR {
        lda #<$0801
        sta dst
        lda #>$0801
        sta dst+1
        lda #1
        sta bank
.bank   lda bank
        sta $de00
        lda #0
        sta src
        lda #$80
        sta src+1
        ldx #32                         ; 32 pages = 8 KB
.page   ldy #0
-       lda (src),y
        sta (dst),y
        iny
        bne -
        inc src+1
        inc dst+1
        dex
        bne .page
        inc bank
        lda bank
        cmp #NB + 1
        bne .bank
        lda #$80                        ; cartridge off: the RAM at $8000 shows again
        sta $de00
        jmp 2061                        ; as RUN would: the program's SYS 2061
}
tr_end
        !if tr_end - tr_src > 128 { !error "copier too big" }
        !if * > $a000 { !error "boot code over 8 KB" }
