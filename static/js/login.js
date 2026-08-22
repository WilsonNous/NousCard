// ============================================================
//  NOUSCARD • LOGIN / LANDING / I18N / GA4
//  Português + Inglês + Origem Comercial
// ============================================================

(function () {
    'use strict';

    // ========================================================
    // TRADUÇÕES
    // ========================================================

    const translations = {

        pt: {
            document_title:
                'NousCard — Gestão simples. Operação organizada. Financeiro sob controle.',

            meta_description:
                'NousCard é uma plataforma da Nous Tecnologia para gestão de clientes, orçamentos, ordens de serviço, financeiro, conciliação e DRE.',

            login_button: 'Entrar',

            hero_eyebrow:
                'GESTÃO PARA PEQUENAS EMPRESAS',

            hero_title:
                'Da proposta ao resultado.<br>Tudo em um só lugar.',

            hero_lead:
                'Clientes, orçamentos, ordens de serviço e financeiro integrados para você acompanhar a operação sem transformar a rotina em burocracia.',

            cta_know:
                'Quero conhecer o NousCard',

            flow_client:
                '👤 Cliente',

            flow_quote:
                '🧾 Orçamento',

            flow_os:
                '🛠️ OS',

            flow_finance:
                '💰 Financeiro',

            trust_simple_title:
                'Simples de usar',

            trust_simple_text:
                'Sem excesso de telas e processos.',

            trust_integrated_title:
                'Visão integrada',

            trust_integrated_text:
                'Gestão e financeiro na mesma plataforma.',

            trust_grow_title:
                'Feito para crescer',

            trust_grow_text:
                'Do primeiro cliente ao controle da operação.',

            features_kicker:
                'RECURSOS',

            features_title:
                'O essencial para organizar a empresa',

            features_lead:
                'O NousCard reúne o que pequenas empresas e prestadores de serviço realmente precisam para acompanhar o dia a dia.',

            feature_clients_title:
                'Clientes',

            feature_clients_text:
                'Mantenha contatos, documentos e informações comerciais organizados em uma base única.',

            feature_quotes_title:
                'Orçamentos',

            feature_quotes_text:
                'Crie propostas profissionais, acompanhe status e transforme aprovações em trabalho executável.',

            feature_os_title:
                'Ordens de Serviço',

            feature_os_text:
                'Acompanhe material, agenda, execução, informações técnicas e conclusão dos serviços.',

            feature_finance_title:
                'Financeiro',

            feature_finance_text:
                'Visualize entradas, saídas, fluxo de caixa, conciliação e DRE em uma visão gerencial.',


            // ==================================================
            // MOCKUP DO DASHBOARD
            // ==================================================

            mockup_overview:
                'VISÃO GERAL',

            mockup_dashboard_title:
                'Dashboard de Gestão',

            mockup_clients:
                'Clientes',

            mockup_quotes:
                'Orçamentos',

            mockup_os_progress:
                'OS em andamento',

            mockup_result:
                'Resultado',

            mockup_result_value:
                'R$ 10,5 mil',

            mockup_sales:
                'Comercial',

            mockup_draft:
                'Rascunho',

            mockup_sent:
                'Enviados',

            mockup_approved:
                'Aprovados',

            mockup_operations:
                'Operação',

            mockup_waiting_material:
                'Aguardando material',

            mockup_scheduled:
                'Agendados',

            mockup_in_progress:
                'Em execução',


            // ==================================================
            // CTA INTERMEDIÁRIO
            // ==================================================

            mid_kicker:
                'COMECE PELO SEU CENÁRIO',

            mid_title:
                'Sua empresa ainda depende de caderno, planilhas ou vários aplicativos?',

            mid_text:
                'Conte rapidamente como você trabalha hoje. A Nous Tecnologia pode mostrar como o NousCard se encaixa na sua operação.',

            mid_cta:
                'Quero ver como funcionaria na minha empresa',


            // ==================================================
            // FLUXO
            // ==================================================

            flow_kicker:
                'FLUXO',

            flow_section_title:
                'Do primeiro contato ao resultado',

            flow_section_text:
                'A informação acompanha o processo. Você reduz retrabalho e passa a enxergar comercial, operação e financeiro como partes da mesma empresa.',

            step1_title:
                'Cadastre o cliente',

            step1_text:
                'Centralize os dados que serão utilizados nos próximos passos.',

            step2_title:
                'Monte o orçamento',

            step2_text:
                'Descrição clara, imagens, valores, condições e apresentação profissional.',

            step3_title:
                'Gere a OS',

            step3_text:
                'O orçamento aprovado vira execução sem redigitação desnecessária.',

            step4_title:
                'Acompanhe o resultado',

            step4_text:
                'Conecte a operação aos dados financeiros e à visão gerencial.',


            // ==================================================
            // SEGMENTOS
            // ==================================================

            segments_kicker:
                'PARA QUEM É',

            segments_title:
                'Pequenas empresas que precisam trabalhar, não administrar um sistema complicado.',

            segment_glass:
                'Vidraçarias',

            segment_construction:
                'Construção',

            segment_maintenance:
                'Manutenção',

            segment_hvac:
                'Climatização',

            segment_carpentry:
                'Marcenaria',

            segment_services:
                'Prestadores de serviço',

            segment_retail:
                'Pequeno comércio',

            segment_selfemployed:
                'Profissionais autônomos',


            // ==================================================
            // CTA FINAL
            // ==================================================

            final_title:
                'Gestão simples. Operação organizada. Financeiro sob controle.',

            final_text:
                'Uma solução da Nous Tecnologia pensada para transformar informação do dia a dia em visão de negócio.',


            // ==================================================
            // LOGIN
            // ==================================================

            login_kicker:
                'ÁREA DO CLIENTE',

            login_title:
                'Acesse sua conta',

            login_lead:
                'Entre com seu e-mail e senha para acessar o NousCard.',

            email_label:
                'E-mail',

            email_hint:
                'Use o e-mail cadastrado no NousCard.',

            password_label:
                'Senha',

            password_hint:
                'Sua senha de acesso ao sistema.',

            remember_me:
                'Lembrar de mim',

            forgot_password:
                'Esqueci minha senha',

            login_submit:
                'Entrar no NousCard',

            login_security:
                '🔒 Ambiente seguro • Dados protegidos',

            no_access_title:
                'Ainda não possui acesso?',

            no_access_text:
                'Fale com a Nous Tecnologia para conhecer o NousCard e avaliar a melhor configuração para sua empresa.',


            // ==================================================
            // LEAD / INTERESSE
            // ==================================================

            interest_kicker:
                'CONHEÇA O NOUSCARD',

            interest_title:
                'Vamos conhecer sua empresa',

            interest_lead:
                'Leva menos de um minuto. Conte como você trabalha hoje e o que gostaria de organizar.',

            interest_success_title:
                'Recebemos seu interesse!',

            interest_success_text:
                'A Nous Tecnologia poderá entrar em contato para entender sua operação e mostrar como o NousCard pode ajudar.',

            interest_whatsapp:
                '💬 Conversar agora pelo WhatsApp',

            interest_continue:
                'Continuar conhecendo o site',

            form_name_label:
                'Seu nome *',

            form_company_label:
                'Empresa *',

            form_whatsapp_label:
                'WhatsApp *',

            form_control_legend:
                'Como você controla sua empresa hoje?',

            control_notebook:
                'Caderno / papel',

            control_spreadsheets:
                'Planilhas',

            control_system:
                'Outro sistema',

            control_mixed:
                'Um pouco de cada',

            form_interest_legend:
                'O que você gostaria de organizar?',

            form_message_label:
                'Quer nos contar algo?',

            privacy_text:
                'Ao enviar, você autoriza a Nous Tecnologia a utilizar esses dados para responder ao seu interesse no NousCard.',


            // ==================================================
            // PLACEHOLDERS
            // ==================================================

            login_email_placeholder:
                'seuemail@empresa.com.br',

            login_password_placeholder:
                'Sua senha',

            phone_placeholder:
                '(48) 99999-9999',

            email_placeholder:
                'voce@empresa.com.br',

            optional_placeholder:
                'Opcional',


            // ==================================================
            // VALIDAÇÕES
            // ==================================================

            validation_required:
                'Preencha nome, empresa e WhatsApp.',

            validation_phone:
                'Informe um WhatsApp válido com DDD.',

            validation_email:
                'Informe um e-mail válido ou deixe o campo vazio.',

            generic_error:
                'Erro ao enviar. Tente novamente.'
        },


        // ======================================================
        // ENGLISH
        // ======================================================

        en: {
            document_title:
                'NousCard — Simple management. Organized operations. Financial control.',

            meta_description:
                'NousCard helps small businesses manage customers, quotes, work orders and finances in one simple platform.',

            login_button:
                'Sign in',

            hero_eyebrow:
                'MANAGEMENT FOR SMALL BUSINESSES',

            hero_title:
                'From quote to payment.<br>Everything in one place.',

            hero_lead:
                'Customers, quotes, work orders and finances connected so you can run your business without unnecessary complexity.',

            cta_know:
                'Discover NousCard',

            flow_client:
                '👤 Customer',

            flow_quote:
                '🧾 Quote',

            flow_os:
                '🛠️ Work Order',

            flow_finance:
                '💰 Finance',

            trust_simple_title:
                'Simple to use',

            trust_simple_text:
                'No unnecessary screens or complicated processes.',

            trust_integrated_title:
                'Integrated view',

            trust_integrated_text:
                'Operations and finance in the same platform.',

            trust_grow_title:
                'Built to grow',

            trust_grow_text:
                'From your first customer to a more organized operation.',

            features_kicker:
                'FEATURES',

            features_title:
                'The essentials to organize your business',

            features_lead:
                'NousCard brings together what small businesses and service providers need to manage everyday operations.',

            feature_clients_title:
                'Customers',

            feature_clients_text:
                'Keep contacts, documents and business information organized in one place.',

            feature_quotes_title:
                'Quotes',

            feature_quotes_text:
                'Create professional quotes, track status and turn approvals into actionable work.',

            feature_os_title:
                'Work Orders',

            feature_os_text:
                'Track materials, schedules, execution details and service completion.',

            feature_finance_title:
                'Finance',

            feature_finance_text:
                'Track money in and out, cash flow, reconciliation and management results.',


            // ==================================================
            // MOCKUP
            // ==================================================

            mockup_overview:
                'OVERVIEW',

            mockup_dashboard_title:
                'Management Dashboard',

            mockup_clients:
                'Customers',

            mockup_quotes:
                'Quotes',

            mockup_os_progress:
                'Work Orders in Progress',

            mockup_result:
                'Result',

            mockup_result_value:
                '€ 10.5K',

            mockup_sales:
                'Sales',

            mockup_draft:
                'Draft',

            mockup_sent:
                'Sent',

            mockup_approved:
                'Approved',

            mockup_operations:
                'Operations',

            mockup_waiting_material:
                'Waiting for Materials',

            mockup_scheduled:
                'Scheduled',

            mockup_in_progress:
                'In Progress',


            // ==================================================
            // CTA INTERMEDIÁRIO
            // ==================================================

            mid_kicker:
                'START WITH YOUR REALITY',

            mid_title:
                'Still running your business with notebooks, spreadsheets and scattered apps?',

            mid_text:
                'Tell us how you work today. Nous Tecnologia can show you how NousCard may fit your operation.',

            mid_cta:
                'Show me how it could work for my business',


            // ==================================================
            // WORKFLOW
            // ==================================================

            flow_kicker:
                'WORKFLOW',

            flow_section_title:
                'From first contact to business results',

            flow_section_text:
                'Information follows the process, reducing rework and connecting sales, operations and finance.',

            step1_title:
                'Add your customer',

            step1_text:
                'Centralize the information you will use throughout the workflow.',

            step2_title:
                'Create the quote',

            step2_text:
                'Clear descriptions, images, pricing, terms and a professional presentation.',

            step3_title:
                'Create the work order',

            step3_text:
                'Turn approved quotes into execution without unnecessary retyping.',

            step4_title:
                'Track the result',

            step4_text:
                'Connect operations with financial information and management insight.',


            // ==================================================
            // SEGMENTS
            // ==================================================

            segments_kicker:
                'WHO IT IS FOR',

            segments_title:
                'Small businesses that need to work — not spend the day managing complicated software.',

            segment_glass:
                'Glass services',

            segment_construction:
                'Construction',

            segment_maintenance:
                'Maintenance',

            segment_hvac:
                'HVAC',

            segment_carpentry:
                'Carpentry',

            segment_services:
                'Service providers',

            segment_retail:
                'Small retail',

            segment_selfemployed:
                'Self-employed professionals',


            // ==================================================
            // FINAL CTA
            // ==================================================

            final_title:
                'Simple management. Organized operations. Financial control.',

            final_text:
                'A Nous Tecnologia solution designed to turn everyday information into clearer business decisions.',


            // ==================================================
            // LOGIN
            // ==================================================

            login_kicker:
                'CLIENT AREA',

            login_title:
                'Sign in to your account',

            login_lead:
                'Use your email and password to access NousCard.',

            email_label:
                'Email',

            email_hint:
                'Use the email registered with NousCard.',

            password_label:
                'Password',

            password_hint:
                'Your NousCard access password.',

            remember_me:
                'Remember me',

            forgot_password:
                'Forgot your password?',

            login_submit:
                'Sign in to NousCard',

            login_security:
                '🔒 Secure environment • Protected data',

            no_access_title:
                'Do not have access yet?',

            no_access_text:
                'Contact Nous Tecnologia to discover NousCard and find the right setup for your business.',


            // ==================================================
            // LEAD
            // ==================================================

            interest_kicker:
                'DISCOVER NOUSCARD',

            interest_title:
                'Tell us about your business',

            interest_lead:
                'It takes less than a minute. Tell us how you work today and what you would like to organize.',

            interest_success_title:
                'We received your request!',

            interest_success_text:
                'Nous Tecnologia may contact you to understand your operation and show how NousCard can help.',

            interest_whatsapp:
                '💬 Talk to us on WhatsApp',

            interest_continue:
                'Continue exploring the website',

            form_name_label:
                'Your name *',

            form_company_label:
                'Company *',

            form_whatsapp_label:
                'WhatsApp / Phone *',

            form_control_legend:
                'How do you manage your business today?',

            control_notebook:
                'Notebook / paper',

            control_spreadsheets:
                'Spreadsheets',

            control_system:
                'Another system',

            control_mixed:
                'A mix of these',

            form_interest_legend:
                'What would you like to organize?',

            form_message_label:
                'Anything else you would like to tell us?',

            privacy_text:
                'By submitting, you authorize Nous Tecnologia to use this information to respond to your interest in NousCard.',


            // ==================================================
            // PLACEHOLDERS
            // ==================================================

            login_email_placeholder:
                'you@company.com',

            login_password_placeholder:
                'Your password',

            phone_placeholder:
                '+351 912 345 678',

            email_placeholder:
                'you@company.com',

            optional_placeholder:
                'Optional',


            // ==================================================
            // VALIDATION
            // ==================================================

            validation_required:
                'Please enter your name, company and phone number.',

            validation_phone:
                'Please enter a valid phone number with country code.',

            validation_email:
                'Please enter a valid email address or leave the field blank.',

            generic_error:
                'Unable to send. Please try again.'
        }
    };


    // ========================================================
    // ORIGEM COMERCIAL
    // ========================================================

    function getReferralSource() {

        const params =
            new URLSearchParams(
                window.location.search
            );

        return (
            params.get('ref')
            || 'direct'
        )
            .toLowerCase()
            .replace(
                /[^a-z0-9_-]/g,
                ''
            )
            .slice(
                0,
                60
            )
            || 'direct';
    }


    // ========================================================
    // IDIOMA INICIAL
    // ========================================================

    function getInitialLanguage() {

        const params =
            new URLSearchParams(
                window.location.search
            );

        const queryLang =
            (
                params.get('lang')
                || ''
            )
                .toLowerCase();


        if (
            queryLang === 'pt'
            || queryLang === 'en'
        ) {
            return queryLang;
        }


        const saved =
            localStorage.getItem(
                'nouscard_lang'
            );


        if (
            saved === 'pt'
            || saved === 'en'
        ) {
            return saved;
        }


        return 'pt';
    }


    // ========================================================
    // TRADUTOR
    // ========================================================

    function t(key) {

        const lang =
            window.NOUSCARD_LANG
            || 'pt';


        return (
            translations[lang]?.[key]
            ?? translations.pt[key]
            ?? key
        );
    }


    // ========================================================
    // HELPERS
    // ========================================================

    function setText(
        selector,
        value
    ) {

        const element =
            document.querySelector(
                selector
            );


        if (
            element
            && value !== undefined
        ) {

            element.textContent =
                value;
        }
    }


    // ========================================================
    // APLICAR IDIOMA
    // ========================================================

    function applyLanguage(
        lang,
        track = true
    ) {

        const dict =
            translations[lang]
            || translations.pt;


        window.NOUSCARD_LANG =
            lang;


        document.documentElement.lang =
            lang === 'en'
                ? 'en'
                : 'pt-BR';


        // ====================================================
        // DATA-I18N
        // ====================================================

        document
            .querySelectorAll(
                '[data-i18n]'
            )
            .forEach(
                function (
                    element
                ) {

                    const key =
                        element
                            .dataset
                            .i18n;


                    if (
                        dict[key]
                        !== undefined
                    ) {

                        element.textContent =
                            dict[key];
                    }
                }
            );


        // ====================================================
        // DATA-I18N-HTML
        // ====================================================

        document
            .querySelectorAll(
                '[data-i18n-html]'
            )
            .forEach(
                function (
                    element
                ) {

                    const key =
                        element
                            .dataset
                            .i18nHtml;


                    if (
                        dict[key]
                        !== undefined
                    ) {

                        element.innerHTML =
                            dict[key];
                    }
                }
            );


        // ====================================================
        // PLACEHOLDERS
        // ====================================================

        document
            .querySelectorAll(
                '[data-i18n-placeholder]'
            )
            .forEach(
                function (
                    element
                ) {

                    const key =
                        element
                            .dataset
                            .i18nPlaceholder;


                    if (
                        dict[key]
                        !== undefined
                    ) {

                        element.placeholder =
                            dict[key];
                    }
                }
            );


        // ====================================================
        // TEXTOS COMPLEMENTARES
        // ====================================================

        setText(
            '.nc-hero-lead',
            dict.hero_lead
        );


        setText(
            '#recursos .nc-section-heading p',
            dict.features_lead
        );


        setText(
            '.nc-feature-card:nth-child(1) p',
            dict.feature_clients_text
        );


        setText(
            '.nc-feature-card:nth-child(2) p',
            dict.feature_quotes_text
        );


        setText(
            '.nc-feature-card:nth-child(3) p',
            dict.feature_os_text
        );


        setText(
            '.nc-feature-card:nth-child(4) p',
            dict.feature_finance_text
        );


        setText(
            '.nc-public-mid-cta p',
            dict.mid_text
        );


        setText(
            '.nc-public-section-soft .nc-section-heading p',
            dict.flow_section_text
        );


        setText(
            '.nc-public-cta p',
            dict.final_text
        );


        setText(
            '.nc-login-panel-lead',
            dict.login_lead
        );


        setText(
            '#email-hint',
            dict.email_hint
        );


        setText(
            '#senha-hint',
            dict.password_hint
        );


        setText(
            '.nc-login-security',
            dict.login_security
        );


        setText(
            '.nc-login-help p',
            dict.no_access_text
        );


        setText(
            '#interestSuccess p',
            dict.interest_success_text
        );


        setText(
            '#interestWhatsapp',
            dict.interest_whatsapp
        );


        setText(
            '.nc-interest-privacy',
            dict.privacy_text
        );


        // ====================================================
        // TÍTULO / META DESCRIPTION
        // ====================================================

        document.title =
            dict.document_title;


        const meta =
            document.querySelector(
                'meta[name="description"]'
            );


        if (meta) {

            meta.content =
                dict.meta_description;
        }


        // ====================================================
        // ESTADO VISUAL PT / EN
        // ====================================================

        document
            .querySelectorAll(
                '[data-lang-switch]'
            )
            .forEach(
                function (
                    button
                ) {

                    const active =
                        button
                            .dataset
                            .langSwitch
                        === lang;


                    button.style.background =
                        active
                            ? 'rgba(255,255,255,.14)'
                            : 'transparent';


                    button.setAttribute(
                        'aria-pressed',
                        active
                            ? 'true'
                            : 'false'
                    );
                }
            );


        // ====================================================
        // CAMPO OCULTO
        // ====================================================

        const hiddenLanguage =
            document.getElementById(
                'landing_language'
            );


        if (
            hiddenLanguage
        ) {

            hiddenLanguage.value =
                lang;
        }


        localStorage.setItem(
            'nouscard_lang',
            lang
        );


        // ====================================================
        // GA4
        // ====================================================

        if (
            track
            && typeof window.ncTrackEvent
            === 'function'
        ) {

            window.ncTrackEvent(
                'language_change',
                {
                    landing_language:
                        lang,

                    referral_source:
                        window.NOUSCARD_REF
                        || 'direct'
                }
            );
        }
    }


    // ========================================================
    // VARIÁVEIS GLOBAIS
    // ========================================================

    window.NOUSCARD_REF =
        getReferralSource();


    window.NOUSCARD_LANG =
        getInitialLanguage();


    window.ncI18n = {
        t:
            t,

        applyLanguage:
            applyLanguage
    };


    // ========================================================
    // INICIALIZAÇÃO
    // ========================================================

    document.addEventListener(
        'DOMContentLoaded',
        function () {

            const hiddenRef =
                document.getElementById(
                    'referral_source'
                );


            if (
                hiddenRef
            ) {

                hiddenRef.value =
                    window.NOUSCARD_REF;
            }


            applyLanguage(
                window.NOUSCARD_LANG,
                false
            );


            document
                .querySelectorAll(
                    '[data-lang-switch]'
                )
                .forEach(
                    function (
                        button
                    ) {

                        button.addEventListener(
                            'click',
                            function () {

                                const lang =
                                    button
                                        .dataset
                                        .langSwitch;


                                applyLanguage(
                                    lang,
                                    true
                                );


                                const url =
                                    new URL(
                                        window.location.href
                                    );


                                url.searchParams.set(
                                    'lang',
                                    lang
                                );


                                history.replaceState(
                                    {},
                                    '',
                                    url.toString()
                                );
                            }
                        );
                    }
                );
        }
    );

})();


