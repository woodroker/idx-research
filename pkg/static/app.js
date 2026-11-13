const KLN=[[/corporate/i,'Korporasi'],[/individual/i,'Individu'],[/mutual\s*funds?/i,'Reksa Dana'],[/investment\s+advis\w*/i,'Penasihat Investasi'],[/investment\s+manager/i,'Manajer Investasi'],[/commanditaire.*/i,'Persekutuan Komanditer (CV)'],[/educational\s+inst\w*/i,'Lembaga Pendidikan'],[/^firm$/i,'Firma'],[/pension\s+funds?/i,'Dana Pensiun'],[/insurance/i,'Asuransi'],[/foundation/i,'Yayasan'],[/securities\s+company/i,'Perusahaan Efek'],[/financial\s+institution\w*/i,'Lembaga Keuangan'],[/^bank$/i,'Bank'],[/government/i,'Pemerintah'],[/cooperatives?/i,'Koperasi']];
const kln=nm=>{let t=String(nm==null?'':nm).replace(/_/g,' ').replace(/\s+/g,' ').trim(),o='';const m=t.match(/^(local|foreign)\s+(.*)$/i);if(m){o=m[1].toLowerCase()==='local'?'Lokal':'Asing';t=m[2]}const q=t.match(/\(([^)]*)\)\s*$/),sfx=q?q[1]:'',base=q?t.replace(/\s*\([^)]*\)\s*$/,''):t,hit=KLN.find(([r])=>r.test(base)),lb=hit?hit[1]:base.toLowerCase().replace(/\b\w/g,c=>c.toUpperCase()),ex=sfx&&!/^(id|cv|mf|pf|is|fd|ib|sc)$/i.test(sfx)?' ('+sfx+')':'';return (o?o+' · ':'')+lb+ex};
const $=s=>document.querySelector(s),th=Math.tanh,D={px:{},days:{},tipe:{},sat:{},kl:{},nm:{},klc:[]};
/* ===== SQLite (screener.db) menggantikan IndexedDB + cloud =====
   Data dibaca dari /api/data; upload diparse & disimpan di server. IndexedDB lama hanya DIBACA sekali untuk migrasi. */
