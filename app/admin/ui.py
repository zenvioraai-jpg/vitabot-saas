"""
Panel administrativo del bot — SPA (Single Page Application), reutilizable por
cualquier empresa del SaaS. Se sirve desde /admin/panel y consume los endpoints
JSON del router. El token y el nombre de la empresa se inyectan reemplazando
__TOKEN__ / __COMPANY_NAME__ para evitar el escape de llaves.
"""


def render_panel(token: str, company_name: str = "VitaBot") -> str:
    return (_PANEL_HTML
            .replace("__TOKEN__", token)
            .replace("__COMPANY_NAME__", company_name))


_PANEL_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>__COMPANY_NAME__ — Panel</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiByeD0iMTQiIGZpbGw9IiNmZmZmZmYiLz48dGV4dCB4PSIzMiIgeT0iNDciIGZvbnQtZmFtaWx5PSJHZW9yZ2lhLCZhcG9zO1RpbWVzIE5ldyBSb21hbiZhcG9zOyxzZXJpZiIgZm9udC1zaXplPSI0OCIgZm9udC13ZWlnaHQ9IjcwMCIgZmlsbD0iIzdhYzA0MyIgdGV4dC1hbmNob3I9Im1pZGRsZSI+UTwvdGV4dD48L3N2Zz4=">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<meta name="theme-color" content="#0b1020">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="VitaPanel">
<link rel="apple-touch-icon" href="/admin/icon-512.png">
<link rel="manifest" href="/admin/manifest.webmanifest?token=__TOKEN__">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    color-scheme:dark;
    --bg:#0b1020; --bg2:#0f1629; --panel:#111a2e; --panel2:#0d1424;
    --border:#1e2a44; --text:#e6ecf7; --muted:#8a98b5; --muted2:#5b6b8c;
    --pri:#7c3aed; --pri2:#6d28d9; --grad:linear-gradient(135deg,#7c3aed,#6d28d9);
    --accent:#a78bfa;
    --hover:#16203a; --inp:#0d1424; --soft:#222b3f;
    --bubble-in:#1a2236; --chat-bg:radial-gradient(circle at 50% 0,#0e1730,#0b1020);
    --pill-bg:rgba(124,58,237,.16); --pill-fg:#c4b5fd;
    --g-bg:#0e2a1a; --g-fg:#4ade80; --b-bg:#0e1b3a; --b-fg:#60a5fa;
    --a-bg:#2a230e; --a-fg:#fbbf24; --r-bg:#2a0e14; --r-fg:#f87171;
    --shadow:0 12px 30px rgba(0,0,0,.35); --shadow-sm:0 2px 10px rgba(0,0,0,.20); --radius:16px;
    --green:#22c55e; --amber:#f59e0b; --blue:#3b82f6; --red:#ef4444;
  }
  /* TEMA CLARO */
  [data-theme=light]{
    color-scheme:light;
    --bg:#eef1f7; --bg2:#ffffff; --panel:#ffffff; --panel2:#f4f6fb;
    --border:#e3e8f0; --text:#18233a; --muted:#5d6b85; --muted2:#94a0b8;
    --accent:#6d28d9;
    --hover:#eef2fb; --inp:#f1f4fa; --soft:#eef2f9;
    --bubble-in:#eef1f7; --chat-bg:#f5f7fc;
    --pill-bg:#ede9fe; --pill-fg:#6d28d9;
    --g-bg:#dcfce7; --g-fg:#15803d; --b-bg:#dbeafe; --b-fg:#1d4ed8;
    --a-bg:#fef3c7; --a-fg:#b45309; --r-bg:#fee2e2; --r-fg:#b91c1c;
    --shadow:0 12px 30px rgba(20,30,60,.10); --shadow-sm:0 2px 10px rgba(20,30,60,.06);
  }
  /* TEMA NEGRO */
  [data-theme=black]{
    --bg:#000000; --bg2:#0a0a0a; --panel:#131313; --panel2:#0c0c0c;
    --border:#272727; --text:#f4f4f5; --muted:#a1a1aa; --muted2:#71717a;
    --pri:#8b5cf6; --pri2:#7c3aed; --grad:linear-gradient(135deg,#8b5cf6,#6d28d9); --accent:#c4b5fd;
    --hover:#1a1a1a; --inp:#0d0d0d; --soft:#1f1f1f;
    --bubble-in:#1c1c1c; --chat-bg:radial-gradient(circle at 50% 0,#141414,#000);
    --pill-bg:rgba(139,92,246,.2); --pill-fg:#c4b5fd;
    --shadow:0 12px 34px rgba(0,0,0,.7); --shadow-sm:0 2px 12px rgba(0,0,0,.5);
  }
  /* TEMA VERDE */
  [data-theme=green]{
    --bg:#07130d; --bg2:#0a1a12; --panel:#0e2219; --panel2:#0a1a12;
    --border:#1c3b2b; --text:#e9f5ee; --muted:#8fb3a0; --muted2:#5e7d6c;
    --pri:#16a34a; --pri2:#15803d; --grad:linear-gradient(135deg,#22c55e,#15803d); --accent:#4ade80;
    --hover:#10271c; --inp:#0a1a12; --soft:#15301f;
    --bubble-in:#123121; --chat-bg:radial-gradient(circle at 50% 0,#0c1f15,#07130d);
    --pill-bg:rgba(34,197,94,.16); --pill-fg:#86efac;
    --shadow:0 12px 30px rgba(0,0,0,.45); --shadow-sm:0 2px 10px rgba(0,0,0,.35);
  }
  html,body{height:100%}
  body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);overflow:hidden;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;letter-spacing:-.01em;transition:background .25s,color .25s}
  .app{display:flex;height:100vh}
  ::-webkit-scrollbar{width:7px;height:7px}
  ::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
  ::-webkit-scrollbar-thumb:hover{background:var(--muted2)}
  a{color:inherit;text-decoration:none}

  /* ─── SIDEBAR ─── */
  .sidebar{width:240px;background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0}
  .brand{display:flex;align-items:center;gap:10px;padding:18px 18px}
  .brand-logo{width:40px;height:40px;border-radius:12px;object-fit:cover;background:#fff;box-shadow:var(--shadow-sm)}
  .brand-name{font-size:17px;font-weight:800;letter-spacing:-.3px}
  .brand-name span{color:var(--accent)}
  .brand-sub{font-size:10px;color:var(--muted2);margin-top:1px}
  .nav{flex:1;overflow-y:auto;padding:8px 10px}
  .nav-item{display:flex;align-items:center;gap:11px;padding:10px 12px;border-radius:10px;color:var(--muted);font-size:13.5px;font-weight:600;cursor:pointer;margin-bottom:2px;transition:all .15s}
  .nav-item:hover{background:var(--hover);color:var(--text)}
  .nav-item.active{background:var(--grad);color:#fff;box-shadow:0 6px 18px rgba(124,58,237,.35)}
  .nav-ico{width:18px;text-align:center;font-size:15px}
  .nav-badge{margin-left:auto;background:var(--pri);color:#fff;font-size:10px;font-weight:700;padding:1px 7px;border-radius:10px}
  .nav-item.active .nav-badge{background:rgba(255,255,255,.25)}
  .plan{margin:10px;padding:16px;border-radius:14px;background:var(--grad);text-align:center}
  .plan-title{font-size:14px;font-weight:800}
  .plan-sub{font-size:11px;opacity:.85;margin:3px 0 12px}
  .plan-btn{background:rgba(255,255,255,.2);border:none;color:#fff;padding:8px 16px;border-radius:9px;font-size:12px;font-weight:700;cursor:pointer;width:100%}

  /* ─── MAIN ─── */
  .main{flex:1;display:flex;flex-direction:column;min-width:0}
  .topbar{height:70px;display:flex;align-items:center;gap:16px;padding:0 22px;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--bg2)}
  .topbar h1{font-size:20px;font-weight:800;letter-spacing:-.4px}
  .topbar .sub{font-size:12px;color:var(--muted)}
  .conn{display:flex;align-items:center;gap:7px;background:#0e2a1a;border:1px solid #1f5236;color:#4ade80;padding:7px 13px;border-radius:20px;font-size:12px;font-weight:600;margin-left:auto}
  .dot{width:7px;height:7px;border-radius:50%;background:#22c55e;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .user{display:flex;align-items:center;gap:9px}
  .user-av{width:38px;height:38px;border-radius:50%;background:var(--grad);display:flex;align-items:center;justify-content:center;font-weight:700}
  .user-nm{font-size:13px;font-weight:700}
  .user-rl{font-size:11px;color:var(--muted)}
  .view{flex:1;overflow-y:auto;padding:22px}
  .view.nopad{padding:0;overflow:hidden}

  /* ─── CARDS / STATS ─── */
  .stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px}
  .stat{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow-sm);transition:transform .18s,box-shadow .18s}
  .stat:hover{transform:translateY(-3px);box-shadow:var(--shadow)}
  .stat-top{display:flex;justify-content:space-between;align-items:flex-start}
  .stat-ico{width:48px;height:48px;border-radius:13px;display:flex;align-items:center;justify-content:center;font-size:22px}
  .stat-label{font-size:13px;color:var(--muted);margin-bottom:6px;font-weight:500}
  .stat-num{font-size:30px;font-weight:800;letter-spacing:-1px}
  .stat-foot{font-size:11px;color:var(--muted2);margin-top:8px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow-sm)}
  .card-h{font-size:16px;font-weight:700;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;letter-spacing:-.2px}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}

  /* recent list */
  .rc{display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid var(--border)}
  .rc:last-child{border-bottom:none}
  .av{width:40px;height:40px;border-radius:50%;background:var(--grad);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0}
  .rc-nm{font-size:13.5px;font-weight:700}
  .rc-tx{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:230px}
  .pill{font-size:10.5px;font-weight:700;padding:3px 10px;border-radius:11px}
  .pill.ai{background:var(--pill-bg);color:var(--pill-fg)}
  .pill.human{background:var(--g-bg);color:var(--g-fg)}
  .pill.wait{background:var(--a-bg);color:var(--a-fg)}
  .pill.closed{background:var(--soft);color:var(--muted)}

  /* bars chart */
  .bars{display:flex;align-items:flex-end;gap:10px;height:170px;padding-top:10px}
  .bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;height:100%;justify-content:flex-end}
  .bar{width:60%;background:var(--grad);border-radius:6px 6px 0 0;min-height:3px;transition:height .4s}
  .bar-lb{font-size:11px;color:var(--muted)}

  /* ─── CHAT (3 columnas) ─── */
  .chat{display:flex;height:100%;min-height:0}
  .clist{width:300px;border-right:1px solid var(--border);display:flex;flex-direction:column;background:var(--bg2);flex-shrink:0}
  .clist-h{padding:16px;border-bottom:1px solid var(--border)}
  .clist-h .t{font-size:16px;font-weight:800;margin-bottom:10px}
  .search{width:100%;background:var(--panel2);border:1px solid var(--border);border-radius:9px;padding:9px 12px;color:var(--text);font-size:13px;outline:none}
  .search:focus{border-color:var(--pri)}
  .filters{display:flex;gap:6px;padding:10px 14px;border-bottom:1px solid var(--border);overflow-x:auto}
  .fbtn{background:transparent;border:none;color:var(--muted);font-size:12px;font-weight:700;padding:5px 11px;border-radius:14px;cursor:pointer;white-space:nowrap}
  .fbtn.active{background:var(--pill-bg);color:var(--pill-fg)}
  .fbtn .c{opacity:.7;margin-left:3px}
  .convs{flex:1;overflow-y:auto}
  .conv{display:flex;gap:11px;padding:12px 14px;cursor:pointer;border-bottom:1px solid var(--border);transition:background .12s}
  .conv:hover{background:var(--hover)}
  .conv.active{background:var(--hover);border-left:3px solid var(--pri)}
  .conv-md{flex:1;min-width:0}
  .conv-top{display:flex;justify-content:space-between;align-items:center}
  .conv-nm{font-size:13.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .conv-tm{font-size:10.5px;color:var(--muted2);flex-shrink:0;margin-left:6px}
  .conv-pv{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:2px 0 5px}
  .conv-unread{background:var(--pri);color:#fff;font-size:10px;font-weight:700;min-width:18px;height:18px;border-radius:9px;display:inline-flex;align-items:center;justify-content:center;padding:0 5px}

  .cmain{flex:1;display:flex;flex-direction:column;min-width:0}
  .cmain-h{height:66px;display:flex;align-items:center;gap:12px;padding:0 18px;border-bottom:1px solid var(--border);flex-shrink:0}
  .cmain-nm{font-size:15px;font-weight:700}
  .cmain-ph{font-size:12px;color:var(--muted)}
  .mode-toggle{margin-left:auto;position:relative}
  .mode-btn{display:flex;align-items:center;gap:8px;background:var(--pill-bg);border:1px solid var(--border);color:var(--pill-fg);padding:8px 14px;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer}
  .mode-btn.human{background:var(--g-bg);border-color:var(--border);color:var(--g-fg)}
  .icon-btn{background:transparent;border:none;color:var(--muted);font-size:18px;cursor:pointer;padding:6px;border-radius:8px}
  .icon-btn:hover{background:var(--hover);color:var(--text)}

  .msgs{flex:1;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:10px;background:var(--chat-bg)}
  .day{align-self:center;background:var(--hover);color:var(--muted);font-size:11px;padding:5px 14px;border-radius:12px;margin:4px 0}
  .row{display:flex;gap:8px;align-items:flex-end;max-width:72%}
  .row.in{align-self:flex-start}
  .row.out{align-self:flex-end;flex-direction:row-reverse}
  .bot-av{width:30px;height:30px;border-radius:50%;background:var(--grad);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
  .bubble{padding:11px 15px;border-radius:14px;font-size:13.5px;line-height:1.5;white-space:pre-wrap;word-break:break-word;position:relative}
  .msg-del{position:absolute;top:-9px;right:-6px;background:var(--bg2);border:1px solid var(--border);border-radius:50%;width:24px;height:24px;display:none;align-items:center;justify-content:center;font-size:12px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.25)}
  .row:hover .msg-del{display:flex}
  @media(hover:none){.msg-del{display:flex;opacity:.55}}
  .row.in .bubble{background:var(--bubble-in);border-bottom-left-radius:4px}
  .row.out .bubble{background:var(--grad);border-bottom-right-radius:4px}
  .row.out.human .bubble{background:linear-gradient(135deg,#2563eb,#1d4ed8)}
  .row.out.internal .bubble{background:#3a2e0e;color:#fde68a;border:1px dashed #a16207;font-style:italic}
  .b-time{font-size:10px;opacity:.7;margin-top:5px;text-align:right}

  .composer{border-top:1px solid var(--border);padding:14px 18px;flex-shrink:0}
  .quick{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
  .qbtn{background:var(--inp);border:1px solid var(--border);color:var(--muted);font-size:12px;font-weight:600;padding:6px 12px;border-radius:8px;cursor:pointer}
  .qbtn:hover{border-color:var(--pri);color:var(--pill-fg)}
  .crow{display:flex;gap:10px;align-items:flex-end}
  .cinput{flex:1;background:var(--panel2);border:1px solid var(--border);border-radius:22px;padding:11px 16px;color:var(--text);font-size:13.5px;resize:none;outline:none;max-height:120px;font-family:inherit;line-height:1.4}
  .cinput:focus{border-color:var(--pri)}
  .send{width:44px;height:44px;border-radius:50%;background:var(--grad);border:none;color:#fff;font-size:17px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center}
  .send:disabled{background:#3a4566;opacity:.5;cursor:not-allowed}
  .ai-hint{font-size:11px;color:var(--muted2);text-align:center;padding:6px}

  .cinfo{width:300px;border-left:1px solid var(--border);background:var(--bg2);flex-shrink:0;overflow-y:auto;padding:18px}
  .cinfo-hd{text-align:center;padding-bottom:16px;border-bottom:1px solid var(--border)}
  .cinfo-av{width:64px;height:64px;border-radius:50%;background:var(--grad);display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;margin:0 auto 10px}
  .cinfo-nm{font-size:16px;font-weight:700}
  .cinfo-ph{font-size:12px;color:var(--muted);margin-top:3px}
  .sec{padding:16px 0;border-bottom:1px solid var(--border)}
  .sec-t{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:12px}
  .inf{display:flex;justify-content:space-between;margin-bottom:9px;font-size:12.5px;gap:10px}
  .inf .k{color:var(--muted)}
  .inf .v{font-weight:600;text-align:right;word-break:break-word}
  .tags{display:flex;flex-wrap:wrap;gap:6px}
  .tag{font-size:11px;font-weight:700;padding:5px 11px;border-radius:13px}
  .tag.g{background:var(--g-bg);color:var(--g-fg)}
  .tag.p{background:var(--pill-bg);color:var(--pill-fg)}
  .tag.a{background:var(--a-bg);color:var(--a-fg)}
  .act{display:flex;flex-direction:column;gap:9px}
  .act-btn{display:flex;align-items:center;gap:10px;padding:11px 14px;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;border:none}
  .act-btn.g{background:var(--g-bg);color:var(--g-fg)}
  .act-btn.b{background:var(--b-bg);color:var(--b-fg)}
  .act-btn.p{background:var(--grad);color:#fff}
  .act-btn.r{background:var(--r-bg);color:var(--r-fg)}
  .act-btn:hover{filter:brightness(1.15)}

  /* tabla clientes */
  .tbl-wrap{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;color:var(--muted);font-weight:700;font-size:12px;padding:12px 14px;border-bottom:1px solid var(--border);white-space:nowrap}
  td{padding:13px 14px;border-bottom:1px solid var(--border);white-space:nowrap}
  tr:hover td{background:var(--hover)}
  .prod-pill{background:var(--pill-bg);color:var(--pill-fg);font-size:11px;font-weight:700;padding:3px 9px;border-radius:10px}

  .empty{text-align:center;padding:60px 20px;color:var(--muted)}
  .empty .ico{font-size:48px;margin-bottom:12px}
  .placeholder{display:flex;align-items:center;justify-content:center;height:100%;flex-direction:column;color:var(--muted)}
  .placeholder .ico{font-size:64px;margin-bottom:16px;opacity:.5}

  .modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}
  .modal.open{display:flex}
  .modal-box{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:24px;width:90%;max-width:420px}
  .modal-box h3{font-size:17px;margin-bottom:16px}
  .modal-box input{width:100%;background:var(--panel2);border:1px solid var(--border);border-radius:9px;padding:11px 13px;color:var(--text);font-size:13px;margin-bottom:11px;outline:none}
  .modal-box input:focus{border-color:var(--pri)}
  .mbtns{display:flex;gap:9px}
  .mbtns button{flex:1;border:none;border-radius:9px;padding:11px;font-size:13px;font-weight:700;cursor:pointer}
  .mbtns .ok{background:var(--grad);color:#fff}
  .mbtns .no{background:var(--soft);color:var(--text)}
  .toast{position:fixed;bottom:22px;right:22px;background:var(--grad);color:#fff;padding:13px 20px;border-radius:11px;font-size:13px;font-weight:600;z-index:200;display:none;box-shadow:0 10px 30px rgba(124,58,237,.4)}

  /* ─── ANIMACIONES ─── */
  @keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  @keyframes fadeIn{from{opacity:0}to{opacity:1}}
  @keyframes popIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}
  .view{animation:fadeIn .22s ease}
  .stat{animation:fadeUp .28s ease both}
  .stat:nth-child(2){animation-delay:.04s}.stat:nth-child(3){animation-delay:.08s}.stat:nth-child(4){animation-delay:.12s}
  .card{animation:fadeUp .26s ease both}
  .bubble{animation:popIn .18s ease}
  .conv{transition:background .15s,transform .08s}
  .conv:active{transform:scale(.99)}
  .nav-item{transition:background .15s,color .15s,transform .08s}
  .nav-item:active{transform:scale(.98)}
  .qbtn,.act-btn,.fbtn,.send,.mbtns button{transition:transform .08s,filter .15s,background .15s}
  .qbtn:active,.act-btn:active,.fbtn:active,.send:active,.mbtns button:active{transform:scale(.96)}
  .act-btn{transition:transform .12s,filter .15s,box-shadow .15s}
  .act-btn:hover{transform:translateY(-1px)}
  .modal.open .modal-box{animation:popIn .2s ease}
  .toast{animation:fadeUp .25s ease}
  @media(prefers-reduced-motion:reduce){*{animation:none!important}}

  .mobile-only{display:none}
  @media(max-width:1100px){.cinfo{display:none}}
  @media(max-width:900px){.stat-grid{grid-template-columns:repeat(2,1fr)}.two-col{grid-template-columns:1fr}.clist{width:240px}}

  /* ─── MÓVIL / PWA ─── */
  @media(max-width:768px){
    html,body{height:100%;overflow:hidden}
    .app{flex-direction:column;height:100vh;height:100dvh}
    /* Deja espacio para la barra de estado / notch del celular */
    .sidebar{width:100%;height:auto;flex-direction:row;align-items:center;border-right:none;border-bottom:1px solid var(--border);overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;flex-shrink:0;background:var(--bg2);padding-top:env(safe-area-inset-top,0px)}
    /* Barra de filtros de período: que se acomode bien, se vea completa y no se sobreponga */
    .period-bar{justify-content:flex-start!important;gap:8px!important;flex-wrap:wrap!important}
    .period-bar .fbtn{flex:0 0 auto}
    .period-bar input[type=date],.period-bar input[type=month]{font-size:13px!important;padding:7px 9px!important;flex:1 1 42%;min-width:120px;max-width:100%;box-sizing:border-box}
    .period-bar label{font-size:12px;flex:0 0 auto}
    .period-bar>span{flex:0 0 auto}
    .brand{padding:8px 10px;flex-shrink:0}
    .brand-logo{width:32px;height:32px}
    .brand-name{font-size:14px}
    .brand-sub{display:none}
    .nav{flex:1;display:flex;flex-direction:row;flex-wrap:nowrap;padding:6px;gap:4px;overflow-x:auto;overflow-y:hidden}
    .nav-item{flex-shrink:0;padding:7px 11px;white-space:nowrap;font-size:12.5px;margin-bottom:0}
    .nav-item span.nav-ico{font-size:16px}
    .nav-badge{margin-left:6px}
    .conn{display:none}
    /* En el celular solo se muestran las categorías esenciales */
    .nav-item[data-view="excel"],.nav-item[data-view="soon"],.nav-item[data-view="etiquetas"],
    .nav-item[data-view="campanas"],.nav-item[data-view="guias"],.nav-item[data-view="contactos"]{display:none}
    .main{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column;overflow-x:hidden}
    .view,.chat,.cmain,.msgs,.clist,.cmain-h,.composer{min-width:0;max-width:100%;overflow-x:hidden}
    .mode-toggle{min-width:0}
    .bubble{max-width:78vw;overflow-wrap:anywhere}
    .row{max-width:90vw}
    .topbar{height:auto;min-height:48px;padding:8px 14px;flex-shrink:0}
    .topbar h1{font-size:16px}.topbar .sub{display:none}
    .user-nm,.user-rl{display:none}
    .view{flex:1;min-height:0;overflow-y:auto;padding:14px}
    .view.nopad{overflow:hidden;padding:0}
    .stat-grid{grid-template-columns:repeat(2,1fr);gap:10px}
    .stat-num{font-size:22px}
    /* Chat: una sola columna (lista o conversación). El panel de datos se oculta. */
    .chat{flex-direction:column;height:100%;min-height:0}
    .clist{width:100%;height:100%;border-right:none}
    .cmain{display:none;width:100%;height:100%;min-height:0}
    .chat.open .clist{display:none}
    .chat.open .cmain{display:flex}
    /* Evita el zoom de iOS al enfocar campos (letra >=16px) */
    .search,.cinput,.modal-box input,input,textarea{font-size:16px!important}
    .cinfo{display:none!important}
    .cmain-h{height:auto;min-height:56px;padding:8px 10px;gap:7px}
    .cmain-nm{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:120px}
    .cmain-ph{font-size:11px}
    .cmain-h .av{width:34px;height:34px;flex-shrink:0}
    .mode-toggle{flex-shrink:1;min-width:0}
    .mode-btn{font-size:11px;padding:7px 9px;white-space:normal}
    /* Ocultar el boton de refrescar en movil (el chat se actualiza solo); dejar solo el de volver */
    .cmain-h .icon-btn:not(.mobile-only){display:none}
    .msgs{padding:14px}
    .composer{padding:10px 12px}
    .mobile-only{display:flex}
    .row{max-width:90%}
  }
</style>
</head>
<body>
<div class="app">

  <!-- SIDEBAR -->
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-logo" id="brand-logo" style="display:flex;align-items:center;justify-content:center;font-weight:900;font-size:22px;color:#7c3aed;background:#fff;border-radius:12px">•</div>
      <div>
        <div class="brand-name" id="brand-name">__COMPANY_NAME__</div>
        <div class="brand-sub">Panel Administrativo</div>
      </div>
    </div>
    <nav class="nav" id="nav">
      <div class="nav-item active" data-view="dashboard"><span class="nav-ico">🏠</span> Dashboard</div>
      <div class="nav-item" data-view="chat"><span class="nav-ico">💬</span> Conversaciones <span class="nav-badge" id="nav-conv-badge">0</span></div>
      <div class="nav-item" data-view="clientes"><span class="nav-ico">🗄️</span> Datos de Clientes</div>
      <div class="nav-item" data-view="segmentos"><span class="nav-ico">🎗️</span> Segmentación</div>
      <div class="nav-item" data-view="masvendidos"><span class="nav-ico">📈</span> Más vendidos</div>
      <div class="nav-item" data-view="multimedia"><span class="nav-ico">📸</span> Multimedia</div>
      <div class="nav-item" data-view="comprobantes"><span class="nav-ico">🧾</span> Comprobantes</div>
      <div class="nav-item" data-view="excel"><span class="nav-ico">📊</span> Exportar a Excel</div>
      <div class="nav-item" data-view="config"><span class="nav-ico">⚙️</span> Configuración</div>
      <div class="nav-item" data-view="respuestas"><span class="nav-ico">⚡</span> Respuestas Rápidas</div>
      <div class="nav-item" data-view="etiquetas"><span class="nav-ico">🏷️</span> Etiquetas</div>
      <div class="nav-item" data-view="campanas"><span class="nav-ico">📣</span> Campañas</div>
      <div class="nav-item" data-view="ayuda"><span class="nav-ico">❓</span> Ayuda</div>
    </nav>
  </aside>

  <!-- MAIN -->
  <div class="main">
    <div class="topbar" id="topbar"></div>
    <div class="view" id="view"></div>
  </div>
</div>

<!-- MODALS -->
<div class="modal" id="modal-email">
  <div class="modal-box">
    <h3>✉️ Enviar Email</h3>
    <input id="em-to" type="email" placeholder="Correo del cliente">
    <input id="em-nm" type="text" placeholder="Nombre del cliente">
    <input id="em-sm" type="text" placeholder="Resumen del pedido (opcional)">
    <div class="mbtns"><button class="ok" onclick="sendEmail()">Enviar</button><button class="no" onclick="closeModal('modal-email')">Cancelar</button></div>
  </div>
</div>
<div class="modal" id="modal-img">
  <div class="modal-box">
    <h3>📎 Enviar archivo</h3>
    <div onclick="document.getElementById('im-file').click()" style="border:2px dashed var(--pri);border-radius:11px;padding:26px;text-align:center;cursor:pointer;background:rgba(124,58,237,.06);margin-bottom:12px">
      <div style="font-size:30px">📎</div>
      <div id="im-name" style="font-size:13px;font-weight:700;color:#c4b5fd;margin-top:6px">Seleccionar archivo</div>
      <div style="font-size:11px;color:var(--muted)">Foto (máx 5MB) · Video (máx 16MB) · Documento (máx 30MB)</div>
      <input id="im-file" type="file" accept="image/*,video/*,application/pdf" style="display:none" onchange="onImg(this)">
    </div>
    <div class="mbtns"><button class="ok" id="im-send" onclick="sendImage()">Enviar</button><button class="no" onclick="closeModal('modal-img')">Cancelar</button></div>
  </div>
</div>
<div class="modal" id="modal-receipts">
  <div class="modal-box" style="max-width:560px;max-height:85vh;overflow-y:auto">
    <h3>📄 Comprobantes del cliente</h3>
    <div id="receipts-body"><div class="empty">Cargando…</div></div>
    <div class="mbtns" style="margin-top:14px"><button class="no" onclick="closeModal('modal-receipts')">Cerrar</button></div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const TOKEN='__TOKEN__';
const COMPANY_NAME='__COMPANY_NAME__';
const API='/admin';
let S={view:'dashboard',convId:null,filter:'all',convs:[],lastTs:null,custName:'',custPhone:''};

const $=s=>document.querySelector(s);
(function(){const lg=$('#brand-logo');if(lg)lg.textContent=(COMPANY_NAME||'?').trim().charAt(0).toUpperCase()||'?';})();
const initials=n=>!n?'?':n.trim().split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase();
const money=n=>'$'+(n||0).toLocaleString('es-CO');
function timeAgo(iso){if(!iso)return'';const d=(Date.now()-new Date(iso))/1000;if(d<60)return'ahora';if(d<3600)return Math.floor(d/60)+' min';if(d<86400)return Math.floor(d/3600)+' h';return Math.floor(d/86400)+' d';}
function hhmm(iso){return new Date(iso).toLocaleTimeString('es-CO',{hour:'2-digit',minute:'2-digit'});}
function toast(m){const t=$('#toast');t.textContent=m;t.style.display='block';clearTimeout(t._t);t._t=setTimeout(()=>t.style.display='none',2800);}
async function api(path,opts){const sep=path.includes('?')?'&':'?';const r=await fetch(API+path+sep+'token='+TOKEN,opts);if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'Error');return r.headers.get('content-type')?.includes('json')?r.json():r;}
function openModal(id){$('#'+id).classList.add('open')}
function closeModal(id){$('#'+id).classList.remove('open')}

/* ─── NAV ─── */
document.querySelectorAll('.nav-item').forEach(n=>n.onclick=()=>{
  const v=n.dataset.view;
  setActiveNav(v);
  location.hash=v;
  showView(v);
});
function setActiveNav(v){document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.view===v));}
function parseHash(){const h=location.hash.replace('#','');const[v,id]=h.split('/');return{view:v||'dashboard',id:id?parseInt(id):null};}
window.addEventListener('hashchange',()=>{const{view,id}=parseHash();setActiveNav(view);if(view!==S.view)showView(view);if(view==='chat'&&id)setTimeout(()=>openConv(id),300);});

function showView(v){
  S.view=v;
  const view=$('#view'); const top=$('#topbar');
  view.className='view';
  if(v==='dashboard'){topbarDash();renderDash();}
  else if(v==='chat'){view.className='view nopad';topbarChat();renderChat();}
  else if(v==='clientes'){topbarClientes();renderClientes();}
  else if(v==='etiquetas'){topbarSimple('🏷️ Etiquetas','Organiza tus clientes con etiquetas');renderEtiquetas();}
  else if(v==='campanas'){topbarSimple('📣 Campañas','Marketing por email y WhatsApp');renderCampanas();}
  else if(v==='masvendidos'){topbarSimple('📈 Más vendidos','Productos más vendidos y métricas');renderTopProducts();}
  else if(v==='multimedia'){topbarSimple('📸 Multimedia','Fotos y videos de cada producto (el bot y tú los envían al cliente)');renderMultimedia();}
  else if(v==='segmentos'){topbarSimple('🎗️ Segmentación','Clientes clasificados por tipo de piel/necesidad');renderSegmentos();}
  else if(v==='respuestas'){topbarSimple('⚡ Respuestas Rápidas','Plantillas de texto para responder más rápido');renderRespuestas();}
  else if(v==='comprobantes'){topbarSimple('🧾 Comprobantes','Archivo permanente de comprobantes de pago');renderComprobantes();}
  else if(v==='ayuda'){topbarSimple('❓ Ayuda','Cómo usar el panel');renderAyuda();}
  else if(v==='config'){topbarSimple('⚙️ Configuración','Personaliza tu asistente');renderConfig();}
  else if(v==='excel'){topbarSimple('📊 Exportar a Excel','Descarga los datos de clientes');renderExcel();}
  else{topbarSimple('Próximamente','Esta sección estará disponible pronto');view.innerHTML='<div class="placeholder"><div class="ico">🚧</div><div>Sección en construcción</div></div>';}
}

/* ─── TOPBARS ─── */
function userBlock(){return `<div class="user"><div class="user-av">A</div><div><div class="user-nm">Admin</div><div class="user-rl">Administrador</div></div></div>`;}
function topbarDash(){$('#topbar').innerHTML=`<div><h1>¡Bienvenido, Admin! 👋</h1><div class="sub">Aquí tienes el resumen de tu asistente</div></div><div class="conn"><span class="dot"></span> Conectado a WhatsApp</div>${userBlock()}`;}
function topbarChat(){$('#topbar').innerHTML=`<div><h1>Chat en vivo</h1></div><div class="conn"><span class="dot"></span> Conectado</div>${userBlock()}`;}
function topbarClientes(){$('#topbar').innerHTML=`<div><h1>Datos de Clientes</h1><div class="sub">Todos los registros de tus clientes</div></div><button class="qbtn" style="margin-left:auto;padding:10px 16px" onclick="downloadExcel()">📊 Exportar a Excel</button>${userBlock()}`;}
function topbarSimple(t,s){$('#topbar').innerHTML=`<div><h1>${t}</h1><div class="sub">${s}</div></div><div style="margin-left:auto"></div>${userBlock()}`;}

/* ─── DASHBOARD ─── */
async function renderDash(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  const per=S.period||'all';
  const customRange=(S.dateStart&&S.dateEnd);
  const statsUrl=customRange?('/api/stats?start='+S.dateStart+'&end='+S.dateEnd):('/api/stats?period='+per);
  let st,convs;
  try{[st,convs]=await Promise.all([api(statsUrl),api('/api/conversations?filter=all')]);}
  catch(e){$('#view').innerHTML='<div class="empty">Error cargando datos</div>';return;}
  if(S.view!=='dashboard')return;
  S.convs=convs;updateBadge(convs);
  const active=convs.filter(c=>c.status==='open');
  const maxDay=Math.max(...st.per_day.map(d=>d.count),1);
  const totVentas=st.ventas_completadas+st.ventas_en_proceso+st.ventas_pendientes;
  const pct=n=>totVentas?Math.round(n/totVentas*100):0;
  const periodOpts=[['day','Hoy'],['week','Semana'],['month','Mes'],['year','Año'],['all','Todo']];
  $('#view').innerHTML=`
    <div class="period-bar" style="display:flex;justify-content:flex-end;align-items:center;margin-bottom:14px;gap:6px;flex-wrap:wrap">
      ${periodOpts.map(([v,l])=>`<button class="fbtn ${(!customRange&&per===v)?'active':''}" onclick="setPeriod('${v}')">${l}</button>`).join('')}
      <span style="width:1px;height:22px;background:var(--border);margin:0 4px"></span>
      <label style="font-size:12px;color:var(--muted)">Mes:</label>
      <input type="month" id="d-month" value="${S.dateMonth||''}" class="fbtn" style="padding:6px 8px" onchange="applyMonth()">
      <span style="width:1px;height:22px;background:var(--border);margin:0 4px"></span>
      <input type="date" id="d-start" value="${S.dateStart||''}" class="fbtn" style="padding:6px 8px">
      <span style="color:var(--muted);font-size:12px">a</span>
      <input type="date" id="d-end" value="${S.dateEnd||''}" class="fbtn" style="padding:6px 8px">
      <button class="fbtn ${customRange?'active':''}" onclick="applyRange()">📅 Aplicar</button>
      ${customRange?`<button class="fbtn" onclick="clearRange()" title="Quitar filtro">✕</button>`:''}
    </div>
    <div class="stat-grid">
      ${statCard('💬','#1e2748','#a5b4fc','Conversaciones Totales',st.total_conversations)}
      ${statCard('💰','#0e2a1a','#4ade80','Conversaciones con Venta',st.conversations_with_sale)}
      ${statCard('🛍️','#0e1b3a','#60a5fa','Tasa de Conversión',st.conversion_rate+'%')}
      ${statCard('🤖','#221047','#c4b5fd','Resueltas por IA',st.resolved_conversations)}
    </div>
    <div class="stat-grid">
      ${statCard('💵','#0e2a1a','#4ade80','Ventas del Mes',money(st.ventas_mes||0))}
      ${statCard('📅','#0e1b3a','#60a5fa','Ventas de Hoy',money(st.ventas_dia||0))}
      ${statCard('🎟️','#221047','#c4b5fd','Ticket Promedio',money(st.ticket_promedio||0))}
      ${statCard('🔁','#2a230e','#fbbf24','Clientes Recurrentes',st.clientes_recurrentes||0)}
    </div>
    <div class="two-col">
      <div class="card">
        <div class="card-h">Conversaciones Recientes</div>
        <div>${active.slice(0,6).map(rcRow).join('')||'<div class="empty">Sin conversaciones</div>'}</div>
      </div>
      <div class="card">
        <div class="card-h">Conversaciones por día</div>
        <div class="bars">${st.per_day.map(d=>`<div class="bar-wrap"><div class="bar" style="height:${d.count/maxDay*100}%"></div><div class="bar-lb">${d.label}</div></div>`).join('')}</div>
        <div class="card-h" style="margin-top:20px">Estado de Conversaciones</div>
        <div style="display:flex;gap:18px;font-size:13px">
          <div><span style="color:#4ade80">●</span> Cerradas: <b>${st.ventas_completadas}</b> (${pct(st.ventas_completadas)}%)</div>
          <div><span style="color:#60a5fa">●</span> Humano: <b>${st.ventas_en_proceso}</b> (${pct(st.ventas_en_proceso)}%)</div>
          <div><span style="color:#a78bfa">●</span> IA: <b>${st.ventas_pendientes}</b> (${pct(st.ventas_pendientes)}%)</div>
        </div>
      </div>
    </div>`;
}
function setPeriod(p){S.period=p;S.dateStart=null;S.dateEnd=null;S.dateMonth=null;renderDash();}
function clearRange(){S.period='all';S.dateStart=null;S.dateEnd=null;S.dateMonth=null;renderDash();}
function applyRange(){
  const s=$('#d-start').value,e=$('#d-end').value;
  if(!s||!e){toast('Elige fecha de inicio y fin');return;}
  if(s>e){toast('La fecha de inicio no puede ser mayor que la final');return;}
  S.dateStart=s;S.dateEnd=e;S.dateMonth=null;renderDash();
}
function applyMonth(){
  const m=$('#d-month').value;if(!m)return;
  const [y,mo]=m.split('-').map(Number);
  const last=new Date(y,mo,0).getDate();
  S.dateMonth=m;S.dateStart=m+'-01';S.dateEnd=m+'-'+String(last).padStart(2,'0');renderDash();
}
function statCard(ico,bg,col,label,num){return `<div class="stat"><div class="stat-top"><div><div class="stat-label">${label}</div><div class="stat-num">${num}</div></div><div class="stat-ico" style="background:${bg};color:${col}">${ico}</div></div></div>`;}
function rcRow(c){const av=initials(c.customer_name||c.phone_number);const st=convStatus(c);return `<div class="rc"><div class="av">${av}</div><div style="flex:1;min-width:0"><div class="rc-nm">${c.customer_name||('+'+c.phone_number)}</div><div class="rc-tx">${c.last_message_preview||'Sin mensajes'}</div></div><span class="pill ${st.cls}">${st.txt}</span><span class="conv-tm">${timeAgo(c.last_message_at||c.updated_at)}</span></div>`;}
function convStatus(c){if(c.status==='archived')return{cls:'closed',txt:'Archivada'};if(c.status==='resolved')return{cls:'closed',txt:'Cerrada'};if(c.mode==='human')return{cls:'human',txt:'Humano'};return{cls:'ai',txt:'IA'};}

/* ─── CHAT ─── */
function renderChat(){
  $('#view').innerHTML=`
    <div class="chat">
      <div class="clist">
        <div class="clist-h"><div class="t">Conversaciones</div><input class="search" id="csearch" placeholder="Buscar..." oninput="filterConvs()"></div>
        <div class="filters">
          <button class="fbtn active" data-f="all" onclick="setFilter('all')">Todas</button>
          <button class="fbtn" data-f="unread" onclick="setFilter('unread')">No leídas</button>
          <button class="fbtn" data-f="ai" onclick="setFilter('ai')">IA</button>
          <button class="fbtn" data-f="human" onclick="setFilter('human')">Humanas</button>
        </div>
        <div class="convs" id="convs"><div class="empty">Cargando…</div></div>
        <div style="padding:10px 12px;border-top:1px solid var(--border)">
          <button class="fbtn" id="arch-btn" style="width:100%;justify-content:center;text-align:center" onclick="toggleArchived()">🗄️ Ver archivadas</button>
        </div>
      </div>
      <div class="cmain" id="cmain"><div class="placeholder"><div class="ico">💬</div><div>Selecciona una conversación</div></div></div>
      <div class="cinfo" id="cinfo" style="display:none"></div>
    </div>`;
  loadConvs();
}
async function loadConvs(){
  try{S.convs=await api('/api/conversations?filter=all');}catch(e){return;}
  updateBadge(S.convs);drawConvs();
}
function setFilter(f){S.filter=f;document.querySelectorAll('.filters .fbtn').forEach(b=>b.classList.toggle('active',b.dataset.f===f));const ab=$('#arch-btn');if(ab){ab.classList.remove('active');ab.textContent='🗄️ Ver archivadas';}drawConvs();}
function toggleArchived(){
  const ab=$('#arch-btn');
  if(S.filter==='archived'){setFilter('all');}
  else{S.filter='archived';document.querySelectorAll('.filters .fbtn').forEach(b=>b.classList.remove('active'));if(ab){ab.classList.add('active');ab.textContent='← Volver a todas';}drawConvs();}
}
function filterConvs(){drawConvs();}
function drawConvs(){
  const box=$('#convs');if(!box)return;
  const q=($('#csearch')?.value||'').toLowerCase();
  let list=S.convs.slice();
  if(S.filter==='archived')list=list.filter(c=>c.status==='archived');
  else if(S.filter==='ai')list=list.filter(c=>c.mode==='ai'&&c.status!=='archived');
  else if(S.filter==='human')list=list.filter(c=>c.mode==='human'&&c.status!=='archived');
  else if(S.filter==='unread')list=list.filter(c=>c.status==='open');
  else list=list.filter(c=>c.status!=='archived');  /* Todas: oculta archivadas */
  if(q)list=list.filter(c=>(c.customer_name||'').toLowerCase().includes(q)||c.phone_number.includes(q));
  if(!list.length){box.innerHTML='<div class="empty" style="padding:40px 16px">Sin conversaciones</div>';return;}
  box.innerHTML=list.map(c=>{
    const st=convStatus(c);
    return `<div class="conv ${c.id===S.convId?'active':''}" onclick="openConv(${c.id})">
      <div class="av">${initials(c.customer_name||c.phone_number)}</div>
      <div class="conv-md">
        <div class="conv-top"><div class="conv-nm">${c.customer_name||('+'+c.phone_number)}</div><div class="conv-tm">${timeAgo(c.last_message_at||c.updated_at)}</div></div>
        <div class="conv-pv">${c.last_message_preview||'Sin mensajes'}</div>
        <span class="pill ${st.cls}">${st.txt}</span>
      </div></div>`;
  }).join('');
}
function updateBadge(convs){const n=convs.filter(c=>c.status==='open').length;const b=$('#nav-conv-badge');if(b)b.textContent=n;}
function backToList(){document.querySelector('.chat')?.classList.remove('open');S.convId=null;}

async function openConv(id){
  S.convId=id;S.lastTs=null;
  if(location.hash!=='#chat/'+id)location.hash='chat/'+id;
  let c=S.convs.find(x=>x.id===id);
  if(!c){try{S.convs=await api('/api/conversations?filter=all');c=S.convs.find(x=>x.id===id);}catch(e){}}
  if(!c)return;
  S.custName=c.customer_name||('+'+c.phone_number);S.custPhone=c.phone_number;
  drawConvs();
  $('#cmain').innerHTML=`
    <div class="cmain-h">
      <button class="icon-btn mobile-only" onclick="backToList()" style="margin-right:2px">←</button>
      <div class="av">${initials(S.custName)}</div>
      <div><div class="cmain-nm">${S.custName}</div><div class="cmain-ph">+${c.phone_number}</div></div>
      <div class="mode-toggle"><button class="mode-btn" id="modeBtn" onclick="toggleMode()">…</button></div>
      <button class="icon-btn" onclick="loadMessages()">↻</button>
    </div>
    <div class="msgs" id="msgs"><div class="empty">Cargando…</div></div>
    <div class="composer" id="composer"></div>`;
  document.querySelector('.chat')?.classList.add('open');
  $('#cinfo').style.display='block';
  renderInfo(c);
  S._mode=c.mode;
  await loadMessages();
  drawComposer();
}
function drawComposer(){
  const human=S._mode==='human';
  $('#composer').innerHTML=human?`
    <div class="quick">
      <button class="qbtn" onclick="openModal('modal-img')">📎 Archivo</button>
      <button class="qbtn" onclick="openProductModal()">🛍️ Producto</button>
      <button class="qbtn" id="recBtn" onclick="toggleRecord()">🎤 Grabar audio</button>
      <button class="qbtn" onclick="openModal('modal-email')">✉️ Email</button>
      <button class="qbtn" onclick="sendQR()">📱 QR Pago</button>
      <button class="qbtn" onclick="showQuickReplies()">⚡ Respuestas</button>
    </div>
    <div id="rec-preview" style="display:none;align-items:center;gap:8px;flex-wrap:wrap;background:var(--inp);border:1px solid var(--border);border-radius:12px;padding:10px;margin-bottom:10px">
      <audio id="rec-audio" controls style="height:38px;flex:1;min-width:160px"></audio>
      <button class="act-btn p" style="padding:8px 14px" onclick="sendRecordedAudio()">📤 Enviar</button>
      <button class="qbtn" onclick="startRecording()">🔁 Repetir</button>
      <button class="qbtn" style="color:#f87171" onclick="cancelRecording()">✖️ Cancelar</button>
    </div>
    <div class="crow">
      <textarea class="cinput" id="cinput" rows="1" placeholder="Escribe un mensaje..." onkeydown="keydown(event)" oninput="grow(this)"></textarea>
      <button class="send" id="sendBtn" onclick="sendMsg()">➤</button>
    </div>`:`<div class="ai-hint">🤖 La IA está respondiendo automáticamente. Cambia a <b>Humano</b> para escribir.</div>`;
  updateModeBtn();
}
function updateModeBtn(){const b=$('#modeBtn');if(!b)return;const human=S._mode==='human';b.className='mode-btn '+(human?'human':'');b.innerHTML=human?'👤 Humano · Pasar a IA':'🤖 IA Respondiendo · Pasar a Humano';}
async function loadMessages(){
  let msgs;try{msgs=await api(`/api/conversations/${S.convId}/messages`);}catch(e){return;}
  const box=$('#msgs');if(!box)return;
  if(!msgs.length){box.innerHTML='<div class="empty">Sin mensajes aún</div>';return;}
  box.innerHTML='<div class="day">Conversación</div>'+msgs.map(msgRow).join('');
  S.lastTs=msgs[msgs.length-1].timestamp;
  box.scrollTop=box.scrollHeight;
}
function msgRow(m){
  const inbound=m.direction==='inbound';
  let cls='out',av='';
  if(inbound){cls='in';}
  else{av='<div class="bot-av">'+(m.sender==='human_advisor'?'👤':'🤖')+'</div>';cls='out '+(m.is_internal?'internal':(m.sender==='human_advisor'?'human':''));}
  const content=(m.content||'').replace('[NOTA INTERNA]','').trim();
  const mm=content.match(/^\[\[MEDIA\|(image|video)\|([^|]+)\|([^\]]*)\]\]$/);
  let inner;
  if(mm){inner=mediaBubble(mm[1],mm[2],mm[3]);}
  else{inner=escapeHtml(content);}
  const del=`<span class="msg-del" title="Eliminar mensaje" onclick="deleteMsg(${m.id},event)">🗑️</span>`;
  return `<div class="row ${cls}" data-mid="${m.id}">${av}<div class="bubble">${inner}<div class="b-time">${hhmm(m.timestamp)}</div>${del}</div></div>`;
}
async function deleteMsg(id,ev){
  if(ev){ev.stopPropagation();}
  if(!confirm('¿Eliminar este mensaje del panel? (No se borra del WhatsApp del cliente)'))return;
  try{await api(`/conversations/${S.convId}/messages/${id}/delete`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN}});
    const row=document.querySelector(`.row[data-mid="${id}"]`);if(row)row.remove();toast('Mensaje eliminado');}
  catch(e){toast('Error: '+e.message);}
}
function mediaBubble(kind,sku,name){
  const url=`${API}/api/product-media/file/${encodeURIComponent(sku)}/${kind==='image'?'image':'video'}?token=${TOKEN}`;
  const cap=`<div style="font-size:11px;opacity:.75;margin-top:5px">${kind==='image'?'📷':'🎬'} ${escapeHtml(name||sku)}</div>`;
  if(kind==='image')return `<img src="${url}" style="max-width:220px;width:100%;border-radius:10px;display:block" onerror="this.style.display='none'">${cap}`;
  return `<video src="${url}" controls preload="metadata" style="max-width:240px;width:100%;border-radius:10px;display:block;background:#000"></video>${cap}`;
}
function escapeHtml(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function pollMessages(){
  if(!S.convId||!S.lastTs||S.view!=='chat')return;
  try{const msgs=await api(`/api/conversations/${S.convId}/messages?since=${encodeURIComponent(S.lastTs)}`);
    if(msgs.length){const box=$('#msgs');box.insertAdjacentHTML('beforeend',msgs.map(msgRow).join(''));S.lastTs=msgs[msgs.length-1].timestamp;box.scrollTop=box.scrollHeight;}}catch(e){}
}
function grow(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px';}
function keydown(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();}}
async function sendMsg(){
  const inp=$('#cinput');const text=inp.value.trim();if(!text)return;
  const btn=$('#sendBtn');btn.disabled=true;
  try{await api(`/conversations/${S.convId}/send_message`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({text})});
    inp.value='';inp.style.height='auto';await pollMessages();}
  catch(e){toast('Error enviando mensaje');}finally{btn.disabled=false;inp.focus();}
}
async function toggleMode(){
  const newMode=S._mode==='ai'?'human':'ai';
  try{await api(`/conversations/${S.convId}/set_mode`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({mode:newMode,notify_customer:newMode==='ai'})});
    S._mode=newMode;const c=S.convs.find(x=>x.id===S.convId);if(c)c.mode=newMode;
    drawComposer();drawConvs();toast(newMode==='human'?'Cambiado a modo Humano':'Devuelto a IA');}
  catch(e){toast('Error cambiando modo');}
}
async function sendQR(){
  if(!confirm('¿Enviar el código QR de pago a este cliente?'))return;
  try{await api(`/conversations/${S.convId}/send_qr`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN}});await pollMessages();toast('✅ QR enviado');}
  catch(e){toast('Error: '+e.message);}
}
function onImg(i){const f=i.files[0];if(f)$('#im-name').textContent='📎 '+f.name;}
async function sendImage(){
  const f=$('#im-file').files[0];
  if(!f){toast('Selecciona un archivo');return;}
  if(f.size>30*1024*1024){toast('El archivo no puede superar 30MB');return;}
  const btn=$('#im-send');btn.disabled=true;btn.textContent='Enviando…';
  try{const fd=new FormData();fd.append('file',f);
    await api(`/conversations/${S.convId}/upload_and_send`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd});
    closeModal('modal-img');$('#im-file').value='';$('#im-name').textContent='Seleccionar archivo';await pollMessages();toast('✅ Enviado');}
  catch(e){toast('Error: '+e.message);}finally{btn.disabled=false;btn.textContent='Enviar';}
}
async function sendEmail(){
  const to=$('#em-to').value.trim(),nm=$('#em-nm').value.trim(),sm=$('#em-sm').value.trim();
  if(!to||!nm){toast('Ingresa correo y nombre');return;}
  try{await api(`/conversations/${S.convId}/send_email`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({to_email:to,customer_name:nm,order_summary:sm})});
    closeModal('modal-email');$('#em-to').value='';$('#em-nm').value='';$('#em-sm').value='';toast('✅ Email enviado');await pollMessages();}
  catch(e){toast('Error: '+e.message);}
}
async function openProductModal(){
  let cat=[];try{cat=await api('/api/product-media');}catch(e){}
  const dim='opacity:.3;pointer-events:none';
  const thumb=p=>p.image_preview
    ?`<img src="${p.image_preview}" style="width:44px;height:44px;object-fit:cover;border-radius:8px;border:1px solid var(--border)" onerror="this.style.display='none'">`
    :`<div style="width:44px;height:44px;border-radius:8px;background:var(--inp);display:flex;align-items:center;justify-content:center;font-size:18px">🛍️</div>`;
  const rows=cat.map(p=>`<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
    ${thumb(p)}
    <span style="flex:1;font-size:13px;min-width:0">${p.name}</span>
    <button class="qbtn" style="padding:4px 8px;${p.has_image_file?'':dim}" title="${p.has_image_file?'Enviar foto':'Sin foto — súbela en Multimedia'}" onclick="sendProduct('${p.sku}','photo')">📷</button>
    <button class="qbtn" style="padding:4px 8px;${p.has_video_file?'':dim}" title="${p.has_video_file?'Enviar video':'Sin video'}" onclick="sendProduct('${p.sku}','video')">🎬</button>
    <button class="qbtn" style="padding:4px 8px;${p.link?'':dim}" title="${p.link?'Enviar link de compra':'Sin link'}" onclick="sendProduct('${p.sku}','link')">🔗</button>
  </div>`).join('');
  showInfoModal('🛍️ Enviar de la biblioteca Multimedia','<div style="font-size:11px;color:var(--muted);margin-bottom:8px">📷 foto · 🎬 video de uso · 🔗 link de compra. Se envían al cliente y quedan en el chat. (Para cargar archivos usa la categoría 📸 Multimedia.)</div>'+rows);
}
async function sendProduct(sku,what){
  toast('Enviando…');
  try{await api('/conversations/'+S.convId+'/send_product',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({sku,what})});
    toast('✅ Enviado');closeModal('info-modal');await pollMessages();}
  catch(e){toast('Error: '+e.message);}
}
let _rec=null,_recChunks=[],_recStream=null,_recBlob=null,_recExt='ogg',_recUrl=null;
function toggleRecord(){
  if(_rec&&_rec.state==='recording'){_rec.stop();return;}
  startRecording();
}
async function startRecording(){
  const btn=$('#recBtn');
  // limpiar previsualización previa
  $('#rec-preview').style.display='none';
  if(_recUrl){URL.revokeObjectURL(_recUrl);_recUrl=null;}
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia||!window.MediaRecorder){
    toast('Tu navegador no soporta grabar audio. Usa Chrome o Safari actualizado.');return;}
  try{
    _recStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const prefs=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/webm','audio/mp4'];
    let mime='';
    try{mime=prefs.find(m=>MediaRecorder.isTypeSupported&&MediaRecorder.isTypeSupported(m))||'';}catch(_){mime='';}
    _rec=mime?new MediaRecorder(_recStream,{mimeType:mime}):new MediaRecorder(_recStream);
    _recChunks=[];
    _rec.ondataavailable=e=>{if(e.data&&e.data.size)_recChunks.push(e.data);};
    _rec.onstop=()=>{
      _recStream.getTracks().forEach(t=>t.stop());
      if(btn){btn.textContent='🎤 Grabar audio';btn.style.color='';}
      const type=(_rec.mimeType||'audio/ogg').split(';')[0];
      _recExt=type.includes('ogg')?'ogg':(type.includes('mp4')?'m4a':'webm');
      _recBlob=new Blob(_recChunks,{type});
      _recUrl=URL.createObjectURL(_recBlob);
      // Mostrar previsualización para escuchar antes de enviar
      const a=$('#rec-audio');if(a)a.src=_recUrl;
      $('#rec-preview').style.display='flex';
    };
    _rec.start();
    if(btn){btn.textContent='⏹️ Detener';btn.style.color='#f87171';}
    toast('🎙️ Grabando… toca Detener para escucharlo');
  }catch(e){
    const n=(e&&e.name)||'';
    if(n==='NotAllowedError'||n==='SecurityError'){toast('Permiso de micrófono denegado. Habilítalo en el navegador (icono 🔒 de la barra).');}
    else if(n==='NotFoundError'){toast('No se detectó ningún micrófono en este equipo.');}
    else{toast('No se pudo grabar: '+(n||e.message||'error desconocido'));}
  }
}
async function showQuickReplies(){
  let items=S._qr;
  if(!items){try{items=await api('/api/quick-replies');S._qr=items;}catch(e){items=[];}}
  if(!items.length){toast('No tienes respuestas rápidas. Créalas en ⚡ Respuestas Rápidas.');return;}
  const body=items.map((it,i)=>`
    <div onclick="insertQuick(${i})" style="border:1px solid var(--border);border-radius:10px;padding:11px;margin-bottom:8px;cursor:pointer" onmouseover="this.style.borderColor='var(--pri)'" onmouseout="this.style.borderColor='var(--border)'">
      <div style="font-weight:700;font-size:13px;margin-bottom:3px">${(it.title||'').replace(/</g,'&lt;')}</div>
      <div style="font-size:12px;color:var(--muted);white-space:pre-wrap">${(it.text||'').replace(/</g,'&lt;').slice(0,140)}</div>
    </div>`).join('');
  showInfoModal('⚡ Respuestas rápidas', body);
}
function insertQuick(i){
  const it=(S._qr||[])[i];if(!it)return;
  const inp=$('#cinput');if(inp){inp.value=it.text;inp.focus();grow(inp);}
  closeModal('info-modal');
}
function cancelRecording(){
  $('#rec-preview').style.display='none';
  if(_recUrl){URL.revokeObjectURL(_recUrl);_recUrl=null;}
  _recBlob=null;
}
async function sendRecordedAudio(){
  if(!_recBlob){toast('Graba un audio primero');return;}
  toast('Enviando audio…');
  try{const fd=new FormData();fd.append('file',_recBlob,'nota.'+_recExt);
    const r=await fetch(`${API}/conversations/${S.convId}/send_audio?token=${TOKEN}`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd});
    if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Error');}
    cancelRecording();toast('✅ Audio enviado');await pollMessages();
  }catch(e){toast('Error: '+e.message);}
}
function renderInfo(c){
  $('#cinfo').innerHTML=`
    <div class="cinfo-hd"><div class="cinfo-av">${initials(S.custName)}</div><div class="cinfo-nm">${S.custName}</div><div class="cinfo-ph">+${c.phone_number}</div></div>
    <div class="sec">
      <div class="sec-t">Datos del Cliente</div>
      <div class="inf"><span class="k">Estado</span><span class="v" id="i-estado">—</span></div>
      <div class="inf"><span class="k">Cédula</span><span class="v" id="i-ced">—</span></div>
      <div class="inf"><span class="k">Correo</span><span class="v" id="i-mail">—</span></div>
      <div class="inf"><span class="k">Dirección</span><span class="v" id="i-dir">—</span></div>
      <div class="inf"><span class="k">Última compra</span><span class="v" id="i-last">—</span></div>
      <div class="inf"><span class="k">Total gastado</span><span class="v" id="i-total">—</span></div>
      <div class="inf"><span class="k"># Compras</span><span class="v" id="i-ncomp">—</span></div>
      <div class="inf"><span class="k">Producto top</span><span class="v" id="i-top">—</span></div>
      <div class="inf"><span class="k">Ticket prom.</span><span class="v" id="i-ticket">—</span></div>
      <div class="inf"><span class="k">Estado</span><span class="v" id="i-cli-estado">—</span></div>
    </div>
    <div class="sec"><div class="sec-t">Etiquetas</div><div class="tags" id="tags-list"><span style="color:var(--muted2);font-size:12px">…</span></div>
      <button class="qbtn" style="margin-top:10px" onclick="promptAddTag()">+ Agregar etiqueta</button></div>
    <div class="sec" style="border-bottom:none">
      <div class="sec-t">Acciones Rápidas</div>
      <div class="act">
        <button class="act-btn g" onclick="toggleMode()">🔄 Cambiar IA / Humano</button>
        <button class="act-btn b" onclick="sendQR()">📱 Enviar QR de pago</button>
        <button class="act-btn b" onclick="openReceipts()">📄 Ver comprobantes</button>
        <button class="act-btn p" onclick="openModal('modal-email')">✉️ Enviar plantilla</button>
        <button class="act-btn g" onclick="markPaymentReceived()">💵 Marcar pago recibido</button>
        <button class="act-btn r" onclick="closeConv()">✅ Marcar como cerrada</button>
        <button class="act-btn b" onclick="archiveConv()">🗄️ Archivar / Desarchivar</button>
        <button class="act-btn r" style="color:#fff;background:#7f1d1d" onclick="deleteConvChat()">🗑️ Eliminar conversación</button>
      </div>
    </div>`;
  fillCustomer(c.phone_number);
  loadTags(c.phone_number);
}
const TAG_COLORS=['g','p','a'];
async function loadTags(phone){
  try{const tags=await api('/api/customers/'+phone+'/tags');const box=$('#tags-list');if(!box)return;
    box.innerHTML=tags.length?tags.map(t=>`<span class="tag ${t.color||'p'}" title="Click para quitar" style="cursor:pointer" onclick="removeTag('${phone}','${t.tag.replace(/'/g,"")}')">${t.tag} ✕</span>`).join(''):'<span style="color:var(--muted2);font-size:12px">Sin etiquetas</span>';}
  catch(e){}
}
async function promptAddTag(){
  const phone=S.custPhone;if(!phone)return;
  const tag=prompt('Nueva etiqueta (ej: VIP, Oncológico, Mayorista):');
  if(!tag)return;
  const color=TAG_COLORS[Math.floor(Math.random()*TAG_COLORS.length)];
  try{await api('/api/customers/'+phone+'/tags',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({tag,color})});loadTags(phone);toast('Etiqueta agregada');}
  catch(e){toast('Error: '+e.message);}
}
async function removeTag(phone,tag){
  try{await api('/api/customers/'+phone+'/tags/'+encodeURIComponent(tag),{method:'DELETE',headers:{'Authorization':'Bearer '+TOKEN}});loadTags(phone);}
  catch(e){toast('Error: '+e.message);}
}
async function openReceipts(){
  const phone=S.custPhone;if(!phone)return;
  openModal('modal-receipts');
  const body=$('#receipts-body');body.innerHTML='<div class="empty">Cargando…</div>';
  try{const rs=await api('/api/receipts?phone='+phone);
    if(!rs.length){body.innerHTML='<div class="empty">Este cliente no ha enviado comprobantes.</div>';return;}
    body.innerHTML=rs.map(r=>`
      <div style="border:1px solid var(--border);border-radius:12px;padding:12px;margin-bottom:12px;display:flex;gap:12px">
        ${r.image?`<a href="${r.image}" target="_blank"><img src="${r.image}" style="width:90px;height:90px;object-fit:cover;border-radius:8px"></a>`:''}
        <div style="flex:1;font-size:12.5px">
          <div style="margin-bottom:4px"><span class="pill ${r.is_valid?'human':'closed'}">${r.is_valid?'✓ Válido':'Pendiente/Rechazado'}</span></div>
          <div class="inf"><span class="k">Banco</span><span class="v">${r.bank}</span></div>
          <div class="inf"><span class="k">Monto</span><span class="v">${money(r.amount)}</span></div>
          <div class="inf"><span class="k">Referencia</span><span class="v">${r.reference}</span></div>
          <div class="inf"><span class="k">Fecha comprobante</span><span class="v">${r.receipt_date}</span></div>
          <div class="inf"><span class="k">Recibido</span><span class="v">${new Date(r.created_at).toLocaleString('es-CO')}</span></div>
        </div>
      </div>`).join('');
  }catch(e){body.innerHTML='<div class="empty">Error: '+e.message+'</div>';}
}
async function renderEtiquetas(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let tags,convs;
  try{[tags,convs]=await Promise.all([api('/api/tags'),api('/api/conversations?filter=all')]);}
  catch(e){$('#view').innerHTML='<div class="empty">Error</div>';return;}
  if(S.view!=='etiquetas')return;
  $('#view').innerHTML=`
    <div class="card" style="max-width:760px">
      <div class="card-h">Etiquetas en uso</div>
      ${tags.length?`<div class="tags">${tags.map(t=>`<span class="tag ${t.color||'p'}" style="font-size:13px;padding:8px 14px">${t.tag} · ${t.count}</span>`).join('')}</div>`:'<div class="empty">Aún no hay etiquetas. Agrégalas desde el panel de un cliente en Conversaciones.</div>'}
      <p style="color:var(--muted);font-size:13px;margin-top:18px;line-height:1.6">
        Para etiquetar un cliente: abre <b>Conversaciones</b>, selecciona el chat y usa
        <b>+ Agregar etiqueta</b> en el panel de la derecha. Las etiquetas te ayudan a clasificar
        clientes (VIP, Oncológico, Mayorista, etc.).</p>
    </div>`;
}
async function fillCustomer(phone){
  try{const all=await api('/api/customers');const cu=all.find(x=>x.phone_number===phone);if(!cu)return;
    const c=S.convs.find(x=>x.id===S.convId);
    $('#i-estado').textContent=c?convStatus(c).txt:'—';
    $('#i-ced').textContent=cu.cedula;$('#i-mail').textContent=cu.email;$('#i-dir').textContent=cu.address;
    $('#i-last').textContent=cu.last_purchase;$('#i-total').textContent=money(cu.total);
    if($('#i-ncomp'))$('#i-ncomp').textContent=cu.purchase_count;
    if($('#i-top'))$('#i-top').textContent=cu.top_product||'—';
    if($('#i-ticket'))$('#i-ticket').textContent=money(cu.ticket_promedio||0);
    if($('#i-cli-estado'))$('#i-cli-estado').textContent=cu.estado||'—';
  }catch(e){}
}
async function markPaymentReceived(){
  if(!confirm('¿Confirmas que ya se recibió el pago de este pedido?'))return;
  try{await api('/conversations/'+S.convId+'/mark-payment-received',{method:'POST',headers:{'Authorization':'Bearer '+TOKEN}});
    toast('✅ Pago marcado como recibido');fillCustomer(S.custPhone);}
  catch(e){toast('Error: '+e.message);}
}
async function closeConv(){
  if(!confirm('¿Marcar esta conversación como cerrada? (No se borra, queda en el historial)'))return;
  try{await api(`/conversations/${S.convId}/close`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN}});
    const c=S.convs.find(x=>x.id===S.convId);if(c)c.status='resolved';drawConvs();toast('Conversación cerrada');}
  catch(e){toast('Error: '+e.message);}
}
async function archiveConv(){
  const c=S.convs.find(x=>x.id===S.convId);
  const isArch=c&&c.status==='archived';
  const archived=!isArch;
  try{await api(`/conversations/${S.convId}/archive`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({archived})});
    if(c)c.status=archived?'archived':'open';drawConvs();toast(archived?'🗄️ Conversación archivada':'Conversación desarchivada');}
  catch(e){toast('Error: '+e.message);}
}
async function deleteConvChat(){
  if(!confirm('⚠️ Eliminar esta conversación borra su hilo de mensajes (y los pedidos/comprobantes ligados SOLO a este chat). El cliente NO se borra. ¿Continuar?'))return;
  try{await api(`/conversations/${S.convId}/delete`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN}});
    S.convs=S.convs.filter(x=>x.id!==S.convId);S.convId=null;
    const m=$('#cmain');if(m)m.innerHTML='<div class="placeholder"><div class="ico">💬</div><div>Selecciona una conversación</div></div>';
    const ci=$('#cinfo');if(ci)ci.style.display='none';
    drawConvs();toast('🗑️ Conversación eliminada');}
  catch(e){toast('Error: '+e.message);}
}

