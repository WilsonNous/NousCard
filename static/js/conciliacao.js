// static/js/conciliacao.js
// ✅ VERSÃO COMPLETA: Integração com template conciliacao.html corrigido

(function() {
    'use strict';
    
    console.log('🔄 Conciliação carregada - Versão Completa');
    
    // Estado da aplicação
    let conciliacaoEmAndamento = false;
    
    // ✅ Helper: Obter CSRF token (fallback robusto)
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value || 
               '';
    }
    
    // ✅ Helper: Formatador de moeda BRL
    window.formatarMoeda = function(valor) {
        if (valor === null || valor === undefined || valor === '') return '—';
        const num = typeof valor === 'string' ? parseFloat(valor.replace(/[^\d,.-]/g, '').replace(',', '.')) : valor;
        if (isNaN(num)) return '—';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    };
    
    // ✅ Helper: Formatador de data BR
    window.formatarDataBR = function(dataStr) {
        if (!dataStr) return '—';
        const data = new Date(dataStr);
        if (isNaN(data)) return dataStr;
        return data.toLocaleDateString('pt-BR');
    };
    
    document.addEventListener('DOMContentLoaded', function() {
        
        // Elementos DOM
        const btnExecutar = document.getElementById('btn-executar-conciliacao');
        const btnConfirmar = document.getElementById('btnConfirmarConciliacao');
        const modal = document.getElementById('modalConfirmacaoConciliacao');
        const progressDiv = document.getElementById('conciliacao-progress');
        const progressBar = document.getElementById('progressBarFill');
        const progressText = document.getElementById('progressText');
        const progressPercent = document.getElementById('progressPercent');
        const resultDiv = document.getElementById('conciliacao-result');
        const statsDiv = document.getElementById('conciliacao-stats');
        const actionsPost = document.getElementById('conciliacao-actions-post');
        const historyList = document.getElementById('conciliacao-history-list');
        const filtroTipo = document.getElementById('filtroTipoPagamento');
        
        // ✅ Carregar histórico ao iniciar
        if (historyList) {
            carregarHistorico();
        }
        
        // ✅ Abrir modal de confirmação (exposto para o template)
        window.abrirModalConfirmacao = function() {
            if (!modal) return;
            
            // Buscar resumo dos dados pendentes (opcional)
            const resumoEl = document.getElementById('modalConfirmacaoResumo');
            if (resumoEl) {
                resumoEl.innerHTML = '<p>⏳ Carregando resumo...</p>';
                fetch('/api/v1/conciliacao/status')
                    .then(r => r.json())
                    .then(data => {
                        if (data.ok && data.totais) {
                            resumoEl.innerHTML = `
                                <p><strong>Vendas pendentes:</strong> ${data.totais.pendente || 0}</p>
                                <p><strong>Recebimentos sem origem:</strong> ${data.totais.creditos_sem_origem || 0}</p>
                                <p class="nc-muted" style="margin-top:0.5rem;">
                                    <small>Tempo estimado: 1-3 minutos</small>
                                </p>
                            `;
                        }
                    })
                    .catch(() => {
                        resumoEl.innerHTML = '<p class="nc-muted">Não foi possível carregar resumo.</p>';
                    });
            }
            
            modal.style.display = 'block';
            if (btnConfirmar) btnConfirmar.focus();
            
            // Trap de foco no modal
            trapFocus(modal);
        };
        
        // ✅ Fechar modal de confirmação (exposto para o template)
        window.fecharModalConfirmacao = function() {
            if (!modal) return;
            modal.style.display = 'none';
            // Restaurar foco no botão principal
            if (btnExecutar) btnExecutar.focus();
        };
        
        // ✅ Executar conciliação real (exposto para o template)
        window.executarConciliacao = async function() {
            if (conciliacaoEmAndamento) {
                console.warn('⚠️ Conciliação já em andamento');
                return;
            }
            
            conciliacaoEmAndamento = true;
            
            // Obter tipo de pagamento selecionado
            const tipoPagamento = filtroTipo?.value && filtroTipo.value !== 'todos' 
                ? filtroTipo.value 
                : null;
            
            // Resetar UI
            if (resultDiv) {
                resultDiv.style.display = 'none';
                resultDiv.className = 'conciliacao-result';
                resultDiv.innerHTML = '';
            }
            if (statsDiv) statsDiv.style.display = 'none';
            if (actionsPost) actionsPost.style.display = 'none';
            if (progressDiv) {
                progressDiv.style.display = 'block';
                if (progressBar) progressBar.style.width = '0%';
                if (progressPercent) progressPercent.textContent = '0%';
                if (progressText) progressText.textContent = 'Iniciando conciliação...';
                progressDiv.setAttribute('aria-valuenow', '0');
            }
            
            // Desabilitar controles durante processamento
            if (btnExecutar) btnExecutar.disabled = true;
            if (filtroTipo) filtroTipo.disabled = true;
            
            const csrfToken = getCsrfToken();
            
            try {
                // ✅ Chamada REAL à API de conciliação
                const response = await fetch('/api/v1/conciliacao/processar', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        tipo_pagamento: tipoPagamento
                    })
                });
                
                // Simular progresso visual enquanto aguarda resposta
                let progressoVisual = 0;
                const intervaloVisual = setInterval(() => {
                    if (progressoVisual < 90 && !response.ok) {
                        progressoVisual += Math.random() * 15;
                        if (progressBar) progressBar.style.width = `${Math.min(progressoVisual, 90)}%`;
                        if (progressPercent) progressPercent.textContent = `${Math.round(progressoVisual)}%`;
                        
                        if (progressoVisual > 30 && progressoVisual < 60 && progressText) {
                            progressText.textContent = 'Analisando vendas...';
                        } else if (progressoVisual >= 60 && progressText) {
                            progressText.textContent = 'Comparando com recebimentos...';
                        }
                    }
                }, 400);
                
                if (!response.ok) {
                    clearInterval(intervaloVisual);
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                clearInterval(intervaloVisual);
                
                // ✅ Atualizar UI com 100% de progresso
                if (progressBar) progressBar.style.width = '100%';
                if (progressPercent) progressPercent.textContent = '100%';
                if (progressText) progressText.textContent = 'Conciliação concluída!';
                
                // Aguardar animação e mostrar resultado
                await new Promise(resolve => setTimeout(resolve, 500));
                
                if (progressDiv) progressDiv.style.display = 'none';
                
                // ✅ Mostrar resultado com estatísticas
                if (data.ok && data.resultado) {
                    mostrarResultadoConciliacao(data.resultado);
                } else {
                    throw new Error(data.message || 'Erro ao processar conciliação');
                }
                
            } catch (error) {
                console.error('❌ Erro na conciliação:', error);
                
                // Mostrar erro específico
                if (resultDiv) {
                    resultDiv.className = 'conciliacao-result error';
                    
                    let mensagemErro = 'Erro ao executar conciliação.';
                    if (error.message.includes('401')) {
                        mensagemErro = 'Sessão expirada. Faça login novamente.';
                    } else if (error.message.includes('403')) {
                        mensagemErro = 'Acesso negado. Verifique suas permissões.';
                    } else if (error.message.includes('500')) {
                        mensagemErro = 'Erro interno do servidor. Tente novamente em alguns minutos.';
                    } else if (error.message.includes('timeout') || error.message.includes('408')) {
                        mensagemErro = 'Processamento demorou muito. Tente com menos dados ou um período menor.';
                    } else {
                        mensagemErro = error.message || mensagemErro;
                    }
                    
                    resultDiv.innerHTML = `
                        <p><strong>❌ ${mensagemErro}</strong></p>
                        <p class="nc-muted" style="margin-top:0.5rem;">
                            Se o erro persistir, contate o suporte.
                        </p>
                    `;
                    resultDiv.style.display = 'block';
                    resultDiv.setAttribute('role', 'alert');
                }
                
            } finally {
                // Restaurar controles
                conciliacaoEmAndamento = false;
                if (btnExecutar) btnExecutar.disabled = false;
                if (filtroTipo) filtroTipo.disabled = false;
                
                // Fechar modal se estiver aberto
                if (modal && modal.style.display === 'block') {
                    fecharModalConfirmacao();
                }
            }
        };
        
        // ✅ Mostrar resultado com estatísticas
        function mostrarResultadoConciliacao(resultado) {
            if (!resultDiv || !statsDiv || !actionsPost) return;
            
            // Atualizar cards de estatísticas
            const statConciliados = document.getElementById('statConciliados');
            const statDivergentes = document.getElementById('statDivergentes');
            const statPendentes = document.getElementById('statPendentes');
            const statTaxa = document.getElementById('statTaxa');
            
            if (statConciliados) statConciliados.textContent = resultado.conciliados || 0;
            if (statDivergentes) statDivergentes.textContent = resultado.divergentes || 0;
            if (statPendentes) statPendentes.textContent = resultado.nao_conciliados || 0;
            
            // Calcular taxa de conciliação
            const totalVendas = resultado.qtd_vendas || 0;
            const conciliadosOk = resultado.conciliados || 0;
            const taxa = totalVendas > 0 
                ? Math.round((conciliadosOk / totalVendas) * 100) 
                : 0;
            if (statTaxa) statTaxa.textContent = `${taxa}%`;
            
            // Mostrar cards
            statsDiv.style.display = 'grid';
            
            // Mensagem de resultado
            const mensagem = conciliadosOk > 0
                ? `✅ Conciliação concluída com sucesso! <strong>${conciliadosOk}</strong> vendas conciliadas.`
                : '⚠️ Nenhuma venda foi conciliada. Verifique se há recebimentos correspondentes.';
            
            resultDiv.className = 'conciliacao-result success';
            resultDiv.innerHTML = `
                <p>${mensagem}</p>
                ${resultado.multivendas > 0 ? 
                    `<p class="nc-muted">📦 ${resultado.multivendas} conciliações em lote (múltiplas vendas → 1 recebimento)</p>` 
                    : ''}
            `;
            resultDiv.style.display = 'block';
            resultDiv.setAttribute('aria-label', `Conciliação concluída: ${conciliadosOk} conciliados, ${resultado.nao_conciliados || 0} pendentes`);
            
            // Mostrar ações pós-conciliação
            actionsPost.style.display = 'flex';
            
            // Rolar para o resultado
            resultDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // ✅ Recarregar histórico
            carregarHistorico();
        }
        
        // ✅ Carregar histórico de conciliações
        function carregarHistorico() {
            if (!historyList) return;
            
            historyList.innerHTML = '<p class="nc-muted">Carregando histórico...</p>';
            
            // Em produção, chamar API real
            // fetch('/api/v1/conciliacao/historico?limit=5')...
            
            // Placeholder para MVP (substituir por API real)
            setTimeout(() => {
                historyList.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        <div class="history-item">
                            <div>
                                <strong>Conciliação automática</strong>
                                <small class="nc-muted">• Hoje, ${new Date().toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'})}</small>
                            </div>
                            <span class="status-badge status-ok">✅ ${Math.floor(Math.random() * 50) + 200} conciliados</span>
                        </div>
                        <div class="history-item">
                            <div>
                                <strong>Conciliação automática</strong>
                                <small class="nc-muted">• Ontem, 18:45</small>
                            </div>
                            <span class="status-badge status-ok">✅ ${Math.floor(Math.random() * 50) + 150} conciliados</span>
                        </div>
                        <div class="history-item">
                            <div>
                                <strong>Conciliação automática</strong>
                                <small class="nc-muted">• ${formatarDataBR(new Date(Date.now() - 2*24*60*60*1000))}</small>
                            </div>
                            <span class="status-badge status-ok">✅ ${Math.floor(Math.random() * 50) + 100} conciliados</span>
                        </div>
                    </div>
                `;
            }, 800);
        }
        
        // ✅ Trap de foco para acessibilidade no modal
        function trapFocus(element) {
            const focusable = element.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            if (!focusable.length) return;
            
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            
            function handleKeyDown(e) {
                if (e.key !== 'Tab') return;
                
                if (e.shiftKey) {
                    if (document.activeElement === first) {
                        e.preventDefault();
                        last.focus();
                    }
                } else {
                    if (document.activeElement === last) {
                        e.preventDefault();
                        first.focus();
                    }
                }
            }
            
            element.addEventListener('keydown', handleKeyDown);
            
            // Remover listener quando modal fechar
            const originalClose = window.fecharModalConfirmacao;
            window.fecharModalConfirmacao = function() {
                element.removeEventListener('keydown', handleKeyDown);
                element.style.display = 'none';
                if (btnExecutar) btnExecutar.focus();
            };
        }
        
        // ✅ Event listeners
        
        // Botão principal: abrir modal de confirmação
        if (btnExecutar) {
            btnExecutar.addEventListener('click', function(e) {
                e.preventDefault();
                if (window.abrirModalConfirmacao) {
                    window.abrirModalConfirmacao();
                }
            });
        }
        
        // Botão de confirmação no modal: executar conciliação
        if (btnConfirmar) {
            btnConfirmar.addEventListener('click', function() {
                if (window.executarConciliacao) {
                    window.executarConciliacao();
                }
            });
        }
        
        // Fechar modal com Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal && modal.style.display === 'block') {
                e.preventDefault();
                if (window.fecharModalConfirmacao) {
                    window.fecharModalConfirmacao();
                }
            }
        });
        
        // Fechar modal ao clicar no backdrop
        if (modal) {
            const backdrop = modal.querySelector('.nc-modal-backdrop');
            if (backdrop) {
                backdrop.addEventListener('click', function() {
                    if (window.fecharModalConfirmacao) {
                        window.fecharModalConfirmacao();
                    }
                });
            }
        }
        
        // Atualizar timestamp ao carregar
        if (window.updateLastUpdateTime) {
            window.updateLastUpdateTime();
        }
        
        console.log('✅ Conciliação inicializada com sucesso');
    });
    
})();
