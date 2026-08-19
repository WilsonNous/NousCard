// ============================================================
//  LOGIN • NousCard
//  Landing pública + painel lateral de autenticação
// ============================================================

(function () {
    'use strict';

    const selectors = {
        openButton: '#openLoginPanel',
        openLinks: '[data-open-login]',
        closeButton: '#closeLoginPanel',
        panel: '#loginPanel',
        overlay: '#loginOverlay',
        form: '#loginForm',
        email: '#email',
        password: '#senha',
        passwordToggle: '#toggleSenha',
        submit: '#btn-login',
        globalError: '#login-error'
    };

    let lastFocusedElement = null;

    function qs(selector) {
        return document.querySelector(selector);
    }

    function qsa(selector) {
        return Array.from(document.querySelectorAll(selector));
    }

    function isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function openPanel() {
        const panel = qs(selectors.panel);
        const overlay = qs(selectors.overlay);
        const openButton = qs(selectors.openButton);

        if (!panel || !overlay) return;

        lastFocusedElement = document.activeElement;

        panel.classList.add('open');
        overlay.classList.add('open');

        panel.setAttribute('aria-hidden', 'false');
        overlay.setAttribute('aria-hidden', 'false');

        if (openButton) {
            openButton.setAttribute('aria-expanded', 'true');
        }

        document.body.classList.add('login-panel-open');

        const email = qs(selectors.email);
        if (email) {
            window.setTimeout(() => email.focus(), 160);
        }
    }

    function closePanel() {
        const panel = qs(selectors.panel);
        const overlay = qs(selectors.overlay);
        const openButton = qs(selectors.openButton);

        if (!panel || !overlay) return;

        panel.classList.remove('open');
        overlay.classList.remove('open');

        panel.setAttribute('aria-hidden', 'true');
        overlay.setAttribute('aria-hidden', 'true');

        if (openButton) {
            openButton.setAttribute('aria-expanded', 'false');
        }

        document.body.classList.remove('login-panel-open');

        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
    }

    function showFieldError(input, message) {
        if (!input) return;

        input.setAttribute('aria-invalid', 'true');

        const error = document.getElementById(`${input.id}-error`);
        if (error) {
            error.textContent = message;
            error.style.display = 'block';
        }
    }

    function clearFieldError(input) {
        if (!input) return;

        input.setAttribute('aria-invalid', 'false');

        const error = document.getElementById(`${input.id}-error`);
        if (error) {
            error.textContent = '';
            error.style.display = 'none';
        }
    }

    function setLoading(isLoading) {
        const button = qs(selectors.submit);
        if (!button) return;

        const text = button.querySelector('.btn-text');
        const loading = button.querySelector('.btn-loading');

        button.disabled = isLoading;
        button.setAttribute('aria-busy', isLoading ? 'true' : 'false');

        if (text) {
            text.style.display = isLoading ? 'none' : 'inline';
        }

        if (loading) {
            loading.style.display = isLoading ? 'inline-flex' : 'none';
        }
    }

    function setupPanel() {
        const openButton = qs(selectors.openButton);
        const closeButton = qs(selectors.closeButton);
        const overlay = qs(selectors.overlay);
        const panel = qs(selectors.panel);

        if (openButton) {
            openButton.addEventListener('click', openPanel);
        }

        qsa(selectors.openLinks).forEach(button => {
            button.addEventListener('click', openPanel);
        });

        if (closeButton) {
            closeButton.addEventListener('click', closePanel);
        }

        if (overlay) {
            overlay.addEventListener('click', closePanel);
        }

        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && panel?.classList.contains('open')) {
                closePanel();
            }
        });

        if (panel?.classList.contains('open')) {
            document.body.classList.add('login-panel-open');

            const email = qs(selectors.email);
            if (email) {
                window.setTimeout(() => email.focus(), 120);
            }
        }
    }

    function setupPasswordToggle() {
        const button = qs(selectors.passwordToggle);
        const password = qs(selectors.password);

        if (!button || !password) return;

        button.addEventListener('click', () => {
            const show = password.type === 'password';

            password.type = show ? 'text' : 'password';
            button.textContent = show ? '🙈' : '👁️';
            button.setAttribute('aria-label', show ? 'Ocultar senha' : 'Mostrar senha');

            password.focus();
        });
    }

    function setupValidation() {
        const form = qs(selectors.form);
        const email = qs(selectors.email);
        const password = qs(selectors.password);

        if (!form || !email || !password) return;

        email.addEventListener('input', () => clearFieldError(email));
        password.addEventListener('input', () => clearFieldError(password));

        email.addEventListener('blur', () => {
            const value = email.value.trim();

            if (value && !isValidEmail(value)) {
                showFieldError(email, 'Digite um e-mail válido.');
            }
        });

        form.addEventListener('submit', event => {
            let valid = true;

            const emailValue = email.value.trim();
            const passwordValue = password.value;

            clearFieldError(email);
            clearFieldError(password);

            if (!emailValue) {
                showFieldError(email, 'E-mail é obrigatório.');
                valid = false;
            } else if (!isValidEmail(emailValue)) {
                showFieldError(email, 'Digite um e-mail válido.');
                valid = false;
            }

            if (!passwordValue) {
                showFieldError(password, 'Senha é obrigatória.');
                valid = false;
            }

            if (!valid) {
                event.preventDefault();
                openPanel();

                if (!emailValue || !isValidEmail(emailValue)) {
                    email.focus();
                } else {
                    password.focus();
                }

                return;
            }

            /*
             * Não usamos fetch aqui.
             * O POST normal do formulário preserva o fluxo atual do Flask:
             * login -> sessão segura -> redirect para dashboard/master.
             */
            setLoading(true);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        setupPanel();
        setupPasswordToggle();
        setupValidation();
    });

})();
