#!/bin/bash
# Question answered: across src/devices/cpu/*, how many CPU device directories
# expose exactly ONE DEFINE_DEVICE_TYPE *and* install their own internal
# address map (address_map_constructor(FUNC(...))) -- and is that one device
# type named for a concrete part number or for a family?
#
# Usage: cpu_device_type_census.sh <path-to-mame-src-devices-cpu>
# Output: TSV  dir <tab> n_define_device_type <tab> has_internal_map <tab> shortname <tab> fullname
set -u
CPU="${1:?usage: $0 <mame>/src/devices/cpu}"
for d in "$CPU"/*/; do
  name=$(basename "$d")
  # count DEFINE_DEVICE_TYPE (and the _PRIVATE/NS variants) in the directory
  n=$(grep -rhoE '\bDEFINE_DEVICE_TYPE(_PRIVATE|_NS)?\b' "$d" --include='*.cpp' --include='*.h' | wc -l)
  # does the device install its OWN internal map?
  if grep -rqE 'address_map_constructor\(FUNC\(' "$d" --include='*.cpp' --include='*.h'; then
    m=yes
  else
    m=no
  fi
  # the single device type's short + full name, when there is exactly one
  if [ "$n" = "1" ]; then
    line=$(grep -rhE '\bDEFINE_DEVICE_TYPE(_PRIVATE|_NS)?\b' "$d" --include='*.cpp' --include='*.h' | head -1)
  else
    line=""
  fi
  printf '%s\t%s\t%s\t%s\n' "$name" "$n" "$m" "$line"
done
