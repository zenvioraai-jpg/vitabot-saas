"""Panel MAESTRO: SPA para listar, crear y administrar todas las empresas del
SaaS. Diseño claro (tema azul/blanco). El token se inyecta reemplazando
__TOKEN__."""


def render_master_panel(token: str) -> str:
    return _HTML.replace("__TOKEN__", token)


_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zenviora AI — Chatbot Manager</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f7fb;color:#1e293b;min-height:100vh}
  .app{display:flex;min-height:100vh}

  /* SIDEBAR */
  .sidebar{width:260px;background:linear-gradient(180deg,#1e3a8a,#1e2f6e);color:#fff;display:flex;flex-direction:column;flex-shrink:0;position:sticky;top:0;height:100vh}
  .brand{display:flex;align-items:center;gap:12px;padding:22px 20px;border-bottom:1px solid rgba(255,255,255,.1)}
  .brand-logo{width:42px;height:42px;border-radius:12px;background:rgba(255,255,255,.15);display:flex;align-items:center;justify-content:center;font-size:22px}
  .brand-name{font-size:16px;font-weight:800}
  .brand-sub{font-size:11px;color:rgba(255,255,255,.65)}
  .nav{flex:1;padding:14px 12px;overflow-y:auto}
  .nav-item{display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:10px;font-size:13.5px;font-weight:600;color:rgba(255,255,255,.8);cursor:pointer;margin-bottom:2px;transition:background .15s}
  .nav-item:hover{background:rgba(255,255,255,.08)}
  .nav-item.active{background:rgba(255,255,255,.16);color:#fff}
  .nav-ico{width:18px;text-align:center}
  .profile{display:flex;align-items:center;gap:10px;padding:16px 18px;border-top:1px solid rgba(255,255,255,.1);cursor:pointer}
  .profile-avatar{width:38px;height:38px;border-radius:50%;background:#3b5bdb;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;overflow:hidden;flex-shrink:0}
  .profile-avatar img{width:100%;height:100%;object-fit:cover}
  .profile-name{font-size:13px;font-weight:700}
  .profile-role{font-size:11px;color:rgba(255,255,255,.6)}

  /* MAIN */
  .main{flex:1;min-width:0;padding:28px 32px}
  .topbar{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:26px;gap:16px;flex-wrap:wrap}
  .topbar h1{font-size:26px;font-weight:800;color:#0f172a}
  .topbar p{font-size:13.5px;color:#64748b;margin-top:4px}
  .topbar-actions{display:flex;gap:10px;align-items:center}
  .search-box{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:9px 14px;font-size:13px;width:220px;outline:none}
  .search-box:focus{border-color:#3b5bdb}
  .btn{cursor:pointer;border:none;border-radius:10px;font-weight:700;font-size:13px;padding:10px 18px}
  .btn-p{background:#2563eb;color:#fff}
  .btn-p:hover{background:#1d4ed8}
  .btn-s{background:#fff;border:1px solid #e2e8f0;color:#475569;padding:8px 14px}

  /* STAT CARDS */
  .stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:22px}
  .stat-card{background:#fff;border-radius:16px;padding:18px 20px;box-shadow:0 1px 3px rgba(15,23,42,.06);display:flex;gap:14px;align-items:flex-start}
  .stat-ico{width:42px;height:42px;border-radius:12px;background:#eef2ff;display:flex;align-items:center;justify-content:center;font-size:19px;flex-shrink:0}
  .stat-label{font-size:12.5px;color:#64748b;font-weight:600}
  .stat-num{font-size:26px;font-weight:800;color:#0f172a;margin-top:2px}
  .stat-link{font-size:11.5px;color:#2563eb;font-weight:700;cursor:pointer;margin-top:4px}

  /* GRID */
  .grid-2{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;margin-bottom:18px}
  @media (max-width:900px){.grid-2{grid-template-columns:1fr}}
  .card{background:#fff;border-radius:16px;padding:20px 22px;box-shadow:0 1px 3px rgba(15,23,42,.06)}
  .card-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
  .card-h h3{font-size:15px;font-weight:800;color:#0f172a}
  .card-link{font-size:12px;color:#2563eb;font-weight:700;cursor:pointer}

  table{width:100%;border-collapse:collapse}
  th{text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.04em;padding:8px 6px;border-bottom:1px solid #eef1f6;font-weight:700}
  td{padding:11px 6px;font-size:13px;border-bottom:1px solid #f1f5f9;color:#334155}
  .avatar-sm{width:30px;height:30px;border-radius:9px;background:#dbeafe;color:#2563eb;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;margin-right:8px}
  .badge{padding:3px 10px;border-radius:10px;font-size:11px;font-weight:700}
  .badge.active{background:#dcfce7;color:#16a34a}
  .badge.onboarding{background:#fef3c7;color:#b45309}
  .badge.paused{background:#fee2e2;color:#dc2626}
  .perf-row{display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid #f1f5f9}
  .perf-row:last-child{border-bottom:none}
  .perf-ico{width:38px;height:38px;border-radius:10px;background:#eef2ff;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
  .perf-name{font-size:13.5px;font-weight:700;color:#0f172a}
  .perf-sub{font-size:11.5px;color:#94a3b8}
  .perf-num{font-size:14px;font-weight:800;color:#0f172a;text-align:right}
  .perf-rate{font-size:11px;color:#16a34a;font-weight:700;text-align:right}
  .act-row{display:flex;gap:12px;align-items:flex-start;padding:11px 0;border-bottom:1px solid #f1f5f9}
  .act-row:last-child{border-bottom:none}
  .act-ico{width:34px;height:34px;border-radius:9px;background:#eef2ff;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
  .act-text{font-size:13px;font-weight:600;color:#1e293b}
  .act-detail{font-size:11.5px;color:#94a3b8}
  .act-time{font-size:11px;color:#cbd5e1;white-space:nowrap;margin-left:auto}

  .empty{text-align:center;color:#94a3b8;padding:36px;font-size:13px}
  a{color:#2563eb;text-decoration:none}

  /* GUIDE ACCORDION (usado en la vista Empresas) */
  details{border:1px solid #e2e8f0;border-radius:12px;margin-bottom:10px;background:#f8fafc}
  summary{cursor:pointer;padding:14px 16px;font-weight:700;font-size:13.5px;list-style:none;display:flex;align-items:center;gap:8px;color:#1e293b}
  summary::-webkit-details-marker{display:none}
  summary:before{content:'▶';font-size:10px;color:#2563eb;transition:transform .15s}
  details[open] summary:before{transform:rotate(90deg)}
  .guide-body{padding:2px 18px 16px}
  .guide-body ol,.guide-body ul{margin-left:20px;line-height:1.85}
  .guide-body li{font-size:12.5px;color:#475569}
  .guide-body b{color:#0f172a}
  .guide-body code{background:#eef2ff;padding:2px 6px;border-radius:5px;font-size:11.5px;color:#2563eb}
  .guide-body p{font-size:12.5px;color:#64748b;margin:6px 0 10px}
  .tip{background:#eef2ff;border-left:3px solid #2563eb;padding:9px 13px;border-radius:0 8px 8px 0;font-size:12px;color:#1e3a8a;margin:10px 0}

  .row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px}
  .field{display:flex;flex-direction:column;gap:5px}
  .field label{font-size:11px;color:#64748b;font-weight:600}
  input,select{background:#fff;border:1px solid #e2e8f0;border-radius:9px;padding:9px 12px;color:#1e293b;font-size:13px;outline:none}
  input:focus,select:focus{border-color:#2563eb}

  .placeholder-card{background:#fff;border-radius:16px;padding:60px 30px;text-align:center;box-shadow:0 1px 3px rgba(15,23,42,.06)}
  .placeholder-card .ico{font-size:44px;margin-bottom:14px}
  .placeholder-card h3{font-size:17px;color:#0f172a;margin-bottom:8px}
  .placeholder-card p{font-size:13px;color:#64748b;max-width:420px;margin:0 auto}

  svg text{font-family:inherit}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-logo">🤖</div>
      <div><div class="brand-name">Zenviora AI</div><div class="brand-sub">Chatbot Manager</div></div>
    </div>
    <nav class="nav" id="nav">
      <div class="nav-item active" data-view="dashboard"><span class="nav-ico">🏠</span> Dashboard</div>
      <div class="nav-item" data-view="empresas"><span class="nav-ico">🏢</span> Empresas</div>
      <div class="nav-item" data-view="conversaciones"><span class="nav-ico">💬</span> Conversaciones</div>
      <div class="nav-item" data-view="analiticas"><span class="nav-ico">📊</span> Analíticas</div>
      <div class="nav-item" data-view="plantillas"><span class="nav-ico">🗂️</span> Plantillas</div>
      <div class="nav-item" data-view="flujos"><span class="nav-ico">🔀</span> Flujos</div>
      <div class="nav-item" data-view="integraciones"><span class="nav-ico">🔌</span> Integraciones</div>
      <div class="nav-item" data-view="usuarios"><span class="nav-ico">👥</span> Usuarios</div>
      <div class="nav-item" data-view="facturacion"><span class="nav-ico">💳</span> Facturación</div>
      <div class="nav-item" data-view="configuracion"><span class="nav-ico">⚙️</span> Configuración</div>
    </nav>
    <div class="profile" onclick="goView('configuracion')">
      <div class="profile-avatar" id="profile-avatar">A</div>
      <div><div class="profile-name" id="profile-name">Administrador</div><div class="profile-role">Administrador</div></div>
    </div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div><h1 id="page-title">Resumen general</h1><p id="page-sub">Administra y monitorea todos tus chatbots desde un solo lugar.</p></div>
      <div class="topbar-actions">
        <input class="search-box" placeholder="Buscar empresa…" id="global-search" onkeydown="if(event.key==='Enter')searchGo()">
        <button class="btn btn-p" onclick="goView('empresas');setTimeout(()=>document.getElementById('nc-name')?.focus(),100)">+ Nueva empresa</button>
      </div>
    </div>
    <div id="view"></div>
  </main>
</div>

<script>
const TOKEN='__TOKEN__';
const $=s=>document.querySelector(s);
let S={view:'dashboard'};

async function api(path,opts){
  const url='/master'+path+(path.includes('?')?'&':'?')+'token='+TOKEN;
  const r=await fetch(url,opts);
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Error');}
  return r.json();
}

function goView(v){
  S.view=v;
  document.querySelectorAll('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.view===v));
  const titles={dashboard:['Resumen general','Administra y monitorea todos tus chatbots desde un solo lugar.'],
    empresas:['Empresas','Crea y administra las empresas de tu SaaS.'],
    conversaciones:['Conversaciones','Las conversaciones más recientes de todas tus empresas.'],
    analiticas:['Analíticas','Métricas detalladas de rendimiento.'],
    plantillas:['Plantillas','Plantillas de mensajes aprobadas por Meta.'],
    flujos:['Flujos','Automatizaciones y flujos de conversación.'],
    integraciones:['Integraciones','Conecta otras herramientas a tu SaaS.'],
    usuarios:['Usuarios','Administradores con acceso a este panel.'],
    facturacion:['Facturación','Planes y cobros de tus empresas clientes.'],
    configuracion:['Configuración','Tu perfil y ajustes de la plataforma.']};
  const [t,s]=titles[v]||[v,''];
  $('#page-title').textContent=t;$('#page-sub').textContent=s;
  render();
}
document.querySelectorAll('.nav-item').forEach(el=>el.addEventListener('click',()=>goView(el.dataset.view)));

function searchGo(){
  const q=$('#global-search').value.trim().toLowerCase();
  if(!q)return;
  goView('empresas');
  setTimeout(()=>{S._companies=(S._allCompanies||[]).filter(c=>c.name.toLowerCase().includes(q));renderEmpresasTable();},150);
}

function timeAgo(iso){
  if(!iso)return '';
  const diff=(Date.now()-new Date(iso).getTime())/1000;
  if(diff<60)return 'Hace un momento';
  if(diff<3600)return 'Hace '+Math.floor(diff/60)+' min';
  if(diff<86400)return 'Hace '+Math.floor(diff/3600)+' hora'+(Math.floor(diff/3600)>1?'s':'');
  return 'Hace '+Math.floor(diff/86400)+' día'+(Math.floor(diff/86400)>1?'s':'');
}
function statusBadge(s){
  const labels={active:'Activo',onboarding:'Onboarding',paused:'Pausado'};
  return `<span class="badge ${s}">${labels[s]||s}</span>`;
}
function initials(name){return (name||'?').trim().split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase()||'?';}

/* ─── SVG line chart (sin librerias externas) ─── */
function lineChart(points,w,h){
  const max=Math.max(1,...points.map(p=>p.count));
  const stepX=w/(points.length-1||1);
  const coords=points.map((p,i)=>[i*stepX, h-(p.count/max)*(h-24)-4]);
  const path=coords.map((c,i)=>(i===0?'M':'L')+c[0].toFixed(1)+','+c[1].toFixed(1)).join(' ');
  const area=path+` L${w},${h} L0,${h} Z`;
  const dots=coords.map((c,i)=>`<circle cx="${c[0].toFixed(1)}" cy="${c[1].toFixed(1)}" r="3.5" fill="#2563eb"><title>${points[i].label}: ${points[i].count}</title></circle>`).join('');
  const labels=points.map((p,i)=>`<text x="${(i*stepX).toFixed(1)}" y="${h+16}" font-size="10" fill="#94a3b8" text-anchor="middle">${p.label}</text>`).join('');
  return `<svg width="100%" height="${h+24}" viewBox="0 0 ${w} ${h+24}" preserveAspectRatio="none" style="overflow:visible">
    <path d="${area}" fill="#2563eb" opacity="0.08"></path>
    <path d="${path}" fill="none" stroke="#2563eb" stroke-width="2.5"></path>
    ${dots}${labels}
  </svg>`;
}

/* ─── DASHBOARD ─── */
async function renderDashboard(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let d;try{d=await api('/api/dashboard');}catch(e){$('#view').innerHTML='<div class="empty">Error cargando el dashboard</div>';return;}
  if(S.view!=='dashboard')return;
  $('#view').innerHTML=`
    <div class="stat-row">
      <div class="stat-card"><div class="stat-ico">🏢</div><div><div class="stat-label">Empresas activas</div><div class="stat-num">${d.companies_active}</div><div class="stat-link" onclick="goView('empresas')">Ver todas →</div></div></div>
      <div class="stat-card"><div class="stat-ico">🤖</div><div><div class="stat-label">Chatbots activos</div><div class="stat-num">${d.chatbots_active}</div><div class="stat-link" onclick="goView('empresas')">Ver todos →</div></div></div>
      <div class="stat-card"><div class="stat-ico">💬</div><div><div class="stat-label">Conversaciones hoy</div><div class="stat-num">${d.conversations_today}</div></div></div>
      <div class="stat-card"><div class="stat-ico">👥</div><div><div class="stat-label">Contactos totales</div><div class="stat-num">${d.total_contacts}</div></div></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-h"><h3>Conversaciones (últimos 7 días)</h3></div>
        ${d.chart.some(p=>p.count>0)?lineChart(d.chart,560,180):'<div class="empty">Aún no hay conversaciones registradas</div>'}
      </div>
      <div class="card">
        <div class="card-h"><h3>Rendimiento por empresa</h3></div>
        ${d.performance.length?d.performance.map(perfRow).join(''):'<div class="empty">Aún no hay conversaciones para medir rendimiento</div>'}
      </div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-h"><h3>Empresas recientes</h3><span class="card-link" onclick="goView('empresas')">Ver todas →</span></div>
        ${d.recent_companies.length?`<table><thead><tr><th>Empresa</th><th>Conversaciones hoy</th><th>Estado</th></tr></thead><tbody>${d.recent_companies.map(recentCompanyRow).join('')}</tbody></table>`:'<div class="empty">Aún no has creado ninguna empresa</div>'}
      </div>
      <div class="card">
        <div class="card-h"><h3>Actividad reciente</h3></div>
        ${d.activity.length?d.activity.map(actRow).join(''):'<div class="empty">Sin actividad todavía</div>'}
      </div>
    </div>`;
}
function perfRow(p){
  return `<div class="perf-row"><div class="perf-ico">🤖</div>
    <div style="flex:1"><div class="perf-name">${p.name}</div><div class="perf-sub">${p.business_type}</div></div>
    <div><div class="perf-num">${p.conversations}</div><div class="perf-sub">Conversaciones</div></div>
    <div><div class="perf-rate">${p.success_rate}%</div><div class="perf-sub">Resueltas IA</div></div>
  </div>`;
}
function recentCompanyRow(c){
  return `<tr><td><span class="avatar-sm">${initials(c.name)}</span><b>${c.name}</b></td><td>${c.conversations_today}</td><td>${statusBadge(c.status)}</td></tr>`;
}
function actRow(a){
  return `<div class="act-row"><div class="act-ico">🔔</div>
    <div style="flex:1"><div class="act-text">${a.text}</div><div class="act-detail">${a.detail}</div></div>
    <div class="act-time">${timeAgo(a.at)}</div>
  </div>`;
}

/* ─── EMPRESAS ─── */
async function loadTypes(){
  try{const types=await api('/api/business-types');
    $('#nc-type').innerHTML=types.map(t=>`<option value="${t.key}">${t.label}</option>`).join('');
  }catch(e){}
}
async function renderEmpresas(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  $('#view').innerHTML=`
    <div class="card" style="margin-bottom:18px">
      <div class="card-h"><h3>📖 Guía paso a paso</h3></div>
      <p style="font-size:12px;color:#64748b;margin-bottom:10px">Ábrela cuando vayas a dar de alta una empresa nueva.</p>
      <details open>
        <summary>1️⃣ Cómo crear una empresa en este panel</summary>
        <div class="guide-body"><ol>
          <li>Completa <b>Nombre</b> y <b>Tipo de negocio</b> en el formulario de abajo.</li>
          <li>Si aún no tienes las credenciales de WhatsApp de Meta, <b>déjalas vacías</b> — puedes crear la empresa igual y completarlas después (botón "Editar" en la tabla).</li>
          <li>Pon el <b>correo de notificaciones</b> del dueño del negocio.</li>
          <li>Clic en <b>Crear empresa</b>. El sistema genera un link único de panel para esa empresa.</li>
          <li>Copia el link (botón "Abrir panel" en la tabla) y compártelo con el dueño del negocio — es su panel privado.</li>
          <li>El dueño entra a <b>Configuración → Entrenamiento</b> y escribe la información de su negocio. El bot la usa de inmediato.</li>
          <li>Antes de conectar el número real de WhatsApp, prueba el bot en <b>Ayuda → Chat de prueba</b> dentro del panel de esa empresa.</li>
        </ol></div>
      </details>
      <details>
        <summary>2️⃣ Cómo conseguir el número de WhatsApp y las credenciales en Meta</summary>
        <div class="guide-body">
          <p>Esto se hace UNA vez por cada empresa nueva, en la cuenta de Meta de esa empresa. Empieza SIEMPRE con la Opción A (gratis) para probar el bot antes de conectar el número real.</p>
          <ol>
            <li>Crea (o usa) una cuenta de <b>Meta Business</b> en <code>business.facebook.com</code>.</li>
            <li>Ve a <code>developers.facebook.com/apps</code> → <b>Crear app</b> → tipo <b>"Otro"</b> → <b>"Empresa"</b>.</li>
            <li>Agrega el producto <b>WhatsApp</b> a la app.</li>
          </ol>
          <p><b>🧪 Opción A — Número de PRUEBA (gratis, recomendado para empezar):</b></p>
          <ol>
            <li>En <b>WhatsApp → Configuración de la API</b>, Meta ya te da un <b>número de prueba gratis</b> con un <b>token temporal</b> (dura 24h, lo regeneras cuando quieras desde la misma pantalla).</li>
            <li>En la sección <b>"Para: Números de teléfono"</b>, agrega tu propio celular como <b>destinatario autorizado</b> (Meta te envía un código para verificarlo).</li>
            <li>Copia el <b>phone_number_id</b> y el <b>token temporal</b> — pégalos aquí marcando <b>"Es un número de prueba"</b> al crear la empresa.</li>
            <li>Escríbele por WhatsApp a ese número de prueba desde tu celular ya autorizado, y verás responder al bot con lo que hayas puesto en Entrenamiento.</li>
          </ol>
          <p><b>✅ Opción B — Número REAL de producción (cuando ya vayas a lanzar con clientes reales):</b></p>
          <ol>
            <li>En <b>Administrador de WhatsApp Business</b>, agrega el número real de la empresa (no puede estar ya activo en la app normal de WhatsApp) y verifícalo por SMS/llamada.</li>
            <li><b>Token permanente</b>: Configuración del negocio → Usuarios del sistema → Agregar → asigna la app de WhatsApp → genera token con permisos <code>whatsapp_business_messaging</code> + <code>whatsapp_business_management</code>, sin expiración.</li>
            <li>Copia el <b>phone_number_id</b> real desde Configuración de la API.</li>
            <li>Edita la empresa aquí, pega las nuevas credenciales y <b>desmarca "Es un número de prueba"</b>.</li>
          </ol>
          <p><b>Para ambas opciones</b>, configura el <b>Webhook</b> en la misma pantalla de Meta: URL <code>https://TU-DOMINIO/webhook</code>, token de verificación (el que pongas en el servidor), suscríbete a <b>messages</b>.</p>
          <div class="tip">💡 Todas las empresas comparten la MISMA url de webhook — el sistema identifica sola a cada una por su phone_number_id. No importa si es número de prueba o real, el webhook es igual.</div>
        </div>
      </details>
      <details>
        <summary>3️⃣ Cómo crear plantillas de mensajes aprobadas por Meta</summary>
        <div class="guide-body">
          <ol>
            <li><code>business.facebook.com</code> → <b>WhatsApp Manager</b> → <b>Plantillas de mensajes</b> → <b>Crear plantilla</b>.</li>
            <li>Categoría: <b>Utilidad</b> (postventa/recordatorios) o <b>Marketing</b> (promociones).</li>
            <li>Nombre en minúsculas sin espacios (ej: <code>recontacto_general</code>).</li>
            <li>Idioma: Español. Usa <code>{{1}}</code> para el nombre del cliente.</li>
            <li>Envíala a revisión (minutos a 24-48h).</li>
            <li>Cuando esté Aprobada, copia el nombre exacto y pégalo en el panel de esa empresa (Postventa / Campañas).</li>
          </ol>
          <div class="tip">💡 Sin plantilla aprobada, los mensajes fuera de 24h no llegan.</div>
        </div>
      </details>
    </div>

    <div class="card" style="margin-bottom:18px">
      <div class="card-h"><h3>➕ Nueva empresa</h3></div>
      <div class="row">
        <div class="field"><label>Nombre</label><input id="nc-name" style="width:180px" placeholder="Panadería El Trigal"></div>
        <div class="field"><label>Tipo de negocio</label><select id="nc-type" style="width:200px"></select></div>
        <div class="field"><label>WhatsApp phone_number_id</label><input id="nc-phone" style="width:170px" placeholder="(opcional por ahora)"></div>
        <div class="field"><label>WhatsApp access_token</label><input id="nc-token" style="width:170px" placeholder="(opcional por ahora)"></div>
        <div class="field"><label>Correo de notificaciones</label><input id="nc-email" style="width:190px" placeholder="dueno@empresa.com"></div>
        <button class="btn btn-p" onclick="createCompany()">Crear empresa</button>
      </div>
      <label style="display:flex;align-items:center;gap:8px;margin:6px 0 10px;font-size:12.5px;color:#334155;cursor:pointer">
        <input type="checkbox" id="nc-test" checked style="width:16px;height:16px;accent-color:#2563eb">
        🧪 Es un número de PRUEBA (recomendado) — así puedes probar el bot con todo lo que entrenaste antes de usarlo con clientes reales
      </label>
      <p style="font-size:11.5px;color:#94a3b8">Si aún no tienes el número de WhatsApp conectado, puedes crearla igual y completar esos datos después (ver Guía, sección 2).</p>
    </div>

    <div class="card">
      <div class="card-h"><h3>🏢 Empresas registradas</h3></div>
      <div id="companies"><div class="empty">Cargando…</div></div>
    </div>`;
  loadTypes();
  loadCompanies();
}

function numberBadge(c){
  return c.is_test_number
    ? '<span class="badge onboarding">🧪 Prueba</span>'
    : '<span class="badge active">✅ Producción</span>';
}
function companyRow(c){
  const panelUrl=location.origin+'/admin/panel?token='+c.admin_token;
  return `<tr>
    <td><span class="avatar-sm">${initials(c.name)}</span><b>${c.name}</b><div style="font-size:11px;color:#94a3b8;margin-left:38px">${c.slug}</div></td>
    <td>${c.business_type}</td>
    <td>${statusBadge(c.status)}</td>
    <td>${numberBadge(c)}</td>
    <td>${c.conversations}</td>
    <td>${c.messages_today}</td>
    <td>${c.last_activity?timeAgo(c.last_activity):'—'}</td>
    <td style="white-space:nowrap">
      <a href="${panelUrl}" target="_blank"><button class="btn btn-s">Abrir panel</button></a>
      <button class="btn btn-s" onclick="openEdit(${c.id})">✏️ Editar</button>
      ${c.status!=='active'?`<button class="btn btn-s" onclick="setStatus(${c.id},'active')">▶️ Activar</button>`:''}
      ${c.status!=='paused'?`<button class="btn btn-s" onclick="setStatus(${c.id},'paused')">⏸️ Pausar</button>`:''}
    </td>
  </tr>
  <tr id="edit-row-${c.id}" style="display:none"><td colspan="8">
    <div class="row" style="padding:10px 0">
      <div class="field"><label>WhatsApp phone_number_id</label><input id="ed-phone-${c.id}" style="width:190px" value="${c.whatsapp_phone_number_id.startsWith('pendiente-')?'':c.whatsapp_phone_number_id}"></div>
      <div class="field"><label>WhatsApp access_token</label><input id="ed-token-${c.id}" style="width:220px" placeholder="(déjalo vacío para no cambiarlo)"></div>
      <div class="field"><label>Correo de notificaciones</label><input id="ed-email-${c.id}" style="width:190px" value="${c.notification_email}"></div>
      <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:#334155;cursor:pointer">
        <input type="checkbox" id="ed-test-${c.id}" ${c.is_test_number?'checked':''} style="width:16px;height:16px;accent-color:#2563eb">
        🧪 Número de prueba
      </label>
      <button class="btn btn-p" onclick="saveEdit(${c.id})">Guardar</button>
      <button class="btn btn-s" onclick="openEdit(${c.id})">Cancelar</button>
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
    is_test_number:$('#ed-test-'+id).checked,
  };
  const tok=$('#ed-token-'+id).value.trim();
  if(tok)body.whatsapp_access_token=tok;
  try{await api('/api/companies/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    alert('✅ Datos actualizados');loadCompanies();}
  catch(e){alert('Error: '+e.message);}
}
function renderEmpresasTable(){
  const cs=S._companies||[];
  if(!$('#companies'))return;
  if(!cs.length){$('#companies').innerHTML='<div class="empty">Sin resultados.</div>';return;}
  $('#companies').innerHTML=`<table><thead><tr><th>Empresa</th><th>Tipo</th><th>Estado</th><th>Número</th><th>Conversaciones</th><th>Msjs hoy</th><th>Última actividad</th><th></th></tr></thead>
    <tbody>${cs.map(companyRow).join('')}</tbody></table>`;
}
async function loadCompanies(){
  let cs=[];
  try{cs=await api('/api/companies');}catch(e){$('#companies').innerHTML='<div class="empty">Error cargando empresas</div>';return;}
  S._allCompanies=cs;S._companies=cs;
  if(!cs.length){$('#companies').innerHTML='<div class="empty">Aún no has creado ninguna empresa.</div>';return;}
  renderEmpresasTable();
}
async function createCompany(){
  const name=$('#nc-name').value.trim();
  if(!name){alert('Ponle un nombre a la empresa');return;}
  const body={
    name, business_type:$('#nc-type').value,
    whatsapp_phone_number_id:$('#nc-phone').value.trim(),
    whatsapp_access_token:$('#nc-token').value.trim(),
    notification_email:$('#nc-email').value.trim(),
    is_test_number:$('#nc-test').checked,
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

/* ─── CONVERSACIONES (todas las empresas) ─── */
async function renderConversaciones(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let convs=[];try{convs=await api('/api/recent-conversations');}catch(e){}
  if(S.view!=='conversaciones')return;
  $('#view').innerHTML=`<div class="card">
    <div class="card-h"><h3>💬 Conversaciones recientes (todas las empresas)</h3></div>
    ${convs.length?`<table><thead><tr><th>Empresa</th><th>Cliente</th><th>Modo</th><th>Último mensaje</th><th>Hace</th><th></th></tr></thead>
      <tbody>${convs.map(c=>`<tr>
        <td><b>${c.company_name}</b></td>
        <td>+${c.phone_number}</td>
        <td>${c.mode==='human'?'👤 Humano':'🤖 IA'}</td>
        <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(c.preview||'').replace(/</g,'&lt;')}</td>
        <td>${timeAgo(c.updated_at)}</td>
        <td><a href="${location.origin+c.panel_url}" target="_blank"><button class="btn btn-s">Abrir</button></a></td>
      </tr>`).join('')}</tbody></table>`:'<div class="empty">Aún no hay conversaciones en ninguna empresa.</div>'}
  </div>`;
}

/* ─── ANALÍTICAS (reusa datos reales del dashboard) ─── */
async function renderAnaliticas(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let d;try{d=await api('/api/dashboard');}catch(e){}
  if(S.view!=='analiticas')return;
  $('#view').innerHTML=`
    <div class="card" style="margin-bottom:18px">
      <div class="card-h"><h3>Conversaciones (últimos 7 días) — todas las empresas</h3></div>
      ${d&&d.chart.some(p=>p.count>0)?lineChart(d.chart,700,220):'<div class="empty">Aún no hay datos suficientes</div>'}
    </div>
    <div class="card">
      <div class="card-h"><h3>Rendimiento por empresa</h3></div>
      ${d&&d.performance.length?d.performance.map(perfRow).join(''):'<div class="empty">Aún no hay conversaciones para medir rendimiento</div>'}
    </div>`;
}

/* ─── PLACEHOLDERS (funcionalidad futura, aun no construida) ─── */
function renderPlaceholder(icon,title,text){
  $('#view').innerHTML=`<div class="placeholder-card"><div class="ico">${icon}</div><h3>${title}</h3><p>${text}</p></div>`;
}

/* ─── CONFIGURACIÓN (perfil del administrador) ─── */
async function renderConfiguracion(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let prof={name:'Administrador',photo_b64:''};try{prof=await api('/api/profile');}catch(e){}
  if(S.view!=='configuracion')return;
  $('#view').innerHTML=`
    <div class="card" style="max-width:520px">
      <div class="card-h"><h3>👤 Tu perfil</h3></div>
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:18px">
        <div class="profile-avatar" style="width:64px;height:64px;font-size:22px;color:#fff" id="cfg-avatar-preview">${prof.photo_b64?`<img src="${prof.photo_b64}">`:initials(prof.name)}</div>
        <label class="btn btn-s" style="cursor:pointer">Cambiar foto
          <input type="file" accept="image/*" style="display:none" onchange="onProfilePhoto(this)"></label>
      </div>
      <div class="field" style="margin-bottom:14px"><label>Nombre</label><input id="cfg-name" style="width:100%" value="${(prof.name||'').replace(/"/g,'&quot;')}"></div>
      <button class="btn btn-p" onclick="saveProfile()">💾 Guardar</button>
    </div>`;
}
let _pendingPhoto=null;
function onProfilePhoto(input){
  const file=input.files[0];if(!file)return;
  const reader=new FileReader();
  reader.onload=e=>{_pendingPhoto=e.target.result;$('#cfg-avatar-preview').innerHTML=`<img src="${_pendingPhoto}">`;};
  reader.readAsDataURL(file);
}
async function saveProfile(){
  const name=$('#cfg-name').value.trim();
  const body={name};
  if(_pendingPhoto)body.photo_b64=_pendingPhoto;
  try{await api('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    alert('✅ Perfil guardado');loadProfileBadge();}
  catch(e){alert('Error: '+e.message);}
}
async function loadProfileBadge(){
  try{const prof=await api('/api/profile');
    $('#profile-name').textContent=prof.name||'Administrador';
    $('#profile-avatar').innerHTML=prof.photo_b64?`<img src="${prof.photo_b64}">`:initials(prof.name);
  }catch(e){}
}

function render(){
  const v=S.view;
  if(v==='dashboard')renderDashboard();
  else if(v==='empresas')renderEmpresas();
  else if(v==='conversaciones')renderConversaciones();
  else if(v==='analiticas')renderAnaliticas();
  else if(v==='configuracion')renderConfiguracion();
  else if(v==='plantillas')renderPlaceholder('🗂️','Plantillas de Meta','Próximamente: administra aquí las plantillas de WhatsApp aprobadas por Meta para todas tus empresas. Por ahora, créalas directamente en Meta Business (ver guía en Empresas) y configúralas dentro del panel de cada empresa.');
  else if(v==='flujos')renderPlaceholder('🔀','Flujos de conversación','Próximamente: diseña flujos y automatizaciones visuales para tus chatbots.');
  else if(v==='integraciones')renderPlaceholder('🔌','Integraciones','Próximamente: conecta CRMs, hojas de cálculo y otras herramientas a tu SaaS.');
  else if(v==='usuarios')renderPlaceholder('👥','Usuarios administradores','Próximamente: invita a otros administradores con acceso a este panel maestro.');
  else if(v==='facturacion')renderPlaceholder('💳','Facturación','Próximamente: gestiona los planes y cobros de las empresas que atiendes.');
}

loadProfileBadge();
render();
setInterval(()=>{if(S.view==='dashboard')renderDashboard();if(S.view==='empresas')loadCompanies();},20000);
</script>
</body></html>"""
