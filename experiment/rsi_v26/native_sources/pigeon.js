'use strict';

// PIGEON CONTROL — pure game logic (no DOM). Browser: window.PigeonLogic.
//
// Pigeons fly into the square. Draw a path from each one to the monument of
// its colour; two birds touching is a mid-air disaster and ends the shift.
// Later: fat pigeons, ninja pigeons, seagulls that answer to nobody and a
// kid with bread who makes everyone forget their flight plan.
(function(root){
  const W = 960, H = 600;

  const KINDS = {
    city:  {speed:44, r:12, color:'#9aa6b8', target:'general'},
    dove:  {speed:40, r:12, color:'#f4f7ff', target:'fountain'},
    fat:   {speed:28, r:16, color:'#b98552', target:'kiosk'},
    ninja: {speed:70, r:10, color:'#2b2f3a', target:'any'}
  };
  const STATUES = [
    {id:'general',  x:190, y:420, r:40, color:'#9aa6b8', name:'Statue du Général'},
    {id:'fountain', x:480, y:170, r:44, color:'#7fe3ff', name:'Fontaine'},
    {id:'kiosk',    x:780, y:410, r:40, color:'#d99a5b', name:'Kiosque à pain'}
  ];
  const LAND_POINTS = 100, STREAK_BONUS = 50, STREAK_WINDOW = 3500;

  function mulberry(seed){
    let s = seed >>> 0 || 1;
    return () => {
      let t = s += 0x6d2b79f5;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function newGame(seed = 1){
    return {
      w:W, h:H, rng:mulberry(seed), time:0, score:0, landed:0, over:false, cause:null,
      pigeons:[], gulls:[], bread:null, incoming:[], events:[], nextId:1,
      nextSpawnAt:600, nextGullAt:38000, nextBreadAt:26000, streak:0, lastLandAt:-1e9, crash:null
    };
  }

  function kindFor(s){
    const t = s.time / 1000, r = s.rng();
    if(t > 45 && r < .12) return 'ninja';
    if(t > 20 && r < .32) return 'fat';
    return r < .66 ? 'city' : 'dove';
  }

  function spawnInterval(s){ return Math.max(1500, 4600 - s.time * .03); }
  function maxBirds(s){ return Math.min(14, 3 + Math.floor(s.time / 12000)); }

  // Pick an entry point on an edge, heading roughly across the square.
  function entry(s){
    const side = Math.floor(s.rng() * 4);
    const along = s.rng();
    const m = 40;
    const pos = [
      {x:m + along * (W - 2 * m), y:-30}, {x:W + 30, y:m + along * (H - 2 * m)},
      {x:m + along * (W - 2 * m), y:H + 30}, {x:-30, y:m + along * (H - 2 * m)}
    ][side];
    const aim = {x:W * (.3 + s.rng() * .4), y:H * (.3 + s.rng() * .4)};
    return {x:pos.x, y:pos.y, angle:Math.atan2(aim.y - pos.y, aim.x - pos.x), side};
  }

  function queueSpawn(s){
    const e = entry(s);
    s.incoming.push({...e, kind:kindFor(s), at:s.time + 1800});
  }

  function spawn(s, inc){
    const k = KINDS[inc.kind];
    const p = {id:s.nextId++, kind:inc.kind, x:inc.x, y:inc.y, angle:inc.angle, speed:k.speed, r:k.r,
      path:[], inside:false, state:'flying', landT:0, statue:null, flap:s.rng() * 6, hungry:false};
    s.pigeons.push(p);
    s.events.push({type:'enter', id:p.id, kind:p.kind});
    return p;
  }

  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const statueAt = (x, y) => STATUES.find(st => Math.hypot(st.x - x, st.y - y) <= st.r);
  const accepts = (st, kind) => KINDS[kind].target === 'any' || KINDS[kind].target === st.id;

  // The player draws: replaces a pigeon's route. Returns the matching statue
  // if the route ends on it.
  function setPath(s, id, points){
    const p = s.pigeons.find(q => q.id === id && q.state === 'flying');
    if(!p) return null;
    p.path = points.map(pt => ({x:Math.max(-20, Math.min(W + 20, pt.x)), y:Math.max(-20, Math.min(H + 20, pt.y))}));
    p.hungry = false;
    const end = p.path[p.path.length - 1];
    const st = end && statueAt(end.x, end.y);
    p.target = st && accepts(st, p.kind) ? st.id : null;
    return p.target;
  }

  function pickPigeon(s, x, y, slop = 22){
    let best = null, bd = Infinity;
    for(const p of s.pigeons){
      if(p.state !== 'flying') continue;
      const d = Math.hypot(p.x - x, p.y - y);
      if(d < p.r + slop && d < bd){ best = p; bd = d; }
    }
    return best;
  }

  function steer(p, tx, ty, dt, turnRate = 3.2){
    const want = Math.atan2(ty - p.y, tx - p.x);
    let diff = want - p.angle;
    while(diff > Math.PI) diff -= Math.PI * 2;
    while(diff < -Math.PI) diff += Math.PI * 2;
    const max = turnRate * dt;
    p.angle += Math.max(-max, Math.min(max, diff));
  }

  // A bird counts as over the square (and can collide) once it is fully in
  // view, whether it is flying free or following a route.
  function markInside(p){
    if(!p.inside && p.x > p.r && p.y > p.r && p.x < W - p.r && p.y < H - p.r) p.inside = true;
  }

  function movePigeon(s, p, dt){
    const step = p.speed * dt;
    if(p.path.length){
      // Follow the drawn route point by point.
      let left = step;
      while(left > 0 && p.path.length){
        const pt = p.path[0];
        const d = Math.hypot(pt.x - p.x, pt.y - p.y);
        if(d <= left){ p.x = pt.x; p.y = pt.y; left -= d; p.path.shift(); }
        else{
          p.angle = Math.atan2(pt.y - p.y, pt.x - p.x);
          p.x += Math.cos(p.angle) * left; p.y += Math.sin(p.angle) * left; left = 0;
        }
      }
      markInside(p);
      if(!p.path.length && p.target){
        const st = STATUES.find(x => x.id === p.target);
        if(st && dist(p, st) <= st.r){ land(s, p, st); return; }
      }
      return;
    }
    if(p.hungry && s.bread) steer(p, s.bread.x, s.bread.y, dt, 2.4);
    p.x += Math.cos(p.angle) * step;
    p.y += Math.sin(p.angle) * step;
    // Once inside, the square's edges bounce birds back in.
    markInside(p);
    if(p.inside){
      if(p.x < p.r || p.x > W - p.r){ p.angle = Math.PI - p.angle; p.x = Math.max(p.r, Math.min(W - p.r, p.x)); }
      if(p.y < p.r || p.y > H - p.r){ p.angle = -p.angle; p.y = Math.max(p.r, Math.min(H - p.r, p.y)); }
    }
  }

  function land(s, p, st){
    p.state = 'landing'; p.statue = st.id; p.landT = 0; p.path = [];
    s.streak = s.time - s.lastLandAt < STREAK_WINDOW ? s.streak + 1 : 1;
    s.lastLandAt = s.time;
    const points = LAND_POINTS + Math.min(s.streak - 1, 5) * STREAK_BONUS + (p.kind === 'ninja' ? 100 : p.kind === 'fat' ? 50 : 0);
    s.score += points;
    s.landed++;
    s.events.push({type:'land', x:st.x, y:st.y, kind:p.kind, points, streak:s.streak});
  }

  function crash(s, a, b){
    s.over = true;
    s.cause = b.kind === 'gull' ? 'gull' : (a.kind === 'fat' || b.kind === 'fat') ? 'fat' : 'collision';
    s.crash = {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2};
    s.events.push({type:'crash', ...s.crash, cause:s.cause});
  }

  // Pairs of birds closer than this will be flagged by the renderer.
  function nearMisses(s){
    const flying = s.pigeons.filter(p => p.state === 'flying');
    const out = new Set();
    for(let i = 0; i < flying.length; i++) for(let j = i + 1; j < flying.length; j++){
      const a = flying[i], b = flying[j];
      if(dist(a, b) < (a.r + b.r) * 2.6){ out.add(a.id); out.add(b.id); }
    }
    return out;
  }

  function update(s, dtMs){
    if(s.over) return s;
    const dt = dtMs / 1000;
    s.time += dtMs;

    // Arrivals, announced 1.8 s ahead so the player can see them coming.
    const flying = s.pigeons.filter(p => p.state === 'flying').length + s.incoming.length;
    if(s.time >= s.nextSpawnAt){
      if(flying < maxBirds(s)) queueSpawn(s);
      s.nextSpawnAt = s.time + spawnInterval(s) * (.75 + s.rng() * .5);
    }
    s.incoming = s.incoming.filter(inc => { if(inc.at <= s.time){ spawn(s, inc); return false; } return true; });

    // A seagull: huge, fast, and deaf to air traffic control.
    if(s.time >= s.nextGullAt){
      const e = entry(s);
      const angle = Math.atan2(H / 2 - e.y, W / 2 - e.x) + (s.rng() - .5) * .5;
      s.gulls.push({x:e.x - Math.cos(angle) * 140, y:e.y - Math.sin(angle) * 140, angle, speed:120, r:22, kind:'gull', warnUntil:s.time + 2000, wing:0});
      s.events.push({type:'gull'});
      s.nextGullAt = s.time + Math.max(9000, 24000 - s.time * .05);
    }
    for(const g of s.gulls){
      g.wing += dt * 8;
      g.x += Math.cos(g.angle) * g.speed * dt;
      g.y += Math.sin(g.angle) * g.speed * dt;
    }
    s.gulls = s.gulls.filter(g => g.x > -300 && g.x < W + 300 && g.y > -300 && g.y < H + 300);

    // A kid throws bread: every bird without a route goes for it.
    if(s.time >= s.nextBreadAt && !s.bread){
      s.bread = {x:180 + s.rng() * (W - 360), y:120 + s.rng() * (H - 240), until:s.time + 5500};
      s.pigeons.forEach(p => { if(p.state === 'flying' && !p.path.length) p.hungry = true; });
      s.events.push({type:'bread', x:s.bread.x, y:s.bread.y});
      s.nextBreadAt = s.time + 30000 + s.rng() * 12000;
    }
    if(s.bread && s.time > s.bread.until){ s.bread = null; s.pigeons.forEach(p => { p.hungry = false; }); }

    for(const p of s.pigeons){
      p.flap += dt * (p.kind === 'fat' ? 9 : 14);
      if(p.state === 'flying') movePigeon(s, p, dt);
      else if(p.state === 'landing'){ p.landT += dt; if(p.landT > .7) p.state = 'landed'; }
    }
    s.pigeons = s.pigeons.filter(p => p.state !== 'landed');

    // Collisions, only between birds that are actually over the square: two
    // incoming pigeons crossing off-screen must not end the shift unseen.
    const air = s.pigeons.filter(p => p.state === 'flying' && p.inside);
    const onScreen = g => g.x > -g.r && g.x < W + g.r && g.y > -g.r && g.y < H + g.r;
    for(let i = 0; i < air.length && !s.over; i++){
      for(let j = i + 1; j < air.length; j++){
        if(dist(air[i], air[j]) < air[i].r + air[j].r){ crash(s, air[i], air[j]); break; }
      }
      for(const g of s.gulls) if(!s.over && onScreen(g) && dist(air[i], g) < air[i].r + g.r) crash(s, air[i], g);
    }
    return s;
  }

  root.PigeonLogic = {W, H, KINDS, STATUES, newGame, update, setPath, pickPigeon, statueAt, accepts, nearMisses, spawn,
    POINTS:{LAND_POINTS, STREAK_BONUS}};
})(typeof window !== 'undefined' ? window : globalThis);