/* ─── CLIENTES ─── */
async function renderClientes(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let cs;try{cs=await api('/api/customers');}catch(e){$('#view').innerHTML='<div class="empty">Error</div>';return;}
  if(S.view!=='clientes')return;
  const totalVentas=cs.reduce((a,c)=>a+c.total,0);
  const conCompra=cs.filter(c=>c.purchase_count>0).length;
  $('#view').innerHTML=`
    <div class="stat-grid">
      ${statCard('👥','#1e2748','#a5b4fc','Clientes Totales',cs.length)}
      ${statCard('🛍️','#0e2a1a','#4ade80','Con Compras',conCompra)}
      ${statCard('💵','#0e1b3a','#60a5fa','Ventas Generadas',money(totalVentas))}
      ${statCard('📦','#221047','#c4b5fd','Registros',cs.length)}
    </div>
    <div class="card">
      <div class="card-h">Registros de Clientes <input class="search" style="width:240px" placeholder="Buscar..." oninput="filterTbl(this.value)"></div>
      <div class="tbl-wrap"><table id="ctbl">
        <thead><tr><th>Nombre</th><th>Teléfono</th><th>Cédula</th><th>Correo</th><th>Ciudad</th><th>Última compra</th><th>Productos</th><th>Estado</th><th>Total</th><th></th></tr></thead>
        <tbody>${cs.map(rowCustomer).join('')||'<tr><td colspan=10 class="empty">Sin clientes aún</td></tr>'}</tbody>
      </table></div>
    </div>
    <div class="card" style="border:1px solid #7f1d1d;margin-top:18px">
      <div class="card-h" style="color:#f87171">⚠️ Zona de peligro — borrado de datos</div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:12px;line-height:1.55">Estas acciones son <b>irreversibles</b> y piden una clave de seguridad. Borran datos reales, no la configuración (cuentas, catálogo, entrenamiento se conservan).</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="qbtn" style="color:#f87171;border-color:#7f1d1d" onclick="resetAll()">🗑️ Borrar TODOS los clientes y ventas</button>
        <button class="qbtn" onclick="clearCat('cupones')">Borrar cupones</button>
      </div>
      <p style="color:var(--muted2);font-size:11px;margin-top:10px">🔒 Los comprobantes de pago NUNCA se pueden borrar (quedan archivados de forma permanente).</p>
    </div>`;
  S._customers=cs;
}
function _askResetPass(){return prompt('🔒 Ingresa la clave de seguridad para borrar:');}
async function delCustomer(phone,name){
  if(!confirm('¿Borrar a "'+name+'" y TODOS sus datos (conversación, pedidos, comprobantes)? Esto no se puede deshacer.'))return;
  const password=_askResetPass();if(!password)return;
  try{await api('/api/reset/customer',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({phone,password})});
    toast('✅ Cliente borrado');renderClientes();}
  catch(e){toast('Error: '+e.message);}
}
async function resetAll(){
  if(!confirm('⚠️ Vas a borrar TODOS los clientes y TODAS las ventas. ¿Continuar?'))return;
  const password=_askResetPass();if(!password)return;
  try{const r=await api('/api/reset/all',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({password})});
    toast('✅ Datos borrados');renderClientes();}
  catch(e){toast('Error: '+e.message);}
}
async function clearCat(category){
  if(!confirm('¿Borrar toda la información de "'+category+'"?'))return;
  const password=_askResetPass();if(!password)return;
  try{const r=await api('/api/reset/category',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({category,password})});
    toast('✅ Borrado: '+r.deleted+' registros');}
  catch(e){toast('Error: '+e.message);}
}
function estadoPill(e){const m={'Recurrente':'g','Nuevo':'p','Sin compra':'closed'};return `<span class="pill ${m[e]||'closed'}">${e}</span>`;}
function rowCustomer(c){return `<tr data-s="${(c.name+' '+c.phone_number+' '+c.cedula+' '+c.email+' '+(c.city||'')).toLowerCase()}">
  <td><b>${c.name}</b></td><td>+${c.phone_number}</td><td>${c.cedula}</td><td>${c.email}</td><td>${c.city||'—'}</td>
  <td>${c.last_purchase}</td><td><span class="prod-pill">${c.product_count} prod.</span></td><td>${estadoPill(c.estado||'Sin compra')}</td><td><b>${money(c.total)}</b></td>
  <td style="white-space:nowrap"><button class="qbtn" style="padding:5px 9px" onclick="viewCustomerOrders('${c.phone_number}','${(c.name||'').replace(/'/g,'')}')">👁️ Ver</button>
  <button class="qbtn" style="padding:5px 9px;color:#f87171;border-color:#7f1d1d" onclick="delCustomer('${c.phone_number}','${(c.name||'').replace(/'/g,'')}')">🗑️</button></td></tr>`;}
