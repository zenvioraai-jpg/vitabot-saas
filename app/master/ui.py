"""Panel MAESTRO: SPA simple para listar, crear y administrar todas las empresas
del SaaS. El token se inyecta reemplazando __TOKEN__."""


def render_master_panel(token: str) -> str:
    return _HTML.replace("__TOKEN__", token)


_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VitaBot SaaS — Panel Maestro</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0b1020;color:#e6ecf7;min-height:100vh}
  .topbar{background:linear-gradient(135deg,#7c3aed,#6d28d9);padding:18px 28px;display:flex;justify-content:space-between;align-items:center}
  .topbar h1{font-size:19px;font-weight:800}
  .topbar p{font-size:12px;color:rgba(255,255,255,.85);margin-top:2px}
  .container{max-width:1200px;margin:0 auto;padding:24px}
  .stat-row{display:flex;gap:14px;margin-bottom:22px;flex-wrap:wrap}
  .stat{background:#111a2e;border:1px solid #1e2a44;border-radius:14px;padding:16px 22px;flex:1;min-width:130px}
  .stat b{display:block;font-size:26px;color:#c4b5fd}
  .stat span{font-size:11px;color:#8a98b5;text-transform:uppercase;letter-spacing:.05em}
  .card{background:#111a2e;border:1px solid #1e2a44;border-radius:16px;padding:22px;margin-bottom:20px}
  .card h2{font-size:16px;margin-bottom:14px}
  .row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px}
  .field{display:flex;flex-direction:column;gap:5px}
  .field label{font-size:11px;color:#8a98b5}
  input,select{background:#0d1424;border:1px solid #1e2a44;border-radius:8px;padding:9px 12px;color:#e6ecf7;font-size:13px;outline:none}
  input:focus,select:focus{border-color:#7c3aed}
  button{cursor:pointer;border:none;border-radius:8px;font-weight:600;font-size:13px}
  .btn-p{background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;padding:10px 18px}
  .btn-s{background:transparent;border:1px solid #1e2a44;color:#8a98b5;padding:8px 14px}
  table{width:100%;border-collapse:collapse}
  th{text-align:left;font-size:11px;color:#8a98b5;text-transform:uppercase;padding:8px;border-bottom:1px solid #1e2a44}
  td{padding:10px 8px;font-size:13px;border-bottom:1px solid #1e2a44}
  .badge{padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}
  .badge.active{background:#0e2a1a;color:#4ade80}
  .badge.onboarding{background:#2a230e;color:#fbbf24}
  .badge.paused{background:#2a0e14;color:#f87171}
  .empty{text-align:center;color:#8a98b5;padding:30px}
  a{color:#c4b5fd}
</style>
</head>
<body>
<div class="topbar">
  <div><h1>🧭 VitaBot SaaS — Panel Maestro</h1><p>Administra todas las empresas del sistema</p></div>
</div>
<div class="container">
  <div class="stat-row" id="stats"></div>

  <div class="card">
    <h2>➕ Nueva empresa</h2>
    <div class="row">
      <div class="field"><label>Nombre</label><input id="nc-name" style="width:180px" placeholder="Panadería El Trigal"></div>
      <div class="field"><label>Tipo de negocio</label><select id="nc-type" style="width:200px"></select></div>
      <div class="field"><label>WhatsApp phone_number_id</label><input id="nc-phone" style="width:170px" placeholder="(opcional por ahora)"></div>
      <div class="field"><label>WhatsApp access_token</label><input id="nc-token" style="width:170px" placeholder="(opcional por ahora)"></div>
      <div class="field"><label>Correo de notificaciones</label><input id="nc-email" style="width:190px" placeholder="dueno@empresa.com"></div>
      <button class="btn-p" onclick="createCompany()">Crear empresa</button>
    </div>
    <p style="font-size:11.5px;color:#8a98b5">Si aún no tienes el número de WhatsApp conectado, puedes crearla igual y completar esos datos después — el panel de la empresa ya queda listo para cargar Entrenamiento y probar el bot.</p>
  </div>

  <div class="card">
    <h2>🏢 Empresas registradas</h2>
    <div id="companies"><div class="empty">Cargando…</div></div>
  </div>
</div>

<script>
const TOKEN='__TOKEN__';
const $=s=>document.querySelector(s);

async function api(path,opts){
  const url='/master'+path+(path.includes('?')?'&':'?')+'token='+TOKEN;
  const r=await fetch(url,opts);
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Error');}
  return r.json();
}

async function loadTypes(){
  try{const types=await api('/api/business-types');
    $('#nc-type').innerHTML=types.map(t=>`<option value="${t.key}">${t.label}</option>`).join('');
  }catch(e){}
}

function statusBadge(s){
  const labels={active:'Activa',onboarding:'Onboarding',paused:'Pausada'};
  return `<span class="badge ${s}">${labels[s]||s}</span>`;
}

function fmtDate(iso){return iso?new Date(iso).toLocaleString('es-CO',{dateStyle:'short',timeStyle:'short'}):'—';}

function companyRow(c){
  const panelUrl=location.origin+'/admin/panel?token='+c.admin_token;
  return `<tr>
    <td><b>${c.name}</b><div style="font-size:11px;color:#8a98b5">${c.slug}</div></td>
    <td>${c.business_type}</td>
    <td>${statusBadge(c.status)}</td>
    <td>${c.conversations}</td>
    <td>${c.messages_today}</td>
    <td>${fmtDate(c.last_activity)}</td>
    <td style="white-space:nowrap">
      <a href="${panelUrl}" target="_blank"><button class="btn-s">Abrir panel</button></a>
      ${c.status!=='active'?`<button class="btn-s" onclick="setStatus(${c.id},'active')">▶️ Activar</button>`:''}
      ${c.status!=='paused'?`<button class="btn-s" onclick="setStatus(${c.id},'paused')">⏸️ Pausar</button>`:''}
    </td>
  </tr>`;
}

async function loadCompanies(){
  let cs=[];
  try{cs=await api('/api/companies');}catch(e){$('#companies').innerHTML='<div class="empty">Error cargando empresas</div>';return;}
  const active=cs.filter(c=>c.status==='active').length;
  const totalMsgs=cs.reduce((a,c)=>a+c.messages_today,0);
  $('#stats').innerHTML=`
    <div class="stat"><b>${cs.length}</b><span>Empresas totales</span></div>
    <div class="stat"><b>${active}</b><span>Activas</span></div>
    <div class="stat"><b>${totalMsgs}</b><span>Mensajes hoy (todas)</span></div>`;
  if(!cs.length){$('#companies').innerHTML='<div class="empty">Aún no has creado ninguna empresa.</div>';return;}
  $('#companies').innerHTML=`<table><thead><tr><th>Empresa</th><th>Tipo</th><th>Estado</th><th>Conversaciones</th><th>Msjs hoy</th><th>Última actividad</th><th></th></tr></thead>
    <tbody>${cs.map(companyRow).join('')}</tbody></table>`;
}

async function createCompany(){
  const name=$('#nc-name').value.trim();
  if(!name){alert('Ponle un nombre a la empresa');return;}
  const body={
    name, business_type:$('#nc-type').value,
    whatsapp_phone_number_id:$('#nc-phone').value.trim(),
    whatsapp_access_token:$('#nc-token').value.trim(),
    notification_email:$('#nc-email').value.trim(),
  };
  try{
    const r=await api('/api/companies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    alert('✅ Empresa creada. Panel: '+location.origin+r.panel_url);
    $('#nc-name').value='';$('#nc-phone').value='';$('#nc-token').value='';$('#nc-email').value='';
    loadCompanies();
  }catch(e){alert('Error: '+e.message);}
}

async function setStatus(id,status){
  try{await api('/api/companies/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});loadCompanies();}
  catch(e){alert('Error: '+e.message);}
}

loadTypes();
loadCompanies();
setInterval(loadCompanies,15000);
</script>
</body></html>"""
