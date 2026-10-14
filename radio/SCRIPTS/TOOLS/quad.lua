-- TNS|Quad ELRS|TNE
-- Shows what the qelrs boot script did with each ELRS setting, and lets you
-- drop hand-made overrides so quad.yaml wins again (ENTER).

local function line(y, text, flags)
  lcd.drawText(0, y, text, flags or 0)
end

local function init() end

local function run(event)
  lcd.clear()
  line(0, "Quad ELRS", INVERS)
  local q = quadElrs
  if q == nil then
    line(10, "Boot script not running.")
    line(20, "Add Special Function:")
    line(30, "ON > Lua Script > qelrs")
    return event == EVT_VIRTUAL_EXIT and 1 or 0
  end
  line(10, q.message or "")
  local y = 20
  for _, k in ipairs(q.order or {}) do
    local st = (q.status or {})[k] or "?"
    local f = (q.fields or {})[k]
    local text = k .. ": " .. (f and f.value or "-")
    if st == "override" then text = text .. " (cfg " .. q.desired[k] .. ")" end
    if st ~= "sync" and st ~= "override" then text = text .. " " .. st end
    line(y, text, st == "sync" and 0 or BLINK)
    y = y + 8
  end
  if event == EVT_VIRTUAL_ENTER and q.phase == "idle" then
    q.reapply = true
  end
  if event == EVT_VIRTUAL_EXIT then return 1 end
  return 0
end

return { init = init, run = run }
