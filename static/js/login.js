// ============================================================
//  LOGIN • NousCard (VERSÃO DEBUG COMPLETA)
//  Logging extensivo para identificar problema de submit
// ============================================================

(function() {
    'use strict';
    console.log('🔄 Login carregado - Versão DEBUG COMPLETA');

    // ============================================================
    // CONFIGURAÇÕES RELAXADAS PARA DEBUG
    // ============================================================
    
    const LoginConfig = {
        minPasswordLength: 6,  // Relaxado para debug
        requireUppercase: false,
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
        const submitBtn = document.querySelector(LoginConfig.selectors.submit);
        
        console.log('🔍 Form encontrado:', !!form, 'id:', form?.id);
        console.log('🔍 Submit button:', !!submitBtn, 'id:', submitBtn?.id, 'type:', submitBtn?.type, 'disabled:', submitBtn?.disabled);
        
        if (!form) {
            console.error('❌ Form NÃO encontrado. Seletores:', LoginConfig.selectors);
            return;
        }
        
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        
        console.log('🔍 Email input:', {
            found: !!emailInput,
            name: emailInput?.name,
            id: emailInput?.id,
            value: repr(emailInput?.value),
            disabled: emailInput?.disabled
        });
        
        console.log('🔍 Password input:', {
            found: !!passwordInput,
            name: passwordInput?.name,
            id: passwordInput?.id,
            value: passwordInput?.value ? '[present]' : '[EMPTY]',
            disabled: passwordInput?.disabled
        });
        
        // ✅ LISTENER DIRETO NO BOTÃO (capture phase para rodar primeiro)
        if (submitBtn) {
            submitBtn.addEventListener('click', function(e) {
                console.log('🚨🚨🚨 BOTÃO CLICKED 🚨🚨🚨');
                console.log('🔍 Button details:', {
                    id: this.id,
                    type: this.type,
                    tagName: this.tagName,
                    disabled: this.disabled,
                    classList: Array.from(this.classList)
                });
                console.log('🔍 Event details:', {
                    type: e.type,
                    defaultPrevented: e.defaultPrevented,
                    cancelable: e.cancelable
                });
                
                // Se o botão NÃO for type="submit", disparar submit manualmente
                if (this.type !== 'submit') {
                    console.log('⚠️ Botão type="' + this.type + '" não dispara submit automaticamente');
                    console.log('🔄 Disparando form.requestSubmit() manualmente...');
                    try {
                        form.requestSubmit();  // Método moderno que dispara eventos
                    } catch (err) {
                        console.error('❌ Erro ao chamar requestSubmit():', err);
                        // Fallback antigo
                        form.submit();
                    }
                }
            }, true);  // ← Capture phase: roda antes de outros listeners
        }
        
        // ✅ LISTENER NO FORM SUBMIT
        form.addEventListener('submit', async function(event) {
            console.log('🚨🚨🚨 FORM SUBMIT TRIGGERED 🚨🚨🚨');
            console.log('🔍 event.type:', event.type);
            console.log('🔍 event.submitter:', event.submitter?.id || event.submitter?.tagName || '[unknown]');
            console.log('🔍 event.defaultPrevented:', event.defaultPrevented);
            
            event.preventDefault();
            console.log('✅ event.preventDefault() chamado');
            
            const submitBtn = document.querySelector(LoginConfig.selectors.submit);
            const emailInput = document.querySelector(LoginConfig.selectors.email);
            const passwordInput = document.querySelector(LoginConfig.selectors.password);
            
            // ✅ LOG COMPLETO DOS VALORES NO MOMENTO DO SUBMIT
            console.log('🔍🔍🔍 VALORES NO SUBMIT 🔍🔍🔍');
            console.log('🔍 Form action:', form.action);
            console.log('🔍 Form method:', form.method);
            console.log('🔍 Form enctype:', form.enctype);
            console.log('🔍 Email field:', {
                value: repr(emailInput?.value),
                name: emailInput?.name,
                id: emailInput?.id,
                trimmed: (emailInput?.value || '').trim()
            });
            console.log('🔍 Password field:', {
                value: passwordInput?.value ? '[present]' : '[EMPTY]',
                name: passwordInput?.name,
                id: passwordInput?.id
            });
            
            // Validar campos (versão simplificada para debug)
            const email = (emailInput?.value || '').trim();
            const password = passwordInput?.value || '';
            
            console.log('🔍 Validação: email="' + email + '", password="' + (password ? '[present]' : '[EMPTY]') + '"');
            
            if (!email) {
                console.error('❌ SUBMIT ABORTED: Email vazio');
                showFieldError(emailInput, 'E-mail é obrigatório.');
                return;
            }
            if (!email.includes('@') || !email.includes('.')) {
                console.error('❌ SUBMIT ABORTED: Email formato inválido:', repr(email));
                showFieldError(emailInput, 'Formato de email inválido.');
                return;
            }
            if (!password) {
                console.error('❌ SUBMIT ABORTED: Senha vazia');
                showFieldError(passwordInput, 'Senha é obrigatória.');
                return;
            }
            
            console.log('✅ Validação mínima passou');
            
            // UI: Loading state
            setLoadingState(submitBtn, true);
            clearGlobalError();
            
            try {
                // Preparar FormData
                const formData = new FormData(form);
                
                // ✅ LOG COMPLETO DO FORMDATA
                console.log('🔍🔍🔍 FORMDATA ENTRIES 🔍🔍🔍');
                let formDataCount = 0;
                for (let [key, value] of formData.entries()) {
                    const displayValue = (key === 'senha' || key === 'password') ? '[HIDDEN]' : repr(value);
                    console.log(`   [${formDataCount}] ${key}: ${displayValue}`);
                    formDataCount++;
                }
                if (formDataCount === 0) {
                    console.warn('⚠️ FormData está VAZIO!');
                }
                
                // CSRF token
                const csrfMeta = document.querySelector('meta[name="csrf-token"]')?.content;
                const csrfInput = document.querySelector('input[name="csrf_token"]')?.value;
                const csrfToken = csrfInput || csrfMeta || '';
                
                console.log('🔍 CSRF sources:', {
                    meta: csrfMeta ? '[present]' : '[MISSING]',
                    input: csrfInput ? '[present]' : '[MISSING]',
                    using: csrfToken ? '[present]' : '[MISSING]'
                });
                
                if (csrfToken && !formData.has('csrf_token')) {
                    formData.append('csrf_token', csrfToken);
                    console.log('✅ CSRF token adicionado ao FormData');
                } else if (!csrfToken) {
                    console.warn('⚠️ CSRF token MISSING - backend pode rejeitar!');
                }
                
                // Headers da request
                const headers = {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrfToken
                };
                console.log('🔍 Request headers:', headers);
                
                // ✅ ENVIAR VIA FETCH
                console.log('🔍🔍🔍 ENVIANDO FETCH POST 🔍🔍🔍');
                console.log('🔍 URL:', form.action);
                console.log('🔍 Method: POST');
                console.log('🔍 Body: FormData com ' + formDataCount + ' entries');
                
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: headers
                });
                
                console.log('🔍🔍🔍 RESPOSTA RECEBIDA 🔍🔍🔍');
                console.log('🔍 Status:', response.status, response.statusText);
                console.log('🔍 OK:', response.ok);
                console.log('🔍 Redirected:', response.redirected);
                console.log('🔍 Content-Type:', response.headers.get('content-type'));
                console.log('🔍 Headers:', Object.fromEntries(response.headers.entries()));
                
                // Parse response baseado no Content-Type
                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('application/json')) {
                    const data = await response.json();
                    console.log('🔍 JSON response:', data);
                    
                    if (response.ok && data.ok) {
                        console.log('✅ Login JSON success!');
                        const redirectUrl = data.redirect || '/dashboard';
                        console.log('🔄 Redirecionando para:', redirectUrl);
                        setTimeout(() => {
                            window.location.href = redirectUrl;
                        }, 500);
                    } else {
                        console.warn('⚠️ Login JSON error:', data.error || data.message);
                        showGlobalError(data.error || data.message || 'Credenciais inválidas.');
                        if (passwordInput) {
                            passwordInput.value = '';
                            passwordInput.focus();
                        }
                    }
                } else {
                    // Resposta HTML
                    if (response.redirected) {
                        console.log('✅ Redirect detected, following...');
                        console.log('🔄 Redirect URL:', response.url);
                        window.location.href = response.url;
                    } else {
                        const html = await response.text();
                        console.log('🔍 HTML response length:', html.length, 'chars');
                        
                        // Tentar extrair mensagem de erro do HTML
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const errorMsg = doc.querySelector('.nc-error')?.textContent?.trim() ||
                                        doc.querySelector('[role="alert"]')?.textContent?.trim();
                        
                        if (errorMsg) {
                            console.warn('⚠️ Error found in HTML:', errorMsg);
                            showGlobalError(errorMsg);
                        } else {
                            console.log('✅ HTML response sem erro visível');
                            // Se não há erro, talvez tenha funcionado - tentar redirecionar
                            console.log('🔄 Tentando redirecionar para dashboard...');
                            window.location.href = '/dashboard';
                        }
                    }
                }
                
            } catch (error) {
                console.error('❌❌❌ FETCH ERROR ❌❌❌');
                console.error('Error name:', error.name);
                console.error('Error message:', error.message);
                console.error('Error stack:', error.stack);
                
                let message = 'Erro de conexão. Verifique sua internet.';
                if (error.name === 'AbortError' || error.message?.includes('timeout')) {
                    message = 'Conexão demorou muito. Tente novamente.';
                } else if (error.name === 'TypeError' && error.message?.includes('Failed to fetch')) {
                    message = 'Não foi possível conectar ao servidor.';
                } else if (error.message?.includes('401')) {
                    message = 'Sessão expirada. Faça login novamente.';
                } else if (error.message?.includes('403')) {
                    message = 'Acesso negado.';
                }
                
                console.error('🔍 Mensagem para usuário:', message);
                showGlobalError(message);
                
                // Resetar senha para nova tentativa
                if (passwordInput) {
                    passwordInput.value = '';
                    passwordInput.focus();
                }
                
            } finally {
                console.log('🔍 DEBUG: Finally block - restoring UI');
                setLoadingState(submitBtn, false);
            }
        });
        
        // Configurar validação em tempo real
        setupRealtimeValidation();
        
        // Configurar toggle de senha
        setupPasswordToggle();
        
        console.log('✅ Login inicializado com logging completo');
    });

    // ============================================================
    // VALIDAÇÃO SIMPLIFICADA PARA DEBUG
    // ============================================================
    
    function setupRealtimeValidation() {
        const emailInput = document.querySelector(LoginConfig.selectors.email);
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        
        if (emailInput) {
            emailInput.addEventListener('blur', function() {
                const email = this.value.trim();
                console.log('🔍 Email blur event, value:', repr(email));
                
                // Validação MÍNIMA para debug
                if (!email) {
                    console.log('⚠️ Email vazio no blur');
                    showFieldError(this, 'E-mail é obrigatório.');
                    return false;
                }
                if (!email.includes('@') || !email.includes('.')) {
                    console.log('⚠️ Email formato inválido:', repr(email));
                    showFieldError(this, 'Formato básico de email inválido.');
                    return false;
                }
                
                console.log('✅ Email validation passed');
                clearFieldError(this);
                return true;
            });
            
            emailInput.addEventListener('input', function() {
                clearFieldError(this);
            });
        }
        
        if (passwordInput) {
            passwordInput.addEventListener('input', function() {
                clearFieldError(this);
            });
        }
    }
    
    // Helper para logar strings com caracteres especiais visíveis
    function repr(str) {
        if (str === null || str === undefined) return 'null';
        if (str === '') return "''";
        // JSON.stringify mostra escapes, substituir para ficar mais legível
        return JSON.stringify(str)
            .replace(/\\n/g, '\\n')
            .replace(/\\r/g, '\\r')
            .replace(/\\t/g, '\\t');
    }
    
    function showFieldError(input, message) {
        if (!input) return;
        input.setAttribute('aria-invalid', 'true');
        
        let errorEl = document.getElementById(input.id + '-error');
        if (!errorEl) {
            errorEl = document.createElement('span');
            errorEl.id = input.id + '-error';
            errorEl.className = 'nc-form-error';
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'polite');
            
            const formGroup = input.closest('.nc-form-group');
            if (formGroup) {
                formGroup.appendChild(errorEl);
            } else {
                input.parentNode?.appendChild(errorEl);
            }
        }
        errorEl.textContent = message;
        errorEl.style.display = 'block';
        console.log('🔍 Field error shown:', message);
    }
    
    function clearFieldError(input) {
        if (!input) return;
        input.setAttribute('aria-invalid', 'false');
        
        const errorEl = document.getElementById(input.id + '-error');
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }

    // ============================================================
    // UI HELPERS
    // ============================================================
    
    function setLoadingState(button, isLoading) {
        if (!button) return;
        
        const textEl = button.querySelector(LoginConfig.selectors.text);
        const loadingEl = button.querySelector(LoginConfig.selectors.loading);
        
        if (isLoading) {
            console.log('🔍 UI: Setting loading state');
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            if (textEl) textEl.style.display = 'none';
            if (loadingEl) loadingEl.style.display = 'inline-flex';
        } else {
            console.log('🔍 UI: Restoring normal state');
            button.disabled = false;
            button.removeAttribute('aria-busy');
            if (textEl) textEl.style.display = 'inline';
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }
    
    function showGlobalError(message) {
        console.log('🔍 Showing global error:', message);
        
        const errorEl = document.querySelector(LoginConfig.selectors.error);
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.textContent = message;
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'assertive');
        } else {
            // Fallback: criar elemento se não existir
            const form = document.querySelector(LoginConfig.selectors.form);
            if (form) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'nc-error';
                errorDiv.id = 'login-error';
                errorDiv.setAttribute('role', 'alert');
                errorDiv.setAttribute('aria-live', 'assertive');
                errorDiv.innerHTML = '<span aria-hidden="true">❌</span> ' + escapeHtml(message);
                form.insertBefore(errorDiv, form.firstChild);
                console.log('🔍 Created fallback error element');
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

    // ============================================================
    // CSRF & UTILITÁRIOS
    // ============================================================
    
    function getCsrfToken() {
        // Tentar múltiplas fontes
        const meta = document.querySelector('meta[name="csrf-token"]')?.content;
        const input = document.querySelector('input[name="csrf_token"]')?.value;
        const hidden = document.querySelector('input[type="hidden"][name="csrf_token"]')?.value;
        
        const token = meta || input || hidden || '';
        if (!token) {
            console.warn('⚠️ CSRF token NOT FOUND in any source');
        }
        return token;
    }

    // ============================================================
    // PASSWORD TOGGLE
    // ============================================================
    
    function setupPasswordToggle() {
        const existingToggle = document.querySelector('#toggleSenha');
        const passwordInput = document.querySelector(LoginConfig.selectors.password);
        
        if (existingToggle && passwordInput) {
            console.log('🔍 Password toggle found, attaching handler');
            existingToggle.addEventListener('click', function() {
                const isHidden = passwordInput.type === 'password';
                passwordInput.type = isHidden ? 'text' : 'password';
                this.textContent = isHidden ? '🙈' : '👁️';
                this.setAttribute('aria-label', isHidden ? 'Ocultar senha' : 'Mostrar senha');
                passwordInput.focus();
                console.log('🔍 Password visibility toggled:', passwordInput.type);
            });
        } else if (passwordInput) {
            console.log('🔍 No password toggle found, creating one');
            // Criar toggle se não existir (fallback)
            const wrapper = passwordInput.closest('.nc-password-wrapper') || passwordInput.parentNode;
            if (wrapper) {
                const toggleBtn = document.createElement('button');
                toggleBtn.type = 'button';
                toggleBtn.id = 'toggleSenha';
                toggleBtn.className = 'nc-password-toggle';
                toggleBtn.setAttribute('aria-label', 'Mostrar senha');
                toggleBtn.innerHTML = '<span aria-hidden="true">👁️</span>';
                toggleBtn.style.cssText = 'position:absolute;right:0.75rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;font-size:1.25rem;opacity:0.7;';
                
                wrapper.style.position = 'relative';
                passwordInput.style.paddingRight = '2.5rem';
                wrapper.appendChild(toggleBtn);
                
                toggleBtn.addEventListener('click', function() {
                    const isHidden = passwordInput.type === 'password';
                    passwordInput.type = isHidden ? 'text' : 'password';
                    toggleBtn.innerHTML = '<span aria-hidden="true">' + (isHidden ? '🙈' : '👁️') + '</span>';
                    passwordInput.focus();
                });
                console.log('🔍 Created password toggle button');
            }
        }
    }

})();
