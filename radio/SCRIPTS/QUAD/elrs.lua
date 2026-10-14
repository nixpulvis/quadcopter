-- quadctl ELRS core: applies SCRIPTS/QUAD/elrs.cfg to the internal ELRS
-- module over CRSF parameter frames, the same frames the stock ExpressLRS
-- Lua uses (0x28 ping, 0x29 device info, 0x2C read, 0x2B entry, 0x2D write,
-- 0x2E status). Loaded by SCRIPTS/FUNCTIONS/qelrs.lua; status is shared with
-- the Tools page through the global table `quadElrs`.
--
-- Per field it compares desired D (elrs.cfg), last applied S (state.txt) and
-- actual A (module):
--   A == D            in sync, no write
--   A == S, D ~= S    config changed: write D
--   A ~= S, A ~= D    changed by hand on the radio: leave it, report override
--   no S yet          first run: write D
-- It only writes while no receiver is linked, and goes idle when done so it
-- stops reading the shared CRSF queue (the telemetry screen needs it).

local DIR = "/SCRIPTS/QUAD/"
local CFG = DIR .. "elrs.cfg"
local STATE = DIR .. "state.txt"

local TX = 0xEE
local HANDSET = 0xEF

local T_SELECT = 9
local T_FOLDER = 11
local T_INFO = 12

local M = {}

