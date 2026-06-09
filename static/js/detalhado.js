// ============================================================
//  DETALHADO • NousCard (VERSÃO SEGURA E COMPLETA)
// ============================================================
// ✅ Integração total com templates HTML corrigidos

(function() {
    'use strict';
    
    console.log('🔄 Detalhado carregado - Versão Completa');
    
    // Estado da aplicação
    let detalhadoState = {
        isLoading: false,
        currentFilters: {},
        allData: [], // Para exportação e busca client-side
        retryCount: 0,
        MAX_RETRY: 3
    };
    
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
    
    // ✅ Helper: Formatador de moeda BRL com precisão
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
    
    // ✅ Helper: Obter empresa_id de forma segura
    function getEmpresaId() {
        return document.body.dataset.empresaId || null;
    }
    
    // ✅ Helper: Construir query params com sanitização
    function buildQueryParams(filters = {}) {
        const params = new URLSearchParams();
        
        // Filtros de período
        if (filters.data_inicio) params.append('data_inicio', filters.data_inicio);
        if (filters.data_fim) params.append('data_fim', filters.data_fim);
        
        // Filtros de status e tipo
        if (filters.status && filters.status !== 'todos') {
            params.append('status', filters.status);
        }
        if (filters.tipo_pagamento && filters.tipo_pagamento !== 'todos') {
            params.append('tipo_pagamento', filters.tipo_pagamento);
        }
        
        // Filtros de adquirente e busca
        if (filters.adquirente && filters.adquirente !== 'todos') {
            params.append('adquirente', filters.adquirente);
        }
        if (filters.busca) {
            params.append('busca', filters.busca);
        }
        
        // Paginação
        if (filters.page) params.append('page', filters.page);
        if (filters.per_page) params.append('per_page', filters.per_page);
        
        return params.toString();
    }
    
    // ✅ Helper: Obter filtros atuais do DOM
    function getCurrentFilters() {
        return {
            data_inicio: document.getElementById('filtroDataInicio')?.value,
            data_fim: document.getElementById('filtroDataFim')?.value,
            status: document.getElementById('filtroStatus')?.value,
            tipo_pagamento: document.getElementById('filtroTipoPagamento')?.value || 'todos',
            adquirente: document.getElementById('filtroAdquirente')?.value,
            busca: document.getElementById('filtroBusca')?.value,
            page: 1, // Resetar página ao mudar filtros
            per_page: 50
        };
    }
    
    document.addEventListener("DOMContentLoaded", () => {
        // Elementos do DOM com verificação de segurança
        const container = document.getElementById("detalhadoContainer");
        const paginationContainer = document.getElementById("paginationContainer");
        const statsContainer = document.getElementById("detalhadoStats");
        const loadingIndicator = document.getElementById('detalhado-loading');
        
        // ✅ Carregar dados iniciais
        carregarDetalhado();
        
        // ✅ Event listeners para filtros
        setupFilterListeners();
        
        // ✅ Botão de refresh
        const btnRefresh = document.getElementById('btn-refresh');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => {
                detalhadoState.currentFilters.page = 1;
                carregarDetalhado(detalhadoState.currentFilters);
            });
        }
        
        // ✅ Botão de exportar CSV
        const btnExport = document.getElementById('btn-export-csv');
        if (btnExport) {
            btnExport.addEventListener('click', exportarCSV);
        }
        
        // ✅ Cleanup ao navegar para outra página
        window.addEventListener('beforeunload', cleanup);
        
        console.log('✅ Detalhado inicializado com sucesso');
    });
    
    // ============================================================
    // CARREGAR DADOS DA API
    // ============================================================
    
    async function carregarDetalhado(filtros = null) {
        // Prevenir múltiplas chamadas simultâneas
        if (detalhadoState.isLoading) {
            console.log('⏳ Carregamento já em andamento, ignorando nova requisição');
            return;
        }
        
        detalhadoState.isLoading = true;
        
        const container = document.getElementById("detalhadoContainer");
        const empresaId = getEmpresaId();
        
        // Validar empresa_id
        if (!empresaId) {
            container.innerHTML = `
                <div class="error-state" role="alert">
                    <p>⚠️ Empresa não identificada. <a href="/auth/login">Faça login novamente</a>.</p>
                </div>
            `;
            detalhadoState.isLoading = false;
            return;
        }
        
        // Mostrar loading state acessível
        if (container) {
            container.innerHTML = `
                <div class="nc-loading" role="status" aria-live="polite" aria-busy="true">
                    <span class="spinner" aria-hidden="true"></span>
                    <span>Carregando dados de detalhamento...</span>
                </div>
            `;
        }
        
        // Usar filtros passados ou obter do DOM
        const activeFilters = filtros || getCurrentFilters();
        detalhadoState.currentFilters = { ...activeFilters };
        
        const queryString = buildQueryParams(activeFilters);
        const url = `/api/v1/conciliacao/detalhes?${queryString}`;
        
        console.log(`📡 Fetching detalhado: ${url}`);
        
        try {
            const res = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken()
                },
                signal: AbortSignal.timeout(30000) // Timeout de 30s
            });
            
            if (!res.ok) {
                // ✅ Tratamento de erro específico por código HTTP
                let errorMsg = `HTTP ${res.status}: ${res.statusText}`;
                
                if (res.status === 401) {
                    errorMsg = 'Sessão expirada. Redirecionando para login...';
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
                throw new Error(data.message || 'Erro ao carregar dados');
            }
            
            // Resetar contador de retry quando dados chegam com sucesso
            detalhadoState.retryCount = 0;
            
            // Armazenar dados para exportação e busca client-side
            detalhadoState.allData = data.dados.registros || [];
            
            // Atualizar UI
            montarTabela(data.dados.registros || [], {
                page: data.dados.page || 1,
                per_page: data.dados.per_page || 50,
                total: data.dados.total || 0,
                pages: data.dados.pages || 1
            });
            
            // Atualizar estatísticas se container existir
            if (statsContainer && data.dados.resumo) {
                atualizarEstatisticas(data.dados.resumo);
            }
            
            // Atualizar info de paginação
            atualizarPaginacao(data.dados);
            
            // Atualizar timestamp se função existir
            if (window.updateLastUpdateTime) {
                window.updateLastUpdateTime();
            }
            
        } catch (err) {
            console.error("❌ Erro ao carregar detalhado:", err);
            
            // ✅ Implementar retry com backoff exponencial para erros de rede
            if ((err.name === 'TimeoutError' || err.message.includes('Failed to fetch')) && 
                detalhadoState.retryCount < detalhadoState.MAX_RETRY) {
                
                detalhadoState.retryCount++;
                const delay = Math.min(1000 * Math.pow(2, detalhadoState.retryCount), 10000);
                
                console.log(`🔄 Tentando retry ${detalhadoState.retryCount}/${detalhadoState.MAX_RETRY} em ${delay}ms...`);
                
                setTimeout(() => {
                    if (!document.hidden) {
                        carregarDetalhado(activeFilters);
                    }
                }, delay);
                
                return;
            }
            
            // Mostrar erro amigável ao usuário
            if (container) {
                container.innerHTML = `
                    <div class="error-state" role="alert">
                        <h3>❌ Erro ao carregar dados</h3>
                        <p>${err.message || 'Não foi possível carregar os dados'}</p>
                        <button type="button" class="nc-btn nc-btn-primary" onclick="carregarDetalhado()">
                            🔄 Tentar Novamente
                        </button>
                    </div>
                `;
                container.setAttribute('aria-busy', 'false');
            }
            
        } finally {
            detalhadoState.isLoading = false;
            
            // Esconder indicador de loading
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        }
    }
    
    // ✅ Expor função globalmente para o template HTML
    window.carregarDetalhado = carregarDetalhado;
    
    // ============================================================
    // MONTAR TABELA (SEGURO + ACESSÍVEL)
    // ============================================================
    
    function montarTabela(linhas, pagination = {}) {
        const container = document.getElementById("detalhadoContainer");
        
        if (!container) return;
        
        // Estado vazio
        if (!linhas || !linhas.length) {
            container.innerHTML = `
                <div class="empty-state" role="status">
                    <span aria-hidden="true" style="font-size: 3rem;">📭</span>
                    <h3>Nenhum dado encontrado</h3>
                    <p>Não há registros de conciliação para os filtros selecionados.</p>
                    <button type="button" class="nc-btn nc-btn-outline" onclick="limparFiltros()">
                        🧹 Limpar Filtros
                    </button>
                </div>
            `;
            return;
        }
        
        // Criar tabela com elementos DOM (não string interpolation)
        const table = document.createElement('table');
        table.className = 'detalhado-table';
        table.setAttribute('role', 'table');
        table.setAttribute('aria-label', 'Tabela de detalhamento de conciliação linha por linha');
        
        // Thead com headers acessíveis
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        const cols = [
            { key: 'data_venda', label: 'Data Venda', class: 'date' },
            { key: 'nsu', label: 'NSU' },
            { key: 'adquirente', label: 'Adquirente' },
            { key: 'bandeira', label: 'Bandeira' },
            { key: 'produto', label: 'Produto' },
            { key: 'parcela', label: 'Parcela' },
            { key: 'valor_bruto', label: 'Valor Bruto', class: 'valor' },
            { key: 'valor_liquido', label: 'Valor Líquido', class: 'valor' },
            { key: 'valor_recebido', label: 'Recebido', class: 'valor' },
            { key: 'diferenca', label: 'Diferença', class: 'valor' },
            { key: 'status_conciliacao', label: 'Status', class: 'status' },
            { key: 'tipo_pagamento', label: 'Tipo' }
        ];
        
        cols.forEach(col => {
            const th = document.createElement('th');
            th.scope = 'col';
            th.textContent = col.label;
            if (col.class) th.className = col.class;
            th.setAttribute('aria-sort', 'none');
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Tbody com dados (usando textContent para segurança)
        const tbody = document.createElement('tbody');
        
        linhas.forEach(row => {
            const tr = document.createElement('tr');
            
            // Calcular diferença com precisão
            const liquido = parseFloat(row.valor_liquido) || 0;
            const recebido = parseFloat(row.valor_recebido) || 0;
            const diff = liquido - recebido;
            
            // Status class e cor
            const status = row.status_conciliacao || 'pendente';
            const statusClass = status === "conciliado"
                ? "status-conciliado"
                : status === "parcial"
                ? "status-parcial"
                : "status-pendente";
            
            const diffColor = diff === 0 ? "#16a34a" : "#dc2626";
            
            // Criar células com textContent (seguro contra XSS)
            cols.forEach(col => {
                const td = document.createElement('td');
                if (col.class) td.className = col.class;
                
                switch(col.key) {
                    case 'data_venda':
                        td.textContent = formatDateBR(row.data_venda);
                        break;
                        
                    case 'valor_bruto':
                    case 'valor_liquido':
                    case 'valor_recebido':
                        td.textContent = formatCurrency(row[col.key]);
                        break;
                        
                    case 'diferenca':
                        td.textContent = formatCurrency(diff);
                        td.style.color = diffColor;
                        td.style.fontWeight = diff !== 0 ? '600' : 'normal';
                        break;
                        
                    case 'status_conciliacao':
                        td.textContent = status === 'conciliado' ? '✅ Conciliado' : 
                                        status === 'parcial' ? '⚠️ Parcial' : '⏳ Pendente';
                        td.className = `status ${statusClass}`;
                        break;
                        
                    case 'parcela':
                        td.textContent = row.parcela || '1/1';
                        break;
                        
                    default:
                        td.textContent = row[col.key] !== undefined && row[col.key] !== null 
                            ? String(row[col.key]) 
                            : '—';
                }
                
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        
        // Limpar container e adicionar tabela
        container.innerHTML = '';
        container.appendChild(table);
        container.setAttribute('aria-busy', 'false');
    }
    
    // ============================================================
    // ATUALIZAR ESTATÍSTICAS
    // ============================================================
    
    function atualizarEstatisticas(resumo) {
        if (!statsContainer || !resumo) return;
        
        // Atualizar cards de estatísticas
        const statConciliados = document.getElementById('statConciliados');
        const statPendentes = document.getElementById('statPendentes');
        const statParciais = document.getElementById('statParciais');
        const statTotalValor = document.getElementById('statTotalValor');
        
        if (statConciliados) statConciliados.textContent = resumo.conciliados || 0;
        if (statPendentes) statPendentes.textContent = resumo.pendentes || 0;
        if (statParciais) statParciais.textContent = resumo.parciais || 0;
        if (statTotalValor) statTotalValor.textContent = formatCurrency(resumo.total_valor || 0);
        
        // Mostrar container se estava oculto
        statsContainer.style.display = 'grid';
    }
    
    // ============================================================
    // ATUALIZAR PAGINAÇÃO
    // ============================================================
    
    function atualizarPaginacao(dados) {
        const paginationContainer = document.getElementById("paginationContainer");
        if (!paginationContainer) return;
        
        const { page, pages, total } = dados;
        
        // Atualizar info de página
        const currentPageEl = document.getElementById('currentPage');
        const totalPagesEl = document.getElementById('totalPages');
        const registroInfoEl = document.getElementById('registroInfo');
        
        if (currentPageEl) currentPageEl.textContent = page;
        if (totalPagesEl) totalPagesEl.textContent = pages;
        if (registroInfoEl) registroInfoEl.textContent = `(${total} registros)`;
        
        // Atualizar botões
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        
        if (btnPrev) {
            btnPrev.disabled = page <= 1;
            btnPrev.onclick = page > 1 ? () => {
                carregarDetalhado({ ...detalhadoState.currentFilters, page: page - 1 });
            } : null;
        }
        
        if (btnNext) {
            btnNext.disabled = page >= pages;
            btnNext.onclick = page < pages ? () => {
                carregarDetalhado({ ...detalhadoState.currentFilters, page: page + 1 });
            } : null;
        }
        
        // Mostrar/ocultar container de paginação
        paginationContainer.style.display = pages > 1 ? 'flex' : 'none';
    }
    
    // ============================================================
    // SETUP DE EVENT LISTENERS PARA FILTROS
    // ============================================================
    
    function setupFilterListeners() {
        // Debounce para evitar múltiplas chamadas rápidas
        let searchTimeout;
        
        // Filtros que disparam recarregamento imediato
        ['filtroStatus', 'filtroTipoPagamento', 'filtroAdquirente'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        detalhadoState.currentFilters.page = 1;
                        carregarDetalhado(getCurrentFilters());
                    }, 300);
                });
            }
        });
        
        // Filtros de data com debounce mais longo
        ['filtroDataInicio', 'filtroDataFim'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        detalhadoState.currentFilters.page = 1;
                        carregarDetalhado(getCurrentFilters());
                    }, 500);
                });
            }
        });
        
        // Busca em tempo real com debounce
        const buscaInput = document.getElementById('filtroBusca');
        if (buscaInput) {
            buscaInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    detalhadoState.currentFilters.page = 1;
                    carregarDetalhado(getCurrentFilters());
                }, 400);
            });
        }
    }
    
    // ============================================================
    // LIMPAR FILTROS
    // ============================================================
    
    window.limparFiltros = function() {
        // Resetar inputs do DOM
        ['filtroDataInicio', 'filtroDataFim', 'filtroStatus', 'filtroTipoPagamento', 'filtroAdquirente', 'filtroBusca'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                if (el.tagName === 'SELECT') {
                    el.selectedIndex = 0;
                } else {
                    el.value = '';
                }
            }
        });
        
        // Resetar estado e recarregar
        detalhadoState.currentFilters = { ...getCurrentFilters(), page: 1 };
        carregarDetalhado(detalhadoState.currentFilters);
    };
    
    // Expor globalmente
    window.limparFiltros = limparFiltros;
    
    // ============================================================
    // EXPORTAR CSV
    // ============================================================
    
    function exportarCSV() {
        const dados = detalhadoState.allData;
        
        if (!dados || !dados.length) {
            alert('Nenhum dado para exportar.');
            return;
        }
        
        // Cabeçalhos
        const headers = [
            'Data Venda', 'NSU', 'Adquirente', 'Bandeira', 'Produto', 'Parcela',
            'Valor Bruto', 'Valor Líquido', 'Recebido', 'Diferença', 'Status', 'Tipo'
        ];
        
        // Linhas de dados
        const rows = dados.map(row => {
            const liquido = parseFloat(row.valor_liquido) || 0;
            const recebido = parseFloat(row.valor_recebido) || 0;
            const diff = liquido - recebido;
            
            return [
                formatDateBR(row.data_venda),
                row.nsu || '',
                row.adquirente || '',
                row.bandeira || '',
                row.produto || '',
                row.parcela || '1/1',
                formatCurrency(row.valor_bruto),
                formatCurrency(row.valor_liquido),
                formatCurrency(recebido),
                formatCurrency(diff),
                row.status_conciliacao || 'pendente',
                row.tipo_pagamento || 'cartao'
            ].map(val => `"${String(val).replace(/"/g, '""')}"`).join(';');
        });
        
        // Montar CSV com BOM para Excel
        const csv = [
            '\ufeff' + headers.join(';'),
            ...rows
        ].join('\n');
        
        // Download
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `detalhamento_conciliacao_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    // ============================================================
    // CLEANUP DE RECURSOS
    // ============================================================
    
    function cleanup() {
        console.log('🧹 Limpando recursos do detalhado');
        
        // Limpar timeout de busca se existir
        if (window._searchTimeout) {
            clearTimeout(window._searchTimeout);
            delete window._searchTimeout;
        }
        
        // Resetar estado
        detalhadoState = {
            isLoading: false,
            currentFilters: {},
            allData: [],
            retryCount: 0,
            MAX_RETRY: 3
        };
    }
    
    // Expor cleanup globalmente
    window.cleanupDetalhado = cleanup;
    
})();
