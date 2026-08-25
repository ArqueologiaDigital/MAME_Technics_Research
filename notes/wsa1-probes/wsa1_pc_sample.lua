-- Where do the two processors actually sit?  Sample the PC every frame and
-- report the top addresses at the end of each second.
_G.h1, _G.h2, _G.n = {}, {}, 0
_G.sub = emu.add_machine_frame_notifier(function ()
	local p1 = manager.machine.devices[":cpu1"].state["CURPC"].value
	local p2 = manager.machine.devices[":cpu2"].state["CURPC"].value
	_G.h1[p1] = (_G.h1[p1] or 0) + 1
	_G.h2[p2] = (_G.h2[p2] or 0) + 1
	_G.n = _G.n + 1
	if (_G.n % 300) ~= 0 then return end
	local function top(h, tag)
		local a = {}
		for k, v in pairs(h) do a[#a+1] = {k, v} end
		table.sort(a, function (x, y) return x[2] > y[2] end)
		local s = ""
		for i = 1, math.min(5, #a) do s = s .. string.format(" %06X:%d", a[i][1], a[i][2]) end
		print("PCS " .. tag .. s)
	end
	top(_G.h1, "cpu1")
	top(_G.h2, "cpu2")
end)
