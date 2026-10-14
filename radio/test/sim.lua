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

-- CRSF frames waiting for crossfireTelemetryPop(), as { command, payload }.
local frames = {}
function crossfireTelemetryPop()
  local f = table.remove(frames, 1)
  if f == nil then return nil end
  return f[1], f[2]
end

-- Encoder side of ArduPilot's passthrough (AP_Frsky_SPort::prep_number and
-- the calc_* packers), so the script's decoder is tested against it.
-- `digits` and `pw` as in ArduPilot: 2 digits are 7 bits, 3 digits 10 bits,
-- then `pw` bits of power of ten, then a sign bit.
local function prep(n, digits, pw)
  local a = math.floor(math.abs(n) + 0.5)
  local nd = digits == 2 and 7 or 10
  if digits == 2 and pw == 0 then
    local r = math.min(a, n < 0 and 63 or 127)
    return n < 0 and r + 64 or r
  end
  local lim, p = (digits == 2) and 100 or 1000, 0
  while a >= lim * 10 ^ p and p < 2 ^ pw - 1 do p = p + 1 end
  local d = math.min(math.floor(a / 10 ^ p + 0.5), 2 ^ nd - 1)
  local r = d * 2 ^ pw + p
  if n < 0 then r = r + 2 ^ (nd + pw) end
  return r
end

local function b(flag, off) return flag and 2 ^ off or 0 end

local pack = {
  [0x5001] = function(t)
    return (t.mode + 1) + b(t.flying, 7) + b(t.armed, 8) + b(t.battFs, 9) + b(t.ekfFs, 10)
      + b(t.fs, 12) + b(t.fence, 13) + b(t.breach, 14) + prep((t.thr or 0) * 0.63, 2, 0) * 2 ^ 19
  end,
  [0x5002] = function(t)
    return t.sats + t.fix * 2 ^ 4 + prep(t.hdop * 10, 2, 1) * 2 ^ 6 + prep(t.alt * 10, 2, 2) * 2 ^ 22
  end,
  [0x5004] = function(t)
    return prep(t.dist, 3, 2) + prep(t.alt * 10, 3, 2) * 2 ^ 12 + math.floor(t.bearing / 3 + 0.5) * 2 ^ 25
  end,
  [0x5005] = function(t) return prep(t.vs * 10, 2, 1) + prep(30, 2, 1) * 2 ^ 9 end,
  [0x5006] = function(t) return 900 + 450 * 2 ^ 11 + prep(t.range * 100, 3, 1) * 2 ^ 21 end,
  [0x5007] = function(t) return 4 * 2 ^ 24 + t.capacity end,
  [0x500B] = function(t) return prep(t.agl * 10, 3, 2) + b(not t.healthy, 13) end,
}

