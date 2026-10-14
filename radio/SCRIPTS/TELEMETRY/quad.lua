-- quad.lua: telemetry screen for the RadioMaster Pocket (128x64, B&W).
--
-- ArduCopter over ELRS in plain CRSF. Reads the sensors EdgeTX discovers on
-- its own, plus ArduPilot's passthrough frames when the FC sends them
-- (RC_OPTIONS passthrough bit). Never sends anything to the module or the
-- FC. Display only.
--
-- Install: copy to /SCRIPTS/TELEMETRY/quad.lua, then
-- Model > Display > Screen 1 > Script > quad.
--
-- Page 1:
--   +----------------------------------------+
--   | MODE     ARMED / FAILSAFE       00:00  |  title bar
--   | batt   |                  home |  link   |
--   | V, A,  |  attitude      climb |  sats   |
--   | mAh, % |  indicator          |  alt... |
--   +----------------------------------------+
-- Page 2 (scroll to switch): recent FC messages and a status grid.

-- Defaults. /SCRIPTS/QUAD/telem_cfg.lua can override any of these by
-- returning a table, e.g. `return { cells = 3, capacity = 5000 }`.
local cfg = {
  cells = 3,          -- 0 = guess from pack voltage
  capacity = 5000,    -- mAh; the FC's BATT_CAPACITY wins when passthrough sends it
  cellWarn = 3.50,    -- V per cell: voltage blinks
  cellCrit = 3.30,    -- V per cell: voltage inverts
  usedWarn = 80,      -- % of capacity used: mAh blinks
  hdopWarn = 2.0,     -- GPS HDOP above this counts as a bad fix
  terrErr = 5,        -- m: assumed SRTM error, for the "~N" on height above ground
  hdopErr = 2.5,      -- m per unit of HDOP, added to terrErr
  pitchSign = 1,      -- flip to -1 if nose up moves the horizon up
  rollSign = 1,       -- flip to -1 if right roll tilts the horizon the wrong way
  pxPerDeg = 1.5,     -- pitch scale of the attitude indicator
  units = "imperial", -- or "metric": ft, mph, mi vs m, km/h, km
}

local CFG_PATH = "/SCRIPTS/QUAD/telem_cfg.lua"

-- Attitude indicator box.
local ADI_X, ADI_Y, ADI_W, ADI_H = 36, 9, 56, 55
local CX, CY = ADI_X + ADI_W / 2, ADI_Y + ADI_H / 2
local RAD = math.pi / 180

-- Flight state the script keeps itself.
local st = {
  page = 1,
  armed = false,
  armedTicks = 0,     -- 10ms ticks accumulated while armed
  lastTick = 0,
  home = nil,         -- { lat, lon, alt } captured at the first fix after arming
}

-- Sensor lookup. Sensors only exist after EdgeTX discovers them, so a
-- missing one returns nil and is looked up again later.
local ids = {}

local function val(name)
  local id = ids[name]
  if id == nil then
    local info = getFieldInfo(name)
    if info == nil then return nil end
    id = info.id
    ids[name] = id
  end
  return getValue(id)
end

local function num(name)
  local v = val(name)
  if type(v) == "number" then return v end
  return nil
end

local function loadCfg()
  local chunk = loadScript(CFG_PATH)
  if chunk == nil then return end
  local ok, t = pcall(chunk)
  if ok and type(t) == "table" then
    for k, v in pairs(t) do
      if cfg[k] ~= nil and type(v) == type(cfg[k]) then cfg[k] = v end
    end
  end
end

-- Passthrough --------------------------------------------------------------
--
-- ArduPilot wraps FrSky passthrough packets (appid + 32-bit value) in CRSF
-- frame 0x80 (0x7F on old TBS firmware): sub-type 0xF0 holds one packet,
-- 0xF2 several, and 0xF1 a status text. Bit layouts follow
-- libraries/AP_Frsky_Telem/AP_Frsky_SPort_Passthrough.cpp.

