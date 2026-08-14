-- Run B1: the 5 RIGHT soft keys, each from a verified SD MENU state
TRIALS = {
  {tag=":cpanel:CPR_SEG5", mask=0x10, name="LCDR1-LOAD"},
  {tag=":cpanel:CPR_SEG5", mask=0x20, name="LCDR2-SAVE"},
  {tag=":cpanel:CPR_SEG7", mask=0x01, name="LCDR3-MEDLEY"},
  {tag=":cpanel:CPR_SEG6", mask=0x01, name="LCDR4-SDAUDIO"},
  {tag=":cpanel:CPR_SEG5", mask=0x01, name="LCDR5-SDSOUND"},
}
dofile("sdnav_lib.lua")
