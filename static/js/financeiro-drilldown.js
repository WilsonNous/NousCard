(() => {
  'use strict';

  if (!document.getElementById('despesas-grupos')) return;

  const GRUPOS = {
    'alimentação': 'alimentacao',
    'alimentacao': 'alimentacao',
    'transporte e combustível': 'transporte',
    'transporte': 'transporte',
    'fornecedores': 'fornecedores',
    'impostos e tributos': 'impostos',
    'impostos': 'impostos',
    'transferências enviadas': 'transferencias_enviadas',
    'transferencias enviadas': 'transferencias_enviadas',
    'outras despesas': 'outras_despesas',
    'pix recebido': 'pix_recebido',
    'transferências recebidas': 'transferencias_recebidas',
    'transferencias recebidas': 'transferencias_recebidas',
    'transferências': 'transferencias_recebidas',
    'transferencias': 'transferencias_recebidas',
    'outras receitas': 'outras_receitas'
  };

  const normalizar = texto => (texto || '')
    .replace(/[🍽️🚗🏪🏛️↗️📦⚡🏦💰]/gu, '')
    .trim()
    .toLocaleLowerCase('pt-BR');

  const brl = valor => new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL'
  }).format(Number(valor || 0));

  const dataBR = valor => {
    if (!valor) return '—';
    const [ano, mes, dia] = valor.split('-');
    return `${dia}/${mes}/${ano}`;
  };

  function instalarEstilos() {
    if (document.getElementById('nc-drilldown-style')) return;
    const style = document.createElement('style');
    style.id = 'nc-drilldown-style';
    style.textContent = `
      .nc-drill-click{cursor:pointer;border-radius:10px;padding:8px;margin:-8px;transition:background .18s,transform .18s}
      .nc-drill-click:hover,.nc-drill-click:focus{background:#F0F2F5;outline:2px solid transparent;transform:translateX(2px)}
      .nc-drill-click .group-name::after,.nc-drill-click .breakdown-name::after{content:'  Ver detalhes ›';font-size:.72rem;color:#1877F2;font-weight:700}
      .nc-drill-overlay{position:fixed;inset:0;background:rgba(16,15,13,.32);z-index:5000;opacity:0;pointer-events:none;transition:opacity .2s}
      .nc-drill-overlay.open{opacity:1;pointer-events:auto}
      .nc-drill-drawer{position:absolute;right:0;top:0;height:100%;width:min(560px,94vw);background:#fff;box-shadow:-12px 0 35px rgba(0,0,0,.16);transform:translateX(100%);transition:transform .24s ease;display:flex;flex-direction:column}
      .nc-drill-overlay.open .nc-drill-drawer{transform:translateX(0)}
      .nc-drill-head{padding:20px 22px;border-bottom:1px solid #DADDE1;display:flex;justify-content:space-between;gap:16px;align-items:flex-start}
      .nc-drill-title{margin:0;font-size:1.35rem;color:#100F0D}.nc-drill-sub{margin:5px 0 0;color:#65676B;font-size:.9rem}
      .nc-drill-close{border:0;background:#F0F2F5;border-radius:50%;width:36px;height:36px;font-size:1.35rem;cursor:pointer}
      .nc-drill-summary{padding:18px 22px;background:#F7F9FC;border-bottom:1px solid #DADDE1}
      .nc-drill-total{font-size:1.7rem;font-weight:800;color:#100F0D}.nc-drill-explain{margin-top:5px;color:#65676B}
      .nc-drill-body{padding:0 22px 24px;overflow:auto;flex:1}.nc-drill-item{display:grid;grid-template-columns:90px 1fr auto;gap:12px;padding:15px 0;border-bottom:1px solid #E4E6EB;align-items:start}
      .nc-drill-date,.nc-drill-meta{font-size:.78rem;color:#65676B}.nc-drill-desc{font-weight:700;color:#100F0D;word-break:break-word}.nc-drill-value{font-weight:800;white-space:nowrap}
      .nc-drill-state{padding:32px 8px;text-align:center;color:#65676B}.nc-drill-error{color:#B3261E}
      @media(max-width:600px){.nc-drill-item{grid-template-columns:1fr auto}.nc-drill-date{grid-column:1/-1}.nc-drill-head,.nc-drill-summary,.nc-drill-body{padding-left:16px;padding-right:16px}}
    `;
    document.head.appendChild(style);
  }

  function criarDrawer() {
    let overlay = document.getElementById('nc-drill-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'nc-drill-overlay';
    overlay.className = 'nc-drill-overlay';
    overlay.innerHTML = `
      <aside class="nc-drill-drawer" role="dialog" aria-modal="true" aria-labelledby="nc-drill-title">
        <div class="nc-drill-head">
          <div><h2 class="nc-drill-title" id="nc-drill-title">Detalhamento</h2><p class="nc-drill-sub" id="nc-drill-sub">Entenda de onde veio este valor.</p></div>
          <button type="button" class="nc-drill-close" aria-label="Fechar detalhamento">×</button>
        </div>
        <div class="nc-drill-summary"><div class="nc-drill-total" id="nc-drill-total">—</div><div class="nc-drill-explain" id="nc-drill-explain"></div></div>
        <div class="nc-drill-body" id="nc-drill-body"></div>
      </aside>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.nc-drill-close').addEventListener('click', fechar);
    overlay.addEventListener('click', e => { if (e.target === overlay) fechar(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && overlay.classList.contains('open')) fechar(); });
    return overlay;
  }

  function fechar() {
    document.getElementById('nc-drill-overlay')?.classList.remove('open');
    document.body.style.overflow = '';
  }

  async function abrir(slug) {
    const overlay = criarDrawer();
    const body = document.getElementById('nc-drill-body');
    document.getElementById('nc-drill-title').textContent = 'Detalhamento financeiro';
    document.getElementById('nc-drill-sub').textContent = 'Buscando os lançamentos que formam este valor...';
    document.getElementById('nc-drill-total').textContent = '—';
    document.getElementById('nc-drill-explain').textContent = '';
    body.innerHTML = '<div class="nc-drill-state">Carregando detalhes...</div>';
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';

    const periodo = document.getElementById('periodoSelect')?.value || '12meses';
    try {
      const r = await fetch(`/financeiro/lancamentos/detalhes?grupo=${encodeURIComponent(slug)}&periodo=${encodeURIComponent(periodo)}`, {headers:{Accept:'application/json'}});
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error(d.error || 'Não foi possível carregar o detalhamento.');

      document.getElementById('nc-drill-title').textContent = `${d.icone || '💰'} ${d.nome}`;
      document.getElementById('nc-drill-sub').textContent = `${d.quantidade} lançamento(s) no período selecionado`;
      document.getElementById('nc-drill-total').textContent = brl(d.total);
      document.getElementById('nc-drill-explain').textContent = d.quantidade
        ? `Você teve ${d.quantidade} lançamento(s) neste grupo. O valor médio foi ${brl(d.media)}.`
        : 'Nenhum lançamento encontrado neste grupo para o período.';

      if (!d.itens?.length) {
        body.innerHTML = '<div class="nc-drill-state">Nenhum lançamento para mostrar.</div>';
        return;
      }
      body.innerHTML = d.itens.map(item => `
        <div class="nc-drill-item">
          <div class="nc-drill-date">${dataBR(item.data)}</div>
          <div><div class="nc-drill-desc">${esc(item.descricao)}</div><div class="nc-drill-meta">${esc(item.subcategoria || item.categoria || 'Sem categoria')}${item.banco ? ` • ${esc(item.banco)}` : ''}${item.origem ? ` • ${esc(item.origem)}` : ''}</div></div>
          <div class="nc-drill-value">${brl(item.valor)}</div>
        </div>`).join('') + (d.limitado ? '<div class="nc-drill-state">Mostrando os lançamentos mais recentes deste grupo.</div>' : '');
    } catch (erro) {
      body.innerHTML = `<div class="nc-drill-state nc-drill-error">${esc(erro.message || 'Não foi possível carregar os detalhes.')}</div>`;
    }
  }

  function esc(valor) {
    const el = document.createElement('div');
    el.textContent = valor == null ? '' : String(valor);
    return el.innerHTML;
  }

  function prepararElemento(el, seletorNome) {
    if (!el || el.dataset.drillReady === '1') return;
    const nome = normalizar(el.querySelector(seletorNome)?.textContent);
    const slug = GRUPOS[nome];
    if (!slug) return;
    el.dataset.drillReady = '1';
    el.classList.add('nc-drill-click');
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', `Ver detalhes de ${nome}`);
    el.addEventListener('click', () => abrir(slug));
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abrir(slug); } });
  }

  function preparar() {
    document.querySelectorAll('#despesas-grupos .group-item').forEach(el => prepararElemento(el, '.group-name'));
    document.querySelectorAll('#despesas-breakdown .breakdown-item').forEach(el => prepararElemento(el, '.breakdown-name'));
    document.querySelectorAll('#receitas-breakdown .breakdown-item').forEach(el => prepararElemento(el, '.breakdown-name'));
  }

  instalarEstilos();
  criarDrawer();
  preparar();
  const observer = new MutationObserver(preparar);
  ['despesas-grupos','despesas-breakdown','receitas-breakdown'].forEach(id => {
    const el = document.getElementById(id); if (el) observer.observe(el,{childList:true,subtree:true});
  });
})();