local FRESH = 500     -- ticks: passthrough values older than 5 s are ignored
local MAX_MSGS = 4

local pt = {}         -- appid -> { v = value, t = tick }
local ptCapacity = nil
local msgs = {}       -- newest last: { sev = MAV_SEVERITY, text = string }

-- Copter custom_mode -> name, at most 6 characters.
local MODES = {
  [0] = "STAB", "ACRO", "ALTHLD", "AUTO", "GUIDED", "LOITER", "RTL", "CIRCLE",
  nil, "LAND", nil, "DRIFT", nil, "SPORT", "FLIP", "ATUNE", "POSHLD", "BRAKE",
  "THROW", "AVOID", "GNOGPS", "SRTL", "FLOW", "FOLLOW", "ZIGZAG", "SYSID",
  "AROT", "AUTRTL", "TURTLE",
}

local function bits(v, off, n)
  return math.floor(v / 2 ^ off) % 2 ^ n
end

-- Inverse of AP_Frsky_SPort::prep_number: `pw` low bits are a power of ten,
-- the next `nd` bits the digits, and (when signed) the bit above is the sign.
local function unpack(v, nd, pw, signed)
  local n = bits(v, pw, nd) * 10 ^ bits(v, 0, pw)
  if signed and bits(v, nd + pw, 1) == 1 then n = -n end
  return n
end

local function onPacket(appid, v)
  pt[appid] = { v = v, t = getTime() }
  if appid == 0x5007 and bits(v, 24, 8) == 4 then   -- BATT_CAPACITY_1
    ptCapacity = bits(v, 0, 24)
  end
end

local function u32(d, i)
  return d[i] + d[i + 1] * 256 + d[i + 2] * 65536 + d[i + 3] * 16777216
end

