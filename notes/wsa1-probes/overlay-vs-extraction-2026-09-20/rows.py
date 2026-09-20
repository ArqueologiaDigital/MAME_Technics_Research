import re,sys
def rows(path, fn):
    src=open(path).read().split('\n')
    # find function
    start=None
    for i,l in enumerate(src):
        if l.startswith('void wsa1_state::%s(address_map &map)'%fn):
            start=i; break
    if start is None: return []
    depth=0; out=[]; buf=''; inrow=False
    i=start
    while i<len(src):
        l=src[i]
        if l.strip()=='}' and depth==1:
            break
        if l.strip()=='{': depth=1
        # strip comments
        code=re.sub(r'//.*','',l)
        if 'map(' in code or inrow:
            buf+=' '+code.strip()
            inrow=True
            if ';' in code:
                out.append((i+1,re.sub(r'\s+',' ',buf).strip()))
                buf=''; inrow=False
        i+=1
    return out
for fn in ['cpu1_map','cpu2_map','lcdc_map']:
    a=rows(sys.argv[1],fn); b=rows(sys.argv[2],fn)
    print('='*20,fn)
    print('--- OVERLAY (%d rows)'%len(a))
    for ln,r in a: print('  %5d  %s'%(ln,r))
    print('--- EXTRACT (%d rows)'%len(b))
    for ln,r in b: print('  %5d  %s'%(ln,r))