local function le(v, n)
  local out = {}
  for i = 0, n - 1 do out[#out + 1] = math.floor(v / 256 ^ i) % 256 end
  return out
end

-- Queue passthrough packets: singles (0xF0) for the first, then ELRS-style
-- multi frames (0xF2) of up to 3 packets, plus status texts (0xF1).
local function queue(spec)
  local packets = {}
  for _, id in ipairs({ 0x5001, 0x5002, 0x5004, 0x5005, 0x5006, 0x5007, 0x500B }) do
    if spec[id] then packets[#packets + 1] = { id, pack[id](spec[id]) } end
  end
  for i, pk in ipairs(packets) do
    if i == 1 then
      local d = { 0xF0 }
      for _, x in ipairs(le(pk[1], 2)) do d[#d + 1] = x end
      for _, x in ipairs(le(pk[2], 4)) do d[#d + 1] = x end
      frames[#frames + 1] = { 0x80, d }
    elseif i % 3 == 2 then
      local d = { 0xF2, 0 }
      for j = i, math.min(i + 2, #packets) do
        d[2] = d[2] + 1
        for _, x in ipairs(le(packets[j][1], 2)) do d[#d + 1] = x end
        for _, x in ipairs(le(packets[j][2], 4)) do d[#d + 1] = x end
      end
      frames[#frames + 1] = { 0x80, d }
    end
  end
  for _, m in ipairs(spec.msgs or {}) do
    local d = { 0xF1, m[1] }
    for i = 1, #m[2] do d[#d + 1] = string.byte(m[2], i) end
    d[#d + 1] = 0
    frames[#frames + 1] = { 0x80, d }
  end
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

-- Passthrough scenarios: { name, sensors, rssi, cfg, passthrough, event, expect }.
local ST = { mode = 5, armed = true, flying = true, fence = true, thr = 45 }
local function st(o)
  local t = {}
  for k, v in pairs(ST) do t[k] = v end
  for k, v in pairs(o or {}) do t[k] = v end
  return t
end
local GOOD = { sats = 14, fix = 3, hdop = 0.8, alt = 72 }
local pts = {
  { "pt-prearm", base({ FM = "LOIT*", Capa = 0, Curr = 0.4, RxBt = 12.6, GSpd = 0, Sats = 9 }), 100,
    nil, { [0x5001] = st({ armed = false, flying = false, thr = 0 }),
           [0x5002] = { sats = 9, fix = 2, hdop = 2.6, alt = 70 },
           [0x5007] = { capacity = 5200 },
           msgs = { { 3, "PreArm: Need 3D Fix" } } }, nil,
    { "LOITER", "DISARM", "9 2D", "100%" } },
  { "pt-flying", base({ Roll = 12 * RAD, Ptch = 4 * RAD, Yaw = 40 * RAD }), 100,
    nil, { [0x5001] = st(), [0x5002] = GOOD,
           [0x5004] = { dist = 149, alt = 30, bearing = 222 }, [0x5005] = { vs = 1.5 } }, nil,
    { "LOITER", "ARMED", "489ft", "98/236" } },
  { "pt-batt-failsafe", base({ FM = "RTL", RxBt = 10.4, Capa = 4350, Roll = -6 * RAD,
                               Ptch = 6 * RAD, Yaw = 225 * RAD }), 100,
    nil, { [0x5001] = st({ mode = 6, battFs = true, fs = true }), [0x5002] = GOOD,
           [0x5004] = { dist = 120, alt = 30, bearing = 228 }, [0x5005] = { vs = 0 } }, nil,
    { "RTL", "BATT FS" } },
  { "pt-ekf", base({ FM = "ALTH", Roll = 3 * RAD, Yaw = 90 * RAD, Sats = 7 }), 100,
    nil, { [0x5001] = st({ mode = 2, ekfFs = true, fs = true }),
           [0x5002] = { sats = 7, fix = 3, hdop = 3.1, alt = 60 },
           [0x5004] = { dist = 64, alt = 18, bearing = 300 }, [0x5005] = { vs = -0.8 } }, nil,
    { "ALTHLD", "EKF", "7 3D" } },
  { "pt-fence-terrain", base({ FM = "RTL", Roll = -18 * RAD, Ptch = 10 * RAD, Yaw = 10 * RAD }), 100,
    nil, { [0x5001] = st({ mode = 6, breach = true }), [0x5002] = GOOD,
           [0x5004] = { dist = 152, alt = 120, bearing = 190 }, [0x5005] = { vs = -2.5 },
           [0x500B] = { agl = 104.3, healthy = true } }, nil,
    { "FENCE", "341~23" } },
  { "pt-rangefinder", base({ Yaw = 0 }), 100,
    { units = "metric" }, { [0x5001] = st(), [0x5002] = GOOD,
           [0x5004] = { dist = 3, alt = 2, bearing = 0 }, [0x5006] = { range = 2.4 },
           [0x500B] = { agl = 3, healthy = true } }, nil,
    { "2~1", "3m" } },
  { "pt-page2", base({ FM = "LOIT*" }), 100,
    nil, { [0x5001] = st({ armed = false, flying = false, thr = 0 }), [0x5002] = GOOD,
           [0x500B] = { agl = 0, healthy = false },
           msgs = { { 6, "EKF3 IMU0 is using GPS" }, { 4, "Battery 1 is low 10.4V" },
                    { 6, "Disarming motors" }, { 6, "Land complete" },
                    { 5, "This one pushes the oldest out" } } }, "next",
    { "This one pushes the oldest out", "Battery 1 is low 10.4V", "3D 0.8", "bad", "gnd", "on" } },
}
for _, p in ipairs(pts) do scenarios[#scenarios + 1] = p end

EVT_VIRTUAL_NEXT = 0x200

local chunk = assert(loadfile(script))
for _, sc in ipairs(scenarios) do
  local name, s, r = sc[1], sc[2], sc[3]
  CFG = sc[4]
  local screen = chunk()
  sensors, rssi, now, frames = {}, 0, 0, {}
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
  if sc[5] then queue(sc[5]) end
  now = now + 100
  screen.background()
  screen.background()
  if sc[6] then
    out = io.open("/dev/null", "w")
    screen.run(EVT_VIRTUAL_NEXT)
    out:close()
  end
  local path = outdir .. "/" .. name .. ".log"
  out = assert(io.open(path, "w"))
  assert(screen.run(0) == 0)
  out:close()
  local log = assert(io.open(path)):read("*a")
  for _, want in ipairs(sc[7] or {}) do
    assert(log:find("T %d+ %d+ %d+ " .. want:gsub("%p", "%%%0") .. "\n"),
           name .. ": expected text '" .. want .. "' on screen")
  end
  print("ok " .. name)
end
