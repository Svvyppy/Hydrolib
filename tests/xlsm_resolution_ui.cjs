// Exercise the embedded script with a minimal DOM; no browser dependencies.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.value='';this.textContent='';this.checked=false;this.hidden=false;this.disabled=false;this.events={};}
 append(...nodes){this.children.push(...nodes);}
 addEventListener(type,callback){this.events[type]=callback;}
 querySelectorAll(tag){return this.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...c.querySelectorAll(tag)]);}
 focus(){} select(){this.selected=true;} click(){if(this.onclick)return this.onclick();}
}
(async()=>{
const html=fs.readFileSync(process.argv[2],'utf8'), els={};
for(const id of ['data','context','workflow','search','pendingOnly','counts','progress','remaining','copy','save','json','cards','empty','allOurs','allTheirs','reset','status','manual'])els[id]=new Element('div');
els.data.textContent=html.split('<script id="data" type="application/json">')[1].split('</script>')[0];
const context=vm.createContext({document:{getElementById:id=>els[id],createElement:tag=>new Element(tag)},navigator:{clipboard:{writeText:async()=>{throw Error('denied');}}},Blob,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}},setTimeout:f=>f()});
const script=html.split('<script>')[1].split('</script>')[0];new vm.Script(script).runInContext(context);
assert.equal(els.copy.disabled,true);assert.equal(els.cards.children.length,3);
const radios=i=>els.cards.children[i].querySelectorAll('input');
radios(0)[0].events.change();radios(1)[1].events.change();radios(2)[0].events.change();
assert.equal(els.copy.disabled,false);const output=JSON.parse(els.json.value);assert.deepEqual(output.conflicts.map(c=>c.choice),['ours','theirs','ours']);
els.pendingOnly.checked=true;els.pendingOnly.onchange();assert(els.cards.children.every(c=>c.hidden));
els.pendingOnly.checked=false;els.search.value='FIRST';els.search.oninput();assert.equal(els.cards.children.filter(c=>!c.hidden).length,1);
els.allTheirs.onclick();assert(JSON.parse(els.json.value).conflicts.every(c=>c.choice==='theirs'));
els.reset.onclick();assert.equal(els.copy.disabled,true);assert(JSON.parse(els.json.value).conflicts.every(c=>c.choice===null));
els.allOurs.onclick();radios(1)[1].events.change();await els.copy.onclick();assert.equal(els.manual.open,true);assert.equal(els.json.selected,true);assert.match(els.status.textContent,/Скопируйте/);els.save.onclick();
console.log(JSON.stringify(output));
})().catch(error=>{console.error(error);process.exit(1);});
