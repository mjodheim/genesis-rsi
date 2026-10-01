'use strict';

// GOOSE DELIVERY — pure game logic (no DOM). Browser: window.GooseLogic.
//
// You are a goose working for a parcel company. Grab the parcel, waddle it to
// the right door before the clock runs out; every delivery buys time. Your
// only tool is HONK: people flee and drop their baguettes, policemen slip.
// Honk too much and the police come for you. Mind the cars.
(function(root){
  const W = 960, H = 600;
  const ROAD_H = {y1:250, y2:330};          // horizontal road
  const ROAD_V = {x1:440, x2:520};          // vertical road
  const HOUSES = [
    {id:'A', x:40,  y:40,  w:150, h:140, roof:'#c8553d', door:'bottom'},
    {id:'B', x:250, y:40,  w:150, h:140, roof:'#3d7dc8', door:'bottom'},
    {id:'C', x:560, y:40,  w:150, h:140, roof:'#7a5cc8', door:'bottom'},
    {id:'D', x:770, y:40,  w:150, h:140, roof:'#3da86a', door:'bottom'},
    {id:'E', x:40,  y:410, w:150, h:150, roof:'#d99a3d', door:'top'},
    {id:'F', x:250, y:410, w:150, h:150, roof:'#c83d7a', door:'top'},
    {id:'G', x:560, y:410, w:150, h:150, roof:'#3dc8c0', door:'top'},
    {id:'H', x:770, y:410, w:150, h:150, roof:'#8a8f9c', door:'top'}
  ].map(h => ({...h, doorX:h.x + h.w / 2, doorY:h.door === 'bottom' ? h.y + h.h + 14 : h.y - 14}));

  const GOOSE_R = 13, GOOSE_SPEED = 190, PED_R = 11, COP_R = 12;
  const HONK_RADIUS = 150, HONK_COOLDOWN = 900;
  const START_TIME = 60000;

  function mulberry(seed){
    let s = seed >>> 0 || 1;
    return () => {
      let t = s += 0x6d2b79f5;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const onRoad = (x, y, pad = 0) => (y > ROAD_H.y1 - pad && y < ROAD_H.y2 + pad) || (x > ROAD_V.x1 - pad && x < ROAD_V.x2 + pad);

  function hitsHouse(x, y, r){
    for(const h of HOUSES){
      const cx = clamp(x, h.x, h.x + h.w), cy = clamp(y, h.y, h.y + h.h);
      if(Math.hypot(x - cx, y - cy) < r) return h;
    }
    return null;
  }

  function walkable(x, y, r){ return x > r && y > r && x < W - r && y < H - r && !hitsHouse(x, y, r); }

  function randomSpot(s, {avoidRoad = true, far = null, minDist = 0} = {}){
    for(let i = 0; i < 300; i++){
      const x = 20 + s.rng() * (W - 40), y = 20 + s.rng() * (H - 40);
      if(!walkable(x, y, 18) || (avoidRoad && onRoad(x, y, 16))) continue;
      if(far && Math.hypot(x - far.x, y - far.y) < minDist) continue;
      return {x, y};
    }
    return {x:215, y:215};
  }

  function newGame(seed = 1){
    const s = {
      w:W, h:H, rng:mulberry(seed), time:0, timeLeft:START_TIME, score:0, over:false,
      goose:{x:330, y:215, vx:0, vy:0, face:0, stun:0, invuln:0, honkAt:-1e9, carrying:false, squashed:0},
      parcel:null, target:null, pickedAt:0, deliveries:0, combo:0, bestCombo:0,
      peds:[], cars:[], items:[], cop:null, nuisance:0, events:[], nextCarAt:500, nextPedAt:0
    };
    for(let i = 0; i < 6; i++) spawnPed(s);
    newParcel(s);
    return s;
  }

  function newParcel(s){
    const spot = randomSpot(s, {far:s.goose, minDist:180});
    s.parcel = {x:spot.x, y:spot.y};
    const choices = HOUSES.filter(h => Math.hypot(h.doorX - spot.x, h.doorY - spot.y) > 260);
    s.target = choices[Math.floor(s.rng() * choices.length)] || HOUSES[0];
  }

  function spawnPed(s){
    const at = randomSpot(s);
    s.peds.push({x:at.x, y:at.y, tx:at.x, ty:at.y, speed:40 + s.rng() * 30, flee:0, baguette:s.rng() < .45,
      shirt:['#ff5ab7','#43efff','#ffd166','#b9ff66','#ff7a59','#8f7cff'][Math.floor(s.rng() * 6)], wait:0});
  }

  function spawnCar(s){
    const lanes = [
      {x:-70, y:272, vx:1, vy:0}, {x:W + 70, y:308, vx:-1, vy:0},
      {x:462, y:-50, vx:0, vy:1}, {x:498, y:H + 50, vx:0, vy:-1}
    ];
    const lane = lanes[Math.floor(s.rng() * lanes.length)];
    const speed = 150 + s.rng() * 90 + Math.min(120, s.time / 1000 * 1.2);
    s.cars.push({x:lane.x, y:lane.y, vx:lane.vx * speed, vy:lane.vy * speed,
      color:['#ff4d5e','#43efff','#ffd166','#f4f7ff','#7a5cc8','#3da86a'][Math.floor(s.rng() * 6)], horizontal:lane.vx !== 0});
  }

  function carHits(car, x, y, r){
    const hw = car.horizontal ? 30 : 15, hh = car.horizontal ? 15 : 30;
    const cx = clamp(x, car.x - hw, car.x + hw), cy = clamp(y, car.y - hh, car.y + hh);
    return Math.hypot(x - cx, y - cy) < r;
  }

  function dropParcel(s, why){
    const g = s.goose;
    if(!g.carrying) return;
    g.carrying = false;
    let spot = null;
    for(let i = 0; i < 20 && !spot; i++){
      const a = s.rng() * Math.PI * 2, d = 40 + s.rng() * 40;
      const x = g.x + Math.cos(a) * d, y = g.y + Math.sin(a) * d;
      if(walkable(x, y, 14) && !onRoad(x, y, 10)) spot = {x, y};
    }
    s.parcel = spot || randomSpot(s);
    s.combo = 0;
    s.events.push({type:'drop', x:s.parcel.x, y:s.parcel.y, why});
  }

  function honk(s){
    const g = s.goose;
    if(s.time - g.honkAt < HONK_COOLDOWN || g.stun > 0) return false;
    g.honkAt = s.time;
    s.nuisance += 10;
    let scared = 0;
    for(const p of s.peds){
      if(dist(p, g) > HONK_RADIUS) continue;
      p.flee = 1600; scared++;
      if(p.baguette){ p.baguette = false; s.items.push({x:p.x, y:p.y, kind:'baguette', born:s.time}); }
    }
    s.nuisance += scared * 5;
    if(s.cop && dist(s.cop, g) < HONK_RADIUS * .8 && !s.cop.stun){ s.cop.stun = 2200; s.nuisance += 15; s.events.push({type:'copSlip', x:s.cop.x, y:s.cop.y}); }
    s.events.push({type:'honk', x:g.x, y:g.y, scared});
    return true;
  }

  function moveCircle(obj, dx, dy, r){
    if(walkable(obj.x + dx, obj.y, r)) obj.x += dx;
    if(walkable(obj.x, obj.y + dy, r)) obj.y += dy;
  }

  function update(s, dtMs, input = {}){
    if(s.over) return s;
    const dt = dtMs / 1000;
    s.time += dtMs;
    s.timeLeft -= dtMs;
    if(s.timeLeft <= 0){ s.timeLeft = 0; s.over = true; s.events.push({type:'timeout'}); return s; }

    const g = s.goose;
    g.stun = Math.max(0, g.stun - dtMs);
    g.invuln = Math.max(0, g.invuln - dtMs);
    g.squashed = Math.max(0, g.squashed - dtMs);
    if(input.honk) honk(s);

    // Goose: snappy acceleration, a little slide, slower when carrying.
    let ix = (input.x || 0), iy = (input.y || 0);
    const len = Math.hypot(ix, iy);
    if(len > 1){ ix /= len; iy /= len; }
    if(g.stun > 0){ ix = 0; iy = 0; }
    const top = GOOSE_SPEED * (g.carrying ? .86 : 1);
    const k = 1 - Math.pow(.0005, dt);
    g.vx += (ix * top - g.vx) * k;
    g.vy += (iy * top - g.vy) * k;
    if(Math.hypot(g.vx, g.vy) > 8) g.face = Math.atan2(g.vy, g.vx);
    moveCircle(g, g.vx * dt, g.vy * dt, GOOSE_R);

    // Parcel pickup and delivery.
    if(!g.carrying && s.parcel && dist(g, s.parcel) < GOOSE_R + 16){
      g.carrying = true; s.parcel = null; s.pickedAt = s.time;
      s.events.push({type:'pickup', x:g.x, y:g.y});
    }
    if(g.carrying && Math.hypot(g.x - s.target.doorX, g.y - s.target.doorY) < GOOSE_R + 18){
      g.carrying = false;
      s.deliveries++; s.combo++; s.bestCombo = Math.max(s.bestCombo, s.combo);
      const speed = Math.max(0, Math.round(100 - (s.time - s.pickedAt) / 100));
      const points = 100 + Math.min(s.combo - 1, 5) * 25 + speed;
      const bonus = Math.max(3500, 7500 - s.deliveries * 200);
      s.score += points; s.timeLeft = Math.min(99000, s.timeLeft + bonus);
      s.events.push({type:'deliver', x:s.target.doorX, y:s.target.doorY, points, bonus, combo:s.combo});
      newParcel(s);
    }

    // Items (baguettes).
    s.items = s.items.filter(it => {
      if(dist(it, g) < GOOSE_R + 14){ s.score += 50; s.timeLeft += 1500; s.events.push({type:'baguette', x:it.x, y:it.y}); return false; }
      return s.time - it.born < 12000;
    });

    // Pedestrians wander; frightened ones run away from the goose.
    const wanted = Math.min(14, 6 + Math.floor(s.time / 15000));
    if(s.peds.length < wanted && s.time >= s.nextPedAt){ spawnPed(s); s.nextPedAt = s.time + 2500; }
    for(const p of s.peds){
      p.flee = Math.max(0, p.flee - dtMs);
      let dx, dy, sp;
      if(p.flee > 0){
        const a = Math.atan2(p.y - g.y, p.x - g.x);
        dx = Math.cos(a); dy = Math.sin(a); sp = 150;
      }else{
        if(p.wait > 0){ p.wait -= dtMs; continue; }
        if(Math.hypot(p.tx - p.x, p.ty - p.y) < 6){ const t = randomSpot(s); p.tx = t.x; p.ty = t.y; p.wait = s.rng() * 900; continue; }
        const a = Math.atan2(p.ty - p.y, p.tx - p.x);
        dx = Math.cos(a); dy = Math.sin(a); sp = p.speed;
      }
      const bx = p.x, by = p.y;
      moveCircle(p, dx * sp * dt, dy * sp * dt, PED_R);
      if(Math.abs(p.x - bx) + Math.abs(p.y - by) < .01 && p.flee <= 0){ const t = randomSpot(s); p.tx = t.x; p.ty = t.y; }
      // Bumping into someone while carrying knocks the parcel loose.
      if(g.carrying && !g.invuln && dist(p, g) < PED_R + GOOSE_R){
        dropParcel(s, 'bump'); g.stun = 450; g.invuln = 1200;
        s.events.push({type:'bump', x:g.x, y:g.y});
      }
    }

    // Traffic.
    if(s.time >= s.nextCarAt){ spawnCar(s); s.nextCarAt = s.time + Math.max(700, 2200 - s.time * .012) * (.6 + s.rng() * .8); }
    for(const c of s.cars){
      c.x += c.vx * dt; c.y += c.vy * dt;
      if(!g.invuln && carHits(c, g.x, g.y, GOOSE_R)){
        dropParcel(s, 'car');
        s.timeLeft -= 5000;
        g.stun = 900; g.invuln = 1800; g.squashed = 900; g.vx = g.vy = 0;
        // Thrown onto the nearest pavement.
        if(c.horizontal) g.y = g.y < (ROAD_H.y1 + ROAD_H.y2) / 2 ? ROAD_H.y1 - GOOSE_R - 4 : ROAD_H.y2 + GOOSE_R + 4;
        else g.x = g.x < (ROAD_V.x1 + ROAD_V.x2) / 2 ? ROAD_V.x1 - GOOSE_R - 4 : ROAD_V.x2 + GOOSE_R + 4;
        s.events.push({type:'car', x:g.x, y:g.y});
      }
    }
    s.cars = s.cars.filter(c => c.x > -120 && c.x < W + 120 && c.y > -120 && c.y < H + 120);

    // Police: summoned by too much honking.
    s.nuisance = Math.max(0, s.nuisance - dt * 4);
    if(!s.cop && s.nuisance >= 60){
      const at = randomSpot(s, {far:g, minDist:320});
      s.cop = {x:at.x, y:at.y, stun:0, speed:130 + Math.min(70, s.time / 1000)};
      s.events.push({type:'cop', x:at.x, y:at.y});
    }
    if(s.cop){
      const c = s.cop;
      c.stun = Math.max(0, c.stun - dtMs);
      if(!c.stun){
        const a = Math.atan2(g.y - c.y, g.x - c.x);
        moveCircle(c, Math.cos(a) * c.speed * dt, Math.sin(a) * c.speed * dt, COP_R);
      }
      if(!c.stun && !g.invuln && dist(c, g) < COP_R + GOOSE_R){
        dropParcel(s, 'cop');
        s.timeLeft -= 8000;
        g.stun = 1200; g.invuln = 2000;
        s.events.push({type:'arrest', x:g.x, y:g.y});
        s.cop = null; s.nuisance = 25;
      }else if(s.nuisance < 10 && !c.stun){
        s.events.push({type:'copLeaves', x:c.x, y:c.y});
        s.cop = null;
      }
    }
    if(s.timeLeft <= 0){ s.timeLeft = 0; s.over = true; s.events.push({type:'timeout'}); }
    return s;
  }

  root.GooseLogic = {W, H, HOUSES, ROAD_H, ROAD_V, GOOSE_R, HONK_RADIUS, HONK_COOLDOWN, START_TIME,
    newGame, update, honk, walkable, onRoad, carHits, dropParcel, spawnCar};
})(typeof window !== 'undefined' ? window : globalThis);
