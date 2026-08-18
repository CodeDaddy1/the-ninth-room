--[[
Curated Bridge — file-spool command executor for the Curated Curiosities pipeline.

Why this exists: the free edition of DaVinci Resolve refuses external scripting
connections (verified 2026-08-18: fusionscript.so and fuscript both return nil
from outside the app). Scripts started from INSIDE Resolve get full API access,
so this script is the pipeline's only door into Resolve.

How it works: run it once per Resolve session from Workspace > Scripts >
Curated Bridge. It loops forever, executing Lua command files the external
pipeline drops into work/_bridge/inbox/ (in filename order), and writes each
command's result to work/_bridge/outbox/<name>.result ("OK\n<value>" or
"ERROR\n<message>"). Executed commands move to done/. A heartbeat timestamp is
written to bridge.alive every loop so the outside can tell the bridge is up.

Stop it by creating the file work/_bridge/stop, or by quitting Resolve.

What breaks if this is wrong: the pipeline can analyze footage and plan the
edit, but nothing ever reaches a Resolve timeline or the render queue.
--]]

local HOME = os.getenv("HOME")
local SPOOL = HOME .. "/Projects/curated-curiosities/work/_bridge"
os.execute('mkdir -p "' .. SPOOL .. '/inbox" "' .. SPOOL .. '/outbox" "' .. SPOOL .. '/done"')

resolve = resolve or Resolve()

local function write_file(path, text)
  local f = io.open(path, "w")
  if f then
    f:write(text)
    f:close()
  end
end

local function list_inbox()
  local names = {}
  local p = io.popen('ls "' .. SPOOL .. '/inbox" 2>/dev/null')
  if p then
    for line in p:lines() do
      if line:match("%.lua$") then
        table.insert(names, line)
      end
    end
    p:close()
  end
  table.sort(names)
  return names
end

-- Single-instance guard: the Scripts menu runs this file as an external
-- fuscript process that can OUTLIVE Resolve itself (verified 2026-08-18: an
-- orphaned bridge from a quit Resolve kept stealing commands it could no
-- longer execute). Each new bridge claims ownership; older instances notice
-- and exit. A dead resolve handle also self-exits.
math.randomseed(os.time())
local OWNER = tostring(os.time()) .. "-" .. tostring(math.random(1, 1e9))
write_file(SPOOL .. "/bridge.owner", OWNER)

local function read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local v = f:read("*a")
  f:close()
  return v
end

write_file(SPOOL .. "/bridge.alive", tostring(os.time()))
print("[curated-bridge] up — spool: " .. SPOOL .. " owner: " .. OWNER)

local ticks = 0
while true do
  local stopf = io.open(SPOOL .. "/stop", "r")
  if stopf then
    stopf:close()
    os.remove(SPOOL .. "/stop")
    break
  end
  if read_file(SPOOL .. "/bridge.owner") ~= OWNER then
    print("[curated-bridge] newer bridge took over — exiting")
    return
  end
  ticks = ticks + 1
  if ticks % 40 == 0 then
    local probe = Resolve()
    if probe == nil then
      print("[curated-bridge] Resolve is gone — exiting")
      return
    end
    resolve = probe
  end

  for _, name in ipairs(list_inbox()) do
    local path = SPOOL .. "/inbox/" .. name
    local chunk, load_err = loadfile(path)
    local out
    if not chunk then
      out = "ERROR\n" .. tostring(load_err)
    else
      local ok, res = pcall(chunk)
      if ok then
        out = "OK\n" .. tostring(res)
      else
        out = "ERROR\n" .. tostring(res)
      end
    end
    write_file(SPOOL .. "/outbox/" .. name .. ".result", out)
    os.rename(path, SPOOL .. "/done/" .. name)
    print("[curated-bridge] ran " .. name)
  end

  write_file(SPOOL .. "/bridge.alive", tostring(os.time()))
  os.execute("sleep 0.3")
end

write_file(SPOOL .. "/bridge.alive", "stopped")
print("[curated-bridge] stopped")
