import sys,re,os
src=sys.argv[1]; out=sys.argv[2]
os.makedirs(out,exist_ok=True)
# reuse strip
sys.path.insert(0,os.path.dirname(os.path.abspath(sys.argv[0])))
import subprocess
txt=subprocess.run(['python3',os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),'strip.py'),src],capture_output=True,text=True).stdout
lines=txt.split('\n')
cur=None;buf=[];depth=0
pat=re.compile(r'^(?:[A-Za-z_][\w:<>,&*\s]*?\s)?wsa1_state::([a-z0-9_]+)\s*\(')
for l in lines:
    m=pat.match(l)
    if m and cur is None and depth==0:
        cur=m.group(1);buf=[l];depth=l.count('{')-l.count('}')
        if depth<=0 and '{' in l: cur=None
        continue
    if cur:
        buf.append(l);depth+=l.count('{')-l.count('}')
        if depth<=0:
            open(os.path.join(out,cur+'.txt'),'w').write('\n'.join(buf))
            cur=None;buf=[]
