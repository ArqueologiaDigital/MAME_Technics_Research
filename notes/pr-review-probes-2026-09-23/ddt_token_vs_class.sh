#!/bin/bash
# Question answered: in src/devices/cpu, how often is a DEFINE_DEVICE_TYPE token
# (the part number the driver writes in machine_config) DIFFERENT from the C++
# class that implements it -- i.e. how often does MAME name the *device type*
# for a concrete part while the *class* keeps a family name?
# Usage: ddt_token_vs_class.sh <mame>/src/devices/cpu
set -u
CPU="${1:?usage: $0 <mame>/src/devices/cpu}"
grep -rhoE 'DEFINE_DEVICE_TYPE(_PRIVATE|_NS)?\([^)]*\)' "$CPU" --include='*.cpp' --include='*.h' |
sed -E 's/DEFINE_DEVICE_TYPE(_PRIVATE|_NS)?\(//; s/\)$//' |
awk -F',' '{
  tok=$1; cls=$2;
  gsub(/^[ \t]+|[ \t]+$/,"",tok); gsub(/^[ \t]+|[ \t]+$/,"",cls);
  sub(/.*::/,"",cls);                    # strip namespace
  ltok=tolower(tok); gsub(/_/,"",ltok);
  lcls=cls; sub(/_device$/,"",lcls); sub(/_cpu$/,"",lcls); gsub(/_/,"",lcls);
  if (index(lcls, ltok) == 0) print "MISMATCH\t" tok "\t" cls; else print "match\t" tok "\t" cls;
}'
