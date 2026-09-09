const $=id=>document.getElementById(id);
let publicData=null,account=null,servants=[],visible=[],picked=new Set(),pendingBackup=null;
const classCN={saber:'剑阶',archer:'弓阶',lancer:'枪阶',rider:'骑阶',caster:'术阶',assassin:'杀阶',berserker:'狂阶',ruler:'裁阶',avenger:'仇阶',moonCancer:'月癌',alterEgo:'丑阶',foreigner:'降临者',pretender:'伪阶',shielder:'盾阶',beast:'兽阶'};

function message(text,error=false){let el=$('notice');el.textContent=text;el.className='notice'+(error?' error':'');clearTimeout(message.timer);message.timer=setTimeout(()=>el.classList.add('hidden'),5000)}
function integer(value,fallback=0){let n=Number.parseInt(value,10);return Number.isFinite(n)?n:fallback}
function faceOf(s){return s.face?`<img src="${s.face}" alt="" loading="lazy" referrerpolicy="no-referrer">`:`<span class="avatar">${s.name.slice(0,1)}</span>`}
function matchesGroups(s,groups){let traits=new Set(s.traits);return !groups.length||groups.some(group=>group.every(id=>traits.has(id)))}

async function loadPublicData(){let response=await fetch('./data/public-data.json');if(!response.ok)throw Error('公共国服资料加载失败');publicData=await response.json()}

function parseBackup(data,profileIndex){let user=(data.users||[])[profileIndex];if(!user||String(user.region||'').toLowerCase()!=='cn')throw Error('请选择国服账号');let servantByCollection=new Map(publicData.servants.map(s=>[s.collectionNo,s.id])),ceByCollection=new Map(publicData.bondCraftEssences.map(e=>[e.collectionNo,e.id])),ownedServants=new Map(),ownedEquips=new Map();Object.entries(user.servants||{}).forEach(([collection,row])=>{let cur=row&&row.cur||{},bond=integer(row&&row.bond),ascension=integer(cur.ascension);if(bond<=0&&ascension<=0)return;let id=servantByCollection.get(integer(collection));if(id)ownedServants.set(id,{bond,ascension})});Object.entries(user.craftEssences||{}).forEach(([collection,row])=>{if(integer(row&&row.status)<=0)return;let id=ceByCollection.get(integer(collection));if(id)ownedEquips.set(id,{limitBreak:integer(row.limitCount),level:integer(row.lv,1)})});return{servants:ownedServants,equips:ownedEquips}}

function decodeToplogin(text){let encoded=decodeURIComponent(text.trim()).replace(/-/g,'+').replace(/_/g,'/');encoded+='='.repeat((4-encoded.length%4)%4);let binary=atob(encoded),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));return JSON.parse(new TextDecoder().decode(bytes))}
function walkCollections(value,visit){if(Array.isArray(value)){value.forEach(v=>walkCollections(v,visit));return}if(!value||typeof value!=='object')return;Object.entries(value).forEach(([key,child])=>{if(Array.isArray(child)&&child.every(x=>x&&typeof x==='object'))visit(key.toLowerCase(),child);walkCollections(child,visit)})}
function parseToplogin(text){let data=decodeToplogin(text),ownedServants=new Map(),ownedEquips=new Map();walkCollections(data,(key,rows)=>{if(['usersvt','servants','servantstatus','svts'].includes(key)){rows.forEach(row=>{let id=integer(row.svtId??row.servantId??row.id);if(id>=9000000)ownedEquips.set(id,{limitBreak:integer(row.limitCount??row.limitBreak),level:integer(row.lv??row.level,1)});else if(id>0)ownedServants.set(id,{bond:integer(row.friendshipRank??row.bondLevel??row.friendshipLevel),level:integer(row.lv??row.level,1)})})}else if(['userequip','equips','craftessences','ces'].includes(key)){rows.forEach(row=>{let id=integer(row.svtId??row.equipId??row.id);if(id>0)ownedEquips.set(id,{limitBreak:integer(row.limitCount??row.limitBreak),level:integer(row.lv??row.level,1)})})}});if(!ownedServants.size)throw Error('没有找到玩家从者数据');return{servants:ownedServants,equips:ownedEquips}}

