// static/js/conciliacao.js
// MVP: Funcionalidade básica de conciliação

(function() {
    'use strict';
    
    console.log('🔄 Conciliação carregada - MVP Mode');
    
    document.addEventListener('DOMContentLoaded', function() {
        
        // ✅ CORREÇÃO: ID correto do botão no HTML
        const btnConciliar = document.getElementById('btn-executar-conciliacao');
        
        if (btnConciliar) {
            console.log('✅ Botão de conciliação encontrado');
            
            btnConciliar.addEventListener('click', async function(e) {
                e.preventDefault();
                
                // UI: Loading state
                const originalText = btnConciliar.innerHTML;
                btnConciliar.disabled = true;
                btnConciliar.innerHTML = '⏳ Processando...';
                
                // Mostrar progresso
                const progress = document.getElementById('conciliacao-progress');
                const result = document.getElementById('conciliacao-result');
                if (progress) progress.style.display = 'block';
                if (result) {
                    result.className = 'nc-conciliacao-result';
                    result.innerHTML = '';
                }
                
                try {
                    // 🎯 MVP: Simular chamada à API
                    // Em produção: await fetch('/api/v1/conciliacao/executar', { method: 'POST' });
                    
                    // Simular delay de processamento
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    // ✅ Sucesso (demo)
                    const mensagem = `
                        <div class="nc-success">
                            <strong>✅ Conciliação concluída!</strong><br><br>
                            <strong>Resumo da Demo:</strong><br>
                            • 📊 5 vendas processadas<br>
                            • ✅ 4 conciliadas com sucesso<br>
                            • ⚠️ 1 com diferença de valor<br>
                            • 💰 Total conciliado: R$ 882,17
                        </div>
                    `;
                    
                    if (result) {
                        result.innerHTML = mensagem;
                        result.style.display = 'block';
                    }
                    
                    // Alerta opcional
                    // alert('Conciliação concluída! Verifique os resultados abaixo.');
                    
                } catch (error) {
                    console.error('Erro na conciliação:', error);
                    
                    if (result) {
                        result.className = 'nc-error';
                        result.innerHTML = '<strong>❌ Erro:</strong> Não foi possível executar a conciliação. Tente novamente.';
                        result.style.display = 'block';
                    }
                    
                } finally {
                    // Restaurar botão
                    btnConciliar.disabled = false;
                    btnConciliar.innerHTML = originalText;
                    
                    // Esconder progresso
                    if (progress) progress.style.display = 'none';
                }
            });
        } else {
            console.warn('⚠️ Botão #btn-executar-conciliacao não encontrado no DOM');
        }
        
        // Filtros (placeholder para MVP)
        const filtroAdquirente = document.getElementById('filtro-adquirente');
        if (filtroAdquirente) {
            filtroAdquirente.addEventListener('change', function() {
                console.log('Filtro alterado:', this.value);
            });
        }
    });
    
    // Utilitário: Formatador de moeda BRL
    window.formatarMoeda = function(valor) {
        if (valor === null || valor === undefined) return '—';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(valor);
    };
    
})();
