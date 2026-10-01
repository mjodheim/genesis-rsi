'use strict';
const fs=require('node:fs'),vm=require('node:vm');
// Only browser initialization is adapted. Native production rotate/collides and
// board functions execute unchanged; no gameplay function is replaced.
const element=()=>({getContext:()=>({}),style:{},classList:{add(){},remove(){}},textContent:''});
const c=vm.createContext({document:{getElementById:element},localStorage:{getItem:()=>null,setItem(){}}});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),c,{timeout:1000});
let passed=0,total=0;const failed=[];
function check(id,test){total++;try{if(test()){passed++;return;}}catch(e){}failed.push(id);}
const matrices=[[[1]],[[1,2]],[[1],[2]],[[1,2],[3,4]],[[1,2,3],[4,5,6]],
 [[1,2],[3,4],[5,6]],[[0,1,0],[1,1,1]],[[1,0,0],[1,1,1]]];
for(let i=0;i<matrices.length;i++){
  const matrix=matrices[i];
  const expected=Array.from({length:matrix[0].length},(_,x)=>matrix.map(row=>row[x]).reverse());
  check("rotation-"+i,()=>JSON.stringify(vm.runInContext("rotate("+JSON.stringify(matrix)+")",c,{timeout:1000}))===JSON.stringify(expected));
}
for(const x of [-2,-1,0,1,5,8,9,10,11]){
  for(const y of [-2,-1,0,1,18,19,20,21]){
    const expected=x<0||x>=10||y>=20;
    check("board-edge-"+x+"-"+y,()=>vm.runInContext(
      "state.board=emptyBoard();collides({matrix:[[1]],x:"+x+",y:"+y+"})",c,{timeout:1000})===expected);
  }
}
for(const occupied of [false,true]){
  check("board-content-"+occupied,()=>vm.runInContext(
    "state.board=emptyBoard();state.board[5][5]="+(occupied?1:0)+";collides({matrix:[[1]],x:5,y:5})",c,{timeout:1000})===occupied);
}
process.stdout.write(JSON.stringify({passed,total,failed})+"\n");
