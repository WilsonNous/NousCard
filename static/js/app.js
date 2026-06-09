// ============================================================
//  APP • NousCard (UTILITÁRIOS GLOBAIS - VERSÃO COMPLETA)
//  Segurança, Acessibilidade e UX para toda a aplicação
// ============================================================

(function() {
    'use strict';

    // ============================================================
    // CONFIGURAÇÕES GLOBAIS
    // ============================================================
    
    const AppConfig = {
        csrfToken: null,
        apiUrl: '/api/v1',
        // ✅ Ler debug de meta tag ou variável global para flexibilidade
        debug: document.querySelector('meta[name="app-debug"]')?.content === 'true' || 
               (window.APP_DEBUG === true),
        messages: {
            error: 'Ocorreu um erro. Tente novamente.',
            network: 'Erro de conexão. Verifique sua internet.',
            timeout: 'Tempo esgotado. Tente novamente.',
            unauthorized: 'Sessão expirada. Faça login novamente.'
        },
        // ✅ Suporte a i18n (pode ser expandido)
        i18n: {
            'pt-BR': {
                error: 'Ocorreu um erro. Tente novamente.',
                network: 'Erro de conexão. Verifique sua internet.',
                timeout: 'Tempo esgotado. Tente novamente.',
                unauthorized: 'Sessão expirada. Faça login novamente.'
            }
            // Adicionar outras línguas aqui
        }
    };

    // ============================================================
    // INICIALIZAÇÃO
    // ============================================================
    
    function init() {
        // Extrair CSRF token do meta tag ou input
        AppConfig.csrfToken = 
            document.querySelector('meta[name="csrf-token"]')?.content ||
            document.querySelector('input[name="csrf_token"]')?.value ||
            '';
        
        // Configurar interceptador global para fetch
        setupFetchInterceptor();
        
        // Configurar handlers globais de erro
        setupGlobalErrorHandlers();
        
        // Configurar navegação por teclado
        setupKeyboardNavigation();
        
        // ✅ Inicializar região aria-live para screen readers
        setupScreenReaderAnnouncer();
        
        // Log de inicialização (apenas em debug)
        if (AppConfig.debug) {
            console.log('🚀 NousCard app.js initialized');
            console.log('🔐 CSRF Token:', AppConfig.csrfToken ? 'present' : 'missing');
        }
    }

    // ============================================================
    // CSRF & FETCH INTERCEPTOR (SEGURO)
    // ============================================================
    
    function setupFetchInterceptor() {
        // ✅ Usar Proxy para interceptar fetch sem substituir completamente
        // Isso evita conflitos com libs como Axios que podem ter seu próprio fetch wrapper
        const originalFetch = window.fetch;
        
        window.fetch = new Proxy(originalFetch, {
            apply: function(target, thisArg, argumentsList) {
                let [url, options = {}] = argumentsList;
                
                // Adicionar CSRF token em requests state-changing
                const method = (options.method || 'GET').toUpperCase();
                if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
                    options.headers = {
                        ...(options.headers || {}),
                        'X-CSRF-Token': AppConfig.csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'  // Para identificação de AJAX no backend
                    };
                }
                
                // Adicionar timeout padrão se não especificado
                if (!options.signal) {
                    options.signal = AbortSignal.timeout(30000);
                }
                
                // Executar fetch original
                return Reflect.apply(target, thisArg, [url, options])
                    .then(async response => {
                        // ✅ Tratar redirect para login em caso de 401/403
                        if (response.status === 401 || response.status === 403) {
                            // Verificar se é uma requisição de API (não navegação)
                            if (url.includes('/api/') || options.headers?.['X-Requested-With'] === 'XMLHttpRequest') {
                                // Mostrar mensagem amigável antes de redirecionar
                                showNotification(AppConfig.messages.unauthorized, 'warning', 2000);
                                
                                // Redirecionar para login após delay, preservando next URL
                                setTimeout(() => {
                                    const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
                                    window.location.href = `/auth/login?next=${nextUrl}`;
                                }, 1500);
                            }
                        }
                        return response;
                    })
                    .catch(error => {
                        // ✅ Log errors em debug mode com contexto
                        if (AppConfig.debug) {
                            console.error('🌐 Fetch error:', { 
                                url: url.toString?.() || url, 
                                method: options.method || 'GET',
                                error: error.message || error 
                            });
                        }
                        
                        // ✅ Traduzir erros comuns para mensagens amigáveis
                        if (error.name === 'AbortError') {
                            error.userMessage = AppConfig.messages.timeout;
                        } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                            error.userMessage = AppConfig.messages.network;
                        }
                        
                        // Re-lançar para tratamento específico no caller
                        throw error;
                    });
            }
        });
    }

    // ============================================================
    // GLOBAL ERROR HANDLERS
    // ============================================================
    
    function setupGlobalErrorHandlers() {
        // ✅ Unhandled promise rejections
        window.addEventListener('unhandledrejection', event => {
            event.preventDefault(); // Previne log duplicado no console
            
            const reason = event.reason;
            console.error('❌ Unhandled promise rejection:', reason);
            
            // ✅ Integrar com Sentry se disponível
            if (window.Sentry && typeof Sentry.captureException === 'function') {
                Sentry.captureException(reason, {
                    tags: { source: 'frontend', type: 'unhandled_rejection' }
                });
            }
            
            // Mostrar mensagem amigável ao usuário (apenas se não for erro silencioso esperado)
            if (!reason?.silent) {
                showNotification(reason?.userMessage || AppConfig.messages.error, 'error');
            }
        }, { passive: true });
        
        // ✅ Global JavaScript errors
        window.addEventListener('error', event => {
            // Ignorar erros de recursos externos (imagens, scripts de CDN) para evitar spam
            if (event.target !== window && event.target?.tagName) {
                return;
            }
            
            const error = event.error;
            console.error('❌ Global error:', error);
            
            // ✅ Integrar com Sentry se disponível
            if (window.Sentry && typeof Sentry.captureException === 'function') {
                Sentry.captureException(error, {
                    tags: { source: 'frontend', type: 'global_error' },
                    extra: { filename: event.filename, lineno: event.lineno, colno: event.colno }
                });
            }
            
            // Em produção, não mostrar stack trace ao usuário
            if (!AppConfig.debug) {
                showNotification('Ocorreu um erro inesperado.', 'error');
            }
        }, { passive: true });
    }

    // ============================================================
    // KEYBOARD NAVIGATION (ACESSIBILIDADE)
    // ============================================================
    
    function setupKeyboardNavigation() {
        // ✅ Suporte para tecla ESC fechar modais
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                // Fechar modais abertos (priorizar funções globais se existirem)
                const openModal = document.querySelector('.nc-modal[style*="display: block"], .nc-modal[aria-hidden="false"]');
                if (openModal) {
                    // Tentar funções específicas primeiro, depois fallback genérico
                    if (typeof window.fecharModal === 'function') {
                        window.fecharModal();
                    } else if (typeof window.fecharModalConfirmacao === 'function') {
                        window.fecharModalConfirmacao();
                    } else {
                        // Fallback: esconder modal manualmente
                        openModal.style.display = 'none';
                        openModal.setAttribute('aria-hidden', 'true');
                        // Restaurar foco no elemento que abriu o modal
                        const lastFocused = openModal._lastFocusedElement;
                        if (lastFocused && typeof lastFocused.focus === 'function') {
                            lastFocused.focus();
                        }
                    }
                }
                
                // Fechar notificações toast com ESC
                const notificationContainer = document.getElementById('nc-notification-container');
                if (notificationContainer) {
                    notificationContainer.remove();
                }
            }
        }, { passive: true });
        
        // ✅ Suporte para Enter em elementos clicáveis (KPIs, cards, etc.)
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && event.target?.classList?.contains('kpi-click')) {
                event.preventDefault();
                event.target.click();
            }
        }, { passive: true });
        
        // ✅ Suporte para navegação por Tab em elementos customizados
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Tab') {
                // Adicionar classe visual de foco para elementos que não têm :focus-visible nativo
                const focused = document.activeElement;
                if (focused && !['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(focused.tagName)) {
                    focused.classList.add('focus-visible-fallback');
                    setTimeout(() => focused.classList.remove('focus-visible-fallback'), 100);
                }
            }
        }, { passive: true });
    }

    // ============================================================
    // SCREEN READER ANNOUNCER (ACESSIBILIDADE AVANÇADA)
    // ============================================================
    
    function setupScreenReaderAnnouncer() {
        // ✅ Criar região aria-live para anúncios dinâmicos
        const announcer = document.createElement('div');
        announcer.id = 'sr-announcer';
        announcer.setAttribute('role', 'status');
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.className = 'sr-only'; // Esconder visualmente
        announcer.style.cssText = 'position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;';
        document.body.appendChild(announcer);
        
        // ✅ Expor função global para anunciar mensagens
        window.announceToScreenReader = function(message, priority = 'polite') {
            // Atualizar prioridade se necessário
            announcer.setAttribute('aria-live', priority);
            // Limpar e definir nova mensagem (mudança de conteúdo dispara anúncio)
            announcer.textContent = '';
            setTimeout(() => { announcer.textContent = message; }, 100);
        };
    }

    // ============================================================
    // UTILITÁRIOS DE UI
    // ============================================================
    
    /**
     * Mostra notificação toast para o usuário
     * @param {string} message - Mensagem a exibir
     * @param {string} type - 'success' | 'error' | 'warning' | 'info'
     * @param {number} duration - Tempo em ms (default: 5000)
     */
    window.showNotification = function(message, type = 'info', duration = 5000) {
        // ✅ Permitir múltiplas notificações empilhadas
        let container = document.getElementById('nc-notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'nc-notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 350px;
                font-family: inherit;
                display: flex;
                flex-direction: column;
                gap: 10px;
            `;
            document.body.appendChild(container);
        }
        
        // ✅ Injetar estilos CSS apenas uma vez
        if (!document.getElementById('nc-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'nc-notification-styles';
            style.textContent = `
                @keyframes nc-slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes nc-slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
                .nc-notification {
                    animation: nc-slideIn 0.3s ease-out;
                }
                .nc-notification.removing {
                    animation: nc-slideOut 0.3s ease-in forwards;
                }
            `;
            document.head.appendChild(style);
        }
        
        // Criar notificação
        const notification = document.createElement('div');
        notification.className = `nc-notification nc-notification-${type}`;
        notification.style.cssText = `
            padding: 12px 16px;
            border-radius: 8px;
            background: ${getNotificationColor(type)};
            color: ${type === 'error' ? '#721c24' : '#212529'};
            border: 1px solid ${getNotificationBorderColor(type)};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 10px;
        `;
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', 'polite');
        
        // Ícone
        const icon = document.createElement('span');
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = getNotificationIcon(type);
        icon.style.fontSize = '1.2rem';
        icon.style.flexShrink = '0';
        
        // Texto
        const text = document.createElement('span');
        text.textContent = message;
        text.style.flex = '1';
        text.style.lineHeight = '1.4';
        
        // Botão fechar
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '&times;';
        closeBtn.style.cssText = `
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: inherit;
            opacity: 0.7;
            padding: 0 4px;
            line-height: 1;
            flex-shrink: 0;
        `;
        closeBtn.setAttribute('aria-label', 'Fechar notificação');
        closeBtn.onclick = () => removeNotification(notification);
        closeBtn.onfocus = (e) => e.target.style.opacity = '1';
        closeBtn.onblur = (e) => e.target.style.opacity = '0.7';
        
        // Montar
        notification.appendChild(icon);
        notification.appendChild(text);
        notification.appendChild(closeBtn);
        container.appendChild(notification);
        
        // ✅ Anunciar para screen readers
        if (typeof window.announceToScreenReader === 'function') {
            window.announceToScreenReader(message, 'assertive');
        }
        
        // Auto-remove após duration
        const timeoutId = setTimeout(() => {
            removeNotification(notification);
        }, duration);
        
        // Permitir cancelamento manual se necessário
        notification._timeoutId = timeoutId;
        
        // Função helper para remover
        function removeNotification(el) {
            if (el._timeoutId) clearTimeout(el._timeoutId);
            el.classList.add('removing');
            setTimeout(() => {
                el.remove();
                // Remover container se vazio
                if (container && container.children.length === 0) {
                    container.remove();
                }
            }, 300);
        }
    };
    
    function getNotificationColor(type) {
        const colors = {
            success: '#d4edda',
            error: '#f8d7da',
            warning: '#fff3cd',
            info: '#cce5ff'
        };
        return colors[type] || colors.info;
    }
    
    function getNotificationBorderColor(type) {
        const colors = {
            success: '#c3e6cb',
            error: '#f5c6cb',
            warning: '#ffeaa7',
            info: '#b8daff'
        };
        return colors[type] || colors.info;
    }
    
    function getNotificationIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        return icons[type] || icons.info;
    }

    /**
     * Formata valor monetário para padrão brasileiro (robusto)
     * @param {number|string} value - Valor a formatar
     * @returns {string} Valor formatado (ex: "R$ 1.234,56")
     */
    window.formatCurrency = function(value) {
        if (value === null || value === undefined || value === '') return '—';
        
        // ✅ Pré-processar string para remover formatação existente
        let num;
        if (typeof value === 'string') {
            // Remover "R$", espaços, pontos de milhar, substituir vírgula por ponto
            const cleaned = value.replace(/[R$\s.]/g, '').replace(',', '.');
            num = parseFloat(cleaned);
        } else {
            num = value;
        }
        
        if (isNaN(num)) return '—';
        
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    };

    /**
     * Escapa HTML para prevenir XSS (versão robusta)
     * @param {string} text - Texto a escapar
     * @returns {string} Texto seguro para inserção no DOM
     */
    window.escapeHtml = function(text) {
        if (text === null || text === undefined) return '';
        
        // ✅ Mapa expandido para cobrir mais vetores de XSS
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
            '/': '&#x2F;',
            '`': '&#x60;',
            '=': '&#x3D;'
        };
        
        return String(text).replace(/[&<>"'\/`=]/g, m => map[m]);
    };

    /**
     * Debounce para funções executadas frequentemente
     * @param {Function} func - Função a debouncar
     * @param {number} wait - Tempo em ms
     * @param {boolean} immediate - Executar no início em vez do fim
     * @returns {Function} Função debounced
     */
    window.debounce = function(func, wait = 300, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const context = this;
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(context, args);
        };
    };

    /**
     * Throttle para limitar execução de funções
     * @param {Function} func - Função a throttlear
     * @param {number} limit - Intervalo em ms
     * @returns {Function} Função throttled
     */
    window.throttle = function(func, limit = 500) {
        let inThrottle;
        return function(...args) {
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    };

    // ============================================================
    // CLEANUP PARA SPA / NAVEGAÇÃO CLIENT-SIDE
    // ============================================================
    
    /**
     * Remove event listeners globais para prevenir memory leaks
     * Deve ser chamado ao navegar para fora da aplicação (se usar SPA)
     */
    window.cleanupAppGlobals = function() {
        if (AppConfig.debug) {
            console.log('🧹 Cleaning up app.js global listeners');
        }
        // Nota: listeners adicionados com addEventListener sem referência 
        // não podem ser removidos individualmente. Para SPA real,
        // considere usar AbortController para cada listener.
        
        // Remover announcer de screen reader se existir
        const announcer = document.getElementById('sr-announcer');
        if (announcer) announcer.remove();
        
        // Remover container de notificações
        const notificationContainer = document.getElementById('nc-notification-container');
        if (notificationContainer) notificationContainer.remove();
    };

    // ============================================================
    // INICIALIZAR QUANDO DOM ESTIVER PRONTO
    // ============================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        // DOM já carregado (cache, back/forward)
        init();
    }

    // ✅ Expor AppConfig para debug/inspeção (apenas em dev)
    if (AppConfig.debug) {
        window.AppConfig = AppConfig;
    }

})();
