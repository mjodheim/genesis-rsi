'use strict';

// FORBIDDEN FRUIT — pure game logic, no DOM. Loaded as a classic script in
// the browser (window.FruitLogic) and through vm in the tests.
//
// You are the apple. Snakes hunt you with three personalities (chaser,
// ambusher, drunk). They never stop growing and speeding up, but a snake that
// crashes into a wall, itself or another snake explodes into seeds — so the
// real game is baiting them into each other.
(function(root){
  const W = 21, H = 21;
  const DIRS = {up:{x:0,y:-1}, down:{x:0,y:1}, left:{x:-1,y:0}, right:{x:1,y:0}};
  const DIR_LIST = [DIRS.up, DIRS.right, DIRS.down, DIRS.left];
  const PERSONALITIES = ['chaser', 'ambusher', 'drunk', 'chaser'];
  const COLORS = ['#b9ff66', '#ff5ab7', '#ffd166', '#43efff'];

  const APPLE_STEP_MS = 105;
  const SEED_POINTS = 25, PEPIN_POINTS = 100, KILL_POINTS = 500, SECOND_POINTS = 10;
  // The multiplier is capped so the scoring rate stays bounded (the server
  // rejects scores faster than the fastest legitimate run).
  const MAX_COMBO = 4;

  function mulberry(seed){
    let s = seed >>> 0 || 1;
    return () => {
      let t = s += 0x6d2b79f5;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  const key = (x, y) => y * W + x;
  const inBounds = (x, y) => x >= 0 && y >= 0 && x < W && y < H;

  function newGame(seed = 1){
    const rng = mulberry(seed);
    const s = {
      w:W, h:H, rng, time:0, score:0, secondsBank:0, over:false, cause:null,
      apple:{x:10, y:15, dir:null, acc:0, lastDir:DIRS.up, lastMoveAt:-1e9},
      snakes:[], seeds:[], events:[], spawnTimer:0, nextSpawnAt:0,
      confusedUntil:0, combo:0, comboUntil:0, kills:0, spawned:0, pendingSpawns:[]
    };
    spawnSnake(s, {x:10, y:1}, DIRS.down, 0);
    s.nextSpawnAt = 22000;
    for(let i = 0; i < 4; i++) addSeed(s, 'seed');
    return s;
  }

  // Cells covered by snake bodies. Only the tail of `mover` is left free — it
  // is vacated during that snake's own step (unless it is growing); every
  // other snake's tail stays solid, since it may not move this tick.
  function occupied(s, mover = null){
    const blocked = new Set();
    for(const sn of s.snakes){
      if(!sn.alive) continue;
      const n = sn.body.length - (sn === mover && !sn.grow ? 1 : 0);
      for(let i = 0; i < n; i++) blocked.add(key(sn.body[i].x, sn.body[i].y));
    }
    return blocked;
  }

  function freeCell(s, avoidNear = null, minDist = 0){
    const blocked = occupied(s, false);
    s.seeds.forEach(p => blocked.add(key(p.x, p.y)));
    blocked.add(key(s.apple.x, s.apple.y));
    for(let tries = 0; tries < 200; tries++){
      const x = Math.floor(s.rng() * W), y = Math.floor(s.rng() * H);
      if(blocked.has(key(x, y))) continue;
      if(avoidNear && Math.abs(x - avoidNear.x) + Math.abs(y - avoidNear.y) < minDist) continue;
      return {x, y};
    }
    return null;
  }

  function addSeed(s, kind){
    const c = freeCell(s);
    if(c) s.seeds.push({...c, kind, born:s.time});
  }

  function spawnSnake(s, at, dir, index){
    // Arrives coiled on one cell and unrolls as it moves.
    const body = Array.from({length:4}, () => ({x:at.x, y:at.y}));
    s.snakes.push({
      id:s.spawned++, body, dir, alive:true, acc:0, grow:0, growAcc:0,
      personality:PERSONALITIES[index % PERSONALITIES.length], color:COLORS[index % COLORS.length], deadAt:0
    });
    s.events.push({type:'spawn', x:at.x, y:at.y, index});
  }

  // Snakes get faster the longer you survive.
  function snakeStepMs(s, sn){
    const base = Math.max(78, 185 - s.time / 1000 * 1.15);
    return sn.personality === 'drunk' ? base * 1.12 : base;
  }

  // Breadth-first search from the head to the target; returns the first step.
  function bfs(s, sn, target, blocked){
    const head = sn.body[0];
    const start = key(head.x, head.y);
    const goal = key(target.x, target.y);
    const prev = new Map([[start, null]]);
    const queue = [head];
    while(queue.length){
      const c = queue.shift();
      const k = key(c.x, c.y);
      if(k === goal){
        let step = k;
        while(prev.get(step) !== start && prev.get(step) !== null) step = prev.get(step);
        return {x:step % W - head.x, y:Math.floor(step / W) - head.y};
      }
      for(const d of DIR_LIST){
        const nx = c.x + d.x, ny = c.y + d.y, nk = key(nx, ny);
        if(!inBounds(nx, ny) || prev.has(nk) || (blocked.has(nk) && nk !== goal)) continue;
        prev.set(nk, k);
        queue.push({x:nx, y:ny});
      }
    }
    return null;
  }

  function floodSize(from, blocked, cap = 120){
    const seen = new Set([key(from.x, from.y)]);
    const queue = [from];
    while(queue.length && seen.size < cap){
      const c = queue.shift();
      for(const d of DIR_LIST){
        const nx = c.x + d.x, ny = c.y + d.y, nk = key(nx, ny);
        if(inBounds(nx, ny) && !seen.has(nk) && !blocked.has(nk)){ seen.add(nk); queue.push({x:nx, y:ny}); }
      }
    }
    return seen.size;
  }

  function isReverse(a, b){ return a.x === -b.x && a.y === -b.y; }

  function safeMoves(s, sn, blocked){
    const head = sn.body[0];
    return DIR_LIST.filter(d => !isReverse(d, sn.dir) && inBounds(head.x + d.x, head.y + d.y) && !blocked.has(key(head.x + d.x, head.y + d.y)));
  }

  function targetFor(s, sn){
    const a = s.apple;
    if(sn.personality !== 'ambusher') return {x:a.x, y:a.y};
    const d = a.dir || a.lastDir;
    for(let k = 4; k > 0; k--){
      const x = a.x + d.x * k, y = a.y + d.y * k;
      if(inBounds(x, y)) return {x, y};
    }
    return {x:a.x, y:a.y};
  }

  function chooseDir(s, sn){
    const blocked = occupied(s, sn);
    const moves = safeMoves(s, sn, blocked);
    if(!moves.length) return sn.dir; // cornered: it will crash
    const confused = s.time < s.confusedUntil;
    const drunkRoll = sn.personality === 'drunk' && s.rng() < .28;
    if(confused || drunkRoll) return moves[Math.floor(s.rng() * moves.length)];
    let step = bfs(s, sn, targetFor(s, sn), blocked);
    if(!step && sn.personality === 'ambusher') step = bfs(s, sn, s.apple, blocked);
    if(step && !isReverse(step, sn.dir)){
      // Don't follow the path into a pocket smaller than the snake itself.
      const head = sn.body[0];
      const next = {x:head.x + step.x, y:head.y + step.y};
      const onApple = next.x === s.apple.x && next.y === s.apple.y;
      if(onApple || floodSize(next, blocked) >= Math.min(sn.body.length, 40)) return step;
    }
    let best = moves[0], bestSize = -1;
    for(const d of moves){
      const head = sn.body[0];
      const size = floodSize({x:head.x + d.x, y:head.y + d.y}, blocked);
      if(size > bestSize){ best = d; bestSize = size; }
    }
    return best;
  }

  function killSnake(s, sn, reason){
    sn.alive = false;
    sn.deadAt = s.time;
    s.kills++;
    s.combo = s.time < s.comboUntil ? Math.min(s.combo + 1, MAX_COMBO) : 1;
    s.comboUntil = s.time + 4000;
    const points = KILL_POINTS * s.combo;
    s.score += points;
    // The corpse turns into seeds: bait them into each other, then feast.
    const cells = sn.body.filter((_, i) => i % 2 === 0).slice(0, 14);
    for(const c of cells) if(!(c.x === s.apple.x && c.y === s.apple.y) && inBounds(c.x, c.y)) s.seeds.push({x:c.x, y:c.y, kind:'seed', born:s.time});
    s.events.push({type:'kill', x:sn.body[0].x, y:sn.body[0].y, color:sn.color, points, combo:s.combo, reason});
    // A replacement arrives, a bit later and a bit longer.
    s.pendingSpawns.push({at:s.time + 2600, length:sn.body.length});
  }

  function stepSnake(s, sn){
    sn.dir = chooseDir(s, sn);
    const head = sn.body[0];
    const nx = head.x + sn.dir.x, ny = head.y + sn.dir.y;
    if(nx === s.apple.x && ny === s.apple.y){
      sn.body.unshift({x:nx, y:ny});
      s.over = true;
      s.cause = sn.personality;
      s.events.push({type:'eaten', x:nx, y:ny, color:sn.color});
      return;
    }
    if(!inBounds(nx, ny)) return killSnake(s, sn, 'wall');
    const blocked = occupied(s, sn);
    if(blocked.has(key(nx, ny))) return killSnake(s, sn, 'crash');
    sn.body.unshift({x:nx, y:ny});
    if(sn.grow > 0) sn.grow--; else sn.body.pop();
    const seedIndex = s.seeds.findIndex(p => p.x === nx && p.y === ny);
    if(seedIndex >= 0){ s.seeds.splice(seedIndex, 1); sn.grow += 2; s.events.push({type:'snakeSeed', x:nx, y:ny}); }
  }

  function moveApple(s, dir){
    const a = s.apple;
    const nx = a.x + dir.x, ny = a.y + dir.y;
    if(!inBounds(nx, ny)) return false;
    for(const sn of s.snakes){
      if(!sn.alive) continue;
      const hit = sn.body.findIndex(c => c.x === nx && c.y === ny);
      if(hit === 0){ a.x = nx; a.y = ny; s.over = true; s.cause = sn.personality; s.events.push({type:'eaten', x:nx, y:ny, color:sn.color}); return true; }
      if(hit > 0) return false;
    }
    a.x = nx; a.y = ny; a.lastDir = dir;
    const i = s.seeds.findIndex(p => p.x === nx && p.y === ny);
    if(i >= 0){
      const seed = s.seeds.splice(i, 1)[0];
      if(seed.kind === 'pepin'){
        s.score += PEPIN_POINTS;
        s.confusedUntil = s.time + 3200;
        s.events.push({type:'pepin', x:nx, y:ny});
      }else{
        s.score += SEED_POINTS;
        s.events.push({type:'seed', x:nx, y:ny});
      }
    }
    return true;
  }

  function edgeSpawn(s){
    const blocked = occupied(s, false);
    let pick = null;
    for(let tries = 0; tries < 24; tries++){
      const side = Math.floor(s.rng() * 4);
      const t = 3 + Math.floor(s.rng() * (W - 6));
      const [at, dir] = [
        [{x:t, y:1}, DIRS.down], [{x:W - 2, y:t}, DIRS.left], [{x:t, y:H - 2}, DIRS.up], [{x:1, y:t}, DIRS.right]
      ][side];
      if(blocked.has(key(at.x, at.y))) continue;
      pick = {at, dir};
      // Never right next to the apple.
      if(Math.abs(at.x - s.apple.x) + Math.abs(at.y - s.apple.y) >= 7) break;
    }
    return pick;
  }

  function aliveCount(s){ return s.snakes.filter(sn => sn.alive).length; }

  // Advance the world by dt milliseconds. `input` is the held direction name
  // ('up' | 'down' | 'left' | 'right' | null).
  function update(s, dt, input){
    if(s.over) return s;
    s.time += dt;
    s.secondsBank += dt;
    while(s.secondsBank >= 1000){ s.secondsBank -= 1000; s.score += SECOND_POINTS; }

    // The apple moves at most once per APPLE_STEP_MS. A new press moves it
    // right away only if the cooldown has elapsed: tapping or switching
    // directions never buys extra steps.
    const a = s.apple;
    const dir = input ? DIRS[input] : null;
    if(dir !== a.dir){ a.dir = dir; a.acc = Math.min(APPLE_STEP_MS, s.time - dt - a.lastMoveAt); }
    if(a.dir){
      a.acc += dt;
      while(a.acc >= APPLE_STEP_MS && !s.over){ a.acc -= APPLE_STEP_MS; if(moveApple(s, a.dir)) a.lastMoveAt = s.time; }
    }
    if(s.over) return s;

    for(const sn of s.snakes){
      if(!sn.alive) continue;
      sn.growAcc += dt;
      if(sn.growAcc >= 3500){ sn.growAcc -= 3500; if(sn.body.length < 42) sn.grow++; }
      sn.acc += dt;
      const every = snakeStepMs(s, sn);
      while(sn.acc >= every && sn.alive && !s.over){ sn.acc -= every; stepSnake(s, sn); }
      if(s.over) return s;
    }
    s.snakes = s.snakes.filter(sn => sn.alive || s.time - sn.deadAt < 700);

    // More hunters over time, up to four at once.
    const cap = Math.min(4, 1 + Math.floor(s.time / 22000));
    if(s.time >= s.nextSpawnAt && aliveCount(s) + s.pendingSpawns.length < cap){
      s.pendingSpawns.push({at:s.time + 1500, length:4 + Math.floor(s.time / 15000)});
      s.nextSpawnAt = s.time + 22000;
    }
    s.pendingSpawns.sort((p, q) => p.at - q.at);
    while(s.pendingSpawns.length && s.pendingSpawns[0].at <= s.time){
      const p = s.pendingSpawns.shift();
      if(aliveCount(s) >= 4) continue;
      const spot = edgeSpawn(s);
      if(!spot){ p.at = s.time + 500; s.pendingSpawns.push(p); break; }
      spawnSnake(s, spot.at, spot.dir, s.spawned);
      const sn = s.snakes[s.snakes.length - 1];
      sn.grow = Math.max(0, Math.min(20, p.length - 4));
    }
    if(!s.pendingSpawns.length && aliveCount(s) === 0) s.pendingSpawns.push({at:s.time + 1200, length:5});

    // Warn the renderer about arrivals.
    s.incoming = s.pendingSpawns.filter(p => p.at - s.time < 1500).length;

    // Seeds trickle in; a golden pépin every so often.
    if(s.seeds.length < 6 && s.rng() < dt / 900) addSeed(s, 'seed');
    if(!s.seeds.some(p => p.kind === 'pepin') && s.rng() < dt / 14000) addSeed(s, 'pepin');
    return s;
  }

  root.FruitLogic = {W, H, DIRS, newGame, update, bfs, occupied, chooseDir, snakeStepMs, moveApple, spawnSnake, killSnake,
    POINTS:{SEED_POINTS, PEPIN_POINTS, KILL_POINTS, SECOND_POINTS, MAX_COMBO}};
})(typeof window !== 'undefined' ? window : globalThis);
