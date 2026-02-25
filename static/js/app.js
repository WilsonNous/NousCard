// ============================================================
//  APP • NousCard (UTILITÁRIOS GLOBAIS)
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
        debug: false,
        messages: {
            error: 'Ocorreu um erro. Tente novamente.',
            network: 'Erro de conexão. Verifique sua internet.',
            timeout: 'Tempo esgotado. Tente novamente.',
            unauthorized: 'Sessão expirada. Faça login novamente.'
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
        
        // Log de inicialização (apenas em debug)
        if (AppConfig.debug) {
            console.log('🚀 NousCard app.js initialized');
        }
    }

    // ============================================================
    // CSRF & FETCH INTERCEPTOR
    // ============================================================
    
    function setupFetchInterceptor() {
        // Guardar referência ao fetch original
        const originalFetch = window.fetch;
        
        // Substituir fetch global
        window.fetch = function(url, options = {}) {
            // Adicionar CSRF token em requests POST/PUT/DELETE
            if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method?.toUpperCase())) {
                options.headers = {
                    ...(options.headers || {}),
                    'X-CSRF-Token': AppConfig.csrfToken
                };
            }
            
            // Adicionar timeout padrão (30s)
            if (!options.signal) {
                options.signal = AbortSignal.timeout(30000);
            }
            
            return originalFetch(url, options)
                .then(async response => {
                    // Tratar redirect para login em caso de 401/403
                    if (response.status === 401 || response.status === 403) {
                        // Verificar se é uma requisição de API
                        if (url.includes('/api/')) {
                            // Redirecionar para login após delay
                            setTimeout(() => {
                                window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
                            }, 1000);
                        }
                    }
                    return response;
                })
                .catch(error => {
                    // Log errors em debug mode
                    if (AppConfig.debug) {
                        console.error('Fetch error:', { url, error });
                    }
                    
                    // Re-lançar para tratamento específico
                    throw error;
                });
        };
    }

    // ============================================================
    // GLOBAL ERROR HANDLERS
    // ============================================================
    
    function setupGlobalErrorHandlers() {
        // Unhandled promise rejections
        window.addEventListener('unhandledrejection', event => {
            event.preventDefault();
            console.error('Unhandled promise rejection:', event.reason);
            
            // Mostrar mensagem amigável ao usuário
            showNotification(AppConfig.messages.error, 'error');
        });
        
        // Global JavaScript errors
        window.addEventListener('error', event => {
            // Ignorar erros de recursos externos (imagens, scripts de CDN)
            if (event.target !== window) {
                return;
            }
            
            console.error('Global error:', event.error);
            
            // Em produção, não mostrar stack trace ao usuário
            if (!AppConfig.debug) {
                showNotification('Ocorreu um erro inesperado.', 'error');
            }
        });
    }

    // ============================================================
    // KEYBOARD NAVIGATION (ACESSIBILIDADE)
    // ============================================================
    
    function setupKeyboardNavigation() {
        // Suporte para tecla ESC fechar modais
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                // Fechar modais abertos
                const openModal = document.querySelector('.nc-modal[style*="display: block"]');
                if (openModal && typeof window.fecharModal === 'function') {
                    window.fecharModal();
                }
                
                // Fechar dropdowns
                const openDropdown = document.querySelector('.dropdown-menu.show');
                if (openDropdown) {
                    openDropdown.classList.remove('show');
                }
            }
        });
        
        // Suporte para Enter em elementos clicáveis
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && event.target.classList.contains('kpi-click')) {
                event.target.click();
            }
        });
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
        // Remover notificações antigas
        const existing = document.getElementById('nc-notification-container');
        if (existing) {
            existing.remove();
        }
        
        // Criar container
        const container = document.createElement('div');
        container.id = 'nc-notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 350px;
            font-family: inherit;
        `;
        
        // Criar notificação
        const notification = document.createElement('div');
        notification.className = `nc-notification nc-notification-${type}`;
        notification.style.cssText = `
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            background: ${getNotificationColor(type)};
            color: ${type === 'error' ? '#721c24' : '#212529'};
            border: 1px solid ${getNotificationBorderColor(type)};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease-out;
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
        
        // Texto
        const text = document.createElement('span');
        text.textContent = message;
        text.style.flex = '1';
        
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
        `;
        closeBtn.setAttribute('aria-label', 'Fechar notificação');
        closeBtn.onclick = () => notification.remove();
        closeBtn.onfocus = (e) => e.target.style.opacity = '1';
        closeBtn.onblur = (e) => e.target.style.opacity = '0.7';
        
        // Montar
        notification.appendChild(icon);
        notification.appendChild(text);
        notification.appendChild(closeBtn);
        container.appendChild(notification);
        document.body.appendChild(container);
        
        // Auto-remove após duration
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in forwards';
            setTimeout(() => {
                notification.remove();
                if (container.children.length === 0) {
                    container.remove();
                }
            }, 300);
        }, duration);
        
        // Adicionar animações CSS se não existirem
        if (!document.getElementById('nc-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'nc-notification-styles';
            style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
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
     * Formata valor monetário para padrão brasileiro
     * @param {number|string} value - Valor a formatar
     * @returns {string} Valor formatado (ex: "R$ 1.234,56")
     */
    window.formatCurrency = function(value) {
        const num = typeof value === 'string' ? parseFloat(value) : value;
        if (isNaN(num)) return 'R$ 0,00';
        
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    };

    /**
     * Escapa HTML para prevenir XSS
     * @param {string} text - Texto a escapar
     * @returns {string} Texto seguro para inserção no DOM
     */
    window.escapeHtml = function(text) {
        if (text === null || text === undefined) return '';
        
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        
        return String(text).replace(/[&<>"']/g, m => map[m]);
    };

    /**
     * Debounce para funções executadas frequentemente
     * @param {Function} func - Função a debouncar
     * @param {number} wait - Tempo em ms
     * @returns {Function} Função debounced
     */
    window.debounce = function(func, wait = 300) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
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
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    };

    // ============================================================
    // INICIALIZAR QUANDO DOM ESTIVER PRONTO
    // ============================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM já carregado (cache, back/forward)
        init();
    }

})();
