// static/js/conciliacao.js
// MVP: Funcionalidade básica de conciliação

(function() {
    'use strict';
    
    document.addEventListener('DOMContentLoaded', function() {
        console.log('Conciliação carregada - MVP');
        
        // Botão de conciliar
        const btnConciliar = document.getElementById('btn-conciliar');
        if (btnConciliar) {
            btnConciliar.addEventListener('click', function(e) {
                e.preventDefault();
                alert('Conciliação iniciada! (Demo)');
                // Aqui entraria a chamada real para a API
            });
        }
        
        // Filtros básicos
        const filtroAdquirente = document.getElementById('filtro-adquirente');
        if (filtroAdquirente) {
            filtroAdquirente.addEventListener('change', function() {
                console.log('Filtro alterado:', this.value);
                // Aqui entraria o reload dos dados
            });
        }
    });
    
    // Utilitário simples para formatar moeda
    window.formatarMoeda = function(valor) {
        if (!valor && valor !== 0) return '—';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(valor);
    };
    
})();
