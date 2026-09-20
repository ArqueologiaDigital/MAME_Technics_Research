import re,sys
def funcs(path):
    src=open(path).read().split("\n")
    out={}
    i=0
    while i<len(src):
        m=re.match(r'^(?:[\w:<>,&\* ]+?)\bwsa1_state::(\w+)\s*\(', src[i])
        if m and not src[i].lstrip().startswith("//"):
            name=m.group(1); j=i; depth=0; started=False; body=[]
            while j<len(src):
                body.append(src[j]); depth+=src[j].count("{")-src[j].count("}")
                if "{" in src[j]: started=True
                if started and depth<=0: break
                j+=1
            out[name]=(i+1,"\n".join(l for l in body if l.strip() and not l.strip().startswith("//")))
            i=j
        i+=1
    return out
a=funcs(sys.argv[1]); b=funcs(sys.argv[2])
only_a=sorted(set(a)-set(b)); only_b=sorted(set(b)-set(a))
print("ONLY IN OVERLAY :", " ".join(only_a))
print("ONLY IN EXTRACT :", " ".join(only_b))
print("\nBODY DIFFERS (both present):")
for k in sorted(set(a)&set(b)):
    if a[k][1].replace(" ","").replace("\t","") != b[k][1].replace(" ","").replace("\t",""):
        print(f"  {k}  overlay:{a[k][0]}  extract:{b[k][0]}")