function finishImport(parsed){account=parsed;servants=publicData.servants.filter(s=>account.servants.has(s.id)).map(s=>({...s,...account.servants.get(s.id)}));picked.clear();$('workspace').classList.remove('hidden');$('analysis').classList.add('hidden');$('accountState').textContent=`已识别 ${servants.length} 位从者 · ${account.equips.size} 张目标羁绊礼装`;buildFilters();filter();message('Box 识别成功，原始文件没有上传或保存')}

$('jsonFile').onchange=async event=>{let file=event.target.files[0];pendingBackup=null;$('profileRow').classList.add('hidden');if(!file)return;$('fileName').textContent=file.name;try{let data=JSON.parse(await file.text()),profiles=(data.users||[]).map((user,index)=>({user,index})).filter(x=>String(x.user.region||'').toLowerCase()==='cn');if(!profiles.length)throw Error('文件中没有国服账号');pendingBackup=data;$('profileSelect').innerHTML='';profiles.forEach((x,i)=>$('profileSelect').add(new Option(x.user.name||`国服账号 ${i+1}`,x.index)));$('profileRow').classList.remove('hidden');if(profiles.length===1)$('jsonImportBtn').click();else message(`找到 ${profiles.length} 个国服账号，请选择自己的账号`)}catch(error){message(`JSON 无法识别：${error.message}`,true)}};
$('jsonImportBtn').onclick=()=>{if(!pendingBackup)return message('请先选择 Chaldea JSON',true);try{finishImport(parseBackup(pendingBackup,integer($('profileSelect').value)))}catch(error){message(error.message,true)}};
$('textImportBtn').onclick=()=>{let text=$('captureText').value.trim();if(!text)return message('请先粘贴 toplogin 字符串',true);try{finishImport(parseToplogin(text))}catch(error){message(`无法识别：${error.message}`,true)}};

function buildFilters(){let classes=[...new Set(servants.map(s=>s.className).filter(Boolean))].sort(),traitIds=[...new Set(servants.flatMap(s=>s.traits))];$('classFilter').innerHTML='<option value="">全部职阶</option>'+classes.map(x=>`<option value="${x}">${classCN[x]||x}</option>`).join('');let options='<option value="">不限</option>'+traitIds.sort((a,b)=>(publicData.traitNames[a]||'').localeCompare(publicData.traitNames[b]||'','zh-CN')).map(id=>`<option value="${id}">${publicData.traitNames[id]||`特性 ${id}`}</option>`).join('');$('traitA').innerHTML=options;$('traitB').innerHTML=options}
function filter(){let cls=$('classFilter').value,a=integer($('traitA').value),b=integer($('traitB').value),q=$('search').value.trim().toLowerCase();visible=servants.filter(s=>(!cls||s.className===cls)&&(!a||s.traits.includes(a))&&(!b||s.traits.includes(b))&&(!q||s.name.toLowerCase().includes(q)));$('candidateCount').textContent=`符合条件：${visible.length} 位`;drawServants()}
function drawServants(){$('servantList').innerHTML=visible.length?visible.map(s=>`<button class="servant-card ${picked.has(s.id)?'picked':''}" data-id="${s.id}">${faceOf(s)}<strong>${s.name}</strong><small>${classCN[s.className]||s.className}${s.bond?` · 羁绊${s.bond}`:''}</small><i>${picked.has(s.id)?'已选':'选择'}</i></button>`).join(''):'<p>没有符合条件的从者</p>';document.querySelectorAll('.servant-card').forEach(el=>el.onclick=()=>toggle(integer(el.dataset.id)))}
function toggle(id){if(picked.has(id))picked.delete(id);else if(picked.size<6)picked.add(id);else return message('队伍最多选择 6 名从者',true);drawServants();drawPicked()}
function drawPicked(){let rows=servants.filter(s=>picked.has(s.id));$('pickedList').innerHTML=rows.map(s=>`<button data-remove="${s.id}">${faceOf(s)}<span>${s.name} ×</span></button>`).join('');$('selectedCount').textContent=`已选 ${picked.size} / 6`;document.querySelectorAll('[data-remove]').forEach(el=>el.onclick=()=>toggle(integer(el.dataset.remove)))}
['classFilter','traitA','traitB'].forEach(id=>$(id).onchange=filter);$('search').oninput=filter;

