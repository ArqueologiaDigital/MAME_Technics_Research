		-- Slider and knob library starts.
		-- Can be copied as-is to other layouts.
		-----------------------------------------------------------------------
		-- Widgets are stored PER VIEW. A single shared list is WRONG when the same control is registered in
		-- more than one view (e.g. a Compact view plus a single-block view): each view has its own coordinate
		-- normalisation, so a pointer hit-test in view A against a widget's bounds registered for view B gives
		-- false matches (symptom: clicking near one control in one view drags a slider that "lives" in another
		-- view whose normalised bounds happen to overlap). Keying the widget list by view fixes that.
		local view_widgets = {}   -- view (userdata) -> list of its widgets
		local active_wl = nil     -- widget list of the view whose pointer last moved (for the frame wheel poll)
		local pointers = {}       -- Tracks pointer state (keyed by pointer id).
		local hover_x, hover_y = -1, -1   -- last pointer position (for wheel-over-widget hit testing)

		local function widget_list(view)
			local wl = view_widgets[view]
			if wl == nil then wl = {}; view_widgets[view] = wl end
			return wl
		end

		-- The knob's Y position must be animated using <animate inputtag="{port_name}">.
		-- The click area's vertical size must exactly span the range of the
		-- knob's movement.
		function add_vertical_slider(view, clickarea_id, knob_id, port_name)
			table.insert(widget_list(view), {
				clickarea   = get_layout_item(view, clickarea_id),
				slider_knob = get_layout_item(view, knob_id),
				field       = get_port_field(port_name),
				is_knob     = false })
		end

		-- A sweep between the attached field's min and max values requires
		-- moving the pointer by `scale * clickarea.height` pixes.
		function add_simplecounter_knob(view, clickarea_id, port_name, scale)
			table.insert(widget_list(view), {
				clickarea = get_layout_item(view, clickarea_id),
				field     = get_port_field(port_name),
				is_knob   = true,
				scale     = scale })
		end

		-- An INFINITE rotary knob (e.g. the TEMPO/PROGRAM wheel). A circular drag rotates the `finger_id`
		-- element around the knob centre and steps the attached relative encoder (an IPT_ADJUSTER the driver
		-- diffs wrap-aware). `finger_id` is repositioned every frame via set_bounds_callback; the running
		-- angle accumulates without limit, so the finger just keeps going round and round.
		function add_rotary_knob(view, clickarea_id, finger_id, port_name)
			local w = {
				clickarea = get_layout_item(view, clickarea_id),
				finger    = get_layout_item(view, finger_id),
				field     = get_port_field(port_name),
				is_rotary = true,
				angle     = 0.0,   -- running finger angle (radians), unbounded
				notch     = 0 }    -- last encoder notch emitted (for stepping the adjuster)
			table.insert(widget_list(view), w)
			-- The finger orbits the knob centre at the current angle (0 = 12 o'clock, clockwise positive).
			-- item.bounds is normalised PER-AXIS (x by view width, y by view height), so a screen-circular
			-- orbit needs the x offset scaled by the click area's normalised WIDTH and the y offset by its
			-- normalised HEIGHT (the click area is square in view units, so these encode the pixel aspect).
			-- Orbit radius 0.24 keeps the finger (half-size 0.148) fully inside the wheel (r 0.48) with an
			-- internal margin; the wheel is square in view units so scale x by width, y by height.
			w.finger:set_bounds_callback(function()
				local b = w.clickarea.bounds
				local cx = (b.x0 + b.x1) / 2
				local cy = (b.y0 + b.y1) / 2
				local wd = b.x1 - b.x0
				local ht = b.y1 - b.y0
				local fx = cx + wd * 0.24 * math.sin(w.angle)
				local fy = cy - ht * 0.24 * math.cos(w.angle)
				local fhx = wd * 0.148
				local fhy = ht * 0.148
				return emu.render_bounds(fx - fhx, fy - fhy, fx + fhx, fy + fhy)
			end)
			return w
		end

		function get_layout_item(view, item_id)
			local item = view.items[item_id]
			if item == nil then
				emu.print_error("Layout element: '" .. item_id .. "' not found.")
			end
			return item
		end

		function get_port_field(port_name)
			local port = file.device:ioport(port_name)
			if port == nil then
				emu.print_error("Port: '" .. port_name .. "' not found.")
				return nil
			end
			local field = nil
			for k, val in pairs(port.fields) do
				field = val
				break
			end
			if field == nil then
				emu.print_error("Port: '" .. port_name .."' does not seem to be an IPT_ADJUSTER.")
				return nil
			end
			return field
		end

		-- Step the rotary encoder: map the accumulated angle to notches and nudge the adjuster by the
		-- notch delta (wrapping 0..100). The driver diffs the adjuster wrap-aware into [0x17] encoder steps.
		local ROTARY_STEPS_PER_REV = 24
		local function rotary_emit(w)
			local target = math.floor(w.angle * ROTARY_STEPS_PER_REV / (2 * math.pi) + 0.5)
			if target ~= w.notch then
				local v = (w.field.user_value + (target - w.notch)) % 101
				if v < 0 then v = v + 101 end
				w.field.user_value = v
				w.notch = target
			end
		end

		-- Pointer angle around a widget's knob centre (0 = 12 o'clock, clockwise positive). Per-axis
		-- normalisation (÷ width, ÷ height) matches the finger's aspect-corrected orbit, so the finger
		-- tracks the cursor faithfully all the way round instead of leading/lagging near the sides.
		local function knob_angle(w, x, y)
			local b = w.clickarea.bounds
			local cx = (b.x0 + b.x1) / 2
			local cy = (b.y0 + b.y1) / 2
			return math.atan((x - cx) / (b.x1 - b.x0), (cy - y) / (b.y1 - b.y0))
		end

		-- Mouse-WHEEL editing for rotary knobs. MAME's layout pointer API does NOT deliver wheel events,
		-- so we read the mouse device's relative Z axis directly each frame (the sandbox exposes `machine`,
		-- hence machine.input). One detent = 120 * RELATIVE_PER_PIXEL(512) = 61440 accumulator units
		-- (SDL osd: m_v += wheel.y * 120 * RELATIVE_PER_PIXEL). Each notch nudges the finger and the encoder
		-- exactly like a click of a drag, but only while the cursor hovers over the wheel.
		local WHEEL_PER_NOTCH = 120 * 512
		local wheel_item, wheel_probed, wheel_accum = nil, false, 0
		local function find_wheel_item()
			local input = machine.input
			if input == nil then return nil end
			local classes = input.device_classes
			if classes == nil then return nil end
			local mouse = classes["mouse"]
			if mouse == nil then return nil end
			for _, mdev in pairs(mouse.devices) do
				for _, it in pairs(mdev.items) do
					if it.token == "ZAXIS" then return it end   -- first mouse's wheel axis
				end
			end
			return nil
		end
		function poll_rotary_wheels()
			if not wheel_probed then wheel_item = find_wheel_item(); wheel_probed = true end
			if wheel_item == nil or active_wl == nil then return end
			local dv = machine.input:code_value(wheel_item.code)
			if dv == 0 then return end
			-- find a rotary widget (in the ACTIVE view) under the cursor's last-known position
			local target = nil
			for i = 1, #active_wl do
				if active_wl[i].is_rotary and active_wl[i].clickarea.bounds:includes(hover_x, hover_y) then
					target = active_wl[i]; break
				end
			end
			if target == nil then wheel_accum = 0; return end
			wheel_accum = wheel_accum + dv
			local step = 2 * math.pi / ROTARY_STEPS_PER_REV
			while wheel_accum >= WHEEL_PER_NOTCH do
				wheel_accum = wheel_accum - WHEEL_PER_NOTCH
				target.angle = target.angle + step   -- scroll up: turn clockwise / increase
				rotary_emit(target)
			end
			while wheel_accum <= -WHEEL_PER_NOTCH do
				wheel_accum = wheel_accum + WHEEL_PER_NOTCH
				target.angle = target.angle - step
				rotary_emit(target)
			end
		end

		-- `wl` is the widget list of the view this callback was installed on (see install_slider_callbacks).
		-- Only widgets belonging to THIS view are hit-tested, so a click never matches another view's control.
		local function pointer_updated(wl, type, id, dev, x, y, btn, dn, up, cnt)
			hover_x, hover_y = x, y   -- remember where the cursor is, so the wheel poll can hit-test it
			active_wl = wl            -- this is the view the user is interacting with

			-- If a button is not pressed, reset the state of the current pointer.
			if btn & 1 == 0 then
				pointers[id] = nil
				return
			end

			-- If a button was just pressed, find the affected widget, if any.
			if dn & 1 ~= 0 then
				for i = 1, #wl do
					local found, relative
					if wl[i].slider_knob and wl[i].slider_knob.bounds:includes(x, y) then
						found = true
						relative = true
					elseif wl[i].clickarea.bounds:includes(x, y) then
						found = true
						relative = false
					end
					if found then
						pointers[id] = {
							selected_wl = wl,
							selected_widget = i,
							relative = relative,
							start_y = y,
							start_value = wl[i].field.user_value }
						if wl[i].is_rotary then
							pointers[id].last_pa = knob_angle(wl[i], x, y)
						end
						break
					end
				end
			end

			-- If there is no widget selected by the current pointer, we are done.
			if pointers[id] == nil then
				return
			end

			-- A widget is selected. Update its state based on the pointer's Y
			-- position. It is assumed the attached IO field is an IPT_ADJUSTER.

			local pointer = pointers[id]
			local widget = pointer.selected_wl[pointer.selected_widget]

			-- Rotary knob: rotate the finger by the pointer's angular motion and step the encoder. The angle
			-- accumulates without limit, so it can be spun round and round (24 encoder steps per revolution).
			if widget.is_rotary then
				local pa = knob_angle(widget, x, y)
				local d = pa - pointer.last_pa
				if d > math.pi then d = d - 2 * math.pi elseif d < -math.pi then d = d + 2 * math.pi end
				widget.angle = widget.angle + d
				pointer.last_pa = pa
				rotary_emit(widget)
				return
			end

			local min_value = widget.field.minvalue
			local max_value = widget.field.maxvalue
			local value_range = max_value - min_value

			local new_value
			if widget.is_knob then
				local step_y = value_range / (widget.scale * widget.clickarea.bounds.height)
				new_value = pointer.start_value + (pointer.start_y - y) * step_y
			else
				local knob_half_height = widget.slider_knob.bounds.height / 2
				local min_y = widget.clickarea.bounds.y0 + knob_half_height
				local max_y = widget.clickarea.bounds.y1 - knob_half_height

				if pointer.relative then
					-- User clicked on the knob. The new value will depend on how
					--  much the knob was dragged.
					new_value = pointer.start_value - value_range * (y - pointer.start_y) / (max_y - min_y)
				else
					-- User clicked elsewhere on the slider. The new value will depend on
					-- the absolute position of the click.
					new_value = max_value - value_range * (y - min_y) / (max_y - min_y)
				end
			end

			new_value = math.floor(new_value + 0.5)
			if new_value < min_value then new_value = min_value end
			if new_value > max_value then new_value = max_value end
			widget.field.user_value = new_value
		end

		local function pointer_left(type, id, dev, x, y, up, cnt)
			pointers[id] = nil
		end

		local function pointer_aborted(type, id, dev, x, y, up, cnt)
			pointers[id] = nil
		end

		local function forget_pointers()
			pointers = {}
		end

		function install_slider_callbacks(view)
			local wl = widget_list(view)
			view:set_pointer_updated_callback(function(type, id, dev, x, y, btn, dn, up, cnt)
				pointer_updated(wl, type, id, dev, x, y, btn, dn, up, cnt)
			end)
			view:set_pointer_left_callback(pointer_left)
			view:set_pointer_aborted_callback(pointer_aborted)
			view:set_forget_pointers_callback(forget_pointers)
		end
		-----------------------------------------------------------------------
		-- Slider and knob library ends.
