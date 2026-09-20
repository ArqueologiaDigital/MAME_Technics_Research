import re,sys,difflib
def bodies(path):
    src=open(path,encoding='utf-8',errors='replace').read().split('\n')
    out={}
    i=0
    while i<len(src):
        m=re.match(r'^(?:\w[\w:<>&\s\*]*?)\bwsa1_state::(\w+)\s*\(',src[i])
        if m and not src[i].lstrip().startswith('//'):
            name=m.group(1); start=i
            # find opening brace
            j=i
            while j<len(src) and '{' not in src[j]: j+=1
            depth=0; k=j
            while k<len(src):
                depth+=src[k].count('{')-src[k].count('}')
                if depth==0 and k>=j: break
                k+=1
            out[name]=(start+1,[l for l in src[start:k+1]])
            i=k+1
        else:
            i+=1
    return out
def strip(lines):
    r=[]
    inblk=False
    for l in lines:
        s=l
        if inblk:
            if '*/' in s: s=s.split('*/',1)[1]; inblk=False
            else: continue
        while '/*' in s:
            pre,rest=s.split('/*',1)
            if '*/' in rest: s=pre+rest.split('*/',1)[1]
            else: s=pre; inblk=True; break
        s=re.sub(r'//.*','',s)
        s=s.strip()
        if s: r.append(s)
    return r
a=bodies(sys.argv[1]); b=bodies(sys.argv[2])
names=sys.argv[3:]
for n in names:
    if n not in a or n not in b:
        print(f"### {n}: overlay={'yes@'+str(a[n][0]) if n in a else 'MISSING'}  extract={'yes@'+str(b[n][0]) if n in b else 'MISSING'}")
        continue
    sa=strip(a[n][1]); sb=strip(b[n][1])
    if sa==sb:
        print(f"### {n}: IDENTICAL (overlay:{a[n][0]} extract:{b[n][0]})")
    else:
        print(f"### {n}: DIFFERS (overlay:{a[n][0]} extract:{b[n][0]})")
        for l in difflib.unified_diff(sa,sb,'overlay','extract',lineterm='',n=1):
            print('   '+l)
