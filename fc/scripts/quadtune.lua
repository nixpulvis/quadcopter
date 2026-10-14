--[[
Quad Tune: a CRSF menu on the FC that picks which gain the S1 dial tunes.

Installed by quadctl at APM/scripts/quadtune.lua; quadctl fills TARGETS from
quad.yaml (tuning.targets). On the radio: ELRS Lua > Other Devices > the FC >
Quad Tune.

What it may change, and nothing else:
  TUNE, TUNE_MIN, TUNE_MAX, always as one of the TARGETS rows (or all 0 for
  Off). The radio only sends a row number; the ranges come from this file,
  which only quadctl writes over USB.
  Changes are RAM only (param:set, never saved), so every boot starts Off.
  A new target is accepted only while disarmed. Off is accepted any time.

ArduPilot applies the dial to the target gain continuously (also RAM only):
a tuned value is gone after a reboot unless you write it down and save it.
--]]

local TARGETS = {} -- quadctl:targets

local NAME = "Quad Tune"
local SELECTION, INFO = 9, 12
local EV_READ, EV_WRITE = 1, 2

local current = 0      -- 0 = Off, else index into TARGETS
local status = ""

local function options()
  local names = { "Off" }
  for _, t in ipairs(TARGETS) do names[#names + 1] = t.name end
  return table.concat(names, ";")
end

local function target_entry()
  return string.pack(">BzzBBBBz", SELECTION, "Target", options(), current, 0, #TARGETS, 0, "")
end

local function value_text()
  local t = TARGETS[current]
  if not t then return "-" end
  local v = param:get(t.param)
  if v == nil then return "?" end
  return string.format("%.4g", v)
end

local function info_entry(name, text)
  return string.pack(">Bzz", INFO, name, text)
end

local function set_tune(tune, lo, hi)
  -- Range first, so TUNE never points at a target with the wrong range.
  return param:set("TUNE", 0) and param:set("TUNE_MIN", lo) and param:set("TUNE_MAX", hi)
     and param:set("TUNE", tune)
end

local function choose(idx)
  if idx == 0 then
    if set_tune(0, 0, 0) then current, status = 0, "" else status = "Couldn't set Off" end
    return
  end
  local t = TARGETS[idx]
  if not t then
    status = "Unknown target"
  elseif arming:is_armed() then
    status = "Disarm to change"
  elseif set_tune(t.tune, t.min, t.max) then
    current, status = idx, ""
    gcs:send_text(6, string.format("%s: dial tunes %s (%g..%g)", NAME, t.name, t.min, t.max))
  else
    set_tune(0, 0, 0)
    current, status = 0, "Couldn't set " .. t.name
  end
end

-- Show what the FC already has (a TUNE set over USB that isn't in the list
-- shows as Off with a note; the dial is left alone).
local function sync_from_params()
  local tune = param:get("TUNE") or 0
  current = 0
  for i, t in ipairs(TARGETS) do
    if t.tune == tune then current = i end
  end
  if tune ~= 0 and current == 0 then status = string.format("TUNE=%d set by USB", tune) end
end

local menu = crsf:add_menu(NAME)
local ids = {}
if menu then
  ids.target = menu:add_parameter(target_entry()):id()
  ids.value = menu:add_parameter(info_entry("Value", "-")):id()
  ids.status = menu:add_parameter(info_entry("Status", "")):id()
end

local function update()
  local count, id, payload, events = crsf:peek_menu_event()
  if count == 0 then return update, 200 end
  if id ~= ids.target and id ~= ids.value and id ~= ids.status then
    return update, 50 -- another script's menu
  end
  crsf:pop_menu_event()
  if (events & EV_WRITE) ~= 0 and id == ids.target then
    choose(string.unpack(">B", payload))
    crsf:send_write_response(string.pack(">B", current))
  elseif (events & EV_READ) ~= 0 then
    if id == ids.target then
      crsf:send_write_response(target_entry())
    elseif id == ids.value then
      crsf:send_write_response(info_entry("Value", value_text()))
    else
      crsf:send_write_response(info_entry("Status", status))
    end
  else
    crsf:send_response()
  end
  return update, 50
end

if not menu then
  gcs:send_text(3, NAME .. ": no CRSF menu support in this firmware")
  return
end
sync_from_params()
return update, 1000
