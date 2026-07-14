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
  details{border:1px solid #1e2a44;border-radius:12px;margin-bottom:10px;background:#0d1424}
  summary{cursor:pointer;padding:14px 16px;font-weight:700;font-size:14px;list-style:none;display:flex;align-items:center;gap:8px}
  summary::-webkit-details-marker{display:none}
  summary:before{content:'▶';font-size:11px;color:#7c3aed;transition:transform .15s}
  details[open] summary:before{transform:rotate(90deg)}
  .guide-body{padding:4px 18px 18px}
  .guide-body ol,.guide-body ul{margin-left:20px;line-height:1.9}
  .guide-body li{font-size:13px;color:#c7cfe2}
  .guide-body b{color:#e6ecf7}
  .guide-body code{background:#1a2236;padding:2px 6px;border-radius:5px;font-size:12px;color:#c4b5fd}
  .guide-body p{font-size:13px;color:#8a98b5;margin:6px 0 10px}
  .tip{background:#1a1030;border-left:3px solid #7c3aed;padding:10px 14px;border-radius:0 8px 8px 0;font-size:12.5px;color:#c4b5fd;margin:10px 0}
</style>
</head>
<body>
<div class="topbar">
  <div><h1>🧭 VitaBot SaaS — Panel Maestro</h1><p>Administra todas las empresas del sistema</p></div>
</div>
<div class="container">
  <div class="stat-row" id="stats"></div>

  <div class="card">
    <h2>📖 Guía paso a paso</h2>
    <p style="font-size:12.5px;color:#8a98b5;margin-bottom:12px">Siempre disponible aquí. Ábrela cuando vayas a dar de alta una empresa nueva.</p>

    <details open>
      <summary>1️⃣ Cómo crear una empresa en este panel</summary>
      <div class="guide-body">
        <ol>
          <li>Completa <b>Nombre</b> y <b>Tipo de negocio</b> en el formulario de abajo.</li>
          <li>Si aún no tienes las credenciales de WhatsApp de Meta, <b>déjalas vacías</b> — puedes crear la empresa igual y completarlas después (botón "Editar" en la tabla).</li>
          <li>Pon el <b>correo de notificaciones</b> del dueño del negocio.</li>
          <li>Clic en <b>Crear empresa</b>. El sistema genera un link único de panel para esa empresa.</li>
          <li>Copia el link (botón "Abrir panel" en la tabla) y compártelo con el dueño del negocio — es su panel privado, solo con ese link entra.</li>
          <li>El dueño (o tú por él) entra a <b>Configuración → Entrenamiento</b> y escribe la información de su negocio (productos/servicios, precios, políticas). El bot la usa de inmediato, sin esperas.</li>
          <li>Antes de conectar el número real de WhatsApp, prueba el bot en <b>Ayuda → Chat de prueba</b> dentro del panel de esa empresa.</li>
          <li>Cuando ya tengas las credenciales de Meta (siguiente sección), complétalas y la empresa queda lista para recibir mensajes reales.</li>
        </ol>
      </div>
    </details>

    <details>
      <summary>2️⃣ Cómo conseguir el número de WhatsApp y las credenciales en Meta</summary>
      <div class="guide-body">
        <p>Esto se hace UNA vez por cada empresa nueva, en la cuenta de Meta de esa empresa (no en la tuya).</p>
        <ol>
          <li>Crea (o usa) una cuenta de <b>Meta Business</b> en <code>business.facebook.com</code>.</li>
          <li>Ve a <code>developers.facebook.com/apps</code> → <b>Crear app</b> → tipo <b>"Otro"</b> → <b>"Empresa"</b> → dale un nombre.</li>
          <li>Dentro de la app, agrega el producto <b>WhatsApp</b> (botón "Configurar" en la tarjeta de WhatsApp).</li>
          <li>En <b>WhatsApp → Configuración de la API</b> verás un número de prueba gratis y un <b>token temporal</b> (dura 24h) — sirve solo para probar rápido.</li>
          <li>Para producción: en <b>Administrador de WhatsApp Business</b> agrega el número real de la empresa (debe ser un número que NO esté ya activo en la app normal de WhatsApp) y verifícalo por SMS o llamada.</li>
          <li><b>Token permanente</b> (para que no se venza cada 24h):
            <ul>
              <li>Ve a <b>Configuración del negocio</b> (<code>business.facebook.com/settings</code>) → <b>Usuarios del sistema</b> → <b>Agregar</b>.</li>
              <li>Asígnale el activo de la app de WhatsApp con rol de administrador.</li>
              <li>Genera un token con los permisos <code>whatsapp_business_messaging</code> y <code>whatsapp_business_management</code>, duración <b>Nunca expira</b>.</li>
            </ul>
          </li>
          <li>Copia el <b>ID del número de teléfono</b> (<code>phone_number_id</code>) desde <b>WhatsApp → Configuración de la API</b>.</li>
          <li>Configura el <b>Webhook</b> (en la misma pantalla, sección Webhooks):
            <ul>
              <li><b>URL de devolución de llamada</b>: <code>https://TU-DOMINIO-DE-RAILWAY/webhook</code></li>
              <li><b>Token de verificación</b>: cualquier palabra secreta que también pongas en <code>WEBHOOK_VERIFY_TOKEN</code> del servidor (o en el campo de la empresa)</li>
              <li>Suscríbete al campo <b>messages</b>.</li>
            </ul>
          </li>
          <li>Pega el <b>phone_number_id</b> y el <b>access_token</b> permanente al crear o editar la empresa en este panel.</li>
        </ol>
        <div class="tip">💡 Todas las empresas comparten la MISMA url de webhook (<code>/webhook</code>) — el sistema identifica sola a cada empresa por su phone_number_id. Solo cambia la URL si cambias de dominio de Railway.</div>
      </div>
    </details>

    <details>
      <summary>3️⃣ Cómo crear plantillas de mensajes aprobadas por Meta</summary>
      <div class="guide-body">
        <p>Las plantillas son obligatorias para escribirle primero a un cliente fuera de la ventana de 24h (recordatorios, postventa, promociones).</p>
        <ol>
          <li>Ve a <code>business.facebook.com</code> → <b>WhatsApp Manager</b> → <b>Plantillas de mensajes</b>.</li>
          <li>Clic en <b>Crear plantilla</b>.</li>
          <li>Elige la <b>categoría</b>: <b>Utilidad</b> (postventa, confirmaciones, recordatorios) o <b>Marketing</b> (promociones).</li>
          <li>Ponle un <b>nombre en minúsculas y sin espacios</b> (ej: <code>recontacto_general</code>, <code>promo_novedades</code>).</li>
          <li>Idioma: <b>Español</b>.</li>
          <li>Escribe el cuerpo del mensaje. Usa <code>{{1}}</code> donde quieras que aparezca el nombre del cliente (se reemplaza automático).</li>
          <li>Envíala a revisión. Meta tarda entre minutos y 24-48h en aprobarla.</li>
          <li>Cuando esté <b>Aprobada</b>, copia el nombre EXACTO de la plantilla y pégalo en el panel de esa empresa, en <b>Configuración → Postventa</b> (para recordatorios) o <b>Campañas</b> (para promociones).</li>
        </ol>
        <div class="tip">💡 Sin plantilla aprobada, los recordatorios/postventa/campañas de WhatsApp SOLO llegan si el cliente escribió en las últimas 24h. Con plantilla, llegan siempre.</div>
      </div>
    </details>
  </div>

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

let _companies=[];
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
      <button class="btn-s" onclick="openEdit(${c.id})">✏️ Editar</button>
      ${c.status!=='active'?`<button class="btn-s" onclick="setStatus(${c.id},'active')">▶️ Activar</button>`:''}
      ${c.status!=='paused'?`<button class="btn-s" onclick="setStatus(${c.id},'paused')">⏸️ Pausar</button>`:''}
    </td>
  </tr>
  <tr id="edit-row-${c.id}" style="display:none"><td colspan="7">
    <div class="row" style="padding:10px 0">
      <div class="field"><label>WhatsApp phone_number_id</label><input id="ed-phone-${c.id}" style="width:190px" value="${c.whatsapp_phone_number_id.startsWith('pendiente-')?'':c.whatsapp_phone_number_id}"></div>
      <div class="field"><label>WhatsApp access_token</label><input id="ed-token-${c.id}" style="width:220px" placeholder="(déjalo vacío para no cambiarlo)"></div>
      <div class="field"><label>Correo de notificaciones</label><input id="ed-email-${c.id}" style="width:190px" value="${c.notification_email}"></div>
      <button class="btn-p" onclick="saveEdit(${c.id})">Guardar</button>
      <button class="btn-s" onclick="openEdit(${c.id})">Cancelar</button>
    </div>
  </td></tr>`;
}
function openEdit(id){
  const row=$('#edit-row-'+id);
  if(row)row.style.display=row.style.display==='none'?'table-row':'none';
}
async function saveEdit(id){
  const body={
    whatsapp_phone_number_id:$('#ed-phone-'+id).value.trim(),
    notification_email:$('#ed-email-'+id).value.trim(),
  };
  const tok=$('#ed-token-'+id).value.trim();
  if(tok)body.whatsapp_access_token=tok;
  try{await api('/api/companies/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    alert('✅ Datos actualizados');loadCompanies();}
  catch(e){alert('Error: '+e.message);}
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
