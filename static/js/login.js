// ============================================================
//  LOGIN • NousCard (VERSÃO COMPLETA E INTEGRADA)
// ============================================================
// ✅ Integração total com templates HTML corrigidos

(function() {
    'use strict';

    console.log('🔄 Login carregado - Versão Completa');

    // ============================================================
    // CONFIGURAÇÕES
    // ============================================================
    
    const LoginConfig = {
        minPasswordLength: 8,
        requireUppercase: true,
        requireLowercase: true,
        requireNumber: true,
        requireSpecial: true,
        specialChars: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/,
        maxLoginAttempts: 5,
        lockoutDuration: 15 * 60 * 1000, // 15 minutos em ms
        redirectWhitelist: ['/', '/dashboard', '/operacoes/importar'],
        selectors: {
            form: '#loginForm',
            email: '#email',
            password: '#senha',
            submit: '#btn-login',
            error: '#login-error',
            loading: '.btn-loading',
            text: '.btn-text',
            lembrar: 'input[name="lembrar"]'
        }
    };

    // ============================================================
    // INICIALIZAÇÃO
    // ============================================================
    
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.querySelector(LoginConfig.selectors.form);
        if (!form) {
            console.warn('⚠️ Formulário de login não encontrado');
            return;
        }
        
        // Focar no campo email ao carregar
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        if (emailInput && !document.querySelector('[aria-invalid="true"]')) {
            emailInput.focus();
        }
        
        // Configurar validação em tempo real
        setupRealtimeValidation();
        
        // Configurar submit do form
        setupFormSubmit(form);
        
        // Configurar toggle de senha (se existir no template)
        setupPasswordToggle();
        
        // Restaurar foco se houver erro do backend
        restoreFocusOnError();
        
        // Exibir flash messages do Flask se existirem
        displayFlashMessages();
        
        console.log('✅ Login inicializado com sucesso');
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
        
        // Validar senha ao perder foco e ao digitar
        if (passwordInput) {
            passwordInput.addEventListener('blur', function() {
                validatePassword(this);
            });
            
            passwordInput.addEventListener('input', function() {
                clearFieldError(this);
                // Atualizar requisitos visuais se existirem
                updatePasswordRequirements(this.value);
            });
        }
    }
    
    function validateEmail(input) {
        const email = input.value.trim();
        const errorId = input.id + '-error';
        
        // Regex para email válido
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
        
        // ✅ Validação de senha forte
        const checks = {
            uppercase: LoginConfig.requireUppercase ? /[A-Z]/.test(password) : true,
            lowercase: LoginConfig.requireLowercase ? /[a-z]/.test(password) : true,
            number: LoginConfig.requireNumber ? /\d/.test(password) : true,
            special: LoginConfig.requireSpecial ? LoginConfig.specialChars.test(password) : true
        };
        
        if (!checks.uppercase) {
            showFieldError(input, 'Senha deve conter pelo menos uma letra maiúscula.', errorId);
            return false;
        }
        if (!checks.lowercase) {
            showFieldError(input, 'Senha deve conter pelo menos uma letra minúscula.', errorId);
            return false;
        }
        if (!checks.number) {
            showFieldError(input, 'Senha deve conter pelo menos um número.', errorId);
            return false;
        }
        if (!checks.special) {
            showFieldError(input, 'Senha deve conter pelo menos um caractere especial (!@#$%...).', errorId);
            return false;
        }
        
        clearFieldError(input);
        return true;
    }
    
    function updatePasswordRequirements(password) {
        // Atualizar indicadores visuais se existirem no template
        const reqLength = document.getElementById('req-length');
        const reqUpper = document.getElementById('req-upper');
        const reqLower = document.getElementById('req-lower');
        const reqNumber = document.getElementById('req-number');
        const reqSpecial = document.getElementById('req-special');
        
        if (reqLength) reqLength.style.color = password.length >= LoginConfig.minPasswordLength ? '#16a34a' : '#6b7280';
        if (reqUpper) reqUpper.style.color = /[A-Z]/.test(password) ? '#16a34a' : '#6b7280';
        if (reqLower) reqLower.style.color = /[a-z]/.test(password) ? '#16a34a' : '#6b7280';
        if (reqNumber) reqNumber.style.color = /\d/.test(password) ? '#16a34a' : '#6b7280';
        if (reqSpecial) reqSpecial.style.color = LoginConfig.specialChars.test(password) ? '#16a34a' : '#6b7280';
    }
    
    function showFieldError(input, message, errorId) {
        // Marcar input como inválido para acessibilidade
        input.setAttribute('aria-invalid', 'true');
        
        // Criar ou atualizar elemento de erro
        let errorEl = document.getElementById(errorId);
        if (!errorEl) {
            errorEl = document.createElement('span');
            errorEl.id = errorId;
            errorEl.className = 'nc-form-error';
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'polite');
            // Inserir após o input ou no container do form-group
            const formGroup = input.closest('.nc-form-group');
            if (formGroup) {
                formGroup.appendChild(errorEl);
            } else {
                input.parentNode.appendChild(errorEl);
            }
        }
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
    
    function clearFieldError(input) {
        input.setAttribute('aria-invalid', 'false');
        const errorId = input.id + '-error';
        const errorEl = document.getElementById(errorId);
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }
    
    function restoreFocusOnError() {
        // Verificar se há erro global do backend
        const errorEl = document.querySelector(LoginConfig.selectors.error);
        if (errorEl && errorEl.style.display !== 'none' && errorEl.textContent.trim()) {
            // Focar no primeiro campo do form para facilitar correção
            const form = errorEl.closest('form');
            if (form) {
                const firstInput = form.querySelector('input:not([type="hidden"]):not([disabled])');
                if (firstInput) {
                    firstInput.focus();
                    // Selecionar texto para emails para facilitar correção
                    if (firstInput.type === 'email' || firstInput.type === 'text') {
                        firstInput.select();
                    }
                }
            }
        }
    }
    
    function displayFlashMessages() {
        // Exibir flash messages injetados pelo Flask no template
        const flashContainer = document.querySelector('.nc-flash-messages');
        if (flashContainer) {
            flashContainer.style.display = 'block';
            flashContainer.setAttribute('role', 'status');
            flashContainer.setAttribute('aria-live', 'polite');
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
            const lembrarInput = document.querySelector(LoginConfig.selectors.lembrar);
            
            // Validar campos
            const isEmailValid = validateEmail(emailInput);
            const isPasswordValid = validatePassword(passwordInput);
            
            if (!isEmailValid || !isPasswordValid) {
                // Focar no primeiro campo com erro
                const firstError = form.querySelector('[aria-invalid="true"]');
                if (firstError) firstError.focus();
                return;
            }
            
            // UI: Loading state e prevenção de múltiplos submits
            setLoadingState(submitBtn, true);
            disableFormInputs(form, true);
            clearGlobalError();
            
            try {
                // Preparar FormData com todos os campos
                const formData = new FormData(form);
                
                // ✅ Adicionar CSRF token explicitamente (fallback seguro)
                const csrfToken = getCsrfToken();
                if (csrfToken && !formData.has('csrf_token')) {
                    formData.append('csrf_token', csrfToken);
                }
                
                // Enviar via fetch
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-Token': csrfToken
                    }
                });
                
                // Parse response baseado no Content-Type
                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('application/json')) {
                    const data = await response.json();
                    
                    if (response.ok && data.ok) {
                        // ✅ Login bem-sucedido
                        showNotification('Login realizado com sucesso!', 'success', 1500);
                        
                        // ✅ Validar redirect contra whitelist para segurança
                        let redirectUrl = data.redirect || '/dashboard';
                        if (!isValidRedirect(redirectUrl)) {
                            console.warn('⚠️ Redirect inválido detectado, usando padrão');
                            redirectUrl = '/dashboard';
                        }
                        
                        // Aguardar mensagem e redirecionar
                        setTimeout(() => {
                            window.location.href = redirectUrl;
                        }, 1000);
                        
                    } else {
                        // ❌ Erro de login (credenciais inválidas, conta bloqueada, etc.)
                        let errorMsg = data.error || 'Credenciais inválidas. Tente novamente.';
                        
                        // Mensagens específicas por tipo de erro
                        if (data.error_code === 'ACCOUNT_LOCKED') {
                            errorMsg = 'Conta temporariamente bloqueada por muitas tentativas. Aguarde alguns minutos.';
                        } else if (data.error_code === 'INVALID_CREDENTIALS') {
                            errorMsg = 'E-mail ou senha incorretos. Verifique e tente novamente.';
                        } else if (data.error_code === 'ACCOUNT_INACTIVE') {
                            errorMsg = 'Conta inativa. Contate o administrador para reativar.';
                        }
                        
                        showGlobalError(errorMsg);
                        
                        // Resetar senha para nova tentativa (mas manter email)
                        if (passwordInput) {
                            passwordInput.value = '';
                            passwordInput.focus();
                        }
                    }
                } else {
                    // Resposta HTML (redirect ou erro do Flask com template)
                    if (response.redirected) {
                        // Redirect direto do backend
                        window.location.href = response.url;
                    } else {
                        // Tentar extrair mensagem de erro do HTML renderizado
                        const html = await response.text();
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        
                        // Procurar por elemento de erro no HTML
                        const errorMsg = doc.querySelector('.nc-error')?.textContent?.trim() ||
                                        doc.querySelector('[role="alert"]')?.textContent?.trim();
                        
                        if (errorMsg) {
                            showGlobalError(errorMsg);
                        } else {
                            showGlobalError('Erro ao processar login. Tente novamente.');
                        }
                    }
                }
                
            } catch (error) {
                console.error('❌ Login error:', error);
                
                // ✅ Mensagens amigáveis por tipo de erro
                let message = 'Erro ao conectar com o servidor. Verifique sua internet e tente novamente.';
                
                if (error.name === 'AbortError' || error.message.includes('timeout')) {
                    message = 'Conexão demorou muito. Verifique sua internet e tente novamente.';
                } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                    message = 'Não foi possível conectar ao servidor. Verifique sua conexão.';
                } else if (error.message.includes('401')) {
                    message = 'Sessão expirada. Tente fazer login novamente.';
                } else if (error.message.includes('403')) {
                    message = 'Acesso negado. Verifique suas credenciais.';
                }
                
                showGlobalError(message);
                
                // Resetar senha para nova tentativa
                if (passwordInput) {
                    passwordInput.value = '';
                    passwordInput.focus();
                }
                
            } finally {
                // ✅ Restaurar UI sempre, mesmo em erro
                setLoadingState(submitBtn, false);
                disableFormInputs(form, false);
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
    
    function disableFormInputs(form, disable) {
        const inputs = form.querySelectorAll('input:not([type="hidden"]), select, textarea, button');
        inputs.forEach(input => {
            // Não desabilitar o botão de submit principal (já controlado por setLoadingState)
            if (input.id !== 'btn-login') {
                input.disabled = disable;
            }
        });
    }
    
    function showGlobalError(message) {
        const errorEl = document.querySelector(LoginConfig.selectors.error);
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.textContent = message;
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'assertive');
            
            // Anunciar para screen readers
            if (typeof window.announceToScreenReader === 'function') {
                window.announceToScreenReader(message, 'assertive');
            }
        } else {
            // Fallback: criar elemento de erro se não existir
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
            errorEl.removeAttribute('aria-live');
        }
    }

    // ============================================================
    // PASSWORD TOGGLE (INTEGRADO COM TEMPLATE)
    // ============================================================
    
    function setupPasswordToggle() {
        // Verificar se template já tem toggle (evitar duplicação)
        const existingToggle = document.querySelector('#toggleSenha');
        if (existingToggle) {
            // Template já tem toggle, apenas configurar handler
            existingToggle.addEventListener('click', function() {
                const passwordInput = document.querySelector(LoginConfig.selectors.password);
                if (!passwordInput) return;
                
                const isHidden = passwordInput.type === 'password';
                passwordInput.type = isHidden ? 'text' : 'password';
                this.textContent = isHidden ? '🙈' : '👁️';
                this.setAttribute('aria-label', isHidden ? 'Ocultar senha' : 'Mostrar senha');
                this.setAttribute('aria-pressed', String(isHidden));
                
                // Manter foco no input após toggle
                passwordInput.focus();
            });
            return;
        }
        
        // Fallback: criar toggle se template não tiver (para compatibilidade)
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        if (!passwordInput) return;
        
        const wrapper = passwordInput.closest('.nc-password-wrapper') || passwordInput.parentNode;
        if (!wrapper) return;
        
        // Criar botão toggle
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.id = 'toggleSenha';
        toggleBtn.className = 'nc-password-toggle';
        toggleBtn.setAttribute('aria-label', 'Mostrar senha');
        toggleBtn.setAttribute('aria-pressed', 'false');
        toggleBtn.innerHTML = '<span aria-hidden="true">👁️</span>';
        toggleBtn.style.cssText = `
            position: absolute;
            right: 0.75rem;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1.25rem;
            opacity: 0.7;
            transition: opacity 0.2s;
            padding: 0.25rem;
        `;
        toggleBtn.onmouseover = () => toggleBtn.style.opacity = '1';
        toggleBtn.onmouseout = () => toggleBtn.style.opacity = '0.7';
        
        // Ajustar padding do input para o botão
        wrapper.style.position = 'relative';
        passwordInput.style.paddingRight = '2.5rem';
        wrapper.appendChild(toggleBtn);
        
        // Handler do toggle
        toggleBtn.addEventListener('click', function() {
            const isHidden = passwordInput.type === 'password';
            passwordInput.type = isHidden ? 'text' : 'password';
            toggleBtn.innerHTML = `<span aria-hidden="true">${isHidden ? '🙈' : '👁️'}</span>`;
            toggleBtn.setAttribute('aria-label', isHidden ? 'Ocultar senha' : 'Mostrar senha');
            toggleBtn.setAttribute('aria-pressed', String(isHidden));
            passwordInput.focus();
        });
        
        // Suporte para teclado
        toggleBtn.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.click();
            }
        });
    }

    // ============================================================
    // UTILITÁRIOS DE SEGURANÇA
    // ============================================================
    
    /**
     * Obtém token CSRF de forma segura
     */
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value || 
               '';
    }
    
    /**
     * Escapa HTML para prevenir XSS
     */
    function escapeHtml(text) {
        if (typeof window.escapeHtml === 'function') {
            return window.escapeHtml(text);
        }
        // Fallback inline seguro
        if (text === null || text === undefined) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
    
    /**
     * Valida URL de redirect contra whitelist para prevenir open redirect
     */
    function isValidRedirect(url) {
        if (!url) return false;
        
        // Permitir URLs relativas
        if (url.startsWith('/')) {
            return LoginConfig.redirectWhitelist.includes(url) || 
                   LoginConfig.redirectWhitelist.some(allowed => url.startsWith(allowed + '/'));
        }
        
        // Permitir URLs absolutas do mesmo domínio
        try {
            const parsed = new URL(url, window.location.origin);
            return parsed.origin === window.location.origin;
        } catch {
            return false;
        }
    }
    
    /**
     * Mostra notificação (integra com app.js ou usa fallback)
     */
    function showNotification(message, type = 'info', duration = 3000) {
        // Se app.js tiver função global, usar
        if (typeof window.showNotification === 'function') {
            return window.showNotification(message, type, duration);
        }
        
        // Fallback: console para debug e alert apenas para erros críticos
        if (type === 'error') {
            console.error(`[Login] ${message}`);
            // Não usar alert para não interromper UX, apenas log
        } else {
            console.log(`[Login] ${message}`);
        }
    }
    
    /**
     * Anuncia mensagem para screen readers (integra com app.js)
     */
    function announceToScreenReader(message, priority = 'polite') {
        if (typeof window.announceToScreenReader === 'function') {
            return window.announceToScreenReader(message, priority);
        }
        // Fallback: criar elemento aria-live temporário
        const announcer = document.createElement('div');
        announcer.setAttribute('role', 'status');
        announcer.setAttribute('aria-live', priority);
        announcer.className = 'sr-only';
        announcer.textContent = message;
        document.body.appendChild(announcer);
        setTimeout(() => announcer.remove(), 1000);
    }

    // ============================================================
    // CLEANUP DE RECURSOS
    // ============================================================
    
    function cleanup() {
        console.log('🧹 Limpando recursos do login');
        
        // Remover listeners de validação se necessário
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        
        if (emailInput) {
            emailInput.replaceWith(emailInput.cloneNode(true));
        }
        if (passwordInput) {
            passwordInput.replaceWith(passwordInput.cloneNode(true));
        }
        
        // Resetar estado do botão
        const submitBtn = document.querySelector(LoginConfig.selectors.submit);
        if (submitBtn) {
            setLoadingState(submitBtn, false);
        }
    }
    
    // Cleanup ao navegar para outra página
    window.addEventListener('beforeunload', cleanup);
    
    // Expor funções úteis globalmente
    window.loginCleanup = cleanup;
    window.loginValidateEmail = validateEmail;
    window.loginValidatePassword = validatePassword;
    
})();
