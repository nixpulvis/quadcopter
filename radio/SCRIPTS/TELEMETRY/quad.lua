-- quad.lua: telemetry screen for the RadioMaster Pocket (128x64, B&W).
--
-- ArduCopter over ELRS in plain CRSF. Reads only the sensors EdgeTX
-- discovers on its own (no passthrough), and never sends anything to the
-- module or the FC. Display only.
--
-- Install: copy to /SCRIPTS/TELEMETRY/quad.lua, then
-- Model > Display > Screen 1 > Script > quad.
--
-- Layout:
--   +----------------------------------------+
--   | MODE        ARMED               00:00  |  title bar
--   | batt   |                     |  link   |
--   | V, A,  |  attitude indicator |  sats   |
--   | mAh, % |                     |  alt... |
--   +----------------------------------------+

-- Defaults. /SCRIPTS/QUAD/telem_cfg.lua can override any of these by
-- returning a table, e.g. `return { cells = 3, capacity = 5000 }`.
local cfg = {
  cells = 3,          -- 0 = guess from pack voltage
  capacity = 5000,    -- mAh
  cellWarn = 3.50,    -- V per cell: voltage blinks
  cellCrit = 3.30,    -- V per cell: voltage inverts
  usedWarn = 80,      -- % of capacity used: mAh blinks
  pitchSign = 1,      -- flip to -1 if nose up moves the horizon up
  rollSign = 1,       -- flip to -1 if right roll tilts the horizon the wrong way
  pxPerDeg = 1.5,     -- pitch scale of the attitude indicator
}

local CFG_PATH = "/SCRIPTS/QUAD/telem_cfg.lua"

-- Attitude indicator box.
local ADI_X, ADI_Y, ADI_W, ADI_H = 36, 9, 56, 55
local CX, CY = ADI_X + ADI_W / 2, ADI_Y + ADI_H / 2
local RAD = math.pi / 180