function filterTbl(q){q=q.toLowerCase();document.querySelectorAll('#ctbl tbody tr').forEach(tr=>{tr.style.display=tr.dataset.s.includes(q)?'':'none';});}
async function viewCustomerOrders(phone,name){
  let orders=[];try{orders=await api('/api/customers/'+phone+'/orders');}catch(e){toast('Error');return;}
  const cust=(S._customers||[]).find(c=>c.phone_number===phone)||{name,phone_number:phone};
  S._viewCust={cust,orders};
  const copyBar=`
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <button class="qbtn" onclick="copyCustomer('full')">📋 Copiar datos completos</button>
      <button class="qbtn" onclick="copyCustomer('basic')">📋 Copiar datos básicos</button>
    </div>
    <p style="font-size:11px;color:var(--muted2);margin:-6px 0 12px">Completos: nombre, número, cédula, correo, dirección y ciudad. Básicos: nombre, número, dirección y ciudad (elige un pedido abajo para agregarlo).</p>`;
  const ordersHtml=orders.length?orders.map((o,i)=>`
    <div style="border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:6px">
        <span>${o.date} · ${o.payment_method||'—'}</span>
        <span>${o.status==='paid'?(o.payment_received?'✅ Pagado':'🟡 Venta'):'⏳ Pendiente'}</span></div>
      ${o.items.map(it=>`<div style="font-size:13px">• ${it.name} <b>x${it.quantity}</b></div>`).join('')||'<div style="font-size:13px;color:var(--muted)">Sin items</div>'}
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
        <button class="qbtn" style="padding:5px 9px;font-size:11.5px" onclick="copyCustomer('basic',${i})">📋 Copiar datos + este pedido</button>
        <span style="font-weight:700">${money(o.total)}</span>
      </div>
    </div>`).join(''):'<div class="empty">Este cliente aún no tiene pedidos registrados</div>';
  showInfoModal('🛍️ Compras de '+name, copyBar+ordersHtml);
}
function _fmtCustomer(mode,orderIdx){
  const v=S._viewCust;if(!v)return'';
  const c=v.cust,dash=x=>(x&&x!=='—')?x:'';
  const dirCiudad=[dash(c.address),dash(c.city)].filter(Boolean).join(', ');
  let L=[];
  L.push('Nombre: '+(dash(c.name)||'—'));
  L.push('Número: +'+c.phone_number);
  if(mode==='full'){
    L.push('Cédula: '+(dash(c.cedula)||'—'));
    L.push('Correo: '+(dash(c.email)||'—'));
  }
  L.push('Dirección: '+(dirCiudad||'—'));
  if(orderIdx!=null&&v.orders[orderIdx]){
    const o=v.orders[orderIdx];
    L.push('');L.push('Pedido ('+o.date+'):');
    o.items.forEach(it=>L.push('- '+it.name+' x'+it.quantity));
    L.push('Total: '+money(o.total)+(o.payment_method?(' · '+o.payment_method):''));
  }
  return L.join('\n');
}
function copyCustomer(mode,orderIdx){copyToClipboard(_fmtCustomer(mode,orderIdx),'Datos copiados');}
function copyToClipboard(text,okMsg){
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(()=>toast('✅ '+(okMsg||'Copiado'))).catch(()=>_fallbackCopy(text,okMsg));
  }else{_fallbackCopy(text,okMsg);}
}
function _fallbackCopy(text,okMsg){
  try{const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();toast('✅ '+(okMsg||'Copiado'));}
  catch(e){toast('No se pudo copiar');}
}
function showInfoModal(title,html){
  let m=$('#info-modal');
  if(!m){m=document.createElement('div');m.id='info-modal';m.className='modal';m.innerHTML='<div class="modal-box" style="max-width:480px"><h3 id="im-title"></h3><div id="im-body" style="max-height:60vh;overflow-y:auto"></div><div class="mbtns" style="margin-top:14px"><button class="no" onclick="closeModal(\'info-modal\')">Cerrar</button></div></div>';document.body.appendChild(m);}
  $('#im-title').textContent=title;$('#im-body').innerHTML=html;m.classList.add('open');
}

