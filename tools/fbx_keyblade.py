import struct,zlib,numpy as np
def read(path):
    d=open(path,'rb').read(); ver=struct.unpack_from('<I',d,23)[0]; big=ver>=7500
    def node(o):
        if big: end,np_,pl=struct.unpack_from('<QQQ',d,o); o+=24
        else: end,np_,pl=struct.unpack_from('<III',d,o); o+=12
        nl=d[o]; o+=1
        if end==0: return None,o
        name=d[o:o+nl].decode(); o+=nl
        props=[]
        for _ in range(np_):
            t=chr(d[o]); o+=1
            if t in 'YCIFDL':
                fmt={'Y':'<h','C':'<?','I':'<i','F':'<f','D':'<d','L':'<q'}[t]; props.append(struct.unpack_from(fmt,d,o)[0]); o+=struct.calcsize(fmt)
            elif t in 'fdlib':
                n,enc,cl=struct.unpack_from('<III',d,o); o+=12
                raw=d[o:o+cl]; o+=cl
                if enc: raw=zlib.decompress(raw)
                props.append(np.frombuffer(raw,{'f':'<f4','d':'<f8','l':'<i8','i':'<i4','b':'u1'}[t]))
            elif t in 'SR':
                n=struct.unpack_from('<I',d,o)[0]; o+=4; props.append(d[o:o+n]); o+=n
        kids=[]
        while o<end:
            c,o=node(o)
            if c is None: break
            kids.append(c)
        return (name,props,kids),end
    o=27; top=[]
    while True:
        n,o=node(o)
        if n is None: break
        top.append(n)
    return top
def find(nodes,name):
    for n in nodes:
        if n[0]==name: yield n
def child(n,name):
    return next((k for k in n[2] if k[0]==name),None)

def props70(n):
    p=child(n,'Properties70'); out={}
    if p:
        for q in p[2]: out[q[1][0].split(b'\x00')[0].decode()]=q[1][4:]
    return out

def load_keyblade(path):
    """Return dict: per-polygon-vertex arrays (pos, normal, uv) for triangles, plus dominant bone per control point."""
    top=read(path); O=next(find(top,'Objects')); C=next(find(top,'Connections'))
    objs={n[1][0]:n for n in O[2]}
    conns=[(c[1][1],c[1][2],c[1][0]) for c in C[2]]  # child,parent,type
    parent_of={}
    for ch,pa,t in conns: parent_of.setdefault(ch,[]).append(pa)
    children={}
    for ch,pa,t in conns: children.setdefault(pa,[]).append(ch)
    name=lambda n:n[1][1].split(b'\x00')[0].decode()
    tris=[]
    for g in [n for n in O[2] if n[0]=='Geometry']:
        gid=g[1][0]
        V=child(g,'Vertices')[1][0].reshape(-1,3)
        PVI=child(g,'PolygonVertexIndex')[1][0]
        # polygons
        polys=[];cur=[]
        for k,i in enumerate(PVI):
            if i<0: cur.append((~i,k)); polys.append(cur); cur=[]
            else: cur.append((i,k))
        def layer(lname,dname,iname):
            L=child(g,lname)
            if L is None: return None
            data=child(L,dname)[1][0]
            mt=child(L,'MappingInformationType')[1][0]; rt=child(L,'ReferenceInformationType')[1][0]
            idx=child(L,iname)[1][0] if child(L,iname) else None
            return data,mt,rt,idx
        Nl=layer('LayerElementNormal','Normals','NormalsIndex'); Ul=layer('LayerElementUV','UV','UVIndex')
        Ml=child(g,'LayerElementMaterial')
        def get(l,dim,cp,pv):
            data,mt,rt,idx=l; data=data.reshape(-1,dim)
            j=pv if mt==b'ByPolygonVertex' else cp
            if rt==b'IndexToDirect': j=idx[j]
            return data[j]
        # skin: dominant bone per control point
        dom=np.full(len(V),-1); best=np.zeros(len(V))
        for sk in children.get(gid,[]):
            if objs.get(sk,(0,))[0]!='Deformer': continue
            for cl in children.get(sk,[]):
                c=objs[cl]
                ix=child(c,'Indexes'); w=child(c,'Weights')
                if ix is None: continue
                bone=[name(objs[p]) for p in children.get(cl,[]) if objs[p][0]=='Model']
                bnm=bone[0] if bone else '?'
                for i,ww in zip(ix[1][0],w[1][0]):
                    if ww>best[i]: best[i]=ww; dom[i]=int(bnm[4:]) if bnm.startswith('Bone') else -2
        # material id per polygon
        for pi,poly in enumerate(polys):
            for a in range(1,len(poly)-1):
                tri=[poly[0],poly[a],poly[a+1]]
                tris.append(dict(geo=gid,cp=[t[0] for t in tri],pos=V[[t[0] for t in tri]],
                                 nrm=np.array([get(Nl,3,t[0],t[1]) for t in tri]) if Nl else None,
                                 uv=np.array([get(Ul,2,t[0],t[1]) for t in tri]),
                                 bone=[dom[t[0]] for t in tri]))
    return tris
