'use strict';

const COLS = 10;
const ROWS = 20;
const CELL = 36;
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const overlay = document.getElementById('overlay');
const octx = overlay.getContext('2d');
const nextCanvas = document.getElementById('next');
const nctx = nextCanvas.getContext('2d');
const cabinet = document.getElementById('cabinet');
const scoreEl = document.getElementById('score');
const linesEl = document.getElementById('lines');
const levelEl = document.getElementById('level');
const chaosLabel = document.getElementById('chaosLabel');
const chaosFill = document.getElementById('chaosFill');
const eventTitle = document.getElementById('eventTitle');
const eventText = document.getElementById('eventText');
const banner = document.getElementById('banner');
const startPanel = document.getElementById('startPanel');
const gameOverPanel = document.getElementById('gameOver');
const finalScoreEl = document.getElementById('finalScore');
const deathLine = document.getElementById('deathLine');
const soundBtn = document.getElementById('soundBtn');
const pauseBtn = document.getElementById('pauseBtn');
const dailyBadge = document.getElementById('dailyBadge');
const bestFreeEl = document.getElementById('bestFree');
const bestDailyEl = document.getElementById('bestDaily');
const newBestEl = document.getElementById('newBest');

const COLORS = ['#000000','#43efff','#8f7cff','#ff5ab7','#ffd166','#b9ff66','#ff7a59','#62a8ff','#d17cff','#ffffff'];
const SHAPES = [
  [[1,1,1,1]],
  [[1,1],[1,1]],
  [[0,1,0],[1,1,1]],
  [[0,1,1],[1,1,0]],
  [[1,1,0],[0,1,1]],
  [[1,0,0],[1,1,1]],
  [[0,0,1],[1,1,1]]
];

const state = {
  board: [], piece: null, next: null, score: 0, lines: 0, level: 1,
  chaos: 0, running: false, paused: false, gameOver: false,
  lastDrop: 0, eventTimer: 0, nextEventAt: 15500,
  activeEvent: null, eventUntil: 0, eventCooldown: 0,
  sheep: [], bombs: [], smoke: [], particles: [], waterCells: [],
  meteors: [], wreck: null, magnet: null, acid: null, lifted: 0,
  side: null, nextSideAt: 0,
  mini: null, sound: true, audio: null, musicTimer: null,
  seed: 1, rngState: 1, daily: false, time: 0, inputLocked: false
};

const EVENT_POOL = [
  {id:'sheep', name:'SHEEPOCALYPSE', icon:'🐑', weight:18, minLevel:1, duration:9000, desc:'Faune non autorisée dans la zone de jeu.'},
  {id:'water', name:'LIQUID BLOCKS', icon:'💧', weight:15, minLevel:1, duration:8500, desc:'Les blocs perdent temporairement tout respect pour la géométrie.'},
  {id:'bomb', name:'BOMB DELIVERY', icon:'💣', weight:16, minLevel:1, duration:10000, desc:'Un colis explosif a été ajouté à la logistique.'},
  {id:'tank', name:'QUESTIONABLE SUPPORT', icon:'🪖', weight:12, minLevel:2, duration:8500, desc:'Un tank allié arrive. La notion d’allié reste à définir.'},
  {id:'blackout', name:'POWER SAVING MODE', icon:'🌑', weight:13, minLevel:2, duration:7000, desc:'Visibilité réduite pour économiser absolument rien.'},
  {id:'glitch', name:'REALITY BUFFERING', icon:'📼', weight:12, minLevel:3, duration:7500, desc:'La réalité a perdu quelques paquets.'},
  {id:'miniworld', name:'STRUCTURAL BREACH', icon:'🌀', weight:9, minLevel:3, duration:0, desc:'La pile vient de s’ouvrir sur autre chose.'},
  {id:'duck', name:'DUCK INSPECTION', icon:'🦆', weight:10, minLevel:1, duration:4500, desc:'Aucun changement mécanique. Probablement.'},
  // The destructive half of the catalogue: these ones actually take the stack
  // apart instead of merely annoying it.
  {id:'meteor', name:'PLUIE DE MÉTÉORES', icon:'☄️', weight:13, minLevel:2, duration:9000, desc:'Le ciel dépose des objets non sollicités. Cratères garantis.'},
  {id:'wreck', name:'PERMIS DE DÉMOLIR', icon:'🏗️', weight:11, minLevel:3, duration:9500, desc:'Une boule de démolition traverse le chantier. Personne n’a signé.'},
  {id:'magnet', name:'AIMANT INDUSTRIEL', icon:'🧲', weight:11, minLevel:3, duration:7500, desc:'Tout ce qui est métallique part d’un seul côté. Tout est métallique.'},
  {id:'acid', name:'PLUIE ACIDE', icon:'🧪', weight:12, minLevel:2, duration:8000, desc:'Le pH du niveau est désormais un problème de sécurité.'},
  {id:'gravity', name:'GRAVITÉ RÉSILIÉE', icon:'🙃', weight:10, minLevel:4, duration:8500, desc:'La pile décolle. Le contrat de gravité arrivait à échéance.'},
  {id:'bsod', name:'ERREUR FATALE', icon:'💀', weight:9, minLevel:2, duration:4200, desc:'Le système a cessé de fonctionner. La partie, elle, continue.'},
  {id:'ad', name:'PAUSE SPONSORISÉE', icon:'📺', weight:9, minLevel:1, duration:5200, desc:'Ce message est diffusé au milieu de ta grille. Bon courage.'}
];

