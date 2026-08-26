const views=['explorer','analysis','discover','hypotheses'];
const titles={explorer:'Explorer',analysis:'Analysis Lab',discover:'Discover',hypotheses:'Hypotheses'};
const $=s=>document.querySelector(s);
function show(view){views.forEach(v=>document.getElementById(v)?.classList.toggle('active-view',v===view));document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$('#page-title').textContent=titles[view];window.scrollTo({top:0,behavior:'smooth'})}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.view)));
const map=$('#map');
const vals=[];
for(let i=0;i<280;i++){const c=document.createElement('div');c.className='cell';const v=Math.random();vals.push(v);c.style.background=`rgba(${50+v*150},${105+v*130},${85+v*30},${.35+v*.55})`;c.title=`Celda ${i+1}`;c.addEventListener('click',()=>{$('#cell-title').textContent=`Celda ${i+1}`;});map.appendChild(c)}
$('#variable').addEventListener('change',e=>{$('#map-title').textContent=`${e.target.options[e.target.selectedIndex].text} · Alto Xingu`;});
$('#lag').addEventListener('input',e=>$('#lag-value').textContent=`${e.target.value} meses`);
$('#run-analysis').addEventListener('click',e=>{e.currentTarget.textContent='Análisis ejecutado ✓';setTimeout(()=>e.currentTarget.textContent='Ejecutar análisis',1600)});