/* ─── EXCEL ─── */
function renderExcel(){
  $('#view').innerHTML=`<div class="card" style="max-width:520px"><div class="card-h">📊 Reporte de Clientes</div>
    <p style="color:var(--muted);font-size:14px;line-height:1.6;margin-bottom:18px">Descarga un Excel con toda la información de clientes e historial de compras. También se envía a tu correo de notificaciones.</p>
    <button class="act-btn p" style="justify-content:center" onclick="downloadExcel()">📥 Descargar Excel</button></div>`;
}
async function downloadExcel(){
  toast('Generando Excel…');
  try{const r=await fetch(API+'/api/customers/export?token='+TOKEN);if(!r.ok)throw new Error('Error');
    const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');
    a.href=url;a.download='clientes_'+new Date().toISOString().slice(0,10)+'.xlsx';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
    toast('✅ Excel descargado');}catch(e){toast('Error descargando Excel');}
}

/* ─── CAMPAÑAS ─── */
async function renderCampanas(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let aud={},promo={};try{[aud,promo]=await Promise.all([api('/api/campaign/audiences'),api('/api/promo-config')]);}catch(e){}
  if(S.view!=='campanas')return;
  const segOpts=[['all','Todos los clientes'],['con_compra','Con compra'],['sin_compra','Sin compra'],['recurrentes','Recurrentes']];
  $('#view').innerHTML=`
    <div class="card" style="max-width:680px">
      <div class="card-h">📣 Nueva campaña</div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Canal</div>
        <select id="cm-channel" class="search" style="width:280px" onchange="updAud()">
          <option value="email">✉️ Email</option>
          <option value="whatsapp">💬 WhatsApp (texto, solo dentro de 24h)</option>
          <option value="whatsapp_template">📄 WhatsApp Plantilla (llega siempre)</option>
        </select></div>
      <div id="cm-tpl-wrap" style="margin-bottom:12px;display:none"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Nombre de la plantilla aprobada de Meta</div>
        <input class="search" id="cm-tpl" style="width:100%" value="${(promo.template_name||'').replace(/"/g,'&quot;')}" placeholder="Ej: promo_novedades"
        <p style="font-size:11px;color:var(--muted);margin-top:6px">La variable {{1}} de la plantilla se reemplaza con el nombre del cliente (en negrilla). Edita el texto de promoción en ⚙️ Configuración.</p></div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Audiencia</div>
        <select id="cm-seg" class="search" style="width:280px" onchange="updAud()">
          ${segOpts.map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}
        </select>
        <div id="cm-count" style="font-size:12px;color:var(--muted);margin-top:6px"></div></div>
      <div id="cm-subj-wrap" style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Asunto (email)</div>
        <input class="search" id="cm-subj" style="width:100%" placeholder="Tenemos novedades para ti 🌿"></div>
      <div style="margin-bottom:14px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Mensaje (puedes usar {nombre})</div>
        <textarea class="cinput" id="cm-body" rows="5" style="width:100%;border-radius:10px">${(promo.message||'').replace(/</g,'&lt;')}</textarea></div>
      <button class="act-btn p" style="max-width:240px;justify-content:center" onclick="sendCampaign()">Enviar campaña</button>
      <p style="color:var(--muted2);font-size:11.5px;margin-top:14px;line-height:1.5">
        ⚠️ WhatsApp solo entrega mensajes a clientes que te escribieron en las últimas 24h, salvo que uses
        plantillas aprobadas por Meta. Email no tiene esa restricción.</p>
    </div>`;
  S._aud=aud;updAud();
}
function updAud(){
  const seg=$('#cm-seg').value,ch=$('#cm-channel').value,a=(S._aud||{})[seg]||{total:0,con_email:0};
  $('#cm-count').textContent=ch==='email'?`${a.con_email} clientes con email`:`${a.total} clientes`;
  $('#cm-subj-wrap').style.display=ch==='email'?'block':'none';
  $('#cm-tpl-wrap').style.display=ch==='whatsapp_template'?'block':'none';
}
async function sendCampaign(){
  const channel=$('#cm-channel').value,segment=$('#cm-seg').value,subject=$('#cm-subj').value,body=$('#cm-body').value.trim();
  const template_name=($('#cm-tpl')?$('#cm-tpl').value.trim():'');
  if(channel==='whatsapp_template'){ if(!template_name){toast('Escribe el nombre de la plantilla');return;} }
  else if(!body){toast('Escribe el mensaje');return;}
  if(!confirm('¿Enviar esta campaña ahora?'))return;
  toast('Enviando campaña…');
  try{const r=await api('/api/campaign/send',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({channel,segment,subject,body,template_name})});
    if(r.failed&&r.error){alert(`Enviados: ${r.sent}\nFallidos: ${r.failed}\n\nMotivo: ${r.error}`);}
    toast(`✅ Enviados: ${r.sent}`+(r.failed?` · Fallidos: ${r.failed}`:''));}
  catch(e){toast('Error: '+e.message);}
}