function emptyBoard(){ return Array.from({length:ROWS},()=>Array(COLS).fill(0)); }

// Every draw in the game goes through this one generator, so a daily run deals
// the same pieces and the same incidents to everyone.
function seedRun(seed){ state.seed=seed>>>0||1; state.rngState=state.seed; }
function rng(){
  let t=state.rngState+=0x6d2b79f5;
  t=Math.imul(t^t>>>15,t|1);
  t^=t+Math.imul(t^t>>>7,t|61);
  return ((t^t>>>14)>>>0)/4294967296;
}
function rand(n){ return Math.floor(rng()*n); }
function todaySeed(d=new Date()){
  const key=`${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
  let h=2166136261;
  for(const ch of key){h^=ch.charCodeAt(0);h=Math.imul(h,16777619);}
  return Math.abs(h>>>0);
}

const BEST_KEY='stack-panic.best.v1';
function readBest(){ try{ return JSON.parse(localStorage.getItem(BEST_KEY)||'{}'); }catch{ return {}; } }
function bestFor(daily){
  const best=readBest();
  if(daily) return best.dailySeed===todaySeed()?(best.daily||0):0;
  return best.free||0;
}
function recordBest(score,daily){
  const best=readBest();
  const previous=bestFor(daily);
  if(score<=previous) return false;
  if(daily){ best.daily=score; best.dailySeed=todaySeed(); } else { best.free=score; }
  try{ localStorage.setItem(BEST_KEY,JSON.stringify(best)); }catch{ /* private window */ }
  return true;
}
const SCORE_LEVEL_CAP=10;
function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
function formatScore(v){ return String(v).padStart(6,'0'); }

function makePiece(){
  const type = rand(SHAPES.length);
  return { matrix: SHAPES[type].map(r=>r.slice()), x: Math.floor(COLS/2)-2, y:-1, color:1+rand(7), type };
}

function rotate(matrix){ return matrix[0].map((_,i)=>matrix.map(row=>row[i]).reverse()); }
function collides(piece, dx=0, dy=0, matrix=piece.matrix){
  for(let y=0;y<matrix.length;y++) for(let x=0;x<matrix[y].length;x++) if(matrix[y][x]){
    const bx=piece.x+x+dx, by=piece.y+y+dy;
    if(bx<0||bx>=COLS||by>=ROWS) return true;
    if(by>=0 && state.board[by][bx]) return true;
  }
  return false;
}

function merge(){
  const p=state.piece;
  p.matrix.forEach((row,y)=>row.forEach((v,x)=>{
    const by=p.y+y, bx=p.x+x;
    if(v && by>=0 && by<ROWS && bx>=0 && bx<COLS) state.board[by][bx]=p.color;
  }));
  clearLines();
  spawn();
}

function clearLines(){
  let cleared=0;
  for(let y=ROWS-1;y>=0;y--){
    if(state.board[y].every(Boolean)){
      state.board.splice(y,1); state.board.unshift(Array(COLS).fill(0)); cleared++; y++;
    }
  }
  if(cleared){
    // Incidents can level far more than four rows at once — a settling flood,
    // a wrecking ball, the stack coming back down. Reading past the end of the
    // table used to turn the score into NaN for the rest of the run.
    const table=[0,100,300,500,800];
    // Levels keep rising every 30 s, but the score multiplier stops at 10 so
    // the scoring rate stays bounded (the leaderboard rejects impossible rates).
    state.score += (table[Math.min(cleared,4)] + Math.max(0,cleared-4)*400)*Math.min(state.level,SCORE_LEVEL_CAP);
    state.lines += cleared;
    state.level = 1 + Math.floor(state.lines/8);
    state.chaos = clamp(state.chaos + cleared*8,0,100);
    burst(180, 360-cleared*20, cleared*22);
    sfx('clear',cleared);
    screenKick('shake',260);
  }
}

function spawn(){
  state.piece=state.next||makePiece();
  state.next=makePiece();
  state.piece.x=Math.floor(COLS/2)-Math.ceil(state.piece.matrix[0].length/2);
  state.piece.y=-1;
  if(collides(state.piece,0,0)) endGame();
  drawNext();
}

function move(dx){ if(canInput()&&!collides(state.piece,dx,0)){state.piece.x+=dx;sfx('move');} }
function softDrop(){ if(!canInput())return; if(!collides(state.piece,0,1)){state.piece.y++;state.score+=1;} else merge(); state.lastDrop=performance.now(); }
function hardDrop(){
  if(!canInput())return;
  let d=0; while(!collides(state.piece,0,1)){state.piece.y++;d++;}
  state.score+=d*2; sfx('drop'); merge(); state.lastDrop=performance.now();
}
function rotatePiece(){
  if(!canInput())return;
  const r=rotate(state.piece.matrix);
  for(const kick of [0,-1,1,-2,2]) if(!collides(state.piece,kick,0,r)){state.piece.matrix=r;state.piece.x+=kick;sfx('rotate');return;}
}
function canInput(){ return state.running&&!state.paused&&!state.gameOver&&!state.inputLocked&&!state.mini; }

function dropInterval(){ return Math.max(105, 720 - (state.level-1)*55); }

function update(t){
  state.time=t;
  if(state.running&&!state.paused&&!state.gameOver){
    if(!state.mini && t-state.lastDrop>dropInterval()){ softDrop(); }
    updateEvents(t);
    updateParticles();
    updateSheep(t);
    updateBombs(t);
    updateTank(t);
    updateWater(t);
    updateMeteors(t);
    updateWreck(t);
    updateMagnet(t);
    updateAcid(t);
    updateSmoke();
    if(state.mini) updateMini(t);
  }
  draw();
  requestAnimationFrame(update);
}

function draw(){
  drawBackground();
  drawBoard();
  if(state.piece&&!state.mini) drawGhostAndPiece();
  drawEventActors();
  drawOverlay();
  updateHud();
}

function drawBackground(){
  const g=ctx.createLinearGradient(0,0,0,canvas.height);
  g.addColorStop(0,'#09101d'); g.addColorStop(1,'#04060b'); ctx.fillStyle=g; ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.strokeStyle='rgba(67,239,255,.055)';ctx.lineWidth=1;
  for(let x=0;x<=COLS;x++){ctx.beginPath();ctx.moveTo(x*CELL,0);ctx.lineTo(x*CELL,canvas.height);ctx.stroke();}
  for(let y=0;y<=ROWS;y++){ctx.beginPath();ctx.moveTo(0,y*CELL);ctx.lineTo(canvas.width,y*CELL);ctx.stroke();}
  const dangerY = canvas.height * .26;
  ctx.fillStyle='rgba(255,95,104,.035)';ctx.fillRect(0,0,canvas.width,dangerY);
  ctx.strokeStyle='rgba(255,95,104,.18)';ctx.setLineDash([6,8]);ctx.beginPath();ctx.moveTo(0,dangerY);ctx.lineTo(canvas.width,dangerY);ctx.stroke();ctx.setLineDash([]);
}

function drawBoard(){
  state.board.forEach((row,y)=>row.forEach((v,x)=>{ if(v) drawCell(ctx,x*CELL,y*CELL,COLORS[v],1); }));
}

function drawCell(c,x,y,color,alpha=1,scale=1){
  c.save();c.globalAlpha=alpha;
  const m=(1-scale)*CELL/2; x+=m;y+=m;const s=CELL*scale;
  c.fillStyle=color;c.fillRect(x+2,y+2,s-4,s-4);
  c.fillStyle='rgba(255,255,255,.19)';c.fillRect(x+4,y+4,s-8,4);
  c.fillStyle='rgba(0,0,0,.22)';c.fillRect(x+4,y+s-8,s-8,4);
  c.strokeStyle='rgba(255,255,255,.26)';c.strokeRect(x+2.5,y+2.5,s-5,s-5);
  c.restore();
}

function drawGhostAndPiece(){
  if(!state.piece)return;
  const ghost={...state.piece,y:state.piece.y};
  while(!collides(ghost,0,1)) ghost.y++;
  ghost.matrix.forEach((row,y)=>row.forEach((v,x)=>{if(v&&ghost.y+y>=0)drawCell(ctx,(ghost.x+x)*CELL,(ghost.y+y)*CELL,COLORS[state.piece.color],.12,.88)}));
  state.piece.matrix.forEach((row,y)=>row.forEach((v,x)=>{if(v&&state.piece.y+y>=0)drawCell(ctx,(state.piece.x+x)*CELL,(state.piece.y+y)*CELL,COLORS[state.piece.color],1,.94)}));
}

function drawNext(){
  nctx.clearRect(0,0,nextCanvas.width,nextCanvas.height);nctx.fillStyle='#090c16';nctx.fillRect(0,0,nextCanvas.width,nextCanvas.height);
  if(!state.next)return; const m=state.next.matrix;const s=26;const ox=(nextCanvas.width-m[0].length*s)/2,oy=(nextCanvas.height-m.length*s)/2;
  m.forEach((row,y)=>row.forEach((v,x)=>{if(v){nctx.fillStyle=COLORS[state.next.color];nctx.fillRect(ox+x*s+2,oy+y*s+2,s-4,s-4);nctx.strokeStyle='rgba(255,255,255,.3)';nctx.strokeRect(ox+x*s+2.5,oy+y*s+2.5,s-5,s-5);}}));
}

function updateHud(){
  scoreEl.textContent=formatScore(state.score);linesEl.textContent=state.lines;levelEl.textContent=state.level;
  chaosFill.style.width=state.chaos+'%';
  chaosLabel.textContent = state.chaos<25?'NORMAL':state.chaos<50?'WEIRD':state.chaos<75?'UNSTABLE':state.chaos<95?'WTF':'REALITY FAIL';
}
