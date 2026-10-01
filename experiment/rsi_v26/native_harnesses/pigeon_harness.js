'use strict';
const fs=require('node:fs'),vm=require('node:vm');
const c=vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),c,{timeout:1000});
const L=c.PigeonLogic;
let passed=0,total=0;const failed=[];
function check(id,test){total++;try{if(test()){passed++;return;}}catch(e){}failed.push(id);}
for(const kind of Object.keys(L.KINDS)){
  for(const statue of L.STATUES){
    const expected=L.KINDS[kind].target==='any'||L.KINDS[kind].target===statue.id;
    check("accepts-"+kind+"-"+statue.id,()=>L.accepts(statue,kind)===expected);
    check("route-target-"+kind+"-"+statue.id,()=>{
      const s=L.newGame(123);
      s.pigeons=[{id:1,state:'flying',kind,path:[],hungry:true}];
      const actual=L.setPath(s,1,[{x:statue.x,y:statue.y}]);
      return actual===(expected?statue.id:null);
    });
  }
}
for(const x of [-80,-21,-20,-1,0,480,960,980,981,1040]){
  for(const y of [-80,-21,-20,0,300,600,620,621,680]){
    check("path-clamp-"+x+"-"+y,()=>{
      const s=L.newGame(123);s.pigeons=[{id:1,state:'flying',kind:'city',path:[],hungry:true}];
      L.setPath(s,1,[{x,y}]);
      const p=s.pigeons[0].path[0];
      return p.x===Math.max(-20,Math.min(980,x))&&p.y===Math.max(-20,Math.min(620,y));
    });
  }
}
process.stdout.write(JSON.stringify({passed,total,failed})+"\n");
