import collections, os, sys
REPO='/home/fsanches/compartilhado/kn7000_mame'
SETS=os.path.join(REPO,'notes/data/kn5000-multisample-sets.tsv')

def read_sets():
    rows=[l.rstrip('\n').split('\t') for l in open(SETS)]
    hdr,rows=rows[0],rows[1:]
    ix={k:i for i,k in enumerate(hdr)}
    out=[]
    for r in rows:
        st=int(r[ix['stride']]); fl=int(r[ix['flags']],16)
        root=int(r[ix['root']],16); base=int(r[ix['basepitch']],16)
        piv=(root<<8)+0x80
        zs=r[ix['zones(lo-hi:class:entry)']]; ft=r[ix['finetune(E:hex)']]
        if not zs: continue
        fts={}
        if ft:
            for f in ft.split(';'):
                k,v=f.split(':'); fts[int(k)]=v
        zones=[]
        for i,z in enumerate(zs.split(';')):
            rng,cls,ent=z.split(':'); lo,hi=[int(x) for x in rng.split('-')]
            trim=0
            if st==6 and i in fts:
                b=bytes.fromhex(fts[i]); trim=b[2]|(b[3]<<8)
                if trim>=0x8000: trim-=0x10000
            zones.append((lo,hi,int(cls),int(ent,16),(base-piv)+trim,trim,i))
        out.append(dict(sid=r[ix['set_idx']],stride=st,flags=fl,
                        kmin=int(r[ix['kmin']],16),kmax=int(r[ix['kmax']],16),
                        root=root,base=base,piv=piv,zones=zones,
                        sub_addr=r[ix['sub_addr']],region_off=r[ix['region_off']],
                        ftraw=fts))
    return out
