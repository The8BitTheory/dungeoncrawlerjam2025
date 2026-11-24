#!/usr/bin/env python3
"""Converts RED.VDC / RED1.VDC (opaque ghost rectangles) into transparent VMS ghosts.
usage: ghostvms.py in.vdc out.vdc
Output file (after the 2 byte load address):
  0..47   for view 0..3, part 0..2: source offset in pixel data (word), list offset (word)
  48,49   offset of the pixel data from the start (word)
  50,51   length of the pixel data (word)
  52..    lists (VMS format, one per view/part), then pixel data
Parts: 0 = left half (cols 0..h-1), 1 = right half (cols h..2h-1), 2 = remaining column(s),
h = width//2.  Offsets in a list are relative to the part's own first column, row stride 80.
"""
import sys
ALPHA=5; STRIDE=80
src=open(sys.argv[1],'rb').read()
n=src[2]; assert n==4
views=[]
for v in range(n):
    e=src[3+7*v:10+7*v]
    off=e[0]|e[1]<<8; w=e[2]; h=e[3]
    d=src[2+29+off:2+29+off+w*h]
    views.append((w,h,[list(d[r*w:(r+1)*w]) for r in range(h)]))
def outside(w,h,rows):
    # exterior = colour-0 pixels reachable from the border (4-neighbourhood, pixel resolution)
    pw=w*2
    px=[[ (rows[y][x//2]>>4) if x%2==0 else rows[y][x//2]&15 for x in range(pw)] for y in range(h)]
    out=[[False]*pw for _ in range(h)]
    st=[(x,y) for y in range(h) for x in range(pw) if (x in (0,pw-1) or y in (0,h-1))]
    while st:
        x,y=st.pop()
        if not(0<=x<pw and 0<=y<h) or out[y][x] or px[y][x]!=0: continue
        out[y][x]=True; st+=[(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
    return px,out
lists=bytearray(); data=bytearray(); table=[]
tabl={}
for v,(w,h,rows) in enumerate(views):
    px,out=outside(w,h,rows)
    hw=w//2
    parts=[(0,hw),(hw,2*hw),(2*hw,w)]
    for p,(c0,c1) in enumerate(parts):
        ent=bytearray(); dat=bytearray(); cnt=0
        for y in range(h):
            x=c0
            while x<c1:
                l,r=out[y][2*x],out[y][2*x+1]
                if l and r: x+=1; continue
                if l or r:
                    a,b=px[y][2*x],px[y][2*x+1]
                    if l: a=ALPHA
                    else: b=ALPHA
                    o=y*STRIDE+(x-c0)
                    ent+=bytes([8,o&255,o>>8]); dat.append(a<<4|b); cnt+=1; x+=1
                else:
                    x2=x
                    while x2<c1 and not out[y][2*x2] and not out[y][2*x2+1]: x2+=1
                    o=y*STRIDE+(x-c0)
                    ent+=bytes([1,o&255,o>>8,x2-x]); dat+=bytes(rows[y][x:x2]); cnt+=1; x=x2
        table.append((len(data),len(lists)))
        lists+=bytes([ALPHA,cnt&255,cnt>>8])+ent; data+=dat
hdr=bytearray()
for s,l in table: hdr+=bytes([s&255,s>>8,l&255,l>>8])
dof=52+len(lists)
hdr+=bytes([dof&255,dof>>8,len(data)&255,len(data)>>8])
out=bytes([0,0])+hdr+lists+data
open(sys.argv[2],'wb').write(out)
print(sys.argv[1],'lists',len(lists),'data',len(data),'file',len(out))