// ============================================================
//  GOOGLE ANALYTICS 4 • FUNIL COMERCIAL
// ============================================================

(function () {
    'use strict';


    window.ncTrackEvent =
        function (
            eventName,
            params = {}
        ) {

            try {

                if (
                    typeof window.gtag
                    !== 'function'
                ) {
                    return;
                }


                window.gtag(
                    'event',
                    eventName,
                    {
                        page_path:
                            window.location.pathname,

                        page_location:
                            window.location.href,

                        landing_language:
                            window.NOUSCARD_LANG
                            || 'pt',

                        referral_source:
                            window.NOUSCARD_REF
                            || 'direct',

                        ...params
                    }
                );


            } catch (
                error
            ) {

                console.warn(
                    '⚠️ Falha ao registrar evento GA4:',
                    eventName,
                    error
                );
            }
        };

})();


// ============================================================
//  LOGIN • NOUSCARD
// ============================================================

(function () {
    'use strict';


    const selectors = {
        openButton:
            '#openLoginPanel',

        openLinks:
            '[data-open-login]',

        closeButton:
            '#closeLoginPanel',

        panel:
            '#loginPanel',

        overlay:
            '#loginOverlay',

        form:
            '#loginForm',

        email:
            '#email',

        password:
            '#senha',

        passwordToggle:
            '#toggleSenha',

        submit:
            '#btn-login'
    };


    let lastFocusedElement =
        null;


    function qs(
        selector
    ) {

        return document.querySelector(
            selector
        );
    }


    function qsa(
        selector
    ) {

        return Array.from(
            document.querySelectorAll(
                selector
            )
        );
    }


    function isValidEmail(
        email
    ) {

        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
            email
        );
    }


    // ========================================================
    // ABRIR LOGIN
    // ========================================================

    function openPanel() {

        const panel =
            qs(
                selectors.panel
            );


        const overlay =
            qs(
                selectors.overlay
            );


        const openButton =
            qs(
                selectors.openButton
            );


        if (
            !panel
            || !overlay
        ) {
            return;
        }


        lastFocusedElement =
            document.activeElement;


        panel.classList.add(
            'open'
        );


        overlay.classList.add(
            'open'
        );


        panel.setAttribute(
            'aria-hidden',
            'false'
        );


        overlay.setAttribute(
            'aria-hidden',
            'false'
        );


        openButton?.setAttribute(
            'aria-expanded',
            'true'
        );


        document.body.classList.add(
            'login-panel-open'
        );


        window.setTimeout(
            function () {

                qs(
                    selectors.email
                )?.focus();

            },
            160
        );
    }


    // ========================================================
    // FECHAR LOGIN
    // ========================================================

    function closePanel() {

        const panel =
            qs(
                selectors.panel
            );


        const overlay =
            qs(
                selectors.overlay
            );


        const openButton =
            qs(
                selectors.openButton
            );


        if (
            !panel
            || !overlay
        ) {
            return;
        }


        panel.classList.remove(
            'open'
        );


        overlay.classList.remove(
            'open'
        );


        panel.setAttribute(
            'aria-hidden',
            'true'
        );


        overlay.setAttribute(
            'aria-hidden',
            'true'
        );


        openButton?.setAttribute(
            'aria-expanded',
            'false'
        );


        document.body.classList.remove(
            'login-panel-open'
        );


        if (
            lastFocusedElement
            && typeof lastFocusedElement.focus
            === 'function'
        ) {

            lastFocusedElement.focus();
        }
    }


    // ========================================================
    // ERRO DE CAMPO
    // ========================================================

    function showFieldError(
        input,
        message
    ) {

        if (
            !input
        ) {
            return;
        }


        input.setAttribute(
            'aria-invalid',
            'true'
        );


        const error =
            document.getElementById(
                `${input.id}-error`
            );


        if (
            error
        ) {

            error.textContent =
                message;


            error.style.display =
                'block';
        }
    }


    function clearFieldError(
        input
    ) {

        if (
            !input
        ) {
            return;
        }


        input.setAttribute(
            'aria-invalid',
            'false'
        );


        const error =
            document.getElementById(
                `${input.id}-error`
            );


        if (
            error
        ) {

            error.textContent =
                '';


            error.style.display =
                'none';
        }
    }


    // ========================================================
    // LOADING
    // ========================================================

    function setLoading(
        isLoading
    ) {

        const button =
            qs(
                selectors.submit
            );


        if (
            !button
        ) {
            return;
        }


        const text =
            button.querySelector(
                '.btn-text'
            );


        const loading =
            button.querySelector(
                '.btn-loading'
            );


        button.disabled =
            isLoading;


        button.setAttribute(
            'aria-busy',
            isLoading
                ? 'true'
                : 'false'
        );


        if (
            text
        ) {

            text.style.display =
                isLoading
                    ? 'none'
                    : 'inline';
        }


        if (
            loading
        ) {

            loading.style.display =
                isLoading
                    ? 'inline-flex'
                    : 'none';
        }
    }


    // ========================================================
    // PAINEL
    // ========================================================

    function setupPanel() {

        const openButton =
            qs(
                selectors.openButton
            );


        const closeButton =
            qs(
                selectors.closeButton
            );


        const overlay =
            qs(
                selectors.overlay
            );


        const panel =
            qs(
                selectors.panel
            );


        openButton?.addEventListener(
            'click',
            function () {

                window.ncTrackEvent?.(
                    'login_click',
                    {
                        source:
                            'header'
                    }
                );


                openPanel();
            }
        );


        qsa(
            selectors.openLinks
        ).forEach(
            function (
                button
            ) {

                button.addEventListener(
                    'click',
                    openPanel
                );
            }
        );


        closeButton?.addEventListener(
            'click',
            closePanel
        );


        overlay?.addEventListener(
            'click',
            closePanel
        );


        document.addEventListener(
            'keydown',
            function (
                event
            ) {

                if (
                    event.key
                    === 'Escape'
                    && panel
                        ?.classList
                        .contains(
                            'open'
                        )
                ) {

                    closePanel();
                }
            }
        );


        if (
            panel
                ?.classList
                .contains(
                    'open'
                )
        ) {

            document.body.classList.add(
                'login-panel-open'
            );


            window.setTimeout(
                function () {

                    qs(
                        selectors.email
                    )?.focus();

                },
                120
            );
        }
    }


    // ========================================================
    // MOSTRAR SENHA
    // ========================================================

    function setupPasswordToggle() {

        const button =
            qs(
                selectors.passwordToggle
            );


        const password =
            qs(
                selectors.password
            );


        if (
            !button
            || !password
        ) {
            return;
        }


        button.addEventListener(
            'click',
            function () {

                const show =
                    password.type
                    === 'password';


                password.type =
                    show
                        ? 'text'
                        : 'password';


                button.textContent =
                    show
                        ? '🙈'
                        : '👁️';


                button.setAttribute(
                    'aria-label',
                    show
                        ? 'Ocultar senha'
                        : 'Mostrar senha'
                );


                password.focus();
            }
        );
    }


    // ========================================================
    // VALIDAÇÃO LOGIN
    // ========================================================

    function setupValidation() {

        const form =
            qs(
                selectors.form
            );


        const email =
            qs(
                selectors.email
            );


        const password =
            qs(
                selectors.password
            );


        if (
            !form
            || !email
            || !password
        ) {
            return;
        }


        email.addEventListener(
            'input',
            function () {

                clearFieldError(
                    email
                );
            }
        );


        password.addEventListener(
            'input',
            function () {

                clearFieldError(
                    password
                );
            }
        );


        email.addEventListener(
            'blur',
            function () {

                const value =
                    email.value.trim();


                if (
                    value
                    && !isValidEmail(
                        value
                    )
                ) {

                    showFieldError(
                        email,

                        window.NOUSCARD_LANG
                        === 'en'
                            ? 'Enter a valid email address.'
                            : 'Digite um e-mail válido.'
                    );
                }
            }
        );


        form.addEventListener(
            'submit',
            function (
                event
            ) {

                let valid =
                    true;


                const emailValue =
                    email.value.trim();


                const passwordValue =
                    password.value;


                clearFieldError(
                    email
                );


                clearFieldError(
                    password
                );


                if (
                    !emailValue
                ) {

                    showFieldError(
                        email,

                        window.NOUSCARD_LANG
                        === 'en'
                            ? 'Email is required.'
                            : 'E-mail é obrigatório.'
                    );


                    valid =
                        false;


                } else if (
                    !isValidEmail(
                        emailValue
                    )
                ) {

                    showFieldError(
                        email,

                        window.NOUSCARD_LANG
                        === 'en'
                            ? 'Enter a valid email address.'
                            : 'Digite um e-mail válido.'
                    );


                    valid =
                        false;
                }


                if (
                    !passwordValue
                ) {

                    showFieldError(
                        password,

                        window.NOUSCARD_LANG
                        === 'en'
                            ? 'Password is required.'
                            : 'Senha é obrigatória.'
                    );


                    valid =
                        false;
                }


                if (
                    !valid
                ) {

                    event.preventDefault();


                    openPanel();


                    if (
                        !emailValue
                        || !isValidEmail(
                            emailValue
                        )
                    ) {

                        email.focus();

                    } else {

                        password.focus();
                    }


                    return;
                }


                setLoading(
                    true
                );
            }
        );
    }


    document.addEventListener(
        'DOMContentLoaded',
        function () {

            setupPanel();

            setupPasswordToggle();

            setupValidation();
        }
    );

})();


