#RetroDevStudio.MetaData.BASIC:7169,BASIC V7.0 VDC,uppercase,10,10
# THIS LOADS SINGLE WALL ELEMENT VDC FILES (CREATED BY THE BMP PROGRAM)
#  AND WRITES THEM INTO ONE SINGLE VDC FILE
#  IN ADDITION TO THAT, OFFSET, WIDTH, HEIGHT AND LENGTH ARE WRITTEN AS METADATA
#  THE RESULTING FILE CONTAINS EVERYTHING THAT'S NEEDED TO BLIT WALL ELEMENTS
#  TO THE SCREEN

1 DEF FN HB(ZZ)=DEC(LEFT$(HEX$(ZZ),2))
2 DEF FN LB(ZZ)=DEC(RIGHT$(HEX$(ZZ),2))
5 DEF FN PA(ZZ)=7*ZZ+1

10 GRAPHIC0:BANK0
20 DD=PEEK(186)
30 BE=PEEK(4624)+PEEK(4625)*256
40 BLOAD"VDCBASIC2D.0AC6",B0,U(DD):SYSDEC("AC6")
50 AP=16000

60 RGW0,127:RGW4,155:RGW6,100:RGW7,140:RGW9,1
70 RGO25,128:REM BITMAP MODE ON
80 RGO28,24:REM 64K VRAM
90 RGW36,0
100 RGW DEC("1A"),DEC("FF")

110 VMF0,15,AP:REM SETUP PIXELS
120 VMFAP,0,8000:REM CLEAR ATTRIBUTE RAM
130 DISP0:ATTRAP:DA=AP+8000:OS=0

140 DC=19:DIM DM(DC-1,4):DIM PO(DC-1)

145 FOR FI=0 TO DC-1:READ V:PO(FI)=V:NEXT

150 FOR FI=1TO DC:FI$=MID$(STR$(FI),2)+".VDC"
160  ?"LOADING "FI$"...";:BLOAD (FI$),B0,P(BE):? "DONE"

170  FL=PEEK(174)+PEEK(175)*256-BE:?"LENGTH:"FL:FL=FL-2

180  ?"RTV TO "(DA+OS)

190  RTV BE+2,DA+OS,FL

200  BW=PEEK(BE):BH=PEEK(BE+1)

210  DM(FI-1,0)=OS
220  DM(FI-1,1)=BW+1
230  DM(FI-1,2)=BH
240  DM(FI-1,3)=FL
241  DM(FI-1,4)=PO(FI-1)/2

250  PRINT DM(FI-1,0)" "DM(FI-1,1)" "DM(FI-1,2)" "DM(FI-1,3)" "DM(FI-1,4)

260  OS=OS+FL

270 NEXT:PRINT "LAST OFFSET:"OS

#   6 BYTES PER WALL-OBJECT ENTRY. PLUS 1 BYTE FOR THE NR OF ENTRIES
#   0,1: OFFSET IN VRAM (STARTING WITH 0)
#   2:   BW
#   3:   BH
#   4,5: OBJECT-LENGTH
271 D=FNPA(DC):POKE BE,DC

272 FOR FI=0TO18:PA=BE+FNPA(FI)

273  POKE PA,FNLB(DM(FI,0)):POKEPA+1,FNHB(DM(FI,0))
274  POKE PA+2,DM(FI,1)
275  POKE PA+3,DM(FI,2)
276  POKE PA+4,FNLB(DM(FI,3)):POKEPA+5,FNHB(DM(FI,3))
277  POKE PA+6,DM(FI,4)

278 NEXT

279 VTR DA,BE+D,OS

280 BSAVE"@WALLS.VDC",B0,P(BE)TOP(BE+OS+D)


281 FOR FI=0TO18:S=TI

290  BW=DM(FI,1):BH=DM(FI,2):FL=DM(FI,3):PO=DM(FI,4)

295  PRINT "VMC FROM "DM(FI,0)" TO 0,BW:"BW",BH:"BH",FL:"FL",PO:"PO

300  VMC DA+DM(FI,0),AP+PO,BW,BH,80,BW


310  DO:LOOPWHILE TI-S<25
320 NEXT:S1=TI-S1:SLOW:PRINT "19 COPIES TOOK "S" JIFFIES."
330 GETKEY I$

340 GOTO 281
350 SLOW
360 BANK15



# THIS IS THE SCREEN OFFSET DATA.
# 

# THIS DATA HAS Y-OFFSET ZERO FOR EVERY ELEMENT.
#1000 DATA 0,118,0,18,118,18,98,0,18,38,98,118,38,88,18,38,48,88,98
