"""Targets 文献证据工作台的静态页面。"""

REVIEW_WORKBENCH_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Targets 文献证据工作台</title>
  <style>
    :root { color-scheme: light; --ink:#1f2937; --muted:#64748b; --line:#dbe4ea;
      --surface:#fff; --canvas:#f4f8f7; --brand:#087f5b; --brand-soft:#e7f5ef;
      --warning:#a15c00; --warning-soft:#fff4df; --danger:#b42318; --danger-soft:#fff0ee; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--canvas); color:var(--ink); font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
    header { background:var(--surface); border-bottom:1px solid var(--line); padding:24px 20px 18px; }
    .header-inner, main { max-width:1120px; margin:0 auto; }
    h1 { margin:0; font-size:24px; letter-spacing:-.02em; }
    .subtitle { margin:6px 0 0; color:var(--muted); }
    main { padding:20px; }
    .toolbar, .notice, .projection { background:var(--surface); border:1px solid var(--line); border-radius:10px; }
    .toolbar { display:flex; flex-wrap:wrap; gap:12px; align-items:end; padding:14px; }
    label { display:flex; flex-direction:column; gap:4px; color:var(--muted); font-size:12px; font-weight:600; }
    input, select, button { font:inherit; }
    input, select { min-height:38px; border:1px solid #b8c7cf; border-radius:6px; background:#fff; color:var(--ink); padding:7px 10px; }
    input:focus, select:focus, button:focus { outline:3px solid #b8e3d1; outline-offset:1px; }
    .token { min-width:240px; }
    button { min-height:38px; border:1px solid var(--brand); border-radius:6px; padding:7px 14px; cursor:pointer; }
    .primary { color:#fff; background:var(--brand); }
    .secondary { color:var(--brand); background:#fff; }
    button:disabled { cursor:not-allowed; opacity:.55; }
    .notice { margin:14px 0; padding:12px 14px; color:#36505a; background:var(--brand-soft); }
    .notice.error { color:var(--danger); background:var(--danger-soft); }
    .list { display:grid; gap:12px; }
    .projection { padding:18px; }
    .projection-head { display:flex; justify-content:space-between; gap:14px; align-items:flex-start; }
    .projection h2 { margin:0; font-size:17px; }
    .meta { display:flex; flex-wrap:wrap; gap:8px 16px; margin:6px 0 0; color:var(--muted); font-size:12px; }
    .badge { display:inline-flex; align-items:center; border-radius:999px; padding:3px 9px; font-size:12px; font-weight:700; white-space:nowrap; }
    .badge.pending { color:var(--warning); background:var(--warning-soft); }
    .badge.approved { color:var(--brand); background:var(--brand-soft); }
    .badge.rejected, .badge.revoked { color:var(--danger); background:var(--danger-soft); }
    .badge.needs_info { color:#475569; background:#eef2f7; }
    .evidence, .pages { margin:14px 0 0; padding-top:12px; border-top:1px solid var(--line); }
    .evidence h3, .pages h3 { margin:0 0 6px; font-size:13px; }
    .evidence-row, .page-row { margin:6px 0; color:#40535d; }
    .excerpt { margin:5px 0 0; padding:8px 10px; border-left:3px solid #9ed5bf; background:#f8fbfa; white-space:pre-wrap; }
    .actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
    .actions button { min-height:34px; padding:5px 10px; }
    .empty, .loading { padding:44px 16px; text-align:center; color:var(--muted); }
    @media (max-width:640px) { header { padding:18px 14px 14px; } main { padding:14px; }
      .toolbar > label, .token { width:100%; min-width:0; } .toolbar button { flex:1; }
      .projection-head { flex-direction:column; } }
  </style>
</head>
<body>
  <header><div class="header-inner">
    <h1>Targets 文献证据工作台</h1>
    <p class="subtitle">只读浏览 WeKnora 已批准证据投影；人工决定仅写回本地待审事件，不自动生成医学结论。</p>
  </div></header>
  <main>
    <section class="toolbar" aria-label="筛选与审核设置">
      <label>显示范围<select id="status"><option value="pending">待审</option><option value="active">活动投影</option><option value="revoked">已撤销</option><option value="all">全部</option></select></label>
      <label class="token">审核令牌（仅保存在当前页面内存）<input id="token" type="password" autocomplete="off" placeholder="写回审核决定时输入"></label>
      <button id="refresh" class="primary" type="button">刷新证据</button>
    </section>
    <div id="notice" class="notice" role="status" aria-live="polite">正在读取证据投影…</div>
    <section id="list" class="list" aria-live="polite"><div class="loading">正在读取…</div></section>
  </main>
  <script>
    (() => {
      const state = { status: 'pending', data: [] };
      const $ = (id) => document.getElementById(id);
      const notice = (message, error = false) => { $('notice').textContent = message; $('notice').className = error ? 'notice error' : 'notice'; };
      const node = (tag, text, className) => { const item = document.createElement(tag); if (className) item.className = className; if (text !== undefined && text !== null) item.textContent = String(text); return item; };
      const badge = (text, className) => node('span', text, `badge ${className || ''}`);
      const addMeta = (container, label, value) => { if (value) container.append(node('span', `${label}：${value}`)); };
      const render = () => {
        const list = $('list'); list.replaceChildren();
        if (!state.data.length) { list.append(node('div', '当前范围没有证据投影。', 'empty')); return; }
        for (const item of state.data) {
          const card = node('article', undefined, 'projection');
          const head = node('div', undefined, 'projection-head');
          const title = node('div'); title.append(node('h2', item.title || item.artifact_id));
          const meta = node('div', undefined, 'meta'); addMeta(meta, 'DOI', item.doi); addMeta(meta, 'PMID', item.pmid); addMeta(meta, 'SHA-256', item.sha256); title.append(meta);
          head.append(title, badge(`${item.status} · ${item.review_status || '未关联审核'}`, item.status === 'revoked' ? 'revoked' : (item.review_status || item.status))); card.append(head);
          const evidence = node('section', undefined, 'evidence'); evidence.append(node('h3', '来源证据'));
          for (const source of (item.payload?.evidence || [])) { const row = node('div', source.source_name || '未命名来源', 'evidence-row'); if (source.license_basis) row.append(node('div', `许可依据：${source.license_basis}`)); evidence.append(row); }
          if (!item.payload?.evidence?.length) evidence.append(node('div', '未提供来源条目。', 'evidence-row'));
          card.append(evidence);
          const pages = node('section', undefined, 'pages'); pages.append(node('h3', '页级摘录'));
          for (const page of (item.payload?.pages || [])) { const row = node('div', undefined, 'page-row'); row.append(node('strong', `第 ${page.page_number || '?'} 页 · ${page.status || '未知'}`)); if (page.text_excerpt) row.append(node('div', page.text_excerpt, 'excerpt')); pages.append(row); }
          if (!item.payload?.pages?.length) pages.append(node('div', '没有可展示的页级摘录。', 'page-row')); card.append(pages);
          if (item.reviewable) { const actions = node('div', undefined, 'actions'); const approve = node('button', '通过并回写', 'primary'); approve.type='button'; approve.addEventListener('click', () => review(item.projection_id, 'approved')); const reject = node('button', '拒绝并回写', 'secondary'); reject.type='button'; reject.addEventListener('click', () => review(item.projection_id, 'rejected')); actions.append(approve, reject); card.append(actions); }
          else if (item.status === 'revoked') card.append(node('div', '该投影已撤销，不允许审核或发布。', 'notice error'));
          list.append(card);
        }
      };
      const load = async () => { state.status = $('status').value; notice('正在读取证据投影…'); $('list').replaceChildren(node('div', '正在读取…', 'loading')); try { const response = await fetch(`/targets/api/projections?status=${encodeURIComponent(state.status)}&limit=50`); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || '读取失败'); state.data = body.data || []; notice(`已加载 ${state.data.length} 条，来自 WeKnora 的脱敏证据投影`); render(); } catch (error) { state.data = []; $('list').replaceChildren(node('div', '证据读取失败，请检查内网服务状态。', 'empty')); notice(error.message || '证据读取失败', true); } };
      const review = async (projectionId, status) => { const token = $('token').value.trim(); if (!token) { notice('审核写回需要输入当前页面令牌。', true); $('token').focus(); return; } const reason = window.prompt('请输入审核说明（不会写入原件或 WeKnora）：', '已完成人工核对'); if (!reason || !reason.trim()) return; try { const response = await fetch(`/targets/api/projections/${encodeURIComponent(projectionId)}/review`, { method:'PATCH', headers:{'Authorization':`Bearer ${token}`, 'Content-Type':'application/json'}, body:JSON.stringify({status, reason:reason.trim()}) }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || '审核写回失败'); notice('审核决定已写回 Targets；请按既有发布流程继续。'); await load(); } catch (error) { notice(error.message || '审核写回失败', true); } };
      $('status').addEventListener('change', load); $('refresh').addEventListener('click', load); load();
    })();
  </script>
</body>
</html>"""