/* ─── GUÍAS DE TRANSPORTADORAS ─── */
// Página de rastreo por transportadora ({G} = número de guía si la soporta en la URL)
/* ─── MÁS VENDIDOS ─── */
async function renderTopProducts(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  const per=S.tpPeriod||'all';
  const custom=(S.tpStart&&S.tpEnd);
  const url=custom?('/api/top-products?start='+S.tpStart+'&end='+S.tpEnd):('/api/top-products?period='+per);
  let d;try{d=await api(url);}catch(e){$('#view').innerHTML='<div class="empty">Error</div>';return;}
  if(S.view!=='masvendidos')return;
  const periodOpts=[['day','Hoy'],['week','Semana'],['month','Mes'],['year','Año'],['all','Todo']];
  const maxU=Math.max(...d.products.map(p=>p.units),1);
  const colors=['#7c3aed','#3b82f6','#22c55e','#f59e0b','#ec4899','#06b6d4','#a855f7','#10b981'];
  const bars=d.products.length?d.products.map((p,i)=>`
    <div style="margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
        <span style="font-weight:600">${i+1}. ${p.name}</span>
        <span style="color:var(--muted)"><b>${p.units}</b> uds · ${money(p.revenue)}</span>
      </div>
      <div style="background:var(--inp);border-radius:8px;height:22px;overflow:hidden">
        <div style="height:100%;width:${Math.round(p.units/maxU*100)}%;background:${colors[i%colors.length]};border-radius:8px;min-width:6px"></div>
      </div>
      <div style="font-size:11px;color:var(--muted2);margin-top:3px">
        ${p.orders} pedido(s)${p.top_customers.length?' · Top: '+p.top_customers.map(c=>`${c.name} (${c.units})`).join(', '):''}
      </div>
    </div>`).join(''):'<div class="empty" style="padding:30px">Aún no hay ventas en este período</div>';
  $('#view').innerHTML=`
    <div class="period-bar" style="display:flex;justify-content:flex-end;align-items:center;margin-bottom:14px;gap:6px;flex-wrap:wrap">
      ${periodOpts.map(([v,l])=>`<button class="fbtn ${(!custom&&per===v)?'active':''}" onclick="tpSetPeriod('${v}')">${l}</button>`).join('')}
      <span style="width:1px;height:22px;background:var(--border);margin:0 4px"></span>
      <input type="date" id="tp-start" value="${S.tpStart||''}" class="fbtn" style="padding:6px 8px">
      <span style="color:var(--muted);font-size:12px">a</span>
      <input type="date" id="tp-end" value="${S.tpEnd||''}" class="fbtn" style="padding:6px 8px">
      <button class="fbtn ${custom?'active':''}" onclick="tpApplyRange()">📅 Aplicar</button>
      ${custom?`<button class="fbtn" onclick="tpSetPeriod('all')">✕</button>`:''}
    </div>
    <div class="stat-grid" style="grid-template-columns:repeat(3,1fr)">
      ${statCard('📦','#221047','#c4b5fd','Unidades vendidas',d.total_units)}
      ${statCard('🛒','#1e2748','#a5b4fc','Pedidos',d.total_orders)}
      ${statCard('💵','#0e2a1a','#4ade80','Ingresos',money(d.total_revenue))}
    </div>
    <div class="card">
      <div class="card-h">🏆 Ranking de productos</div>
      ${bars}
    </div>`;
}
function tpSetPeriod(p){S.tpPeriod=p;S.tpStart=null;S.tpEnd=null;renderTopProducts();}
function tpApplyRange(){
  const s=$('#tp-start').value,e=$('#tp-end').value;
  if(!s||!e){toast('Elige fecha de inicio y fin');return;}
  if(s>e){toast('La fecha inicial no puede ser mayor que la final');return;}
  S.tpStart=s;S.tpEnd=e;renderTopProducts();
}