local function readFile(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local chunks = {}
  while true do
    local s = io.read(f, 256)
    if s == nil or #s == 0 then break end
    chunks[#chunks + 1] = s
  end
  io.close(f)
  return table.concat(chunks)
end

local function parseKV(text)
  local out, order = {}, {}
  if not text then return out, order end
  for line in string.gmatch(text, "[^\n]+") do
    local k, v = string.match(line, "^%s*([^=]-)%s*=%s*(.-)%s*$")
    if k and k ~= "" then
      if out[k] == nil then order[#order + 1] = k end
      out[k] = v
    end
  end
  return out, order
end

local function readString(data, offset)
  local chars = {}
  while data[offset] ~= nil and data[offset] ~= 0 do
    chars[#chars + 1] = string.char(data[offset])
    offset = offset + 1
  end
  return table.concat(chars), offset + 1
end

local function splitOptions(s)
  local opts = {}
  local start = 1
  while true do
    local i = string.find(s, ";", start, true)
    if not i then
      opts[#opts + 1] = string.sub(s, start)
      break
    end
    opts[#opts + 1] = string.sub(s, start, i - 1)
    start = i + 1
  end
  return opts
end

local function be(data, offset, size)
  local v = 0
  for i = 0, size - 1 do v = v * 256 + (data[offset + i] or 0) end
  return v
end

-- Parse a complete parameter entry payload (after id and chunk count).
function M.parseField(id, p)
  local f = { id = id, parent = p[1], type = (p[2] or 0) % 128, hidden = (p[2] or 0) >= 128 }
  local off
  f.name, off = readString(p, 3)
  if f.type == T_SELECT then
    local opts
    opts, off = readString(p, off)
    f.options = splitOptions(opts)
    f.index = p[off]
    f.value = f.options[(f.index or 0) + 1]
  elseif f.type <= 3 then
    local size = math.floor(f.type / 2) + 1
    f.index = be(p, off, size)
    f.value = tostring(f.index)
  elseif f.type == T_INFO then
    f.value = readString(p, off)
  end
  return f
end

function M.new(now)
  local s = {
    phase = "wait_module",
    timer = 0,
    tries = 0,
    fields = {},       -- by name
    fieldCount = 0,
    loadQueue = {},
    chunk = 0,
    buf = nil,
    writes = {},
    message = "waiting for ELRS module",
    status = {},       -- label -> "sync" | "pending" | "override" | "error: ..."
    version = nil,
    linked = nil,
  }
  local cfg, order = parseKV(readFile(CFG))
  s.reset = cfg.reset
  cfg.reset = nil
  s.desired, s.order = {}, {}
  for _, k in ipairs(order) do
    if k ~= "reset" then
      s.desired[k] = cfg[k]
      s.order[#s.order + 1] = k
    end
  end
  local st = parseKV(readFile(STATE))
  s.applied = {}
  for k, v in pairs(st) do
    local key = string.match(k, "^applied%.(.*)$")
    if key then s.applied[key] = v end
  end
  if st.reset ~= s.reset then
    s.applied = {}  -- reset token changed: forget overrides, config wins
  end
  return s
end

local function saveState(s)
  local f = io.open(STATE, "w")
  if not f then return end
  io.write(f, "reset=" .. (s.reset or "0") .. "\n")
  if s.version then io.write(f, "tx_version=" .. s.version .. "\n") end
  for _, k in ipairs(s.order) do
    local fld = s.fields[k]
    if s.applied[k] then io.write(f, "applied." .. k .. "=" .. s.applied[k] .. "\n") end
    if fld and fld.value then io.write(f, "actual." .. k .. "=" .. fld.value .. "\n") end
    if s.status[k] == "override" then io.write(f, "override." .. k .. "=" .. fld.value .. "\n") end
  end
  io.close(f)
end

local function requestNext(s, now)
  local id = s.loadQueue[#s.loadQueue]
  crossfireTelemetryPush(0x2C, { TX, HANDSET, id, s.chunk })
  s.timer = now + 100
end

local function startLoad(s, now, ids)
  s.loadQueue = {}
  for i = #ids, 1, -1 do s.loadQueue[#s.loadQueue + 1] = ids[i] end
  s.chunk, s.buf, s.tries = 0, nil, 0
  if #s.loadQueue > 0 then requestNext(s, now) end
end

local function onDeviceInfo(s, data, now)
  if data[2] ~= TX then return end
  local name, off = readString(data, 3)
  s.moduleName = name
  s.isElrs = be(data, off, 4) == 0x454C5253
  s.version = string.format("%d.%d.%d", data[off + 9] or 0, data[off + 10] or 0, data[off + 11] or 0)
  s.fieldCount = data[off + 12] or 0
  if s.phase == "wait_module" then
    if not s.isElrs then
      s.phase, s.message = "error", "internal module isn't ExpressLRS"
      return
    end
    s.phase = "load"
    s.message = "reading ELRS settings"
    local ids = {}
    for i = 1, s.fieldCount do ids[#ids + 1] = i end
    startLoad(s, now, ids)
  end
end

local function onEntry(s, data, now)
  local id = s.loadQueue[#s.loadQueue]
  if data[2] ~= TX or data[3] ~= id then return end
  local remain = data[4]
  s.buf = s.buf or {}
  for i = 5, #data do s.buf[#s.buf + 1] = data[i] end
  if remain > 0 then
    s.chunk = s.chunk + 1
    requestNext(s, now)
    return
  end
  local f = M.parseField(id, s.buf)
  if s.fields[f.name] == nil or s.fields[f.name].id == id then
    s.fields[f.name] = f
  end
  s.loadQueue[#s.loadQueue] = nil
  s.chunk, s.buf, s.tries = 0, nil, 0
  if #s.loadQueue > 0 then requestNext(s, now) end
end

local function onStatus(s, data)
  if data[2] ~= TX then return end
  s.linked = (data[6] or 0) % 2 == 1
end

local function indexOf(options, text)
  for i, o in ipairs(options) do
    if o == text then return i - 1 end
  end
  return nil
end

-- Decide what to write. Returns true if anything needs writing.
function M.compare(s)
  s.writes = {}
  local overrides, errors = 0, 0
  for _, k in ipairs(s.order) do
    local want = s.desired[k]
    local f = s.fields[k]
    if f == nil then
      if k == "Link Mode" then
        s.status[k] = "sync"   -- field only exists on ELRS 3.5+; older is always normal CRSF
      else
        s.status[k] = "error: no field " .. k
        errors = errors + 1
      end
    elseif f.type ~= T_SELECT and f.type > 3 then
      s.status[k] = "error: " .. k .. " isn't settable"
      errors = errors + 1
    else
      local idx = (f.type == T_SELECT) and indexOf(f.options, want) or tonumber(want)
      if idx == nil then
        s.status[k] = "error: unknown option " .. want
        errors = errors + 1
      elseif f.value == want then
        s.status[k] = "sync"
        s.applied[k] = want
      elseif s.applied[k] == nil or s.applied[k] == f.value then
        s.status[k] = "pending"
        s.writes[#s.writes + 1] = { field = f, index = idx, value = want, key = k }
      else
        s.status[k] = "override"
        overrides = overrides + 1
      end
    end
  end
  s.overrides, s.errors = overrides, errors
  return #s.writes > 0
end

local function summary(s)
  if s.errors > 0 then return "ELRS: " .. s.errors .. " setting(s) not applied" end
  if s.overrides > 0 then return "ELRS overridden: " .. s.overrides .. " setting(s)" end
  return "ELRS settings in sync"
end

local function publish(s)
  quadElrs = quadElrs or {}
  quadElrs.phase = s.phase
  quadElrs.message = s.message
  quadElrs.status = s.status
  quadElrs.order = s.order
  quadElrs.desired = s.desired
  quadElrs.fields = s.fields
  quadElrs.version = s.version
end

-- One non-blocking step. Call from run(); `now` is getTime() (10 ms ticks).
function M.step(s, now)
  if s.phase ~= "idle" and s.phase ~= "error" then
    while true do
      local cmd, data = crossfireTelemetryPop()
      if cmd == nil then break end
      if cmd == 0x29 then onDeviceInfo(s, data, now)
      elseif cmd == 0x2B then onEntry(s, data, now)
      elseif cmd == 0x2E then onStatus(s, data)
      end
    end
  end

  local p = s.phase
  if p == "wait_module" then
    if now >= s.timer then
      crossfireTelemetryPush(0x28, { 0x00, HANDSET })
      s.timer = now + 100
    end
  elseif p == "load" or p == "reload" then
    if #s.loadQueue == 0 then
      if p == "load" then
        if M.compare(s) then
          s.phase, s.linked, s.timer = "check_link", nil, 0
          s.message = "ELRS changes pending"
        else
          s.phase, s.message = "idle", summary(s)
          saveState(s)
        end
      else
        M.compare(s)
        for _, w in ipairs(s.lastWrites or {}) do
          if s.fields[w.key] and s.fields[w.key].value == w.value then s.applied[w.key] = w.value end
        end
        s.phase, s.message = "idle", summary(s)
        saveState(s)
      end
    elseif now >= s.timer then
      s.tries = s.tries + 1
      if s.tries > 5 then
        s.phase, s.message = "error", "ELRS module stopped answering"
      else
        requestNext(s, now)
      end
    end
  elseif p == "check_link" then
    if s.linked == true then
      s.message = "ELRS changes pending: power the quad off"
      s.linked = nil
    elseif s.linked == false then
      s.phase = "write"
    end
    if s.phase == "check_link" and now >= s.timer then
      s.statusTries = (s.statusTries or 0) + 1
      if s.statusTries > 5 and getRSSI ~= nil then
        -- No 0x2E status from this module: fall back to EdgeTX's link RSSI.
        if getRSSI() == 0 then s.phase = "write" else s.message = "ELRS changes pending: power the quad off" end
      end
      crossfireTelemetryPush(0x2D, { TX, HANDSET, 0x00, 0x00 })  -- request status (0x2E)
      s.timer = now + 100
    end
  elseif p == "write" then
    for _, w in ipairs(s.writes) do
      crossfireTelemetryPush(0x2D, { TX, HANDSET, w.field.id, w.index })
    end
    s.lastWrites = s.writes
    s.phase, s.timer = "settle", now + 50
    s.message = "writing ELRS settings"
  elseif p == "settle" then
    if now >= s.timer then
      local ids = {}
      for _, w in ipairs(s.lastWrites) do ids[#ids + 1] = w.field.id end
      s.phase = "reload"
      startLoad(s, now, ids)
    end
  elseif p == "idle" then
    if quadElrs and quadElrs.reapply then
      -- Tools page asked to drop overrides: config wins again.
      quadElrs.reapply = nil
      for k, st in pairs(s.status) do
        if st == "override" then s.applied[k] = s.fields[k].value end
      end
      s.phase = "load"
      local ids = {}
      for i = 1, s.fieldCount do ids[#ids + 1] = i end
      startLoad(s, now, ids)
    end
  end
  publish(s)
  return s
end

return M
