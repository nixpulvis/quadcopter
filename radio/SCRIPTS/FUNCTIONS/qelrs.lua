-- Function script: applies quadctl's ELRS settings once per power-up.
-- Model > Special Functions: ON, Lua Script, qelrs. See tools/quadctl/README.md.

local core = loadScript("/SCRIPTS/QUAD/elrs.lua")()
local state

local function init()
  state = core.new()
end

local function run()
  state = core.step(state, getTime())
end

return { init = init, run = run }
