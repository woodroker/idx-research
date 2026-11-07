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
function parse(a,fn){
 const hi=a.findIndex(r=>r&&(r.includes('Kode Efek')||r.includes('Penutupan')||r.includes('SHARE_CODE')||r.includes('SHARE CODE')||r[2]==='NUMBER_OF_SHARES'));if(hi<0)return null;
 const h=a[hi],o={},nm={};let d;
 if(h.includes('Penutupan')){const m=(fn||'').match(/(\d{4})(\d{2})(\d{2})/);if(m)d=`${m[1]}-${m[2]}-${m[3]}`;else{const t=String(a[hi+1][6]).match(/(\d+) (\w+) (\d+)/);if(!t)return null;d=`${t[3]}-${String(MO[t[2].toUpperCase()]).padStart(2,'0')}-${t[1].padStart(2,'0')}`}
  for(const r of a.slice(hi+1))if(r&&r[1]){o[r[1]]=n(r[12])?[10,4,12,13,14,24,23,5,8,9,15,16,17,18,19,21,25].map(i=>n(r[i])):[n(r[10]),n(r[4])];nm[r[1]]=r[2]}
  return[{k:'px',d,data:o},{k:'nm',d:'-',data:nm}]}
 if(h.includes('Kode Efek')){const m=String(h[14]).match(/(\d+)-(\w+)-(\d+)/);d=`${m[3]}-${String(MO[m[2].toUpperCase()]).padStart(2,'0')}-${m[1].padStart(2,'0')}`;
  const ag={};let cur=null;
  for(const r of a.slice(hi+2)){if(!r||!r[1])continue;const c=r[1];if(r[0]!=null||!cur||cur[0]!==c)cur=[c,r[4]||r[3],r[10]];if(r[2])nm[c]=r[2];
   const k=c+'|'+cur[1],e=ag[k]||(ag[k]=[c,[cur[1],cur[2],0,0]]);e[1][2]+=n(r[11]);e[1][3]+=n(r[14])}
  for(const[c,e]of Object.values(ag))(o[c]=o[c]||[]).push(e);
  return[{k:'days',d,data:o},{k:'nm',d:'-',data:nm}]}
 if(h[2]==='NUMBER_OF_SHARES'){for(const r of a.slice(hi+3))if(r&&r[0]&&r[1]){d=iso(r[0]);o[r[1]]=r.slice(2,40).map(n)}return[{k:'tipe',d,data:o}]}
 if(h.includes('SHARE_CODE')){const ix=(re,ne)=>h.findIndex(x=>re.test(String(x||''))&&!(ne&&ne.test(String(x||'')))),fb=(i,k)=>i<0?k:i,iN=ix(/NATIONALITY/i),iD=ix(/DOMICILE/i),iS=ix(/SCRIPLESS/i),iC=ix(/SCRIP/i,/SCRIPLESS/i),iNm=fb(ix(/INVESTOR.?NAME/i),3),iTy=fb(ix(/INVESTOR.?(TYPE|CLASS)/i),4),iLF=fb(ix(/LOCAL/i),5),iTt=fb(ix(/TOTAL/i),10),iPc=fb(ix(/PERCENT|PCT|%/i),11),PC=v=>typeof v==='number'?v:parseFloat(String(v??'').replace('%','').replace(/\s/g,'').replace(/,(?=\d{1,2}$)/,'.').replace(/,/g,''))||0;for(const r of a.slice(hi+1))if(r&&r[0]&&r[1]){d=iso(r[0]);(o[r[1]]=o[r[1]]||[]).push([r[iNm],r[iTy],(r[iLF]==null?'':String(r[iLF]).trim()),n(r[iTt]),PC(r[iPc]),iN<0?null:r[iN],iD<0?null:r[iD],iS<0?null:n(r[iS]),iC<0?null:n(r[iC])]);nm[r[1]]=r[2]}return[{k:'sat',d,data:o},{k:'nm',d:'-',data:nm}]}
 for(const r of a.slice(hi+1))if(r&&r[0]&&r[1]){d=iso(r[0]);o[r[1]]=r.slice(3,43).map(n);nm[r[1]]=nm[r[1]]||r[2]}
 return[{k:'kl',d,data:o},{k:'klc',d:'-',data:h.slice(3,43).map(String)},{k:'nm',d:'-',data:nm}]}
module.exports={n,iso,parse,SAN:null};
function SAN(o){let mx=0,bd=0;for(const c in o)for(const r of o[c]){if(r[4]>100.01){r[4]=0;bd++}if(r[4]>mx)mx=r[4]}if(!bd&&mx>0&&mx<=1)for(const c in o)for(const r of o[c])r[4]=r[4]*100;return bd}
;module.exports={n,iso,parse,SAN};