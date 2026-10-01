'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context, {timeout:1000});
const L = context.FruitLogic;
let passed = 0, total = 0;
const failed = [];
function check(id, test){ total++; try {if(test()){passed++;return;}}catch(e){} failed.push(id); }
for(const grow of [0, 1, 2]){
  for(const offset of [0, 3, 8]){
    const own = {alive:true,grow,body:[{x:offset+1,y:2},{x:offset,y:2}]};
    const other = {alive:true,grow:0,body:[{x:offset+1,y:5},{x:offset,y:5}]};
    const s = {snakes:[own,other]};
    const key = (x,y)=>y*21+x;
    check("own-tail-"+grow+"-"+offset,()=>L.occupied(s,own).has(key(offset,2)) === Boolean(grow));
    check("other-tail-"+grow+"-"+offset,()=>L.occupied(s,own).has(key(offset,5)));
    check("no-mover-"+grow+"-"+offset,()=>L.occupied(s).size === 4);
  }
}
for(const x of [1, 7, 13]){
  const sn = {body:[{x,y:10}]};
  const goal = {x:x+1,y:10};
  const key = (a,b)=>b*21+a;
  check("blocked-goal-"+x,()=>{const d=L.bfs({},sn,goal,new Set([key(goal.x,goal.y)]));return d && d.x===1 && d.y===0;});
  check("blocked-route-"+x,()=>L.bfs({},sn,{x:x+2,y:10},new Set([key(x-1,10),key(x+1,10),key(x,9),key(x,11)]))===null);
  check("detour-"+x,()=>{const d=L.bfs({},sn,{x:x+2,y:10},new Set([key(x+1,10)]));return d && d.x===0 && d.y===-1;});
}
process.stdout.write(JSON.stringify({passed,total,failed})+"\n");