-- Flight state the script keeps itself.
local st = {
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

local function init()
  loadCfg()
  st.lastTick = getTime()
end

-- Telemetry is "up" while the RX is reporting link quality.
local function linkUp()
  local rssi = getRSSI()
  return rssi ~= nil and rssi > 0
end

-- ArduPilot's CRSF flight mode string ends in '*' while disarmed.
local function flightMode()
  local fm = val("FM")
  if type(fm) ~= "string" or fm == "" then return nil, false end
  if string.sub(fm, -1) == "*" then
    return string.sub(fm, 1, -2), false
  end
  return fm, true
end

-- Short ground distance between two lat/lon points, in metres.
local function distance(lat1, lon1, lat2, lon2)
  local x = (lon2 - lon1) * RAD * math.cos((lat1 + lat2) / 2 * RAD)
  local y = (lat2 - lat1) * RAD
  return math.sqrt(x * x + y * y) * 6371000
end

local function updateState()
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

local function background()
  updateState()
end

-- Drawing helpers --------------------------------------------------------

local function fmt(f, ...)
  return string.format(f, ...)
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
    lcd.drawLine(math.floor(a + 0.5), math.floor(b + 0.5),
                 math.floor(c + 0.5), math.floor(d + 0.5), SOLID, flags or 0)
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
        lcd.drawLine(x, math.floor(y1 + 0.5), x, math.floor(y2 + 0.5), SOLID, 0)
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
  local r = fmt("%d", math.floor(rollDeg + 0.5))
  lcd.drawFilledRectangle(ADI_X + 1, ADI_Y + 1, 15, 7, ERASE)
  lcd.drawText(ADI_X + 2, ADI_Y + 2, r, SMLSIZE)
  if heading then
    local h = fmt("%03d", math.floor(heading + 0.5) % 360)
    lcd.drawFilledRectangle(CX - 7, ADI_Y + ADI_H - 9, 15, 8, 0)
    lcd.drawText(CX - 6, ADI_Y + ADI_H - 8, h, SMLSIZE + INVERS)
  end
end

local function drawTitle(mode, armed, up)
  lcd.drawFilledRectangle(0, 0, LCD_W, 8, 0)
  lcd.drawText(1, 0, mode or "----", INVERS)
  local state
  if not up then
    state = "NO TLM"
  elseif armed then
    state = "ARMED"
  else
    state = "DISARM"
  end
  lcd.drawText(46, 0, state, INVERS + ((not up or armed) and BLINK or 0))
  local secs = math.floor(st.armedTicks / 100)
  lcd.drawText(LCD_W - 1, 0, fmt("%02d:%02d", math.floor(secs / 60), secs % 60),
               INVERS + RIGHT)
end

local function drawBattery()
  local x = 0
  local v = num("RxBt")
  local a = num("Curr")
  local mah = num("Capa")

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
  if mah and cfg.capacity > 0 then used = mah / cfg.capacity * 100 end
  lcd.drawText(x, 33, mah and fmt("%dmAh", math.floor(mah)) or "----mAh",
               SMLSIZE + ((used and used >= cfg.usedWarn) and BLINK or 0))

  -- Remaining: from mAh used against the pack size, else the FC's Bat%.
  local pct = used and 100 - used or num("Bat%")
  lcd.drawRectangle(x, 42, 32, 8, SOLID)
  lcd.drawFilledRectangle(x + 32, 44, 2, 4, 0)
  if pct then
    if pct < 0 then pct = 0 elseif pct > 100 then pct = 100 end
    local w = math.floor(30 * pct / 100 + 0.5)
    if w > 0 then lcd.drawFilledRectangle(x + 1, 43, w, 6, 0) end
    lcd.drawText(x, 52, fmt("%d%%", math.floor(pct + 0.5)), 0)
  else
    lcd.drawText(x, 52, "--%", 0)
  end
end

local function drawStats(up)
  local x, xr = 94, LCD_W - 1
  local rows = {}

  local rq = num("RQly")
  rows[#rows + 1] = { "RQ", rq and fmt("%d", math.floor(rq)) or "--",
                      (rq and rq < 70) and BLINK or 0 }

  local sats = num("Sats")
  rows[#rows + 1] = { "Sat", sats and fmt("%d", math.floor(sats)) or "--",
                      (sats and sats < 6) and BLINK or 0 }

  -- Height above the arming point / GPS altitude above sea level.
  local msl = num("Alt")
  local rel = nil
  if msl and st.home and st.home.alt then rel = msl - st.home.alt end
  local function m(v) return v and fmt("%d", math.floor(v + 0.5)) or "--" end
  rows[#rows + 1] = { "A", (rel or msl) and m(rel) .. "/" .. m(msl) or "--", 0 }

  local spd = num("GSpd")
  rows[#rows + 1] = { "Spd", spd and fmt("%d", math.floor(spd + 0.5)) or "--", 0 }

  local dist = nil
  local gps = val("GPS")
  if st.home and type(gps) == "table" and gps.lat then
    dist = distance(st.home.lat, st.home.lon, gps.lat, gps.lon)
  end
  rows[#rows + 1] = { "Hm", dist and fmt("%dm", math.floor(dist + 0.5)) or "--", 0 }

  local pwr = num("TPWR")
  rows[#rows + 1] = { "Pwr", pwr and fmt("%d", math.floor(pwr)) or "--", 0 }

  for i, r in ipairs(rows) do
    local y = 3 + i * 8
    lcd.drawText(x, y, r[1], SMLSIZE)
    lcd.drawText(xr, y, r[2], SMLSIZE + RIGHT + (up and r[3] or 0))
  end
end

local function run(event)
  updateState()
  lcd.clear()

  local up = linkUp()
  local mode = flightMode()
  drawTitle(mode, st.armed, up)
  drawBattery()

  -- EdgeTX reports CRSF attitude in radians.
  local p, r, y = num("Ptch"), num("Roll"), num("Yaw")
  if p then p = p / RAD * cfg.pitchSign end
  if r then r = r / RAD * cfg.rollSign end
  -- Prefer the FC's yaw; GPS course over ground is noise in a hover.
  local hdg = y and (y / RAD) % 360 or num("Hdg")
  drawAttitude(p, r, hdg)

  drawStats(up)

  -- Long ENTER resets the flight timer.
  if event == EVT_ENTER_LONG then st.armedTicks = 0 end
  return 0
end

return { init = init, background = background, run = run }
