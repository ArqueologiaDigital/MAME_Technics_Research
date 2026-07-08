		-- Slider and knob library starts.
		-- Can be copied as-is to other layouts.
		-----------------------------------------------------------------------
		local widgets = {}   -- Stores slider and knob information.
		local pointers = {}  -- Tracks pointer state.

		-- The knob's Y position must be animated using <animate inputtag="{port_name}">.
		-- The click area's vertical size must exactly span the range of the
		-- knob's movement.
		function add_vertical_slider(view, clickarea_id, knob_id, port_name)
			table.insert(widgets, {
				clickarea   = get_layout_item(view, clickarea_id),
				slider_knob = get_layout_item(view, knob_id),
				field       = get_port_field(port_name),
				is_knob     = false })
		end

		-- A sweep between the attached field's min and max values requires
		-- moving the pointer by `scale * clickarea.height` pixes.
		function add_simplecounter_knob(view, clickarea_id, port_name, scale)
			table.insert(widgets, {
				clickarea = get_layout_item(view, clickarea_id),
				field     = get_port_field(port_name),
				is_knob   = true,
				scale     = scale })
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

		local function pointer_updated(type, id, dev, x, y, btn, dn, up, cnt)
			-- If a button is not pressed, reset the state of the current pointer.
			if btn & 1 == 0 then
				pointers[id] = nil
				return
			end

			-- If a button was just pressed, find the affected widget, if any.
			if dn & 1 ~= 0 then
				for i = 1, #widgets do
					local found, relative
					if widgets[i].slider_knob and widgets[i].slider_knob.bounds:includes(x, y) then
						found = true
						relative = true
					elseif widgets[i].clickarea.bounds:includes(x, y) then
						found = true
						relative = false
					end
					if found then
						pointers[id] = {
							selected_widget = i,
							relative = relative,
							start_y = y,
							start_value = widgets[i].field.user_value }
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
			local widget = widgets[pointer.selected_widget]

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
			view:set_pointer_updated_callback(pointer_updated)
			view:set_pointer_left_callback(pointer_left)
			view:set_pointer_aborted_callback(pointer_aborted)
			view:set_forget_pointers_callback(forget_pointers)
		end
		-----------------------------------------------------------------------
		-- Slider and knob library ends.
