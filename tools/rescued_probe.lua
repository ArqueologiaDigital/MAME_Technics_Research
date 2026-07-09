-- KN7000 splash probe: does a real image palette/blit ever run at boot?
local mem = manager.machine.devices[":maincpu"].spaces["program"]
local GREEN = 0x0080FF80
-- CLUT image range = indices 0x1D..0xF3 -> bytes 0x50031490+0x1D*4 .. +0xF3*4
local CLUT = 0x50031490
local clut_lo = CLUT + 0x1D*4
local clut_hi = CLUT + 0xF3*4 + 3
local clut_writes = {}          -- non-green writes into image CLUT range
local clut_write_count = 0
-- Framebuffer picture-box write watch (central area). FB=0x500D4080, 640x240.
local FB = 0x500D4080
local fb_write_count = 0
local fb_vals = {}

-- write tap on the whole workram to catch CLUT + FB writes
local wram = mem
wram:install_write_tap(clut_lo, clut_hi, "clutwatch", function(off, data, mask)
  clut_write_count = clut_write_count + 1
  -- record any word-ish value that isn't the green placeholder
  if data ~= GREEN and data ~= 0 then
    local k = string.format("0x%08X=0x%08X", off, data)
    if not clut_writes[k] then clut_writes[k] = 0 end
    clut_writes[k] = clut_writes[k] + 1
  end
end)

local dumped = false
local function dump()
  if dumped then return end
  dumped = true
  local out = {}
  local function p(s) out[#out+1]=s end
  p("=== KN7000 SPLASH PROBE @ t="..tostring(manager.machine.time.seconds).."s ===")
  -- jiffy
  p(string.format("jiffy(0x500D3C58)=0x%08X", mem:read_u32(0x500D3C58)))
  -- FB histogram (read u32, 38400 reads)
  local hist = {}
  for i=0,153600-1,4 do
    local v = mem:read_u32(FB+i)
    for b=0,3 do
      local idx = (v >> (8*b)) & 0xFF
      hist[idx] = (hist[idx] or 0) + 1
    end
  end
  local distinct=0
  for k,_ in pairs(hist) do distinct=distinct+1 end
  p("FB distinct indices = "..distinct)
  -- top 12
  local arr={}
  for k,v in pairs(hist) do arr[#arr+1]={k,v} end
  table.sort(arr, function(a,b) return a[2]>b[2] end)
  for i=1,math.min(12,#arr) do
    p(string.format("  FB idx 0x%02X : %d px", arr[i][1], arr[i][2]))
  end
  -- CLUT samples
  p("--- CLUT entries (0x00BBGGRR) ---")
  for _,idx in ipairs({0x00,0x01,0x1C,0x1D,0x40,0x80,0xC0,0xD0,0xD4,0xD8,0xF3,0xF4,0xFF}) do
    p(string.format("  CLUT[0x%02X]=0x%08X", idx, mem:read_u32(CLUT+idx*4)))
  end
  -- CLUT image-range write summary
  p("--- CLUT image-range writes (idx 0x1D..0xF3) ---")
  p("  total writes into range = "..clut_write_count)
  local nonc=0
  for k,v in pairs(clut_writes) do nonc=nonc+1 end
  p("  distinct NON-green/nonzero values written = "..nonc)
  local shown=0
  for k,v in pairs(clut_writes) do
    p("    "..k.." x"..v); shown=shown+1; if shown>=16 then break end
  end
  -- VRAM 0x90000000 density scan
  local nz=0
  for i=0,0x80000-1,4 do
    if mem:read_u32(0x90000000+i) ~= 0 then nz=nz+1 end
  end
  p(string.format("VRAM 0x90000000..+0x80000: nonzero u32 = %d / %d", nz, 0x80000/4))
  p("VRAM first 16 u32:")
  local s=""
  for i=0,15 do s=s..string.format("%08X ", mem:read_u32(0x90000000+i*4)) end
  p("  "..s)
  local f=io.open("/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/74c7edc4-f16b-4349-97a0-39242e320cdb/scratchpad/probe_out.txt","w")
  f:write(table.concat(out,"\n").."\n")
  f:close()
  emu.print_info(table.concat(out,"\n"))
end

emu.register_periodic(function()
  if manager.machine.time.seconds >= 17.0 then
    dump()
    manager.machine:exit()
  end
end)
