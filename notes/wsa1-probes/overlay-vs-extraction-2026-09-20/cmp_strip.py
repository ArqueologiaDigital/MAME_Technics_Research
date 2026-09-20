import sys,re
s=open(sys.argv[1],encoding='utf-8',errors='replace').read()
out=[];i=0;n=len(s)
while i<n:
    c=s[i]
    if c=='"' or c=="'":
        q=c;out.append(c);i+=1
        while i<n:
            if s[i]=='\\': out.append(s[i:i+2]); i+=2; continue
            out.append(s[i])
            if s[i]==q: i+=1; break
            i+=1
        continue
    if c=='/' and i+1<n and s[i+1]=='/':
        while i<n and s[i]!='\n': i+=1
        continue
    if c=='/' and i+1<n and s[i+1]=='*':
        i+=2
        while i+1<n and not(s[i]=='*' and s[i+1]=='/'): i+=1
        i+=2; continue
    out.append(c); i+=1
t=''.join(out)
lines=[re.sub(r'\s+',' ',l).strip() for l in t.split('\n')]
print('\n'.join(l for l in lines if l))