local function pollCrsf()
  if crossfireTelemetryPop == nil then return end
  for _ = 1, 10 do
    local cmd, d = crossfireTelemetryPop()
    if cmd == nil then return end
    if (cmd == 0x80 or cmd == 0x7F) and d and d[1] then
      local sub = d[1]
      if sub == 0xF0 and d[7] then
        onPacket(d[2] + d[3] * 256, u32(d, 4))
      elseif sub == 0xF2 and d[2] then
        for i = 0, d[2] - 1 do
          local o = 3 + i * 6
          if d[o + 5] then onPacket(d[o] + d[o + 1] * 256, u32(d, o + 2)) end
        end
      elseif sub == 0xF1 and d[2] then
        local chars = {}
        for i = 3, #d do
          if d[i] == 0 then break end
          chars[#chars + 1] = string.char(d[i])
        end
        msgs[#msgs + 1] = { sev = d[2], text = table.concat(chars) }
        if #msgs > MAX_MSGS then table.remove(msgs, 1) end
      end
    end
  end
end

local function get(appid)
  local p = pt[appid]
  if p and getTime() - p.t < FRESH then return p.v end
  return nil
end

-- 0x5001: mode, armed, failsafes, fence, throttle.
local function ptStatus()
  local v = get(0x5001)
  if v == nil then return nil end
  local thr = bits(v, 19, 6)
  if bits(v, 25, 1) == 1 then thr = -thr end
  return {
    mode = bits(v, 0, 5) - 1,
    flying = bits(v, 7, 1) == 1,
    armed = bits(v, 8, 1) == 1,
    battFs = bits(v, 9, 1) == 1,
    ekfFs = bits(v, 10, 1) == 1,
    fs = bits(v, 12, 1) == 1,
    fence = bits(v, 13, 1) == 1,
    breach = bits(v, 14, 1) == 1,
    thr = thr / 0.63,
  }
end

-- 0x5002: sats, fix (0 no GPS, 1 no fix, 2 2D, 3 3D+), HDOP.
local function ptGps()
  local v = get(0x5002)
  if v == nil then return nil end
  return { sats = bits(v, 0, 4), fix = bits(v, 4, 2),
           hdop = unpack(bits(v, 6, 8), 7, 1) / 10 }
end

-- 0x5004: distance (m), height above home (m), bearing to home (deg).
local function ptHome()
  local v = get(0x5004)
  if v == nil then return nil end
  return { dist = unpack(bits(v, 0, 12), 10, 2),
           alt = unpack(bits(v, 12, 13), 10, 2, true) / 10,
           bearing = bits(v, 25, 7) * 3 }
end

-- 0x5005: vertical speed (m/s, up positive).
local function ptClimb()
  local v = get(0x5005)
  if v == nil then return nil end
  return unpack(bits(v, 0, 9), 7, 1, true) / 10
end

-- 0x500B: height above terrain (m). Only sent while TERRAIN_ENABLE is on.
local function ptTerrain()
  local v = get(0x500B)
  if v == nil then return nil end
  return { agl = unpack(bits(v, 0, 13), 10, 2, true) / 10,
           healthy = bits(v, 13, 1) == 0 }
end

-- 0x5006 bits 21-31: downward rangefinder (m), 0 when there is none.
local function ptRange()
  local v = get(0x5006)
  if v == nil then return nil end
  local r = unpack(bits(v, 21, 11), 10, 1) / 100
  if r > 0 then return r end
  return nil
end

-- Flight state ---------------------------------------------------------------

local function init()
  loadCfg()
  st.lastTick = getTime()
end

-- Telemetry is "up" while the RX is reporting link quality.
local function linkUp()
  local rssi = getRSSI()
  return rssi ~= nil and rssi > 0
end

-- Mode and armed state: from passthrough when fresh, else from the CRSF
-- flight mode string, which ArduPilot ends in '*' while disarmed.
local function flightMode()
  local s = ptStatus()
  if s then return MODES[s.mode] or string.format("M%d", s.mode), s.armed end
  local fm = val("FM")
  if type(fm) ~= "string" or fm == "" then return nil, false end
  if string.sub(fm, -1) == "*" then
    return string.sub(fm, 1, -2), false
  end
  return fm, true
end

-- Short ground distance (m) and bearing (deg) from point 1 to point 2.
local function distance(lat1, lon1, lat2, lon2)
  local x = (lon2 - lon1) * RAD * math.cos((lat1 + lat2) / 2 * RAD)
  local y = (lat2 - lat1) * RAD
  local atan2 = math.atan2 or math.atan
  return math.sqrt(x * x + y * y) * 6371000, atan2(x, y) / RAD % 360
end

local function updateState()
  pollCrsf()
  local now = getTime()
  local armed = st.armed
  -- With no link, keep the last known state: the quad is still flying.
  if linkUp() then
    local _
    _, armed = flightMode()
  end
  if armed then
    st.armedTicks = st.armedTicks + (now - st.lastTick)
    if st.home == nil then
      local gps = val("GPS")
      local sats = num("Sats")
      if type(gps) == "table" and gps.lat and sats and sats >= 6 then
        st.home = { lat = gps.lat, lon = gps.lon, alt = num("Alt") }
      end
    end
  elseif st.armed then
    -- Disarmed: keep the timer, drop home so the next arm sets a new one.
    st.home = nil
  end
  st.armed = armed
  st.lastTick = now
end

-- Home: the FC's when passthrough sends it, else the script's own.
-- Returns distance (m), bearing to home (deg), height above home (m).
local function home(msl)
  local h = ptHome()
  if h then
    local g = ptGps()
    if g and g.fix < 3 then return nil, nil, h.alt end
    return h.dist, h.bearing, h.alt
  end
  if st.home == nil then return nil end
  local dist, brg
  local gps = val("GPS")
  if type(gps) == "table" and gps.lat then
    dist, brg = distance(gps.lat, gps.lon, st.home.lat, st.home.lon)
  end
  local rel = (msl and st.home.alt) and msl - st.home.alt or nil
  return dist, brg, rel
end

local function background()
  updateState()
end

-- Drawing helpers --------------------------------------------------------

local function fmt(f, ...)
  return string.format(f, ...)
end

local function round(v)
  return math.floor(v + 0.5)
end

-- Liang-Barsky: clip segment to the attitude box, nil if outside.
local function clip(x1, y1, x2, y2)
  local xmin, ymin = ADI_X + 1, ADI_Y + 1
  local xmax, ymax = ADI_X + ADI_W - 2, ADI_Y + ADI_H - 2
  local dx, dy = x2 - x1, y2 - y1
  local t0, t1 = 0, 1
  local p = { -dx, dx, -dy, dy }
  local q = { x1 - xmin, xmax - x1, y1 - ymin, ymax - y1 }
  for i = 1, 4 do
    if p[i] == 0 then
      if q[i] < 0 then return nil end
    else
      local t = q[i] / p[i]
      if p[i] < 0 then
        if t > t1 then return nil end
        if t > t0 then t0 = t end
      else
        if t < t0 then return nil end
        if t < t1 then t1 = t end
      end
    end
  end
  return x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy
end

local function line(x1, y1, x2, y2, flags)
  local a, b, c, d = clip(x1, y1, x2, y2)
  if a then
    lcd.drawLine(round(a), round(b), round(c), round(d), SOLID, flags or 0)
  end
end

-- Attitude indicator. In screen coordinates (y down) the ground normal is
-- n = (sin r, cos r) and the horizon runs along h = (cos r, -sin r). A point
-- p is ground when (p - c) . n > pitch * k.
local function drawAttitude(pitchDeg, rollDeg, heading)
  lcd.drawRectangle(ADI_X, ADI_Y, ADI_W, ADI_H, SOLID)
  if pitchDeg == nil or rollDeg == nil then
    lcd.drawText(CX - 11, CY - 3, "NO ATT", SMLSIZE)
    return
  end

  local k = cfg.pxPerDeg
  local s, c = math.sin(rollDeg * RAD), math.cos(rollDeg * RAD)
  local off = pitchDeg * k
  local top, bot = ADI_Y + 1, ADI_Y + ADI_H - 2

  -- Ground: every other column, so it reads as grey on a 1-bit screen.
  for x = ADI_X + 1, ADI_X + ADI_W - 2, 2 do
    local dx = x - CX
    local y1, y2
    if c > 0.02 then
      y1, y2 = CY + (off - dx * s) / c, bot
    elseif c < -0.02 then
      y1, y2 = top, CY + (off - dx * s) / c
    elseif dx * s > off then
      y1, y2 = top, bot
    end
    if y1 then
      if y1 < top then y1 = top end
      if y2 > bot then y2 = bot end
      if y2 >= y1 then
        lcd.drawLine(x, round(y1), x, round(y2), SOLID, 0)
      end
    end
  end

  -- Horizon and pitch ladder (every 10 degrees, short rungs).
  local function rung(deg, half)
    local d = (pitchDeg - deg) * k
    local px, py = CX + d * s, CY + d * c
    line(px - half * c, py + half * s, px + half * c, py - half * s,
         deg < 0 and ERASE or 0)
  end
  rung(0, 60)
  for deg = -30, 30, 10 do
    if deg ~= 0 then rung(deg, (deg % 20 == 0) and 8 or 4) end
  end

  -- Fixed aircraft symbol: wings and a centre dot, with an erased outline
  -- so it stays visible over the ground stripes.
  lcd.drawFilledRectangle(CX - 14, CY - 1, 10, 3, ERASE)
  lcd.drawFilledRectangle(CX + 5, CY - 1, 10, 3, ERASE)
  lcd.drawFilledRectangle(CX - 2, CY - 2, 5, 5, ERASE)
  lcd.drawLine(CX - 13, CY, CX - 5, CY, SOLID, 0)
  lcd.drawLine(CX + 5, CY, CX + 13, CY, SOLID, 0)
  lcd.drawFilledRectangle(CX - 1, CY - 1, 3, 3, 0)

  -- Roll and heading readouts, on erased tags so they read over the ground.
  lcd.drawFilledRectangle(ADI_X + 1, ADI_Y + 1, 15, 7, ERASE)
  lcd.drawText(ADI_X + 2, ADI_Y + 2, fmt("%d", round(rollDeg)), SMLSIZE)
  if heading then
    lcd.drawFilledRectangle(CX - 7, ADI_Y + ADI_H - 9, 15, 8, 0)
    lcd.drawText(CX - 6, ADI_Y + ADI_H - 8, fmt("%03d", round(heading) % 360),
                 SMLSIZE + INVERS)
  end
end

-- Arrow pointing home relative to the nose, top right of the attitude box.
local function drawHomeArrow(rel)
  local x0, y0, r = ADI_X + ADI_W - 9, ADI_Y + 8, 5
  lcd.drawFilledRectangle(x0 - 7, y0 - 7, 15, 15, ERASE)
  lcd.drawRectangle(x0 - 7, y0 - 7, 15, 15, SOLID)
  local s, c = math.sin(rel * RAD), math.cos(rel * RAD)
  local hx, hy = x0 + r * s, y0 - r * c
  lcd.drawLine(round(x0 - r * s), round(y0 + r * c), round(hx), round(hy), SOLID, 0)
  for _, a in ipairs({ rel + 145, rel - 145 }) do
    lcd.drawLine(round(hx), round(hy), round(hx + 4 * math.sin(a * RAD)),
                 round(hy - 4 * math.cos(a * RAD)), SOLID, 0)
  end
end

-- Climb rate bar on the right edge of the attitude box, full scale 5 m/s.
local function drawClimb(vs)
  local x, top, h = ADI_X + ADI_W - 6, ADI_Y + 17, ADI_H - 28
  local mid = top + math.floor(h / 2)
  lcd.drawFilledRectangle(x - 1, top, 6, h, ERASE)
  lcd.drawLine(x - 1, mid, x + 4, mid, SOLID, 0)
  local len = round(math.max(-1, math.min(1, vs / 5)) * h / 2)
  if len > 0 then
    lcd.drawFilledRectangle(x, mid - len, 4, len, 0)
  elseif len < 0 then
    lcd.drawFilledRectangle(x, mid + 1, 4, -len, 0)
  end
end

-- Most urgent FC alert for the title bar, or nil.
local function alert(s)
  if s == nil then return nil end
  if s.breach then return "FENCE" end
  if s.battFs then return "BATT FS" end
  if s.ekfFs then return "EKF" end
  if s.fs then return "FS" end
  return nil
end

local function drawTitle(mode, armed, up)
  lcd.drawFilledRectangle(0, 0, LCD_W, 8, 0)
  lcd.drawText(1, 0, mode or "----", INVERS)
  local a = up and alert(ptStatus())
  if a then
    -- Black text on a white tag inside the black bar.
    lcd.drawFilledRectangle(44, 0, #a * 6 + 3, 8, ERASE)
    lcd.drawText(46, 0, a, BLINK)
  else
    local state = (not up) and "NO TLM" or (armed and "ARMED" or "DISARM")
    lcd.drawText(46, 0, state, INVERS + ((not up or armed) and BLINK or 0))
  end
  local secs = math.floor(st.armedTicks / 100)
  lcd.drawText(LCD_W - 1, 0, fmt("%02d:%02d", math.floor(secs / 60), secs % 60),
               INVERS + RIGHT)
end

local function drawBattery()
  local x = 0
  local v = num("RxBt")
  local a = num("Curr")
  local mah = num("Capa")
  local capacity = (ptCapacity and ptCapacity > 0) and ptCapacity or cfg.capacity

  local cells = cfg.cells
  if cells == 0 and v and v > 1 then cells = math.ceil(v / 4.35) end
  local cell = (v and cells > 0) and v / cells or nil

  local vFlags = 0
  if cell and cell < cfg.cellCrit then
    vFlags = INVERS
  elseif cell and cell < cfg.cellWarn then
    vFlags = BLINK
  end
  lcd.drawText(x, 10, v and fmt("%.1fV", v) or "--.-V", vFlags)
  lcd.drawText(x, 19, cell and fmt("%.2f/c", cell) or "-.--/c", SMLSIZE)
  lcd.drawText(x, 26, a and fmt("%.1fA", a) or "--.-A", SMLSIZE)

  local used = nil
  if mah and capacity > 0 then used = mah / capacity * 100 end
  lcd.drawText(x, 33, mah and fmt("%dmAh", math.floor(mah)) or "----mAh",
               SMLSIZE + ((used and used >= cfg.usedWarn) and BLINK or 0))

  -- Remaining: from mAh used against the pack size, else the FC's Bat%.
  local pct = used and 100 - used or num("Bat%")
  lcd.drawRectangle(x, 42, 32, 8, SOLID)
  lcd.drawFilledRectangle(x + 32, 44, 2, 4, 0)
  if pct then
    if pct < 0 then pct = 0 elseif pct > 100 then pct = 100 end
    local w = round(30 * pct / 100)
    if w > 0 then lcd.drawFilledRectangle(x + 1, 43, w, 6, 0) end
    lcd.drawText(x, 52, fmt("%d%%", round(pct)), 0)
  else
    lcd.drawText(x, 52, "--%", 0)
  end
end

local FIX = { [0] = "--", "NF", "2D", "3D" }

local function drawStats(up)
  local x, xr = 94, LCD_W - 1
  local rows = {}

  -- EdgeTX reports CRSF altitude in m and ground speed in km/h.
  local imp = cfg.units ~= "metric"
  local function h(v) return v and fmt("%d", round(imp and v * 3.28084 or v)) or "--" end

  local rq = num("RQly")
  rows[#rows + 1] = { "RQ", rq and fmt("%d", math.floor(rq)) or "--",
                      (rq and rq < 70) and BLINK or 0 }

  -- Sats; the fix type only shows (inverted) when it is bad.
  local sats = num("Sats")
  local g = ptGps()
  if sats == nil and g then sats = g.sats end
  local s, sf = sats and fmt("%d", math.floor(sats)) or "--", 0
  if g and (g.fix < 3 or g.hdop > cfg.hdopWarn) then
    s, sf = fmt("%s %s", s, FIX[g.fix]), INVERS
  elseif sats and sats < 6 then
    sf = BLINK
  end
  rows[#rows + 1] = { "Sat", s, sf }

  local msl = num("Alt")
  local dist, _, rel = home(msl)
  local d = "--"
  if dist and imp then
    local ft = dist * 3.28084
    d = ft < 5280 and fmt("%dft", round(ft)) or fmt("%.1fmi", ft / 5280)
  elseif dist then
    d = dist < 1000 and fmt("%dm", round(dist)) or fmt("%.1fkm", dist / 1000)
  end
  rows[#rows + 1] = { "Hm", d, 0 }

  -- Height: above the ground under the quad, with a rough error, when the
  -- FC has terrain data (or a rangefinder); else above home / above sea level.
  local agl, err = ptRange(), 0.1
  if agl == nil then
    local t = ptTerrain()
    if t and t.healthy then
      agl, err = t.agl, cfg.terrErr + cfg.hdopErr * (g and g.hdop or 1)
    end
  end
  local a
  if agl then
    a = h(agl) .. "~" .. h(math.max(err, imp and 0.31 or 1))
  elseif rel or msl then
    a = h(rel) .. "/" .. h(msl)
  else
    a = "--"
  end
  rows[#rows + 1] = { "A", a, 0 }

  local spd = num("GSpd")
  if spd and imp then spd = spd * 0.621371 end
  rows[#rows + 1] = { imp and "mph" or "kmh", spd and fmt("%d", round(spd)) or "--", 0 }

  local pwr = num("TPWR")
  rows[#rows + 1] = { "Pwr", pwr and fmt("%d", math.floor(pwr)) or "--", 0 }

  for i, r in ipairs(rows) do
    local y = 3 + i * 8
    lcd.drawText(x, y, r[1], SMLSIZE)
    lcd.drawText(xr, y, r[2], SMLSIZE + RIGHT + (up and r[3] or 0))
  end
end

-- Page 2: recent FC messages, then a status grid.
local function drawPage2()
  for i, m in ipairs(msgs) do
    -- Warnings and worse (MAV_SEVERITY 0-4) are inverted.
    lcd.drawText(1, 3 + i * 8, string.sub(m.text, 1, 31),
                 SMLSIZE + (m.sev <= 4 and INVERS or 0))
  end
  if #msgs == 0 then lcd.drawText(1, 11, "No FC messages", SMLSIZE) end
  lcd.drawLine(0, 42, LCD_W - 1, 42, SOLID, 0)

  local s, g, t = ptStatus(), ptGps(), ptTerrain()
  local function yn(b, yes, no) if s == nil then return "--" end return b and yes or no end
  local terr = "--"
  if t then terr = t.healthy and "ok" or "bad" end
  local cells = {
    { "EKF", yn(s and s.ekfFs, "BAD", "ok"), s and s.ekfFs },
    { "Fence", s and (s.breach and "BRCH" or (s.fence and "on" or "off")) or "--",
      s and s.breach },
    { "GPS", g and fmt("%s %.1f", FIX[g.fix], g.hdop) or "--",
      g and (g.fix < 3 or g.hdop > cfg.hdopWarn) },
    { "Thr", s and fmt("%d%%", round(s.thr)) or "--" },
    { "Terr", terr, t and not t.healthy },
    { "Air", yn(s and s.flying, "fly", "gnd") },
  }
  for i, c in ipairs(cells) do
    local x = ((i - 1) % 2) * 66
    local y = 45 + math.floor((i - 1) / 2) * 7
    lcd.drawText(x, y, c[1], SMLSIZE)
    lcd.drawText(x + 61, y, c[2], SMLSIZE + RIGHT + (c[3] and INVERS or 0))
  end
end

local function isEvent(event, ...)
  for _, e in ipairs({ ... }) do
    if e ~= nil and event == e then return true end
  end
  return false
end

local function run(event)
  updateState()
  lcd.clear()

  -- Scroll switches pages; long ENTER resets the flight timer.
  if isEvent(event, EVT_VIRTUAL_NEXT, EVT_VIRTUAL_PREV, EVT_ROT_RIGHT, EVT_ROT_LEFT) then
    st.page = 3 - st.page
  elseif isEvent(event, EVT_ENTER_LONG, EVT_VIRTUAL_ENTER_LONG) then
    st.armedTicks = 0
  end

  local up = linkUp()
  local mode = flightMode()
  drawTitle(mode, st.armed, up)
  if st.page == 2 then
    drawPage2()
    return 0
  end
  drawBattery()

  -- EdgeTX reports CRSF attitude in radians.
  local p, r, y = num("Ptch"), num("Roll"), num("Yaw")
  if p then p = p / RAD * cfg.pitchSign end
  if r then r = r / RAD * cfg.rollSign end
  -- Prefer the FC's yaw; GPS course over ground is noise in a hover.
  local hdg = y and (y / RAD) % 360 or num("Hdg")
  drawAttitude(p, r, hdg)

  local dist, brg = home(num("Alt"))
  if p and r and hdg and dist and brg and dist >= 2 then drawHomeArrow(brg - hdg) end
  local vs = ptClimb() or num("VSpd")
  if p and r and vs then drawClimb(vs) end

  drawStats(up)
  return 0
end

return { init = init, background = background, run = run }
