; =============================================================================================
;  Tidal Array 6400 -- addresses and zero page shared by the leader and the cores.
;  Included first, so zero-page names assemble as zero-page addresses.
; =============================================================================================

JOB_INIT  = $3000
JOB_TILE  = $3003
JOB_INFO  = $3006
JOB_HOOKV = $300c
JOB_CORE  = $300e
JOB_TABM  = $300f
JOB_TAOFF = $3011
JOB_PALS  = $3013
JOB_PALC  = $301b
JOB_NOOP  = $3023
JOB_START = $2c00
JOB_LEN   = $1400

TXT     = $5800                         ; text screen (rows 20-24 are visible)
CHARS   = $4800                         ; a RAM copy of the character ROM (bank 1 cannot see the ROM)
SCREEN  = $5c00
BITMAP  = $6000
COLRAM  = $d800
TROW    = TXT + 20 * 40                 ; first visible text row
SPLIT   = 210                           ; last bitmap raster line (row 19 ends at 50 + 160)

; zero page $40-$5f: link, kernel and printing
lptr    = $40                           ; 16-bit
llen    = $42                           ; 16-bit
lcnt    = $44                           ; 16-bit
sptr    = $46                           ; 16-bit (printing)
irqst   = $48
jvec    = $49                           ; 16-bit (kernel CALL)
jarg    = $4b

