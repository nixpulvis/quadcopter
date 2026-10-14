-- sim.lua: run quad.lua against a mocked EdgeTX API, one scenario at a time.
--
-- Usage: lua sim.lua SCRIPT OUTDIR
-- Writes OUTDIR/<scenario>.log draw logs for render.py and fails loudly on
-- any Lua error. EdgeTX runs Lua 5.2; this runs under 5.2 or 5.3.

local script, outdir = arg[1], arg[2]
local RAD = math.pi / 180

-- Flags, matching render.py.
INVERS, BLINK, SMLSIZE, RIGHT, ERASE, MIDSIZE, DBLSIZE = 1, 2, 4, 8, 16, 32, 64
SOLID, DOTTED, FORCE = 0, 1, 0
LCD_W, LCD_H = 128, 64
EVT_ENTER_LONG = 0x100

local out
local function emit(...)
  local t = {}
  for i, v in ipairs({ ... }) do
    t[i] = type(v) == "number" and string.format("%d", math.floor(v)) or tostring(v)
  end
  out:write(table.concat(t, " "), "\n")
end

local function int(v, what)
  assert(type(v) == "number", what .. ": expected a number, got " .. type(v))
  return v
end

lcd = {
  clear = function() emit("C") end,
  drawLine = function(x1, y1, x2, y2, pattern, flags)
    emit("L", int(x1, "x1"), int(y1, "y1"), int(x2, "x2"), int(y2, "y2"),
         int(pattern, "pattern"), flags or 0)
  end,
  drawRectangle = function(x, y, w, h, flags) emit("R", x, y, w, h, flags or 0) end,
  drawFilledRectangle = function(x, y, w, h, flags) emit("F", x, y, w, h, flags or 0) end,
  drawPoint = function(x, y, flags) emit("P", x, y, flags or 0) end,
  drawText = function(x, y, text, flags)
    assert(type(text) == "string", "drawText: text must be a string")
    emit("T", int(x, "x"), int(y, "y"), flags or 0, text)
  end,
}

local sensors, rssi, now = {}, 0, 0

function getFieldInfo(name)
  if sensors[name] == nil then return nil end
  return { id = name, name = name }
end
function getValue(id) return sensors[id] or 0 end
function getRSSI() return rssi, 45, 42 end
function getTime() return now end
function loadScript(path)
  if path == "/SCRIPTS/QUAD/telem_cfg.lua" then
    if CFG == nil then return nil, "not found" end
    return function() return CFG end
  end
  return loadfile(path)
end

local function base(o)
  local s = {
    FM = "LOIT", RxBt = 11.9, Curr = 14.2, Capa = 1320, ["Bat%"] = 74,
    RQly = 100, TPWR = 100, Sats = 14, Alt = 42, GSpd = 3,
    GPS = { lat = 42.3601, lon = -71.0589 },
    Ptch = 0, Roll = 0, Yaw = 90 * RAD,
  }
  for k, v in pairs(o or {}) do
    if v == false then s[k] = nil else s[k] = v end
  end
  return s
end

local scenarios = {
  { "no-telemetry", {}, 0 },
  { "disarmed-level", base({ FM = "STAB*", Capa = 0, Curr = 0.4, RxBt = 12.6, GSpd = 0 }), 100 },
  { "armed-bank-right", base({ Roll = 25 * RAD, Ptch = 8 * RAD }), 100 },
  { "armed-dive-left", base({ Roll = -40 * RAD, Ptch = -15 * RAD, Yaw = 271 * RAD }), 90 },
  { "low-battery", base({ FM = "RTL", RxBt = 10.2, Capa = 4300, RQly = 62, Sats = 5,
                          Roll = 5 * RAD }), 62 },
  { "inverted", base({ Roll = 170 * RAD, Ptch = 10 * RAD }), 100 },
  { "metric", base({ Roll = 10 * RAD }), 100, { units = "metric" } },
  { "no-gps", base({ GPS = false, Sats = false, Alt = false, GSpd = false }), 100 },
}

local chunk = assert(loadfile(script))
for _, sc in ipairs(scenarios) do
  local name, s, r = sc[1], sc[2], sc[3]
  CFG = sc[4]
  local screen = chunk()
  sensors, rssi, now = {}, 0, 0
  screen.init()
  -- Arm on a home fix, then move ~150 m north-east and climb before drawing.
  sensors, rssi = s, r
  if s.GPS then
    local home = s.GPS
    screen.background()
    now = now + 75 * 100 + 2 * 6000
    s.GPS = { lat = home.lat + 0.001, lon = home.lon + 0.0012 }
    s.Alt = (s.Alt or 0) + 30
  end
  now = now + 100
  screen.background()
  out = assert(io.open(outdir .. "/" .. name .. ".log", "w"))
  assert(screen.run(0) == 0)
  out:close()
  print("ok " .. name)
end
