const views=['explorer','analysis','discover','hypotheses'];
const titles={explorer:'Explorer',analysis:'Analysis',discover:'Discover',hypotheses:'Hypotheses'};
const $=s=>document.querySelector(s);
function show(view){views.forEach(v=>document.getElementById(v)?.classList.toggle('active-view',v===view));document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$('#page-title').textContent=titles[view];window.scrollTo({top:0,behavior:'smooth'})}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.view)));
const colors={ndvi:[35,145,78],precip:[55,125,185],temp:[205,115,55],water:[55,145,170],fire:[190,70,45]};
const map=$('#map');
function buildGrid(target,hotspots=false){if(!target)return;target.innerHTML='';const n=target===map?280:96;for(let i=0;i<n;i++){const c=document.createElement('div');c.className='cell';const x=(Math.sin(i*7.31)+1)/2;const y=(Math.sin(i*.73+2)+1)/2;const v=Math.min(1,.15+x*.55+y*.3);const [r,g,b]=colors[$('#variable')?.value||'ndvi'];c.style.background=`rgba(${r},${g},${b},${.18+v*.68})`;if(hotspots&&v>.75)c.classList.add('hot');c.title=`Zona ${i+1} · intensidad ${(v*100).toFixed(0)}%`;c.onclick=()=>selectCell(i,v);target.appendChild(c)}}
function selectCell(i,v){$('#cell-title').textContent=`Zona ${i+1}`;$('#score').textContent=v.toFixed(2)}
buildGrid(map);buildGrid($('#discover-map'));
$('#variable')?.addEventListener('change',e=>{const names={ndvi:'NDVI · intensidad relativa',precip:'Precipitación · anomalía',temp:'Temperatura · anomalía',water:'Agua · disponibilidad',fire:'Fuego · intensidad'};$('#map-title').textContent=names[e.target.value];buildGrid(map)});
$('#hotspots')?.addEventListener('click',e=>{const on=e.currentTarget.classList.toggle('on');e.currentTarget.textContent=on?'Ocultar hotspots':'Mostrar hotspots';buildGrid(map,on)});
$('#lag')?.addEventListener('input',e=>$('#lag-value').textContent=`${e.target.value} meses`);
$('#run-analysis')?.addEventListener('click',e=>{e.currentTarget.textContent='Análisis ejecutado ✓';setTimeout(()=>e.currentTarget.textContent='Ejecutar análisis',1800)});
document.addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(b&&!b.classList.contains('nav'))show(b.dataset.view)});