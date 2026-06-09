// ============================================================
//  DASHBOARD • NousCard Premium (VERSÃO FINAL CORRIGIDA)
// ============================================================
// ✅ Integração completa com templates HTML corrigidos

(function() {
    'use strict';
    
    console.log('🔄 Dashboard carregado - Versão Completa');
    
    // Estado da aplicação
    let dashboardState = {
        ultimoKpis: null,
        graficoVendas: null,
        graficoBandeiras: null,
        kpiInterval: null,
        graficoBandeirasRetryCount: 0,
        isLoading: false,
        lastFetchTime: null
    };
    
    const MAX_GRAFICO_RETRY = 3;
    const AUTO_REFRESH_INTERVAL = 30000; // 30 segundos
    
    // ✅ Helper: Obter CSRF token (fallback robusto)
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value || 
               '';
    }
    
    // ✅ Helper: Escape HTML para prevenir XSS
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
    
    // ✅ Helper: Formatador de moeda BRL
    window.formatCurrency = function(value) {
        if (value === null || value === undefined || value === '') return '—';
        const num = typeof value === 'string' 
            ? parseFloat(value.replace(/[^\d,.-]/g, '').replace(',', '.')) 
            : value;
        if (isNaN(num)) return '—';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    };
    
    // ✅ Helper: Formatador de data BR
    window.formatDateBR = function(dateStr) {
        if (!dateStr) return '—';
        const date = new Date(dateStr);
        if (isNaN(date)) return dateStr;
        return date.toLocaleDateString('pt-BR');
    };
    
    // ✅ Helper: Construir query string com filtros
    function buildQueryParams(filters = {}) {
        const params = new URLSearchParams();
        
        // Filtros de período
        if (filters.periodo) params.append('periodo', filters.periodo);
        if (filters.data_inicio) params.append('data_inicio', filters.data_inicio);
        if (filters.data_fim) params.append('data_fim', filters.data_fim);
        
        // ✅ NOVO: Filtro por tipo de pagamento
        if (filters.tipo_pagamento && filters.tipo_pagamento !== 'todos') {
            params.append('tipo_pagamento', filters.tipo_pagamento);
        }
        
        return params.toString();
    }
    
    // ✅ Helper: Obter filtros atuais do DOM
    function getCurrentFilters() {
        return {
            periodo: document.getElementById('filtroPeriodo')?.value || 'todos',
            data_inicio: document.getElementById('filtroInicio')?.value,
            data_fim: document.getElementById('filtroFim')?.value,
            tipo_pagamento: document.getElementById('filtroTipoPagamento')?.value || 'todos'
        };
    }
    
    document.addEventListener("DOMContentLoaded", () => {
        // Elementos do DOM com verificação de segurança
        const kpiVendas = document.querySelector(".kpi-value-vendas");
        const kpiRecebido = document.querySelector(".kpi-value-recebido");
        const kpiDiferenca = document.querySelector(".kpi-value-diferenca");
        const kpiAlertas = document.querySelector(".kpi-value-alertas");
        // ✅ NOVO: KPI de PIX
        const kpiPix = document.querySelector(".kpi-value-pix");
        const ctxGrafico = document.getElementById("graficoVendasRecebidos");
        const ctxBandeiras = document.getElementById("graficoBandeiras");
        const acqContainer = document.getElementById("acqContainer");
        const dashboardError = document.getElementById("dashboard-error");
        const loadingIndicator = document.getElementById('dashboard-loading');
        
        // ================== CARREGAR KPIs DA API ==================
        async function carregarKPIs(filters = null) {
            // Prevenir múltiplas chamadas simultâneas
            if (dashboardState.isLoading) {
                console.log('⏳ Carregamento já em andamento, ignorando nova requisição');
                return;
            }
            
            dashboardState.isLoading = true;
            
            // Mostrar loading se for a primeira carga ou se elementos estão vazios
            const kpiElements = document.querySelectorAll('.kpi-value[data-loading="true"]');
            const shouldShowLoading = kpiElements.length > 0 || !dashboardState.ultimoKpis;
            
            if (shouldShowLoading && kpiElements.length > 0) {
                kpiElements.forEach(el => {
                    if (el) el.innerHTML = '<span class="loading-spinner" aria-label="Carregando">⏳</span>';
                });
            }
            
            // Mostrar indicador de atualização discreto
            if (loadingIndicator) {
                loadingIndicator.style.display = 'flex';
            }
            
            try {
                // Usar filtros passados ou obter do DOM
                const activeFilters = filters || getCurrentFilters();
                const queryString = buildQueryParams(activeFilters);
                const url = `/api/v1/dashboard/kpis${queryString ? '?' + queryString : ''}`;
                
                console.log(`📡 Fetching KPIs: ${url}`);
                
                const res = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': getCsrfToken()
                    },
                    // ✅ NOVO: Timeout para prevenir requests pendentes infinitos
                    signal: AbortSignal.timeout(15000)
                });
                
                if (!res.ok) {
                    // ✅ Tratamento de erro específico por código HTTP
                    let errorMsg = `HTTP ${res.status}: ${res.statusText}`;
                    
                    if (res.status === 401) {
                        errorMsg = 'Sessão expirada. Redirecionando para login...';
                        // Redirecionar após delay
                        setTimeout(() => {
                            window.location.href = '/auth/login?expired=1';
                        }, 2000);
                    } else if (res.status === 403) {
                        errorMsg = 'Acesso negado. Verifique suas permissões.';
                    } else if (res.status === 429) {
                        errorMsg = 'Muitas requisições. Aguarde alguns segundos.';
                    } else if (res.status >= 500) {
                        errorMsg = 'Erro interno do servidor. Tente novamente em alguns minutos.';
                    }
                    
                    throw new Error(errorMsg);
                }
                
                const data = await res.json();
                
                if (!data.ok) {
                    throw new Error(data.error || 'Erro ao carregar dados');
                }
                
                // Atualizar estado
                dashboardState.ultimoKpis = data.kpis;
                dashboardState.lastFetchTime = new Date();
                
                // Resetar contador de retry quando dados chegam com sucesso
                dashboardState.graficoBandeirasRetryCount = 0;
                
                // ✅ Preparar objeto de elementos com kpiPix se existir
                const kpiElementsObj = { 
                    kpiVendas, 
                    kpiRecebido, 
                    kpiDiferenca, 
                    kpiAlertas 
                };
                if (kpiPix) kpiElementsObj.kpiPix = kpiPix;
                
                // Atualizar UI
                atualizarKPIs(data.kpis, kpiElementsObj);
                
                // ✅ CORREÇÃO: API retorna "adquirentes" (array), não objeto
                const adquirentesData = data.kpis.adquirentes || [];
                atualizarAcquirers(adquirentesData, acqContainer);
                
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
                
                // Anunciar atualização para screen readers
                if (dashboardError?.getAttribute('aria-live')) {
                    dashboardError.setAttribute('aria-live', 'polite');
                    dashboardError.textContent = `Dados atualizados em ${new Date().toLocaleTimeString('pt-BR')}`;
                    setTimeout(() => { dashboardError.textContent = ''; }, 3000);
                }
                
            } catch (err) {
                console.error("❌ Erro ao carregar KPIs:", err);
                
                // Mostrar erro amigável ao usuário
                if (dashboardError) {
                    dashboardError.className = 'nc-error';
                    dashboardError.textContent = `⚠️ ${err.message || 'Não foi possível carregar os dados'}`;
                    dashboardError.style.display = 'block';
                    dashboardError.setAttribute('role', 'alert');
                    dashboardError.setAttribute('aria-live', 'assertive');
                }
                
                // Manter valores anteriores ou mostrar placeholder
                if (kpiVendas && !dashboardState.ultimoKpis) {
                    kpiVendas.textContent = '—';
                }
                
                // ✅ Implementar retry com backoff exponencial para erros de rede
                if (err.name === 'TimeoutError' || err.message.includes('Failed to fetch')) {
                    console.log('🔄 Tentando retry em 5 segundos...');
                    setTimeout(() => {
                        if (!document.hidden) { // Só retry se aba estiver visível
                            carregarKPIs(filters);
                        }
                    }, 5000);
                }
                
            } finally {
                dashboardState.isLoading = false;
                
                // Esconder indicador de loading
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            }
        }
        
        // ✅ Expor carregarKPIs globalmente para o inline script
        window.carregarKPIs = carregarKPIs;
        
        // ✅ NOVO: Função para carregar KPIs com filtros (usada pelo inline script)
        window.carregarKPIsComFiltros = async function(queryString = '') {
            // Parsear query string para objeto de filtros
            const params = new URLSearchParams(queryString);
            const filters = {
                periodo: params.get('periodo') || 'todos',
                data_inicio: params.get('data_inicio'),
                data_fim: params.get('data_fim'),
                tipo_pagamento: params.get('tipo_pagamento') || 'todos'
            };
            
            // Atualizar UI dos filtros no DOM (se existirem)
            if (filters.periodo && document.getElementById('filtroPeriodo')) {
                document.getElementById('filtroPeriodo').value = filters.periodo;
            }
            if (filters.data_inicio && document.getElementById('filtroInicio')) {
                document.getElementById('filtroInicio').value = filters.data_inicio;
            }
            if (filters.data_fim && document.getElementById('filtroFim')) {
                document.getElementById('filtroFim').value = filters.data_fim;
            }
            if (filters.tipo_pagamento && document.getElementById('filtroTipoPagamento')) {
                document.getElementById('filtroTipoPagamento').value = filters.tipo_pagamento;
            }
            
            // Chamar carregarKPIs com filtros
            await carregarKPIs(filters);
        };
        
        // ================== ATUALIZAR VALORES DOS KPIs ==================
        function atualizarKPIs(kpis, elements) {
            const { 
                kpiVendas, 
                kpiRecebido, 
                kpiDiferenca, 
                kpiAlertas,
                kpiPix // ✅ NOVO: KPI de PIX
            } = elements;
            
            // KPI: Total Vendas
            if (kpiVendas && kpis.total_vendas !== undefined) {
                kpiVendas.textContent = formatCurrency(kpis.total_vendas);
                kpiVendas.removeAttribute('data-loading');
            }
            
            // KPI: Total Recebido
            if (kpiRecebido && kpis.total_recebido !== undefined) {
                kpiRecebido.textContent = formatCurrency(kpis.total_recebido);
                kpiRecebido.removeAttribute('data-loading');
            }
            
            // KPI: Diferença (com cor condicional)
            if (kpiDiferenca && kpis.diferenca !== undefined) {
                const diff = parseFloat(kpis.diferenca);
                kpiDiferenca.textContent = diff >= 0 ? `+${formatCurrency(diff)}` : formatCurrency(diff);
                kpiDiferenca.classList.toggle('negativo', diff < 0);
                kpiDiferenca.removeAttribute('data-loading');
            }
            
            // KPI: Alertas
            if (kpiAlertas && kpis.alertas !== undefined) {
                kpiAlertas.textContent = kpis.alertas;
            }
            
            // ✅ NOVO: KPI de PIX (se elemento existir e dados estiverem presentes)
            if (kpiPix && kpis.total_vendas_pix !== undefined) {
                kpiPix.textContent = formatCurrency(kpis.total_vendas_pix);
                kpiPix.removeAttribute('data-loading');
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
            if (n.includes("pagseguro")) return "acq-pagseguro";
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
                    if (!dashboardState.ultimoKpis) return;
                    const nome = card.dataset.acq;
                    const linhas = (dashboardState.ultimoKpis.detalhamento?.vendas || [])
                        .filter(l => (l.adquirente || "Outros") === nome);
                    abrirModal(`Detalhamento de Vendas — ${nome}`, linhas);
                });
            });
        }
        
        // ✅ Expor atualizarAcquirers globalmente
        window.atualizarAcquirers = atualizarAcquirers;
        
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
            
            // Destruir gráfico anterior se existir
            if (dashboardState.graficoVendas) {
                dashboardState.graficoVendas.destroy();
                dashboardState.graficoVendas = null;
            }
            
            const vendas = parseFloat(kpis.total_vendas) || 0;
            const recebido = parseFloat(kpis.total_recebido) || 0;
            
            try {
                dashboardState.graficoVendas = new Chart(ctx, {
                    type: "bar",
                    data: {
                        labels: ["Vendas", "Recebido"],
                        datasets: [{
                            label: "Valores",
                            data: [vendas, recebido],
                            backgroundColor: ["#1877f2", "#3cb371"],
                            borderRadius: 6,
                            borderSkipped: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {
                            duration: 500,
                            easing: 'easeOutQuart'
                        },
                        layout: {
                            padding: { top: 10, right: 10, bottom: 10, left: 10 }
                        },
                        plugins: { 
                            legend: { display: false },
                            tooltip: {
                                enabled: true,
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
                                    maxTicksLimit: 5,
                                    font: { size: 10 }
                                },
                                afterFit: (scale) => { scale.width = 60; },
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }
                            },
                            x: {
                                ticks: {
                                    autoSkip: true,
                                    maxRotation: 0,
                                    minRotation: 0,
                                    font: { size: 11 }
                                },
                                grid: {
                                    display: false
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
                if (dashboardState.graficoBandeirasRetryCount < MAX_GRAFICO_RETRY) {
                    dashboardState.graficoBandeirasRetryCount++;
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
            dashboardState.graficoBandeirasRetryCount = 0;
            
            const labels = Object.keys(bandeiras || {});
            
            if (!labels.length) {
                if (container) {
                    container.innerHTML = '<p class="nc-empty-state" style="text-align:center;color:var(--gray-dark);padding:2rem">Sem dados para exibir</p>';
                }
                return;
            }
            
            const valores = labels.map(l => {
                const item = bandeiras[l];
                return parseFloat(item?.total || item?.vendas || 0);
            });
            
            // Destruir gráfico anterior se existir
            if (dashboardState.graficoBandeiras) {
                dashboardState.graficoBandeiras.destroy();
                dashboardState.graficoBandeiras = null;
            }
            
            // Cores para bandeiras
            const colors = {
                'Visa': '#1877f2',
                'Mastercard': '#eb001b',
                'Elo': '#ffc600',
                'Amex': '#007cc3',
                'Hipercard': '#00a650',
                'outros': '#6c757d'
            };
            
            const backgroundColors = labels.map(l => 
                colors[l] || colors['outros']
            );
            
            try {
                dashboardState.graficoBandeiras = new Chart(ctx, {
                    type: "doughnut",
                    data: {
                        labels,
                        datasets: [{
                            label: "Vendas por Bandeira",
                            data: valores,
                            backgroundColor: backgroundColors,
                            borderWidth: 2,
                            borderColor: '#fff',
                            hoverOffset: 8
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {
                            animateRotate: true,
                            animateScale: true,
                            duration: 600
                        },
                        layout: {
                            padding: { top: 10, right: 10, bottom: 10, left: 10 }
                        },
                        plugins: {
                            legend: { 
                                position: "bottom",
                                labels: {
                                    padding: 15,
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    boxWidth: 10,
                                    font: { size: 10, family: 'system-ui, -apple-system, sans-serif' },
                                    generateLabels: (chart) => {
                                        const data = chart.data;
                                        return data.labels.map((label, i) => ({
                                            text: `${label}: ${formatCurrency(data.datasets[0].data[i])}`,
                                            fillStyle: chart.data.datasets[0].backgroundColor[i],
                                            strokeStyle: '#fff',
                                            lineWidth: 2,
                                            index: i,
                                            hidden: !chart.getDataVisibility(i)
                                        }));
                                    }
                                }
                            },
                            tooltip: {
                                enabled: true,
                                callbacks: {
                                    label: (context) => {
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                        return `${label}: ${formatCurrency(value)} (${percentage}%)`;
                                    }
                                }
                            }
                        },
                        cutout: '60%'
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
            
            // Focar no botão de fechar para acessibilidade
            const closeBtn = modal.querySelector('.nc-modal-close');
            if (closeBtn) closeBtn.focus();
            
            // Setup focus trap
            setupModalFocusTrap(modal);
            
            // Prevenir scroll do body
            document.body.style.overflow = 'hidden';
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
            
            // Remover focus trap
            if (modal._focusTrapHandler) {
                modal.removeEventListener('keydown', modal._focusTrapHandler);
                delete modal._focusTrapHandler;
            }
            
            // Restaurar scroll do body
            document.body.style.overflow = '';
            
            // Focar no último elemento interativo antes do modal abrir (se possível)
            const lastFocused = modal._lastFocusedElement;
            if (lastFocused && typeof lastFocused.focus === 'function') {
                lastFocused.focus();
            }
        };
        
        // ================== CLIQUES NOS KPIs ==================
        document.querySelectorAll(".kpi-click").forEach(card => {
            card.addEventListener("click", () => {
                if (!dashboardState.ultimoKpis) return;
                const acao = card.dataset.acao;
                
                if (acao === "vendas") {
                    abrirModal("Detalhamento de Vendas", dashboardState.ultimoKpis.detalhamento?.vendas || []);
                } else if (acao === "recebidos") {
                    abrirModal("Detalhamento de Recebimentos", dashboardState.ultimoKpis.detalhamento?.recebidos || []);
                } else if (acao === "diferencas") {
                    abrirModal("Diferenças (vendas ainda não conciliadas)", dashboardState.ultimoKpis.detalhamento?.pendentes || []);
                }
            });
        });
        
        // ================== EVENT LISTENERS PARA FILTROS ==================
        // Aplicar filtros ao mudar valores
        ['filtroInicio', 'filtroFim', 'filtroTipoPagamento'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    // Debounce para evitar múltiplas chamadas rápidas
                    clearTimeout(window._filterTimeout);
                    window._filterTimeout = setTimeout(() => {
                        carregarKPIs();
                    }, 300);
                });
            }
        });
        
        // ================== REDIMENSIONAR GRÁFICOS AO REDIMENSIONAR JANELA ==================
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                if (dashboardState.graficoVendas && dashboardState.ultimoKpis) {
                    atualizarGraficoVendas(dashboardState.ultimoKpis, ctxGrafico);
                }
                if (dashboardState.graficoBandeiras && dashboardState.ultimoKpis?.bandeiras) {
                    atualizarGraficoBandeiras(dashboardState.ultimoKpis.bandeiras, ctxBandeiras);
                }
            }, 250);
        });
        
        // ================== INICIAR LOOP DE ATUALIZAÇÃO ==================
        // Carregar dados iniciais
        carregarKPIs();
        
        // Configurar auto-refresh
        if (dashboardState.kpiInterval) clearInterval(dashboardState.kpiInterval);
        dashboardState.kpiInterval = setInterval(() => {
            // Só auto-refresh se aba estiver visível
            if (!document.hidden && !dashboardState.isLoading) {
                carregarKPIs();
            }
        }, AUTO_REFRESH_INTERVAL);
        
        // Pausar auto-refresh quando aba não estiver visível
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('📴 Aba oculta, pausando auto-refresh');
            } else {
                console.log('📱 Aba visível, retomando auto-refresh');
                if (!dashboardState.isLoading) {
                    carregarKPIs(); // Recarregar ao voltar
                }
            }
        });
        
        // ================== CLEANUP NO UNLOAD ==================
        function cleanup() {
            console.log('🧹 Limpando recursos do dashboard');
            
            if (dashboardState.kpiInterval) {
                clearInterval(dashboardState.kpiInterval);
                dashboardState.kpiInterval = null;
            }
            if (dashboardState.graficoVendas) {
                dashboardState.graficoVendas.destroy();
                dashboardState.graficoVendas = null;
            }
            if (dashboardState.graficoBandeiras) {
                dashboardState.graficoBandeiras.destroy();
                dashboardState.graficoBandeiras = null;
            }
            clearTimeout(resizeTimeout);
            clearTimeout(window._filterTimeout);
            
            // Remover listeners globais
            window.removeEventListener('resize', arguments.callee);
        }
        
        window.addEventListener('beforeunload', cleanup);
        
        // ✅ Expor funções de cleanup para uso externo se necessário
        window.cleanupDashboard = cleanup;
        
        console.log('✅ Dashboard inicializado com sucesso');
    });
    
})();