/* ─── MULTIMEDIA ─── */
async function renderMultimedia(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let media=[];try{media=await api('/api/product-media');}catch(e){}
  if(S.view!=='multimedia')return;
  const conFoto=media.filter(m=>m.has_image_file).length;
  const conVideo=media.filter(m=>m.has_video_file).length;
  $('#view').innerHTML=`
    <div class="stat-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:16px">
      ${statCard('🛍️','#221047','#c4b5fd','Productos',media.length)}
      ${statCard('📷','#0e2a1a','#4ade80','Con foto',conFoto)}
      ${statCard('🎬','#1e2748','#a5b4fc','Con video',conVideo)}
    </div>
    <div class="card" style="max-width:820px">
      <div class="card-h">📸 Fotos y videos por producto <button class="qbtn" onclick="saveMedia()">💾 Guardar links</button></div>
      <p style="color:var(--muted);font-size:13px;margin-bottom:10px">Sube la <b>foto</b> (JPG/PNG) y el <b>video</b> (MP4) de cada producto. El bot envía la foto cuando el cliente pregunta por el producto y el video cuando pregunta cómo se usa. En el chat (modo Humano) también puedes enviarlas con el botón 🛍️ Producto. Se guardan en el sistema, por eso llegan siempre sin fallar.</p>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px;padding:10px;border:1px solid var(--border);border-radius:10px;background:var(--bg2,transparent)">
        <span style="font-size:12px;color:var(--muted)">📱 Número para probar envíos:</span>
        <input id="mm-test-phone" class="search" style="flex:1;max-width:220px" placeholder="Ej: 573001234567">
      </div>
      <div id="media-list">${media.length?media.map(mediaRow).join(''):'<div class="empty" style="padding:30px">No hay productos en el catálogo</div>'}</div>
    </div>`;
}

/* ─── SEGMENTACIÓN ─── */
async function renderSegmentos(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let d;try{d=await api('/api/segments');}catch(e){$('#view').innerHTML='<div class="empty">Error</div>';return;}
  if(S.view!=='segmentos')return;
  const meta={oncologico:{t:'🎗️ Oncológico',c:'#ec4899',bg:'#2a0f1e',d:'En tratamiento oncológico / quimio / radioterapia'},
              sensible:{t:'🌿 Piel sensible',c:'#4ade80',bg:'#0e2a1a',d:'Piel reactiva, alérgica, dermatitis, irritación'},
              diario:{t:'💧 Cuidado diario',c:'#a5b4fc',bg:'#1e2748',d:'Cuidado natural diario, sin condición especial'}};
  const groups=d.groups||{};
  const total=Object.values(groups).reduce((a,g)=>a+g.length,0);
  const cards=Object.keys(meta).map(k=>{
    const list=groups[k]||[];const m=meta[k];
    const rows=list.length?list.map(c=>`
      <div onclick="openConvByPhone('${c.phone_number}')" style="display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;cursor:pointer;border:1px solid var(--border);margin-bottom:7px" onmouseover="this.style.borderColor='${m.c}'" onmouseout="this.style.borderColor='var(--border)'">
        <div class="av" style="width:32px;height:32px;font-size:12px">${initials(c.name||c.phone_number)}</div>
        <div style="flex:1;min-width:0"><div style="font-weight:600;font-size:13px">${c.name||('+'+c.phone_number)}</div>
        <div style="font-size:11px;color:var(--muted2)">${c.city||''} ${c.city?'·':''} +${c.phone_number}</div></div>
      </div>`).join(''):'<div style="color:var(--muted2);font-size:12px;padding:10px">Sin clientes en este grupo aún</div>';
    return `
      <div class="card" style="border-top:3px solid ${m.c}">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <div style="font-weight:700;font-size:15px">${m.t}</div>
          <div style="background:${m.bg};color:${m.c};font-weight:700;border-radius:20px;padding:3px 12px;font-size:13px">${list.length}</div>
        </div>
        <div style="font-size:11.5px;color:var(--muted);margin-bottom:12px">${m.d}</div>
        ${rows}
      </div>`;}).join('');
  $('#view').innerHTML=`
    <p style="color:var(--muted);font-size:13px;margin-bottom:16px">El bot clasifica automáticamente a cada cliente según lo que necesita mientras conversan. ${total} cliente(s) segmentado(s). Toca un cliente para abrir su chat.</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px">${cards}</div>`;
}
function openConvByPhone(phone){
  const c=(S.convs||[]).find(x=>x.phone_number===phone);
  if(c){setActiveNav('chat');location.hash='chat/'+c.id;showView('chat');setTimeout(()=>openConv(c.id),300);}
  else{toast('Abre Conversaciones para ver este chat');}
}

/* ─── RESPUESTAS RÁPIDAS ─── */
async function renderRespuestas(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let items=[];try{items=await api('/api/quick-replies');}catch(e){}
  if(S.view!=='respuestas')return;
  S._qr=items;
  $('#view').innerHTML=`
    <div class="card" style="max-width:760px">
      <div class="card-h">⚡ Respuestas rápidas <button class="qbtn" onclick="addQuickReply()">+ Agregar</button></div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:14px">Crea plantillas de texto para responder más rápido en modo Humano. Aparecen en el chat con el botón ⚡ para insertarlas con un toque (puedes editarlas antes de enviar).</p>
      <div id="qr-list">${items.length?items.map(qrRow).join(''):'<div class="empty" style="padding:30px">Aún no tienes respuestas rápidas. Crea la primera con “+ Agregar”.</div>'}</div>
      <button class="act-btn p" style="max-width:200px;justify-content:center;margin-top:6px" onclick="saveQuickReplies()">💾 Guardar</button>
    </div>`;
}
function qrRow(it,i){return `
  <div class="qr-item" style="border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:10px">
    <div style="display:flex;gap:8px;margin-bottom:8px">
      <input class="search qr-title" style="flex:1" value="${(it.title||'').replace(/"/g,'&quot;')}" placeholder="Título (ej: Saludo, Datos de envío)">
      <button class="qbtn" style="color:#f87171" onclick="this.closest('.qr-item').remove()">🗑️</button>
    </div>
    <textarea class="cinput qr-text" rows="2" style="width:100%;border-radius:10px">${(it.text||'').replace(/</g,'&lt;')}</textarea>
  </div>`;}
function addQuickReply(){
  const list=$('#qr-list');
  if(list.querySelector('.empty'))list.innerHTML='';
  const div=document.createElement('div');div.innerHTML=qrRow({title:'',text:''});
  list.appendChild(div.firstElementChild);
}
async function saveQuickReplies(){
  const items=[...document.querySelectorAll('.qr-item')].map(el=>({
    title:el.querySelector('.qr-title').value.trim(),
    text:el.querySelector('.qr-text').value.trim()
  })).filter(x=>x.title&&x.text);
  try{await api('/api/quick-replies',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({items})});
    S._qr=items;toast('✅ Respuestas guardadas');}
  catch(e){toast('Error: '+e.message);}
}

/* ─── COMPROBANTES ─── */
async function renderComprobantes(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let rs=[];try{rs=await api('/api/receipts');}catch(e){$('#view').innerHTML='<div class="empty">Error</div>';return;}
  if(S.view!=='comprobantes')return;
  const validos=rs.filter(r=>r.is_valid).length;
  const cards=rs.length?rs.map(r=>`
    <div class="card" style="padding:12px;animation:fadeUp .3s ease both">
      <div style="display:flex;justify-content:space-between;align-items:start;gap:8px;margin-bottom:8px">
        <div><div style="font-weight:700;font-size:13.5px">${r.customer_name}</div>
          <div style="font-size:11px;color:var(--muted)">+${r.customer_phone||'—'}</div></div>
        <span class="pill ${r.is_valid?'human':'wait'}">${r.is_valid?'✅ Válido':'🕵️ Revisar'}</span>
      </div>
      ${r.image?`<img src="${r.image}" style="width:100%;border-radius:9px;border:1px solid var(--border);cursor:pointer;max-height:260px;object-fit:cover" onclick="showInfoModal('Comprobante de '+'${r.customer_name.replace(/'/g,'')}','<img src=\\''+this.src+'\\' style=\\'width:100%\\'>')">`:'<div class="empty" style="padding:20px">Sin imagen</div>'}
      <div style="font-size:11.5px;color:var(--muted);margin-top:8px;line-height:1.6">
        🏦 ${r.bank} · 💵 ${r.amount?money(r.amount):'—'}<br>
        📅 ${r.receipt_date} · 🔖 ${r.reference}<br>
        <span style="color:var(--muted2)">Recibido: ${new Date(r.created_at).toLocaleString('es-CO')}</span>
      </div>
    </div>`).join(''):'';
  $('#view').innerHTML=`
    <div class="stat-grid" style="grid-template-columns:repeat(3,1fr)">
      ${statCard('🧾','#1e2748','#a5b4fc','Comprobantes',rs.length)}
      ${statCard('✅','#0e2a1a','#4ade80','Válidos',validos)}
      ${statCard('📥','#221047','#c4b5fd','Descargar','ZIP')}
    </div>
    <div class="card" style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
      <div style="font-size:13px;color:var(--muted)">🔒 Archivo permanente. Los comprobantes no se pueden borrar. Puedes descargarlos todos organizados por fecha y cliente.</div>
      <button class="act-btn p" style="max-width:230px;justify-content:center" onclick="downloadReceipts()">📥 Descargar todos (ZIP)</button>
    </div>
    ${rs.length?`<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px">${cards}</div>`:'<div class="empty"><div class="ico">🧾</div>Aún no hay comprobantes recibidos</div>'}`;
}
async function downloadReceipts(){
  toast('Generando ZIP…');
  try{const r=await fetch(API+'/api/receipts/download?token='+TOKEN);if(!r.ok)throw new Error('Error');
    const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');
    a.href=url;a.download='comprobantes_vita_qualitat_'+new Date().toISOString().slice(0,10)+'.zip';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
    toast('✅ Descargado');}
  catch(e){toast('Error al descargar');}
}

/* ─── AYUDA ─── */
function renderAyuda(){
  if(S.view!=='ayuda')return;
  if(!S.help)S.help=[];
  const item=(t,d)=>`<div style="padding:12px 0;border-bottom:1px solid var(--border)"><div style="font-weight:700;font-size:14px;margin-bottom:4px">${t}</div><div style="font-size:13px;color:var(--muted);line-height:1.6">${d}</div></div>`;
  $('#view').innerHTML=`
    <div class="card" style="max-width:820px;margin-bottom:18px;border:1px solid var(--pri)">
      <div class="card-h">🧪 Chat de prueba con TU bot</div>
      <p style="font-size:12.5px;color:var(--muted);margin-bottom:12px">Prueba el bot exactamente como lo verá un cliente real (usa tu catálogo y tu Entrenamiento actual), sin gastar mensajes de WhatsApp ni tocar tus datos reales.</p>
      <div id="test-chat-msgs" style="background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:14px;height:320px;overflow-y:auto;display:flex;flex-direction:column;gap:10px"></div>
      <div style="display:flex;gap:8px;margin-top:12px">
        <input class="search" id="test-chat-input" style="flex:1" placeholder="Escribe como si fueras un cliente…" onkeydown="if(event.key==='Enter')testChatSend()">
        <button class="act-btn p" style="max-width:120px;justify-content:center" onclick="testChatSend()">Enviar</button>
        <button class="qbtn" onclick="testChatReset()">🔄 Reiniciar</button>
      </div>
    </div>
    <div class="card" style="max-width:820px;margin-bottom:18px">
      <div class="card-h">🤖 Asistente de ayuda <span style="font-size:11px;color:var(--muted);font-weight:400">· resuelve tus dudas sobre el panel</span></div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:10px">Pregúntame cómo usar cualquier parte del sistema. Soy independiente del bot que atiende a tus clientes. 🌿</p>
      <div id="help-msgs" style="background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:14px;height:320px;overflow-y:auto;display:flex;flex-direction:column;gap:10px"></div>
      <div style="display:flex;gap:8px;margin-top:12px">
        <input class="search" id="help-input" style="flex:1" placeholder="Escribe tu duda… (ej: ¿cómo cargo la foto de un producto?)" onkeydown="if(event.key==='Enter')helpSend()">
        <button class="act-btn p" style="max-width:120px;justify-content:center" onclick="helpSend()">Enviar</button>
      </div>
      <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
        ${['¿Cómo cargo la foto de un producto?','¿Cómo conecto la plantilla de postventa?','¿Cómo veo qué compró un cliente?','¿Cómo borro los datos de prueba?'].map(q=>`<button onclick="helpQuick(this.textContent)" style="background:var(--bg);border:1px solid var(--border);color:var(--muted);font-size:11px;padding:6px 10px;border-radius:14px;cursor:pointer">${q}</button>`).join('')}
      </div>
    </div>
    <div class="card" style="max-width:820px">
      <div class="card-h">❓ Guía de uso del panel</div>
      ${item('🏠 Dashboard','Resumen en vivo: conversaciones, ventas del día/mes, ticket promedio, clientes nuevos y recurrentes, conversión de la IA. Se actualiza solo.')}
      ${item('💬 Conversaciones (Chat en vivo)','Lista de chats con filtros (Todas, No leídas, IA, Humanas). Abre un chat para ver los mensajes. Con el botón <b>IA / Humano</b> tomas el control o se lo devuelves al bot. En modo Humano puedes escribir, enviar imágenes, productos guardados, audios, QR de pago y plantillas. A la derecha ves los datos del cliente, sus etiquetas y acciones rápidas.')}
      ${item('🗄️ Datos de Clientes','Todos los clientes con cédula, correo, dirección, última compra, total gastado y # de compras. El botón <b>👁️ Ver</b> muestra qué productos y cuántas unidades ha comprado cada cliente. Botón <b>Exportar a Excel</b> arriba.')}
      ${item('🏷️ Etiquetas','Clasifica clientes (VIP, recurrente, etc). Se agregan desde el panel derecho de cada chat.')}
      ${item('📣 Campañas','Envía mensajes masivos por <b>email</b> o <b>WhatsApp</b> a un segmento (todos, con compra, sin compra, recurrentes). WhatsApp solo entrega a clientes que escribieron en las últimas 24h, salvo plantillas aprobadas por Meta.')}
      ${item('⚙️ Configuración','Cuentas de pago, cupones y descuentos, precios y stock de productos, fotos y videos de cada producto, postventa y reseñas, y respuestas de voz (ElevenLabs).')}
      ${item('📱 Usar el panel en el celular','Abre este mismo link en el navegador del celular (Chrome en Android, Safari en iPhone). Para tenerlo como app: <b>Android</b> → menú ⋮ → "Agregar a pantalla de inicio". <b>iPhone</b> → botón Compartir ⬆️ → "Agregar a inicio".')}
    </div>`;
  helpRender();
  testChatRender();
}
if(!window.S)window.S={};
async function testChatSend(){
  const inp=$('#test-chat-input');const text=inp.value.trim();if(!text)return;
  if(!S.testChat)S.testChat=[];
  S.testChat.push({role:'user',content:text});inp.value='';testChatRender();
  S.testChat.push({role:'assistant',content:'…'});testChatRender();
  try{const r=await api('/api/test-chat',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({messages:S.testChat.slice(0,-1)})});
    S.testChat[S.testChat.length-1]={role:'assistant',content:r.reply||'(sin respuesta)'};
  }catch(e){S.testChat[S.testChat.length-1]={role:'assistant',content:'⚠️ No pude responder: '+e.message};}
  testChatRender();
}
function testChatReset(){S.testChat=[];testChatRender();}
function testChatRender(){
  const box=$('#test-chat-msgs');if(!box)return;
  if(!S.testChat)S.testChat=[];
  box.innerHTML=S.testChat.map(m=>`<div style="align-self:${m.role==='user'?'flex-end':'flex-start'};max-width:80%;background:${m.role==='user'?'var(--pri)':'var(--panel2)'};color:${m.role==='user'?'#fff':'var(--text)'};padding:8px 12px;border-radius:10px;font-size:13px;white-space:pre-wrap">${m.content}</div>`).join('')||'<div style="color:var(--muted2);font-size:12px">Escribe abajo como si fueras un cliente para probar el bot.</div>';
  box.scrollTop=box.scrollHeight;
}
function helpRender(){
  const box=$('#help-msgs');if(!box)return;
  if(!S.help.length){box.innerHTML='<div style="margin:auto;color:var(--muted);font-size:12px;text-align:center">👋 Hola, soy tu asistente del panel.<br>Hazme cualquier pregunta sobre cómo usar el sistema.</div>';return;}
  box.innerHTML=S.help.map(m=>{
    const mine=m.role==='user';
    return `<div style="align-self:${mine?'flex-end':'flex-start'};max-width:80%;background:${mine?'var(--pri)':'var(--card)'};color:${mine?'#fff':'var(--text)'};border:1px solid var(--border);padding:9px 12px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap">${(m.content||'').replace(/</g,'&lt;')}</div>`;
  }).join('');
  box.scrollTop=box.scrollHeight;
}
function helpQuick(q){$('#help-input').value=q;helpSend();}
async function helpSend(){
  const inp=$('#help-input');if(!inp)return;
  const text=inp.value.trim();if(!text)return;
  inp.value='';
  S.help.push({role:'user',content:text});
  S.help.push({role:'assistant',content:'…'});
  helpRender();
  try{
    const msgs=S.help.filter(m=>m.content!=='…');
    const r=await api('/api/help-chat',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({messages:msgs})});
    S.help[S.help.length-1]={role:'assistant',content:r.reply||'(sin respuesta)'};
  }catch(e){S.help[S.help.length-1]={role:'assistant',content:'⚠️ No pude responder en este momento. Intenta de nuevo.'};}
  helpRender();
}

