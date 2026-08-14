import csv, collections
D='/home/fsanches/compartilhado/kn7000_mame/notes/data/'
setrow={}; set_cls=collections.defaultdict(set); set6zones={}
with open(D+'kn5000-multisample-sets.tsv') as f:
    for row in csv.DictReader(f,delimiter='\t'):
        si=int(row['set_idx']); setrow[si]=row
        z6=[]
        for z in row['zones(lo-hi:class:entry)'].split(';'):
            if not z: continue
            rng,c,e=z.split(':'); c=int(c)
            set_cls[si].add(c)
            if c==6: z6.append(z)
        set6zones[si]=z6
S6=set(s for s in setrow if 6 in set_cls[s])

print("=== A. PATCH PARTIALS reaching a class-6 SET ===")
hits=collections.defaultdict(list)
allsets_from_patches=set()
with open(D+'kn5000-patch-partials.tsv') as f:
    for row in csv.DictReader(f,delimiter='\t'):
        sids=[int(x) for x in row['set_idx_per_velzone'].split('/')]
        allsets_from_patches.update(sids)
        for vz,si in enumerate(sids):
            if si in S6:
                hits[si].append((row['patch'],row['name'].strip(),row['partial'],vz))
for si in sorted(hits):
    names=sorted(set((h[1],h[0]) for h in hits[si]))
    print(f"  SET {si}: {len(hits[si])} (patch,partial,velzone) hits, {len(names)} distinct patches")
    for n,p in names[:40]: print(f"      patch#{p} {n!r}")
print("  distinct class-6 SETs reached from patches:", sorted(hits))
print("  distinct SETs reachable from patches at all:", len(allsets_from_patches))

print()
print("=== B. NAMED TONE RECORDS (610) reaching a class-6 SET ===")
nhits=collections.defaultdict(list)
allsets_from_names=set()
clsused=collections.Counter()
with open(D+'kn5000-sample-name-table.tsv') as f:
    for row in csv.DictReader(f,delimiter='\t'):
        si=row['set_idx']
        ce=row['(class:entry) used']
        if ce and ':' in ce: clsused[int(ce.split(':')[0])]+=1
        if si=='' or si=='-': continue
        si=int(si); allsets_from_names.add(si)
        if si in S6: nhits[si].append((row['rec'],row['name'].strip(),row['partial'],ce))
for si in sorted(nhits):
    print(f"  SET {si}: {len(nhits[si])} rows")
    for h in nhits[si][:20]: print("      ",h)
print("  distinct class-6 SETs reached from named records:", sorted(nhits))
print("  distinct SETs reachable from named records:", len(allsets_from_names))
print("  class histogram of the '(class:entry) used' column:", dict(sorted(clsused.items())))

print()
print("=== C. class-6 SETs NOT reached by either table ===")
print(sorted(S6 - allsets_from_patches - allsets_from_names))
print()
print("=== D. the 12 class-6 SET descriptors, with their class-6 zones ===")
for si in sorted(S6):
    r=setrow[si]
    print(f"  SET {si:3d} sub={r['sub_addr']} flags={r['flags']} stride={r['stride']} kmin=0x{r['kmin']} kmax=0x{r['kmax']} root=0x{r['root']} base=0x{r['basepitch']} nz={r['n_zones']} classes={sorted(set_cls[si])}")
    print(f"        cls6 zones: {';'.join(set6zones[si])}")
