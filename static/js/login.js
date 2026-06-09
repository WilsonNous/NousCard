// ============================================================
//  LOGIN • NousCard (VERSÃO DEBUG COM LOGGING)
// ============================================================

(function() {
    'use strict';

    console.log('🔄 Login carregado - Versão DEBUG');

    // ============================================================
    // CONFIGURAÇÕES RELAXADAS PARA DEBUG
    // ============================================================
    
    const LoginConfig = {
        minPasswordLength: 6,  // ✅ Relaxado de 8 para 6
        requireUppercase: false,  // ✅ Desabilitado para debug
        requireLowercase: false,
        requireNumber: false,
        requireSpecial: false,
        specialChars: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/,
        selectors: {
            form: '#loginForm',
            email: '#email',
            password: '#senha',
            submit: '#btn-login',
            error: '#login-error',
            loading: '.btn-loading',
            text: '.btn-text'
        }
    };

    // ============================================================
    // INICIALIZAÇÃO COM LOGGING
    // ============================================================
    
    document.addEventListener('DOMContentLoaded', function() {
        console.log('🔍 DEBUG: DOMContentLoaded');
        
        const form = document.querySelector(LoginConfig.selectors.form);
        console.log('🔍 DEBUG: Form encontrado:', !!form, form?.id);
        
        if (!form) {
            console.error('❌ Formulário de login NÃO encontrado. Seletores esperados:', LoginConfig.selectors);
            return;
        }
        
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        
        console.log('🔍 DEBUG: Email input:', !!emailInput, 'value:', emailInput?.value);
        console.log('🔍 DEBUG: Password input:', !!passwordInput, 'value:', passwordInput?.value ? '[present]' : '[missing]');
        
        // Focar no email se estiver vazio
        if (emailInput && !emailInput.value) {
            emailInput.focus();
        }
        
        // Configurar validação e submit
        setupRealtimeValidation();
        setupFormSubmit(form);
        setupPasswordToggle();
        
        console.log('✅ Login inicializado');
    });

    // ============================================================
    // VALIDAÇÃO SIMPLIFICADA
    // ============================================================
    
    function setupRealtimeValidation() {
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        
        if (emailInput) {
            emailInput.addEventListener('blur', function() {
                const email = this.value.trim();
                console.log('🔍 DEBUG: Email blur, value:', repr(email));
                
                // Validação MÍNIMA para debug
                if (!email) {
                    showFieldError(this, 'E-mail é obrigatório.');
                    return false;
                }
                if (!email.includes('@') || !email.includes('.')) {
                    showFieldError(this, 'Formato básico de email inválido.');
                    return false;
                }
                
                clearFieldError(this);
                return true;
            });
            
            emailInput.addEventListener('input', function() {
                clearFieldError(this);
            });
        }
    }
    
    // Helper para logar strings com caracteres invisíveis
    function repr(str) {
        if (!str) return "''";
        return JSON.stringify(str).replace(/\\u/g, '\\u');
    }
    
    function showFieldError(input, message) {
        input.setAttribute('aria-invalid', 'true');
        let errorEl = document.getElementById(input.id + '-error');
        if (!errorEl) {
            errorEl = document.createElement('span');
            errorEl.id = input.id + '-error';
            errorEl.className = 'nc-form-error';
            errorEl.setAttribute('role', 'alert');
            const formGroup = input.closest('.nc-form-group');
            if (formGroup) formGroup.appendChild(errorEl);
            else input.parentNode.appendChild(errorEl);
        }
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
    
    function clearFieldError(input) {
        input.setAttribute('aria-invalid', 'false');
        const errorEl = document.getElementById(input.id + '-error');
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }

    // ============================================================
    // SUBMIT COM LOGGING DETALHADO
    // ============================================================
    
    function setupFormSubmit(form) {
        form.addEventListener('submit', async function(event) {
            console.log('🔍 DEBUG: Form submit triggered');
            event.preventDefault();
            
            const submitBtn = document.querySelector(LoginConfig.selectors.submit);
            const emailInput = document.querySelector(LoginConfig.selectors.email);
            const passwordInput = document.querySelector(LoginConfig.selectors.password);
            
            // ✅ LOG COMPLETO ANTES DO SUBMIT
            console.log('🔍🔍🔍 DEBUG SUBMIT START 🔍🔍🔍');
            console.log('🔍 Form action:', form.action);
            console.log('🔍 Form method:', form.method);
            console.log('🔍 Email field value:', repr(emailInput?.value));
            console.log('🔍 Email field name:', emailInput?.name);
            console.log('🔍 Password field value:', passwordInput?.value ? '[present]' : '[missing]');
            console.log('🔍 Password field name:', passwordInput?.name);
            
            // Validar campos (versão simplificada)
            const email = (emailInput?.value || '').trim();
            const password = passwordInput?.value || '';
            
            if (!email) {
                console.error('❌ DEBUG: Email vazio - abortando submit');
                showFieldError(emailInput, 'E-mail é obrigatório.');
                return;
            }
            if (!email.includes('@') || !email.includes('.')) {
                console.error('❌ DEBUG: Email formato inválido:', repr(email));
                showFieldError(emailInput, 'Formato de email inválido.');
                return;
            }
            if (!password) {
                console.error('❌ DEBUG: Senha vazia - abortando submit');
                showFieldError(passwordInput, 'Senha é obrigatória.');
                return;
            }
            
            console.log('✅ DEBUG: Validação passou, prosseguindo com submit');
            
            // UI: Loading state
            setLoadingState(submitBtn, true);
            clearGlobalError();
            
            try {
                // Preparar FormData
                const formData = new FormData(form);
                
                // ✅ LOG DO FORMDATA
                console.log('🔍 FormData entries:');
                for (let [key, value] of formData.entries()) {
                    console.log(`   ${key}: ${key === 'senha' || key === 'password' ? '[hidden]' : repr(value)}`);
                }
                
                // CSRF token
                const csrfToken = getCsrfToken();
                console.log('🔍 CSRF token:', csrfToken ? '[present]' : '[MISSING]');
                
                if (csrfToken && !formData.has('csrf_token')) {
                    formData.append('csrf_token', csrfToken);
                    console.log('🔍 CSRF token adicionado ao FormData');
                }
                
                // ✅ LOG DOS HEADERS
                const headers = {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrfToken
                };
                console.log('🔍 Request headers:', headers);
                
                // Enviar via fetch
                console.log('🔍 Enviando fetch POST para:', form.action);
                
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: headers
                });
                
                console.log('🔍 Resposta recebida:', response.status, response.statusText);
                console.log('🔍 Content-Type:', response.headers.get('content-type'));
                console.log('🔍 Redirected:', response.redirected);
                
                // Parse response
                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('application/json')) {
                    const data = await response.json();
                    console.log('🔍 JSON response:', data);
                    
                    if (response.ok && data.ok) {
                        console.log('✅ Login JSON success, redirecting...');
                        setTimeout(() => {
                            window.location.href = data.redirect || '/dashboard';
                        }, 500);
                    } else {
                        console.warn('⚠️ Login JSON error:', data.error);
                        showGlobalError(data.error || 'Credenciais inválidas.');
                        if (passwordInput) {
                            passwordInput.value = '';
                            passwordInput.focus();
                        }
                    }
                } else {
                    // HTML response
                    if (response.redirected) {
                        console.log('✅ Redirect detected, following...');
                        window.location.href = response.url;
                    } else {
                        const html = await response.text();
                        console.log('🔍 HTML response length:', html.length);
                        
                        // Tentar extrair erro do HTML
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const errorMsg = doc.querySelector('.nc-error')?.textContent?.trim();
                        
                        if (errorMsg) {
                            console.warn('⚠️ Error extracted from HTML:', errorMsg);
                            showGlobalError(errorMsg);
                        } else {
                            console.log('✅ HTML response without error - assuming success?');
                            // Se não há erro visível, talvez tenha funcionado
                            // Tentar redirecionar para dashboard
                            window.location.href = '/dashboard';
                        }
                    }
                }
                
            } catch (error) {
                console.error('❌❌❌ FETCH ERROR ❌❌❌', error);
                console.error('Error name:', error.name);
                console.error('Error message:', error.message);
                
                let message = 'Erro de conexão. Verifique sua internet.';
                if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                    message = 'Não foi possível conectar ao servidor.';
                }
                
                showGlobalError(message);
                
            } finally {
                console.log('🔍 DEBUG: Finally block - restoring UI');
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
            if (textEl) textEl.style.display = 'none';
            if (loadingEl) loadingEl.style.display = 'inline-flex';
        } else {
            button.disabled = false;
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
    // UTILITÁRIOS
    // ============================================================
    
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value || 
               '';
    }
    
    function setupPasswordToggle() {
        const existingToggle = document.querySelector('#toggleSenha');
        if (existingToggle) {
            existingToggle.addEventListener('click', function() {
                const passwordInput = document.querySelector(LoginConfig.selectors.password);
                if (!passwordInput) return;
                const isHidden = passwordInput.type === 'password';
                passwordInput.type = isHidden ? 'text' : 'password';
                this.textContent = isHidden ? '🙈' : '👁️';
                passwordInput.focus();
            });
        }
    }

})();
