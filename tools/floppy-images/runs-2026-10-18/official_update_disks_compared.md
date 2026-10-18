# Official KN5000 update disks vs the KN5000's own formatter and a rebuilt software-list disk

Sources (archive.org item technics-kn5000-system-update-disks, folder "01-The_original_distribution_format"):
v5/v6 = the .IMG inside kn5000update5v0.zip (md5 dcbd48e5...) / KN5000update6v0.zip (20598ae7...), each paired with DOSIMAGE.EXE;
v7/v8 = the 1,474,560 bytes appended at offset 49152 of KN5KPV7.EXE (9b5faab1...) / KN5KPV8.EXE (cc893c2b...), Matsushita's
"Self executable Image file to FD V0.1" (DOS, 1998); v9/v10 = KN5V9.IMG (9cff518d...) / Kn5kv10.img (3355b87b...) as uploaded
in 2023. hd-ae5000_disk.img from "02-System_update_floppy_images". Produced by:

| image                        | OEM      | 0x25 | 55AA | label       | files | created         | accessed   | contiguous | slack          | free space         |
|------------------------------|----------|------|------|-------------|-------|-----------------|------------|------------|----------------|--------------------|
| v5_from_zip.img              | (O%W{IHC | 00   | no   | -           | 4     | 0               | 0          | yes        | 00x951 01x27   | F6x387072 E5x12288 |
| v6_from_zip.img              | (;S2rIHC | 00   | no   | -           | 4     | 0               | 0          | yes        | 00x1011 20x72  | 00x16239 FFx6636   |
| v7_from_exe.img              | Technics | 00   | no   | -           | 4     | 0               | 0          | yes        | E5x1352 00x363 | E5x397824          |
| v8_from_exe.img              | Technics | 00   | no   | -           | 4     | 0               | 0          | yes        | 00x456 E5x110  | E5x397312          |
| v9_orig.img                  | Technics | 01   | no   | -           | 4     | 1980-01-01      | 2023-02-26 | yes        | 00x1390 DBx1   | E5x397312          |
| v10_orig.img                 | Technics | 01   | no   | -           | 4     | 1980-01-01      | 2023-02-26 | yes        | 00x1420        | E5x397312          |
| hd-ae5000_disk.img           | Technics | 00   | no   | -           | 1     | 2023-03-02 5CF4 | 2023-03-02 | yes        | B0x18 C5x17    | E5x399297 00x24402 |
| kn5000_formatted.img         | Technics | 00   | no   | ___________ | 0     |                 |            | yes        | -              | E5x1457664         |
| kn5000_formatted_unnamed.img | Technics | 00   | no   | -           | 0     |                 |            | yes        | -              | E5x1457664         |
| rebuilt_ca5001.img           | Technics | 00   | no   | CA5001_____ | 30    | 0               | 0          | yes        | 00x6396        | E5x391168          |
