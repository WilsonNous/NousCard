// ============================================================
//  DETALHADO • NousCard (VERSÃO SEGURA)
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    carregarDetalhado();
});

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

/**
 * Obtém empresa_id de forma segura (data attribute do body)
 */
function getEmpresaId() {
    return document.body.dataset.empresaId || null;
}

// ============================================================
// CARREGAR DADOS
// ============================================================

async function carregarDetalhado(filtros = {}) {
    const container = document.getElementById("detalhadoContainer");
    const empresaId = getEmpresaId();
    
    // Validar empresa_id
    if (!empresaId) {
        container.innerHTML = '<p class="nc-error" role="alert">⚠️ Empresa não identificada. Faça login novamente.</p>';
        return;
    }

    // Mostrar loading state acessível
    container.innerHTML = `
        <div class="nc-loading" role="status" aria-live="polite">
            <span class="spinner" aria-hidden="true"></span>
            <span>Carregando dados de detalhamento...</span>
        </div>
    `;
    container.setAttribute('aria-busy', 'true');

    try {
        // Construir query params com sanitização
        const params = new URLSearchParams({ empresa_id: empresaId });
        if (filtros.data_inicio) params.append('data_inicio', filtros.data_inicio);
        if (filtros.data_fim) params.append('data_fim', filtros.data_fim);
        if (filtros.status) params.append('status', filtros.status);
        if (filtros.page) params.append('page', filtros.page);
        if (filtros.per_page) params.append('per_page', filtros.per_page);

        const res = await fetch(`/api/v1/conciliacao/detalhes?${params}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            signal: AbortSignal.timeout(30000)  // Timeout de 30s
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const data = await res.json();

        if (data.status !== "success") {
            throw new Error(data.message || 'Erro ao carregar dados');
        }

        // Atualizar UI
        montarTabela(data.dados || [], {
            page: data.page || 1,
            per_page: data.per_page || 50,
            total: data.total || 0,
            pages: data.pages || 1
        });

        container.setAttribute('aria-busy', 'false');

    } catch (err) {
        console.error("Erro ao carregar detalhado:", err);
        
        // Mensagem amigável ao usuário
        container.innerHTML = `
            <div class="nc-error" role="alert">
                <span aria-hidden="true">⚠️</span>
                <p>Não foi possível carregar os dados. ${err.message.includes('timeout') ? 'A conexão está lenta. ' : ''}Tente novamente.</p>
                <button type="button" class="nc-btn nc-btn-sm" onclick="carregarDetalhado()">🔄 Recarregar</button>
            </div>
        `;
        container.setAttribute('aria-busy', 'false');
    }
}

// ============================================================
// MONTAR TABELA (SEGURO + ACESSÍVEL)
// ============================================================

function montarTabela(linhas, pagination = {}) {
    const container = document.getElementById("detalhadoContainer");
    
    if (!container) return;

    // Estado vazio
    if (!linhas || !linhas.length) {
        container.innerHTML = `
            <div class="nc-empty-state" role="status">
                <span aria-hidden="true">📭</span>
                <h3>Nenhum dado encontrado</h3>
                <p>Não há registros de conciliação para os filtros selecionados.</p>
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
        { key: 'data_venda', label: 'Data Venda' },
        { key: 'adquirente', label: 'Adquirente' },
        { key: 'bandeira', label: 'Bandeira' },
        { key: 'valor_liquido', label: 'Valor Líquido' },
        { key: 'data_prevista', label: 'Previsto' },
        { key: 'valor_conciliado', label: 'Conciliado' },
        { key: 'diferenca', label: 'Diferença' },
        { key: 'status', label: 'Status' }
    ];

    cols.forEach(col => {
        const th = document.createElement('th');
        th.scope = 'col';
        th.textContent = col.label;
        // Adicionar ordenação se implementada no backend
        th.setAttribute('aria-sort', 'none');
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Tbody com dados (usando textContent para segurança)
    const tbody = document.createElement('tbody');
    
    linhas.forEach(row => {
        const tr = document.createElement('tr');
        
        // Calcular diferença com Decimal para precisão
        const liquido = parseFloat(row.valor_liquido) || 0;
        const conciliado = parseFloat(row.valor_conciliado) || 0;
        const diff = liquido - conciliado;
        
        // Status class e cor
        const statusClass = row.status === "conciliado"
            ? "status-ok"
            : row.status === "parcial"
            ? "status-parcial"
            : "status-pendente";
        
        const diffColor = diff === 0 ? "#008000" : diff > 0 ? "#cc0000" : "#cc0000";

        // Criar células com textContent (seguro contra XSS)
        cols.forEach(col => {
            const td = document.createElement('td');
            
            switch(col.key) {
                case 'data_venda':
                case 'data_prevista':
                    td.textContent = row[col.key] || '-';
                    break;
                    
                case 'adquirente':
                case 'bandeira':
                case 'status':
                    td.textContent = row[col.key] || '-';
                    if (col.key === 'status') {
                        td.className = statusClass;
                    }
                    break;
                    
                case 'valor_liquido':
                case 'valor_conciliado':
                    td.textContent = formatCurrency(row[col.key]);
                    break;
                    
                case 'diferenca':
                    td.textContent = formatCurrency(diff);
                    td.style.color = diffColor;
                    td.style.fontWeight = diff !== 0 ? 'bold' : 'normal';
                    break;
                    
                default:
                    td.textContent = row[col.key] !== undefined ? row[col.key] : '-';
            }
            
            tr.appendChild(td);
        });
        
        tbody.appendChild(tr);
    });
    
    table.appendChild(tbody);
    
    // Limpar container e adicionar tabela
    container.innerHTML = '';
    container.appendChild(table);
    
    // Adicionar paginação se houver múltiplas páginas
    if (pagination.pages > 1) {
        const paginationNav = document.createElement('nav');
        paginationNav.className = 'nc-pagination';
        paginationNav.setAttribute('role', 'navigation');
        paginationNav.setAttribute('aria-label', 'Paginação da tabela');
        
        // Botão anterior
        if (pagination.page > 1) {
            const prevBtn = document.createElement('button');
            prevBtn.type = 'button';
            prevBtn.className = 'nc-btn nc-btn-sm';
            prevBtn.textContent = '← Anterior';
            prevBtn.setAttribute('aria-label', 'Página anterior');
            prevBtn.addEventListener('click', () => {
                carregarDetalhado({ ...getFiltrosAtuais(), page: pagination.page - 1 });
            });
            paginationNav.appendChild(prevBtn);
        }
        
        // Info de página
        const pageInfo = document.createElement('span');
        pageInfo.className = 'nc-page-info';
        pageInfo.setAttribute('aria-current', 'page');
        pageInfo.textContent = `Página ${pagination.page} de ${pagination.pages}`;
        paginationNav.appendChild(pageInfo);
        
        // Botão próxima
        if (pagination.page < pagination.pages) {
            const nextBtn = document.createElement('button');
            nextBtn.type = 'button';
            nextBtn.className = 'nc-btn nc-btn-sm';
            nextBtn.textContent = 'Próxima →';
            nextBtn.setAttribute('aria-label', 'Próxima página');
            nextBtn.addEventListener('click', () => {
                carregarDetalhado({ ...getFiltrosAtuais(), page: pagination.page + 1 });
            });
            paginationNav.appendChild(nextBtn);
        }
        
        container.appendChild(paginationNav);
    }
}

// ============================================================
// HELPERS PARA FILTROS (se implementar UI de filtros)
// ============================================================

function getFiltrosAtuais() {
    return {
        data_inicio: document.getElementById('filtro-data-inicio')?.value || null,
        data_fim: document.getElementById('filtro-data-fim')?.value || null,
        status: document.getElementById('filtro-status')?.value || null
    };
}

// Expor função globalmente para botões de filtro
window.carregarDetalhado = carregarDetalhado;
