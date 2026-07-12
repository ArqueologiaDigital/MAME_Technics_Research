-- floppy_yes_sweep.lua : reach the ATTENTION "Are You Sure?" confirm, save state, then test EVERY
-- SEG* button from that state to find YES (the one that executes the format). Detection: the disk
-- device struct 0x50071254 becomes non-zero (disk-init runs on any real disk op), and/or the screen
-- changes to formatting/complete. Snapshots each; run WITHOUT -log.
local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local function setbtn(p, mk, v)
  local port = mach.ioport.ports[":" .. p]; if not port then return end
  for _, f in pairs(port.fields) do if f.mask == mk then f:set_value(v) end end
end

local cand = {}
for tag, port in pairs(mach.ioport.ports) do
  local seg = tag:match("^:(SEG%x%x)$")
  if seg then for _, f in pairs(port.fields) do if f.mask and f.mask>0 then cand[#cand+1]={seg,f.mask} end end end
end
table.sort(cand, function(a,b) if a[1]==b[1] then return a[2]<b[2] else return a[1]<b[1] end end)
emu.print_info("### candidates = "..#cand)

-- nav to ATTENTION: DISK 0x04 -> SEG11 0x10 (FORMAT 2/2) -> SEG0B 0x10 (PAGE UP -> ATTENTION 1/2)
local nav = { {"SEG0D",0x04},{"SEG11",0x10},{"SEG0B",0x10} }
local phase="boot"; local fc=0; local ni=1; local ci=0
_G._n = emu.register_frame_done(function()
  local ok,err = pcall(function()
    fc=fc+1
    local t=mach.time.seconds
    if phase=="boot" then if t>=17 then phase="np"; fc=0 end
    elseif phase=="np" then setbtn(nav[ni][1],nav[ni][2],1); phase="nh"; fc=0
    elseif phase=="nh" and fc>=20 then setbtn(nav[ni][1],nav[ni][2],0); phase="nw"; fc=0
    elseif phase=="nw" and fc>=130 then
      ni=ni+1
      if ni>#nav then mach:save("att"); mach.video:snapshot(); emu.print_info("### saved ATTENTION; sweep begin"); phase="ld"; fc=0
      else phase="np"; fc=0 end
    elseif phase=="ld" then mach:load("att"); phase="ls"; fc=0
    elseif phase=="ls" and fc>=3 then
      ci=ci+1
      if ci>#cand then emu.print_info("### sweep done"); mach:exit(); return end
      setbtn(cand[ci][1],cand[ci][2],1); phase="ch"; fc=0
    elseif phase=="ch" and fc>=12 then setbtn(cand[ci][1],cand[ci][2],0); phase="cw"; fc=0
    elseif phase=="cw" and fc>=60 then
      local ds = sp:read_u32(0x50071254)
      local stat = sp:read_u8(0x5006bc19)
      mach.video:snapshot()
      local flag = (ds~=0) and " <<DISKINIT!>>" or ""
      emu.print_info(string.format("### c%03d %s %02X struct=%08X stat=%02X%s", ci, cand[ci][1], cand[ci][2], ds, stat, flag))
      phase="ld"; fc=0
    end
  end)
  if not ok then emu.print_info("### CALLBACK ERROR: "..tostring(err)) end
end)
emu.print_info("### floppy_yes_sweep loaded")
