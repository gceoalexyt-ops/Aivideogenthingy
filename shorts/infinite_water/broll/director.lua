-- Films b-roll for the infinite-water Short: builds an island, then runs a fixed shot list.
local GRASS, DIRT = "default:dirt_with_grass", "default:dirt"
local HOLE = {{0,0},{1,0},{0,1},{1,1}}         -- x,z ; A=(0,0) B=(1,1)
local LAVA = {{-5,-5},{-4,-5},{-5,-4},{-4,-4}}
local player, t0, built = nil, nil, false
local events, shots = {}, {}
local function at(t, f) events[#events+1] = {t=t, f=f} end
local function log(msg) minetest.log("action", "[director] " .. msg) end

local function build()
  for x = -9, 9 do for z = -9, 9 do
    for y = -3, -1 do minetest.set_node({x=x,y=y,z=z}, {name=DIRT}) end
    minetest.set_node({x=x,y=0,z=z}, {name=GRASS})
  end end
  -- a few trees and flowers for life
  for _, p in ipairs({{-7,7},{7,-7},{6,6}}) do
    for y = 1, 4 do minetest.set_node({x=p[1],y=y,z=p[2]}, {name="default:tree"}) end
    for dx=-2,2 do for dz=-2,2 do for dy=3,5 do
      if math.abs(dx)+math.abs(dz)+math.abs(dy-4) < 4 then
        local q = {x=p[1]+dx,y=dy,z=p[2]+dz}
        if minetest.get_node(q).name == "air" then minetest.set_node(q,{name="default:leaves"}) end
      end end end end
  end
  for _, p in ipairs({{-3,4,"flowers:rose"},{4,-2,"flowers:dandelion_yellow"},{-2,-6,"flowers:tulip"},{5,3,"flowers:geranium"},{3,6,"default:grass_3"},{-6,1,"default:grass_4"},{2,-4,"default:grass_2"}}) do
    minetest.set_node({x=p[1],y=1,z=p[2]}, {name=p[3]})
  end
  for _, c in ipairs(LAVA) do minetest.set_node({x=c[1],y=0,z=c[2]}, {name="air"}) end
end

local cam = {pos={x=0,y=0,z=0}, target={x=0,y=0,z=0}}
local function aim(eye, target)
  local d = vector.subtract(target, eye)
  player:set_pos({x=eye.x, y=eye.y-1.625, z=eye.z})
  player:set_look_horizontal(math.atan2(-d.x, d.z))
  player:set_look_vertical(math.atan2(-d.y, math.sqrt(d.x*d.x+d.z*d.z)))
end
local function shot(t, name, eye, target, wield)
  at(t, function()
    log(string.format("SHOT %s %.3f", name, minetest.get_us_time()/1e6))
    cam.pos, cam.target, cam.orbit = eye, target, nil
    player:get_inventory():set_stack("main", 1, ItemStack(wield or ""))
  end)
end
local function dig(t, x, z)
  at(t, function()
    local p = {x=x,y=0,z=z}
    minetest.set_node(p, {name="air"})
    minetest.add_particlespawner({amount=24, time=0.1, minpos=vector.subtract(p,0.4), maxpos=vector.add(p,0.4),
      minvel={x=-2,y=2,z=-2}, maxvel={x=2,y=4,z=2}, minacc={x=0,y=-10,z=0}, maxacc={x=0,y=-10,z=0},
      minexptime=0.5, maxexptime=0.9, minsize=1.5, maxsize=3, node={name=GRASS}})
  end)
end
local function place(t, x, z, name) at(t, function() minetest.set_node({x=x,y=0,z=z}, {name=name}) end) end

-- Shot list. Hole centre is (0.5, 0.4, 0.5); lava pit centre (-4.5, 0.4, -4.5).
local hc, lc = {x=0.5,y=0.3,z=0.5}, {x=-4.5,y=0.3,z=-4.5}
shot(0,  "dig",   {x=2.9,y=3.6,z=-1.5}, hc)
for i, c in ipairs(HOLE) do dig(1.0 + 0.6*i, c[1], c[2]) end
shot(5.5, "pour", {x=2.7,y=3.3,z=-1.3}, hc)
place(6.5, 0, 0, "default:water_source")
place(9.0, 1, 1, "default:water_source")
shot(13, "scoop", {x=2.5,y=3.0,z=-1.1}, hc)
place(14.0, 1, 0, "air")
place(16.0, 0, 1, "air")
place(18.0, 0, 0, "air")
shot(21, "lava",  {x=-2.3,y=3.4,z=-6.3}, lc)
place(22.0, -5, -5, "default:lava_source")
place(23.5, -4, -4, "default:lava_source")
place(26.5, -5, -5, "air")
place(27.5, -4, -4, "air")
at(31, function() log(string.format("SHOT orbit %.3f", minetest.get_us_time()/1e6)); cam.orbit = 0
  player:get_inventory():set_stack("main", 1, ItemStack("")) end)
at(42, function() log("DONE"); minetest.request_shutdown("done") end)

minetest.register_on_joinplayer(function(p)
  player = p
  p:hud_set_flags({hotbar=false, healthbar=false, crosshair=false, breathbar=false, minimap=false, minimap_radar=false, wielditem=true})
  p:set_physics_override({gravity=0, speed=0, jump=0})
  p:set_properties({visual_size={x=0,y=0}})
  minetest.set_timeofday(0.5)
  minetest.emerge_area({x=-16,y=-16,z=-16}, {x=16,y=16,z=16}, function(_, _, left)
    if left == 0 then build(); built = true; log("BUILT")
      minetest.after(4, function() t0 = 0; log(string.format("START %.3f", minetest.get_us_time()/1e6)) end)
    end
  end)
end)

local ei = 1
minetest.register_globalstep(function(dt)
  if not player then return end
  if t0 then
    t0 = t0 + dt
    while events[ei] and events[ei].t <= t0 do events[ei].f(); ei = ei + 1 end
  end
  if cam.orbit then
    cam.orbit = cam.orbit + dt
    local a = -2.4 + cam.orbit * 0.22
    aim({x=0.5+math.cos(a)*14, y=9, z=0.5+math.sin(a)*14}, {x=0.5,y=0,z=0.5})
  elseif t0 then aim(cam.pos, cam.target)
  else aim({x=2.9,y=3.6,z=-1.5}, hc) end
end)
