'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context, {timeout:1000});
const L = context.GooseLogic;
let passed = 0, total = 0;
const failed = [];
function check(id, test){ total++; try {if(test()){passed++;return;}}catch(e){} failed.push(id); }
for(const horizontal of [false,true]){
  const car={x:480,y:290,horizontal};
  const hw=horizontal?30:15,hh=horizontal?15:30;
  for(const r of [1,5,13]){
    for(const [dx,dy] of [[0,0],[hw,0],[0,hh],[hw+r-0.1,0],[0,hh+r-0.1],[hw+r,0],[0,hh+r],[40,40]]){
      const cx=Math.max(-hw,Math.min(hw,dx)), cy=Math.max(-hh,Math.min(hh,dy));
      const expected=Math.hypot(dx-cx,dy-cy)<r;
      check("collision-"+horizontal+"-"+r+"-"+dx+"-"+dy,()=>L.carHits(car,480+dx,290+dy,r)===expected);
    }
  }
}
for(const elapsed of [0,1,450,899,900,901,1800]){
  for(const stun of [0,1]){
    check("honk-"+elapsed+"-"+stun,()=>{
      const s=L.newGame(123); s.time=elapsed; s.goose.honkAt=0; s.goose.stun=stun;
      return L.honk(s)===(elapsed>=900 && stun===0);
    });
  }
}
process.stdout.write(JSON.stringify({passed,total,failed})+"\n");