/* ─── CONFIG ─── */
async function renderConfig(){
  $('#view').innerHTML='<div class="empty">Cargando…</div>';
  let media=[],pv={},cat=[],voice={},pay={},coupons=[],promo={},train={},botn={};
  let paused={paused:false},notif={},binfo={fields:{},values:{}};
  try{[media,pv,cat,voice,pay,coupons,promo,train,botn,paused,notif,binfo]=await Promise.all([api('/api/product-media'),api('/api/postventa-config'),api('/api/catalog'),api('/api/voice-config'),api('/api/payment-config'),api('/api/coupons'),api('/api/promo-config'),api('/api/training-config'),api('/api/bot-name'),api('/api/bot-paused'),api('/api/notif-config'),api('/api/business-info')]);}catch(e){}
  if(S.view!=='config')return;
  S._pay=pay;
  const themes=[['dark','Azul oscuro','#0b1020','#7c3aed'],['light','Claro','#eef1f7','#6d28d9'],['black','Negro','#000000','#8b5cf6'],['green','Verde','#07130d','#22c55e']];
  const ct=currentTheme();
  const isP=!!(paused&&paused.paused);
  $('#view').innerHTML=`
    <div class="card" style="max-width:760px;margin-bottom:18px;border:1px solid ${isP?'#f59e0b':'var(--border)'}">
      <div class="card-h">${isP?'⏸️':'▶️'} Estado del bot</div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:12px">Cuando pausas el bot, deja de responder automáticamente a los clientes (tú atiendes a mano desde el chat). Vuelve a activarlo cuando quieras, desde el PC o el celular.</p>
      <div style="display:flex;align-items:center;gap:12px">
        <button class="act-btn ${isP?'p':'r'}" style="max-width:280px;justify-content:center" onclick="toggleBotPaused(${isP})">${isP?'▶️ Activar el bot':'⏸️ Pausar el bot'}</button>
        <span style="font-size:13px;font-weight:700;color:${isP?'#f59e0b':'var(--green)'}">${isP?'PAUSADO (respondes tú)':'ACTIVO (responde solo)'}</span>
      </div>
    </div>
    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🔔 Notificaciones <button class="qbtn" onclick="saveNotif()">💾 Guardar</button></div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:12px">Recibe un aviso cuando pasa algo importante. El <b>email</b> es el canal seguro. El <b>WhatsApp</b> es opcional (para que llegue, ese número debe haberle escrito al bot en las últimas 24h).</p>
      <div style="margin-bottom:10px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Email(s) para avisos (separa con coma)</div>
        <input class="search" id="nf-email" style="width:100%" value="${(notif.email||'').replace(/"/g,'&quot;')}" placeholder="tucorreo@gmail.com"></div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">WhatsApp(s) para avisos (con indicativo, ej: 573001234567)</div>
        <input class="search" id="nf-wa" style="width:100%" value="${(notif.whatsapp||'').replace(/"/g,'&quot;')}" placeholder="573001234567"></div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <label style="display:flex;align-items:center;gap:9px;font-size:13px"><input type="checkbox" id="nf-new" ${notif.new_client?'checked':''} style="width:17px;height:17px;accent-color:var(--pri)"> Cuando un cliente <b>NUEVO</b> escribe (inicia conversación)</label>
        <label style="display:flex;align-items:center;gap:9px;font-size:13px"><input type="checkbox" id="nf-ret" ${notif.returning?'checked':''} style="width:17px;height:17px;accent-color:var(--pri)"> Cuando un cliente que <b>ya escribió/compró</b> vuelve a escribir</label>
        <label style="display:flex;align-items:center;gap:9px;font-size:13px"><input type="checkbox" id="nf-sale" ${notif.sale?'checked':''} style="width:17px;height:17px;accent-color:var(--pri)"> Cuando se <b>CIERRA una venta</b> (método de pago, qué compró y a dónde va)</label>
        <label style="display:flex;align-items:center;gap:9px;font-size:13px"><input type="checkbox" id="nf-card" ${notif.card?'checked':''} style="width:17px;height:17px;accent-color:var(--pri)"> Cuando un cliente quiere pagar con <b>tarjeta o PSE</b> (para enviarle el link)</label>
      </div>
      <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border)">
        <div style="font-size:13px;font-weight:700;margin-bottom:4px">🚀 Envío de correo (Resend)</div>
        <p style="color:var(--muted);font-size:12px;margin-bottom:10px;line-height:1.5">El servidor bloquea el correo tradicional (SMTP), así que los avisos se envían por <b>Resend</b> (gratis hasta 3.000 correos/mes). Crea una cuenta gratis en resend.com con este mismo correo, copia tu <b>API key</b> y pégala aquí.</p>
        <div style="max-width:420px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">API key de Resend</div>
          <input class="search" id="nf-resend-key" type="password" style="width:100%" value="${(notif.resend_api_key||'').replace(/"/g,'&quot;')}" placeholder="re_xxxxxxxxxxxxxxxxxxxx"></div>
      </div>
      <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border)">
        <div style="font-size:13px;font-weight:700;margin-bottom:4px">✉️ Correo emisor por SMTP (alterno, no funciona en este servidor)</div>
        <p style="color:var(--muted);font-size:12px;margin-bottom:10px;line-height:1.5">Deja esto solo por si más adelante cambias de servidor. Mientras tengas la API key de Resend arriba, esto no se usa.</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <div style="flex:1;min-width:220px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Correo emisor</div>
            <input class="search" id="nf-smtp-user" style="width:100%" value="${(notif.smtp_user||'').replace(/"/g,'&quot;')}" placeholder="tucorreo@gmail.com"></div>
          <div style="flex:1;min-width:220px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Contraseña de aplicación</div>
            <input class="search" id="nf-smtp-pass" type="password" style="width:100%" value="${(notif.smtp_pass||'').replace(/"/g,'&quot;')}" placeholder="xxxx xxxx xxxx xxxx"></div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
          <div style="flex:1;min-width:220px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Host SMTP (avanzado — déjalo así para Gmail)</div>
            <input class="search" id="nf-smtp-host" style="width:100%" value="${(notif.smtp_host||'').replace(/"/g,'&quot;')}" placeholder="smtp.gmail.com"></div>
          <div style="width:110px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Puerto</div>
            <input class="search" id="nf-smtp-port" style="width:100%" value="${(notif.smtp_port||'').toString().replace(/"/g,'&quot;')}" placeholder="587"></div>
        </div>
        <div style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <button class="qbtn" onclick="testNotif()">📨 Guardar y enviar correo de prueba</button>
          <span id="nf-test-result" style="font-size:12.5px;color:var(--muted)"></span>
        </div>
      </div>
    </div>
    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🎨 Tema del panel</div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:12px">Elige el color del panel. Se guarda en este dispositivo.</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        ${themes.map(([id,label,bg,acc])=>`
          <div onclick="setTheme('${id}')" style="cursor:pointer;border:2px solid ${ct===id?'var(--pri)':'var(--border)'};border-radius:14px;padding:12px;width:130px;background:var(--panel2);transition:border-color .15s">
            <div style="height:46px;border-radius:9px;background:${bg};position:relative;overflow:hidden;border:1px solid var(--border)">
              <div style="position:absolute;left:8px;top:8px;width:30px;height:10px;border-radius:4px;background:${acc}"></div>
              <div style="position:absolute;left:8px;top:24px;width:54px;height:7px;border-radius:4px;background:${acc};opacity:.5"></div>
            </div>
            <div style="font-size:12.5px;font-weight:700;margin-top:8px;display:flex;align-items:center;gap:6px">${ct===id?'✅':''} ${label}</div>
          </div>`).join('')}
      </div>
    </div>
    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🤖 Nombre del bot <button class="qbtn" onclick="saveBotName()">💾 Guardar</button></div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:10px">Así se presentará el bot con tus clientes. Ej: "¡Hola! Soy ${(botn.name||'Asistente')}, de ${COMPANY_NAME} 🌿".</p>
      <input class="search" id="bot-name" style="width:280px" value="${(botn.name||'Asistente').replace(/"/g,'&quot;')}" placeholder="Asistente">
    </div>
    ${Object.keys(binfo.fields||{}).length?`<div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🧩 Información del negocio (${binfo.business_type_label||''}) <button class="qbtn" onclick="saveBusinessInfo()">💾 Guardar</button></div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:12px">Campos sugeridos para tu tipo de negocio. El bot los usa como contexto adicional al conversar.</p>
      <div style="display:flex;flex-direction:column;gap:10px">
        ${Object.entries(binfo.fields).map(([key,label])=>`
        <div><div style="font-size:12px;color:var(--muted);margin-bottom:5px">${label}</div>
          <input class="search bi-field" data-key="${key}" style="width:100%" value="${(binfo.values[key]||'').replace(/"/g,'&quot;')}"></div>`).join('')}
      </div>
    </div>`:''}
    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🎓 Entrenamiento del bot <button class="qbtn" onclick="saveTraining()">💾 Guardar</button></div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:10px;line-height:1.55">Aquí defines la información oficial que el bot usa para presentar los productos: componentes, beneficios, modo de uso y rutina. Tiene prioridad alta. Edítalo cuando quieras afinar lo que el bot responde. 🌿</p>
      <textarea class="cinput" id="train-notes" rows="18" style="width:100%;border-radius:10px;font-size:12.5px;line-height:1.5;font-family:inherit">${(train.notes||'').replace(/</g,'&lt;')}</textarea>
      <p style="font-size:11px;color:var(--muted);margin-top:6px">Consejo: escribe en lenguaje natural, por producto. El bot lo combina con el catálogo y nunca lo recita completo de golpe.</p>
    </div>
    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🏦 Cuentas de pago / Bre-B <button class="qbtn" onclick="savePay()">💾 Guardar</button></div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Titular (nombre que debe aparecer en los comprobantes)</div>
        <input class="search" id="pay-titular" style="width:100%" value="${(pay.titular||'').replace(/"/g,'&quot;')}"></div>
      <div id="pay-list">${(pay.accounts||[]).map(payRow).join('')}</div>
      <button class="qbtn" style="margin-top:8px" onclick="addPayRow()">+ Agregar cuenta</button>
      <p style="color:var(--muted2);font-size:11.5px;margin-top:10px">El bot comparte estas cuentas al cobrar y valida los comprobantes contra el titular y estos datos.</p>
    </div>

    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🎟️ Cupones y descuentos</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-bottom:14px">
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Código</div><input class="search" id="cp-code" style="width:140px" placeholder="VITA10"></div>
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Tipo</div>
          <select class="search" id="cp-kind" style="width:150px"><option value="percent">% descuento</option><option value="fixed">$ fijo (COP)</option><option value="free_shipping">Envío gratis</option></select></div>
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Valor</div><input class="search" id="cp-value" type="number" style="width:110px" placeholder="10"></div>
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Máx. usos (0=∞)</div><input class="search" id="cp-max" type="number" style="width:120px" value="0"></div>
        <button class="act-btn p" style="padding:9px 16px" onclick="createCoupon()">Crear</button>
      </div>
      <div id="coupon-list">${couponsHtml(coupons)}</div>
    </div>

    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">🏷️ Productos y precios <button class="qbtn" onclick="saveCatalog()">💾 Guardar precios/stock</button></div>
      <p style="color:var(--muted);font-size:13px;margin-bottom:14px">Agrega tus productos/servicios y edita precio y disponibilidad. El bot usará estos valores al hablar con los clientes.</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-bottom:14px;padding:12px;border:1px solid var(--border);border-radius:10px">
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">SKU</div><input class="search" id="np-sku" style="width:110px" placeholder="SKU-01"></div>
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Nombre</div><input class="search" id="np-name" style="width:180px" placeholder="Nombre del producto"></div>
        <div><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Precio (COP)</div><input class="search" id="np-price" type="number" style="width:120px" placeholder="50000"></div>
        <div style="flex:1;min-width:160px"><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Descripción</div><input class="search" id="np-desc" style="width:100%" placeholder="Opcional"></div>
        <button class="act-btn p" style="padding:9px 16px" onclick="addProduct()">+ Agregar</button>
      </div>
      <div class="tbl-wrap"><table id="cat-tbl"><thead><tr><th>Producto</th><th>Precio (COP)</th><th>En stock</th><th></th></tr></thead>
        <tbody>${cat.map(catRow).join('')||'<tr><td colspan=4 class="empty">Aún no tienes productos. Agrega el primero arriba.</td></tr>'}</tbody></table></div>
    </div>`+`
    <div class="card" style="max-width:760px;margin-bottom:18px">
      <div class="card-h">📱 QR de pago y Excel</div>
      <p style="color:var(--muted);font-size:13px;margin-bottom:14px">El QR de pago (llave Bre-B), verificación de comprobantes y reporte Excel se gestionan en la página completa.</p>
      <a class="act-btn p" style="justify-content:center;max-width:280px" href="/admin/config?token=${TOKEN}">Abrir configuración de QR →</a>
    </div>

    <div class="card" style="max-width:760px">
      <div class="card-h">💬 Postventa y Reseñas <button class="qbtn" onclick="savePV()">💾 Guardar</button></div>
      <div class="toggle" style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <input type="checkbox" id="pv-enabled" ${pv.enabled?'checked':''} style="width:18px;height:18px;accent-color:var(--pri)">
        <label for="pv-enabled" style="font-size:13px">Activar seguimiento postventa automático</label>
      </div>
      <div class="inf" style="display:block;margin-bottom:12px"><div class="info-label" style="font-size:12px;color:var(--muted);margin-bottom:5px">Días después de la compra para preguntar</div>
        <input class="search" id="pv-days" type="number" value="${pv.days_after||3}" style="width:120px"></div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Mensaje de seguimiento (usa {nombre})</div>
        <textarea class="cinput" id="pv-msg" rows="3" style="width:100%;border-radius:10px">${(pv.message||'').replace(/</g,'&lt;')}</textarea></div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Link para dejar reseña (Google, web, etc.)</div>
        <input class="search" id="pv-link" style="width:100%" value="${pv.review_link||''}" placeholder="https://..."></div>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Incentivo por reseña</div>
        <select id="pv-incentive" class="search" style="width:280px" onchange="togglePVCustom()">
          <option value="ninguno" ${pv.incentive==='ninguno'?'selected':''}>Ninguno (sin beneficio)</option>
          <option value="descuento_7" ${pv.incentive==='descuento_7'?'selected':''}>7% de descuento próxima compra</option>
          <option value="envio_gratis" ${pv.incentive==='envio_gratis'?'selected':''}>Envío gratis próxima compra</option>
          <option value="personalizado" ${pv.incentive==='personalizado'?'selected':''}>Personalizado…</option>
        </select></div>
      <div id="pv-custom-wrap" style="display:${pv.incentive==='personalizado'?'block':'none'}">
        <div style="font-size:12px;color:var(--muted);margin-bottom:5px">Beneficio personalizado (lo que el bot le ofrecerá)</div>
        <input class="search" id="pv-custom" style="width:100%" value="${(pv.incentive_custom||'').replace(/"/g,'&quot;')}" placeholder="Ej: un detalle de regalo en tu próximo pedido">
      </div>
      <div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--bd)">
        <div style="font-size:12px;color:var(--muted);margin-bottom:5px">Plantilla aprobada de Meta (para enviar después de las 24h)</div>
        <input class="search" id="pv-template" style="width:100%" value="${(pv.template_name||'').replace(/"/g,'&quot;')}" placeholder="Ej: retroalimentacion_15dias">
        <p style="font-size:11px;color:var(--muted);margin-top:6px;line-height:1.5">⚠️ Sin plantilla, el mensaje solo llega si el cliente escribió en las últimas 24h. Con plantilla aprobada por Meta, llega siempre. La variable {{1}} de la plantilla se reemplaza con el nombre del cliente (en negrilla).</p>
      </div>
      <div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--bd)">
        <div style="font-size:12px;color:var(--muted);margin-bottom:5px">Plantilla de recordatorio (cuando el cliente dice "vuelvo en X días" y no vuelve)</div>
        <input class="search" id="pv-recon-template" style="width:100%" value="${(pv.recontacto_template||'').replace(/"/g,'&quot;')}" placeholder="Ej: recordatorio_pendiente">
        <p style="font-size:11px;color:var(--muted);margin-top:6px;line-height:1.5">El bot detecta solo cuando un cliente promete volver y agenda el recordatorio. Para que llegue después de 24h necesita una plantilla aprobada (variable {{1}} = nombre).</p>
      </div>
    </div>

    <div class="card" style="max-width:760px;margin-top:18px">
      <div class="card-h">📣 Promoción / Marketing <button class="qbtn" onclick="savePromo()">💾 Guardar</button></div>
      <p style="color:var(--muted);font-size:12.5px;margin-bottom:12px">Mensaje de promoción que se usa en Campañas. Puedes editarlo aquí y se recordará. Usa <b>{nombre}</b> para el nombre del cliente.</p>
      <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Mensaje de promoción (texto libre, dentro de 24h)</div>
        <textarea class="cinput" id="promo-msg" rows="3" style="width:100%;border-radius:10px">${(promo.message||'').replace(/</g,'&lt;')}</textarea></div>
      <div><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Plantilla aprobada de Meta (para enviar después de las 24h)</div>
        <input class="search" id="promo-template" style="width:100%" value="${(promo.template_name||'').replace(/"/g,'&quot;')}" placeholder="Ej: promo_novedades"
        <p style="font-size:11px;color:var(--muted);margin-top:6px;line-height:1.5">El texto de la plantilla está fijo en Meta; aquí defines cuál usar. El mensaje de arriba es el que se envía dentro de las 24h.</p></div>
    </div>

    <div class="card" style="max-width:760px;margin-top:18px">
      <div class="card-h">🎙️ Respuestas de voz (ElevenLabs) <button class="qbtn" onclick="saveVoice()">💾 Guardar</button></div>
      <p style="color:var(--muted);font-size:13px;margin-bottom:8px">Cuando un cliente envía una nota de voz, el bot puede responderle también con voz.
        Estado de la API: <b style="color:${voice.api_key_set?'#4ade80':'#f87171'}">${voice.api_key_set?'Conectada ✓':'Falta ELEVENLABS_API_KEY en Railway'}</b></p>
      <div class="toggle" style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
        <input type="checkbox" id="vc-enabled" ${voice.enabled?'checked':''} style="width:18px;height:18px;accent-color:var(--pri)">
        <label for="vc-enabled" style="font-size:13px">Activar respuestas de voz</label>
      </div>
      <div><div style="font-size:12px;color:var(--muted);margin-bottom:5px">Voice ID de ElevenLabs</div>
        <input class="search" id="vc-voice" style="width:100%" value="${voice.voice_id||''}" placeholder="Ej: 21m00Tcm4TlvDq8ikWAM"></div>
    </div>`;
}
async function saveVoice(){
  const body={enabled:$('#vc-enabled').checked,voice_id:$('#vc-voice').value.trim()};
  try{await api('/api/voice-config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(body)});toast('✅ Voz guardada');}
  catch(e){toast('Error: '+e.message);}
}
function payRow(a){return `
  <div style="display:flex;gap:6px;margin-bottom:6px;align-items:center" class="pay-acc">
    <input class="search pa-bank" style="flex:1" value="${(a.bank||'').replace(/"/g,'&quot;')}" placeholder="Banco">
    <input class="search pa-type" style="width:110px" value="${(a.type||'').replace(/"/g,'&quot;')}" placeholder="Tipo">
    <input class="search pa-num" style="flex:1" value="${(a.number||'').replace(/"/g,'&quot;')}" placeholder="N° cuenta">
    <input class="search pa-breb" style="width:130px" value="${(a.bre_b||'').replace(/"/g,'&quot;')}" placeholder="Llave Bre-B">
    <input type="checkbox" class="pa-en" ${a.enabled!==false?'checked':''} title="Activa" style="width:18px;height:18px;accent-color:var(--pri)">
    <button class="qbtn" onclick="this.parentElement.remove()" style="padding:6px 9px">✕</button>
  </div>`;}
function addPayRow(){$('#pay-list').insertAdjacentHTML('beforeend',payRow({enabled:true}));}
async function savePay(){
  const accounts=[];
  document.querySelectorAll('#pay-list .pay-acc').forEach(r=>{
    accounts.push({bank:r.querySelector('.pa-bank').value.trim(),type:r.querySelector('.pa-type').value.trim(),number:r.querySelector('.pa-num').value.trim(),bre_b:r.querySelector('.pa-breb').value.trim(),enabled:r.querySelector('.pa-en').checked});
  });
  const data={titular:$('#pay-titular').value.trim(),accounts};
  try{await api('/api/payment-config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(data)});toast('✅ Cuentas guardadas');}
  catch(e){toast('Error: '+e.message);}
}
function couponsHtml(cs){if(!cs.length)return '<div style="color:var(--muted2);font-size:12px">Sin cupones</div>';
  const lbl=c=>c.kind==='percent'?c.value+'%':(c.kind==='fixed'?money(c.value):'Envío gratis');
  return cs.map(c=>`<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
    <span class="tag p" style="font-size:12px">${c.code}</span>
    <span style="font-size:13px">${lbl(c)}</span>
    <span style="font-size:11px;color:var(--muted)">usos: ${c.uses}${c.max_uses?'/'+c.max_uses:''}</span>
    <button class="qbtn" style="margin-left:auto;padding:5px 9px" onclick="delCoupon('${c.code}')">🗑️</button>
  </div>`).join('');}
async function createCoupon(){
  const code=$('#cp-code').value.trim();if(!code){toast('Escribe el código');return;}
  const body={code,kind:$('#cp-kind').value,value:parseInt($('#cp-value').value)||0,max_uses:parseInt($('#cp-max').value)||0};
  try{await api('/api/coupons',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(body)});
    const cs=await api('/api/coupons');$('#coupon-list').innerHTML=couponsHtml(cs);$('#cp-code').value='';$('#cp-value').value='';toast('✅ Cupón creado');}
  catch(e){toast('Error: '+e.message);}
}
async function delCoupon(code){
  try{await api('/api/coupons/'+encodeURIComponent(code),{method:'DELETE',headers:{'Authorization':'Bearer '+TOKEN}});
    const cs=await api('/api/coupons');$('#coupon-list').innerHTML=couponsHtml(cs);toast('Cupón eliminado');}
  catch(e){toast('Error: '+e.message);}
}
function catRow(p){return `<tr data-sku="${p.sku}">
  <td><b>${p.name}</b><div style="font-size:11px;color:var(--muted2)">${p.sku}</div></td>
  <td><input class="search ct-price" type="number" value="${p.price_cop}" style="width:130px"></td>
  <td><input type="checkbox" class="ct-stock" ${p.in_stock?'checked':''} style="width:18px;height:18px;accent-color:var(--pri)"></td>
  <td><button class="qbtn" style="padding:5px 9px" onclick="delProduct('${p.sku}')">🗑️</button></td></tr>`;}
async function addProduct(){
  const sku=$('#np-sku').value.trim(),name=$('#np-name').value.trim();
  const price=parseInt($('#np-price').value)||0,description=$('#np-desc').value.trim();
  if(!sku||!name){toast('Pon el SKU y el nombre');return;}
  try{await api('/api/products',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({sku,name,price,description,in_stock:true})});
    toast('✅ Producto agregado');$('#np-sku').value='';$('#np-name').value='';$('#np-price').value='';$('#np-desc').value='';
    renderConfig();}
  catch(e){toast('Error: '+e.message);}
}
async function delProduct(sku){
  if(!confirm('¿Eliminar este producto? También se borrará su foto/video si los tiene.'))return;
  try{await api('/api/products/'+encodeURIComponent(sku),{method:'DELETE',headers:{'Authorization':'Bearer '+TOKEN}});toast('Producto eliminado');renderConfig();}
  catch(e){toast('Error: '+e.message);}
}
async function saveCatalog(){
  const data={};
  document.querySelectorAll('#cat-tbl tbody tr[data-sku]').forEach(tr=>{
    data[tr.dataset.sku]={price_cop:parseInt(tr.querySelector('.ct-price').value)||0,in_stock:tr.querySelector('.ct-stock').checked};
  });
  try{await api('/api/catalog',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(data)});toast('✅ Precios guardados');}
  catch(e){toast('Error: '+e.message);}
}
function mediaRow(m){
  const previews=`<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px">
    ${m.image_preview?`<div style="text-align:center"><img src="${m.image_preview}" style="width:96px;height:96px;object-fit:cover;border-radius:10px;border:1px solid var(--border)"><div style="font-size:10px;color:var(--muted2);margin-top:3px">Foto</div></div>`:''}
    ${m.video_preview?`<div style="text-align:center"><video src="${m.video_preview}" style="width:140px;height:96px;object-fit:cover;border-radius:10px;border:1px solid var(--border);background:#000" controls muted preload="metadata"></video><div style="font-size:10px;color:var(--muted2);margin-top:3px">Video</div></div>`:''}
  </div>`;
  return `
  <div style="border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:10px" data-sku="${m.sku}">
    <div style="font-weight:700;font-size:13px;margin-bottom:8px">${m.name} <span style="color:var(--muted2);font-weight:400">(${m.sku})</span></div>
    ${(m.image_preview||m.video_preview)?previews:''}
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;align-items:center">
      <label class="qbtn" style="cursor:pointer">📷 ${m.has_image_file?'Cambiar':'Subir'} imagen (JPG/PNG)
        <input type="file" accept="image/png,image/jpeg" style="display:none" onchange="uploadMedia('${m.sku}','image',this)"></label>
      <span id="mst-image-${m.sku}" style="font-size:12px;color:${m.has_image_file?'#4ade80':'var(--muted2)'}">${m.has_image_file?'✓ imagen cargada':'sin imagen'}</span>
      <button class="qbtn" id="mdel-image-${m.sku}" style="padding:5px 9px;display:${m.has_image_file?'inline-block':'none'}" onclick="deleteMedia('${m.sku}','image')">🗑️</button>
      ${m.has_image_file?`<button class="qbtn" onclick="testSendMedia('${m.sku}','image')">📤 Enviar prueba</button>`:''}
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px;align-items:center">
      <label class="qbtn" style="cursor:pointer">🎬 ${m.has_video_file?'Cambiar':'Subir'} video (MP4)
        <input type="file" accept="video/mp4" style="display:none" onchange="uploadMedia('${m.sku}','video',this)"></label>
      <span id="mst-video-${m.sku}" style="font-size:12px;color:${m.has_video_file?'#4ade80':'var(--muted2)'}">${m.has_video_file?'✓ video cargado':'sin video'}</span>
      <button class="qbtn" id="mdel-video-${m.sku}" style="padding:5px 9px;display:${m.has_video_file?'inline-block':'none'}" onclick="deleteMedia('${m.sku}','video')">🗑️</button>
      ${m.has_video_file?`<button class="qbtn" onclick="testSendMedia('${m.sku}','video')">📤 Enviar prueba</button>`:''}
    </div>
    <div id="mm-test-result-${m.sku}" style="font-size:12px;margin-bottom:8px"></div>
    <input class="search mm-link" style="width:100%" value="${m.link||''}" placeholder="Link de compra / ficha (opcional)">
    <input type="hidden" class="mm-img" value="${m.image_url||''}"><input type="hidden" class="mm-vid" value="${m.video_url||''}">
  </div>`;}
async function testSendMedia(sku,kind){
  const phone=($('#mm-test-phone')?.value||'').replace(/\D/g,'');
  const box=$('#mm-test-result-'+sku);
  if(!phone){toast('Escribe primero el número de prueba arriba');return;}
  if(box){box.textContent='Enviando prueba…';box.style.color='var(--muted)';}
  try{
    const r=await api('/api/product-media/test-send',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({sku,kind,phone})});
    if(box){box.textContent=(r.ok?'✅ ':'❌ ')+r.message;box.style.color=r.ok?'#4ade80':'#f87171';}
  }catch(e){if(box){box.textContent='❌ Error: '+e.message;box.style.color='#f87171';}}
}
async function uploadMedia(sku,kind,input){
  const f=input.files[0];if(!f)return;
  toast('Subiendo '+(kind==='image'?'imagen':'video')+'…');
  try{const fd=new FormData();fd.append('file',f);
    const r=await fetch(`${API}/api/product-media/upload?sku=${encodeURIComponent(sku)}&kind=${kind}&token=${TOKEN}`,{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd});
    if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Error');}
    const lbl=$('#mst-'+kind+'-'+sku);if(lbl){lbl.textContent=kind==='image'?'✓ imagen cargada':'✓ video cargado';lbl.style.color='#4ade80';}
    const del=$('#mdel-'+kind+'-'+sku);if(del)del.style.display='inline-block';
    toast('✅ '+(kind==='image'?'Imagen':'Video')+' cargado');
    // Refrescar para mostrar la previsualización recién subida
    if(S.view==='multimedia')renderMultimedia();
  }catch(e){toast('Error: '+e.message);}
}
async function deleteMedia(sku,kind){
  if(!confirm('¿Eliminar '+(kind==='image'?'la imagen':'el video')+' de este producto?'))return;
  try{await api('/api/product-media/'+encodeURIComponent(sku)+'/'+kind,{method:'DELETE',headers:{'Authorization':'Bearer '+TOKEN}});
    const lbl=$('#mst-'+kind+'-'+sku);if(lbl){lbl.textContent=kind==='image'?'sin imagen':'sin video';lbl.style.color='var(--muted2)';}
    const del=$('#mdel-'+kind+'-'+sku);if(del)del.style.display='none';
    toast('Eliminado');
  }catch(e){toast('Error: '+e.message);}
}
async function saveMedia(){
  const data={};
  document.querySelectorAll('#media-list [data-sku]').forEach(d=>{
    data[d.dataset.sku]={image_url:d.querySelector('.mm-img').value.trim(),video_url:d.querySelector('.mm-vid').value.trim(),link:d.querySelector('.mm-link').value.trim()};
  });
  try{await api('/api/product-media',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(data)});toast('✅ Catálogo guardado');}
  catch(e){toast('Error: '+e.message);}
}
function togglePVCustom(){$('#pv-custom-wrap').style.display=$('#pv-incentive').value==='personalizado'?'block':'none';}
async function savePV(){
  const body={enabled:$('#pv-enabled').checked,days_after:parseInt($('#pv-days').value)||3,message:$('#pv-msg').value,review_link:$('#pv-link').value.trim(),incentive:$('#pv-incentive').value,incentive_custom:($('#pv-custom')?$('#pv-custom').value.trim():''),template_name:($('#pv-template')?$('#pv-template').value.trim():''),recontacto_template:($('#pv-recon-template')?$('#pv-recon-template').value.trim():'')};
  try{await api('/api/postventa-config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(body)});toast('✅ Postventa guardada');}
  catch(e){toast('Error: '+e.message);}
}
async function savePromo(){
  const body={message:$('#promo-msg').value,template_name:($('#promo-template')?$('#promo-template').value.trim():'')};
  try{await api('/api/promo-config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(body)});toast('✅ Promoción guardada');}
  catch(e){toast('Error: '+e.message);}
}
async function saveBotName(){
  const name=$('#bot-name').value.trim()||'Asistente';
  try{await api('/api/bot-name',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({name})});toast('✅ Nombre guardado: '+name);}
  catch(e){toast('Error: '+e.message);}
}
async function toggleBotPaused(currentlyPaused){
  const paused=!currentlyPaused;
  if(paused&&!confirm('¿Pausar el bot? Dejará de responder solo; tú atenderás desde el chat.'))return;
  try{await api('/api/bot-paused',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({paused})});
    toast(paused?'⏸️ Bot pausado':'▶️ Bot activado');renderConfig();}
  catch(e){toast('Error: '+e.message);}
}
function _notifBody(){
  return {email:$('#nf-email').value.trim(),whatsapp:$('#nf-wa').value.trim(),
    new_client:$('#nf-new').checked,returning:$('#nf-ret').checked,sale:$('#nf-sale').checked,
    card:$('#nf-card').checked,
    smtp_user:$('#nf-smtp-user').value.trim(),smtp_pass:$('#nf-smtp-pass').value.trim(),
    smtp_host:$('#nf-smtp-host').value.trim(),smtp_port:$('#nf-smtp-port').value.trim(),
    resend_api_key:$('#nf-resend-key').value.trim()};
}
async function saveNotif(){
  try{await api('/api/notif-config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(_notifBody())});toast('✅ Notificaciones guardadas');}
  catch(e){toast('Error: '+e.message);}
}
async function testNotif(){
  const el=$('#nf-test-result');el.style.color='var(--muted)';el.textContent='Enviando…';
  try{const r=await api('/api/notif-test',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(_notifBody())});
    if(r.ok){el.style.color='#16a34a';el.textContent='✅ '+r.message;toast('✅ Correo de prueba enviado');}
    else{el.style.color='#dc2626';el.textContent='❌ '+r.message;}}
  catch(e){el.style.color='#dc2626';el.textContent='❌ '+e.message;}
}
async function saveTraining(){
  const body={notes:$('#train-notes').value};
  try{await api('/api/training-config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify(body)});toast('✅ Entrenamiento guardado');}
  catch(e){toast('Error: '+e.message);}
}
async function saveBusinessInfo(){
  const values={};
  document.querySelectorAll('.bi-field').forEach(inp=>{values[inp.dataset.key]=inp.value.trim();});
  try{await api('/api/business-info',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},body:JSON.stringify({values})});toast('✅ Información guardada');}
  catch(e){toast('Error: '+e.message);}
}

/* ─── INIT + POLLING ─── */
/* ─── TEMA (color del panel) ─── */
function applyTheme(t){
  if(t&&t!=='dark')document.documentElement.setAttribute('data-theme',t);
  else document.documentElement.removeAttribute('data-theme');
}
function setTheme(t){localStorage.setItem('vitatheme',t);applyTheme(t);if(S.view==='config')renderConfig();}
function currentTheme(){return localStorage.getItem('vitatheme')||'dark';}
applyTheme(currentTheme());

(function(){const{view,id}=parseHash();setActiveNav(view);showView(view);if(view==='chat'&&id)setTimeout(()=>openConv(id),400);})();
setInterval(()=>{if(S.view==='chat'){pollMessages();}},3000);
setInterval(()=>{
  // Solo el chat se actualiza en vivo (mensajes nuevos). El resto NO se re-renderiza
  // para no interrumpir la experiencia: solo se refresca el contador de no leídas en segundo plano.
  if(S.view==='chat'){loadConvs();if(S.convId)fillCustomer(S.custPhone);}
  else{api('/api/conversations?filter=all').then(c=>{S.convs=c;updateBadge(c);}).catch(()=>{});}
},10000);
</script>
</body></html>"""