window.__wait=true;let USR=[];
const API={
 async load(){const r=await fetch('/api/data',{cache:'no-cache'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()},
 apply(j){window.__av=(window.__av||0)+1;const snap=()=>{const d=Object.keys(D.px).sort();const P=d.length?D.px[d.at(-1)]:null,m={};if(P)for(const c in P){const v=P[c]&&P[c][0];if(v)m[c]=v}return m},old=snap();for(const k of ['px','days','tipe','sat','kl','nm']){const t=D[k];for(const x in t)delete t[x];Object.assign(t,j[k]||{})}
  D.klc=j.klc||[];D.aff=j.aff||{};const base=D.hc||{},h={};for(const c in base)h[c]=Object.assign({},base[c]);for(const c in (j.hc||{}))h[c]=Object.assign({},h[c],j.hc[c]);D.hc=h;const nw=snap();window.__tick={};for(const c in nw)if(old[c]&&old[c]!==nw[c])window.__tick[c]=nw[c]>old[c]?'up':'dn'},
 async refresh(){this.apply(await this.load());window.__wait=false;run();renderWL();flashTicks();COUNTERS_READY=true}
};
const IDB={o(){return new Promise((r,j)=>{setTimeout(()=>j(new Error('idb timeout')),10000);const q=indexedDB.open('ksei',1);q.onupgradeneeded=()=>q.result.createObjectStore('kv');q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error)})},async get(){const d=await this.o();return new Promise((r,j)=>{const q=d.transaction('kv').objectStore('kv').get('usr');q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error)})}};
async function migrateLegacy(manual){
 let items=[];try{items=(await IDB.get())||[]}catch(e){}
 try{const l=JSON.parse(localStorage.getItem('ksei_usr')||'[]');if(Array.isArray(l))items=items.concat(l)}catch(e){}
 if(!items.length){if(manual)$('#log').innerHTML='ℹ Tidak ada data lama di browser ini.';return}
 const r=await fetch('/api/migrate/legacy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items,mode:'fill'})});
 const j=await r.json();if(!j.ok)throw Error(j.error||'migrasi gagal');
 const c=j.summary||{};$('#log').innerHTML='✓ Migrasi data lama browser → SQLite: '+Object.entries(c).map(([k,v])=>v+' '+k).join(', ')+(j.conflicts&&j.conflicts.length?'<br>⚠ '+j.conflicts.length+' dataset berbeda isi dengan database (database dipertahankan).':'')+'<br>Data di browser TIDAK dihapus.';
 await API.refresh()}
(async()=>{try{await API.refresh();wlLoad();
 try{const st=await (await fetch('/api/status')).json();if(st.ok&&!st.legacy_idb_migrated)await migrateLegacy(false)}catch(e){$('#log').innerHTML+='<br>⚠ Migrasi data lama browser gagal: '+e.message}
 }catch(e){window.__wait=false;$('#log').innerHTML='✗ Gagal memuat data dari database (SQLite): '+e.message+'<br>Pastikan server (run.bat) berjalan.'}})();
function save(x){if(x.k!=='hc')return;fetch('/api/hc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:x.data})}).then(r=>r.json()).then(j=>{if(!j.ok)throw Error(j.error)}).catch(e=>{$('#log').innerHTML+='<br>⚠ Gagal menyimpan jumlah saham ke database: '+e.message})}
const n=v=>typeof v==='number'?v:parseFloat(String(v??'').replace(/,/g,''))||0;
const iso=v=>{
 if(v instanceof Date)return new Date(v.getTime()+432e5).toISOString().slice(0,10);
 if(typeof v==='string'){
  const s=v.trim(),m=s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if(m)return `${m[1]}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}`;
  const d=new Date(s);if(!Number.isNaN(d.getTime()))return d.toISOString().slice(0,10);
 }
 const d=new Date(Math.round((Number(v)-25569)*864e5));
 return Number.isNaN(d.getTime())?'':d.toISOString().slice(0,10)
};
const MO={JAN:1,FEB:2,MAR:3,APR:4,MEI:5,MAY:5,JUN:6,JUL:7,AGU:8,AUG:8,SEP:9,OKT:10,OCT:10,NOV:11,DES:12,DEC:12};
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

const LB={px:'Harga',days:'5% harian',tipe:'Tipe investor',sat:'≥1%',kl:'Klasifikasi'};
const setUploadProgress=(msg,show=true)=>{const p=$('#uploadProgress');if(!p)return;p.hidden=!show;$('#uploadStatus').textContent=msg;$('#uploadBtn').classList.toggle('busy',show);$('#f').disabled=show};
$('#f').onchange=async e=>{
 try{
  const files=[...(e.target.files||[])];if(!files.length)return;
  setUploadProgress('Mengunggah '+files.length+' file ke server…');
  const fd=new FormData();files.forEach(f=>fd.append('files',f));
  const r=await fetch('/api/upload',{method:'POST',body:fd});const j=await r.json();
  if(!j.results)throw Error(j.error||'upload gagal');
  setUploadProgress('Memuat data dari database…');
  const L=j.results.map(x=>x.ok?`✓ ${x.file} → ${LB[x.kind]||x.kind} ${x.dates.join(', ')} (${x.status})`+(x.warnings?' ⚠ '+x.warnings.join('; '):''):'✗ '+x.file+' ('+x.error+')');
  const ok=j.results.filter(x=>x.ok).length,bad=L.filter(x=>x[0]==='✗');
  if(ok){await API.refresh()}
  $('#log').innerHTML='✓ '+ok+' file disimpan ke database'+(bad.length?'<br>✗ '+bad.length+' gagal:<br>'+bad.join('<br>'):'')+'<br>Tanggal sama diperbarui; tanggal baru ditambahkan.';
  e.target.value='';setUploadProgress('',false)
 }catch(fatal){setUploadProgress('',false);$('#log').textContent='✗ Upload gagal: '+(fatal&&fatal.message||fatal);e.target.value=''}
};
const ffDateInput=$('#ffDate');if(ffDateInput)ffDateInput.value=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok'}).format(new Date());
$('#ffFile').onchange=async e=>{const file=e.target.files&&e.target.files[0],date=ffDateInput&&ffDateInput.value,log=$('#ffLog'),btn=$('#ffUploadBtn');if(!file)return;
 try{if(!date)throw Error('Pilih tanggal snapshot terlebih dahulu');btn.classList.add('busy');log.textContent='Memvalidasi dan memperbarui snapshot…';
  const fd=new FormData();fd.append('file',file);fd.append('as_of',date);const r=await fetch('/api/free-float/upload',{method:'POST',body:fd}),j=await r.json();if(!r.ok||!j.ok)throw Error(j.error||'Upload gagal');
  log.textContent=`✓ ${j.rows} emiten diperbarui · snapshot ${j.as_of}`;await loadFreeFloat();if(typeof pushDash==='function')pushDash();
 }catch(err){log.textContent='✕ '+(err&&err.message||err)}finally{btn.classList.remove('busy');e.target.value=''}};


let WL=[];
const SIDE_COUNTER_VALUES=new Map();
const DASH_COUNTER_VALUES=new Map();
let COUNTERS_READY=false;
let TG_FRESH_CODES=new Set(),TG_ROWS=[];
function formatCounter(v,digits=0,signed=false){const n=Number(v),abs=Math.abs(n).toLocaleString('id-ID',{minimumFractionDigits:digits,maximumFractionDigits:digits});return(signed&&n>0?'+':signed&&n<0?'−':'')+abs}
function counterMarkup(value,key,digits=0,signed=false,fresh=false){const n=Number(value);return`<span class="sidebar-counter" data-counter-key="${esc(key)}" data-counter-value="${n}" data-counter-digits="${digits}" data-counter-signed="${signed?1:0}" data-counter-fresh="${fresh?1:0}">${formatCounter(n,digits,signed)}</span>`}
const displayTGTagLabel=label=>label==='Batas ARA tersentuh'?'ARA Touched':label;
function animateSidebarCounters(animateNew=COUNTERS_READY){document.querySelectorAll('#tg .sidebar-counter,#wl .sidebar-counter').forEach(el=>{const key=el.dataset.counterKey,to=Number(el.dataset.counterValue),digits=Number(el.dataset.counterDigits)||0,signed=el.dataset.counterSigned==='1',fresh=el.dataset.counterFresh==='1';if(!key||!Number.isFinite(to))return;const from=SIDE_COUNTER_VALUES.get(key);SIDE_COUNTER_VALUES.set(key,to);if(fresh||from==null){if(fresh||animateNew){el.dataset.v=0;tween(el,to,v=>formatCounter(v,digits,signed))}else{el.textContent=formatCounter(to,digits,signed);el.dataset.v=to}}else if(from!==to){el.dataset.v=from;tween(el,to,v=>formatCounter(v,digits,signed))}else{el.textContent=formatCounter(to,digits,signed);el.dataset.v=to}delete el.dataset.counterFresh})}
function counterToken(raw){const sign=raw[0]==='-'||raw[0]==='−'?-1:1,explicitPlus=raw[0]==='+',minus=raw[0]==='−'?'−':'-',body=raw.replace(/^[+−-]/,''),seps=[...body.matchAll(/[.,]/g)],last=seps.at(-1),tail=last?body.length-last.index-1:0;let decimalSep='',groupSep='';if(seps.length){const unique=[...new Set(seps.map(x=>x[0]))];if(unique.length>1){decimalSep=last[0];groupSep=unique.find(x=>x!==decimalSep)}else if(tail>0&&tail<3)decimalSep=last[0];else if(tail===3)groupSep=last[0];if(groupSep)body.replaceAll(groupSep,'')}
 let normalized=body;if(groupSep)normalized=normalized.replaceAll(groupSep,'');if(decimalSep&&decimalSep!=='.')normalized=normalized.replace(decimalSep,'.');const value=Number(normalized)*sign;if(!Number.isFinite(value))return null;return{value,digits:decimalSep?tail:0,decimalSep,groupSep,explicitPlus,minus}}
function formatAutoCounter(value,m){let s=Math.abs(value).toFixed(m.digits),parts=s.split('.'),whole=parts[0];if(m.groupSep)whole=whole.replace(/\B(?=(\d{3})+(?!\d))/g,m.groupSep);const prefix=value<0?m.minus:m.explicitPlus&&value>0?'+':'';return prefix+whole+(m.digits?m.decimalSep+parts[1]:'')}
function animateDashboardCounters(animateNew=COUNTERS_READY){const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode())){const parent=node.parentElement;if(!parent||parent.closest('script,style,textarea,.sidebar-counter,.dashboard-counter,.yf-meta,.tc'))continue;const text=node.nodeValue;if(!/[0-9]/.test(text)||/[/:]/.test(text))continue;const row=parent.closest('[data-c],.sgc[data-k]'),scope=row||parent.closest('#cards,#dc,#sgk');if(!scope)continue;const rx=/(?<![A-Za-z0-9])([+−-]?\d[\d.,]*)(?![A-Za-z0-9])/g,matches=[...text.matchAll(rx)];if(!matches.length)continue;let path=[],el=parent;while(el&&el!==scope){const same=[...el.parentElement.children].filter(x=>x.tagName===el.tagName),ix=same.indexOf(el);path.unshift(el.tagName+'.'+[...el.classList].sort().join('.')+':'+ix);el=el.parentElement}const base=(row?'row:'+(row.dataset.c||row.dataset.k):'scope:'+scope.id)+'|'+path.join('/'),frag=document.createDocumentFragment();let at=0;matches.forEach((match,i)=>{const token=counterToken(match[1]);if(!token)return;frag.append(document.createTextNode(text.slice(at,match.index)));const span=document.createElement('span'),key=base+'|'+i,prev=DASH_COUNTER_VALUES.get(key);span.className='dashboard-counter';span.textContent=match[1];if(prev!=null&&prev.value!==token.value){span.dataset.v=prev.value;tween(span,token.value,v=>formatAutoCounter(v,token))}else if(prev==null&&animateNew){span.dataset.v=0;tween(span,token.value,v=>formatAutoCounter(v,token))}else span.textContent=formatAutoCounter(token.value,token);DASH_COUNTER_VALUES.set(key,token);frag.append(span);at=match.index+match[0].length});if(at){frag.append(document.createTextNode(text.slice(at)));node.replaceWith(frag)}}}
window.animateDashboardCounters=animateDashboardCounters;
function flashTicks(){animateDashboardCounters();const T=window.__tick||{};window.__tick={};let n=0;for(const c in T){if(n>400)break;document.querySelectorAll('[data-c="'+c+'"]').forEach(el=>{el.classList.remove('tick-up','tick-dn');void el.offsetWidth;el.classList.add('tick-'+T[c]);n++;setTimeout(()=>el.classList.remove('tick-up','tick-dn'),2000)})}}
function renderWL(){const L=$('#wll');if(!L)return;const ds=Object.keys(D.px).sort(),N=ds.length,last=ds.at(-1),LP=N?D.px[last]:{},f=v=>v==null?'-':(v>=0?'+':'−')+Math.abs(v).toFixed(1)+'%';
 const dlist=$('#wld');if(dlist&&!dlist.children.length&&Object.keys(D.nm).length)dlist.innerHTML=Object.keys(D.nm).sort().map(c=>'<option value="'+c+'">'+esc(D.nm[c]||'')+'</option>').join('');
 $('#wlh').innerHTML=counterMarkup(WL.length,'wl-count')+' saham'+(last?' · '+dl(last):'');
 L.innerHTML=WL.length?WL.map(w=>{const c=w.code,a=LP[c]||[],cl=g(a,0),pv=g(a,1),ch=cl&&pv?(cl/pv-1)*100:null;let w5=null;if(N>5){const b=D.px[ds[N-6]][c],bc=b&&g(b,0);if(bc&&cl)w5=(cl/bc-1)*100}
  let tags=[];try{tags=TGX(c).filter(x=>x[0]==='Batas ARA tersentuh')}catch(_){}const tagHtml=tags.length?'<div class="tgs wl-tags">'+tags.map(x=>`<span class="tc" style="background:${x[1]}" title="${esc(x[2])}">${esc(displayTGTagLabel(x[0]))}</span>`).join('')+'</div>':'';
  return `<div class="tr" data-c="${c}" title="${esc(D.nm[c]||'')}"><span class="wl-info"><b>${c}</b><small class="mu">${cl?counterMarkup(cl,'wl-price:'+c):'tidak ada harga'}</small>${tagHtml}</span><b class="${ch==null?'':ch>=0?'up':'dn'}">${ch==null?'-':counterMarkup(ch,'wl-change:'+c,1,true)+'%'}</b><small class="${w5==null?'mu':w5>=0?'up':'dn'}" title="vs close 5 hari bursa lalu">5h ${w5==null?'-':counterMarkup(w5,'wl-week:'+c,1,true)+'%'}</small><button class="wx" data-wx="${c}" title="Hapus">✕</button></div>`}).join(''):'<small class="mu">Belum ada. Ketik kode lalu tekan +.</small>';animateSidebarCounters()}
async function wlLoad(){try{const j=await (await fetch('/api/watchlist')).json();WL=j.codes||[]}catch(e){}renderWL()}
async function wlAdd(){const i=$('#wli'),m=$('#wlm'),c=(i.value||'').trim().toUpperCase();if(!c)return;m.textContent='';
 try{const r=await fetch('/api/watchlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:c})});const j=await r.json();if(!j.ok)throw Error(j.error||'gagal');
  if(!WL.some(w=>w.code===j.code))WL.push({code:j.code,note:''});i.value='';renderWL()}catch(e){m.textContent='✗ '+e.message}}
$('#wlb').onclick=wlAdd;$('#wli').addEventListener('keydown',e=>{if(e.key==='Enter')wlAdd()});
$('#wl').addEventListener('click',async e=>{const x=e.target.closest('[data-wx]');if(x){e.stopPropagation();const c=x.dataset.wx;try{await fetch('/api/watchlist/'+encodeURIComponent(c),{method:'DELETE'});WL=WL.filter(w=>w.code!==c);renderWL()}catch(err){}return}
 const r=e.target.closest('.tr[data-c]');if(!r)return;const c=r.dataset.c;if(S&&S.R.find(v=>v.c===c))detail(c);else if(typeof DS!=='undefined'&&DS&&DS.R&&DS.R.find(v=>v.c===c))dtl(c)});

/* ===== Tab Fundamental di panel detail emiten (data: yfinance via /api/fundamental) ===== */
const FUND={};window.__ptab='main';window.__fc=null;
const fN=(v,d=1)=>v==null||!isFinite(v)?'—':(+v).toLocaleString('id-ID',{minimumFractionDigits:d,maximumFractionDigits:d}),
 fP=(v,d=1,s=false)=>v==null||!isFinite(v)?'—':(s&&v>0?'+':'')+fN(v,d)+'%',fX=(v,d=2)=>v==null||!isFinite(v)?'—':fN(v,d)+'x',
 fR=v=>v==null||!isFinite(v)?'—':'Rp '+(Math.abs(v)>=1e12?fN(v/1e12,1)+' T':Math.abs(v)>=1e9?fN(v/1e9,1)+' M':Math.abs(v)>=1e6?fN(v/1e6,1)+' Jt':fN(v,0)),
 fT=v=>v==null?'':v>0?'up':'dn',TONE={up:'var(--up)',dn:'var(--dn)',wn:'#f59e0b',ac:'var(--ac)',mu:'var(--mu)'};
function pnTabs(c){const pn=$('#pn'),bar=pn&&pn.querySelector(':scope>.bar');if(!bar||pn.querySelector('.ptabs'))return;bar.classList.add('phd');
 bar.insertAdjacentHTML('afterend','<div id="pnDec"></div><div class="ptabs"><button data-t="main">Analisis</button><button data-t="fund">Fundamental</button></div><div id="pnFund"></div>');window.__fc=c;
 const set=t=>{window.__ptab=t;pn.classList.toggle('tf',t==='fund');pn.querySelectorAll('.ptabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));if(t==='fund')fundLoad(c)};
 pn.querySelectorAll('.ptabs button').forEach(b=>b.onclick=()=>set(b.dataset.t));set(window.__ptab||'main');decRender(c);if(FW.autoFund&&!FUND[c]&&!FUNDERR[c]&&window.__ptab!=='fund')fundLoad(c)}
const _detail=detail,_dtl=dtl;
detail=function(c){$('#pn').classList.remove('tf');_detail(c);pnTabs(c)};dtl=function(c){$('#pn').classList.remove('tf');_dtl(c);pnTabs(c)};
async function fundLoad(c,force){const el=$('#pnFund');if(!el)return;if(FUND[c]&&!force){fundRender(c,FUND[c]);return}
 el.innerHTML='<div class="fu"><div class="fu-sk"></div><div class="fu-sk"></div><div class="fu-sk" style="height:90px"></div></div>';
 try{const r=await fetch('/api/fundamental/'+encodeURIComponent(c)+(force?'?refresh=1':''));const j=await r.json();if(!j.ok)throw Error(j.error||('HTTP '+r.status));FUND[c]=j;delete FUNDERR[c];if(window.__fc===c&&$('#pnFund'))fundRender(c,j);decRender(c);clearTimeout(window.__brT);window.__brT=setTimeout(()=>{try{BR()}catch(e){}},500)}
 catch(e){FUNDERR[c]=1;decRender(c);if(window.__fc===c&&$('#pnFund'))$('#pnFund').innerHTML='<div class="fu-w"><b>Gagal memuat fundamental</b><ul><li>'+esc(e.message)+'</li></ul><div style="margin-top:8px"><button class="btn" id="fuRetry">↻ Coba lagi</button></div></div>',$('#fuRetry').onclick=()=>fundLoad(c,true)}}
function fundRender(c,j){const el=$('#pnFund');if(!el)return;const m=j.metrics||{},v=j.valuation||{},q=j.quadrant||{},tr=j.trend||{},rg=j.range52,qc=TONE[q.tone]||'var(--mu)';
 const card=(val,lb,cls)=>`<div class="fu-c"><b class="${cls||''}">${val}</b><small>${lb}</small></div>`;
 const s14=j.score14||{},sg=j.signal||{},AC={BUY:'var(--up)',HOLD:'#60a5fa',WAIT:'#f59e0b',SELL:'var(--dn)'},sc=j.score;const age=j.fetched?Math.max(0,Math.round((Date.now()-Date.parse(j.fetched))/36e5)):null;
 const ff=FREE_FLOAT.rows[c],ffCard=ff&&ff.available?(()=>{const current=ff.current_pct,required=ff.required_pct,gap=ff.gap_pp,deadline=ff.deadline_status||'Status tidak tersedia',penalty=Number(ff.penalty)||0;
  const stat=deadline.startsWith('31 Maret ')&&current!=null&&required!=null?`${fN(current,1)}% dari target ${fN(required,1)}%`:current==null?deadline:`${fN(current,1)}% · ${deadline}`;
  const detail=deadline.startsWith('31 Maret ')&&gap>0?`Kurang ${fN(gap,2)} poin persentase · tenggat ${deadline}`:deadline;
  return `<div class="fu-ff" title="${esc(ff.source||'')} · snapshot ${esc(ff.as_of||'')} "><b>◉ Free float</b><strong>${esc(stat)}</strong><small>${esc(detail)}${penalty>0?` · penalti skor −${fN(penalty,1)}/100`:''}</small><small class="fu-ff-src">Snapshot ${esc(ff.as_of||'—')} · penyesuaian risiko heuristik</small></div>`})():`<div class="fu-ff"><b>◉ Free float</b><strong>Data belum tersedia</strong><small>Unggah snapshot di Input data.</small></div>`;
 const hdates=Object.keys(D.px||{}).sort().filter(d=>{const a=D.px[d]&&D.px[d][c];return a&&Number(a[0])>0}),
   baseIndex=Math.max(0,hdates.length-6),baseClose=hdates.length>1?Number(D.px[hdates[baseIndex]][c][0]):null,
   rangePos=p=>rg&&Number(rg.high)>Number(rg.low)?Math.max(0,Math.min(100,(p-Number(rg.low))/(Number(rg.high)-Number(rg.low))*100)):null,
   priorPos=baseClose!=null?rangePos(baseClose):null,currentPos=rg?Number(rg.pos):null,
   trendDir=baseClose!=null&&Number(j.price)>0?Math.sign(Number(j.price)-baseClose):0,
   trendPct=baseClose&&Number(j.price)>0?(Number(j.price)/baseClose-1)*100:null,
   sessions=Math.min(5,Math.max(1,hdates.length-1)),
   trail=trendDir&&priorPos!=null&&currentPos!=null?`<i class="fu-r-trail ${trendDir>0?'u':'d'}" style="left:${Math.min(priorPos,currentPos).toFixed(1)}%;width:${Math.max(.7,Math.abs(currentPos-priorPos)).toFixed(1)}%" title="Harga ${trendDir>0?'naik':'turun'} ${trendPct>0?'+':''}${trendPct.toFixed(1).replace('.',',')}% dalam ${sessions} sesi"></i>`:'',
   rgH=rg?`<div class="fu-r"><div class="tr"><span>POSISI HARGA 52 MINGGU</span><b style="color:#f59e0b">${esc(rg.label)} · ${fN(rg.pos,0)}%</b></div><div class="fu-rb" style="--p:${rg.pos}%">${trail}<div class="mk ${rg.pos>85?'r':rg.pos<15?'l':''} ${trendDir>0?'u':trendDir<0?'d':'flat'}" style="left:${rg.pos}%" title="${trendDir?`Bergerak ${trendDir>0?'naik':'turun'} ${Math.abs(trendPct).toFixed(1)}% dalam ${sessions} sesi`:'Arah 5 sesi belum tersedia'}"><em>Rp ${fN(j.price,0)}</em></div></div><div class="tr"><span>Rp ${fN(rg.low,0)}</span><span>Rp ${fN(rg.high,0)}</span></div><div class="tr"><span>Terendah 52W</span><span>Tertinggi 52W · ${fP(rg.to_high,0,true)} dari harga kini</span></div></div>`:'';
 el.innerHTML=`<div class="fu" style="--qc:${qc}">
 <div class="fu-g">${card(fR(m.mcap),'Market Cap')}${card(fX(m.pe,1),'P/E Ratio',m.pe<0?'dn':'')}${card(fX(m.pb,2),'P/B Ratio')}${card(fP(m.dy,1),'Dividen Yield',m.dy>25?'dn':'')}
 ${card(fP(m.roe,1),'ROE')}${card(fX(m.der,2),'D/E Ratio')}${card(m.eps==null?'—':'Rp '+fN(m.eps,0),'EPS (TTM)')}${card(fP(m.margin,1),'Profit Margin')}</div>
 <div class="fu-top"><div class="fu-q"><div class="fu-v"><span class="fu-pill">● ${esc(q.short||q.title||'—')}</span><div class="fu-seg"><span class="sg">${[0,1,2,3].map(k=>`<i class="${k<(q.segs||0)?'on':''}"></i>`).join('')}</span><b>${esc(q.grade||'–')}</b><small>· ${s14.total==null?'n/a':fN(s14.total,1)}/14</small></div></div></div>${rgH}</div>
 <div class="fu-g">${card(fP(m.roe,1),'ROE TTM · batas 15%',m.roe>15?'up':m.roe<10?'dn':'')}${card(fX(m.pb,2),'PBV · batas 1,5x',m.pb<1?'up':m.pb>1.5?'dn':'')}${card(fX(m.pe,1),'PE · batas 15x',m.pe>0&&m.pe<15?'up':m.pe>=15||m.pe<0?'dn':'')}
  <div class="fu-c"><b><span class="${fT(tr.ni_yoy)}">laba ${fP(tr.ni_yoy,0,true)}</span> · <span class="${fT(tr.rev_yoy)}">jual ${fP(tr.rev_yoy,0,true)}</span></b><small>Tren YoY${tr.src?' ('+esc(tr.src)+')':''}</small></div></div>
 <div><div class="mu" style="font-size:10px;margin-bottom:4px">UJI KUALITAS (${j.passed}/${j.evaluated})</div><div class="fu-t">${(j.tests||[]).map(t=>`<span class="${t.ok==null?'na':t.ok?'ok':'no'}">${t.ok==null?'·':t.ok?'✓':'✕'} ${esc(t.label)}</span>`).join('')}</div></div>
 <div class="fu-alert-grid">${(j.warnings||[]).length?`<div class="fu-w"><b>⚠ Perhatian</b><ul>${j.warnings.map(w=>'<li>'+esc(w)+'</li>').join('')}</ul></div>`:''}${ffCard}</div>

 <div class="fu-foot"><span class="fu-src">${esc((j.sources||['yfinance']).join(' + '))} (tidak resmi) · laporan ${esc(j.report_date||'—')} · PER &amp; PBV memakai harga terakhir${age!=null?' · data '+(age<1?'baru saja':age+' jam lalu'):''}${String(j.status||'').startsWith('basi')?' · ⚠ gagal refresh, memakai cache':''}</span><span><button class="btn" id="fuRef">↻ Refresh</button> <button class="btn" id="fuDet">📊 Detail Fundamental</button></span></div>
 <div class="fu-d" id="fuD" hidden></div></div>`;
 requestAnimationFrame(()=>el.querySelectorAll('.fu-bar i').forEach(i=>i.style.width=i.dataset.w+'%'));
 $('#fuRef').onclick=()=>fundLoad(c,true);
 $('#fuDet').onclick=()=>{const d=$('#fuD');if(!d.hidden){d.hidden=true;return}const A=(j.detail||{}).annual||[],Q=(j.detail||{}).quarterly||[];
  d.innerHTML='<div class="fu-t" style="margin-bottom:8px">'+((j.score14||{}).parts||[]).map(x=>`<span class="${x.pts==null?'na':x.pts>=x.max?'ok':x.pts<0?'no':x.pts>0?'md':'z'}">${esc(x.label)} ${esc(x.txt)} ${x.pts==null?'·':(x.pts>0?'+':'')+x.pts}</span>`).join('')+'</div><table><tr><th>Tahunan</th><th>Penjualan</th><th>Laba</th><th>Ekuitas</th><th>ROE</th><th>DER</th></tr>'+A.map(x=>`<tr><td>${esc(x.d.slice(0,4))}</td><td>${fR(x.rev)}</td><td>${fR(x.ni)}</td><td>${fR(x.eq)}</td><td>${fP(x.roe,1)}</td><td>${fX(x.der,2)}</td></tr>`).join('')+'</table><br><table><tr><th>Kuartal</th><th>Penjualan</th><th>Laba</th></tr>'+Q.map(x=>`<tr><td>${esc(x.d)}</td><td>${fR(x.rev)}</td><td>${fR(x.ni)}</td></tr>`).join('')+'</table>';d.hidden=false}}

/* ===== Holder aktif per emiten: pemegang >=5% (days terbaru) + 1-5% (sat terbaru); yang sudah keluar (kepemilikan 0) tidak dihitung ===== */
var HMk=null,HMv={};
function HMAP(){const dd=Object.keys(D.days).sort(),sd=Object.keys(D.sat).sort(),ld=dd.at(-1),ls=sd.at(-1),k=(window.__av||0)+'|'+ld+'|'+ls+'|'+(ld?Object.keys(D.days[ld]).length:0)+'|'+(ls?Object.keys(D.sat[ls]).length:0);if(k===HMk)return HMv;
 const A=ld?D.days[ld]:{},B=ls?D.sat[ls]:{},M={};
 for(const c in A){const n=A[c].filter(h=>h[3]>0).length;if(n)(M[c]=M[c]||{h5:0,h1:0}).h5=n}
 for(const c in B){const n=B[c].filter(h=>h[3]>0&&h[4]>=1&&h[4]<5).length;if(n)(M[c]=M[c]||{h5:0,h1:0}).h1=n}
 for(const c in M)M[c].t=M[c].h5+M[c].h1;HMk=k;HMv=M;return M}

/* ===== Keputusan gabungan MODEL C: arus dana KSEI + rekomendasi BSX + aktivitas dini + fundamental (semua skala -100..+100) ===== */
const FW={mf:35/110,bsx:25/110,dy:10/110,fund:30/110,ax:10/110, /* proporsi awal dinormalisasi ke 100%; nilai yang kosong dikeluarkan lalu sisanya dinormalisasi ulang */
 buy:30,hold:10,sell:-30,                   /* ambang skor gabungan */
 mfBuy:15,mfSell:-45,mfNeg:-15,             /* gerbang arus dana */
 autoFund:true};                            /* ambil fundamental otomatis saat panel emiten dibuka */
const FREE_FLOAT={rows:{},scoring:{}};
async function loadFreeFloat(){try{const r=await fetch('/api/free-float',{cache:'no-store'}),j=await r.json();if(!j.ok)return;Object.keys(FREE_FLOAT.rows).forEach(c=>delete FREE_FLOAT.rows[c]);Object.assign(FREE_FLOAT.rows,j.rows||{});FREE_FLOAT.scoring=j.scoring||{};
 if(typeof BR==='function'&&S)BR();if(window.__fc&&typeof decRender==='function')decRender(window.__fc);if(window.__fc&&window.__ptab==='fund'&&FUND[window.__fc])fundRender(window.__fc,FUND[window.__fc])}catch(e){}}
setTimeout(loadFreeFloat,1000);setInterval(loadFreeFloat,300000);
const FUNDERR={};
const fundZ=j=>{const v=j&&j.score14&&j.score14.total;return v==null?null:Math.max(-100,Math.min(100,(v-7)/7*100))};
function decide(i){const W=[['mf','KSEI holder',FW.mf],['bsx','Holder + struktur',FW.bsx],['dy','Flow harian + dini',FW.dy],['fund','Fundamental',FW.fund],['ax','AMDX',FW.ax]],ok=v=>v!=null&&isFinite(v),
 av=W.filter(([k])=>ok(i[k])),sw=av.reduce((a,x)=>a+x[2],0),rawK=sw?av.reduce((a,[k,,w])=>a+w*i[k],0)/sw:null,
 ff=FREE_FLOAT.rows[String(i.code||'').toUpperCase()],penalty=rawK>0&&FREE_FLOAT.scoring.enabled&&ff?Math.max(0,Number(ff.penalty)||0):0,K=rawK==null?null:rawK-penalty,
 comps=W.map(([k,l,w])=>({k,l,w:ok(i[k])&&sw?w/sw:0,v:ok(i[k])?i[k]:null})),R=(act,why)=>({act,K,rawK,freeFloatPenalty:penalty,freeFloat:ff||null,comps,why,n:av.length});
 if(K==null||(!ok(i.mf)&&!ok(i.bsx))||av.length<2)return R('WAIT','data belum cukup');
 const fs=i.fundAct==='SELL',bs=i.bsxRec==='SELL';
 if(rawK>=FW.buy&&K<FW.buy)return R('HOLD','BUY tertahan oleh penyesuaian risiko free float');
 if(K<=FW.sell)return R('SELL','skor gabungan '+Math.round(K)+' ≤ '+FW.sell);
 if(ok(i.mf)&&i.mf<=FW.mfSell)return R('SELL','arus dana keluar kuat ('+Math.round(i.mf)+')');
 if((bs||fs)&&ok(i.mf)&&i.mf<=FW.mfNeg)return R('SELL','arus dana negatif dan '+(bs?'rekomendasi teknikal':'fundamental')+' SELL');
 if(K>=FW.buy){const blk=ok(i.mf)&&i.mf<FW.mfBuy?'arus dana belum cukup masuk':bs?'rekomendasi teknikal SELL':fs?'fundamental SELL':null;
  return blk?R('HOLD','BUY tertahan: '+blk):R('BUY','skor '+Math.round(K)+', arus dana masuk, teknikal & fundamental tidak menolak')}
 return K>=FW.hold?R('HOLD','skor gabungan positif ('+Math.round(K)+')'):R('WAIT','belum ada keunggulan jelas ('+Math.round(K)+')')}
const FUNDC={};
function KEP(c){const RM=S&&(S.__rm||(S.__rm=Object.fromEntries(S.R.map(x=>[x.c,x])))),r=RM?RM[c]:null,b=(typeof BM!=='undefined'&&BM)?BM[c]:null,j=FUND[c]||FUNDC[c];
 return decide({code:c,mf:r?r.s:null,bsx:b?(b.sc0??b.sc):null,dy:b&&b.dy&&typeof b.dy.s==='number'?b.dy.s:null,fund:fundZ(j),ax:b&&typeof b.ax==='number'?b.ax:null,bsxRec:b?(b.rec0??b.rec):null,fundAct:j&&j.signal?j.signal.action:null})}
function decRender(c){const el=$('#pnDec');if(!el||window.__fc!==c)return;const d=KEP(c),AC={BUY:'var(--up)',HOLD:'#60a5fa',WAIT:'#f59e0b',SELL:'var(--dn)'},ld=!FUND[c]&&!FUNDERR[c];
 el.style.setProperty('--dc',AC[d.act]);
 const ff=d.freeFloat,ffTip=ff&&ff.available?`\nFree float ${ff.current_pct==null?'n/a':ff.current_pct+'%'} · target ${ff.required_pct==null?'n/a':ff.required_pct+'%'} · ${ff.deadline_status||'status n/a'} · snapshot ${ff.as_of||'n/a'}${d.freeFloatPenalty>0?' · penalti '+d.freeFloatPenalty.toFixed(1)+'/100 (heuristik)':''}`:'';
 el.title=d.why+(ld?' · fundamental dimuat…':FUNDERR[c]?' · fundamental tidak tersedia':'')+'\nBobot efektif (dinormalisasi dari komponen tersedia): '+d.comps.map(x=>x.l+' '+Math.round(x.w*100)+'%'+(x.v==null?' (n/a)':' = '+Math.round(x.v))).join(' · ')+ffTip;
 const phase=BM&&BM[c]?BM[c].ph:null;
 const ffs=d.freeFloat&&d.freeFloat.available?`<small class="dk-ff">Free float ${d.freeFloat.current_pct==null?'n/a':fN(d.freeFloat.current_pct,1)+'%'} · ${d.freeFloat.deadline_status||'status n/a'}${d.freeFloatPenalty>0?' · skor −'+fN(d.freeFloatPenalty,1):''}</small>`:'';
 el.innerHTML=`<div class="dh"><span class="dact">${d.act}</span></div><b class="dk">${d.K==null?'–':(d.K>0?'+':'')+Math.round(d.K)}</b>${d.freeFloatPenalty>0?`<small class="mu">dasar ${d.rawK>0?'+':''}${Math.round(d.rawK)} · penalti free float −${fN(d.freeFloatPenalty,1)}</small>`:''}${ffs}${AMDXBars(phase,false)}` }

/* ===== Fundamental massal (cache SQLite) untuk halaman daftar + antrean prefetch hemat limit ===== */
async function fundCache(){try{const j=await (await fetch('/api/fundamental/cached')).json();if(!j.ok)return;let ch=false;
 for(const c in j.items){const o=j.items[c];if(!FUNDC[c]||FUNDC[c].score14.total!==o.t||FUNDC[c].signal.action!==o.a)ch=true;FUNDC[c]={score14:{total:o.t},signal:{action:o.a}}}
 if(ch&&typeof BR==='function'&&S)BR()}catch(e){}}
async function fundQueue(){try{if(!BL||!BL.length)return;const w=(typeof WL!=='undefined'?WL:[]).map(x=>x.code),top=BL.filter(x=>x.av>=BSM.min).sort((a,b)=>Math.abs(b.sc)-Math.abs(a.sc)).slice(0,40).map(x=>x.c);
 await fetch('/api/fundamental/queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({codes:[...new Set([...w,...top])].slice(0,60)})})}catch(e){}}
setTimeout(fundQueue,7000);setTimeout(fundCache,12000);setInterval(fundCache,120000);setInterval(fundQueue,1800000);
/* ===== Telegram: status, tombol, dan kirim kandidat sinyal ke server (server yang membatasi & mengirim) ===== */
const TGS={on:false,cfg:false,pushed:{}};
function tgShow(st){const t=st&&st.tg,b=$('#tgb');if(!t||!b)return;TGS.on=!!t.enabled;TGS.cfg=!!t.configured;
 b.className='tgb '+((t.blocked||(t.last_error&&t.want_enabled&&!t.enabled)||(t.configured&&t.want_enabled&&t.worker_running===false))?'err':t.enabled?'on':'');
 b.querySelector('.ts').textContent=t.configured?(t.sent_today+'/'+t.max_per_day):'belum diatur';
 b.title=(t.configured?'Notifikasi sinyal trading detail (Entry/OTE, Stop Loss, TP1, TP2)':'Belum terhubung: kirim /start ke bot, lalu jalankan: py telegram_setup.py')+(t.configured&&t.want_enabled&&t.worker_running===false?'\nWorker Telegram tidak aktif. Jalankan run.bat.':'')+(t.last_error?'\nError terakhir: '+t.last_error:'')+(t.last_sent?'\nTerkirim terakhir: '+t.last_sent.slice(11,16)+' WIB':'');
 $('#tgO').textContent=t.want_enabled?'ON':'OFF';$('#tgO').disabled=!t.configured;$('#tgT').disabled=!t.configured}
$('#tgO').onclick=async()=>{const on=$('#tgO').textContent==='ON';try{await fetch('/api/telegram/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:!on})})}catch(e){}yfPoll(true)};
$('#tgT').onclick=async()=>{const b=$('#tgT');b.disabled=true;try{const r=await fetch('/api/telegram/test',{method:'POST'}),j=await r.json();$('#tgb').title=j.ok?'Tes terkirim':'Tes gagal: '+(j.error||r.status)}catch(e){$('#tgb').title='Tes gagal: '+e.message}b.disabled=false;yfPoll(true)};
function otePush(){if(!TGS.on||!BL||!BL.length)return;const today=new Date(Date.now()+7*36e5).toISOString().slice(0,10),ld=Object.keys(D.px).sort().at(-1);if(ld!==today)return;
 const c=BL.filter(x=>x.av>=BSM.min&&x.en&&x.en.up&&x.en.s==='DI ZONA OTE'&&x.rec0!=='SELL'&&x.px>=x.en.lo&&x.px<=x.en.hi&&x.st<x.px&&x.px<x.t1&&x.t1<x.t2&&TGS.pushed[x.c]!==today).slice(0,10);if(!c.length)return;
 c.forEach(x=>TGS.pushed[x.c]=today);
 fetch('/api/alerts/ote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:c.map(x=>({code:x.c,price:x.px,lo:x.en.lo,hi:x.en.hi,stop:x.st,t1:x.t1,t2:x.t2,date:ld}))})}).catch(()=>{})}
{const _r=run;run=function(){_r.apply(this,arguments);try{otePush()}catch(e){console.error(e)}}}
const YF={st:null,busy:false,tk:null};
function tween(el,to,format=v=>Math.round(v).toLocaleString('id-ID')){const from=+el.dataset.v||0;el.dataset.v=to;if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){el.textContent=format(to);return}const t0=performance.now(),f=t=>{const k=Math.min(1,(t-t0)/700);el.textContent=format(from+(to-from)*k);if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)}
function yfBreadth(){const y=$('#yf');if(!y)return;const ds=Object.keys(D.px).sort(),P=ds.length?D.px[ds.at(-1)]:{};let u=0,d=0,f=0;for(const c in P){const a=P[c];if(!a||a.length<2||!(a[2]>0))continue;a[0]>a[1]?u++:a[0]<a[1]?d++:f++}
 const t=u+d+f;y.querySelector('.yf-up').style.flexGrow=t?u/t*100:0;y.querySelector('.yf-flat').style.flexGrow=t?f/t*100:0;y.querySelector('.yf-dn').style.flexGrow=t?d/t*100:0;tween($('#yfAdv'),u);tween($('#yfDec'),d);y.classList.remove('pop');void y.offsetWidth;y.classList.add('pop')}
function yfShow(st){const y=$('#yf'),l=st&&st.live;if(!y||!l)return;YF.st=st;const now=Date.now()/1000,age=l.last_ok?now-Date.parse(l.last_ok)/1000:1e9;
 const s=(l.running||YF.busy)?'busy':(l.ok===false&&l.last_run)?'err':(l.auto&&st.market&&age<(l.interval||300)*3)?'live':'idle';
 y.className='yf '+s+(y.classList.contains('pop')?' pop':'');y.title=(l.message||'')+(l.last_ok?' · update '+l.last_ok.slice(11,16)+' WIB':'')+(l.auto?'':' · mode manual');
 $('#yfT').textContent=l.last_ok?l.last_ok.slice(11,16):'--:--';try{tgShow(st)}catch(e){}}
function yfTick(){const y=$('#yf'),l=YF.st&&YF.st.live;if(!y||!l)return;const bar=y.querySelector('.yf-next i');
 if(l.next_run&&l.interval&&!y.classList.contains('idle')){const now=Date.now()/1000,p=1-(l.next_run-now)/l.interval;bar.style.width=Math.max(0,Math.min(100,p*100))+'%';if(now>l.next_run+4&&YF.tk!==l.next_run){YF.tk=l.next_run;yfPoll(true)}}else bar.style.width='0'}
setInterval(yfTick,1000);
let DV=null;
const yfPoll=async(force)=>{if(document.hidden&&force!==true)return;try{const st=await (await fetch('/api/status')).json();yfShow(st);if(DV===null){DV=st.data_version;yfBreadth();return}
 if(st.data_version!==DV){const ov=$('#ov');if(ov&&!ov.hidden)return;DV=st.data_version;await API.refresh();yfBreadth()}}catch(e){}};
setInterval(()=>yfPoll(),30000);setTimeout(()=>yfPoll(true),1500);
$('#yfBtn').onclick=async()=>{if(YF.busy)return;YF.busy=true;if(YF.st)yfShow(YF.st);else $('#yf').className='yf busy';
 try{const r=await fetch('/api/live/update',{method:'POST'});const j=await r.json();if(!j.ok)throw Error(j.error||('HTTP '+r.status))}catch(e){const y=$('#yf');y.title='✗ '+e.message;if(YF.st)YF.st.live=Object.assign({},YF.st.live,{ok:false,last_run:'x',message:e.message})}
 YF.busy=false;await yfPoll(true)};
let LOT=false;const fr=v=>{const a=Math.abs(v),s=v<0?'−':'+';return v?s+(a>=1e12?(a/1e12).toFixed(2)+' T':a>=1e9?(a/1e9).toFixed(2)+' M':a>=1e6?(a/1e6).toFixed(1)+' Jt':a.toFixed(0)):'-'};const fm=v=>{if(LOT)v=v/100;const a=Math.abs(v),s=v<0?'−':v>0?'+':'';return s+(a>=1e12?(a/1e12).toFixed(2)+' T':a>=1e9?(a/1e9).toFixed(2)+' M':a>=1e6?(a/1e6).toFixed(2)+' Jt':a>=1e3?(a/1e3).toFixed(1)+' Rb':a.toFixed(0))};
const cl=v=>v>0?'up':v<0?'dn':'';const dl=d=>d.slice(8)+'/'+d.slice(5,7);
const lab=s=>s>=45?['Strong Buy ','#2dd4bf']:s>=15?['Buy ','#86e0b0']:s>-15?['Neutral','#7d8894']:s>-45?['Sell ','#f5a623']:['Strong Sell ','#f0544f'];
function G(t){let ret=t[7]+t[25],inst=0,blk=0,fr=0;for(let k=0;k<9;k++){const lo=1+2*k,fo=19+2*k;blk+=t[lo+1]+t[fo+1];fr+=t[fo]+t[fo+1];if([2,4,5,7].includes(k))inst+=t[lo]+t[fo]}return{ret,inst,blk,fr,oth:t[37]-ret-inst-blk}}
let W=0,ST={t:'all',q:'',s:'s',asc:false,lim:10},S;
function A(){
 const da=Object.keys(D.days).sort().slice(W?-W:0),ds=TP==='all'?da:da.filter(d=>PK(TP,d)===PK(TP,da.at(-1))),td=Object.keys(D.tipe).sort(),sd=Object.keys(D.sat).sort(),kd=Object.keys(D.kl).sort();
 const pd=Object.keys(D.px).sort(),P=pd.length?D.px[pd.at(-1)]:{};const T=td.length?D.tipe[td.at(-1)]:{};const cs=new Set([...ds.flatMap(d=>Object.keys(D.days[d])),...Object.keys(T)]);
 const M={buy:0,sell:0,net:0,rp:0,fnet:0,acc:0,dist:0,br:ds.map(()=>[0,0])},R=[];
 for(const c of cs){
  const r={c,nm:D.nm[c]||'',day:[],cum:[],buy:0,sell:0,net:0,fnet:0,up:0,dn:0,nb:0,ns:0,mv:{},so:(T[c]||[])[0]||0,rp:0,px:(P[c]||[])[0]||0,chg:P[c]&&P[c][1]?(P[c][0]/P[c][1]-1)*100:null};let cu=0;
  const has=ds.some(d=>D.days[d][c]);
  ds.forEach((d,i)=>{let s=0;for(const[nv,st,p,q]of D.days[d][c]||[]){const x=q-p;if(!x)continue;s+=x;if(x>0){r.buy+=x;r.nb++}else{r.sell-=x;r.ns++}if(st==='A')r.fnet+=x;r.mv[nv]=(r.mv[nv]||0)+x}
   r.rp+=s*((D.px[d]&&D.px[d][c]||P[c]||[])[0]||0);r.day.push(s);cu+=s;r.cum.push(cu);if(s>0){r.up++;M.br[i][0]++}else if(s<0){r.dn++;M.br[i][1]++}});
  r.net=cu;r.np=r.so?cu/r.so*100:0;const C=[];
  if(has){const k5=ds.slice(-5).length,l5=r.day.slice(-5).reduce((a,b)=>a+b,0),sc=r.so||1;
   C.push(['a','Net Holder ≥5%',.30,th(r.np/.3),`net ${fm(r.net)} ${LOT?'lot':'saham'} (${r.np.toFixed(2)}% saham beredar)`]);
   C.push(['b','Konsistensi',.12,r.up+r.dn?(r.up-r.dn)/(r.up+r.dn):0,`${r.up} hari beli vs ${r.dn} hari jual`]);
   C.push(['c','Breadth',.10,r.nb+r.ns?(r.nb-r.ns)/(r.nb+r.ns):0,`${r.nb} aksi beli vs ${r.ns} aksi jual`]);
   C.push(['d','Momentum 5 hari',.13,th(l5/sc*100/.15),`aliran ${k5} hari terakhir ${fm(l5)}`])}
  r.tp=td.map(d=>{const t=D.tipe[d][c];if(!t)return null;const g=G(t),so=t[0]||1,o={d};for(const k in g)o[k]=g[k]/so*100;return o}).filter(Boolean);
  if(r.tp.length>1){const a=r.tp.at(-1),b=r.tp.at(-2),dr=a.ret-b.ret,di=a.inst-b.inst,df=a.fr-b.fr;
   C.push(['e','Institusi vs ritel',.15,th((di-dr)/2),`institusi ${di>=0?'+':''}${di.toFixed(2)}pp, ritel ${dr>=0?'+':''}${dr.toFixed(2)}pp (${dl(b.d)}→${dl(a.d)})`]);
   C.push(['f','Porsi asing',.10,th(df),`porsi asing ${df>=0?'+':''}${df.toFixed(2)}pp`])}
  if(sd.length>1){const x=D.sat[sd.at(-1)][c]||[],y=D.sat[sd.at(-2)][c]||[];if(x.length||y.length){const dp=x.reduce((a,b)=>a+b[4],0)-y.reduce((a,b)=>a+b[4],0);
   C.push(['g','Holder ≥1% bulanan',.10,th(dp/1.5),`pemegang ≥1% ${dp>=0?'+':''}${dp.toFixed(2)}pp (${dl(sd.at(-2))}→${dl(sd.at(-1))})`])}}
  if(!C.length)continue;const w=C.reduce((a,b)=>a+b[2],0);r.C=C;r.s=100*C.reduce((a,b)=>a+b[2]*b[3],0)/w*(.4+.6*Math.min(1,w));
  const sh=C.filter(x=>'abcd'.includes(x[0])),lg=C.filter(x=>'efg'.includes(x[0]));
  if(sh.length&&lg.length){const a=sh.reduce((p,q)=>p+q[2]*q[3],0),b=lg.reduce((p,q)=>p+q[2]*q[3],0);r.dv=Math.abs(a)>.08&&Math.abs(b)>.08&&a*b<0}
  M.buy+=r.buy;M.sell+=r.sell;M.net+=r.net;M.rp+=r.rp;M.fnet+=r.fnet;if(r.s>=15)M.acc++;else if(r.s<=-15)M.dist++;R.push(r)}
 return{R,ds,da,td,sd,kd,M}}
let TP='all';const PK=(p,d)=>{if(p==='y')return d.slice(0,4);if(p==='m')return d.slice(0,7);if(p==='d')return d;const t=new Date(d+'T00:00:00Z');return new Date(t.getTime()-((t.getUTCDay()+6)%7)*864e5).toISOString().slice(0,10)};
let BG='d';const BN=['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
function BGD(ds,M){if(BG==='d'){const L=[],B=[];for(const d of S.da){let u=0,v=0;for(const c in D.days[d]){let s=0;for(const x of D.days[d][c])s+=x[3]-x[2];if(s>0)u++;else if(s<0)v++}L.push(dl(d));B.push([u,v])}return{L,B}}
 const bk=new Map(),key=d=>{if(BG==='y')return d.slice(0,4);if(BG==='m')return d.slice(0,7);const t=new Date(d+'T00:00:00Z');return new Date(t.getTime()-((t.getUTCDay()+6)%7)*864e5).toISOString().slice(0,10)};
 for(const d of Object.keys(D.days).sort()){const k=key(d);let m=bk.get(k);if(!m)bk.set(k,m=new Map());for(const c in D.days[d]){let s=0;for(const x of D.days[d][c])s+=x[3]-x[2];m.set(c,(m.get(c)||0)+s)}}
 const L=[],B=[];for(const[k,m]of bk){let u=0,v=0;for(const s of m.values()){if(s>0)u++;else if(s<0)v++}L.push(BG==='y'?k:BG==='m'?BN[+k.slice(5)-1]+' '+k.slice(2,4):dl(k));B.push([u,v])}
 return{L,B}}
function AC(inp,src){let box=$('#sg');if(!box){box=document.createElement('div');box.id='sg';document.body.appendChild(box);window.addEventListener('scroll',e=>{if(e.target!==box)box.style.display='none'},true)}
 let ix=-1,cur=[],skip=false;const hide=()=>{box.style.display='none';ix=-1},mk2=()=>[...box.children].forEach((e,i)=>e.classList.toggle('on',i===ix)),pick=c=>{hide();skip=true;inp.value=c;inp.dispatchEvent(new Event('input'));skip=false};
 inp.addEventListener('input',()=>{if(skip)return;const q=inp.value.trim().toUpperCase();if(!q)return hide();
  const all=src(),cmp=(a,b)=>a[0].localeCompare(b[0]),pre=all.filter(x=>x[0].startsWith(q)).sort(cmp),oth=all.filter(x=>!x[0].startsWith(q)&&(x[0].includes(q)||x[1].toUpperCase().includes(q))).sort(cmp);
  cur=pre.concat(oth).slice(0,40);if(!cur.length)return hide();box._o=inp;
  const r=inp.getBoundingClientRect(),w=Math.min(Math.max(r.width,240),innerWidth-16);Object.assign(box.style,{left:Math.max(8,Math.min(r.left,innerWidth-w-8))+'px',top:r.bottom+2+'px',width:w+'px',display:'block'});
  box.innerHTML=cur.map(([c,nm])=>`<div data-c="${c}"><b>${c.startsWith(q)?'<mark>'+esc(q)+'</mark>'+esc(c.slice(q.length)):esc(c)}</b><small>${esc(nm).slice(0,30)}</small></div>`).join('');ix=-1});
 inp.addEventListener('keydown',e=>{if(box.style.display!=='block'||box._o!==inp)return;if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();ix=(ix+(e.key==='ArrowDown'?1:-1)+cur.length)%cur.length;mk2();box.children[ix].scrollIntoView({block:'nearest'})}else if(e.key==='Enter'&&ix>=0){e.preventDefault();pick(cur[ix][0])}else if(e.key==='Escape')hide()});
 inp.addEventListener('blur',hide);box.addEventListener('mousedown',e=>{const d=e.target.closest('[data-c]');if(d&&box._o===inp){e.preventDefault();pick(d.dataset.c)}})}
const BFP={id:'bfp',beforeDatasetsDraw(ch){if(window.BFXX==null)return;ch.ctx.save();ch.ctx.beginPath();ch.ctx.rect(0,0,window.BFXX,ch.height);ch.ctx.clip()},afterDatasetsDraw(ch){if(window.BFXX!=null)ch.ctx.restore()}};
const CH={};function mk(id,cfg){CH[id]?.destroy();const cv=document.getElementById(id);if(!cv)return;cfg.options=Object.assign({responsive:true,maintainAspectRatio:false},cfg.options);if(cfg.options.indexAxis!=='y'){const sc=cfg.options.scales=cfg.options.scales||{},x=sc.x=sc.x||{},t=x.ticks=x.ticks||{};Object.assign(t,{maxTicksLimit:8,maxRotation:0,minRotation:0,autoSkip:true});t.font=Object.assign({size:6},t.font)}CH[id]=new Chart(cv,cfg)}
function areaFade(context,rgb){const{chart}=context,{ctx,chartArea}=chart;if(!chartArea)return`rgba(${rgb},.12)`;const g=ctx.createLinearGradient(0,chartArea.top,0,chartArea.bottom);g.addColorStop(0,`rgba(${rgb},.2)`);g.addColorStop(.72,`rgba(${rgb},.045)`);g.addColorStop(1,`rgba(${rgb},0)`);return g}
function run(){if(window.__wait)return;S=A();const{R,ds,td,sd,kd,M,da}=S,pd=Object.keys(D.px).sort();const cs=getComputedStyle(document.documentElement);Chart.defaults.color=cs.getPropertyValue('--mu');Chart.defaults.font.family="'JetBrains Mono',monospace";Chart.defaults.font.size=8;Chart.defaults.plugins.legend.labels.boxWidth=10;Chart.defaults.plugins.legend.labels.boxHeight=10;Chart.defaults.borderColor='rgba(32,40,51,.3)';Chart.defaults.elements.point.radius=0;Chart.defaults.elements.point.hoverRadius=3;Chart.defaults.elements.line.tension=.4;Chart.defaults.elements.line.borderWidth=2;
 $('#cov').innerHTML=`5% harian: ${da.length?dl(da[0])+' → '+dl(da.at(-1))+' ('+da.length+' hari)':'-'}<br>Harga: ${pd.length?dl(pd[0])+' → '+dl(pd.at(-1))+' ('+pd.length+' hari)':'-'}<br>Snapshot bulanan: tipe ${td.length} · ≥1% ${sd.length} · klasifikasi ${kd.length}`;
 const K=(t,v,c='')=>`<div class="k"><small${t==='Net semua saham'?' class="total-net-title"':''}>${t}</small><b class="${c}">${v}</b></div>`;
 $('#cards').innerHTML=K('Saham dianalisis',R.length)+K('Buy  (≥15)',M.acc,'up')+K('Sell  (≤−15)',M.dist,'dn')+K('Total Beli 5%',fm(M.buy).replace('+',''),'up')+K('Total Jual 5%',fm(-M.sell).replace('−',''),'dn')+K('Net semua saham',fm(M.net),cl(M.net))+K('Total Net asing',fm(M.fnet),cl(M.fnet))+K('Total Net Rp',fr(M.rp),cl(M.rp));
 const up=cs.getPropertyValue('--up'),dn=cs.getPropertyValue('--dn');
 const g=BGD(ds,M);$('#bgt').textContent='Breadth '+({d:'harian',w:'mingguan',m:'bulanan',y:'tahunan'}[BG])+': jumlah saham net beli vs net jual (pemegang ≥5%)';$('#bgn').textContent=BG==='d'?'':'Memakai seluruh data yang diunggah (tidak terpengaruh filter hari). Saham dihitung net beli/jual dari total periode'+(BG==='w'?'; label = Senin awal minggu.':'.');
 mk('c1',{type:'line',data:{labels:g.L,datasets:[{label:'Selisih (beli − jual)',data:g.B.map(b=>b[0]-b[1]),borderColor:'#b45309',backgroundColor:'rgba(180,83,9,.04)',borderWidth:.8,borderDash:[2,3],tension:.48,pointRadius:0,pointHoverRadius:3,order:0},{label:'Net beli',data:g.B.map(b=>b[0]),borderColor:up,backgroundColor:c=>areaFade(c,'45,212,191'),fill:'origin',borderWidth:1.8,tension:.48,pointRadius:0,pointHoverRadius:3,order:1},{label:'Net jual',data:g.B.map(b=>b[1]),borderColor:dn,backgroundColor:c=>areaFade(c,'240,84,79'),fill:'origin',borderWidth:1.8,tension:.48,pointRadius:0,pointHoverRadius:3,order:2}]},plugins:[BFP],options:{animation:{duration:1100,easing:'easeInOutCubic'},interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{generateLabels(chart){const labels=Chart.defaults.plugins.legend.labels.generateLabels(chart);for(const item of labels){if(item.datasetIndex===1||item.datasetIndex===2){const color=chart.data.datasets[item.datasetIndex].borderColor;item.fillStyle=color;item.strokeStyle=color}}return labels}}},tooltip:{itemSort:(a,b)=>a.datasetIndex-b.datasetIndex,callbacks:{labelColor(context){const color=context.dataset.borderColor;return{borderColor:color,backgroundColor:color,borderWidth:0}}}}},scales:{x:{ticks:{maxRotation:0,autoSkip:true}},y:{title:{display:true,text:'jumlah saham'}}}}});
 try{TGL()}catch(e){console.error(e)}try{BFX()}catch(e){}try{draw()}catch(e){console.error(e)}try{DR()}catch(e){console.error(e)}try{RR()}catch(e){console.error(e)}try{BR()}catch(e){console.error(e)}}
/* animasi React: overlay di atas chart breadth (loop, tanpa tombol, efek saat garis beli/jual hampir bersentuhan) */
function BFX(){const cv=document.getElementById('c1');if(!cv||cv.dataset.fx||!window.React||!window.ReactDOM)return;cv.dataset.fx='1';const R=window.React,h=R.createElement,pa=cv.parentElement,hd=document.createElement('div');hd.style.cssText='position:absolute;inset:0;pointer-events:none';pa.appendChild(hd);
 function FX(){const ref=R.useRef(null);R.useEffect(()=>{const c=ref.current,x=c.getContext('2d'),RM=false;let p=0,hold=0,tm=0,pr=[],ph=0;
  const dot=(px,py,r,col,a)=>{x.globalAlpha=a;x.fillStyle=col;x.beginPath();x.arc(px,py,r,0,7);x.fill()};
  const tick=()=>{tm=setTimeout(tick,55);const ch=CH.c1;const W=c.clientWidth,H=c.clientHeight;if(document.hidden||!ch||!W||!ch.chartArea)return;const dpr=window.devicePixelRatio||1;if(c.width!==Math.round(W*dpr)||c.height!==Math.round(H*dpr)){c.width=Math.round(W*dpr);c.height=Math.round(H*dpr)}x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,W,H);
   const mb=ch.getDatasetMeta(1).data,ms=ch.getDatasetMeta(2).data,N=Math.min(mb.length,ms.length);if(N<2)return;const ca=ch.chartArea,th=(ca.bottom-ca.top)*.07,sp=Math.max(.15,N/130);ph+=.35;
   const at=(m,f)=>{const i=Math.max(0,Math.min(N-2,Math.floor(f))),t=f-i;return[m[i].x+(m[i+1].x-m[i].x)*t,m[i].y+(m[i+1].y-m[i].y)*t]};
   x.save();x.beginPath();x.rect(ca.left,ca.top-4,ca.right-ca.left,ca.bottom-ca.top+8);x.clip();
   for(let i=0;i<=p&&i<N;i++){const g=Math.abs(mb[i].y-ms[i].y);if(g<th){const a=.25+.2*Math.sin(ph+i);x.strokeStyle='#fbbf24';x.globalAlpha=a;x.lineWidth=1;const m=(mb[i].y+ms[i].y)/2;x.beginPath();x.arc(mb[i].x,m,3+(1-g/th)*2,0,7);x.stroke()}}
   if(!RM){if(hold>0){hold--;if(!hold)p=0}else{p+=sp;if(p>=N-1){p=N-1;hold=18}}}else p=N-1;
   for(let k=7;k>=0;k--){const f=p-k*sp*.6;if(f<0)continue;const a=(1-k/8)*.8,[bx,by]=at(mb,f),[sx,sy]=at(ms,f);dot(bx,by,k?1.6:2.8,'#2dd4bf',a);dot(sx,sy,k?1.6:2.8,'#f0544f',a)}
   const[bx,by]=at(mb,p),[sx,sy]=at(ms,p),gp=Math.abs(by-sy);window.BFXX=(RM||p>=N-1)?null:bx+1;ch.draw();
   x.globalAlpha=.7;x.strokeStyle=gp<th?'#fbbf24':'rgba(230,235,240,.4)';x.setLineDash([2,2]);x.beginPath();x.moveTo(bx,by);x.lineTo(sx,sy);x.stroke();x.setLineDash([]);
   if(gp<th&&!RM){const k=1-gp/th,mx=bx,my=(by+sy)/2,r=6+k*8+3*Math.sin(ph*2);x.shadowColor='#fbbf24';x.shadowBlur=14;x.globalAlpha=.5+.4*k;x.strokeStyle='#fde68a';x.lineWidth=1.6;x.beginPath();x.arc(mx,my,r,0,7);x.stroke();x.globalAlpha=.9;x.fillStyle='#fff';x.beginPath();x.arc(mx,my,2+k*2,0,7);x.fill();x.shadowBlur=0;
    if(pr.length<60)for(let q=0;q<3;q++){const a=Math.random()*6.283,v=1+Math.random()*2.2;pr.push({x:mx,y:my,vx:Math.cos(a)*v,vy:Math.sin(a)*v,l:1})}}
   pr=pr.filter(o=>o.l>0);for(const o of pr){o.x+=o.vx;o.y+=o.vy;o.vx*=.92;o.vy*=.92;o.l-=.09;dot(o.x,o.y,1.4,'#fde68a',Math.max(0,o.l))}
   x.restore();x.globalAlpha=1};
  tick();return()=>{clearTimeout(tm);window.BFXX=null}},[]);return h('canvas',{ref,style:{width:'100%',height:'100%',display:'block'}})}
 ReactDOM.createRoot(hd).render(h(FX))}
const FS={i:'',a:'',k:''};
function FL(r){const e=(r.C||[]).find(x=>x[0]==='e'),t=r.up+r.dn;
 if(FS.i==='i'&&!(e&&e[3]>.1))return false;if(FS.i==='r'&&!(e&&e[3]<-.1))return false;
 if(FS.a==='b'&&!(r.fnet>0))return false;if(FS.a==='s'&&!(r.fnet<0))return false;
 if(FS.k==='b'&&!(t>=3&&r.up/t>=.7))return false;if(FS.k==='s'&&!(t>=3&&r.dn/t>=.7))return false;return true}
function draw(){const{R}=S,q=ST.q.toUpperCase();R.forEach(r=>{if(r.hold==null)r.hold=(HMAP()[r.c]||{}).t||0});let L=R.filter(r=>(ST.t==='all'||(ST.t==='acc'?r.s>=15:r.s<=-15))&&(!q||r.c.includes(q)||r.nm.toUpperCase().includes(q))&&FL(r));
 const k=ST.s;L.sort((a,b)=>(k==='c'?a.c.localeCompare(b.c):(k==='up'?a.up-a.dn-(b.up-b.dn):(a[k]-b[k])))*(ST.asc?1:-1));
 if(!ST.asc&&ST.t==='dist'&&k==='s')L.reverse();
 $('#tb').innerHTML=L.slice(0,ST.lim).map(r=>{const[lb,co]=lab(r.s);return`<tr data-c="${r.c}"><td><b>${r.c}</b><small class="cn2">${esc(r.nm)}</small></td><td><span class="sb"><i style="width:${Math.min(50,Math.abs(r.s)/2)}%;${r.s>=0?'left:50%;background:var(--up);box-shadow:0 0 8px 1px var(--up)':'right:50%;background:var(--dn);box-shadow:0 0 8px 1px var(--dn)'}"></i></span><b class="${cl(r.s)}">${r.s.toFixed(0)}</b><small class="lb2" style="color:${co}">${lb}${r.dv?' ⚠':''}</small>${r.s>=45&&BM&&BM[r.c]&&BM[r.c].dy&&BM[r.c].dy.dini?'<span class="tc" style="display:inline-block;margin-top:3px;background:#a855f7;color:#fff" title="Early Smart Money: value ≥1,5× rata-rata; harga <3% hari ini dan <6% vs 5 sesi; sedikitnya 3 dari 5 konfirmasi aliran.">SMART MONEY</span>':''}</td><td class="${cl(r.net)}">${fm(r.net)}</td><td class="${cl(r.np)}">${r.so?r.np.toFixed(2)+'%':'-'}</td><td title="≥5%: ${(HMAP()[r.c]||{}).h5||0} · 1–5%: ${(HMAP()[r.c]||{}).h1||0}">${r.hold||'–'}</td><td class="${cl(r.fnet)}">${fm(r.fnet)}</td><td class="${cl(r.rp)}">${fr(r.rp)}</td><td>${r.px?r.px.toLocaleString('id-ID')+(r.chg==null?'':` <small class="${cl(r.chg)}">${r.chg>0?'+':''}${r.chg.toFixed(1)}%</small>`):'-'}</td><td>${r.up}↑ ${r.dn}↓</td><td class="dcc">${(()=>{try{const d=KEP(r.c),ph=BM&&BM[r.c]&&BM[r.c].ph,pl=ph&&ph.p&&PCC.ph[ph.p]?PNM(ph.p,ph.dr):'—';return'<div class="decision-amdx"><b class="decision-label" style="color:'+BCO[d.act]+'" title="'+esc(d.why||'')+'">'+d.act+' · '+(d.K==null?'—':Math.round(d.K))+'</b>'+'</div><small class="lb2">Fase: '+pl+'</small>'}catch(e){return'—'}})()}</td></tr>`}).join('');
 const sm=f=>L.reduce((a,r)=>a+r[f],0);$('#tf').innerHTML=`<tr><td>Total ${L.length} saham</td><td>${L.length?(sm('s')/L.length).toFixed(1):0} (rata²)</td><td class="${cl(sm('net'))}">${fm(sm('net'))}</td><td></td><td></td><td class="${cl(sm('fnet'))}">${fm(sm('fnet'))}</td><td class="${cl(sm('rp'))}">${fr(sm('rp'))}</td><td></td><td>${sm('up')}↑ ${sm('dn')}↓</td><td></td></tr>`;
 $('#cnt').textContent=`${Math.min(ST.lim,L.length)} dari ${L.length} · periode: ${S.ds.length?dl(S.ds[0])+(S.ds.length>1?'–'+dl(S.ds.at(-1)):''):'-'} (${S.ds.length} hari) · satuan: ${LOT?'lot':'saham'} · Net Rp ≈ net harian × harga penutupan hari itu`;$('#more').hidden=ST.lim>=L.length;animateDashboardCounters()}
document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{ST.t=b.dataset.t;ST.lim=10;ST.asc=false;document.querySelectorAll('[data-t]').forEach(x=>x.classList.toggle('on',x===b));draw()});
document.querySelectorAll('th[data-s]').forEach(h=>h.onclick=()=>{const s=h.dataset.s;ST.asc=ST.s===s?!ST.asc:false;ST.s=s;draw()});
$('#q').oninput=e=>{ST.q=e.target.value;ST.lim=10;draw()};$('#more').onclick=()=>{ST.lim+=10;draw()};$('#w').onchange=e=>{W=+e.target.value;run()};
$('#un').onchange=e=>{LOT=e.target.value==='1';run()};$('#bg').onchange=e=>{BG=e.target.value;run()};$('#tp').onchange=e=>{TP=e.target.value;ST.lim=10;run()};
AC($('#q'),()=>S?S.R.map(r=>[r.c,r.nm||'']):[]);AC($('#dq'),()=>DS&&DS.R?DS.R.map(r=>[r.c,r.nm||'']):[]);try{document.fonts&&document.fonts.load("9px 'JetBrains Mono'").then(()=>{try{run()}catch(e){}})}catch(e){}
[['fi','i'],['fa','a'],['fk','k']].forEach(([id,k])=>$('#'+id).onchange=e=>{FS[k]=e.target.value;ST.lim=10;draw()});
$('#tb').onclick=e=>{const tr=e.target.closest('tr');if(tr)detail(tr.dataset.c)};$('#ov').onclick=e=>{if(e.target.id==='ov')$('#ov').hidden=true};
let LV=null;
const DQ=(p,ch)=>p?`<div class="detail-quote"><small>Close</small><b>${Number(p).toLocaleString('id-ID')}</b>${ch==null?'':`<span class="${cl(ch)}">${ch>0?'+':''}${Number(ch).toFixed(1)}% hari ini</span>`}</div>`:'';
function detail(c){LV=()=>detail(c);const r=S.R.find(x=>x.c===c),{ds,kd}=S,[lb,co]=lab(r.s);
 const mv=Object.entries(r.mv).filter(x=>x[1]).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).slice(0,6);
 const top=[...r.C].sort((a,b)=>Math.abs(b[2]*b[3])-Math.abs(a[2]*a[3])).slice(0,3).filter(x=>Math.abs(x[3])>.1);
window.__hd1='<p class="mu">'+(r.px?'Harga '+r.px.toLocaleString('id-ID')+(r.chg==null?'':' ('+DCH(r.chg,(r.chg>0?'+':'')+r.chg.toFixed(1)+'%')+')')+' · ':'')+(top.map(x=>x[4]).join(' · ')||'Tidak ada pergerakan berarti.')+'</p>';
 let kl='';if(kd.length){const v=D.kl[kd.at(-1)][c];if(v){const isTot=nm=>/^\s*total\b/i.test(String(nm||'')),rows=D.klc.map((nm,i)=>[nm,+v[i]||0,i]).filter(([nm,x,i])=>i<v.length&&!isTot(nm)&&String(nm).trim()&&String(nm)!=='null'),tot=rows.reduce((a,r)=>a+r[1],0);if(tot>0)kl='<h3>Komposisi klasifikasi investor ('+dl(kd.at(-1))+')</h3>'+rows.filter(r=>r[1]>0).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([nm,x])=>{const p=Math.min(100,x/tot*100);return `<div class="cp"><span title="${esc(kln(nm))}">${esc(kln(nm))}</span><span class="sb"><i style="left:0;width:${p}%;background:var(--ac)"></i></span><span>${p.toFixed(1)}%</span></div>`}).join('')}}
 $('#pn').innerHTML=`<div class="bar"><h1 style="flex:1">${c} <small>${esc(r.nm)}</small></h1>${DQ(r.px??r.cl,r.chg??r.ch)}<button class="btn" id="x">✕</button></div>
 <p><span class="tag" style="background:${co}">${lb}</span> skor <b class="${cl(r.s)}">${r.s.toFixed(1)}</b> ${r.dv?'<span class="mu">⚠ sinyal jangka pendek &amp; bulanan berlawanan</span>':''}</p>

 <div class="rvr-layout"><div class="rvr-radar">${RAD(r.C)}</div><div class="rvr-candle">${RVW(c)}</div></div>${RVF(c)}<div class="daily-chart-grid">${BM[c]&&BM[c].dy?'<section class="daily-chart-panel"><h3>Harga &amp; value harian</h3><div class="ch"><canvas id="c4"></canvas></div></section>':''}<section class="daily-chart-panel"><h3>Aliran harian &amp; kumulatif pemegang ≥5% (${LOT?'lot':'saham'})</h3><div class="ch"><canvas id="c2"></canvas></div></section></div>${PCH()}
 ${r.tp.length?'<h3 style="margin-top:12px">Pergerakan kepemilikan per bulan (% saham beredar)</h3><div class="ch"><canvas id="c3"></canvas></div>':''}
 <h3 style="margin-top:12px">Pelaku terbesar (net periode)</h3>${mv.length?mv.map(([nm,x])=>`<div class="cp" style="grid-template-columns:1fr auto"><span>${esc(nm).slice(0,40)}${AFN(c,nm)}</span><b class="${cl(x)}">${fm(x)}${lp(c)?' · '+fr(x*lp(c)):''}</b></div>`).join(''):'<small>Tidak ada perubahan.</small>'}
 ${hold(c)}<div style="margin-top:12px">${kl}</div>`;
 $('#ov').hidden=false;$('#x').onclick=()=>$('#ov').hidden=true;PCI(c);DXI(c);RX();const cs=getComputedStyle(document.documentElement),up=cs.getPropertyValue('--up'),dn=cs.getPropertyValue('--dn');
 const FW=FLW(c);mk('c2',{type:'bar',data:{labels:FW.L.map(dl),datasets:[{label:'Net harian',data:FW.day,backgroundColor:FW.day.map(v=>v>=0?up:dn)},{type:'line',label:'Kumulatif',data:FW.cum,borderColor:'#f59e0b',tension:.3}]},options:{interaction:{mode:'index',intersect:false},plugins:{tooltip:{callbacks:{label:x=>x.dataset.label+': '+fm(x.parsed.y)}}},scales:{y:{ticks:{callback:v=>fm(v).replace('+','')}},x:{ticks:{maxRotation:0,autoSkip:true}}}}});
 if(r.tp.length)mk('c3',{type:'line',data:{labels:r.tp.map(t=>dl(t.d)),datasets:[['ret','Ritel <5%','#94a3b8'],['inst','Institusi <5%','#ef4444'],['blk','Pemegang ≥5%','#7c3aed'],['fr','Asing','#f59e0b']].map(([k,l,col])=>({label:l,data:r.tp.map(t=>+t[k].toFixed(2)),borderColor:col,backgroundColor:col,borderWidth:2,tension:.4,pointRadius:0}))},options:{interaction:{mode:'index',intersect:false},scales:{y:{title:{display:true,text:'% saham beredar'}}}}})}
const DT={f:'all',q:'',lim:25,min:1e9,s:'s',asc:false,d:'',w:1},g=(a,i)=>a&&a[i]||0,fv=v=>fr(v).slice(1),mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
function DY(d,ds){
 const i=ds.indexOf(d),pr=ds.slice(Math.max(0,i-5),i),P=D.px[d],R=[];
 for(const c in P){
  const a=P[c],cl=g(a,0),pv=g(a,1),vol=g(a,2),val=g(a,3),flowMissing=Number(a[17])===1,fq=flowMissing?null:g(a,4);
  if(!cl||!vol)continue;
  const op=g(a,7)||pv||cl,hi=g(a,8)||cl,lo=g(a,9)||cl,ch=pv?(cl/pv-1)*100:0,cp=hi>lo?(cl-lo)/(hi-lo)*2-1:0,
   fnet=flowMissing?null:g(a,5)-g(a,6),ov=g(a,12),bv=g(a,14),bo=flowMissing?null:(ov+bv?(bv-ov)/(ov+bv):0);
  const H=pr.map(x=>D.px[x][c]).filter(x=>g(x,3)>0),rv=H.length?val/mean(H.map(x=>g(x,3))):1,
   tradeBase=H.filter(x=>Number(x[17])!==1&&g(x,4)>0).map(x=>g(x,2)/g(x,4)),
   tk=flowMissing?null:H.length&&fq&&tradeBase.length?(vol/fq)/mean(tradeBase):1,
   has5=H.length===5,mo=has5?(cl/(g(H[0],0)||cl)-1)*100:null;
  const q5=[rv>=1.5,tk==null?null:tk>=1.3,fnet==null?null:fnet>0,bo==null?null:bo>.1,cp>.2],ns=q5.filter(Boolean).length,available=q5.filter(x=>x!==null).length,
   dini=has5&&rv>=1.5&&ch<3&&mo<6&&ns>=3&&available>=3,
   dwhy=dini?[`value ${rv.toFixed(1)}× rata² tetapi harga masih tenang (${ch>=0?'+':''}${ch.toFixed(1)}% hari ini, ${mo>=0?'+':''}${mo.toFixed(1)}% vs 5 sesi bursa sebelumnya)`,tk!=null&&tk>=1.3?`lot/transaksi ${tk.toFixed(1)}× biasanya (pemain besar)`:'',fnet>0?'asing net beli':'',bo!=null&&bo>.1?`bid dominan ${(bo*100).toFixed(0)}%`:'',cp>.2?'close di sisi atas range':''].filter(Boolean).join(' · '):'',
   sg=ch>.3?1:ch<-.3?-1:Math.sign(cp),C=[['Posisi close dalam range',.2,cp,`close di ${((cp+1)*50).toFixed(0)}% range (L ${lo} – H ${hi})`],['Candle close vs open',.1,th((cl/op-1)*50),`open ${op} → close ${cl}`]];
  if(fnet!=null)C.push(['Net asing',.15,th(fnet/vol*8),`asing net ${fr(fnet*cl)} (${(fnet/vol*100).toFixed(1)}% volume)`]);
  if(bo!=null)C.push(['Bid vs offer',.15,bo,`bid ${bv.toLocaleString('id-ID')} · offer ${ov.toLocaleString('id-ID')}`]);
  if(H.length){C.push(['Lonjakan value',.2,th(Math.log(rv))*sg,`value ${rv.toFixed(1)}× rata² ${H.length} hari`]);if(tk!=null)C.push(['Ukuran transaksi',.1,th(Math.log(tk))*(cp>=0?1:-1),`lot/transaksi ${tk.toFixed(1)}× biasanya`])}
  if(has5)C.push(['Momentum multi-hari',.1,th(mo/5),`${mo>=0?'+':''}${mo.toFixed(1)}% vs penutupan 5 sesi bursa sebelumnya`]);
  const w=C.reduce((x,y)=>x+y[1],0),baseScore=100*C.reduce((x,y)=>x+y[1]*y[2],0)/w,diniBonus=dini?10:0;if(dini)C.push(['Early Smart Money',.1,diniBonus/100,'Bonus +10 poin saat minimal 3/5 syarat terpenuhi']);R.push({d,c,pv,nm:D.nm[c]||'',cl,ch,val,fq,fnr:fnet==null?null:fnet*cl,bo,rv,ii:g(a,10),s:Math.max(-100,Math.min(100,baseScore+diniBonus)),C,spk:H.length>0&&rv>=2,dini,dns:ns,flowCoverage:available,dwhy,op,hi,lo})
 }
 return R}
function smartMoneyWindow(rows,currentClose){const latest=[...rows].reverse().find(r=>r.dini&&r.cl>0);if(!latest||!currentClose)return{dini:false,dns:0,diniDay:null,diniMove:null,dwhy:''};const valid=[...rows].reverse().find(r=>r.dini&&r.cl>0&&Math.abs(currentClose/r.cl-1)<.06);if(!valid){const move=currentClose/latest.cl-1;return{dini:false,dns:0,diniDay:null,diniMove:move,dwhy:`Sinyal ${dl(latest.d)} tidak aktif; harga berubah ${(move>=0?'+':'')+(move*100).toFixed(1)}% sejak sinyal`}}const move=currentClose/valid.cl-1;return{dini:true,dns:valid.dns,diniDay:valid.d,diniMove:move,dwhy:`${valid.dwhy} · sinyal ${dl(valid.d)}; harga kini ${(move>=0?'+':'')+(move*100).toFixed(1)}% dari harga saat sinyal`}}
function DA(){const ds=Object.keys(D.px).sort();if(!ds.length)return{R:[],ds,d:''};const d=ds.includes(DT.d)?DT.d:ds.at(-1),i=ds.indexOf(d),W=DT.w||9999,wd=ds.slice(Math.max(0,i-W+1),i+1),M={};
 wd.forEach(x=>DY(x,ds).forEach(r=>(M[r.c]=M[r.c]||[]).push(r)));const R=[];
 for(const c in M){const v=M[c],l=v.at(-1),n=v.length,sm=f=>v.reduce((a,r)=>a+(r[f]??0),0),val=sm('val'),fn=v.filter(r=>r.fnr!=null),bn=v.filter(r=>r.bo!=null),fqv=v.filter(r=>r.fq!=null);if(val/n<DT.min)continue;
  const smState=smartMoneyWindow(v,l.cl);R.push({...l,n,dini:smState.dini,dns:smState.dns,diniDay:smState.diniDay,diniMove:smState.diniMove,dwhy:smState.dwhy,s:sm('s')/n,val,fq:sm('fq'),fqDays:fqv.length,fnr:fn.length?sm('fnr'):null,fnrDays:fn.length,bo:bn.length?sm('bo')/bn.length:null,boDays:bn.length,ch:v[0].pv?(l.cl/v[0].pv-1)*100:l.ch,up:v.filter(r=>r.s>0).length,dn:v.filter(r=>r.s<0).length})}
 return{R,ds,d,n:wd.length}}
let DS;
function DR(){DS=DA();const{R,ds,d}=DS,sel=$('#dd');if(!sel)return;sel.innerHTML=ds.slice().reverse().map(x=>`<option value="${x}"${x===d?' selected':''}>${x.split('-').reverse().join('/')}</option>`).join('');
 const up=R.filter(r=>r.ch>0).length,dn=R.filter(r=>r.ch<0).length,K=(t,v,c='')=>`<div class="k"><small>${t}</small><b class="${c}">${v}</b></div>`,flow=R.filter(r=>r.fnr!=null),fs=flow.reduce((x,r)=>x+r.fnr,0),flowObs=flow.reduce((x,r)=>x+r.fnrDays,0),flowExp=R.reduce((x,r)=>x+r.n,0),flowText=flow.length?fr(fs)+(flowObs<flowExp?` <small class="mu">(${flowObs}/${flowExp} saham-hari)</small>`:''):'—';
 $('#dc').innerHTML=ds.length?K('Saham dianalisis',R.length)+K('Naik / Turun',`<span class="up">${up}</span> / <span class="dn">${dn}</span>`)+K('Total Value',fv(R.reduce((x,r)=>x+r.val,0)))+K('Total Net asing',flowText,cl(fs))+K('Buy ',R.filter(r=>r.s>=15).length,'up')+K('Early Smart Money',R.filter(r=>r.dini).length,'up')+K('Sell ',R.filter(r=>r.s<=-15).length,'dn'):'<div class="mu">Belum ada data harga. Unggah file Ringkasan Saham IDX.</div>';dd()}
function dd(){const{R,n}=DS;for(const[k,t]of[['val','Value'],['fnr','Asing net'],['ch','Harga']])document.querySelector('th[data-d='+k+']').textContent=(n>1&&k!=='ch'?'Total ':'')+t+(n>1&&k==='ch'?' (periode)':'');const q=DT.q.toUpperCase(),k=DT.s;let L=R.filter(r=>(DT.f==='all'||(DT.f==='acc'?r.s>=15:DT.f==='dist'?r.s<=-15:DT.f==='dini'?r.dini:r.spk))&&(!q||r.c.includes(q)||r.nm.toUpperCase().includes(q)));
 L.sort((a,b)=>(k==='c'?a.c.localeCompare(b.c):a[k]-b[k])*(DT.asc?1:-1));if(!DT.asc&&DT.f==='dist'&&k==='s')L.reverse();
 $('#dtb').innerHTML=L.slice(0,DT.lim).map(r=>{const[lb,co]=lab(r.s);return`<tr data-c="${r.c}"><td><b>${r.c}</b> <small class="cn">${esc(r.nm).slice(0,22)}</small></td><td><b class="${cl(r.s)}">${r.s.toFixed(0)}</b> <small style="color:${co}">${lb}</small></td><td>${r.cl.toLocaleString('id-ID')} <small class="${cl(r.ch)}">${r.ch>0?'+':''}${r.ch.toFixed(1)}%</small></td><td>${fv(r.val)}</td><td class="${cl(r.fnr)}" title="Arus asing tersedia ${r.fnrDays}/${r.n} sesi">${r.fnr==null?'—':fr(r.fnr)+(r.fnrDays<r.n?` <small class="mu">${r.fnrDays}/${r.n}</small>`:'')}</td><td class="${cl(r.bo)}">${r.bo==null?'—':(r.bo*100).toFixed(0)+'%'}</td><td>${r.rv.toFixed(1)}×${r.spk?' ⚡':''}${r.dini?' <small class="up">DINI</small>':''}</td><td>${n>1?r.up+'↑ '+r.dn+'↓':'-'}</td></tr>`}).join('');
 $('#dcnt').textContent=`${Math.min(DT.lim,L.length)} dari ${L.length} · ${n>1?'kumulatif '+n+' hari s/d '+dl(DS.d):'harian '+dl(DS.d)}`;$('#dmore').hidden=DT.lim>=L.length;animateDashboardCounters()}
function dtl(c){LV=()=>dtl(c);const r=DS.R.find(x=>x.c===c),[lb,co]=lab(r.s);$('#pn').innerHTML=`<div class="bar"><h1 style="flex:1">${c} <small>${esc(r.nm)}</small></h1>${DQ(r.px??r.cl,r.chg??r.ch)}<button class="btn" id="x">✕</button></div>
 <p><span class="tag" style="background:${co}">${lb}</span> skor <b class="${cl(r.s)}">${r.s.toFixed(1)}</b></p><p class="mu" style="font-size:6px">${r.n>1?`Periode ${r.n} hari: Total value ${fv(r.val)} · Total asing net ${r.fnr==null?'n/a':fr(r.fnr)+(r.fnrDays<r.n?` (${r.fnrDays}/${r.n} hari data)`:'' )} · skor = rata² harian. Hari terakhir: `:''}O <b style="font-size:9px">${r.op}</b> · H <b style="font-size:9px">${r.hi}</b> · L <b style="font-size:9px">${r.lo}</b> · C <b style="font-size:9px">${r.cl}</b> · <b style="font-size:9px">${r.fq==null?'frekuensi n/a':r.fq.toLocaleString('id-ID')+' transaksi'} </b> · Index individual <b style="font-size:9px">${r.ii}</b></p>
 ${r.dini?`<div class="rb" style="font-size:9px;line-height:1.4"><b class="up">Tanda dini smart money (${r.dns}/5 sinyal):</b> ${r.dwhy}</div>`:''}${RB(c)}<h3>Kontribusi komponen</h3>${r.C.map(x=>`<div class="cp" style="grid-template-columns:150px 1fr 44px"><span>${x[0]}</span><span class="sb"><i style="width:${Math.abs(x[2])*50}%;${x[2]>=0?'left:50%;background:var(--up)':'right:50%;background:var(--dn)'}"></i></span><span class="${cl(x[2])}">${(x[2]*100).toFixed(0)}</span></div><small style="display:block;margin:-2px 0 4px 2px;font-size:6px">${x[3]}</small>`).join('')}
 ${PCH()}<h3 style="margin-top:12px">Harga &amp; value harian</h3><div class="ch"><canvas id="c2"></canvas></div>${HP(c)}`;$('#ov').hidden=false;$('#x').onclick=()=>$('#ov').hidden=true;PCI(c);HC(c);
 const X=DS.ds.filter(d=>g(D.px[d][c],0)),cs=getComputedStyle(document.documentElement);
 mk('c2',{type:'bar',data:{labels:X.map(dl),datasets:[{type:'bar',label:'Value (Rp M)',data:X.map(d=>+(g(D.px[d][c],3)/1e9).toFixed(2)),backgroundColor:X.map(d=>{const a=D.px[d][c];return cs.getPropertyValue(g(a,0)>=g(a,1)?'--up':'--dn')}),yAxisID:'v'},{type:'line',label:'Close',data:X.map(d=>g(D.px[d][c],0)),borderColor:'#f59e0b',borderWidth:2,tension:.4,pointRadius:0,pointHoverRadius:3,yAxisID:'p'}]},options:{scales:{v:{position:'right',grid:{display:false}},p:{position:'left'}}}})}
document.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>{$('#v1').hidden=b.dataset.v!=='1';$('#v2').hidden=b.dataset.v!=='2';$('#v3').hidden=b.dataset.v!=='3';$('#v4').hidden=b.dataset.v!=='4';document.body.classList.toggle('sector-fullscreen',b.dataset.v==='3');document.querySelectorAll('[data-v]').forEach(x=>x.classList.toggle('on',x===b))});
document.querySelectorAll('[data-f]').forEach(b=>b.onclick=()=>{DT.f=b.dataset.f;DT.lim=50;document.querySelectorAll('[data-f]').forEach(x=>x.classList.toggle('on',x===b));dd()});
document.querySelectorAll('th[data-d]').forEach(h=>h.onclick=()=>{const s=h.dataset.d;DT.asc=DT.s===s?!DT.asc:false;DT.s=s;dd()});
$('#dq').oninput=e=>{DT.q=e.target.value;DT.lim=50;dd()};$('#dmore').onclick=()=>{DT.lim+=50;dd()};$('#dd').onchange=e=>{DT.d=e.target.value;DR()};$('#dl').onchange=e=>{DT.min=+e.target.value;DR()};$('#dw').onchange=e=>{DT.w=+e.target.value;DR()};$('#dtb').onclick=e=>{const tr=e.target.closest('tr');if(tr)dtl(tr.dataset.c)};
function HP(c){const r=S&&S.R.find(x=>x.c===c);if(!r)return'<h3 style="margin-top:12px">Data pemegang</h3><small class="mu">Tidak ada data pemegang untuk saham ini.</small>';
 const mv=Object.entries(r.mv||{}).filter(x=>x[1]).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).slice(0,6);
 return(r.tp&&r.tp.length?'<h3 style="margin-top:12px">Pergerakan kepemilikan per bulan (% saham beredar)</h3><div class="ch"><canvas id="c3"></canvas></div>':'')+'<h3 style="margin-top:12px">Perubahan kepemilikan pemegang ≥5% (net periode)</h3>'+(mv.length?mv.map(([nm,x])=>`<div class="cp" style="grid-template-columns:1fr auto"><span>${esc(nm).slice(0,40)}${AFN(c,nm)}</span><b class="${cl(x)}">${fm(x)}${lp(c)?' · '+fr(x*lp(c)):''}</b></div>`).join(''):'<small>Tidak ada perubahan.</small>')+hold(c)}
function HC(c){const r=S&&S.R.find(x=>x.c===c);if(r&&r.tp&&r.tp.length)mk('c3',{type:'line',data:{labels:r.tp.map(t=>dl(t.d)),datasets:[['ret','Ritel <5%','#94a3b8'],['inst','Institusi <5%','#ef4444'],['blk','Pemegang ≥5%','#7c3aed'],['fr','Asing','#f59e0b']].map(([k,l,col])=>({label:l,data:r.tp.map(t=>+t[k].toFixed(2)),borderColor:col,backgroundColor:col,borderWidth:2,tension:.4,pointRadius:0}))},options:{interaction:{mode:'index',intersect:false},scales:{y:{title:{display:true,text:'% saham beredar'}}}}})}
function showH(n){const sd=S.sd;if(!sd.length)return;const d=sd.at(-1),d0=sd.length>1?sd.at(-2):null,H=[],CO=new Map();
 for(const c in D.sat[d]){const row=D.sat[d][c],x=row.find(y=>y[0]===n);if(!x)continue;const pv=d0?((D.sat[d0][c]||[]).find(y=>y[0]===n)||[])[4]:null;H.push({c,pct:x[4],q:x[3],f:x[2],dd:pv==null?null:x[4]-pv,v:x[3]*lp(c)});
  for(const y of row){if(y[0]===n)continue;const m=CO.get(y[0])||{n:y[0],f:y[2],s:[]};m.s.push(c);CO.set(y[0],m)}}
 H.sort((a,b)=>b.v-a.v||b.pct-a.pct);const tv=H.reduce((a,h)=>a+h.v,0),fl=H.length&&H[0].f==='A'?'asing':'lokal';
 const NW=[...CO.values()].sort((a,b)=>b.s.length-a.s.length).slice(0,10).filter(m=>m.s.length>=Math.min(2,H.length));
 const stk=s=>s.slice(0,8).join(', ')+(s.length>8?' +'+(s.length-8):'');
 $('#pn').innerHTML=`<div class="bar"><button class="btn" data-bk="1">← Kembali</button><h1 style="flex:1;font-size:12px">${esc(n)} <small style="font-size:6px">${fl}</small></h1><button class="btn" id="x">✕</button></div>
 <p class="mu" style="font-size:8px">Pemegang ≥1% pada snapshot ${dl(d)}: ${H.length} saham${tv?' · total nilai ≈ '+fr(tv):''}</p>
 <h3>Saham yang dipegang</h3><div class="tw"><table style="min-width:420px"><thead><tr><th>Saham</th><th>%</th><th>Saham</th><th>Nilai Rp</th><th>Δ</th></tr></thead><tbody>`+H.map(h=>`<tr data-sc="${h.c}" style="cursor:pointer"><td><b>${h.c}</b> <small class="cn">${esc(D.nm[h.c]||'').slice(0,22)}</small></td><td>${h.pct.toFixed(2)}%</td><td>${fm(h.q).replace('+','')}</td><td>${lp(h.c)?fv(h.v):'-'}</td><td class="${h.dd==null?'':cl(+h.dd.toFixed(2))}">${h.dd==null?'-':(h.dd>0?'+':'')+h.dd.toFixed(2)+'pp'}</td></tr>`).join('')+`</tbody></table></div>
 <h3 style="margin-top:12px">Jaringan (pemegang lain di saham yang sama)</h3>`+(NW.length?NW.map(m=>`<div class="cp" style="grid-template-columns:1fr auto"><span><a data-h="${encodeURIComponent(m.n)}" style="cursor:pointer;color:var(--ac);text-decoration:underline dotted">${esc(m.n).slice(0,36)}</a><br><small style="font-size:7px">${stk(m.s)}</small></span><b>${m.s.length} saham</b></div>`).join('')+'<small class="mu" style="font-size:7px;display:block;margin-top:4px">Jaringan = pemegang lain yang sama-sama ada di saham ini, urut dari yang paling banyak tumpang tindih. Ini kedekatan dari data kepemilikan, bukan bukti afiliasi/satu grup.</small>':'<small>Tidak ada pemegang lain yang tumpang tindih.</small>');
 $('#x').onclick=()=>$('#ov').hidden=true;$('#pn').scrollTop=0}
$('#pn').addEventListener('click',e=>{const hs=e.target.closest('#hs'),bt=hs&&e.target.closest('[data-hm],[data-hi],[data-hn]');if(bt){if(bt.dataset.hm)HMD=+bt.dataset.hm;else if(bt.dataset.hi)HI=+bt.dataset.hi;else HI=Math.max(0,Math.min(S.sd.length-1,HI+ +bt.dataset.hn));hs.innerHTML=HB(hs.dataset.c);HSC();return}const a=e.target.closest('[data-h]');if(a){e.preventDefault();showH(decodeURIComponent(a.dataset.h));return}if(e.target.closest('[data-bk]')&&LV){LV();return}const t=e.target.closest('[data-sc]');if(t&&S.R.find(r=>r.c===t.dataset.sc))detail(t.dataset.sc)});
const lp=c=>{const k=Object.keys(D.px).sort();return k.length?((D.px[k.at(-1)]||{})[c]||[])[0]||0:0};
let HI=-1,HMD=1;
const NZ=new Set(['PT','TBK','CV','DRS','DR','IR','HJ','SE','SH','MM','MBA','LTD','LIMITED','PTE','PERSERO','PERSEROAN','PERUSAHAAN','INC','CORP','CO','LLC']),NK=s=>String(s).toUpperCase().replace(/\([^)]*\)/g,' ').replace(/[^A-Z0-9 ]/g,' ').split(/\s+/).filter(w=>w&&!NZ.has(w)).sort().join(' ')||String(s).toUpperCase().trim();
function MVP(cur,prv){const used=new Set(),K=prv.map(y=>NK(y[0])),pr=cur.map(x=>({x,q:null}));pr.forEach(p=>{const k=NK(p.x[0]),i=prv.findIndex((y,j)=>!used.has(j)&&K[j]===k);if(i>=0){used.add(i);p.q=prv[i]}});pr.forEach(p=>{if(p.q||!(p.x[3]>0))return;const i=prv.findIndex((y,j)=>!used.has(j)&&y[3]===p.x[3]);if(i>=0){used.add(i);p.q=prv[i]}});return{pr,gone:prv.filter((y,j)=>!used.has(j))}}
function HB(c){const sd=S.sd,N=sd.length;if(!N)return'';if(HI<0||HI>=N)HI=N-1;const d=sd[HI],dp=HI>0?sd[HI-1]:null,p=lp(c),nd=x=>+x.slice(8)+' '+BN[+x.slice(5,7)-1]+' '+x.slice(2,4);
 const cur=(D.sat[d][c]||[]).slice().sort((a,b)=>b[4]-a[4]),prv=dp?(D.sat[dp][c]||[]):[];
 let h=`<div class="bar" style="gap:6px"><button class="btn${HMD===1?' on':''}" data-hm="1">&gt;1%</button><button class="btn${HMD===2?' on':''}" data-hm="2">100%</button></div><div class="bar ms" style="gap:4px;flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;padding-bottom:4px">${sd.map((x,i)=>`<button class="btn${i===HI?' on':''}" data-hi="${i}">${BN[+x.slice(5,7)-1]} ${x.slice(2,4)}</button>`).join('')}</div><div class="bar"><small class="mu" style="flex:1;font-size:8px">Pembaruan terakhir ${nd(d)}</small><button class="btn" data-hn="-1">&lsaquo;</button><button class="btn" data-hn="1">&rsaquo;</button></div>`;
 if(HMD===2){const r=S.R.find(x=>x.c===c),T=(r&&r.tp||[]).filter(t=>t.d.slice(0,7)===d.slice(0,7)).at(-1)||(r&&r.tp||[]).filter(t=>t.d<=d).at(-1);
  return h+(T?'<small class="mu" style="font-size:8px;display:block;margin:4px 0">Komposisi menurut tipe investor ('+nd(T.d)+')</small>'+[['ret','Ritel <5%','#94a3b8'],['inst','Institusi <5%','#ef4444'],['blk','Pemegang \u22655%','#7c3aed'],['fr','Asing','#f59e0b']].map(([k,l,col])=>`<div class="cp"><span>${l}</span><span class="sb"><i style="left:0;width:${Math.min(100,T[k])}%;background:${col}"></i></span><span>${T[k].toFixed(2)}%</span></div>`).join(''):'<small>Tidak ada data komposisi untuk periode ini.</small>')}
 const row=(x,pv,now)=>{const ch=dp&&Math.abs(now-pv)>=.005;return`<tr style="cursor:default"><td><a data-h="${encodeURIComponent(x[0])}" style="font-size:10px;cursor:pointer;color:var(--ac);text-decoration:underline dotted" title="Lihat portofolio &amp; jaringan">${esc(x[0]).slice(0,34)}</a> <small style="font-size:6px">${x[2]==='A'?'asing':'lokal'}</small>${now&&x[3]?`<br><small style="font-size:7px">${fm(x[3]).replace('+','')} saham${p?' \u00b7 '+fv(x[3]*p):''}</small>`:''}</td><td style="text-align:right;white-space:nowrap">${ch?`<small>${pv.toFixed(2)}%</small> \u2192 <b class="${now>pv?'up':'dn'}">${now.toFixed(2)}%</b>`:`<b>${now.toFixed(2)}%</b>`}</td></tr>`};
 let rows=cur.map(x=>{const q=prv.find(y=>NK(y[0])===NK(x[0]));return row(x,q?q[4]:0,x[4])}).join('');
 if(dp)rows+=prv.filter(y=>!cur.some(x=>NK(x[0])===NK(y[0]))).map(y=>row(y,y[4],0)).join('');
 const tot=cur.reduce((a,x)=>a+x[4],0);
 return h+(cur.length?`<div class="tw"><table style="min-width:0"><thead><tr><th>Nama</th><th style="text-align:right">Kepemilikan</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><td><b>Total</b></td><td style="text-align:right"><b>${tot.toFixed(2)}%</b></td></tr></tfoot></table></div>`:'<small>Tidak ada pemegang \u22651% pada snapshot ini.</small>')}
function HSC(){try{const b=document.querySelector('#hs .ms .btn.on');if(!b)return;const s=b.parentElement,sr=s.getBoundingClientRect(),br=b.getBoundingClientRect();s.scrollLeft+=br.left-sr.left-(sr.width-br.width)/2}catch(e){}}
const TYN={CP:'Corporate',ID:'Individual',IB:'Financial Inst.',IS:'Insurance',MF:'Mutual Fund',PF:'Pension Fund',SC:'Securities Co.',FD:'Foundation',OT:'Lainnya'},BNL=['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
try{const SD={AGII:{'2026-09-30':3198,'2026-08-31':3613,'2026-07-31':3718,'2026-06-30':3571,'2026-05-31':3700,'2026-04-30':3863,'2026-03-31':4162,'2026-02-28':4632,'2026-01-31':5406,'2025-12-31':6263,'2025-11-30':6156,'2025-10-31':5530,'2025-09-30':6461,'2025-08-31':5568,'2025-07-31':5178}};D.hc=D.hc||{};for(const k in SD)D.hc[k]=Object.assign({},SD[k],D.hc[k])}catch(e){}
function HCN(c){const h=(D.hc||{})[c]||{},ks=Object.keys(h).sort().reverse(),f=v=>v.toLocaleString('id-ID');const rw=ks.map((k,i)=>{const p=ks[i+1],dv=p?h[k]-h[p]:null;return`<tr style="cursor:default"><td>${+k.slice(8)} ${BNL[+k.slice(5,7)-1]} ${k.slice(0,4)}</td><td>${f(h[k])}${dv==null?'':` <small class="${cl(dv)}">(${dv>0?'+':''}${f(dv)})</small>`}</td></tr>`}).join('');if(!rw)return'';return'<h3 style="margin-top:12px">Jumlah Pemegang Saham</h3>'+(rw?`<div class="tw" style="max-height:260px;overflow-y:auto"><table style="min-width:0"><tbody>${rw}</tbody></table></div>`:'<small class="mu">Belum ada data.</small>')+`<details><summary>Tambah / perbarui data</summary><textarea id="hcin" rows="4" style="width:100%;background:var(--bg);color:var(--tx);border:1px solid var(--bd);font:10px monospace" placeholder="30 Sep 2026 3,198&#10;31 Aug 2026 3,613"></textarea><button class="btn" data-hcs="${c}">Simpan</button></details>`}
$('#pn').addEventListener('click',e=>{const b=e.target.closest('[data-hcs]');if(!b)return;const c=b.dataset.hcs,o=Object.assign({},(D.hc||{})[c]);let k=0;for(const m of $('#hcin').value.matchAll(/(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+([\d.,]+)/g)){const mo=MO[m[2].slice(0,3).toUpperCase()];if(!mo)continue;o[m[3]+'-'+String(mo).padStart(2,'0')+'-'+m[1].padStart(2,'0')]=parseInt(m[4].replace(/[.,]/g,''),10);k++}if(!k)return;D.hc=D.hc||{};D.hc[c]=o;save({k:'hc',d:'-',data:D.hc});const hs=$('#hs');if(hs)hs.innerHTML=HB(c)});
const AFL={P:'Pengendali',T:'Terafiliasi'},AFH=t=>t&&AFL[t]?'<span class="aft"><i class="af-'+t+'">'+AFL[t]+'</i></span>':'',
 AFT=x=>AFH(x&&x[9]),
 AFN=(c,n)=>{const k=NK(n);for(const d of Object.keys(D.sat).sort().reverse()){const r=(D.sat[d][c]||[]).find(y=>NK(y[0])===k);if(r)return AFH(r[9])}return''};
const DN=s=>String(s==null?'':s).toUpperCase().replace(/^[.\s]+/,'').replace(/^PT[.\s]+/,'').replace(/[,\s]+PT\.?$/,'').trim();
function SMT(cur,prv,hp,p){const M=MVP(cur,prv),nf=v=>(LOT?v/100:v).toLocaleString('en-US',{maximumFractionDigits:0}),sg=v=>(v>0?'+':'-')+nf(Math.abs(v)),isF=z=>z==='A'||z==='F',hs=cur.some(x=>x[7]!=null||x[8]!=null),hd=cur.some(x=>x[6]),T=[0,0,0,0,0];
 const sc=(now,pv)=>{const dl=hp&&pv!=null?now-pv:0,k=dl>0?'up':dl<0?'dn':'';return`<td class="${k}">${nf(now)}${dl?`<br><small style="font-size:8px">${sg(dl)}</small>`:''}</td>`};
 const rw=(x,q,st)=>{const now=st==='out'?0:x[4],pv=st==='new'||!hp?(hp?0:null):q?q[4]:x[4],dm=hp?now-(pv||0):0,val=p&&x[3]&&st!=='out'?x[3]*p:0,sh=st==='out'?0:x[3],s7=st==='out'?0:x[7]||0,s8=st==='out'?0:x[8]||0,p7=st==='new'?0:st==='out'?x[7]||0:q?q[7]:null,p8=st==='new'?0:st==='out'?x[8]||0:q?q[8]:null;
  T[0]+=now;T[1]+=val;T[2]+=sh;T[3]+=s7;T[4]+=s8;
  const dc=hp&&Math.abs(dm)>=.005?`<span class="${dm>0?'up':'dn'}">${dm>0?'\u2197':'\u2198'} ${Math.abs(dm).toFixed(2)}%</span>`:'-',own=hp&&Math.abs(now-(pv||0))>=.005?`<small>${(pv||0).toFixed(2)}%</small> \u2192 <b class="${now>pv?'up':'dn'}">${now.toFixed(2)}%</b>`:`${now.toFixed(2)}%`;
  return`<tr style="cursor:default"><td><a data-h="${encodeURIComponent(x[0])}" style="cursor:pointer;color:var(--ac)" title="Lihat portofolio &amp; jaringan">${esc(DN(x[0])).slice(0,34)}</a>${AFT(x)}</td><td>${dc}</td><td style="white-space:nowrap">${own}</td><td>${val?fv(val):st==='out'?'0':'-'}</td><td>${nf(sh)}</td>${hs?sc(s7,p7)+sc(s8,p8):''}<td>${TYN[x[1]]||x[1]||'-'}</td><td style="color:${isF(x[2])?'var(--dn)':x[2]?'#a78bfa':'inherit'}">${isF(x[2])?'F':x[2]?'D':'-'}</td>${hd?`<td>${x[6]?esc(String(x[6])).toUpperCase():'-'}</td>`:''}</tr>`};
 let r=M.pr.map(z=>rw(z.x,z.q,hp&&!z.q?'new':'')).join('');if(hp)r+=M.gone.map(y=>rw(y,y,'out')).join('');
 return`<div class="tw"><table style="min-width:${hs?860:640}px;font-size:10px"><thead><tr><th>Name</th><th>\u0394 MoM%</th><th>Ownership</th><th>Value (Rp)</th><th>Total Shares</th>${hs?'<th>Scripless</th><th>Scrip</th>':''}<th>Type</th><th aria-label="Location"></th>${hd?'<th>Domicile</th>':''}</tr></thead><tbody>${r}</tbody><tfoot><tr><td><b>TOTAL</b></td><td></td><td><b>${T[0].toFixed(2)}%</b></td><td><b>${p?fv(T[1]):'-'}</b></td><td><b>${nf(T[2])}</b></td>${hs?`<td><b>${nf(T[3])}</b></td><td><b>${nf(T[4])}</b></td>`:''}<td></td><td></td>${hd?'<td></td>':''}</tr></tfoot></table></div>`}
const _HB0=HB;HB=function(c){const o=_HB0(c),i=o.indexOf('<div class="tw">');if(HMD!==1||i<0)return o+(HMD===1?HCN(c):'');const d=S.sd[HI],dp=HI>0?S.sd[HI-1]:null,p=lp(c),cur=(D.sat[d][c]||[]).slice().sort((a,b)=>b[4]-a[4]),prv=dp?(D.sat[dp][c]||[]):[];return o.slice(0,i)+SMT(cur,prv,!!dp,p)+HCN(c)};
function hold(c){if(!S.sd.length)return'';HI=-1;HMD=1;setTimeout(HSC,0);return`<h3 style="margin-top:12px">Shareholder Movement</h3><div id="hs" data-c="${c}">${HB(c)}</div>`}
run=(r0=>function(){const on=(S&&S.sd?S.sd.length:0),wl=HI<0||HI>=on-1;r0.apply(this,arguments);try{const h=document.querySelector('#hs');if(h&&S.sd.length){if(wl)HI=S.sd.length-1;h.innerHTML=HB(h.dataset.c);HSC()}}catch(e){}})(run);
const SEC={ENR:'Energi',BSC:'Bahan Dasar',IND:'Industri',CNC:'Konsumer Primer',CCL:'Konsumer Siklikal',HC:'Kesehatan',FIN:'Keuangan',PRO:'Properti',TEC:'Teknologi',INF:'Infrastruktur',TRA:'Transportasi'},SMAP={"ENR": "ADRO ADMR AADI PTBA ITMG INDY BUMI BYAN HRUM GEMS DOID KKGI MEDC PGAS AKRA ELSA ENRG APEX RUIS TOBA PTRO SMMT BSSR CNKO TEBE ABMM MCOL CUAN RAJA BREN DSSA ARII BIPI MYOH SURE WINS BULL", "BSC": "ANTM INCO MDKA TINS NCKL MBMA AMMN BRMS PSAB HRTA SMGR INTP SMBR SMCB TPIA BRPT INKP TKIM AVIA ESSA EKAD SRSN FPNI KRAS GDST NIKL CITA ZINC PURE DKFT BTON ISSP NICL IFSH", "IND": "ASII UNTR HEXA INTA ARNA TOTO AMFG LION KBLI KBLM JECC SCCO VOKS IKAI MLIA WTON", "CNC": "ICBP INDF UNVR MYOR CPIN JPFA AMRT HMSP GGRM WIIM CMRY CLEO MLBI ULTJ GOOD AALI LSIP TBLA SSMS DSNG SMAR PGUN ADES ROTI STTP CAMP AISA DLTA FOOD BUDI WMUF UNSP BWPT MIDI CPRO MAIN TAPG PALM ALTO CEKA HOKI KEJU SKBM SKLT TGKA ANJT JAWA SGRO BISI", "CCL": "ACES MAPI MAPA ERAA LPPF RALS SCMA MNCN FILM MSIN CSAP IMAS MPMX GJTL BRAM PZZA ESTA PANR PJAA BAYU FAST MAPB BMTR KPIG VIVA AUTO SMSM", "HC": "KLBF SIDO MIKA HEAL SILO PRDA TSPC KAEF INAF PYFA SAME DVLA MERK BMHS IRRA CARE SRAJ PEHA SOHO MTMH PRAY DGNS CSMI RSGK", "FIN": "BBCA BBRI BMRI BBNI BRIS BBTN BNGA BDMN BNLI MEGA PNBN BTPS NISP BJBR BJTM BNII MAYA ARTO AGRO BBYB BBKP NOBU SDRA BABP BCIC BSIM BVIC MCOR PNBS BFIN ADMF CFIN WOMF TIFA PNLF LPGI ASRM AMAG MREI ABDA BNBA AMOR POOL TRIM PEGE PNIN BPII TUGU MFIN VRNA BEKS BACA SMMA BBHI AMAR MASB BINA BGTG", "PRO": "BSDE CTRA SMRA PWON LPKR ASRI DMAS KIJA JRPT MKPI DILD APLN BKSL CITY LPCK RDTX PPRO TRIN BEST MTLA GPRA MDLN SSIA EMDE LCGP KOTA BAPA POLL FMII URBN RODA PLIN DUTI CBDK ROCK RISE TARA REAL ELTY", "TEC": "GOTO EMTK BUKA DCII EDGE MTDL MLPT ATIC WIFI IRSX DMMX CYBR NFCX MCAS KIOS ZYRX AWAN CASH BELI MSTI HDIT", "INF": "TLKM ISAT EXCL TOWR TBIG MTEL JSMR PGEO KEEN ADHI PTPP WIKA WSKT TOTL NRCA JKON META CMNP POWR CASA SUPR LINK IBST PORT MORA TGRA LCKM OASA HGII BALI", "TRA": "BIRD ASSA SMDR TMAS NELY BLTA GIAA HITS WEHA TAXI JAYA MIRA ELPI SAFE LRNA TNCA PURA BPTR IPCM PSSI HELI TRJA CMPP BBRM SOCI MBSS LEAD TRUK"},SM={};
for(const k in SMAP)SMAP[k].split(' ').forEach(t=>SM[t]=k);
const QC={Memimpin:'#2dd4bf',Membaik:'#60a5fa',Melemah:'#f5a623',Tertinggal:'#f0544f'},qn=(x,y)=>x>=100?(y>=100?'Memimpin':'Melemah'):(y>=100?'Membaik':'Tertinggal');
function RR(){const el=$('#rc');if(!el)return;const ds=Object.keys(D.px).sort(),N=+$('#rw').value,NR=Math.max(N,5),K=3,ks=Object.keys(SEC),I={},M=[100];ks.forEach(k=>I[k]=[100]);
 ds.forEach(d=>{const a={},t=[0,0];for(const c in D.px[d]){const x=D.px[d][c],cl=g(x,0),pv=g(x,1),w=pv*g(x,15)||g(x,3);if(!cl||!pv||!g(x,2)||!w)continue;const r=cl/pv-1,k=SM[c];t[0]+=w*r;t[1]+=w;if(k){a[k]=a[k]||[0,0];a[k][0]+=w*r;a[k][1]+=w}}
  M.push(M.at(-1)*(1+(t[1]?t[0]/t[1]:0)));ks.forEach(k=>I[k].push(I[k].at(-1)*(1+(a[k]?a[k][0]/a[k][1]:0))))});
 const L=M.length;if(L<NR+K+1){el.innerHTML=`<div class="mu">Butuh minimal ${NR+K} hari data harga (saat ini ${ds.length}). Unggah file Ringkasan Saham lebih banyak.</div>`;$('#rl').innerHTML='';return}
 const T={};ks.forEach(k=>{const rs=I[k].map((v,i)=>v/M[i]),ra=[];for(let t=NR-1;t<L;t++)ra[t]=100*rs[t]/(rs.slice(t-NR+1,t+1).reduce((a,b)=>a+b,0)/NR);const p=[];for(let t=Math.max(NR-1+K,L-NR);t<L;t++)p.push([ra[t],100*ra[t]/ra[t-K],ds[t-1]]);T[k]={p,rt:(I[k][L-1]/I[k][L-1-N]-1)*100,q:qn(...p.at(-1))}});
 const DV={};ks.forEach(k=>DV[k]=new Map());
 for(let t=Math.max(0,ds.length-N);t<ds.length;t++){const day=D.px[ds[t]],tw={},cr=[];for(const c in day){const x=day[c],a=g(x,0),pv=g(x,1),w=pv*g(x,15)||g(x,3);if(!a||!pv||!g(x,2)||!w)continue;const k=SM[c];if(!k)continue;tw[k]=(tw[k]||0)+w;cr.push([c,k,w*(a/pv-1)])}cr.forEach(([c,k,v])=>DV[k].set(c,(DV[k].get(c)||0)+v/tw[k]*100))}
 const drv=k=>{const up=T[k].rt>=0,s=[...DV[k].entries()].filter(x=>up?x[1]>0:x[1]<0).sort((a,b)=>up?b[1]-a[1]:a[1]-b[1]).slice(0,4);return s.length?`<div style="font-size:10px;margin-top:3px;line-height:1.5;white-space:normal;font-weight:400">${s.map(([c,v])=>`<span class="${cl(v)}" title="kontribusi ${v>0?'+':''}${v.toFixed(2)} pt">${c}</span>`).join(' ')}</div>`:''};
 const A=ks.flatMap(k=>T[k].p),rx=Math.max(1,...A.map(p=>Math.abs(p[0]-100)))*1.05,ry=Math.max(1,...A.map(p=>Math.abs(p[1]-100)))*1.05,X=x=>Math.min(625,Math.max(15,320+(x-100)/rx*290)),Y=y=>Math.min(485,Math.max(15,250-(y-100)/ry*230));
 let v=`<svg viewBox="0 0 640 500" preserveAspectRatio="none" style="width:100%;height:100%;font:10px 'JetBrains Mono',monospace">`+[['Membaik',0,0,'start',8],['Memimpin',320,0,'end',632],['Tertinggal',0,250,'start',8],['Melemah',320,250,'end',632]].map(([q,x,y,an,tx])=>`<rect x="${x}" y="${y}" width="320" height="250" fill="${QC[q]}" opacity=".07"/><text x="${tx}" y="${y?494:14}" text-anchor="${an}" style="fill:${QC[q]};letter-spacing:.08em">${q.toUpperCase()}</text>`).join('')+`<path d="M320 0V500M0 250H640" style="stroke:var(--bd)"/>`;
 ks.forEach(k=>{const t=T[k],c=QC[t.q],P=t.p.map(p=>X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1)),e=P.at(-1).split(',');v+=`<polyline points="${P.join(' ')}" fill="none" stroke="${c}" stroke-width="1.6" stroke-linejoin="round" opacity=".7"/>`+P.slice(0,-1).map(p=>`<circle cx="${p.split(',')[0]}" cy="${p.split(',')[1]}" r="1.8" fill="${c}" opacity=".6"/>`).join('')+`<circle cx="${e[0]}" cy="${e[1]}" r="4.5" fill="${c}"/><text x="${+e[0]+7}" y="${+e[1]+3}" style="fill:var(--tx)">${SEC[k]}</text>`});
 if(RC&&RD2)RRX(el,{T,ks,rx,ry,N,X,Y});else el.innerHTML=v+'</svg>';
 const cn=q=>ks.filter(k=>T[k].q===q).length;$('#rl').innerHTML=Object.keys(QC).map(q=>`<div class="cp" style="grid-template-columns:1fr auto"><span style="color:${QC[q]}">&#9632; ${q}</span><b>${cn(q)}</b></div>`).join('')+`<div class="tw" style="margin-top:8px"><table style="min-width:0"><thead><tr><th>Sektor</th><th>Kuadran</th><th>${N} hari</th></tr></thead><tbody>`+ks.slice().sort((a,b)=>T[b].rt-T[a].rt).map(k=>`<tr style="cursor:default"><td>${SEC[k]}${drv(k)}</td><td style="color:${QC[T[k].q]}">${T[k].q}</td><td class="${cl(T[k].rt)}">${T[k].rt>0?'+':''}${T[k].rt.toFixed(1)}%</td></tr>`).join('')+'</tbody></table></div>'}
$('#rw').onchange=RR;
try{const u=JSON.parse(localStorage.getItem('ksei_ui')||'{}');['w','un','bg','tp','fi','fa','fk','dl','dw'].forEach(id=>{const e=$('#'+id);if(e&&u[id]!=null&&[...e.options].some(o=>o.value===u[id]))e.value=u[id]});
 if(u.w!=null){W=+$('#w').value;LOT=$('#un').value==='1';BG=$('#bg').value;TP=$('#tp').value;DT.min=+$('#dl').value;DT.w=+$('#dw').value;FS.i=$('#fi').value;FS.a=$('#fa').value;FS.k=$('#fk').value}
 if(u.t){ST.t=u.t;document.querySelectorAll('[data-t]').forEach(x=>x.classList.toggle('on',x.dataset.t===u.t))}
 if(u.v&&u.v!=='1')document.querySelector('[data-v="'+u.v+'"]')?.click();else document.querySelector('[data-v="4"]')?.click()}catch(e){}
const saveUI=()=>{try{const u={};['w','un','bg','tp','fi','fa','fk','dl','dw','rw'].forEach(id=>u[id]=$('#'+id).value);u.t=document.querySelector('[data-t].on')?.dataset.t;u.v=document.querySelector('[data-v].on')?.dataset.v;localStorage.setItem('ksei_ui',JSON.stringify(u))}catch(e){}};
document.addEventListener('change',saveUI);document.addEventListener('click',e=>{if(e.target.closest('[data-t],[data-v]'))setTimeout(saveUI,0)});

const SG=a=>Math.sign(a),RD=v=>Math.round(v);
function FLW(c){const L=Object.keys(D.days).sort(),day=[],cum=[];let u=0;for(const d of L){let s=0;for(const x of D.days[d][c]||[])s+=x[3]-x[2];day.push(s);u+=s;cum.push(u)}return{L,day,cum}}
let BM={},BL=[];
function BSX(){const pd=Object.keys(D.px).sort(),ad=Object.keys(D.days).sort(),T=Object.keys(D.tipe).sort(),out=[];if(pd.length<3)return out;const lastd=pd.at(-1),LAST=D.px[lastd],DYM={};try{pd.slice(-(BSM.w||5)).forEach(x=>DY(x,pd).forEach(r=>(DYM[r.c]=DYM[r.c]||[]).push(r)))}catch(e){}
 for(const c in LAST){const cl=g(LAST[c],0);if(!cl)continue;
  const H=[];for(const d of pd){const a=D.px[d][c];if(g(a,0))H.push({d,op:g(a,7)||g(a,1)||g(a,0),cl:g(a,0),hi:g(a,8)||g(a,0),lo:g(a,9)||g(a,0),v:g(a,3)})}
  if(H.length<3)continue;const n=H.length,av=H.slice(-20).reduce((a,b)=>a+b.v,0)/Math.min(20,n);
  const rt=[];for(let i=Math.max(1,n-20);i<n;i++)rt.push(H[i].cl/H[i-1].cl-1);const mu=rt.reduce((a,b)=>a+b,0)/rt.length,sd=Math.sqrt(rt.reduce((a,b)=>a+(b-mu)**2,0)/rt.length)||.02,s5=sd*Math.sqrt(5);
  const sh=T.length?(D.tipe[T.at(-1)][c]||[])[0]||0:0;let bq=0,bc=0,sq=0,sc2=0,net=0,f10=0,has=false;const NW=BSM.w||10,RW=BSM.w?Math.max(20,Math.min(60,NW)):60,dates=ad.slice(-NW);
  for(const d of ad){const r=D.days[d][c];if(!r)continue;has=true;const pr=g(D.px[d]&&D.px[d][c],0)||cl;let s=0;for(const x of r){const q=x[3]-x[2];if(!q)continue;s+=q;if(q>0){bq+=q;bc+=q*pr}else{sq-=q;sc2-=q*pr}}if(!BSM.w||dates.includes(d))net+=s;if(dates.includes(d))f10+=s}
  const avgB=bq?bc/bq:0,avgS=sq?sc2/sq:0,base=sh||(H.slice(-20).reduce((a,b)=>a+b.v/b.cl,0)||1),f10n=f10/base*100,nn=net/base*100;
  const p10=cl/H[Math.max(0,n-1-NW)].cl-1,dchg=n>1&&H[n-2].cl?cl/H[n-2].cl-1:0,W60=H.slice(-RW),hi=Math.max(...W60.map(x=>x.hi)),lo=Math.min(...W60.map(x=>x.lo)),pos=hi>lo?(cl-lo)/(hi-lo):.5;
  const C=[],R=[];
  if(has){const kf=NW/10,kp=Math.sqrt(kf),ns=BSM.w?Math.max(.05,.3*Math.min(1,NW/Math.max(ad.length,1))):.3;C.push([.25,th(nn/ns)]);C.push([.2,th(f10n/(.1*kf))]);
   let dv=0;if(f10&&Math.abs(p10)>.03*kp){dv=SG(f10)*SG(-p10)>0?SG(f10)*Math.min(1,Math.abs(th(f10n/(.1*kf))*th(p10/(.08*kp)))*1.6):.3*SG(f10)}
   C.push([.25,dv]);
   if(dv>.25)R.push('Harga turun '+(p10*100).toFixed(1)+'% ('+NW+' hari) tapi pemegang ≥5% net beli: indikasi tekanan beli (LPM) saat harga murah.');else if(dv<-.25)R.push('Harga naik '+(p10*100).toFixed(1)+'% ('+NW+' hari) tapi pemegang ≥5% net jual: indikasi tekanan jual (LPM) saat harga tinggi.');else if(f10&&Math.abs(p10)>.03*kp)R.push('Harga dan aliran 5% searah ('+(f10>0?'beli':'jual')+').');
   R.push((BSM.w?'Net 5% '+NW+' hari terakhir ':'Net 5% seluruh periode ')+fm(net)+' saham ('+nn.toFixed(2)+'% saham beredar)'+(BSM.w?'.':'; 10 hari terakhir '+fm(f10)+'.'));
   if(avgB){const gp=cl/avgB-1;C.push([.15,net>0?th(-gp/.12):0]);R.push('Avg beli bandar '+RD(avgB).toLocaleString('id-ID')+(avgS?' · avg jual '+RD(avgS).toLocaleString('id-ID'):'')+'; harga kini '+(gp>=0?'+':'')+(gp*100).toFixed(1)+'% dari avg beli.')}}
  C.push([.15,-th((pos-.5)*2.5)]);R.push('Posisi di range '+RW+' hari: '+(pos*100).toFixed(0)+'% ('+(pos<.5?'discount':'premium')+' vs IRL '+RD((hi+lo)/2).toLocaleString('id-ID')+').');
  let RV=0;try{if(n>=20){const Bz=H.map(x=>({o:x.cl,h:x.hi,l:x.lo,c:x.cl,v:x.v})),az=PATR(Bz),Pz=PZZ(Bz,az),rz=PRSI(Bz),dz=PDV(Bz,Pz,az,rz,PTR(Bz,Pz,az)),rc=Math.max(5,Math.min(15,NW)),dd=dz.filter(x=>x.p2.i>=n-1-rc).at(-1);if(dd){const wv={bull:10,hbull:6,bear:-10,hbear:-6}[dd.k]||0;RV=wv;R.push('Divergence RSI '+({bull:'bullish (reguler)',hbull:'hidden bullish',bear:'bearish (reguler)',hbear:'hidden bearish'}[dd.k])+' (RSI '+dd.r1.toFixed(0)+' → '+dd.r2.toFixed(0)+', '+dl(H[dd.p2.i].d)+'): '+(wv>0?'+':'')+wv+' poin skor.')}}}catch(e){}
  let dy=null;{const v=DYM[c];if(v&&v.length){const l=v.at(-1),k=v.length,sm=f=>v.reduce((a,r)=>a+(r[f]??0),0),fn=v.filter(r=>r.fnr!=null),bn=v.filter(r=>r.bo!=null),ds=sm('s')/k,wB=C.reduce((a,b)=>a+b[0],0);const sw=smartMoneyWindow(v,l.cl);dy={n:k,l,val:sm('val'),dns:sw.dns,diniDay:sw.diniDay,diniMove:sw.diniMove,C:l.C.map(x=>{const a=v.map(r=>(r.C.find(y=>y[0]===x[0])||[])[2]).filter(z=>z!=null);return[x[0],x[1],a.reduce((p,q)=>p+q,0)/a.length,x[3]]}),s:ds,fnr:fn.length?sm('fnr'):null,fnrDays:fn.length,bo:bn.length?sm('bo')/bn.length:null,boDays:bn.length,rv:l.rv,rvmax:Math.max(...v.map(r=>r.rv)),dini:sw.dini,dwhy:sw.dwhy};C.push([wB*2/3,ds/100]);R.push('Aliran harian ('+k+' hari, 40% skor): skor day trading '+ds.toFixed(0)+'; asing net '+(dy.fnr==null?'n/a':fr(dy.fnr)+(dy.fnrDays<k?' ('+dy.fnrDays+'/'+k+' hari data)':''))+'; bid/offer '+(dy.bo==null?'n/a':(dy.bo>=0?'+':'')+(dy.bo*100).toFixed(0)+'%'+(dy.boDays<k?' ('+dy.boDays+'/'+k+' hari data)':''))+'; value hari terakhir '+l.rv.toFixed(1)+'× rata².');}}
  const w=C.reduce((a,b)=>a+b[0],0),sc=Math.max(-100,Math.min(100,100*C.reduce((a,b)=>a+b[0]*b[1],0)/w*(has?1:.4)+RV)),rec=!has?'HOLD':sc>=30?'BUY':sc<=-30?'SELL':'HOLD',irl=(hi+lo)/2;
  let t1,t2,st;if(rec==='SELL'){t1=irl<cl*.99?irl:cl*(1-s5);t2=Math.min(lo,cl*(1-2*s5));st=Math.min(hi,cl*(1+2*s5))}else{t1=irl>cl*1.01?irl:cl*(1+s5);t2=Math.max(hi,cl*(1+2*s5));st=Math.max(lo<cl?lo:0,cl*(1-2*s5))}
  let en=null;try{if(n>=5){const Bz=H.map(x=>({o:x.cl,h:x.hi,l:x.lo,c:x.cl,v:x.v})),Pz=PZZ(Bz,PATR(Bz)),wt=rec==='SELL'?'L':rec==='BUY'?'H':Pz.at(-1)?.t;let k=-1;for(let q=Pz.length-1;q>=1;q--)if(Pz[q].t===wt){k=q;break}
  if(k>0){const a=Pz[k-1],b=Pz[k],up=b.t==='H',Rg=Math.abs(b.p-a.p);if(Rg>0){const zz=r=>up?b.p-r*Rg:b.p+r*Rg,za=zz(.62),zb=zz(.79),zl=Math.min(za,zb),zh=Math.max(za,zb),ret=(up?b.p-cl:cl-b.p)/Rg,s=ret<0?'tunggu pullback':ret<.62?'belum retrace':ret<=.79?'DI ZONA OTE':ret<=1?'lewat OTE':'leg gagal';
   en={up,lo:RD(zl),hi:RD(zh),mid:RD(zz(.705)),ret,s,a:RD(a.p),b:RD(b.p),d:H[b.i].d,ea:cl>zh?(cl-zh)/cl:cl<zl?(zl-cl)/cl:0}}}}}catch(e){en=null}
let ph=null,ew=null,ax=null;try{if(n>=5){const Bz=H.map(x=>({d:x.d,o:x.op||x.cl,h:x.hi,l:x.lo,c:x.cl,v:x.v})),at=PATR(Bz),r=PPH(Bz,at);if(r){const sg=r.segs.at(-1);ph={p:sg.p,d:H[sg.s].d,n:sg.e-sg.s+1,dr:sg.dr};ax=AMX(Bz,ph)}ew=PEW(PZZ(Bz,at))}}catch(e){}
  out.push({c,nm:D.nm[c]||'',px:cl,en,ph,ax,ew,dy,fnr:dy?dy.fnr:null,bo:dy?dy.bo:null,rv:dy?dy.rv:null,ea:en?en.ea:null,sc,rec,net,nn,f10,p10,dchg,avgB,avgS,gap:avgB?cl/avgB-1:null,t1:RD(t1),t2:RD(t2),st:RD(st),hi:RD(hi),lo:RD(lo),irl:RD(irl),sd,s5,R,has,av})}
 return out}
const ENC=x=>{const e=x.en;if(!e)return'-';const col=e.up?'#2dd4bf':'#f0544f';return `<b style="color:${col}">${e.lo.toLocaleString('id-ID')}–${e.hi.toLocaleString('id-ID')}</b> <small style="font-size:6px" class="mu">${e.up?'↑ buy':'↓ sell'}</small><br><small style="font-size:6px" class="${e.s==='DI ZONA OTE'?'up':'mu'}">${e.s}${e.ea?' ('+(e.ea*100).toFixed(1)+'% dari zona)':''}</small>`};
const PHC=x=>{const p=x.ph;if(!p)return'-';const m=PCC.ph[p.p];return `<b style="color:${m[1]};font-weight:normal">${PNM(p.p,p.dr)}</b><br><small style="font-size:6px" class="mu">${p.n} hari sejak ${p.d.split('-').slice(1).reverse().join('/')}</small>`};
const EWC=x=>{const e=x.ew;if(!e){let t=[];try{t=TGX(x.c)}catch(_){}if(t.length)return t.map(s=>`<span class="tc" style="background:${s[1]}" title="${esc(s[2])}">${s[0]}</span>`).join(' ')}return e?`<small style="font-size:8px;line-height:1.2;color:${e.s>0?'#2dd4bf':'#f0544f'}">${e.t}</small>`:'<small style="font-size:8px" class="mu">-</small>'};
function PEW(P){const n=P.length;for(const m of[6,5]){if(n<m)continue;const w=P.slice(-m),s=w[1].p>w[0].p?1:-1,L=i=>Math.abs(w[i+1].p-w[i].p),pv=!!P.at(-1).prov;
 if(!(s*(w[2].p-w[0].p)>0&&s*(w[3].p-w[1].p)>0&&(m===6?L(2)>=Math.min(L(0),L(4)):L(2)>L(0))&&s*(w[4].p-w[1].p)>0&&(m<6||s*(w[5].p-w[3].p)>0)))continue;
  const a=s>0?'↑':'↓';return{s,m,t:m===6?'Impulse '+a+(pv?': gel. 5 berjalan':': gel. 5 selesai, waspada koreksi A-B-C'):'Impulse '+a+(pv?': gel. 4 berjalan':': gel. 4 selesai, gel. 5 diharapkan')}}return null}
const SGM={};
function SGX(c){const ds=Object.keys(D.px).sort(),dt=ds.at(-1),a=dt&&D.px[dt]&&D.px[dt][c],key=c+'|'+ds.length+'|'+dt+'|'+(a?[a[0],a[1],a[8]].join(':'):'-');if(SGM[key])return SGM[key];let o=[];try{o=TGX(c).slice()}catch(e){}
 try{const B=PCB(c),N=B.length;if(N>=10){const at=PATR(B),P=PZZ(B,at),rs=PRSI(B),tr=PTR(B,P,at),dv=PDV(B,P,at,rs,tr),d=dv.at(-1);if(d&&d.p2.i>=N-20){const nm={bear:'Div bearish',bull:'Div bullish',hbear:'Hidden div bearish',hbull:'Hidden div bullish'}[d.k];o.push([nm,d.k.endsWith('bull')?'#2dd4bf':'#f0544f','Divergence RSI vs harga: harga '+Math.round(d.p1.p).toLocaleString('id-ID')+' → '+Math.round(d.p2.p).toLocaleString('id-ID')+', RSI '+d.r1.toFixed(0)+' → '+d.r2.toFixed(0)+(d.conf?'':' (pivot terakhir belum terkonfirmasi)')])}}}catch(e){}
 SGM[key]=o;return o}
const compactFilterTag=s=>{const m=String(s).match(/^(?:Top Gainer|Pre-ARA)\s+(\d+)(?:\/100)?$/i);return m?m[1]:/^(?:Top Gainer|Pre-ARA)\b/i.test(String(s))?'':s};
const PHT=x=>{const sg=SGX(x.c),h4=FOUR_HORSEMEN_MAP[x.c]||[],h4tag=h4.length?`<span class="tc" style="background:#14b8a6" title="${esc(h4.join(' · '))}">4 HORSEMEN</span>`:'',tg=sg.length||h4tag?'<div class="tgs" style="margin-top:2px">'+sg.map(s=>{const label=compactFilterTag(s[0]);return label?`<span class="tc" style="background:${s[1]}" title="${esc(s[2])}">${esc(label)}</span>`:''}).join('')+h4tag+'</div>':'';const f=PHC(x);return(f==='-'?'':f)+tg||'-'};
const BCO={BUY:'#2dd4bf',HOLD:'#60a5fa',WAIT:'#f59e0b',SELL:'#f0544f'};
const DDIR=v=>v<0?'dir-neg':v>0?'dir-pos':'dir-zero',DCH=(v,t)=>`<span class="${DDIR(v)}">${t}</span>`,DTXT=t=>String(t).replace(/([+−-]\s*\d[\d.,]*(?:\s*(?:Jt|M|×|%|poin))?)/g,m=>`<span class="${m.trim()[0]==='+'?'dir-pos':'dir-neg'}">${m}</span>`).replace(/\b(turun)\s+([\d.,]+%)/gi,'$1 <span class="dir-neg">$2</span>').replace(/\b(naik)\s+([\d.,]+%)/gi,'$1 <span class="dir-pos">$2</span>');
function RB(c){const x=BM[c];if(!x)return'';const B=PCB(c),atr=PATR(B),P=PZZ(B,atr),lv=PLV(B,atr,P),trend=lv.trend,pc=v=>(v/x.px-1)*100,f=v=>v.toLocaleString('id-ID')+' <small class="'+DDIR(v-x.px)+'">'+(pc(v)>=0?'+':'')+pc(v).toFixed(1)+'%</small>',ahead=lv.irls.filter(q=>trend>0?q.rh>=x.px:trend<0?q.rl<=x.px:true).sort((a,b)=>Math.abs((a.rl+a.rh)/2-x.px)-Math.abs((b.rl+b.rh)/2-x.px)),gap=ahead[0],upperClass=trend>0?'trend-up':trend<0?'level-muted':'trend-flat',lowerClass=trend<0?'trend-down':trend>0?'level-muted':'trend-flat',gapClass=gap?(gap.up?'trend-up':'trend-down'):'level-muted',level=v=>v==null?'—':Math.round(v).toLocaleString('id-ID'),flowTrend=trend>0?'tren swing naik':trend<0?'tren swing turun':'tren swing netral';
 return '<div class="rb">'+(x.has?'':'<div class="bar" style="margin:0"><small class="mu">data 5% belum ada: hanya dari posisi harga</small></div>')+'<ul>'+x.R.map(t=>'<li>'+DTXT(t)+'</li>').join('')+'</ul>'+(x.en?'<div class="tg">Area entry <b style="font-size:12px">'+f(x.en.lo)+' – '+f(x.en.hi)+'</b> <small class="mu" style="font-size:7px">OTE '+(x.en.up?'bullish (buy)':'bearish (sell)')+' · 70,5% '+x.en.mid.toLocaleString('id-ID')+' · leg '+x.en.a.toLocaleString('id-ID')+'→'+x.en.b.toLocaleString('id-ID')+' ('+x.en.d.split('-').reverse().join('/')+') · '+x.en.s+'</small></div>':'')+'<div class="tg">Fase: '+PHC(x).replace('<br>',' · ')+' · Struktur: '+EWC(x)+'</div><div class="ict-level-strip" title="ERL = swing high/low terkonfirmasi; IRL = zona FVG aktif di dalam dealing range."><div class="ict-level"><small>ERL atas</small><strong class="ict-level-price '+upperClass+'">'+level(lv.hi&&lv.hi.p)+'</strong></div><div class="ict-level"><small>IRL · FVG aktif</small><strong class="ict-level-price '+gapClass+'">'+(gap?level(gap.rl)+'–'+level(gap.rh):'—')+'</strong></div><div class="ict-level"><small>ERL bawah</small><strong class="ict-level-price '+lowerClass+'">'+level(lv.lo&&lv.lo.p)+'</strong></div><small class="ict-level-meta">'+flowTrend+' · σ '+(x.sd*100).toFixed(1)+'%/hari (±'+(x.s5*100).toFixed(1)+'%/minggu)</small></div></div>'}
function BR(){BL=BSX();BM={};BL.forEach(x=>{x.rec0=x.rec;x.sc0=x.sc;BM[x.c]=x});BL.forEach(x=>{const d=KEP(x.c);x.dc=d;x.rec=d.act;x.sc=d.K==null?0:d.K});if(!$('#bc'))return;const n=r=>BL.filter(x=>x.rec===r&&x.av>=BSM.min).length,K=(t,v,c='')=>`<div class="k"><small>${t}</small><b class="${c}">${v}</b></div>`,flowRows=BL.filter(x=>x.av>=BSM.min&&x.dy),flow=flowRows.filter(x=>x.fnr!=null),flowSum=flow.reduce((a,x)=>a+x.fnr,0),flowDays=flow.reduce((a,x)=>a+x.dy.fnrDays,0),flowExpected=flowRows.reduce((a,x)=>a+x.dy.n,0),flowText=flow.length?fr(flowSum)+(flowDays<flowExpected?` <small class="mu">(${flowDays}/${flowExpected} saham-hari)</small>`:''):'—';
 $('#bc').innerHTML=BL.length?K('Saham dianalisis',BL.filter(x=>x.av>=BSM.min).length)+K('Naik / Turun',`<span class="up">${BL.filter(x=>x.av>=BSM.min&&x.dchg>0).length}</span> / <span class="dn">${BL.filter(x=>x.av>=BSM.min&&x.dchg<0).length}</span>`)+K('Total Value',fv(BL.filter(x=>x.av>=BSM.min).reduce((a,x)=>a+(x.dy?x.dy.l.val:0),0)))+K('Buy',n('BUY'),'up')+K('Hold',n('HOLD'))+K('Wait',n('WAIT'))+K('Sell',n('SELL'),'dn')+K('Early Smart Money',BL.filter(x=>x.dy&&x.dy.dini&&x.av>=BSM.min).length,'up')+K('Net asing',flowText,cl(flowSum)):'<div class="mu">Belum ada data harga. Unggah file Ringkasan Saham IDX.</div>';bd();CUX();try{draw()}catch(e){}}
const signalTagMatch=(code,tag)=>{if(tag==='early_smart_money')return!!(BM[code]&&BM[code].dy&&BM[code].dy.dini);if((SIGNAL_TAGS[tag]||[]).includes(code))return true;if(tag==='potensi_ara')return!!ARAHitToday(code);if(tag==='potensi_breakout')return SGX(code).some(t=>/^(breakout|pot\.\s*breakout)/i.test(t[0]));return false};
function bd(){const q=BSM.q.toUpperCase(),k=BSM.s;let L=BL.filter(x=>x.av>=BSM.min&&(BSM.f==='all'||x.rec===BSM.f||(BSM.f==='SPK'&&x.dy&&x.dy.rvmax>=2))&&(!BSM.tags.length||BSM.tags.some(tag=>signalTagMatch(x.c,tag)))&&(!q||x.c.includes(q)||x.nm.toUpperCase().includes(q))),horsemen=BL.filter(x=>SIGNAL_TAGS.four_horsemen.includes(x.c));
 L.sort((a,b)=>(k==='c'?a.c.localeCompare(b.c):((a[k]??(k==='ea'?9:-9))-(b[k]??(k==='ea'?9:-9))))*(BSM.asc?1:-1));
 const emptySignalMessage=BSM.tags.includes('four_horsemen')&&horsemen.some(x=>x.av<BSM.min)?horsemen.filter(x=>x.av<BSM.min).length+' kandidat 4 Horsemen berada di bawah batas value rata-rata yang dipilih. Pilih “Semua likuiditas” untuk melihatnya.':'Tidak ada saham yang lolos filter aktif pada snapshot harga terakhir. Periksa pilihan filter dan tanggal data.'; $('#btb').innerHTML=L.length?L.slice(0,BSM.lim).map(x=>`<tr data-c="${x.c}"><td><b>${x.c}</b> <small class="cn">${esc(x.nm).slice(0,22)}</small></td><td><span class="bt" style="background:${BCO[x.rec]}">${x.rec}</span> <small class="${cl(x.sc)}">${x.sc.toFixed(0)}</small>${x.dy&&x.dy.dini?`<br><span class="tc" style="background:#a855f7" title="${esc(x.dy.dwhy)}">SMART MONEY · ${x.dy.diniDay?dl(x.dy.diniDay):''}</span>`:''}</td><td>${PHT(x)}</td><td>${x.px.toLocaleString('id-ID')} <small class="${cl(x.dchg)}">${x.dchg>0?'+':''}${(x.dchg*100).toFixed(1)}%</small></td><td>${x.avgB?RD(x.avgB).toLocaleString('id-ID')+' <small class="'+cl(x.gap)+'">'+(x.gap>0?'+':'')+(x.gap*100).toFixed(1)+'%</small>':'-'}</td><td class="${cl(x.net)}">${fm(x.net)}</td><td class="${x.dy?cl(x.fnr):''}">${x.dy?fr(x.fnr):'-'}</td><td class="${x.dy?cl(x.bo):''}">${x.dy&&x.bo!=null?(x.bo>=0?'+':'')+(x.bo*100).toFixed(0)+'%':'-'}</td><td>${x.dy?x.rv.toFixed(1)+'×':'-'}</td><td>${ENC(x)}</td><td>${x.t1.toLocaleString('id-ID')}</td><td>${x.t2.toLocaleString('id-ID')}</td><td>${x.st.toLocaleString('id-ID')}</td></tr>`).join(''):`<tr><td colspan="13" class="mu">${emptySignalMessage}</td></tr>`;
 $('#bcnt').textContent=`${Math.min(BSM.lim,L.length)} dari ${BL.filter(x=>x.av>=BSM.min).length} kandidat likuid · ${L.length} lolos filter · data harga s/d ${Object.keys(D.px).sort().at(-1)?.split('-').reverse().join('/')||'-'}`;$('#bmore').hidden=BSM.lim>=L.length;animateDashboardCounters()}
const BSM={f:'all',tags:[],q:'',lim:10,min:0,s:'sc',asc:false,w:0};
const SIGNAL_TAGS={divergence:[],mss:[],potensi_breakout:[],potensi_ara:[],potensi_ara_early:[],potensi_ara_momentum:[],potensi_top_gainer:[],four_horsemen:[],mean_reversion:[],strong_bullish:[],early_smart_money:[]};const ARA_SCORE_MAP={},TG_SCORE_MAP={},FOUR_HORSEMEN_MAP={};
async function loadSignalTags(){try{const r=await fetch('/api/screener/tags',{cache:'no-store'});if(!r.ok)return;const j=await r.json();if(!j.ok)return;for(const k of Object.keys(SIGNAL_TAGS))SIGNAL_TAGS[k]=Array.isArray(j.tags&&j.tags[k])?j.tags[k]:[];Object.keys(ARA_SCORE_MAP).forEach(k=>delete ARA_SCORE_MAP[k]);Object.assign(ARA_SCORE_MAP,j.tags.ara_scores||{});Object.keys(TG_SCORE_MAP).forEach(k=>delete TG_SCORE_MAP[k]);Object.assign(TG_SCORE_MAP,j.tags.top_gainer_scores||{});Object.keys(FOUR_HORSEMEN_MAP).forEach(k=>delete FOUR_HORSEMEN_MAP[k]);Object.assign(FOUR_HORSEMEN_MAP,j.tags.four_horsemen_rules||{});Object.keys(SGM).forEach(k=>delete SGM[k]);bd();TGL();renderWL()}catch(e){}}
setTimeout(loadSignalTags,2500);setInterval(loadSignalTags,60000);
const DXP=c=>{const x=BM[c],d=x&&x.dy;if(!d)return'';const r=d.l,b=t=>`<b class="n">${t}</b>`,s=(v,t)=>`<b class="n ${DDIR(v)}">${t}</b>`,fn=d.fnr==null?b('n/a'):s(d.fnr,fr(d.fnr)+(d.fnrDays<d.n?` (${d.fnrDays}/${d.n} hari data)`:''));return `<p class="mu">${d.n>1?`Periode ${d.n} hari: Total value ${b(fv(d.val))} · Total asing net ${fn} · skor = rata² harian. Hari terakhir: `:''}O ${b(r.op)} · H ${b(r.hi)} · L ${b(r.lo)} · C ${b(r.cl)} · ${r.fq==null?'frekuensi n/a':r.fq.toLocaleString('id-ID')+' transaksi'} · Index individual ${r.ii}</p>`};
const DXH=c=>{const x=BM[c],d=x&&x.dy;if(!d||!d.dini||!d.dwhy)return'';return `<section class="rvr-dini"><b class="rvr-dini-title">Tanda dini smart money (${d.dns}/5 sinyal)</b><p>${DTXT(d.dwhy)}</p></section>`};
const DXI=c=>{if(!$('#c4'))return;const X=Object.keys(D.px).sort().filter(d=>g(D.px[d][c],0)),cs=getComputedStyle(document.documentElement);mk('c4',{type:'bar',data:{labels:X.map(dl),datasets:[{type:'bar',label:'Value (Rp M)',data:X.map(d=>+(g(D.px[d][c],3)/1e9).toFixed(2)),backgroundColor:X.map(d=>{const a=D.px[d][c];return cs.getPropertyValue(g(a,0)>=g(a,1)?'--up':'--dn')}),yAxisID:'v'},{type:'line',label:'Close',data:X.map(d=>g(D.px[d][c],0)),borderColor:'#f59e0b',borderWidth:2,tension:.4,pointRadius:0,pointHoverRadius:3,yAxisID:'p'}]},options:{scales:{v:{position:'right',grid:{display:false}},p:{position:'left'}}}})};
document.querySelectorAll('[data-bw]').forEach(b=>b.onclick=()=>{BSM.w=+b.dataset.bw;BSM.lim=10;document.querySelectorAll('[data-bw]').forEach(x=>x.classList.toggle('on',x===b));const h=document.querySelector('th[data-bs="net"]');if(h)h.textContent=BSM.w?'Net 5% ('+b.textContent+')':'Net 5% (semua)';BR()});
document.querySelectorAll('[data-bx]').forEach(b=>b.onclick=()=>{const tag=b.dataset.bx;if(tag==='all')BSM.tags=[];else BSM.tags=BSM.tags.includes(tag)?BSM.tags.filter(x=>x!==tag):[...BSM.tags,tag];BSM.lim=10;document.querySelectorAll('[data-bx]').forEach(x=>x.classList.toggle('on',x.dataset.bx==='all'?!BSM.tags.length:BSM.tags.includes(x.dataset.bx)));bd()});
document.querySelectorAll('[data-b]').forEach(b=>b.onclick=()=>{BSM.f=b.dataset.b;BSM.lim=10;document.querySelectorAll('[data-b]').forEach(x=>x.classList.toggle('on',x===b));BR()});
document.querySelectorAll('th[data-bs]').forEach(h=>h.onclick=()=>{const k=h.dataset.bs;BSM.asc=BSM.s===k?!BSM.asc:k==='ea';BSM.s=k;bd()});
$('#bq').oninput=e=>{BSM.q=e.target.value;BSM.lim=10;bd()};$('#bmore').onclick=()=>{BSM.lim+=10;bd()};$('#bl').onchange=e=>{BSM.min=+e.target.value;BR()};
$('#btb').onclick=e=>{const tr=e.target.closest('tr');if(!tr)return;const c=tr.dataset.c;if(S.R.find(x=>x.c===c))detail(c);else{if(!DS||!DS.R.find(x=>x.c===c)){const m=DT.min;DT.min=0;DS=DA();DT.min=m}if(DS.R.find(x=>x.c===c))dtl(c)}};
AC($('#bq'),()=>BL.map(x=>[x.c,x.nm||'']));

/* ===== Chart harga ICT: candle, volume, FVG, OTE, STDV, divergence RSI, trend, fase ===== */
const PCC={ph:{A:['Accumulation','#7d8894'],M:['Manipulation','#f5a623'],D:['Distribution','#22c55e'],XC:['X · Continuation','#2dd4bf'],XR:['X · Reversal','#f0544f']}};
function AMDXBars(phase,compact=false){const current=phase&&phase.p?(String(phase.p).startsWith('X')?'X':String(phase.p).charAt(0)):'',steps=[['A','Accumulation'],['M','Manipulation'],['D','Distribution'],['X','Continuation / Reversal']];return '<div class="amdx-bars '+(compact?'compact':'full')+'" title="Fase AMDX saat ini: '+(current||'belum tersedia')+'">'+steps.map(([key,label])=>{const active=current===key,color=key==='X'?(phase&&phase.p==='XR'?PCC.ph.XR[1]:PCC.ph.XC[1]):PCC.ph[key][1];return '<span class="amdx-step '+(active?'active':'')+'" style="--phase-color:'+color+'" title="'+label+'"><i></i><b>'+key+'</b></span>'}).join('')+'</div>'}
function PNM(p,dr){const m=PCC.ph[p];return m?m[0]+(dr>0?' ↗':dr<0?' ↘':''):'—'}
const PCT={fvg:1,ote:1,sd:1,dv:1,ma:1,lv:1,ys:0};let PCX=null; // fase AMDX tidak digambar sebagai overlay chart; indikator 4 bar ada di tabel emiten.
function PCB(c){const B=[];let pc=0;for(const d of Object.keys(D.px).sort()){const a=D.px[d][c],cl=g(a,0);if(!cl)continue;const pv=g(a,1)||pc||cl,op=g(a,7)||pv;B.push({d,o:op,h:Math.max(g(a,8),op,cl),l:Math.min(g(a,9)||1e12,op,cl),c:cl,v:g(a,2)});pc=cl}return B}
function PATR(B){const a=[];let s=0;B.forEach((b,i)=>{const tr=i?Math.max(b.h-b.l,Math.abs(b.h-B[i-1].c),Math.abs(b.l-B[i-1].c)):b.h-b.l;if(i<14){s+=tr;a.push(s/(i+1))}else a.push((a[i-1]*13+tr)/14)});return a}
function PRSI(B){const n=B.length,p=Math.min(14,n-1),r=new Array(n).fill(null);if(n<8)return r;let ag=0,al=0;for(let i=1;i<=p;i++){const d=B[i].c-B[i-1].c;if(d>0)ag+=d;else al-=d}ag/=p;al/=p;r[p]=al?100-100/(1+ag/al):100;for(let i=p+1;i<n;i++){const d=B[i].c-B[i-1].c;ag=(ag*(p-1)+Math.max(d,0))/p;al=(al*(p-1)+Math.max(-d,0))/p;r[i]=al?100-100/(1+ag/al):100}return r}
function PEMA(B,p){if(B.length<p)return null;const k=2/(p+1),e=[];let v=B.slice(0,p).reduce((a,b)=>a+b.c,0)/p;B.forEach((b,i)=>{if(i<p-1)e.push(null);else{if(i>p-1)v=b.c*k+v*(1-k);e.push(v)}});return e}
/* swing (zigzag) berbasis ATR: pivot terakhir = ekstrem yang masih berjalan */
function PZZ(B,atr){const n=B.length,P=[];if(n<3)return P;let dir=0,hP=B[0].h,hI=0,lP=B[0].l,lI=0;
 for(let i=1;i<n;i++){const t=Math.max(1.5*atr[i],.01*B[i].c);
  if(dir===0){if(B[i].h>hP){hP=B[i].h;hI=i}if(B[i].l<lP){lP=B[i].l;lI=i}
   if(hI>lI&&hP-lP>=t){P.push({i:lI,p:lP,t:'L'});dir=1}else if(lI>hI&&hP-lP>=t){P.push({i:hI,p:hP,t:'H'});dir=-1}}
  else if(dir===1){if(B[i].h>=hP){hP=B[i].h;hI=i}else if(hP-B[i].l>=t){P.push({i:hI,p:hP,t:'H'});dir=-1;lP=B[i].l;lI=i}}
  else{if(B[i].l<=lP){lP=B[i].l;lI=i}else if(B[i].h-lP>=t){P.push({i:lI,p:lP,t:'L'});dir=1;hP=B[i].h;hI=i}}}
 if(dir===1)P.push({i:hI,p:hP,t:'H',prov:1});else if(dir===-1)P.push({i:lI,p:lP,t:'L',prov:1});
 const lh={H:null,L:null};P.forEach(x=>{const q=lh[x.t];if(q)x.s=x.t==='H'?(x.p>q.p?'HH':'LH'):(x.p>q.p?'HL':'LL');lh[x.t]=x});return P}
function PTR(B,P,atr){const n=B.length,why=[];let st=0;const H=P.filter(x=>x.t==='H').slice(-2),L=P.filter(x=>x.t==='L').slice(-2);
 if(H.length===2&&L.length===2){const hh=H[1].p>H[0].p,hl=L[1].p>L[0].p;if(hh&&hl){st=1;why.push('struktur HH + HL')}else if(!hh&&!hl){st=-1;why.push('struktur LH + LL')}else why.push('struktur campuran ('+(hh?'HH':'LH')+' + '+(hl?'HL':'LL')+')')}else why.push('swing belum cukup untuk struktur');
 const k=Math.min(n,20),y=B.slice(-k).map(b=>b.c),mx=(k-1)/2,my=y.reduce((a,b)=>a+b,0)/k;let nu=0,de=0;y.forEach((v,j)=>{nu+=(j-mx)*(v-my);de+=(j-mx)**2});
 const mv=de?nu/de*(k-1)/(atr[n-1]||1):0,rg=mv>1.5?1:mv<-1.5?-1:0;why.push('regresi '+k+' hari '+(mv>=0?'+':'')+mv.toFixed(1)+' ATR');
 return{s:st&&(rg===st||!rg)?st:!st?rg:Math.abs(mv)>=3?rg:0,st,rg,mv,why}}
/* AMDX Quarterly Theory (siklus mingguan, data harian): Sen=A Accumulation, Sel=M Manipulation, Rab=D Distribution, Kam-Jum=X (Continuation/Reversal). Panah = arah. Fase juga jadi komponen skor keputusan lewat AMX() di bawah. */
function PPH(B,atr){const n=B.length;if(n<5)return null;const sgn=(v,t)=>v>t?1:v<-t?-1:0,wk=d=>{const t=new Date(d+'T00:00:00Z'),w=t.getUTCDay()||7;return Math.floor(t.getTime()/864e5)-(w-1)},ph=new Array(n).fill(null),dra=new Array(n).fill(0),inf=[];let ws=0,wd=0;
 for(let i=0;i<n;i++){const t=new Date(B[i].d+'T00:00:00Z'),w=t.getUTCDay()||7;if(i===0||wk(B[i].d)!==wk(B[i-1].d)){ws=i;wd=0}
  const a=atr[i]||1,o0=B[ws].o,net=(B[i].c-o0)/a,mv=i?(B[i].c-B[i-1].c)/a:0;let p,dr;
  if(w===1){p='A';dr=sgn(B[i].c-B[i].o,0)}
  else if(w===2){p='M';const pv=i>ws?B[i-1]:B[i],up=B[i].h>pv.h,dn=B[i].l<pv.l;dr=up&&!dn?-1:dn&&!up?1:-sgn(B[i].c-B[i].o,0)}
  else if(w===3){p='D';dr=sgn(net,.15)||sgn(mv,0);wd=dr}
  else{if(!wd)for(let j=i-1;j>=ws;j--){const nj=(B[j].c-o0)/(atr[j]||1);if(Math.abs(nj)>.15){wd=sgn(nj,0);break}}
   const m=sgn(mv,0);if(wd&&m&&m!==wd){p='XR';dr=m}else{p='XC';dr=wd||m}}
  ph[i]=p;dra[i]=dr;inf[i]={w,net,mv,dr,wd}}
 const sg=[];ph.forEach((p,i)=>{const L=sg.at(-1);if(L&&L.p===p&&wk(B[i].d)===wk(B[L.s].d))L.e=i,L.dr=dra[i];else sg.push({p,s:i,e:i,dr:dra[i]})});
 return{ph,segs:sg,w:5,I:inf[n-1]}}
/* Skor AMDX untuk keputusan beli (-100..+100), checklist 3 kondisi: (1) sudah masuk Q3 (fase D/X), (2) Selasa menyapu low Senin lalu close kembali di atasnya, (3) harga di bawah True Open (open Selasa = awal Q2). Fase A/M belum terbentuk -> null (komponen dikeluarkan). */
function AMX(B,ph){
 if(!B||B.length<5||!ph||!ph.p)return false;
 const n=B.length,weekday=d=>new Date(d+'T00:00:00Z').getUTCDay()||7,
 wk=d=>{const t=new Date(d+'T00:00:00Z');return Math.floor(t.getTime()/864e5)-(weekday(d)-1)};
 const last=B[n-1],w=weekday(last.d);if(w<3)return false;
 let mo=null,tu=null;for(let i=n-1;i>=0&&wk(B[i].d)===wk(last.d);i--){const wd=weekday(B[i].d);if(wd===1)mo=B[i];else if(wd===2)tu=B[i]}
 if(!mo||!tu)return false;
 const sweep=tu.l<mo.l&&tu.c>mo.l;
 const reclaim=last.c>tu.h&&last.c>tu.c&&last.c>=mo.l&&last.c<=mo.h;
 const bullishPhase=(ph.dr>0)&&(['D','XC','XR'].includes(ph.p));
 return !!(sweep&&reclaim&&bullishPhase);
}

/* Fair Value Gap (ICT): gap antara high candle-1 dan low candle-3 (bullish) / sebaliknya (bearish) */
function PFV(B,atr){const F=[],n=B.length;
 for(let i=2;i<n;i++){const a=B[i-2],b=B[i],sz=Math.max(.25*atr[i-1],1);let f=null;
  if(a.h<b.l&&b.l-a.h>=sz)f={up:1,lo:a.h,hi:b.l};else if(a.l>b.h&&a.l-b.h>=sz)f={up:0,lo:b.h,hi:a.l};
  if(!f)continue;f.i=i-1;f.end=null;f.st='open';let lo=f.lo,hi=f.hi;
  for(let j=i+1;j<n;j++){const x=B[j];
   if(f.up){if(x.l<=f.lo){f.st='fill';f.end=j;break}if(x.l<hi){hi=x.l;f.st='part'}}
   else{if(x.h>=f.hi){f.st='fill';f.end=j;break}if(x.h>lo){lo=x.h;f.st='part'}}}
  f.rl=lo;f.rh=hi;F.push(f)}
 return F}
/* Divergence harga vs RSI(14) pada pivot swing: reguler & hidden, garis tidak boleh terpotong */
function PLV(B,atr,P){const swings=P||PZZ(B,atr),confirmed=swings.filter(p=>!p.prov),highs=confirmed.filter(p=>p.t==='H'),lows=confirmed.filter(p=>p.t==='L'),hi=highs.at(-1)||null,lo=lows.at(-1)||null,trend=PTR(B,swings,atr).s,all=PFV(B,atr).filter(f=>f.st!=='fill'),irls=hi&&lo&&hi.p>lo.p?all.filter(f=>f.rl>=lo.p&&f.rh<=hi.p):[];return{hi,lo,trend,irls}}
function PDV(B,P,atr,rsi,tr){const out=[],n=B.length;if(!rsi.some(x=>x!=null))return out;
 const rv=(i,t)=>{let v=null;for(let j=Math.max(0,i-1);j<=Math.min(n-1,i+1);j++){const x=rsi[j];if(x==null)continue;v=v==null?x:t==='H'?Math.max(v,x):Math.min(v,x)}return v};
 for(const t of['H','L']){const Q=P.filter(p=>p.t===t&&rv(p.i,t)!=null);
  for(let m=1;m<Q.length;m++){const p1=Q[m-1],p2=Q[m],gp=p2.i-p1.i;if(gp<3||gp>45)continue;
   const r1=rv(p1.i,t),r2=rv(p2.i,t),a=atr[p2.i]||1,dp=p2.p-p1.p;let k=null;
   if(t==='H'){if(dp>.2*a&&r2<r1-3&&r1>=50)k='bear';else if(dp<-.2*a&&r2>r1+3&&tr.s<=0)k='hbear'}
   else{if(dp<-.2*a&&r2>r1+3&&r1<=50)k='bull';else if(dp>.2*a&&r2<r1-3&&tr.s>=0)k='hbull'}
   if(!k)continue;let ok=true;
   for(let j=p1.i+1;j<p2.i;j++){const f=(j-p1.i)/gp,lp=p1.p+(p2.p-p1.p)*f,lr=r1+(r2-r1)*f;
    if(t==='H'){if(B[j].c>lp+.1*a||(rsi[j]!=null&&rsi[j]>lr+1.5))ok=false}else{if(B[j].c<lp-.1*a||(rsi[j]!=null&&rsi[j]<lr-1.5))ok=false}}
   if(ok)out.push({k,t,p1,p2,r1,r2,conf:!p2.prov})}}
 return out.sort((x,y)=>x.p2.i-y.p2.i).slice(-4)}
let PTF='D';
function PAG(B){if(PTF==='D')return B;const O=[];let k0=null,g=null;
 for(const b of B){let k;const m=+b.d.slice(5,7);
  if(PTF==='W'){const t=new Date(b.d+'T00:00:00Z');t.setUTCDate(t.getUTCDate()-(t.getUTCDay()+6)%7);k=t.toISOString().slice(0,10)}
  else if(PTF==='M')k=b.d.slice(0,7);else k=b.d.slice(0,4)+(m<=6?'H1':'H2');
  if(k!==k0){g={d:b.d,o:b.o,h:b.h,l:b.l,c:b.c,v:b.v};O.push(g);k0=k}
  else{g.h=Math.max(g.h,b.h);g.l=Math.min(g.l,b.l);g.c=b.c;g.v+=b.v}}
 return O}
function PCA(c){const B=PAG(PCB(c)),n=B.length,o={B,n};if(n<3)return o;
 const atr=PATR(B),rsi=PRSI(B),P=PZZ(B,atr);Object.assign(o,{atr,rsi,P});
 o.e1=n>=20?[20,PEMA(B,20)]:n>=10?[10,PEMA(B,10)]:null;o.e2=n>=50?PEMA(B,50):null;
 o.tr=PTR(B,P,atr);o.ew=PEW(P);o.ph=PPH(B,atr);o.fvg=PFV(B,atr);o.dv=PDV(B,P,atr,rsi,o.tr);
 if(P.length>=2){const a=P.at(-2),b=P.at(-1),up=b.t==='H',R=Math.abs(b.p-a.p),cp=B[n-1].c,z=r=>up?b.p-r*R:b.p+r*R;
  o.ote={a,b,up,R,z1:z(.62),z2:z(.79),mid:z(.705),ret:(up?b.p-cp:cp-b.p)/R};o.sd=[1,2,2.5,4].map(k=>({k,p:Math.round(b.p+(up?1:-1)*k*R)})).filter(s=>s.p>0)}
 o.lv=PLV(B,atr,P);
 const L=P.filter(q=>q.t===(o.tr.s>0?'L':'H')).slice(-2);if(o.tr.s&&L.length===2&&(o.tr.s>0?L[1].p>L[0].p:L[1].p<L[0].p))o.tl=L;
 return o}
function PCH(){const b=(k,t)=>`<button class="btn${PCT[k]?' on':''}" data-pt="${k}" style="font-size:9px;padding:4px 7px">${t}</button>`;
 return`<h3 style="margin-top:12px">Chart harga · ICT</h3><div class="bar" style="gap:4px">${b('fvg','FVG')}${b('ote','OTE')}${b('sd','STDV')}${b('dv','Divergence')}${b('ma','EMA')}${b('lv','ERL/IRL')}${b('ys','Skala +STDV')}${['D','W','M','6M'].map(t=>`<button class="btn${PTF===(t==='6M'?'6M':t)?' on':''}" data-ptf="${t}" style="font-size:9px;padding:4px 7px">${t}</button>`).join('')}<span style="flex:1"></span><button class="btn" data-pz="out" style="font-size:9px;padding:4px 9px">−</button><button class="btn" data-pz="in" style="font-size:9px;padding:4px 9px">＋</button><button class="btn" data-pz="yout" style="font-size:9px;padding:4px 7px">↕−</button><button class="btn" data-pz="yin" style="font-size:9px;padding:4px 7px">↕＋</button><button class="btn" data-pz="fit" style="font-size:9px;padding:4px 7px">Fit</button></div><div class="pcw"><canvas id="pcv"></canvas></div><div class="rb" id="pcs"></div>`}
function PCS(A){const n=A.n;if(n<3)return'<small class="mu">Butuh minimal 3 hari data harga untuk chart. Unggah file Ringkasan Saham IDX.</small>';
 const B=A.B,c1=B[n-1].c,fp=v=>Math.round(v).toLocaleString('id-ID'),pc=v=>((v/c1-1)*100>=0?'+':'')+((v/c1-1)*100).toFixed(1)+'%',R=[],T=A.tr;
 R.push(`<b>Trend:</b> <span class="${T.s>0?'up':T.s<0?'dn':''}">${T.s>0?'Uptrend':T.s<0?'Downtrend':'Sideways / transisi'}</span> · ${T.why.join('; ')}.`);
 R.push('<b>Elliott:</b> '+(A.ew?A.ew.t+' (aturan lolos: W2 tidak melewati awal W1, W3 bukan terpendek, W4 tidak overlap W1)':'tidak ada pola impulse 5 gelombang yang lolos aturan. Indikatif saja, karena penghitungan gelombang bersifat subjektif.'));
 if(A.ph){const sg=A.ph.segs.at(-1),nm=PCC.ph[sg.p],I=A.ph.I,DN=['','Senin','Selasa','Rabu','Kamis','Jumat'][I.w]||'';R.push(`<b>Fase (AMDX mingguan):</b> <span style="color:${nm[1]}">${PNM(sg.p,sg.dr)}</span> · ${DN} · ${I.net>=0?'+':''}${I.net.toFixed(1)} ATR dari open minggu ini.`)}else R.push('<b>Fase:</b> butuh minimal 5 hari data harga.');
 const O=A.ote;if(O){const st=O.ret<0?'harga melampaui ujung leg':O.ret<.62?'belum retrace ke OTE':O.ret<=.79?'<b>DI DALAM zona OTE</b>':O.ret<=1?'sudah melewati OTE':'leg gagal (menembus awal leg)';
  R.push(`<b>OTE:</b> leg ${O.up?'naik':'turun'} ${fp(O.a.p)} → ${fp(O.b.p)} (${dl(B[O.a.i].d)}–${dl(B[O.b.i].d)}${O.b.prov?', ujung masih berjalan':''}). Zona 62–79%: ${fp(Math.min(O.z1,O.z2))}–${fp(Math.max(O.z1,O.z2))}, sweet spot 70.5% ${fp(O.mid)}. Retrace kini ${(O.ret*100).toFixed(0)}% → ${st}. Bias: ${O.up?'beli di area discount':'jual di area premium'}.`);
  R.push(`<b>STDV:</b> ${A.sd.map(s=>`−${s.k} SD ${fp(s.p)} (${pc(s.p)})`).join(' · ')} <small class="mu">(range leg × k dari ujung leg)</small>`)}else R.push('<b>OTE / STDV:</b> belum ada leg swing yang valid (butuh pergerakan ≥ 1,5 ATR).');
 const op=A.fvg.filter(f=>f.st!=='fill'),lw=op.filter(f=>f.rh<=c1).sort((a,b)=>b.rh-a.rh)[0],hg=op.filter(f=>f.rl>c1).sort((a,b)=>a.rl-b.rl)[0],ff=f=>`${f.up?'bullish':'bearish'} ${fp(f.rl)}–${fp(f.rh)} (${dl(B[f.i].d)}${f.st==='part'?', sebagian terisi':''})`;
 R.push(`<b>FVG:</b> ${op.length} belum terisi penuh, ${A.fvg.length-op.length} sudah terisi.${lw?' Terdekat di bawah: '+ff(lw)+'.':''}${hg?' Terdekat di atas: '+ff(hg)+'.':''}`);
 if(n<8)R.push('<b>Divergence:</b> butuh minimal 8 hari data harga (RSI).');
 else if(!A.dv.length)R.push('<b>Divergence:</b> tidak ada divergence valid (RSI 14 vs pivot swing) pada data saat ini.');
 else A.dv.slice().reverse().forEach(d=>{const nm={bear:'Bearish (reguler)',bull:'Bullish (reguler)',hbear:'Hidden bearish',hbull:'Hidden bullish'}[d.k];R.push(`<b>Divergence:</b> <span class="${d.k.endsWith('bull')?'up':'dn'}">${nm}</span> · harga ${fp(d.p1.p)} → ${fp(d.p2.p)}, RSI ${d.r1.toFixed(0)} → ${d.r2.toFixed(0)} (${dl(B[d.p1.i].d)}–${dl(B[d.p2.i].d)}) · ${d.conf?'pivot terkonfirmasi':'pivot terakhir belum terkonfirmasi'}.`)});
 if(n<30)R.push(`<small class="mu">Baru ${n} hari data harga: trend, fase, dan divergence makin akurat dengan data lebih panjang (disarankan ≥ 30 hari). Unggah lebih banyak file Ringkasan Saham.</small>`);
 return'<ul style="margin:0;padding-left:12px;font-size:8px;color:var(--mu)">'+R.map(x=>'<li>'+x+'</li>').join('')+'</ul><details style="margin-top:6px"><summary style="font-size:8px">Aturan perhitungan</summary><ul style="font-size:8px"><li><b>Swing</b>: zigzag dengan ambang 1,5 × ATR(14); pivot terakhir adalah ekstrem yang masih berjalan.</li><li><b>FVG</b>: 3 candle, gap antara high candle-1 dan low candle-3 (bullish) atau low candle-1 dan high candle-3 (bearish), minimal 0,25 ATR. Terisi sebagian bila harga masuk, selesai bila menembus sisi jauh gap. Garis putus-putus = CE (50%).</li><li><b>OTE</b>: retracement 62%–79% (sweet spot 70,5%) dari leg swing terakhir.</li><li><b>STDV</b>: proyeksi 1, 2, 2,5, dan 4 × range leg dari ujung leg, searah leg.</li><li><b>Divergence</b>: pivot swing berurutan sejenis vs RSI(14); harga HH/LL dengan RSI berlawanan ≥ 3 poin; hidden hanya bila searah trend; garis tidak boleh terpotong oleh harga/RSI di antara dua pivot.</li><li><b>Trend</b>: struktur HH/HL atau LH/LL dikonfirmasi regresi 20 hari. <b>Fase</b>: AMDX Quarterly Theory siklus mingguan (data harian): Senin = Accumulation, Selasa = Manipulation (arah panah = arah sebenarnya yang diharapkan, berlawanan dengan sapuan high/low), Rabu = Distribution (ekspansi searah open minggu), Kamis–Jumat = X: Continuation bila searah Rabu, Reversal bila berbalik.</li><li>Bukan rekomendasi investasi.</li></ul></details>'}
function PCI(c){clearTimeout(window.PCAN);let cv=$('#pcv');if(!cv)return;{const k=cv.cloneNode(false);cv.replaceWith(k);cv=k}const A=PCA(c),n=A.n,wrap=cv.parentElement,ctx=cv.getContext('2d');PCX=A;wrap.style.display='';$('#pcs').innerHTML=PCS(A);
 if(n<3){wrap.style.display='none';return}
 const L=2,RW=46,T=12,BM2=14,G=4,sr=n>=8,UP='#2dd4bf',DN='#f0544f',MONO="'JetBrains Mono',monospace",V={x0:0,x1:1,h:-1,yz:1,yo:0,rv:null};
 const fit=()=>{V.yz=1;V.yo=0;const lo=Math.max(0,n-180);V.x0=lo-.5;V.x1=n-.5+Math.max(2,(n-lo)*.07)};fit();
 const fp=v=>Math.round(v).toLocaleString('id-ID'),fv=v=>v>=1e9?(v/1e9).toFixed(1)+'M':v>=1e6?(v/1e6).toFixed(1)+'Jt':v>=1e3?(v/1e3).toFixed(0)+'Rb':''+Math.round(v);
 const tick=(lo,hi,k)=>{const r=(hi-lo)/k||1,m=10**Math.floor(Math.log10(r)),q=r/m,s=(q<1.5?1:q<3?2:q<7?5:10)*m,o=[];for(let v=Math.ceil(lo/s)*s;v<=hi;v+=s)o.push(v);return o};
 const draw=()=>{const dpr=window.devicePixelRatio||1,W=wrap.clientWidth,H=wrap.clientHeight;if(!W||!H)return;
  if(cv.width!==Math.round(W*dpr)||cv.height!==Math.round(H*dpr)){cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr)}
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);
  const inner=H-T-BM2-G*(sr?2:1),hp=inner*(sr?.58:.78),hr=sr?inner*.25:0,hv=inner-hp-hr,pw=W-L-RW,vy=T+hp+G,ry=vy+hv+G,bot=sr?ry+hr:vy+hv,xs=i=>L+(i-V.x0)/(V.x1-V.x0)*pw,step=pw/(V.x1-V.x0),xr=L+pw;
  const i0=Math.max(0,Math.ceil(V.x0)),i1=Math.min(n-1,Math.floor(V.x1));if(i1<i0)return;
  let lo=1e18,hi=-1e18,mv=0;for(let i=i0;i<=i1;i++){const b=A.B[i];lo=Math.min(lo,b.l);hi=Math.max(hi,b.h);mv=Math.max(mv,b.v)}
  const h0=hi,l0=lo,cr=hi-lo||hi*.02,inc=p=>{hi=Math.max(hi,p);lo=Math.min(lo,p)};
  if(PCT.ote&&A.ote){inc(A.ote.z1);inc(A.ote.z2)}
  if(PCT.sd&&A.sd)A.sd.forEach(s=>{const ex=s.p>h0?s.p-h0:l0-s.p;if(ex>0&&(PCT.ys||ex<=.6*cr))inc(s.p)});
  const pad=(hi-lo)*.06||1,ya=hi+pad,yb=lo-pad,ym=(ya+yb)/2+V.yo*(ya-yb),yh=(ya-yb)/2*V.yz,ymax=ym+yh,ymin=ym-yh,ys=p=>T+(1-(p-ymin)/(ymax-ymin))*hp;
  ctx.font='8px '+MONO;ctx.textBaseline='alphabetic';
  ctx.save();if(V.rv!=null){const cx=L+(V.rv+.5-V.x0)/(V.x1-V.x0)*(W-L-RW);ctx.beginPath();ctx.rect(0,0,Math.max(0,cx),H);ctx.rect(W-RW,0,RW,H);ctx.clip()}
  ctx.strokeStyle='rgba(125,136,148,.14)';ctx.lineWidth=1;ctx.fillStyle='#7d8894';ctx.textAlign='left';
  for(const v of tick(ymin,ymax,5)){const y=Math.round(ys(v))+.5;ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(xr,y);ctx.stroke();ctx.fillText(fp(v),xr+3,y+3)}
  ctx.strokeStyle='rgba(125,136,148,.3)';[[T,hp],[vy,hv]].concat(sr?[[ry,hr]]:[]).forEach(([y,h])=>ctx.strokeRect(L+.5,Math.round(y)+.5,pw,Math.round(h)));
  /* volume */
  for(let i=i0;i<=i1;i++){const b=A.B[i],h=mv?b.v/mv*(hv-2):0,bw=Math.max(1,step*.68);ctx.fillStyle=(b.c>=b.o?UP:DN)+'99';ctx.fillRect(xs(i)-bw/2,vy+hv-h,bw,h)}
  ctx.fillStyle='#7d8894';ctx.textAlign='left';ctx.fillText('Vol '+fv(mv),xr+3,vy+9);
  /* RSI */
  const ryv=v=>ry+(1-v/100)*hr;
  if(sr){ctx.strokeStyle='rgba(125,136,148,.3)';ctx.setLineDash([3,3]);[30,50,70].forEach(v=>{ctx.beginPath();ctx.moveTo(L,ryv(v));ctx.lineTo(xr,ryv(v));ctx.stroke()});ctx.setLineDash([]);
   ctx.fillStyle='#7d8894';[30,70].forEach(v=>ctx.fillText(v,xr+3,ryv(v)+3));ctx.fillText('RSI 14',L+3,ry+9);
   ctx.save();ctx.beginPath();ctx.rect(L,ry,pw,hr);ctx.clip();ctx.strokeStyle='#a78bfa';ctx.lineWidth=1.2;ctx.beginPath();let st=false;
   for(let i=Math.max(0,i0-1);i<=Math.min(n-1,i1+1);i++){const r=A.rsi[i];if(r==null)continue;const x=xs(i),y=ryv(r);if(st)ctx.lineTo(x,y);else{ctx.moveTo(x,y);st=true}}ctx.stroke();
   if(PCT.dv)for(const d of A.dv){ctx.strokeStyle=d.k.endsWith('bull')?UP:DN;ctx.lineWidth=1.6;ctx.setLineDash(d.k[0]==='h'?[4,3]:[]);ctx.beginPath();ctx.moveTo(xs(d.p1.i),ryv(d.r1));ctx.lineTo(xs(d.p2.i),ryv(d.r2));ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle=d.k.endsWith('bull')?UP:DN;[[d.p1.i,d.r1],[d.p2.i,d.r2]].forEach(([i,r])=>{ctx.beginPath();ctx.arc(xs(i),ryv(r),2.2,0,7);ctx.fill()})}
   ctx.restore()}
  /* harga (clip) */
  ctx.save();ctx.beginPath();ctx.rect(L,T,pw,hp);ctx.clip();
  if(PCT.fvg){const F=A.fvg.filter(f=>f.st!=='fill').slice(-8).concat(A.fvg.filter(f=>f.st==='fill'&&n-1-f.end<=25).slice(-4));
   for(const f of F){const a=xs(f.i-.4),b=f.st==='fill'?xs(f.end):xr,y1=ys(f.rh),y2=ys(f.rl),col=f.up?UP:DN;if(b<L||a>xr)continue;
    ctx.fillStyle=col+(f.st==='fill'?'0d':'30');ctx.fillRect(a,y1,b-a,Math.max(1,y2-y1));ctx.strokeStyle=col+(f.st==='fill'?'55':'aa');ctx.lineWidth=1;ctx.setLineDash(f.st==='fill'?[2,3]:[]);ctx.strokeRect(a+.5,y1+.5,b-a,Math.max(1,y2-y1));ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(a,(y1+y2)/2);ctx.lineTo(b,(y1+y2)/2);ctx.stroke();ctx.setLineDash([]);
    if(b-a>30&&y2-y1>9){ctx.fillStyle=col;ctx.textAlign='left';ctx.fillText('FVG'+(f.up?'↑':'↓')+(f.st==='part'?'½':f.st==='fill'?' ✓':''),Math.max(a,L)+2,y1+8)}}}
  if(PCT.ote&&A.ote){const O=A.ote,a=xs(O.b.i),y1=ys(Math.max(O.z1,O.z2)),y2=ys(Math.min(O.z1,O.z2));ctx.fillStyle='rgba(168,85,247,.18)';ctx.fillRect(a,y1,xr-a,y2-y1);ctx.strokeStyle='rgba(168,85,247,.8)';ctx.lineWidth=1;ctx.strokeRect(a+.5,y1+.5,xr-a,y2-y1);
   ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(a,ys(O.mid));ctx.lineTo(xr,ys(O.mid));ctx.stroke();ctx.setLineDash([]);ctx.strokeStyle='rgba(168,85,247,.55)';ctx.beginPath();ctx.moveTo(xs(O.a.i),ys(O.a.p));ctx.lineTo(xs(O.b.i),ys(O.b.p));ctx.stroke();
   ctx.fillStyle='#c084fc';ctx.textAlign='right';ctx.fillText('OTE 62–79% · '+fp(Math.min(O.z1,O.z2))+'–'+fp(Math.max(O.z1,O.z2)),xr-3,y1+8)}
  if(PCT.sd&&A.sd&&A.ote){const a=xs(A.ote.b.i),col=A.ote.up?UP:DN;ctx.lineWidth=1;ctx.setLineDash([5,3]);for(const s of A.sd){const y=ys(s.p);if(y<T-2||y>T+hp+2)continue;ctx.strokeStyle=col+'cc';ctx.beginPath();ctx.moveTo(a,y);ctx.lineTo(xr,y);ctx.stroke();ctx.fillStyle=col;ctx.textAlign='right';ctx.fillText('−'+s.k+' SD '+fp(s.p),xr-3,y-2)}ctx.setLineDash([])}
if(PCT.lv&&A.lv){const lv=A.lv,dir=lv.trend||0,draw=function(tag,p,col,focus){if(!(p>0))return;const y=ys(p);if(y<T||y>T+hp)return;ctx.strokeStyle=col;ctx.globalAlpha=focus?.9:.42;ctx.lineWidth=focus?1.5:1;ctx.setLineDash(focus?[4,3]:[1,4]);ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(xr,y);ctx.stroke();ctx.setLineDash([]);ctx.textAlign='right';ctx.globalAlpha=1;ctx.fillStyle=col;ctx.font='700 11px JetBrains Mono,monospace';ctx.fillText(fp(p),xr-4,y-3);ctx.fillStyle=focus?col:'#9aa5b1';ctx.font='8px JetBrains Mono,monospace';ctx.fillText(tag,xr-4,y+8)};draw('ERL ↑ · BSL',lv.hi&&lv.hi.p,dir>0?UP:'#f0544f',dir>0);draw('ERL ↓ · SSL',lv.lo&&lv.lo.p,dir<0?DN:'#2dd4bf',dir<0);(lv.irls||[]).slice(-4).forEach(function(f){const y1=ys(f.rh),y2=ys(f.rl),col=f.up?UP:DN;if(y2<T||y1>T+hp)return;ctx.fillStyle=col+'20';ctx.fillRect(L,y1,xr-L,Math.max(1,y2-y1));ctx.strokeStyle=col+'aa';ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(L,(y1+y2)/2);ctx.lineTo(xr,(y1+y2)/2);ctx.stroke();ctx.setLineDash([]);ctx.textAlign='right';ctx.fillStyle=col;ctx.font='700 10px JetBrains Mono,monospace';ctx.fillText(fp((f.rl+f.rh)/2),xr-4,Math.max(T+10,Math.min(T+hp-3,(y1+y2)/2-2)));ctx.fillStyle=col;ctx.font='8px JetBrains Mono,monospace';ctx.fillText('IRL · FVG',xr-4,Math.max(T+18,Math.min(T+hp+5,(y1+y2)/2+8)))})}
  if(PCT.ma){const ln=(e,col)=>{if(!e)return;ctx.strokeStyle=col;ctx.lineWidth=1.1;ctx.beginPath();let s=false;for(let i=Math.max(0,i0-1);i<=Math.min(n-1,i1+1);i++){if(e[i]==null)continue;const x=xs(i),y=ys(e[i]);if(s)ctx.lineTo(x,y);else{ctx.moveTo(x,y);s=true}}ctx.stroke()};ln(A.e1&&A.e1[1],'#f59e0b');ln(A.e2,'#60a5fa')}
  if(A.tl){const[p,q]=A.tl,m=(q.p-p.p)/(q.i-p.i);ctx.strokeStyle=A.tr.s>0?UP:DN;ctx.lineWidth=1;ctx.setLineDash([6,3]);ctx.beginPath();ctx.moveTo(xs(p.i),ys(p.p));ctx.lineTo(xr,ys(q.p+m*(V.x1-q.i)));ctx.stroke();ctx.setLineDash([])}
  for(let i=i0;i<=i1;i++){const b=A.B[i],x=xs(i),bw=Math.max(1,step*.68),up=b.c>=b.o,col=up?UP:DN;ctx.strokeStyle=col;ctx.fillStyle=col;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(Math.round(x)+.5,ys(b.h));ctx.lineTo(Math.round(x)+.5,ys(b.l));ctx.stroke();const y1=ys(Math.max(b.o,b.c)),y2=ys(Math.min(b.o,b.c));ctx.fillRect(x-bw/2,y1,bw,Math.max(1,y2-y1))}
  if(PCT.dv)for(const d of A.dv){const col=d.k.endsWith('bull')?UP:DN;ctx.strokeStyle=col;ctx.fillStyle=col;ctx.lineWidth=1.6;ctx.setLineDash(d.k[0]==='h'?[4,3]:[]);ctx.beginPath();ctx.moveTo(xs(d.p1.i),ys(d.p1.p));ctx.lineTo(xs(d.p2.i),ys(d.p2.p));ctx.stroke();ctx.setLineDash([]);
   [d.p1,d.p2].forEach(p=>{ctx.beginPath();ctx.arc(xs(p.i),ys(p.p),2.4,0,7);ctx.fill()});ctx.textAlign='left';ctx.fillText({bear:'Bear Div',bull:'Bull Div',hbear:'H-Bear Div',hbull:'H-Bull Div'}[d.k],xs(d.p2.i)+4,ys(d.p2.p)+(d.t==='H'?-5:11))}
  if(step>7)for(const p of A.P){if(!p.s||p.i<i0||p.i>i1)continue;ctx.fillStyle='#9aa5b1';ctx.textAlign='center';ctx.fillText(p.s,xs(p.i),p.t==='H'?ys(p.p)-5:ys(p.p)+11)}
  ctx.restore();
  /* label harga terakhir */
  const lc=A.B[V.rv==null?n-1:Math.min(n-1,Math.max(0,V.rv))],ly=Math.max(T+4,Math.min(T+hp-4,ys(lc.c)));ctx.fillStyle=lc.c>=lc.o?UP:DN;ctx.fillRect(xr,ly-6,RW,12);ctx.fillStyle='#04110f';ctx.textAlign='left';ctx.fillText(fp(lc.c),xr+3,ly+3);
  /* sumbu tanggal */
  ctx.fillStyle='#7d8894';ctx.textAlign='center';ctx.font='6px '+MONO;const k=Math.max(1,Math.ceil(40/step));for(let i=i0;i<=i1;i++)if((i1-i)%k===0)ctx.fillText(dl(A.B[i].d),xs(i),H-3);ctx.font='8px '+MONO;
  ctx.restore();/* crosshair */
  if(V.h>=i0&&V.h<=i1&&(V.rv==null||V.h<=V.rv)){const b=A.B[V.h],x=xs(V.h);ctx.strokeStyle='rgba(230,235,240,.35)';ctx.lineWidth=1;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(Math.round(x)+.5,T);ctx.lineTo(Math.round(x)+.5,bot);ctx.stroke();ctx.setLineDash([]);
   const r=A.rsi[V.h],t=`${dl(b.d)}  O ${fp(b.o)}  H ${fp(b.h)}  L ${fp(b.l)}  C ${fp(b.c)}  Vol ${fv(b.v)}${r!=null?'  RSI '+r.toFixed(0):''}`;ctx.font='9px '+MONO;const tw=ctx.measureText(t).width;ctx.fillStyle='rgba(11,15,20,.88)';ctx.fillRect(L+2,T+12,tw+8,13);ctx.fillStyle='#e6ebf0';ctx.textAlign='left';ctx.fillText(t,L+6,T+22);ctx.font='8px '+MONO;
   const ev=EV[V.h];if(ev&&ev.length){const R=ev.slice(0,8).map(([,col,tx])=>{const p=tx.split(' · '),rest=p.slice(1).join(' · '),m=/^(.*?)\s([+\-−]\d.*)$/.exec(rest);return{col,k:p[0],nm:m?m[1]:rest,v:m?m[2]:''}});
   ctx.font='9px '+MONO;const hd=dl(b.d)+' · PERUBAHAN HOLDER';let W2=ctx.measureText(hd).width+16;R.forEach(r=>{W2=Math.max(W2,ctx.measureText(r.k).width+ctx.measureText(r.nm).width+ctx.measureText(r.v).width+56)});W2=Math.min(W2,wrap.clientWidth-L-RW-16);
   const hh=R.length*15+26,x0=Math.max(L+4,Math.min(xr-W2-4,x-W2/2)),targetY=Math.max(T+24,Math.min(bot-hh-4,ys(b.h)-hh-12)),now=performance.now();if(HOVI!==V.h){HOVI=V.h;HOVSTART=now}const p=Math.min(1,(now-HOVSTART)/180),ease=1-Math.pow(1-p,3),y0=targetY+7*(1-ease);ctx.save();ctx.globalAlpha=ease;ctx.fillStyle='rgba(8,11,16,.95)';ctx.fillRect(x0,y0,W2,hh);ctx.strokeStyle='rgba(125,136,148,.4)';ctx.lineWidth=1;ctx.strokeRect(x0+.5,y0+.5,W2,hh);ctx.fillStyle='#7d8894';ctx.textAlign='left';ctx.fillText(hd,x0+8,y0+14);
   R.forEach((r,i)=>{const yy=y0+32+i*15;ctx.fillStyle=r.col;ctx.fillRect(x0+8,yy-8,7,7);ctx.fillText(r.k,x0+20,yy);const kw=ctx.measureText(r.k).width;ctx.fillStyle='#e6ebf0';ctx.fillText(r.nm,x0+28+kw,yy);ctx.fillStyle=r.col;ctx.textAlign='right';ctx.fillText(r.v,x0+W2-8,yy);ctx.textAlign='left'});ctx.restore();if(p<1&&!HOVRAF)HOVRAF=requestAnimationFrame(()=>{HOVRAF=0;draw()});ctx.font='8px '+MONO}else if(HOVI!==-1){HOVI=-1;if(HOVRAF)cancelAnimationFrame(HOVRAF);HOVRAF=0}}};
 const clamp=()=>{const r=V.x1-V.x0;if(V.x0<-r*.3){V.x0=-r*.3;V.x1=V.x0+r}if(V.x1>n+r*.3){V.x1=n+r*.3;V.x0=V.x1-r}};
 const zoomY=k=>{V.yz=Math.max(.15,Math.min(6,V.yz*k));draw()};const HPX=()=>(wrap.clientHeight-T-BM2-G*(sr?2:1))*(sr?.58:.78);
 const zoom=(f,k)=>{const r=V.x1-V.x0,nr=Math.max(Math.min(n+3,6),Math.min(n*1.3+4,r*k)),x=V.x0+f*r;V.x0=x-f*nr;V.x1=V.x0+nr;clamp();draw()};
 const idx=e=>{const x=e.clientX-cv.getBoundingClientRect().left;return Math.max(0,Math.min(n-1,Math.round(V.x0+(x-L)/(wrap.clientWidth-L-RW)*(V.x1-V.x0))))};
 let HOVI=-1,HOVSTART=0,HOVRAF=0;const EV={},addE=(i,col,tx)=>{(EV[i]=EV[i]||[]).push([0,col,tx])},bx={};A.B.forEach((b,i)=>bx[b.d]=i);
 try{for(const d in D.days){const i=bx[d];if(i==null)continue;for(const[nv,st,p,q]of D.days[d][c]||[]){const x=q-p;if(!x)continue;addE(i,x>0?UP:DN,'5% '+(x>0?'Tambah':'Kurang')+' · '+String(nv).slice(0,20)+' '+fm(x))}}
  const sdt=Object.keys(D.sat).sort();sdt.forEach((sd,k)=>{if(!k)return;let j=-1;for(let i=0;i<n;i++){if(A.B[i].d<=sd)j=i;else break}if(j<0)return;const cu=D.sat[sd][c]||[],pr=D.sat[sdt[k-1]][c]||[],t=' ('+dl(sd)+')';
   for(const r of cu){const pv=pr.find(y=>NK(y[0])===NK(r[0])),dp=pv?r[4]-pv[4]:r[4];if(Math.abs(dp)>=.005)addE(j,dp>0?UP:DN,'1% '+(pv?(dp>0?'Tambah':'Kurang'):'Baru')+' · '+String(r[0]).slice(0,20)+' '+(dp>0?'+':'')+dp.toFixed(2)+'pp → '+r[4].toFixed(2)+'%'+t)}
   for(const r of pr)if(!cu.some(y=>NK(y[0])===NK(r[0])))addE(j,DN,'1% Keluar · '+String(r[0]).slice(0,20)+' −'+r[4].toFixed(2)+'pp'+t)})}catch(e){}
 const pt=new Map();let drag=null,pin=null;
 cv.addEventListener('pointerdown',e=>{try{cv.setPointerCapture(e.pointerId)}catch(x){}pt.set(e.pointerId,e);if(pt.size===2){const[a,b]=[...pt.values()];pin={d:Math.abs(a.clientX-b.clientX)||1,x0:V.x0,x1:V.x1,cx:(a.clientX+b.clientX)/2};drag=null}else{drag={x:e.clientX,y:e.clientY,yo:V.yo,x0:V.x0,x1:V.x1};V.h=idx(e);draw()}});
 cv.addEventListener('pointermove',e=>{if(pt.has(e.pointerId))pt.set(e.pointerId,e);const pw=wrap.clientWidth-L-RW;
  if(pin&&pt.size===2){const[a,b]=[...pt.values()],r0=pin.x1-pin.x0,nr=Math.max(Math.min(n+3,6),Math.min(n*1.3+4,r0*pin.d/(Math.abs(a.clientX-b.clientX)||1))),f=(pin.cx-cv.getBoundingClientRect().left-L)/pw,x=pin.x0+f*r0;V.x0=x-f*nr;V.x1=V.x0+nr;clamp()}
  else if(drag&&pt.has(e.pointerId)){const dx=(e.clientX-drag.x)/pw*(drag.x1-drag.x0);V.x0=drag.x0-dx;V.x1=drag.x1-dx;clamp();if(e.pointerType==='mouse')V.yo=drag.yo+(e.clientY-drag.y)/HPX()*V.yz}
  V.h=idx(e);draw()});
 const up=e=>{pt.delete(e.pointerId);if(pt.size<2)pin=null;if(!pt.size)drag=null;if(e.pointerType==='touch'&&!pt.size){V.h=-1;draw()}};
 cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',up);cv.addEventListener('pointerleave',e=>{if(e.pointerType==='mouse'){V.h=-1;draw()}});
 cv.addEventListener('wheel',e=>{e.preventDefault();const r=cv.getBoundingClientRect(),k=e.deltaY>0?1.15:1/1.15;if(e.shiftKey||e.ctrlKey||e.clientX-r.left>wrap.clientWidth-RW)zoomY(k);else zoom((e.clientX-r.left-L)/(wrap.clientWidth-L-RW),k)},{passive:false});
 cv.addEventListener('dblclick',()=>{fit();draw()});
 const pn=$('#pn');pn.querySelectorAll('[data-pt]').forEach(b=>b.onclick=()=>{PCT[b.dataset.pt]=PCT[b.dataset.pt]?0:1;b.classList.toggle('on',!!PCT[b.dataset.pt]);draw()});
 pn.querySelectorAll('[data-pz]').forEach(b=>b.onclick=()=>{const z=b.dataset.pz;if(z==='fit'){fit();draw()}else if(z==='yin')zoomY(1/1.3);else if(z==='yout')zoomY(1.3);else zoom(.5,z==='in'?1/1.4:1.4)});
 pn.querySelectorAll('[data-ptf]').forEach(b=>b.onclick=()=>{PTF=b.dataset.ptf;pn.querySelectorAll('[data-ptf]').forEach(x=>x.classList.toggle('on',x===b));PCI(c)});
 if(window.ResizeObserver)new ResizeObserver(()=>draw()).observe(wrap);else window.addEventListener('resize',draw);
 draw()}

/* ===== Top Gainer / Loser (sidebar) + sinyal struktur: MSS, breakout, breakdown ===== */
const ARA_RULE_EFFECTIVE='2026-09-28';
const araTick=p=>p<200?1:p<500?2:p<2000?5:p<5000?10:25;
const ARAHitToday=c=>{const ds=Object.keys(D.px).sort(),date=ds.at(-1),a=date&&D.px[date]&&D.px[date][c];if(!a||date<ARA_RULE_EFFECTIVE)return null;const prev=Number(a[1]),high=Number(a[8]),bid=Number(a[14]),offer=Number(a[12]);if(!(prev>0&&high>0))return null;const pct=prev<=10?null:prev<=200?.35:prev<=5000?.25:.20,raw=prev<=10?prev+1:prev*(1+pct),tick=araTick(raw),limit=Math.floor(raw/tick+1e-12)*tick,bo=bid>0&&offer>0?bid/offer:null;return high>=limit?{date,high,limit,close:Number(a[0]),rule:ARA_RULE_EFFECTIVE,boardAssumed:true,bid,offer,bidOffer:bo}:null};
const ARAContext=c=>{const ds=Object.keys(D.px).sort(),date=ds.at(-1),a=date&&D.px[date]&&D.px[date][c];if(!a||date<ARA_RULE_EFFECTIVE)return 'batas BEI belum dapat diverifikasi untuk tanggal data';const prev=Number(a[1]),last=Number(a[0]),raw=prev<=10?prev+1:prev*(1+(prev<=200?.35:prev<=5000?.25:.20)),limit=Math.floor(raw/araTick(raw)+1e-12)*araTick(raw),bid=Number(a[14]),offer=Number(a[12]),bo=bid>0&&offer>0?bid/offer:null;return 'Cap teoritis '+Math.round(limit).toLocaleString('id-ID')+', jarak '+(last>0?((limit/last-1)*100).toFixed(1)+'%':'n/a')+' dari close '+Math.round(last).toLocaleString('id-ID')+'. Asumsi papan reguler (metadata papan tidak tersedia). Snapshot '+date+' bid/offer '+(bo==null?'n/a':bid.toLocaleString('id-ID')+'/'+offer.toLocaleString('id-ID')+' ('+bo.toFixed(2)+'x)')+'. Heuristik harian; bukan sinyal antrean 5–15 menit atau jaminan fill. Acuan BEI efektif 28 Sep 2026.'};
function TGX(c){const B=PCB(c),N=B.length,o=[],f=v=>Math.round(v).toLocaleString('id-ID'),ara=ARAHitToday(c);const radar=TG_SCORE_MAP[c];if(radar&&radar.candidate)o.push(['Top Gainer '+Math.round(radar.score)+'/100','#0891b2','Radar Top Gainer rank '+radar.rank+'/'+radar.universe+' pada '+radar.asof+'; ranking relatif, bukan probabilitas. '+(radar.reasons||[]).join(' · ')]);
 // ARA reguler: high harian menyentuh cap dari close sebelumnya dan fraksi harga; papan khusus memakai cap berbeda.
 // OHLC harian hanya membuktikan sentuhan batas teoritis; papan belum tersedia dalam metadata.
 if(ara){const q=ara.bidOffer==null?'bid/offer n/a':'snapshot bid/offer '+ara.bid.toLocaleString('id-ID')+'/'+ara.offer.toLocaleString('id-ID')+' ('+ara.bidOffer.toFixed(2)+'x)';o.push(['Batas ARA tersentuh','#b91c1c','Data harian '+dl(ara.date)+': high '+f(ara.high)+' mencapai batas teoritis '+f(ara.limit)+'. Asumsi papan Utama/Pengembangan/Ekonomi Baru; status papan belum ada di data. BEI efektif 28 Sep 2026. '+q+'. OHLC/snapshot tidak membuktikan harga terkunci, urutan antrean intraday, atau fill.'])}
 if(!ara&&(SIGNAL_TAGS.potensi_ara_early||[]).includes(c)){const z=ARA_SCORE_MAP[c],label=z&&Number.isFinite(+z.score)?'Pre-ARA '+Math.round(+z.score)+'/100':'Pre-ARA',why=z&&Array.isArray(z.reasons)?z.reasons.join(' · '):'';o.push([label,'#a855f7','Skor heuristik, bukan probabilitas. '+why+' '+ARAContext(c)]);}
 if(!ara&&(SIGNAL_TAGS.potensi_ara_momentum||[]).includes(c))o.push(['Potensi ARA','#a855f7','Kandidat momentum/breakout; bukan jaminan ARA. '+ARAContext(c)]);
 if(N<10)return o;
 const atr=PATR(B),P=PZZ(B,atr).filter(p=>!p.prov),cl=B[N-1].c;
 const H=P.filter(p=>p.t==='H'),L=P.filter(p=>p.t==='L');
 const fr=(lv,s,up)=>{for(let j=s+1;j<N;j++)if(up?B[j].c>lv:B[j].c<lv)return j>=N-3;return false};
 if(H.length>1&&L.length>1){const h1=H.at(-1),h0=H.at(-2),l1=L.at(-1),l0=L.at(-2);
  if(h1.p<h0.p&&l1.p<l0.p&&fr(h1.p,h1.i,1))o.push(['MSS ↑','#2dd4bf','MSS bullish: close menembus lower high terakhir '+f(h1.p)+' setelah struktur LH + LL (dalam 3 hari terakhir).']);
  else if(h1.p>h0.p&&l1.p>l0.p&&fr(l1.p,l1.i,0))o.push(['MSS ↓','#f0544f','MSS bearish: close menembus higher low terakhir '+f(l1.p)+' setelah struktur HH + HL (dalam 3 hari terakhir).'])}
 const k=Math.min(20,N-1),Wn=B.slice(N-1-k,N-1),res=Math.max(...Wn.map(b=>b.h)),sup=Math.min(...Wn.map(b=>b.l)),av=Wn.reduce((a,b)=>a+b.v,0)/k,vr=av?B[N-1].v/av:1,tol=Math.max(.015*cl,.5*atr[N-1]),vt=' · vol '+vr.toFixed(1)+'× rata² '+k+' hari';
 if(cl>res)o.push([vr>=1.2?'Breakout':'Breakout lemah','#2dd4bf','Close '+f(cl)+' di atas high '+k+' hari ('+f(res)+')'+vt]);
 else if(cl>=res-tol)o.push(['Pot. breakout','#86e0b0','Close '+f(cl)+' tinggal '+((res/cl-1)*100).toFixed(1)+'% dari high '+k+' hari ('+f(res)+')'+vt]);
 else if(cl<sup)o.push([vr>=1.2?'Breakdown':'Breakdown lemah','#f0544f','Close '+f(cl)+' di bawah low '+k+' hari ('+f(sup)+')'+vt]);
 else if(cl<=sup+tol)o.push(['Pot. breakdown','#f5a623','Close '+f(cl)+' tinggal '+((cl/sup-1)*100).toFixed(1)+'% dari low '+k+' hari ('+f(sup)+')'+vt]);
 return o.slice(0,3)}
const TG_STAR_VALUES=new Map();
function tgStarMarkup(code,rawScore){const score=Math.max(0,Math.min(100,Number(rawScore)||0)),from=TG_STAR_VALUES.get(code)??0;TG_STAR_VALUES.set(code,score);const label=Math.round(score);return`<span class="tg-stars" role="img" aria-label="Skor ${label} dari 100" title="Skor ${label}/100"><span class="tg-stars-empty">★★★</span><span class="tg-stars-fill" style="--star-from:${from}%;--star-to:${score}%">★★★</span></span>`}
function TGL(){const el=$('#tg');if(!el)return;const ds=Object.keys(D.px).sort(),N=ds.length;
 if(N<2){el.innerHTML='<div class="tgh">Top Gainer / Loser</div><small class="mu">Butuh minimal 2 hari data harga. Unggah file Ringkasan Saham IDX.</small>';return}
 const last=ds.at(-1),w=Math.min(5,N),first=ds[N-w],LP=D.px[last],FP=D.px[first],MV=1e9;
 const calc=wk=>{const R=[];for(const c in LP){const a=LP[c],cl=g(a,0);if(!cl||!g(a,2))continue;let base,val;
   if(!wk){base=g(a,1);val=g(a,3)}else{base=g(FP[c],1);let s=0,q=0;for(let i=N-w;i<N;i++){const x=D.px[ds[i]][c];if(g(x,3)>0){s+=g(x,3);q++}}val=q?s/q:0}
   if(!base||val<MV)continue;R.push({c,cl,ch:(cl/base-1)*100})}
  R.sort((a,b)=>b.ch-a.ch);return{G:R.filter(r=>r.ch>0),L:R.filter(r=>r.ch<0).sort((a,b)=>a.ch-b.ch)}};
 const row=r=>{let t=[];try{t=TGX(r.c).filter(x=>!/^Top Gainer\b/i.test(x[0]))}catch(e){}const fresh=TG_FRESH_CODES.has(r.c);return`<div class="tr" data-c="${r.c}" title="${esc(D.nm[r.c]||'')}"><span><b>${r.c}</b> <small class="mu">${counterMarkup(r.cl,'tg-price:'+r.c,0,false,fresh)}</small></span><b class="${r.ch>=0?'up':'dn'}">${counterMarkup(r.ch,'tg-change:'+r.c,1,true,fresh)}%</b>${t.length?'<div class="tgs">'+t.map(x=>`<span class="tc" style="background:${x[1]}" title="${esc(x[2])}">${esc(displayTGTagLabel(x[0]))}</span>`).join('')+'</div>':''}</div>`};
 const blk=(t,cls,L,sub)=>`<div class="tgh ${cls}">${t} <small>${sub}</small></div>`+(L.length?L.map(row).join(''):'<small class="mu">-</small>');
 const D1=calc(0),W1=calc(1),dd=dl(last),wd=dl(first)+'–'+dd;
 const TT=[['▲ Harian','u',D1.G,dd,'Top Gainer · Harian'],['▲ Minggu','u',W1.G,w+' hari, '+wd,'Top Gainer · Mingguan'],['▼ Harian','d',D1.L,dd,'Top Loser · Harian'],['▼ Minggu','d',W1.L,w+' hari, '+wd,'Top Loser · Mingguan']],ti=Math.min(window.__tgt||0,3);
 window.__tgmore=window.__tgmore||[5,5,5,5];TG_ROWS=TT.map(t=>t[2].map(r=>r.c));
 const renderBlock=(item,index)=>{const all=item[2],limit=window.__tgmore[index]||5,shown=all.slice(0,limit),title=item[4]+' · '+counterMarkup(Math.min(limit,all.length),'tg-shown:'+index)+'/'+counterMarkup(all.length,'tg-total:'+index),hasMore=all.length>limit,canReset=limit>5;
  const controls=hasMore||canReset?`<div class="bar tg-more-row" style="margin:6px 0 2px">${hasMore?`<button class="btn" data-tgmore="${index}">Tampilkan lebih banyak (+5)</button>`:''}${canReset?`<button class="btn tg-reset" data-tgreset="${index}" title="Kembali ke 5 saham" aria-label="Kembali ke tampilan minimum">×</button>`:''}${hasMore?`<small class="mu">${counterMarkup(all.length-limit,'tg-remaining:'+index)} emiten lainnya</small>`:''}</div>`:'';
  return blk(title,item[1],shown,item[3])+controls;};
 const renderRadar=()=>{const R=Object.entries(TG_SCORE_MAP).filter(x=>x[1]&&x[1].candidate).sort((a,b)=>a[1].rank-b[1].rank).slice(0,10);const head='<div class="tgh tg-radar-title" style="margin-top:12px">Kandidat Top Gainer <small class="tg-radar-next"><span>Sesi berikutnya</span><span class="tg-radar-date">'+dl(last)+'</span></small></div>';if(!R.length)return head;return head+R.map(([c,z])=>'<div class="tr tg-radar-item" data-c="'+esc(c)+'" title="'+esc((z.reasons||[]).join(' · '))+'"><span class="tg-radar-head"><b>'+esc(c)+'</b><small class="tg-radar-price '+(Number(z.ret_1d_pct)>=0?'up':'dn')+'">'+counterMarkup(Math.round(z.close),'radar-price:'+c)+'</small></span><b class="tg-radar-score">'+tgStarMarkup(c,z.score)+'</b><small class="mu tg-radar-meta">#'+counterMarkup(z.rank,'radar-rank:'+c)+' · 10% teratas</small></div>').join('')};
 el.innerHTML='<div class="tgh">Top Movers</div><div class="tgtabs">'+TT.map((t,i)=>`<button data-tgt="${i}" class="${i===ti?'on ':''}${t[1]}">${t[0]}</button>`).join('')+'</div><div id="tgbody">'+renderBlock(TT[ti],ti)+'</div>'
  +'<details><summary>Keterangan tag</summary><ul><li>Hanya saham dengan value rata² ≥ Rp1 M. Mingguan = close terakhir vs close sebelum '+w+' hari bursa terakhir.</li><li><b>MSS ↑/↓</b>: close menembus swing terakhir yang berlawanan trend (lower high / higher low) dalam 3 hari terakhir.</li><li><b>Breakout/Breakdown</b>: close di atas high / di bawah low 20 hari sebelumnya (lemah = volume &lt; 1,2× rata²). <b>Pot.</b> = dalam ±1,5% (atau 0,5 ATR) dari level itu.</li><li>Klik baris untuk membuka detail saham. Bukan rekomendasi investasi.</li></ul></details>';const radarEl=$('#tgRadar');if(radarEl)radarEl.innerHTML=renderRadar();animateSidebarCounters();TG_FRESH_CODES.clear()}
$('#tg').addEventListener('click',e=>{const reset=e.target.closest('[data-tgreset]');if(reset){const i=+reset.dataset.tgreset;window.__tgmore=window.__tgmore||[5,5,5,5];window.__tgmore[i]=5;TG_FRESH_CODES.clear();TGL();return}const more=e.target.closest('[data-tgmore]');if(more){const i=+more.dataset.tgmore;window.__tgmore=window.__tgmore||[5,5,5,5];const from=window.__tgmore[i]||5;window.__tgmore[i]=from+5;TG_FRESH_CODES=new Set((TG_ROWS[i]||[]).slice(from,from+5));TGL();return}const tb=e.target.closest('[data-tgt]');if(tb){window.__tgt=+tb.dataset.tgt;TG_FRESH_CODES.clear();TGL();const bd=$('#tgbody');if(bd){bd.classList.add('animate-fadeIn');setTimeout(()=>bd.classList.remove('animate-fadeIn'),500)}return}const r=e.target.closest('[data-c]');if(!r)return;const c=r.dataset.c;if(S&&S.R.find(x=>x.c===c))detail(c);else if(DS&&DS.R&&DS.R.find(x=>x.c===c))dtl(c)});

document.querySelectorAll('.sl').forEach(s=>{const inp=s.querySelector('input'),out=s.querySelector('output'),bt=[...s.querySelectorAll('.slb button')],dots=[...s.querySelectorAll('.sld i')],N=bt.length,isW=bt[0].hasAttribute('data-bw'),DW=bt.map(b=>+b.dataset.bw||0);let cur=0,lastW=0,tm=0;
 const dayAt=v=>{if(v<.5)return 0;if(v<=1)return DW[1];const i=Math.min(Math.floor(v),N-2);return Math.round(DW[i]+(DW[i+1]-DW[i])*(v-i))};
 const txt=v=>{const n=Math.round(v);if(Math.abs(v-n)<1e-6)return bt[n].textContent;return isW?(v<.5?bt[0].textContent:dayAt(v)+' hari'):bt[n].textContent};
 const render=v=>{const q='calc(8px + (100% - 16px) * '+(v/(N-1))+')';inp.style.setProperty('--p',q);out.style.left=q;out.textContent=txt(v);dots.forEach((d,i)=>d.style.opacity=Math.abs(v-i)<.35?0:1)};
 const fin=v=>{clearTimeout(tm);if(isW){const d=dayAt(v);if(d!==lastW){lastW=d;BSM.w=d;BSM.lim=10;const h=document.querySelector('th[data-bs="net"]');if(h)h.textContent=d?'Net 5% ('+txt(v)+')':'Net 5% (semua)';BR()}}else{const i=Math.round(v);if(i!==cur){cur=i;bt[i].click()}}};
 const snap=()=>{const from=+inp.value,to=Math.round(from);if(isW||from===to){fin(from);return}const t0=performance.now(),tick=t=>{const k=Math.min(1,(t-t0)/140),v=from+(to-from)*(1-Math.pow(1-k,3));inp.value=v;render(v);if(k<1)requestAnimationFrame(tick);else fin(to)};requestAnimationFrame(tick)};
 inp.addEventListener('input',()=>{let v=+inp.value;const r=Math.round(v);if(Math.abs(v-r)<.07){v=r;inp.value=r}render(v);clearTimeout(tm);tm=setTimeout(()=>fin(v),isW?140:100)});
 inp.addEventListener('change',snap);
 ['pointerdown','focus'].forEach(e=>inp.addEventListener(e,()=>s.classList.add('act')));['pointerup','blur','pointercancel'].forEach(e=>inp.addEventListener(e,()=>s.classList.remove('act')));
 render(0)});
const RADS=C=>{const n=C.length;if(n<3)return'';const W=480,H=360,cx=240,cy=180,R=108,A=i=>-Math.PI/2+2*Math.PI*i/n,pt=(i,v)=>{const r=R*(v+1)/2;return[cx+r*Math.cos(A(i)),cy+r*Math.sin(A(i))]},f=a=>a.map(z=>z.toFixed(1)).join(','),V=C.map(x=>x[3]);
 let s=`<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:640px;display:block;margin:6px auto;font-family:'JetBrains Mono',monospace">`;
 [-1,-.5,0,.5,1].forEach(v=>s+=`<polygon points="${C.map((_,i)=>f(pt(i,v))).join(' ')}" fill="none" style="stroke:${v===0?'var(--mu)':'var(--bd)'}" stroke-width="1" ${v===0?'stroke-dasharray="3 3"':''}/>`);
 C.forEach((_,i)=>{const[x,y]=pt(i,1);s+=`<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" style="stroke:var(--bd)"/>`});
 const m=V.reduce((a,b)=>a+b,0)/n;s+=`<polygon points="${V.map((v,i)=>f(pt(i,v))).join(' ')}" style="fill:${m<0?'var(--dn)':'var(--up)'};fill-opacity:.14;stroke:none"/>`;
 V.forEach((v,i)=>{const j=(i+1)%n,a=pt(i,v),b=pt(j,V[j]);s+=`<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" stroke-width="2" stroke-linecap="round" style="stroke:${(v+V[j])/2<0?'var(--dn)':'var(--up)'}"/>`});
 V.forEach((v,i)=>{const[x,y]=pt(i,v);s+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" style="fill:${v<0?'var(--dn)':'var(--up)'}"/>`});
 C.forEach((x,i)=>{const co=Math.cos(A(i)),si=Math.sin(A(i)),lx=cx+(R+20)*co,ly=cy+(R+20)*si,an=co>.3?'start':co<-.3?'end':'middle',w=[],sp=String(x[1]).split(' ');let cur='';sp.forEach(t=>{if((cur+' '+t).trim().length>14&&cur){w.push(cur);cur=t}else cur=(cur+' '+t).trim()});w.push(cur);
  const L=w.length+1,y0=ly-(si<-.3?(L-1)*13:si>.3?0:(L-1)*6.5)+3;
  s+=`<text text-anchor="${an}" font-size="11" style="fill:var(--tx)">${w.map((t,k)=>`<tspan x="${lx.toFixed(1)}" y="${(y0+k*13).toFixed(1)}">${t}</tspan>`).join('')}<tspan x="${lx.toFixed(1)}" y="${(y0+w.length*13).toFixed(1)}" font-weight="600" style="fill:${V[i]<0?'var(--dn)':'var(--up)'}">${(V[i]*100).toFixed(0)}</tspan></text>`});
 return s+'</svg>'};

const RC=window.React,RD2=window.ReactDOM;let RXC=null,RXR=null,CUR=[],CUP={};
const RAD=C=>{RXC=C;return '<div id="radr" style="min-height:280px"></div>'};
if(RC&&RD2){
 var CU=({to,from,dec,suf})=>{const[v,setV]=RC.useState(from);RC.useEffect(()=>{if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){setV(to);return}let raf,t0;const f=t=>{t0=t0||t;const k=Math.min(1,(t-t0)/750),e=1-Math.pow(1-k,3);setV(from+(to-from)*e);if(k<1)raf=requestAnimationFrame(f)};raf=requestAnimationFrame(f);return()=>cancelAnimationFrame(raf)},[to]);return v.toFixed(dec)+suf};
 var RRAD=({C})=>{const h=RC.createElement,[t,setT]=RC.useState(0);RC.useEffect(()=>{let raf,t0;const f=x=>{t0=t0||x;const k=Math.min(1,(x-t0)/1000);setT(k);if(k<1)raf=requestAnimationFrame(f)};raf=requestAnimationFrame(f);return()=>cancelAnimationFrame(raf)},[]);
  const n=C.length,cx=240,cy=180,R=108,e=1+2.4*Math.pow(t-1,3)+1.4*Math.pow(t-1,2),A=i=>-Math.PI/2+2*Math.PI*i/n,pt=(i,v,k=1)=>{const r=R*(v+1)/2*k;return[cx+r*Math.cos(A(i)),cy+r*Math.sin(A(i))]},V=C.map(x=>x[1]),m=V.reduce((a,b)=>a+b,0)/n,P=a=>a.map(z=>z.toFixed(1)).join(','),el=[];
  [-1,-.5,0,.5,1].forEach(v=>el.push(h('polygon',{key:'g'+v,points:C.map((_,i)=>P(pt(i,v))).join(' '),fill:'none',strokeWidth:1,strokeDasharray:v===0?'3 3':undefined,style:{stroke:v===0?'var(--mu)':'var(--bd)'}})));
  C.forEach((_,i)=>{const[x,y]=pt(i,1);el.push(h('line',{key:'a'+i,x1:cx,y1:cy,x2:x,y2:y,style:{stroke:'var(--bd)'}}))});
  el.push(h('polygon',{key:'f',points:V.map((v,i)=>P(pt(i,v,e))).join(' '),style:{fill:m<0?'var(--dn)':'var(--up)',fillOpacity:.14*Math.min(1,t*2),stroke:'none'}}));
  V.forEach((v,i)=>{const j=(i+1)%n,a=pt(i,v,e),b=pt(j,V[j],e);el.push(h('line',{key:'s'+i,x1:a[0],y1:a[1],x2:b[0],y2:b[1],strokeWidth:2,strokeLinecap:'round',style:{stroke:(v+V[j])/2<0?'var(--dn)':'var(--up)'}}))});
  V.forEach((v,i)=>{const[x,y]=pt(i,v,e);el.push(h('circle',{key:'d'+i,cx:x,cy:y,r:5*Math.min(1,t*3),style:{fill:v<0?'var(--dn)':'var(--up)'}}))});
  C.forEach((x,i)=>{const co=Math.cos(A(i)),si=Math.sin(A(i)),lx=cx+(R+20)*co,ly=cy+(R+20)*si,an=co>.3?'start':co<-.3?'end':'middle',w=[];let cur='';String(x[0]).split(' ').forEach(q=>{if((cur+' '+q).trim().length>14&&cur){w.push(cur);cur=q}else cur=(cur+' '+q).trim()});w.push(cur);
   const L=w.length+1,y0=ly-(si<-.3?(L-1)*13:si>.3?0:(L-1)*6.5)+3,op=Math.max(0,Math.min(1,(t-.35)/.5));
   el.push(h('text',{key:'t'+i,textAnchor:an,fontSize:11,opacity:op,style:{fill:'var(--tx)'}},...w.map((q,k)=>h('tspan',{key:k,x:lx,y:y0+k*13},q)),h('tspan',{key:'v',x:lx,y:y0+w.length*13,fontWeight:600,style:{fill:V[i]<0?'var(--dn)':'var(--up)'}},(V[i]*100*Math.min(1,e)).toFixed(0))))});
  return h('svg',{viewBox:'0 0 480 360',style:{width:'100%',maxWidth:640,display:'block',margin:'6px auto',fontFamily:"'JetBrains Mono',monospace"}},el)};
}
var RRR=null;
function rn(s){s=Math.sin(s*127.1+311.7)*43758.5453;return s-Math.floor(s)}
function RRB(A,B,sd){const dx=B[0]-A[0],dy=B[1]-A[1],L=Math.hypot(dx,dy)||1,nx=-dy/L,ny=dx/L,am=Math.min(12,3+L*.1);let d='M'+A[0].toFixed(1)+' '+A[1].toFixed(1);for(let m=1;m<=6;m++){const t=m/7,o=(rn(sd+m)-.5)*2*am;d+='L'+(A[0]+dx*t+nx*o).toFixed(1)+' '+(A[1]+dy*t+ny*o).toFixed(1)}return d+'L'+B[0].toFixed(1)+' '+B[1].toFixed(1)}
function RRX(el,P){try{RRR&&RRR.unmount()}catch(e){}RRR=null;el.innerHTML='';RRR=RD2.createRoot(el);RRR.render(RC.createElement(RRM,P))}
function RRM({T,ks,rx,ry,N,X,Y}){
 const h=RC.createElement,[hov,setH]=RC.useState(null),el=[],top=[];
 [['Membaik',0,0,'start',8],['Memimpin',320,0,'end',632],['Tertinggal',0,250,'start',8],['Melemah',320,250,'end',632]].forEach(([q,x,y,an,tx])=>el.push(h('rect',{key:'r'+q,x,y,width:320,height:250,fill:QC[q],opacity:.07}),h('text',{key:'q'+q,x:tx,y:y?494:14,textAnchor:an,style:{fill:QC[q],letterSpacing:'.08em'}},q.toUpperCase())));
 el.push(h('path',{key:'ax',d:'M320 0V500M0 250H640',fill:'none',style:{stroke:'var(--bd)'}}));
 ks.forEach(k=>{const p=T[k].p,pt=p.map(q=>[X(q[0]),Y(q[1])]),c=QC[T[k].q],on=hov===k,e=pt.at(-1),d='M'+pt.map(q=>q[0].toFixed(1)+' '+q[1].toFixed(1)).join('L'),dim=hov&&!on;
  el.push(h('g',{key:'g'+k,onMouseEnter:()=>setH(k),onMouseLeave:()=>setH(null),style:{cursor:'pointer'},opacity:dim?.1:1},
   h('path',{d,fill:'none',stroke:'transparent',strokeWidth:14}),
   on?h('path',{key:'gl'+hov,d,pathLength:1,fill:'none',stroke:c,strokeWidth:6,opacity:.28,strokeDasharray:1,className:'animate-draw',style:{filter:'blur(3px)'}}):null,
   h('path',{key:'p'+(on?1:0),d,pathLength:1,fill:'none',stroke:c,strokeWidth:on?2.2:1.2,opacity:on?1:.28,strokeLinejoin:'round',strokeDasharray:on?1:undefined,className:on?'animate-draw':undefined}),
   ...(on?pt.map((q,i)=>h('circle',{key:'c'+i,cx:q[0],cy:q[1],r:i===pt.length-1?4.5:2.2,fill:c,opacity:.9})):[h('circle',{key:'e',cx:e[0],cy:e[1],r:3,fill:c,opacity:.55})]),
   on?h('circle',{key:'ring',cx:e[0],cy:e[1],r:8,fill:'none',stroke:c,className:'animate-ping2',style:{transformBox:'fill-box',transformOrigin:'center'}}):null,
   h('text',{key:'tx',x:e[0]+7,y:e[1]+3,opacity:on?1:.5,style:{fill:on?c:'var(--tx)',fontWeight:on?600:400,fontSize:on?11:8}},SEC[k])))});
 if(hov){const q=T[hov].p.at(-1),e=[X(q[0]),Y(q[1])],tw=220,tx=Math.min(632-tw,Math.max(8,e[0]-tw/2)),ty=e[1]>120?e[1]-54:e[1]+16,c=QC[T[hov].q];
  top.push(h('g',{key:'tt',style:{pointerEvents:'none'},className:'animate-fadeIn'},h('rect',{x:tx,y:ty,width:tw,height:40,fill:'#080b10',stroke:'var(--bd)'}),h('text',{x:tx+8,y:ty+15,style:{fill:'#fff',fontWeight:600}},SEC[hov]+' — '+(q[2]||'')),h('rect',{x:tx+8,y:ty+23,width:7,height:7,fill:c}),h('text',{x:tx+20,y:ty+31,style:{fill:'#e6ebf0'}},'RS-Ratio: '+q[0].toFixed(2)+'  Momentum: '+q[1].toFixed(2))))}
 return h('svg',{viewBox:'0 0 640 500',preserveAspectRatio:'none',style:{width:'100%',height:'100%',font:"10px 'JetBrains Mono',monospace"}},el,top)}
function CUX(){if(!RC||!RD2)return;CUR.forEach(r=>{try{r.unmount()}catch(e){}});CUR=[];document.querySelectorAll('#bc .k b').forEach((b,i)=>{if(b.children.length)return;const m=/^(-?)(\d+(?:\.\d+)?)(\s.*)?$/.exec(b.textContent.trim());if(!m)return;const to=parseFloat(m[1]+m[2]),dec=(m[2].split('.')[1]||'').length,from=CUP[i]??0;CUP[i]=to;if(from===to)return;const r=RD2.createRoot(b);r.render(RC.createElement(CU,{to,from,dec,suf:m[3]||''}));CUR.push(r)})}
function RX(){const el=$('#radr');if(!el||!RXC)return;try{RXR&&RXR.unmount()}catch(e){}RXR=null;if(!RC||!RD2){el.innerHTML=RADS(RXC);return}RXR=RD2.createRoot(el);RXR.render(RC.createElement(RRAD,{C:RXC.map(x=>[x[1],x[3]])}))}
const RVI=c=>{
 const x=BM[c];if(!x||!x.px||!x.sd)return'';
 const N=5,V=2,px=x.px,H0=(()=>{const a=[];for(const d of Object.keys(D.px).sort()){const q=D.px[d][c];if(q&&g(q,0))a.push({d,o:g(q,7)||g(q,0),h:g(q,8)||g(q,0),l:g(q,9)||g(q,0),c:g(q,0)})}let s=0,k=0;a.forEach(b=>{if(b.h>=b.l&&b.l>0&&b.o>0){s+=.5*Math.log(b.h/b.l)**2-.386294*Math.log(b.c/b.o)**2;k++}});const gk=k>=10&&s>0?Math.sqrt(s/k):0,rr=[];for(let i=1;i<a.length;i++)if(a[i-1].c>0&&a[i].c>0)rr.push(Math.log(a[i].c/a[i-1].c));const rm=rr.reduce((p,q)=>p+q,0)/(rr.length||1),cc=rr.length>=20?Math.sqrt(rr.reduce((p,q)=>p+(q-rm)**2,0)/rr.length):0;return{a,sd:gk&&cc?(gk+cc)/2:gk||cc||x.sd}})(),sd=H0.sd,mu=.15*sd*Math.max(-100,Math.min(100,x.sc||0))/100,Z=v=>Math.round(v).toLocaleString('id-ID');
 const SC=[['Target 1',x.t1],['Target 2',x.t2],[x.rec==='SELL'?'Invalidasi':'Stop',x.st]].filter(a=>a[1]);
 const norm=v=>{const t=Math.abs(v)/Math.SQRT2,u=1/(1+.3275911*t),er=1-(((((1.061405429*u-1.453152027)*u)+1.421413741)*u-.284496736)*u+.254829592)*u*Math.exp(-t*t);return v>=0?.5*(1+er):.5*(1-er)};
 const rows=SC.map(([name,T])=>{const r=Math.sign(Math.log(T/px))*Math.min(Math.abs(Math.log(T/px))/N,sd*.5),up=T>px,b=Math.abs(Math.log(T/px)),m=(up?1:-1)*mu,s=sd*Math.sqrt(N),dr=m*N,pm=Math.min(1,Math.max(0,norm((-b+dr)/s)+Math.exp(Math.min(30,2*m*b/(sd*sd)))*norm((-b-dr)/s))),ratio=T/px;let hit=0,total=0;for(let i=0;i+N<H0.a.length;i++){total++;let ok=false;for(let j=i+1;j<=i+N;j++)if(up?H0.a[j].h>=H0.a[i].c*ratio:H0.a[j].l<=H0.a[i].c*ratio){ok=true;break}if(ok)hit++}const probability=Math.min(1,total>=20?.5*pm+.5*hit/total:pm);return{name,T,r,probability,level:[(probability*100).toFixed(0)+'%',probability>=.35?'var(--up)':probability>=.1?'#f59e0b':'var(--dn)',probability>=.35?'wajar':probability>=.1?'lemah':'ekstrem'],fallback:Array.from({length:V},(_,k)=>px*Math.exp(r*(k+1)))}});

 const bars=H0.a,atr=PATR(bars),swings=PZZ(bars,atr),liq=PLV(bars,atr,swings),last=bars.at(-1),top=liq.hi,bottom=liq.lo,hasRange=!!(top&&bottom&&top.p>bottom.p),sweepTop=hasRange&&last.h>top.p&&last.c<top.p,sweepBottom=hasRange&&last.l<bottom.p&&last.c>bottom.p;
 let dir=sweepTop&&!sweepBottom?-1:sweepBottom&&!sweepTop?1:liq.trend;
 if(!dir&&hasRange)dir=Math.abs(top.p-px)<=Math.abs(px-bottom.p)?1:-1;
 const fvgAhead=dir?liq.irls.filter(f=>dir>0?f.rh>=px:f.rl<=px):liq.irls.slice();
 fvgAhead.sort((a,b)=>{const da=dir>0?Math.max(0,a.rl-px):dir<0?Math.max(0,px-a.rh):Math.abs((a.rl+a.rh)/2-px),db=dir>0?Math.max(0,b.rl-px):dir<0?Math.max(0,px-b.rh):Math.abs((b.rl+b.rh)/2-px);return da-db});
 const zone=fvgAhead[0]||null,irlTarget=zone?(dir>0?(px<zone.rl?zone.rl:zone.rh):(px>zone.rh?zone.rh:zone.rl)):null;
 let erlTarget=hasRange&&dir?(dir>0?top.p:bottom.p):null;if(erlTarget&&dir*(erlTarget-px)<=0)erlTarget=null;
 const atrNow=atr.at(-1)||px*sd,maxMove=Math.max(1,atrNow*.85),recent=bars.slice(-7),avg=a=>a.reduce((p,q)=>p+q,0)/(a.length||1),wickUp=Math.min(atrNow*.45,Math.max(atrNow*.05,avg(recent.map(b=>Math.max(0,b.h-Math.max(b.o,b.c)))))),wickDown=Math.min(atrNow*.45,Math.max(atrNow*.05,avg(recent.map(b=>Math.max(0,Math.min(b.o,b.c)-b.l)))));
 const H=bars.slice(-7),P=[];let prev=px,reachedIRL=!zone;
 for(let i=0;i<V;i++){const structuralGoal=hasRange&&dir?(zone&&!reachedIRL?irlTarget:erlTarget):null,goal=structuralGoal==null?(rows[0]?rows[0].fallback[i]:prev):structuralGoal,delta=goal==null?0:goal-prev,step=Math.sign(delta)*Math.min(Math.abs(delta),maxMove),close=Math.max(1,prev+step),o=prev,h=Math.max(o,close)+wickUp,l=Math.max(1,Math.min(o,close)-wickDown);P.push({o,h,l,c:close});if(zone&&dir*(close-irlTarget)>=0)reachedIRL=true;prev=close}
 const modelled=hasRange&&!!dir;
 const erlLevels=modelled&&top&&bottom?[{p:top.p,arrow:'↑',label:'ERL atas',color:dir>0?'var(--up)':'#7d8894'},{p:bottom.p,arrow:'↓',label:'ERL bawah',color:dir<0?'var(--dn)':'#7d8894'}]:[];
 const levelValues=[modelled&&erlTarget?erlTarget:null,zone?zone.rl:null,zone?zone.rh:null,top?top.p:null,bottom?bottom.p:null].filter(v=>Number.isFinite(v)&&v>0);
 const all=[...H.flatMap(k=>[k.h,k.l]),...P.flatMap(k=>[k.h,k.l]),px*(1+sd*Math.sqrt(N)),px*(1-sd*Math.sqrt(N)),...levelValues],mx=Math.max(...all),mn=Math.min(...all),W=480,Hh=180,Y=v=>8+(mx-v)/(mx-mn||1)*(Hh-16),n=H.length+P.length,gap=22,side=(W-(n-1)*gap)/2,sx=i=>side+i*gap,bw=16;
 let sv='<svg viewBox="0 0 '+W+' '+Hh+'" style="width:100%;max-width:100%;display:block;margin:4px auto">';
 const x0=sx(H.length-1),x1=sx(n-1);sv+='<polygon points="'+x0+','+Y(px)+' '+x1+','+Y(px*(1+sd*Math.sqrt(N)))+' '+x1+','+Y(px*(1-sd*Math.sqrt(N)))+'" style="fill:var(--mu);fill-opacity:.08;stroke:none"/>';
 if(erlLevels.length){erlLevels.forEach(({p,arrow,color})=>{const yy=Y(p),xa=Math.min(W-52,x1+12),label=arrow+' '+Z(p);sv+='<line x1="'+x0+'" x2="'+x1+'" y1="'+yy+'" y2="'+yy+'" stroke="'+color+'" stroke-opacity=".5" stroke-dasharray="3 3"/><text x="'+xa+'" y="'+(yy+3)+'" text-anchor="start" font-size="8" font-weight="700" fill="'+color+'">'+label+'</text>'})}
 if(zone){const yy=Y(zone.rh),hh=Math.max(1,Y(zone.rl)-yy),col=zone.up?'var(--up)':'var(--dn)';sv+='<rect x="'+x0+'" y="'+yy+'" width="'+(x1-x0)+'" height="'+hh+'" fill="'+col+'" fill-opacity=".12" stroke="'+col+'" stroke-opacity=".65" stroke-dasharray="2 3"/><text x="'+(x0+3)+'" y="'+Math.max(9,yy-3)+'" font-size="8" fill="'+col+'">IRL · FVG '+Z(zone.rl)+'–'+Z(zone.rh)+'</text>'}
 H.forEach((k,i)=>{const col=k.c>=k.o?'var(--up)':'var(--dn)',X=sx(i),hi=Y(k.h),lo=Y(k.l),rawTop=Y(Math.max(k.o,k.c)),rawBottom=Y(Math.min(k.o,k.c)),bodyH=Math.max(1.5,rawBottom-rawTop),mid=(rawTop+rawBottom)/2,y1=mid-bodyH/2,y2=mid+bodyH/2;if(hi<y1)sv+='<line x1="'+X+'" x2="'+X+'" y1="'+hi+'" y2="'+y1+'" stroke="'+col+'"/>';if(lo>y2)sv+='<line x1="'+X+'" x2="'+X+'" y1="'+y2+'" y2="'+lo+'" stroke="'+col+'"/>';sv+='<rect x="'+(X-bw/2)+'" y="'+y1+'" width="'+bw+'" height="'+bodyH+'" fill="'+col+'"/>'});
 P.forEach((k,i)=>{const col=k.c>=k.o?'var(--up)':'var(--dn)',X=sx(H.length+i),hi=Y(k.h),lo=Y(k.l),rawTop=Y(Math.max(k.o,k.c)),rawBottom=Y(Math.min(k.o,k.c)),bodyH=Math.max(1.5,rawBottom-rawTop),mid=(rawTop+rawBottom)/2,y1=mid-bodyH/2,y2=mid+bodyH/2,delay=.18*i;sv+='<g class="rvc animate-pump" style="animation-delay:'+delay+'s">';if(hi<y1)sv+='<line x1="'+X+'" x2="'+X+'" y1="'+hi+'" y2="'+y1+'" stroke="'+col+'" stroke-dasharray="2 2"/>';if(lo>y2)sv+='<line x1="'+X+'" x2="'+X+'" y1="'+y2+'" y2="'+lo+'" stroke="'+col+'" stroke-dasharray="2 2"/>';sv+='<rect style="fill:'+col+';fill-opacity:.22;stroke:'+col+';stroke-dasharray:2 2" x="'+(X-bw/2)+'" y="'+y1+'" width="'+bw+'" height="'+bodyH+'"/></g>'});
 sv+='</svg>';

 const statRows=rows.slice().sort((a,b)=>a.T-b.T).map(r=>{const erl=erlLevels.find(q=>Math.round(q.p)===Math.round(r.T)),price=Z(r.T)+(erl?' <span style="font-size:7px;color:'+erl.color+'">'+erl.arrow+'</span>':'');return '<tr><td><span class="rvl">'+r.name+'</span> <b class="rvv">'+price+'</b></td><td class="'+(r.r>=0?'up':'dn')+'">'+(r.r>=0?'+':'')+(r.r*100).toFixed(1)+'%</td>'+r.fallback.map(v=>'<td>'+Z(v)+'</td>').join('')+'<td style="color:'+r.level[1]+'">'+r.level[0]+' <small>('+r.level[2]+')</small></td></tr>'}).join('');
 return '<h3 class="rv-title" title="Proyeksi arah memakai swing PZZ dan FVG aktif PFV pada data harian. Sweep hanya indikasi dari OHLC, bukan urutan intraday atau fill.">Siklus ERL / IRL <span class="rvn">SKENARIO STRUKTUR</span></h3>'+sv+'<h3 class="rv-stat-title">Peluang sentuh target sistem</h3><div class="tw"><table class="rvt"><tr><th>Target sistem</th><th>/candle</th>'+Array.from({length:V},(_,k)=>'<th>+'+(k+1)+'</th>').join('')+'<th>Peluang historis/model</th></tr>'+statRows+'</table></div>'
};
const RVF=c=>{
 const x=BM[c]||{},d=x.dy,NM={'Posisi close dalam range':'posisi close dalam range harian','Candle close vs open':'perbandingan harga penutupan dengan pembukaan','Net asing':'','Bid vs offer':'','Lonjakan value':'','Ukuran transaksi':'lot per transaksi dibanding kebiasaan','Momentum multi-hari':''},
  items=d&&Array.isArray(d.C)?d.C.filter(y=>Object.hasOwn(NM,y[0])).map((y,i)=>{const raw=Number(y[2]),v=Number.isFinite(raw)?Math.max(-1,Math.min(1,raw)):0,score=Math.round(v*100),dir=DDIR(v),mark=v>0?'↑':v<0?'↓':'•',value=(score>0?'+':score<0?'−':'')+Math.abs(score);return `<div class="rvr-flow-item"><div class="rvr-flow-head"><b>${esc(y[0])}</b><strong class="rvr-flow-value ${dir}">${mark} ${value}</strong></div><div class="rvr-flow-track" role="meter" aria-label="${esc(y[0])}" aria-valuemin="-100" aria-valuemax="100" aria-valuenow="${score}" aria-valuetext="${esc(y[0])}: skor ${value} dari 100"><i class="rvr-flow-axis" aria-hidden="true"></i><i class="rvr-flow-fill ${dir}" style="--flow-width:${(Math.abs(v)*50).toFixed(1)}%;--flow-delay:${Math.min(i*65,390)}ms" aria-hidden="true"></i></div><small>${NM[y[0]]?esc(NM[y[0]])+(y[3]?' · ':''):''}${y[3]?esc(y[3]):''}</small></div>`}).join(''):'',
  flow=items?`<div class="rvr-flow-list">${items}</div>`:'<p class="mu">Belum ada data komponen aliran harian.</p>';
 return `<div class="rvr-facts-grid"><details class="rvr-fact"><summary class="rvr-fact-title">PEMEGANG &amp; LEVEL</summary>${RB(c)}</details><details class="rvr-fact"><summary class="rvr-fact-title">HARGA &amp; PERIODE</summary>${window.__hd1||''}${DXP(c)}</details><details class="rvr-fact rvr-flow-card"><summary class="rvr-fact-title">ALIRAN HARIAN</summary>${flow}</details></div>${DXH(c)}`
};
document.addEventListener('toggle',e=>{const card=e.target;if(!(card instanceof HTMLDetailsElement)||!card.matches('details.rvr-flow-card')||!card.open)return;card.querySelectorAll('.rvr-flow-fill').forEach(fill=>{fill.classList.remove('rvr-flow-run');void fill.offsetWidth;fill.classList.add('rvr-flow-run')})},true);
const RVW=c=>`<div id="rvs" data-c="${c}">${RVI(c)||'<div class="rv-no-data">Proyeksi reverse candle belum tersedia.</div>'}</div>`;


run();
/* Kirim skor Keputusan (KEP) ke server agar skor sinyal Telegram sama dengan tabel */
async function pushDash(){try{const o={},source=(typeof BL!=='undefined'&&BL.length)?BL:((typeof S!=='undefined'&&S&&S.R)||[]);source.forEach(r=>{const d=KEP(r.c),x=(typeof BM!=='undefined'&&BM)?BM[r.c]:null,ph=x&&x.ph?x.ph.p:null;if(d&&d.K!=null)o[r.c]={K:d.rawK,act:d.act,phase:ph,phase_dir:x&&x.ph?x.ph.dr:null,amdx_buy:!!(x&&x.ax)}});
 if(Object.keys(o).length)await fetch('/api/telegram/dash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows:o})})}catch(e){}}
setTimeout(pushDash,8000);setInterval(pushDash,300000);
