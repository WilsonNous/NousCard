// ============================================================
//  LOGIN • NousCard
//  Validação, UX e segurança para página de login
// ============================================================

(function() {
    'use strict';

    // ============================================================
    // CONFIGURAÇÕES
    // ============================================================
    
    const LoginConfig = {
        minPasswordLength: 8,
        maxLoginAttempts: 5,
        lockoutDuration: 15 * 60 * 1000, // 15 minutos em ms
        selectors: {
            form: 'form[method="POST"]',
            email: '#email',
            password: '#senha',
            submit: '#btn-login',
            error: '#login-error',
            loading: '.btn-loading',
            text: '.btn-text'
        }
    };

    // ============================================================
    // INICIALIZAÇÃO
    // ============================================================
    
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.querySelector(LoginConfig.selectors.form);
        if (!form) return;
        
        // Focar no campo email ao carregar
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        if (emailInput) {
            emailInput.focus();
        }
        
        // Configurar validação em tempo real
        setupRealtimeValidation();
        
        // Configurar submit do form
        setupFormSubmit(form);
        
        // Configurar toggle de senha (se existir)
        setupPasswordToggle();
        
        // Restaurar foco se houver erro
        restoreFocusOnError();
    });

    // ============================================================
    // VALIDAÇÃO EM TEMPO REAL
    // ============================================================
    
    function setupRealtimeValidation() {
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        
        // Validar email ao perder foco
        if (emailInput) {
            emailInput.addEventListener('blur', function() {
                validateEmail(this);
            });
            
            // Limpar erro ao digitar
            emailInput.addEventListener('input', function() {
                clearFieldError(this);
            });
        }
        
        // Validar senha ao perder foco
        if (passwordInput) {
            passwordInput.addEventListener('blur', function() {
                validatePassword(this);
            });
            
            // Limpar erro ao digitar
            passwordInput.addEventListener('input', function() {
                clearFieldError(this);
            });
        }
    }
    
    function validateEmail(input) {
        const email = input.value.trim();
        const errorId = input.id + '-error';
        
        // Regex simples para email
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        
        if (!email) {
            showFieldError(input, 'E-mail é obrigatório.', errorId);
            return false;
        }
        
        if (!emailRegex.test(email)) {
            showFieldError(input, 'Por favor, insira um e-mail válido.', errorId);
            return false;
        }
        
        clearFieldError(input);
        return true;
    }
    
    function validatePassword(input) {
        const password = input.value;
        const errorId = input.id + '-error';
        
        if (!password) {
            showFieldError(input, 'Senha é obrigatória.', errorId);
            return false;
        }
        
        if (password.length < LoginConfig.minPasswordLength) {
            showFieldError(input, `Senha deve ter pelo menos ${LoginConfig.minPasswordLength} caracteres.`, errorId);
            return false;
        }
        
        clearFieldError(input);
        return true;
    }
    
    function showFieldError(input, message, errorId) {
        // Marcar input como inválido
        input.setAttribute('aria-invalid', 'true');
        
        // Criar ou atualizar elemento de erro
        let errorEl = document.getElementById(errorId);
        if (!errorEl) {
            errorEl = document.createElement('span');
            errorEl.id = errorId;
            errorEl.className = 'nc-field-error';
            errorEl.setAttribute('role', 'alert');
            input.parentNode.appendChild(errorEl);
        }
        errorEl.textContent = message;
    }
    
    function clearFieldError(input) {
        input.setAttribute('aria-invalid', 'false');
        const errorId = input.id + '-error';
        const errorEl = document.getElementById(errorId);
        if (errorEl) {
            errorEl.remove();
        }
    }
    
    function restoreFocusOnError() {
        const errorEl = document.querySelector(LoginConfig.selectors.error);
        if (errorEl) {
            // Focar no primeiro campo do form
            const form = errorEl.closest('form');
            if (form) {
                const firstInput = form.querySelector('input:not([type="hidden"])');
                if (firstInput) {
                    firstInput.focus();
                    // Selecionar texto para facilitar correção
                    if (firstInput.type === 'email' || firstInput.type === 'text') {
                        firstInput.select();
                    }
                }
            }
        }
    }

    // ============================================================
    // SUBMIT DO FORM
    // ============================================================
    
    function setupFormSubmit(form) {
        form.addEventListener('submit', async function(event) {
            event.preventDefault();
            
            const submitBtn = document.querySelector(LoginConfig.selectors.submit);
            const emailInput = document.querySelector(LoginConfig.selectors.email);
            const passwordInput = document.querySelector(LoginConfig.selectors.password);
            
            // Validar campos
            const isEmailValid = validateEmail(emailInput);
            const isPasswordValid = validatePassword(passwordInput);
            
            if (!isEmailValid || !isPasswordValid) {
                // Focar no primeiro campo com erro
                const firstError = form.querySelector('[aria-invalid="true"]');
                if (firstError) firstError.focus();
                return;
            }
            
            // UI: Loading state
            setLoadingState(submitBtn, true);
            clearGlobalError();
            
            try {
                // Preparar dados
                const formData = new FormData(form);
                
                // Enviar via fetch (com CSRF token via interceptor global)
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    // Headers adicionados automaticamente pelo app.js interceptor
                    credentials: 'same-origin'
                });
                
                // Parse response
                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('application/json')) {
                    const data = await response.json();
                    
                    if (response.ok && data.ok) {
                        // Login bem-sucedido → redirecionar
                        showNotification('Login realizado com sucesso!', 'success', 2000);
                        // Redirecionamento será feito pelo backend via redirect
                        // Aguardar um pouco para o usuário ver a mensagem
                        setTimeout(() => {
                            window.location.href = data.redirect || '/';
                        }, 1000);
                    } else {
                        // Erro de login (credenciais inválidas, etc.)
                        showGlobalError(data.error || 'Credenciais inválidas. Tente novamente.');
                        // Resetar senha para nova tentativa
                        if (passwordInput) {
                            passwordInput.value = '';
                            passwordInput.focus();
                        }
                    }
                } else {
                    // Resposta HTML (redirect ou erro do Flask)
                    if (response.redirected) {
                        window.location.href = response.url;
                    } else {
                        // Tentar extrair mensagem do HTML
                        const html = await response.text();
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const errorMsg = doc.querySelector('.nc-error')?.textContent?.trim();
                        
                        if (errorMsg) {
                            showGlobalError(errorMsg);
                        } else {
                            showGlobalError('Erro ao processar login. Tente novamente.');
                        }
                    }
                }
                
            } catch (error) {
                console.error('Login error:', error);
                
                // Mensagens amigáveis por tipo de erro
                let message = AppConfig.messages.error;
                
                if (error.name === 'AbortError') {
                    message = AppConfig.messages.timeout;
                } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                    message = AppConfig.messages.network;
                }
                
                showGlobalError(message);
                
                // Resetar senha para nova tentativa
                if (passwordInput) {
                    passwordInput.value = '';
                    passwordInput.focus();
                }
                
            } finally {
                // Restaurar UI
                setLoadingState(submitBtn, false);
            }
        });
    }
    
    function setLoadingState(button, isLoading) {
        if (!button) return;
        
        const textEl = button.querySelector(LoginConfig.selectors.text);
        const loadingEl = button.querySelector(LoginConfig.selectors.loading);
        
        if (isLoading) {
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            if (textEl) textEl.style.display = 'none';
            if (loadingEl) loadingEl.style.display = 'inline-flex';
        } else {
            button.disabled = false;
            button.removeAttribute('aria-busy');
            if (textEl) textEl.style.display = 'inline';
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }
    
    function showGlobalError(message) {
        const errorEl = document.querySelector(LoginConfig.selectors.error);
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.textContent = message;
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'assertive');
        } else {
            // Fallback: criar elemento de erro
            const form = document.querySelector(LoginConfig.selectors.form);
            if (form) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'nc-error';
                errorDiv.id = 'login-error';
                errorDiv.setAttribute('role', 'alert');
                errorDiv.setAttribute('aria-live', 'assertive');
                errorDiv.innerHTML = `<span aria-hidden="true">❌</span> ${escapeHtml(message)}`;
                form.insertBefore(errorDiv, form.firstChild);
            }
        }
    }
    
    function clearGlobalError() {
        const errorEl = document.querySelector(LoginConfig.selectors.error);
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }

    // ============================================================
    // PASSWORD TOGGLE (OPCIONAL)
    // ============================================================
    
    function setupPasswordToggle() {
        // Verificar se há wrapper de senha com botão toggle
        const passwordWrapper = document.querySelector('.nc-password-wrapper');
        if (!passwordWrapper) return;
        
        const passwordInput = passwordWrapper.querySelector('input[type="password"]');
        if (!passwordInput) return;
        
        // Criar botão toggle se não existir
        let toggleBtn = passwordWrapper.querySelector('.nc-toggle-password');
        if (!toggleBtn) {
            toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'nc-toggle-password';
            toggleBtn.setAttribute('aria-label', 'Mostrar senha');
            toggleBtn.setAttribute('aria-pressed', 'false');
            toggleBtn.innerHTML = '<span aria-hidden="true">👁️</span>';
            toggleBtn.style.cssText = `
                position: absolute;
                right: 12px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                cursor: pointer;
                font-size: 1.2rem;
                padding: 4px;
                color: #666;
            `;
            passwordWrapper.style.position = 'relative';
            passwordInput.style.paddingRight = '40px';
            passwordWrapper.appendChild(toggleBtn);
        }
        
        // Handler do toggle
        toggleBtn.addEventListener('click', function() {
            const isHidden = passwordInput.type === 'password';
            passwordInput.type = isHidden ? 'text' : 'password';
            toggleBtn.setAttribute('aria-pressed', String(isHidden));
            toggleBtn.innerHTML = `<span aria-hidden="true">${isHidden ? '🙈' : '👁️'}</span>`;
            toggleBtn.setAttribute('aria-label', isHidden ? 'Ocultar senha' : 'Mostrar senha');
            
            // Manter foco no input após toggle
            passwordInput.focus();
        });
        
        // Suporte para teclado no botão toggle
        toggleBtn.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.click();
            }
        });
    }

    // ============================================================
    // UTILITÁRIOS
    // ============================================================
    
    /**
     * Escapa HTML para prevenir XSS (fallback se app.js não carregou)
     */
    function escapeHtml(text) {
        if (typeof window.escapeHtml === 'function') {
            return window.escapeHtml(text);
        }
        // Fallback inline
        if (text === null || text === undefined) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
    
    /**
     * Mostra notificação (fallback se app.js não carregou)
     */
    function showNotification(message, type, duration) {
        if (typeof window.showNotification === 'function') {
            return window.showNotification(message, type, duration);
        }
        // Fallback simples: alert para erros críticos
        if (type === 'error') {
            console.error(message);
        }
    }

})();
