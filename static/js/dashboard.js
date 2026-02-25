// ============================================================
//  DASHBOARD • NousCard Premium (VERSÃO SEGURA)
// ============================================================

let ultimoKpis = null;
let graficoVendas = null;
let graficoBandeiras = null;
let kpiInterval = null;

// ============================================================
// UTILITÁRIOS SEGUROS
// ============================================================

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * Formata moeda com precisão (usa string para evitar float errors)
 */
function formatCurrency(value) {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return 'R$ 0,00';
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 2
    }).format(num);
}

/**
 * Obtém token CSRF do meta tag ou input
 */
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content ||
           document.querySelector('input[name="csrf_token"]')?.value ||
           '';
}

// ============================================================
// INICIALIZAÇÃO
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    // Elementos do DOM
    const kpiVendas = document.querySelector(".kpi-value-vendas");
    const kpiRecebido = document.querySelector(".kpi-value-recebido");
    const kpiDiferenca = document.querySelector(".kpi-value-diferenca");
    const kpiAlertas = document.querySelector(".kpi-value-alertas");
    const ctxGrafico = document.getElementById("graficoVendasRecebidos");
    const ctxBandeiras = document.getElementById("graficoBandeiras");
    const acqContainer = document.getElementById("acqContainer");
    const dashboardError = document.getElementById("dashboard-error");

    // ================== CARREGAR KPIs DA API ==================
    async function carregarKPIs() {
        // Mostrar loading se for a primeira carga
        const kpiElements = document.querySelectorAll('.kpi-value[data-loading="true"]');
        kpiElements.forEach(el => {
            el.innerHTML = '<span class="loading-spinner" aria-label="Carregando">⏳</span>';
        });

        try {
            const res = await fetch("/api/v1/dashboard/kpis", {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken()
                }
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            }

            const data = await res.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Erro ao carregar dados');
            }

            ultimoKpis = data.kpis;

            // Atualizar UI
            atualizarKPIs(data.kpis, { kpiVendas, kpiRecebido, kpiDiferenca, kpiAlertas });
            atualizarAcquirers(data.kpis.acquirers || {}, acqContainer);
            
            if (ctxGrafico) atualizarGraficoVendas(data.kpis, ctxGrafico);
            if (ctxBandeiras) atualizarGraficoBandeiras(data.kpis.acquirers || {}, ctxBandeiras);

            // Esconder erro se existir
            if (dashboardError) dashboardError.style.display = 'none';

        } catch (err) {
            console.error("Erro ao carregar KPIs:", err);
            
            // Mostrar erro amigável ao usuário
            if (dashboardError) {
                dashboardError.textContent = '⚠️ Não foi possível carregar os dados. Verifique sua conexão e tente novamente.';
                dashboardError.style.display = 'block';
                dashboardError.setAttribute('role', 'alert');
            }
            
            // Manter valores anteriores ou mostrar placeholder
            if (kpiVendas && !ultimoKpis) {
                kpiVendas.textContent = '—';
            }
        }
    }

    // ================== ATUALIZAR VALORES DOS KPIs ==================
    function atualizarKPIs(kpis, elements) {
        const { kpiVendas, kpiRecebido, kpiDiferenca, kpiAlertas } = elements;

        if (kpiVendas && kpis.total_vendas !== undefined) {
            kpiVendas.textContent = formatCurrency(kpis.total_vendas);
            kpiVendas.removeAttribute('data-loading');
        }

        if (kpiRecebido && kpis.total_recebido !== undefined) {
            kpiRecebido.textContent = formatCurrency(kpis.total_recebido);
            kpiRecebido.removeAttribute('data-loading');
        }

        if (kpiDiferenca && kpis.diferenca !== undefined) {
            const diff = parseFloat(kpis.diferenca);
            kpiDiferenca.textContent = diff >= 0 ? `+${formatCurrency(diff)}` : formatCurrency(diff);
            kpiDiferenca.classList.toggle('negativo', diff < 0);
            kpiDiferenca.removeAttribute('data-loading');
        }

        if (kpiAlertas && kpis.alertas !== undefined) {
            kpiAlertas.textContent = kpis.alertas;
        }
    }

    // ================== CARDS DE ADQUIRENTES ==================
    function classFromAcquirer(nome) {
        const n = (nome || '').toLowerCase();
        if (n.includes("cielo")) return "acq-cielo";
        if (n.includes("rede")) return "acq-rede";
        if (n.includes("getnet")) return "acq-getnet";
        if (n.includes("stone")) return "acq-stone";
        return "acq-outros";
    }

    function atualizarAcquirers(acquirers, container) {
        if (!container) return;

        container.innerHTML = "";

        const nomes = Object.keys(acquirers || {}).sort();

        if (nomes.length === 0) {
            container.innerHTML = '<p class="nc-empty-state">Nenhuma adquirente encontrada.</p>';
            return;
        }

        nomes.forEach(nome => {
            const acq = acquirers[nome];
            const card = document.createElement("button");
            card.type = "button";
            card.className = `nc-acq-card acq-click ${classFromAcquirer(nome)}`;
            card.dataset.acq = nome;
            card.setAttribute('aria-label', `Ver detalhamento de ${escapeHtml(nome)}`);

            // Criar conteúdo com textContent (seguro contra XSS)
            const header = document.createElement("div");
            header.className = "nc-acq-header";
            
            const icon = document.createElement("div");
            icon.className = "nc-acq-icon";
            icon.setAttribute('aria-hidden', 'true');
            icon.textContent = '💳';
            
            const label = document.createElement("div");
            label.className = "nc-acq-label";
            label.textContent = nome;
            
            header.appendChild(icon);
            header.appendChild(label);

            const values = document.createElement("div");
            values.className = "nc-acq-values";
            
            const vendas = document.createElement("strong");
            vendas.textContent = `Vendas: ${formatCurrency(acq.vendas || 0)}`;
            
            const recebido = document.createElement("span");
            recebido.innerHTML = `<br>Recebido: ${formatCurrency(acq.recebidos || 0)}`;
            
            const diff = document.createElement("span");
            const diffVal = parseFloat(acq.diferenca || 0);
            diff.innerHTML = `<br>Diferença: <span style="color:${diffVal >= 0 ? '#008000' : '#cc0000'}">${formatCurrency(diffVal)}</span>`;
            
            values.appendChild(vendas);
            values.appendChild(recebido);
            values.appendChild(diff);

            card.appendChild(header);
            card.appendChild(values);
            container.appendChild(card);
        });

        // Listeners para abrir modal
        container.querySelectorAll(".acq-click").forEach(card => {
            card.addEventListener("click", () => {
                if (!ultimoKpis) return;
                const nome = card.dataset.acq;
                const linhas = (ultimoKpis.detalhamento?.vendas || [])
                    .filter(l => (l.adquirente || "Outros") === nome);

                abrirModal(
                    `Detalhamento de Vendas — ${nome}`,
                    linhas
                );
            });
        });
    }

    // ================== GRÁFICO VENDAS x RECEBIDO ==================
    function atualizarGraficoVendas(kpis, ctx) {
        if (!ctx || !Chart) return;

        if (graficoVendas) graficoVendas.destroy();

        const vendas = parseFloat(kpis.total_vendas) || 0;
        const recebido = parseFloat(kpis.total_recebido) || 0;

        graficoVendas = new Chart(ctx, {
            type: "bar",
            data: {
                labels: ["Vendas", "Recebido"],
                datasets: [{
                    label: "Valores",
                    data: [vendas, recebido],
                    backgroundColor: ["#1877f2", "#3cb371"],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => formatCurrency(context.parsed.y)
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => formatCurrency(value)
                        }
                    }
                }
            }
        });
    }

    // ================== GRÁFICO BANDEIRAS ==================
    function atualizarGraficoBandeiras(acquirers, ctx) {
        if (!ctx || !Chart) return;

        const labels = Object.keys(acquirers || {});
        if (!labels.length) {
            ctx.parentElement.innerHTML = '<p class="nc-empty-state">Sem dados para exibir.</p>';
            return;
        }

        const valores = labels.map(l => parseFloat(acquirers[l].vendas) || 0);

        if (graficoBandeiras) graficoBandeiras.destroy();

        graficoBandeiras = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    label: "Vendas por Adquirente",
                    data: valores,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        position: "bottom",
                        labels: {
                            generateLabels: (chart) => {
                                const data = chart.data;
                                return data.labels.map((label, i) => ({
                                    text: `${label}: ${formatCurrency(data.datasets[0].data[i])}`,
                                    fillStyle: chart.data.datasets[0].backgroundColor[i],
                                    index: i
                                }));
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => formatCurrency(context.parsed)
                        }
                    }
                }
            }
        });
    }

    // ================== MODAL SEGURO E ACESSÍVEL ==================
    function criarElementoSeguro(tag, textContent, className = '') {
        const el = document.createElement(tag);
        el.textContent = textContent;
        if (className) el.className = className;
        return el;
    }

    window.abrirModal = function(titulo, linhas) {
        const modal = document.getElementById("modalDetalhe");
        const tituloEl = document.getElementById("modalTitulo");
        const tabela = document.getElementById("modalTabela");
        const modalEmpty = document.getElementById("modal-empty");

        if (!modal || !tituloEl || !tabela) return;

        // Escapar título
        tituloEl.textContent = titulo;

        // Limpar tabela
        tabela.innerHTML = '';
        tabela.setAttribute('role', 'table');
        tabela.setAttribute('aria-label', 'Tabela de detalhamento');

        if (!linhas || !linhas.length) {
            if (modalEmpty) {
                modalEmpty.style.display = 'block';
                tabela.parentElement.style.display = 'none';
            }
        } else {
            if (modalEmpty) modalEmpty.style.display = 'none';
            tabela.parentElement.style.display = 'block';

            // Criar thead
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            const cols = ['Data Venda', 'Adquirente', 'Descrição', 'Valor', 'Previsão', 'Banco', 'Data Receb.', 'Tipo'];
            
            cols.forEach(col => {
                const th = document.createElement('th');
                th.scope = 'col';
                th.textContent = col;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            tabela.appendChild(thead);

            // Criar tbody
            const tbody = document.createElement('tbody');
            linhas.forEach(l => {
                const tr = document.createElement('tr');
                
                [l.data, l.adquirente, l.descricao, l.valor, l.previsao, l.banco, l.data_recebimento, l.tipo].forEach(val => {
                    const td = document.createElement('td');
                    // Formatar valor monetário se for campo de valor
                    if (val !== undefined && val !== null) {
                        td.textContent = typeof val === 'number' ? formatCurrency(val) : String(val);
                    } else {
                        td.textContent = '-';
                    }
                    tr.appendChild(td);
                });
                
                tbody.appendChild(tr);
            });
            tabela.appendChild(tbody);
        }

        // Mostrar modal
        modal.style.display = "block";
        modal.setAttribute('aria-hidden', 'false');
        
        // Focar no botão fechar para acessibilidade
        const closeBtn = modal.querySelector('.nc-modal-close');
        if (closeBtn) closeBtn.focus();

        // Trap de foco
        setupModalFocusTrap(modal);
    };

    function setupModalFocusTrap(modal) {
        const focusable = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        function handleKeydown(e) {
            if (e.key === 'Tab') {
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                window.fecharModal();
            }
        }

        modal.addEventListener('keydown', handleKeydown);
        modal._focusTrapHandler = handleKeydown;
    }

    window.fecharModal = function() {
        const modal = document.getElementById("modalDetalhe");
        if (!modal) return;
        
        modal.style.display = "none";
        modal.setAttribute('aria-hidden', 'true');
        
        // Remover trap de foco
        if (modal._focusTrapHandler) {
            modal.removeEventListener('keydown', modal._focusTrapHandler);
            delete modal._focusTrapHandler;
        }
        
        // Restaurar foco no elemento que abriu o modal
        const lastFocused = document.activeElement;
        if (lastFocused && lastFocused !== document.body) {
            // Opcional: guardar referência do elemento que abriu
        }
    };

    // ================== CLIQUES NOS KPIs ==================
    document.querySelectorAll(".kpi-click").forEach(card => {
        card.addEventListener("click", () => {
            if (!ultimoKpis) return;
            const acao = card.dataset.acao;

            if (acao === "vendas") {
                abrirModal("Detalhamento de Vendas", ultimoKpis.detalhamento?.vendas || []);
            } else if (acao === "recebidos") {
                abrirModal("Detalhamento de Recebimentos", ultimoKpis.detalhamento?.recebidos || []);
            } else if (acao === "diferencas") {
                abrirModal("Diferenças (vendas ainda não conciliadas)", ultimoKpis.detalhamento?.vendas || []);
            }
        });
    });

    // ================== INICIAR LOOP DE ATUALIZAÇÃO ==================
    carregarKPIs();
    
    // Clear interval anterior se existir (hot reload)
    if (kpiInterval) clearInterval(kpiInterval);
    
    kpiInterval = setInterval(carregarKPIs, 30000); // 30 segundos (menos agressivo)

    // ================== CLEANUP NO UNLOAD ==================
    window.addEventListener('beforeunload', () => {
        if (kpiInterval) clearInterval(kpiInterval);
        if (graficoVendas) graficoVendas.destroy();
        if (graficoBandeiras) graficoBandeiras.destroy();
    });
});
