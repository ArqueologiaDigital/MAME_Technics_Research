import re,sys,os
def split(path):
    src=open(path,encoding='utf8',errors='replace').read()
    # strip comments
    src=re.sub(r'/\*.*?\*/','',src,flags=re.S)
    src=re.sub(r'//[^\n]*','',src)
    out={}
    for m in re.finditer(r'^(?:\w[\w:<>,\s\*&]*?)\bwsa1_state::(\w+)\s*\(', src, re.M):
        name=m.group(1); i=src.find('{',m.end()-1)
        if i<0: continue
        d=0; j=i
        while j<len(src):
            if src[j]=='{': d+=1
            elif src[j]=='}':
                d-=1
                if d==0: break
            j+=1
        body=src[i:j+1]
        body=re.sub(r'\s+',' ',body).strip()
        out[name]=body
    return out
a=split(sys.argv[1]); b=split(sys.argv[2])
print("ONLY IN A (%s): "%sys.argv[1], sorted(set(a)-set(b)))
print()
print("ONLY IN B (%s): "%sys.argv[2], sorted(set(b)-set(a)))
print()
print("DIFFERENT BODIES:")
for k in sorted(set(a)&set(b)):
    if a[k]!=b[k]:
        print("=== %s ==="%k)
        print("  A:",a[k][:900])
        print("  B:",b[k][:900])
        print()
