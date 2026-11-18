; =============================================================================================
;  Super Commodore 6400 -- CORE: load this on every worker C64. It sets the screen up, says it is
;  waiting, and then only obeys the leader over the link (src/common.asm). The leader uploads the job,
;  tells the core its number, and hands it work.
;  LOAD"PACK CORE",8 then RUN.
;  Designed and Created by Project Moon Pi.
; =============================================================================================

!cpu 6510
!source "src/defs.asm"
!to "build/core.prg", cbm

SIG     = $0f00                         ; "PACK" + version: the leader reads this to find a core

        * = $0801
        !word +, 6400
        !byte $9e
        !text "2061"
        !byte 0
+       !word 0

start   jsr setup
        jsr print
        !word TROW
        !scr "super commodore 6400", 0
        jsr print
        !word TROW + 40
        !scr "core: waiting for the leader", 0
        jsr print
        !word TROW + 4 * 40
        !scr "designed and created by project moon pi", 0
        jmp kernel

!source "src/common.asm"

        !if * > SIG { !error "core code runs past the signature" }
        * = SIG
        !text "PACK", 1
