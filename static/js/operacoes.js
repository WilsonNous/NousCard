// ============================================================
//  OPERAÇÕES • NousCard (VERSÃO SEGURA E COMPLETA - CORRIGIDA)
// ============================================================

(function() {
    'use strict';
    
    console.log('🔄 Operações carregado - Versão Completa');
    
    // Estado da aplicação
    let operacoesState = {
        selectedFiles: [],
        uploadXHR: null,
        isProcessing: false,
        retryCount: 0,
        MAX_RETRY: 2
    };
    
    // Configurações
    const AppConfig = {
        maxSize: 10 * 1024 * 1024, // 10MB
        maxFiles: 10,
        allowedExtensions: ['.csv', '.xlsx', '.xls', '.ofx', '.txt'],
        allowedMimeTypes: [
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/x-ofx',
            'text/plain'
        ]
    };
    
    // ============================================================
    // UTILITÁRIOS SEGUROS
    // ============================================================

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

    window.formatCurrency = function(value) {
        if (value === null || value === undefined || value === '') return '—';
        const num = typeof value === 'string' 
            ? parseFloat(value.replace(/[^\d,.-]/g, '').replace(',', '.')) 
            : value;
        if (isNaN(num)) return '—';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    };

    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content ||
               document.querySelector('input[name="csrf_token"]')?.value ||
               '';
    }

    function getEmpresaId() {
        return document.body.dataset.empresaId || null;
    }
    
    window.formatFileSize = function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };
    
    function detectFileType(filename) {
        const lower = filename.toLowerCase();
        if (lower.includes('venda') || lower.includes('sales') || lower.includes('adquirente') || lower.includes('cielo') || lower.includes('rede')) {
            return { label: '📊 Vendas', class: 'file-type-venda' };
        } else if (lower.includes('extrato') || lower.includes('banco') || lower.includes('recebimento') || lower.includes('ofx')) {
            return { label: '🏦 Banco', class: 'file-type-banco' };
        }
        return { label: '📁 Arquivo', class: 'file-type-unknown' };
    }

    function validarArquivo(file) {
        const errors = [];

        const hasValidExtension = AppConfig.allowedExtensions.some(ext => 
            file.name.toLowerCase().endsWith(ext)
        );
        if (!hasValidExtension) {
            errors.push(`Extensão não permitida: ${file.name}`);
        }

        if (file.type && !AppConfig.allowedMimeTypes.includes(file.type) && !hasValidExtension) {
            errors.push(`Tipo de arquivo não permitido: ${file.name}`);
        }

        if (file.size > AppConfig.maxSize) {
            errors.push(`Arquivo muito grande: ${file.name} (${formatFileSize(file.size)}) - Máx: 10MB`);
        }

        if (file.name.includes('/') || file.name.includes('\\') || file.name.startsWith('.') || file.name.length > 255) {
            errors.push(`Nome de arquivo inválido: ${file.name}`);
        }
        
        if (operacoesState.selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
            errors.push(`Arquivo já selecionado: ${file.name}`);
        }

        return errors;
    }

    document.addEventListener("DOMContentLoaded", () => {
        
        // ============================================================
        // ELEMENTOS DO DOM
        // ============================================================
        
        const dropZone = document.getElementById("dropZone");
        const fileInput = document.getElementById("fileInput");
        const uploadForm = document.getElementById("uploadForm");
        const uploadResult = document.getElementById("uploadResult");
        const fileList = document.getElementById("fileList");
        const uploadErrors = document.getElementById("uploadErrors");
        const uploadProgress = document.getElementById("uploadProgress");
        const btnUpload = document.getElementById("btn-upload");
        const btnCancel = document.getElementById("btn-cancel");
        const historyList = document.getElementById("ultimosUploads");
        
        // ============================================================
        // DRAG & DROP + SELEÇÃO DE ARQUIVOS
        // ============================================================

        if (dropZone && fileInput && uploadForm) {

            dropZone.addEventListener("click", () => {
                if (!operacoesState.isProcessing) {
                    fileInput.click();
                }
            });
            
            dropZone.addEventListener("keydown", (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    fileInput.click();
                }
            });
            dropZone.setAttribute('tabindex', '0');
            dropZone.setAttribute('role', 'button');
            dropZone.setAttribute('aria-label', 'Área para arrastar e soltar arquivos ou clique para selecionar');

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, e => {
                    e.preventDefault();
                    e.stopPropagation();
                }, false);
            });

            ['dragenter', 'dragover'].forEach(eventName => {
                dropZone.addEventListener(eventName, () => {
                    if (!operacoesState.isProcessing) {
                        dropZone.classList.add('dragover');
                    }
                }, false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, () => {
                    dropZone.classList.remove('dragover');
                }, false);
            });

            dropZone.addEventListener('drop', e => {
                if (operacoesState.isProcessing) return;
                
                const files = e.dataTransfer.files;
                if (files.length) {
                    handleFileSelection(files);
                }
            }, false);

            fileInput.addEventListener('change', e => {
                if (operacoesState.isProcessing) return;
                handleFileSelection(e.target.files);
            });

            // ✅ ✅ ✅ FUNÇÃO CORRIGIDA: handleFileSelection ✅ ✅ ✅
            function handleFileSelection(files) {
                const errors = [];
                const validFiles = [];
                const newFiles = Array.from(files);

                if (operacoesState.selectedFiles.length + newFiles.length > AppConfig.maxFiles) {
                    errors.push(`Máximo de ${AppConfig.maxFiles} arquivos permitidos.`);
                }

                newFiles.forEach(file => {
                    const fileErrors = validarArquivo(file);
                    if (fileErrors.length) {
                        errors.push(...fileErrors);
                    } else {
                        validFiles.push(file);
                    }
                });

                if (errors.length && uploadErrors) {
                    uploadErrors.innerHTML = errors.map(err => 
                        `<div>❌ ${escapeHtml(err)}</div>`
                    ).join('');
                    uploadErrors.style.display = 'block';
                    uploadErrors.setAttribute('role', 'alert');
                } else if (uploadErrors) {
                    uploadErrors.style.display = 'none';
                    uploadErrors.innerHTML = '';
                }

                if (validFiles.length) {
                    operacoesState.selectedFiles = [...operacoesState.selectedFiles, ...validFiles];
                    
                    // ✅ ✅ ✅ CORREÇÃO CRÍTICA: Atualizar fileInput.files para o submit funcionar ✅ ✅ ✅
                    const dt = new DataTransfer();
                    operacoesState.selectedFiles.forEach(f => dt.items.add(f));
                    fileInput.files = dt.files;
                    // ✅ ✅ ✅ FIM DA CORREÇÃO ✅ ✅ ✅
                    
                    updateFileList();
                }

                fileInput.value = '';
            }
            
            function updateFileList() {
                if (!fileList) return;
                
                if (operacoesState.selectedFiles.length === 0) {
                    fileList.style.display = 'none';
                    fileList.innerHTML = '';
                    return;
                }
                
                fileList.style.display = 'block';
                fileList.innerHTML = `
                    <h4 class="nc-subtitle" style="margin-bottom: 0.5rem;">
                        Arquivos Selecionados (${operacoesState.selectedFiles.length}):
                    </h4>
                    <div class="file-list-items">
                        ${operacoesState.selectedFiles.map((f, idx) => {
                            const typeInfo = detectFileType(f.name);
                            return `
                                <div class="file-item" data-index="${idx}">
                                    <div class="file-info">
                                        <div class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
                                        <div class="file-meta">
                                            <span class="file-size">${formatFileSize(f.size)}</span>
                                            <span class="file-type ${typeInfo.class}">${typeInfo.label}</span>
                                        </div>
                                    </div>
                                    <button type="button" class="btn-remove" onclick="removerArquivo(${idx})" aria-label="Remover ${escapeHtml(f.name)}">
                                        ✕
                                    </button>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
            }
            
            window.removerArquivo = function(index) {
                operacoesState.selectedFiles.splice(index, 1);
                updateFileList();
                
                const dt = new DataTransfer();
                operacoesState.selectedFiles.forEach(f => dt.items.add(f));
                fileInput.files = dt.files;
            };

            // ============================================================
            // UPLOAD COM PROGRESSO REAL
            // ============================================================
            
            uploadForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                
                if (operacoesState.isProcessing) {
                    console.log('⏳ Upload já em andamento');
                    return;
                }

                const files = fileInput.files;
                
                if (!files || !files.length) {
                    mostrarResultado('error', 'Nenhum arquivo selecionado.');
                    return;
                }

                const allErrors = [];
                Array.from(files).forEach(f => {
                    allErrors.push(...validarArquivo(f));
                });
                if (allErrors.length) {
                    mostrarResultado('error', allErrors[0]);
                    return;
                }

                operacoesState.isProcessing = true;
                mostrarLoading();
                
                if (btnUpload) btnUpload.disabled = true;
                if (btnCancel) btnCancel.style.display = 'inline-block';
                if (dropZone) dropZone.style.pointerEvents = 'none';
                if (fileInput) fileInput.disabled = true;

                const tipoArquivo = document.querySelector('input[name="tipo_arquivo"]:checked')?.value || 'venda';

                const formData = new FormData();
                for (const f of files) formData.append("files", f);
                formData.append("tipo_arquivo", tipoArquivo);

                let xhr = null;
                operacoesState.retryCount = 0;

                async function tentarUpload() {
                    return new Promise((resolve, reject) => {
                        xhr = new XMLHttpRequest();
                        operacoesState.uploadXHR = xhr;
                        
                        xhr.upload.addEventListener('progress', (e) => {
                            if (e.lengthComputable && uploadProgress) {
                                const percent = Math.round((e.loaded / e.total) * 100);
                                updateProgress(percent, 'Enviando arquivos...');
                            }
                        });

                        xhr.onload = () => {
                            if (xhr.status === 200) {
                                try {
                                    const data = JSON.parse(xhr.responseText);
                                    resolve(data);
                                } catch (err) {
                                    reject(new Error('Resposta inválida do servidor'));
                                }
                            } else if (xhr.status >= 500 && operacoesState.retryCount < operacoesState.MAX_RETRY) {
                                operacoesState.retryCount++;
                                const delay = Math.min(1000 * Math.pow(2, operacoesState.retryCount), 5000);
                                console.log(`🔄 Retry ${operacoesState.retryCount}/${operacoesState.MAX_RETRY} em ${delay}ms...`);
                                updateProgress(0, `Tentando novamente em ${delay/1000}s...`);
                                setTimeout(() => tentarUpload().then(resolve).catch(reject), delay);
                            } else {
                                reject(new Error(`Erro HTTP: ${xhr.status}`));
                            }
                        };

                        xhr.onerror = () => {
                            if (operacoesState.retryCount < operacoesState.MAX_RETRY) {
                                operacoesState.retryCount++;
                                const delay = Math.min(1000 * Math.pow(2, operacoesState.retryCount), 5000);
                                console.log(`🔄 Retry ${operacoesState.retryCount}/${operacoesState.MAX_RETRY} em ${delay}ms...`);
                                updateProgress(0, `Tentando novamente em ${delay/1000}s...`);
                                setTimeout(() => tentarUpload().then(resolve).catch(reject), delay);
                            } else {
                                reject(new Error('Erro de rede ao enviar arquivos'));
                            }
                        };

                        xhr.onabort = () => {
                            reject(new Error('Upload cancelado pelo usuário'));
                        };

                        xhr.open('POST', uploadForm.action || '/operacoes/upload');
                        
                        const csrfToken = getCsrfToken();
                        if (csrfToken) {
                            xhr.setRequestHeader('X-CSRF-Token', csrfToken);
                        }
                        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

                        xhr.send(formData);
                    });
                }

                try {
                    const data = await tentarUpload();
                    handleUploadResponse(data);
                    
                } catch (err) {
                    console.error("❌ Erro ao enviar arquivos:", err);
                    
                    let errorMsg = 'Erro ao enviar arquivos. Tente novamente.';
                    if (err.message.includes('413')) {
                        errorMsg = 'Arquivo muito grande. Máximo permitido: 10MB por arquivo.';
                    } else if (err.message.includes('401')) {
                        errorMsg = 'Sessão expirada. Faça login novamente.';
                        setTimeout(() => window.location.href = '/auth/login?expired=1', 2000);
                    } else if (err.message.includes('403')) {
                        errorMsg = 'Acesso negado. Verifique suas permissões.';
                    } else if (err.message.includes('timeout') || err.name === 'TimeoutError') {
                        errorMsg = 'Conexão demorou muito. Verifique sua internet e tente novamente.';
                    } else if (err.message.includes('cancelado')) {
                        errorMsg = 'Upload cancelado.';
                    }
                    
                    mostrarResultado('error', errorMsg);
                    
                } finally {
                    operacoesState.isProcessing = false;
                    operacoesState.uploadXHR = null;
                    resetUploadUI();
                    
                    if (uploadResult?.querySelector('.nc-success')) {
                        operacoesState.selectedFiles = [];
                        updateFileList();
                        fileInput.value = '';
                        
                        if (uploadForm) {
                            uploadForm.querySelectorAll('input, button').forEach(el => {
                                if (el.type !== 'hidden') el.disabled = true;
                            });
                        }
                    }
                }
            });

            if (btnCancel) {
                btnCancel.addEventListener('click', () => {
                    if (operacoesState.uploadXHR && operacoesState.uploadXHR.readyState !== 4) {
                        operacoesState.uploadXHR.abort();
                        mostrarResultado('warning', 'Upload cancelado pelo usuário.');
                        resetUploadUI();
                    }
                });
            }
            
            window.addEventListener('beforeunload', () => {
                if (operacoesState.uploadXHR && operacoesState.uploadXHR.readyState !== 4) {
                    operacoesState.uploadXHR.abort();
                }
            });

            // ============================================================
            // HELPERS DE UI
            // ============================================================

            function mostrarLoading() {
                if (uploadResult) {
                    uploadResult.innerHTML = `
                        <div class="nc-loading" role="status" aria-live="polite" aria-busy="true">
                            <span class="spinner" aria-hidden="true"></span>
                            <span id="progressStatusLabel">Enviando arquivos...</span>
                        </div>
                    `;
                }
                if (uploadProgress) {
                    uploadProgress.style.display = 'block';
                    updateProgress(0, 'Enviando...');
                }
            }

            function updateProgress(percent, label = null) {
                if (!uploadProgress) return;
                const bar = uploadProgress.querySelector('.nc-progress-bar');
                const text = uploadProgress.querySelector('.nc-progress-text');
                const statusLabel = document.getElementById('progressStatusLabel');
                
                if (bar) bar.style.width = percent + '%';
                if (text) text.textContent = `${percent}%`;
                if (statusLabel && label) statusLabel.textContent = label;
                
                uploadProgress.setAttribute('aria-valuenow', percent);
            }

            function resetUploadUI() {
                if (btnUpload) btnUpload.disabled = false;
                if (btnCancel) btnCancel.style.display = 'none';
                if (uploadProgress) {
                    uploadProgress.style.display = 'none';
                    const bar = uploadProgress.querySelector('.nc-progress-bar');
                    const text = uploadProgress.querySelector('.nc-progress-text');
                    if (bar) bar.style.width = '0%';
                    if (text) text.textContent = '0%';
                }
                if (dropZone) dropZone.style.pointerEvents = '';
                if (fileInput) fileInput.disabled = false;
            }

            function handleUploadResponse(data) {
                if (!data.ok) {
                    mostrarResultado('error', data.message || 'Erro ao processar arquivos.');
                    return;
                }

                const resumo = `
                    <div class="nc-success" role="status">
                        <h3>✔ Arquivos processados com sucesso!</h3>
                        <ul class="nc-summary">
                            <li>📁 <strong>${escapeHtml(data.total_arquivos || 0)}</strong> arquivo(s) enviado(s)</li>
                            <li>🛍️ <strong>${escapeHtml(data.qtde_vendas || 0)}</strong> venda(s) identificada(s)</li>
                            <li>💸 <strong>${escapeHtml(data.qtde_recebimentos || 0)}</strong> recebimento(s) identificado(s)</li>
                            <li>💰 Total Vendas: <strong>${formatCurrency(data.total_vendas)}</strong></li>
                            <li>💰 Total Recebido: <strong>${formatCurrency(data.total_recebimentos)}</strong></li>
                        </ul>
                        <p>${escapeHtml(data.message || '')}</p>
                        <div class="nc-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            <a href="/operacoes/conciliacao" class="nc-btn nc-btn-primary">✔️ Ir para conciliação</a>
                            <a href="/operacoes/arquivos" class="nc-btn nc-btn-outline">📂 Ver arquivos</a>
                            <button type="button" class="nc-btn nc-btn-secondary" onclick="location.reload()">Enviar mais</button>
                        </div>
                    </div>
                `;
                mostrarResultado('success', resumo, true);
                
                if (historyList) {
                    carregarHistoricoUploads();
                }
            }

            function mostrarResultado(type, message, isHtml = false) {
                if (!uploadResult) return;
                
                const className = type === 'error' ? 'nc-error' : 
                                 type === 'warning' ? 'nc-warning' : 'nc-success';
                
                if (isHtml) {
                    uploadResult.innerHTML = `<div class="${className}" role="status">${message}</div>`;
                } else {
                    uploadResult.innerHTML = `
                        <div class="${className}" role="alert">
                            <span aria-hidden="true">${type === 'error' ? '❌' : type === 'warning' ? '⚠️' : '✅'}</span>
                            ${escapeHtml(message)}
                        </div>
                    `;
                }
                uploadResult.setAttribute('aria-live', 'polite');
                uploadResult.style.display = 'block';
                
                uploadResult.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
            // static/js/operacoes.js - Função carregarHistoricoUploads()
            
            function carregarHistoricoUploads() {
                if (!historyList) return;
                
                historyList.innerHTML = '<p class="nc-muted">Carregando histórico...</p>';
                
                // ✅ ✅ ✅ CORREÇÃO: URL deve bater com o blueprint prefix ✅ ✅ ✅
                fetch('/operacoes/api/ultimos-uploads')  // ← ANTES: '/api/operacoes/ultimos-uploads'
                    .then(r => r.json())
                    .then(data => {
                        if (data.ok && data.uploads && data.uploads.length > 0) {
                            historyList.innerHTML = `
                                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                                    ${data.uploads.map(u => `
                                        <div class="file-item" style="padding: 0.5rem; background: var(--gray-lightest); border-radius: 6px;">
                                            <div class="file-info">
                                                <div class="file-name" title="${escapeHtml(u.nome)}">${escapeHtml(u.nome)}</div>
                                                <div class="file-meta">
                                                    <span class="file-date">${u.data ? new Date(u.data).toLocaleDateString('pt-BR') : '—'}</span>
                                                    <span class="file-status">${escapeHtml(u.status)}</span>
                                                </div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            `;
                        } else {
                            historyList.innerHTML = '<p class="nc-muted">Nenhum upload recente.</p>';
                        }
                    })
                    .catch(err => {
                        console.error('Erro ao carregar histórico:', err);
                        historyList.innerHTML = '<p class="nc-muted">Não foi possível carregar histórico.</p>';
                    });
            }
        } // 🔥 FECHAMENTO DO IF DRAG & DROP


        // ============================================================
        // CONCILIAÇÃO
        // ============================================================

        const btnConciliar = document.getElementById("btn-executar-conciliacao");
        const conciliacaoResult = document.getElementById("conciliacao-result");
        const conciliacaoProgress = document.getElementById("conciliacao-progress");
        
        const empresaId = getEmpresaId();
        
        if (btnConciliar && conciliacaoResult) {
        
            btnConciliar.addEventListener("click", async () => {
                
                if (operacoesState.isProcessing) {
                    console.log('⏳ Conciliação já em andamento');
                    return;
                }
    
                if (!empresaId) {
                    conciliacaoResult.innerHTML = `
                        <div class="nc-error" role="alert">
                            ⚠️ Empresa não identificada. Faça login novamente.
                        </div>
                    `;
                    return;
                }

                operacoesState.isProcessing = true;
                conciliacaoResult.innerHTML = `
                    <div class="nc-loading" role="status" aria-live="polite" aria-busy="true">
                        <span class="spinner" aria-hidden="true"></span>
                        <span>Executando conciliação...</span>
                    </div>
                `;
                if (conciliacaoProgress) {
                    conciliacaoProgress.style.display = 'block';
                    updateConciliacaoProgress(0, 'Iniciando...');
                }
                if (btnConciliar) btnConciliar.disabled = true;

                const filtroTipo = document.getElementById('filtroTipoPagamento');
                const tipoPagamento = filtroTipo?.value && filtroTipo.value !== 'todos' ? filtroTipo.value : null;

                try {
                    const response = await fetch("/api/v1/conciliacao/processar", {
                        method: "POST",
                        headers: { 
                            "Content-Type": "application/json",
                            "X-CSRF-Token": getCsrfToken(),
                            "X-Requested-With": "XMLHttpRequest"
                        },
                        body: JSON.stringify({ 
                            tipo_pagamento: tipoPagamento 
                        }),
                        signal: AbortSignal.timeout(60000)
                    });

                    let progressoVisual = 0;
                    const intervaloVisual = setInterval(() => {
                        if (progressoVisual < 90) {
                            progressoVisual += Math.random() * 10;
                            updateConciliacaoProgress(Math.min(progressoVisual, 90), 
                                progressoVisual > 50 ? 'Comparando com recebimentos...' : 'Analisando vendas...');
                        }
                    }, 500);

                    const data = await response.json();
                    clearInterval(intervaloVisual);

                    if (!response.ok || (data.status !== "success" && !data.ok)) {
                        let errorMsg = data.message || data.error || "Erro ao processar conciliação";
                        
                        if (response.status === 401) {
                            errorMsg = 'Sessão expirada. Faça login novamente.';
                            setTimeout(() => window.location.href = '/auth/login?expired=1', 2000);
                        } else if (response.status === 403) {
                            errorMsg = 'Acesso negado. Verifique suas permissões.';
                        } else if (response.status === 408 || errorMsg.includes('timeout')) {
                            errorMsg = 'Processamento demorou muito. Tente com menos dados ou um período menor.';
                        }
                        
                        throw new Error(errorMsg);
                    }

                    updateConciliacaoProgress(100, 'Concluído!');
                    
                    const r = data.resultado || {};

                    conciliacaoResult.innerHTML = `
                        <div class="nc-success" role="status">
                            <h3>✔ Conciliação concluída</h3>
                            <ul class="nc-summary">
                                <li>✅ Vendas conciliadas: <strong>${escapeHtml(r.conciliados || 0)}</strong></li>
                                <li>⚠️ Parciais: <strong>${escapeHtml(r.parciais || 0)}</strong></li>
                                <li>🔗 Multivendas: <strong>${escapeHtml(r.multivendas || 0)}</strong></li>
                                <li>❌ Não conciliadas: <strong>${escapeHtml(r.nao_conciliados || 0)}</strong></li>
                                <li>❓ Créditos sem origem: <strong>${escapeHtml(r.creditos_sem_origem || 0)}</strong></li>
                            </ul>
                            <p>${escapeHtml(data.message || 'Processamento concluído.')}</p>
                            <div class="nc-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                                <a href="/operacoes/detalhado" class="nc-btn nc-btn-primary">📊 Ver detalhamento</a>
                                <a href="/operacoes/arquivos" class="nc-btn nc-btn-outline">📂 Ver arquivos</a>
                            </div>
                        </div>
                    `;
                    
                    conciliacaoResult.scrollIntoView({ behavior: 'smooth', block: 'center' });

                } catch (err) {
                    console.error("❌ Erro conciliação:", err);
                    
                    const msg = err.name === 'TimeoutError' || err.message.includes('timeout')
                        ? 'Processamento demorou muito. Tente com menos dados.' 
                        : err.message || 'Erro ao processar conciliação. Tente novamente.';
                    
                    conciliacaoResult.innerHTML = `
                        <div class="nc-error" role="alert">
                            ❌ ${escapeHtml(msg)}
                        </div>
                    `;
                    
                } finally {
                    operacoesState.isProcessing = false;
                    if (btnConciliar) btnConciliar.disabled = false;
                    if (conciliacaoProgress) {
                        conciliacaoProgress.style.display = 'none';
                    }
                }
            });
        }
        
        function updateConciliacaoProgress(percent, label = null) {
            if (!conciliacaoProgress) return;
            const bar = conciliacaoProgress.querySelector('.nc-progress-bar');
            const text = conciliacaoProgress.querySelector('.nc-progress-text');
            const statusLabel = conciliacaoProgress.querySelector('.nc-progress-status');
            
            if (bar) bar.style.width = percent + '%';
            if (text) text.textContent = `${Math.round(percent)}%`;
            if (statusLabel && label) statusLabel.textContent = label;
            
            conciliacaoProgress.setAttribute('aria-valuenow', Math.round(percent));
        }
        
        // Expor funções globalmente para o template HTML
        window.removerArquivo = window.removerArquivo || function() {};
        window.formatCurrency = window.formatCurrency || function(v) { return v; };
        window.formatFileSize = window.formatFileSize || function(b) { return b + ' bytes'; };
        
        console.log('✅ Operações inicializado com sucesso');
    });
    
})();
