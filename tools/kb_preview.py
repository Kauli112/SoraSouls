"""Preview the texture sheet of KH2 weapon .mdlx files (for identifying which file is which Keyblade).
Reads the BAR, the type-7 texture entry, unswizzles the 8-bit image and applies the palette. Preview only."""
import struct,glob,sys,numpy as np
from PIL import Image, ImageDraw
def unswz(buf,w,h):
    y,x=np.mgrid[0:h,0:w]
    bl=(y&~0xf)*w+(x&~0xf)*2; ss=(((y+2)>>2)&1)*4
    py=(((y&~3)>>1)+(y&1))&7; cl=py*w*2+((x+ss)&7)*4; bn=((y>>1)&1)+((x>>2)&2)
    return buf[bl+cl+bn]
def tex(fn):
    d=open(fn,'rb').read(); n=struct.unpack_from('<I',d,4)[0]
    for i in range(n):
        t,_,_,off,size=struct.unpack_from('<HH4sII',d,16+i*16)
        if t==7: break
    h=struct.unpack_from('<9I',d,off)
    pix=np.frombuffer(d,np.uint8,h[8]-h[7],off+h[7])
    p=np.frombuffer(d,np.uint8,1024,off+h[8]).reshape(256,4).copy()
    idx=np.arange(256); p=p[(idx&~0x18)|((idx&0x8)<<1)|((idx&0x10)>>1)]
    rgb=np.clip(p[:,:3].astype(int)*2,0,255).astype(np.uint8)
    W=256;H=len(pix)//W
    return Image.fromarray(rgb[unswz(pix,W,H)])
fs=sorted(glob.glob(sys.argv[1]+"/W_EX010*.mdlx"))
cols=3; tw,th=384,192
out=Image.new('RGB',(tw*cols,(th+16)*((len(fs)+cols-1)//cols)),'white')
for k,f in enumerate(fs):
    try: im=tex(f)
    except Exception as e: print(f,e); continue
    im=im.crop((0,0,256,128)).resize((tw,th))
    x=(k%cols)*tw;y=(k//cols)*(th+16)
    out.paste(im,(x,y+16));ImageDraw.Draw(out).text((x+4,y+2),f.split('/')[-1],fill='black')
out.save(sys.argv[2])
