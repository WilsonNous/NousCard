// ============================================================
//  DASHBOARD • NousCard Premium (VERSÃO FINAL CORRIGIDA)
// ============================================================

// ✅ Expor variáveis globalmente para acesso do inline script
window.ultimoKpis = null;
window.graficoVendas = null;
window.graficoBandeiras = null;
window.kpiInterval = null;
window.graficoBandeirasRetryCount = 0;
const MAX_GRAFICO_RETRY = 3;

// ============================================================
// UTILITÁRIOS SEGUROS
// ============================================================

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

function formatCurrency(value) {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return 'R$ 0,00';
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 2
    }).format(num);
}

function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content ||
           document.querySelector('input[name="csrf_token"]')?.value ||
           '';
}

// ============================================================
// INICIALIZAÇÃO
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    // Elementos do DOM com verificação de segurança
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
            if (el) el.innerHTML = '<span class="loading-spinner" aria-label="Carregando">⏳</span>';
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

            window.ultimoKpis = data.kpis;

            // Resetar contador de retry quando novos dados chegam
            window.graficoBandeirasRetryCount = 0;

            // Atualizar UI com verificações de segurança
            atualizarKPIs(data.kpis, { kpiVendas, kpiRecebido, kpiDiferenca, kpiAlertas });
            
            // ✅ CORREÇÃO: API retorna "adquirentes", não "acquirers"
            atualizarAcquirers(data.kpis.adquirentes || {}, acqContainer);
            
            // Renderizar gráficos se canvas existir e Chart.js estiver carregado
            if (ctxGrafico && window.Chart) {
                atualizarGraficoVendas(data.kpis, ctxGrafico);
            }
            if (ctxBandeiras && window.Chart) {
                atualizarGraficoBandeiras(data.kpis.bandeiras || {}, ctxBandeiras);
            }

            // Esconder erro se existir
            if (dashboardError) {
                dashboardError.style.display = 'none';
                dashboardError.textContent = '';
            }

        } catch (err) {
            console.error("Erro ao carregar KPIs:", err);
            
            // Mostrar erro amigável ao usuário
            if (dashboardError) {
                dashboardError.textContent = '⚠️ Não foi possível carregar os dados. Verifique sua conexão e tente novamente.';
                dashboardError.style.display = 'block';
                dashboardError.setAttribute('role', 'alert');
            }
            
            // Manter valores anteriores ou mostrar placeholder
            if (kpiVendas && !window.ultimoKpis) {
                kpiVendas.textContent = '—';
            }
        }
    }
    
    // ✅ Expor carregarKPIs globalmente para o inline script
    window.carregarKPIs = carregarKPIs;

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
    
    // ✅ Expor atualizarKPIs globalmente
    window.atualizarKPIs = atualizarKPIs;

    // ================== CARDS DE ADQUIRENTES ==================
    function classFromAcquirer(nome) {
        const n = (nome || '').toLowerCase();
        if (n.includes("cielo")) return "acq-cielo";
        if (n.includes("rede")) return "acq-rede";
        if (n.includes("getnet")) return "acq-getnet";
        if (n.includes("stone")) return "acq-stone";
        return "acq-outros";
    }

    // ================== CARDS DE ADQUIRENTES (CORRIGIDO) ==================
    function atualizarAcquirers(adquirentesData, container) {
        // Verificar se container existe
        if (!container) {
            console.warn('⚠️ Container de adquirentes não encontrado');
            return;
        }
    
        // Limpar container
        container.innerHTML = "";
    
        // ✅ Verificar se temos dados válidos (array de objetos)
        if (!adquirentesData || !Array.isArray(adquirentesData) || adquirentesData.length === 0) {
            container.innerHTML = '<p class="nc-empty-state">Nenhuma adquirente encontrada.</p>';
            return;
        }
    
        // ✅ Iterar sobre cada adquirente
        adquirentesData.forEach(acq => {
            // Validar dados mínimos
            if (!acq || !acq.nome) return;
            
            const card = document.createElement("button");
            card.type = "button";
            card.className = `nc-acq-card acq-click ${classFromAcquirer(acq.nome)}`;
            card.dataset.acq = acq.nome;
            card.setAttribute('aria-label', `Ver detalhamento de ${escapeHtml(acq.nome)}`);
    
            const header = document.createElement("div");
            header.className = "nc-acq-header";
            
            const icon = document.createElement("div");
            icon.className = "nc-acq-icon";
            icon.setAttribute('aria-hidden', 'true');
            icon.textContent = '💳';
            
            const label = document.createElement("div");
            label.className = "nc-acq-label";
            label.textContent = acq.nome;
            
            header.appendChild(icon);
            header.appendChild(label);
    
            const values = document.createElement("div");
            values.className = "nc-acq-values";
            
            const vendas = document.createElement("strong");
            vendas.textContent = `Vendas: ${formatCurrency(acq.total_vendas || 0)}`;
            
            const recebido = document.createElement("span");
            recebido.textContent = `Recebido: ${formatCurrency(acq.total_liquido || 0)}`;
            
            const diffVal = (parseFloat(acq.total_vendas) || 0) - (parseFloat(acq.total_liquido) || 0);
            const diff = document.createElement("span");
            diff.textContent = `Diferença: ${formatCurrency(diffVal)}`;
            if (diffVal < 0) diff.style.color = '#cc0000';
            
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
                if (!window.ultimoKpis) return;
                const nome = card.dataset.acq;
                const linhas = (window.ultimoKpis.detalhamento?.vendas || [])
                    .filter(l => (l.adquirente || "Outros") === nome);
                abrirModal(`Detalhamento de Vendas — ${nome}`, linhas);
            });
        });
    };

    // ================== GRÁFICO VENDAS x RECEBIDO ==================
    function atualizarGraficoVendas(kpis, ctx) {
        if (!ctx || !window.Chart) {
            console.warn('⚠️ Chart.js não carregado ou canvas não encontrado');
            return;
        }

        const container = ctx.parentElement;
        if (!container || container.offsetWidth === 0) {
            // Tentar novamente no próximo frame se container não tem dimensões
            requestAnimationFrame(() => {
                if (container && container.offsetWidth > 0) {
                    atualizarGraficoVendas(kpis, ctx);
                }
            });
            return;
        }

        if (window.graficoVendas) {
            window.graficoVendas.destroy();
            window.graficoVendas = null;
        }

        const vendas = parseFloat(kpis.total_vendas) || 0;
        const recebido = parseFloat(kpis.total_recebido) || 0;

        try {
            window.graficoVendas = new Chart(ctx, {
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
                    layout: {
                        padding: { top: 10, right: 10, bottom: 10, left: 10 }
                    },
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
                                callback: (value) => formatCurrency(value),
                                maxTicksLimit: 5
                            },
                            afterFit: (scale) => { scale.width = 60; }
                        },
                        x: {
                            ticks: {
                                autoSkip: true,
                                maxRotation: 45,
                                minRotation: 0
                            }
                        }
                    }
                }
            });
        } catch (err) {
            console.error('Erro ao criar gráfico de vendas:', err);
        }
    }
    
    // ✅ Expor atualizarGraficoVendas globalmente
    window.atualizarGraficoVendas = atualizarGraficoVendas;

    // ================== GRÁFICO BANDEIRAS ==================
    function atualizarGraficoBandeiras(bandeiras, ctx) {
        if (!ctx || !window.Chart) {
            console.warn('⚠️ Chart.js não carregado ou canvas não encontrado para gráfico de bandeiras');
            return;
        }

        const container = ctx.parentElement;
        
        // ✅ CORREÇÃO: Se container não tem dimensões, tentar novamente com requestAnimationFrame
        if (!container || container.offsetWidth === 0) {
            // Prevenir spam: só tenta retry até MAX_GRAFICO_RETRY vezes
            if (window.graficoBandeirasRetryCount < MAX_GRAFICO_RETRY) {
                window.graficoBandeirasRetryCount++;
                requestAnimationFrame(() => {
                    if (container && container.offsetWidth > 0) {
                        atualizarGraficoBandeiras(bandeiras, ctx);
                    }
                });
            } else {
                // Após máx tentativas, mostra mensagem e para de tentar
                console.warn('⚠️ Container do gráfico de bandeiras ainda sem dimensões após retry');
                if (container) {
                    container.innerHTML = '<p class="nc-empty-state" style="text-align:center;color:var(--gray-dark);padding:2rem">Sem dados para exibir</p>';
                }
            }
            return;
        }

        // Resetar contador quando gráfico for renderizado com sucesso
        window.graficoBandeirasRetryCount = 0;

        const labels = Object.keys(bandeiras || {});
        
        if (!labels.length) {
            container.innerHTML = '<p class="nc-empty-state" style="text-align:center;color:var(--gray-dark);padding:2rem">Sem dados para exibir</p>';
            return;
        }

        const valores = labels.map(l => parseFloat(bandeiras[l]?.total || bandeiras[l]?.vendas) || 0);

        if (window.graficoBandeiras) {
            window.graficoBandeiras.destroy();
            window.graficoBandeiras = null;
        }

        try {
            window.graficoBandeiras = new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [{
                        label: "Vendas por Bandeira",
                        data: valores,
                        backgroundColor: ["#1877f2", "#42b72a", "#f0c808", "#dc3545", "#6f42c1", "#fd7e14", "#20c997", "#e83e8c"],
                        borderWidth: 2,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {
                        padding: { top: 10, right: 10, bottom: 10, left: 10 }
                    },
                    plugins: {
                        legend: { 
                            position: "bottom",
                            labels: {
                                padding: 15,
                                usePointStyle: true,
                                boxWidth: 12,
                                font: { size: 11 },
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
        } catch (err) {
            console.error('Erro ao criar gráfico de bandeiras:', err);
            if (container) {
                container.innerHTML = '<p class="nc-error" style="padding:1rem">Erro ao renderizar gráfico. Tente recarregar a página.</p>';
            }
        }
    }
    
    // ✅ Expor atualizarGraficoBandeiras globalmente
    window.atualizarGraficoBandeiras = atualizarGraficoBandeiras;

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

        if (!modal || !tituloEl || !tabela) {
            console.warn('⚠️ Elementos do modal não encontrados');
            return;
        }

        tituloEl.textContent = titulo;
        tabela.innerHTML = '';
        tabela.setAttribute('role', 'table');
        tabela.setAttribute('aria-label', 'Tabela de detalhamento');

        if (!linhas || !linhas.length) {
            if (modalEmpty) {
                modalEmpty.style.display = 'block';
                if (tabela.parentElement) tabela.parentElement.style.display = 'none';
            }
        } else {
            if (modalEmpty) modalEmpty.style.display = 'none';
            if (tabela.parentElement) tabela.parentElement.style.display = 'block';

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

            const tbody = document.createElement('tbody');
            linhas.forEach(l => {
                const tr = document.createElement('tr');
                [l.data, l.adquirente, l.descricao, l.valor, l.previsao, l.banco, l.data_recebimento, l.tipo].forEach(val => {
                    const td = document.createElement('td');
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

        modal.style.display = "block";
        modal.setAttribute('aria-hidden', 'false');
        
        const closeBtn = modal.querySelector('.nc-modal-close');
        if (closeBtn) closeBtn.focus();
        setupModalFocusTrap(modal);
    };

    function setupModalFocusTrap(modal) {
        const focusable = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable.length) return;
        
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
        
        if (modal._focusTrapHandler) {
            modal.removeEventListener('keydown', modal._focusTrapHandler);
            delete modal._focusTrapHandler;
        }
    };

    // ================== CLIQUES NOS KPIs ==================
    document.querySelectorAll(".kpi-click").forEach(card => {
        card.addEventListener("click", () => {
            if (!window.ultimoKpis) return;
            const acao = card.dataset.acao;

            if (acao === "vendas") {
                abrirModal("Detalhamento de Vendas", window.ultimoKpis.detalhamento?.vendas || []);
            } else if (acao === "recebidos") {
                abrirModal("Detalhamento de Recebimentos", window.ultimoKpis.detalhamento?.recebidos || []);
            } else if (acao === "diferencas") {
                abrirModal("Diferenças (vendas ainda não conciliadas)", window.ultimoKpis.detalhamento?.vendas || []);
            }
        });
    });

    // ================== REDIMENSIONAR GRÁFICOS AO REDIMENSIONAR JANELA ==================
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (window.graficoVendas && window.ultimoKpis) {
                atualizarGraficoVendas(window.ultimoKpis, ctxGrafico);
            }
            if (window.graficoBandeiras && window.ultimoKpis?.bandeiras) {
                atualizarGraficoBandeiras(window.ultimoKpis.bandeiras, ctxBandeiras);
            }
        }, 250);
    });

    // ================== INICIAR LOOP DE ATUALIZAÇÃO ==================
    carregarKPIs();
    
    if (window.kpiInterval) clearInterval(window.kpiInterval);
    window.kpiInterval = setInterval(carregarKPIs, 30000);

    // ================== CLEANUP NO UNLOAD ==================
    window.addEventListener('beforeunload', () => {
        if (window.kpiInterval) clearInterval(window.kpiInterval);
        if (window.graficoVendas) window.graficoVendas.destroy();
        if (window.graficoBandeiras) window.graficoBandeiras.destroy();
        clearTimeout(resizeTimeout);
    });
});