// ============================================================
//  PAINEL COMERCIAL • QUERO CONHECER
// ============================================================

(function () {
    'use strict';


    document.addEventListener(
        'DOMContentLoaded',
        function () {

            const panel =
                document.getElementById(
                    'interestPanel'
                );


            const overlay =
                document.getElementById(
                    'interestOverlay'
                );


            const closeButton =
                document.getElementById(
                    'closeInterestPanel'
                );


            const form =
                document.getElementById(
                    'interestForm'
                );


            const success =
                document.getElementById(
                    'interestSuccess'
                );


            const errorBox =
                document.getElementById(
                    'interestError'
                );


            const submitButton =
                document.getElementById(
                    'interestSubmit'
                );


            const whatsappButton =
                document.getElementById(
                    'interestWhatsapp'
                );


            const phoneInput =
                document.getElementById(
                    'interest_telefone'
                );


            if (
                !panel
                || !overlay
                || !form
            ) {
                return;
            }


            let lastFocusedElement =
                null;


            let leadFormStarted =
                false;


            // ==================================================
            // FORM START
            // ==================================================

            function trackLeadFormStart() {

                if (
                    leadFormStarted
                ) {
                    return;
                }


                leadFormStarted =
                    true;


                window.ncTrackEvent?.(
                    'lead_form_start',
                    {
                        form_name:
                            'nouscard_interest'
                    }
                );
            }


            form.addEventListener(
                'input',
                function (
                    event
                ) {

                    if (
                        event.target
                            ?.name
                        !== 'website'
                    ) {

                        trackLeadFormStart();
                    }
                }
            );


            form.addEventListener(
                'change',
                function (
                    event
                ) {

                    if (
                        event.target
                            ?.name
                        !== 'website'
                    ) {

                        trackLeadFormStart();
                    }
                }
            );


            // ==================================================
            // ABRIR
            // ==================================================

            function openInterestPanel() {

                lastFocusedElement =
                    document.activeElement;


                document
                    .getElementById(
                        'loginPanel'
                    )
                    ?.classList
                    .remove(
                        'open'
                    );


                document
                    .getElementById(
                        'loginOverlay'
                    )
                    ?.classList
                    .remove(
                        'open'
                    );


                panel.classList.add(
                    'open'
                );


                overlay.classList.add(
                    'open'
                );


                panel.setAttribute(
                    'aria-hidden',
                    'false'
                );


                overlay.setAttribute(
                    'aria-hidden',
                    'false'
                );


                document.body.classList.add(
                    'login-panel-open'
                );


                window.setTimeout(
                    function () {

                        document
                            .getElementById(
                                'interest_nome'
                            )
                            ?.focus();

                    },
                    140
                );
            }


            // ==================================================
            // FECHAR
            // ==================================================

            function closeInterestPanel() {

                panel.classList.remove(
                    'open'
                );


                overlay.classList.remove(
                    'open'
                );


                panel.setAttribute(
                    'aria-hidden',
                    'true'
                );


                overlay.setAttribute(
                    'aria-hidden',
                    'true'
                );


                document.body.classList.remove(
                    'login-panel-open'
                );


                if (
                    lastFocusedElement
                    && typeof lastFocusedElement.focus
                    === 'function'
                ) {

                    lastFocusedElement.focus();
                }
            }


            // ==================================================
            // CTAs
            // ==================================================

            document
                .querySelectorAll(
                    '[data-open-interest]'
                )
                .forEach(
                    function (
                        element
                    ) {

                        element.addEventListener(
                            'click',
                            function () {

                                window.ncTrackEvent?.(
                                    'cta_quero_conhecer',
                                    {
                                        cta_position:
                                            element
                                                .dataset
                                                .ctaPosition
                                            || 'unknown',

                                        cta_label:
                                            element
                                                .dataset
                                                .ctaLabel
                                            || 'unknown'
                                    }
                                );


                                openInterestPanel();
                            }
                        );
                    }
                );


            document
                .querySelectorAll(
                    '[data-close-interest]'
                )
                .forEach(
                    function (
                        element
                    ) {

                        element.addEventListener(
                            'click',
                            closeInterestPanel
                        );
                    }
                );


            closeButton?.addEventListener(
                'click',
                closeInterestPanel
            );


            overlay.addEventListener(
                'click',
                closeInterestPanel
            );


            document.addEventListener(
                'keydown',
                function (
                    event
                ) {

                    if (
                        event.key
                        === 'Escape'
                        && panel
                            .classList
                            .contains(
                                'open'
                            )
                    ) {

                        closeInterestPanel();
                    }
                }
            );


            // ==================================================
            // LOADING
            // ==================================================

            function setInterestLoading(
                isLoading
            ) {

                if (
                    !submitButton
                ) {
                    return;
                }


                submitButton.disabled =
                    isLoading;


                const text =
                    submitButton.querySelector(
                        '.btn-text'
                    );


                const loading =
                    submitButton.querySelector(
                        '.btn-loading'
                    );


                if (
                    text
                ) {

                    text.style.display =
                        isLoading
                            ? 'none'
                            : 'inline';
                }


                if (
                    loading
                ) {

                    loading.style.display =
                        isLoading
                            ? 'inline-flex'
                            : 'none';
                }
            }


            // ==================================================
            // ERRO
            // ==================================================

            function showInterestError(
                message
            ) {

                if (
                    !errorBox
                ) {
                    return;
                }


                errorBox.textContent =
                    message;


                errorBox.style.display =
                    'flex';
            }


            function clearInterestError() {

                if (
                    !errorBox
                ) {
                    return;
                }


                errorBox.textContent =
                    '';


                errorBox.style.display =
                    'none';
            }


            // ==================================================
            // TELEFONE
            //
            // PT:
            // (48) 99999-9999
            //
            // EN:
            // +351 912 345 678
            // +39 333 123 4567
            // +34 612 345 678
            // ==================================================

            phoneInput?.addEventListener(
                'input',
                function () {

                    if (
                        (
                            window.NOUSCARD_LANG
                            || 'pt'
                        )
                        === 'en'
                    ) {

                        this.value =
                            this.value
                                .replace(
                                    /[^\d+\s().-]/g,
                                    ''
                                )
                                .slice(
                                    0,
                                    24
                                );


                        return;
                    }


                    let value =
                        this.value
                            .replace(
                                /\D/g,
                                ''
                            )
                            .slice(
                                0,
                                11
                            );


                    if (
                        value.length > 10
                    ) {

                        value =
                            value.replace(
                                /^(\d{2})(\d{5})(\d{4})$/,
                                '($1) $2-$3'
                            );


                    } else if (
                        value.length > 6
                    ) {

                        value =
                            value.replace(
                                /^(\d{2})(\d{4})(\d{0,4})$/,
                                '($1) $2-$3'
                            );


                    } else if (
                        value.length > 2
                    ) {

                        value =
                            value.replace(
                                /^(\d{2})(\d+)$/,
                                '($1) $2'
                            );


                    } else if (
                        value.length
                    ) {

                        value =
                            value.replace(
                                /^(\d{0,2})$/,
                                '($1'
                            );
                    }


                    this.value =
                        value;
                }
            );


            // ==================================================
            // SUBMIT
            // ==================================================

            form.addEventListener(
                'submit',
                async function (
                    event
                ) {

                    event.preventDefault();


                    clearInterestError();


                    // ============================================
                    // CAMPOS
                    // ============================================

                    const nome =
                        document
                            .getElementById(
                                'interest_nome'
                            )
                            ?.value
                            .trim()
                        || '';


                    const empresa =
                        document
                            .getElementById(
                                'interest_empresa'
                            )
                            ?.value
                            .trim()
                        || '';


                    const telefone =
                        document
                            .getElementById(
                                'interest_telefone'
                            )
                            ?.value
                            .trim()
                        || '';


                    const email =
                        document
                            .getElementById(
                                'interest_email'
                            )
                            ?.value
                            .trim()
                        || '';


                    const mensagem =
                        document
                            .getElementById(
                                'interest_mensagem'
                            )
                            ?.value
                            .trim()
                        || '';


                    const website =
                        document
                            .getElementById(
                                'interest_website'
                            )
                            ?.value
                        || '';


                    // ============================================
                    // REQUIRED
                    // ============================================

                    if (
                        !nome
                        || !empresa
                        || !telefone
                    ) {

                        showInterestError(
                            window.ncI18n.t(
                                'validation_required'
                            )
                        );


                        return;
                    }


                    // ============================================
                    // TELEFONE
                    // ============================================

                    const phoneDigits =
                        telefone.replace(
                            /\D/g,
                            ''
                        );


                    const minPhoneDigits =
                        (
                            window.NOUSCARD_LANG
                            || 'pt'
                        )
                        === 'en'
                            ? 8
                            : 10;


                    if (
                        phoneDigits.length
                        < minPhoneDigits
                    ) {

                        showInterestError(
                            window.ncI18n.t(
                                'validation_phone'
                            )
                        );


                        return;
                    }


                    // ============================================
                    // EMAIL
                    // ============================================

                    if (
                        email
                        && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
                            email
                        )
                    ) {

                        showInterestError(
                            window.ncI18n.t(
                                'validation_email'
                            )
                        );


                        return;
                    }


                    // ============================================
                    // CONTROLE ATUAL
                    // ============================================

                    const controleAtual =
                        form
                            .querySelector(
                                'input[name="controle_atual"]:checked'
                            )
                            ?.value
                        || '';


                    // ============================================
                    // INTERESSES
                    // ============================================

                    const interesses =
                        Array.from(
                            form.querySelectorAll(
                                'input[name="interesses"]:checked'
                            )
                        )
                        .map(
                            function (
                                input
                            ) {

                                return input.value;
                            }
                        );


                    // ============================================
                    // GA4 • SUBMIT
                    // ============================================

                    window.ncTrackEvent?.(
                        'lead_submit',
                        {
                            form_name:
                                'nouscard_interest',

                            controle_atual:
                                controleAtual
                                || 'nao_informado',

                            interesses_count:
                                interesses.length,

                            has_email:
                                email
                                    ? 'sim'
                                    : 'nao'
                        }
                    );


                    setInterestLoading(
                        true
                    );


                    // ============================================
                    // API
                    // ============================================

                    try {

                        const response =
                            await fetch(
                                '/api/public/leads',
                                {
                                    method:
                                        'POST',

                                    headers: {
                                        'Content-Type':
                                            'application/json'
                                    },

                                    body:
                                        JSON.stringify({
                                            nome:
                                                nome,

                                            empresa:
                                                empresa,

                                            telefone:
                                                telefone,

                                            email:
                                                email,

                                            controle_atual:
                                                controleAtual,

                                            interesses:
                                                interesses,

                                            mensagem:
                                                mensagem,

                                            website:
                                                website,

                                            landing_language:
                                                window.NOUSCARD_LANG
                                                || 'pt',

                                            referral_source:
                                                window.NOUSCARD_REF
                                                || 'direct'
                                        })
                                }
                            );


                        const data =
                            await response.json();


                        if (
                            !response.ok
                            || !data.ok
                        ) {

                            throw new Error(
                                data.error
                                || window.ncI18n.t(
                                    'generic_error'
                                )
                            );
                        }


                        // ========================================
                        // GA4 • CONVERSÃO REAL
                        // ========================================

                        window.ncTrackEvent?.(
                            'lead_success',
                            {
                                form_name:
                                    'nouscard_interest',

                                controle_atual:
                                    controleAtual
                                    || 'nao_informado',

                                interesses_count:
                                    interesses.length,

                                conversion_source:
                                    'landing_nouscard'
                            }
                        );


                        // ========================================
                        // SUCESSO
                        // ========================================

                        form.style.display =
                            'none';


                        if (
                            success
                        ) {

                            success.style.display =
                                'block';
                        }


                        if (
                            whatsappButton
                            && data.whatsapp_url
                        ) {

                            whatsappButton.href =
                                data.whatsapp_url;
                        }


                    } catch (
                        error
                    ) {

                        showInterestError(
                            error.message
                            || window.ncI18n.t(
                                'generic_error'
                            )
                        );


                    } finally {

                        setInterestLoading(
                            false
                        );
                    }
                }
            );
        }
    );

})();