$('analyzeBtn').onclick=()=>{let selected=servants.filter(s=>picked.has(s.id)),rows=[];publicData.bondCraftEssences.forEach(ce=>{let owned=account.equips.get(ce.id);if(!owned)return;let effect=owned.limitBreak>=4?ce.mlb:ce.normal,groups=effect.targetGroups||[],covered=visible.filter(s=>matchesGroups(s,groups));if(!covered.length||!selected.every(s=>matchesGroups(s,groups)))return;let suggested=[...selected,...covered.filter(s=>!picked.has(s.id))].slice(0,6);rows.push({...ce,percent:effect.percent,covered,suggested,coverage:covered.length})});rows.sort((a,b)=>b.coverage-a.coverage||b.percent-a.percent||a.name.localeCompare(b.name,'zh-CN'));drawResults(rows)};
function portrait(s,locked=false){return`<button class="portrait ${locked?'locked':''}" data-pick="${s.id}">${faceOf(s)}<small>${s.name}</small></button>`}
function drawResults(rows){$('analysis').classList.remove('hidden');$('ceList').innerHTML=rows.length?rows.map((r,i)=>`<article class="ce-result"><div class="ce-left"><span class="rank">${i+1}</span>${r.icon?`<img src="${r.icon}" alt="${r.name}" loading="lazy" referrerpolicy="no-referrer">`:'<div class="ce-placeholder">CE</div>'}<strong>${r.name}</strong><small>${r.target} · +${r.percent}%</small></div><div class="ce-right"><div class="coverage-title"><span>推荐 6 人组合</span><b>覆盖 ${r.coverage}/${visible.length}</b></div><div class="portrait-row">${r.suggested.map(s=>portrait(s,picked.has(s.id))).join('')}</div><details><summary>查看全部 ${r.coverage} 名适用从者</summary><div class="portrait-row">${r.covered.map(s=>portrait(s,picked.has(s.id))).join('')}</div></details></div></article>`).join(''):'<div class="panel">当前持有礼装中，没有能覆盖全部已选队员的特定对象羁绊礼装。</div>';document.querySelectorAll('[data-pick]').forEach(el=>el.onclick=()=>toggle(integer(el.dataset.pick)));$('analysis').scrollIntoView({behavior:'smooth'})}

loadPublicData().catch(error=>message(error.message,true));

if(document.modelContext?.registerTool){
  document.modelContext.registerTool({
    name:'configure_servant_filters',title:'设置从者筛选',
    description:'在当前 FGO 羁绊配队页面设置职阶、两个特性和名字搜索条件。',
    inputSchema:{type:'object',properties:{className:{type:'string'},traitA:{type:'integer'},traitB:{type:'integer'},search:{type:'string'}},additionalProperties:false},
    annotations:{readOnlyHint:false,untrustedContentHint:false},
    execute(input){
      if(!account)throw Error('请先在页面中导入玩家数据');
      $('classFilter').value=input.className||'';$('traitA').value=input.traitA||'';$('traitB').value=input.traitB||'';$('search').value=input.search||'';filter();
      return{candidateCount:visible.length,selectedCount:picked.size};
    }
  });
}
