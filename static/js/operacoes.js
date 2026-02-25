// ============================================================
//  OPERAÇÕES • NousCard (VERSÃO SEGURA)
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // ============================================================
    // UTILITÁRIOS SEGUROS
    // ============================================================

    /**
     * Escapa HTML para prevenir XSS
     */
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

    /**
     * Formata moeda com precisão
     */
    function formatCurrency(value) {
        const num = typeof value === 'string' ? parseFloat(value) : value;
        if (isNaN(num)) return 'R$ 0,00';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            minimumFractionDigits: 2
        }).format(num);
    }

    /**
     * Obtém token CSRF
     */
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content ||
               document.querySelector('input[name="csrf_token"]')?.value ||
               '';
    }

    /**
     * Obtém empresa_id de forma segura
     */
    function getEmpresaId() {
        return document.body.dataset.empresaId || null;
    }

    /**
     * Valida arquivo antes do upload
     */
    function validarArquivo(file) {
        const allowedTypes = [
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/x-ofx',
            'text/plain'
        ];
        const allowedExtensions = ['.csv', '.xlsx', '.xls', '.ofx', '.txt'];
        const maxSize = 10 * 1024 * 1024; // 10MB

        const errors = [];

        // Validar tipo MIME
        if (!allowedTypes.includes(file.type) && 
            !allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext))) {
            errors.push(`Tipo de arquivo não permitido: ${file.name}`);
        }

        // Validar tamanho
        if (file.size > maxSize) {
            errors.push(`Arquivo muito grande: ${file.name} (${formatFileSize(file.size)})`);
        }

        // Validar nome (prevenir path traversal)
        if (file.name.includes('/') || file.name.includes('\\') || file.name.startsWith('.')) {
            errors.push(`Nome de arquivo inválido: ${file.name}`);
        }

        return errors;
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // ============================================================
    // DRAG & DROP + UPLOAD
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

    if (dropZone && fileInput && uploadForm) {

        // Clique na zona abre o seletor
        dropZone.addEventListener("click", () => fileInput.click());

        // Drag & Drop handlers
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('nc-dropzone-dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('nc-dropzone-dragover');
            }, false);
        });

        // Handle do drop
        dropZone.addEventListener('drop', e => {
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                handleFileSelection(files);
            }
        }, false);

        // Handle da seleção via input
        fileInput.addEventListener('change', e => {
            handleFileSelection(e.target.files);
        });

        // Validar e mostrar preview dos arquivos
        function handleFileSelection(files) {
            const errors = [];
            const validFiles = [];

            Array.from(files).forEach(file => {
                const fileErrors = validarArquivo(file);
                if (fileErrors.length) {
                    errors.push(...fileErrors);
                } else {
                    validFiles.push(file);
                }
            });

            // Mostrar erros
            if (errors.length && uploadErrors) {
                uploadErrors.innerHTML = errors.map(err => 
                    `<div>❌ ${escapeHtml(err)}</div>`
                ).join('');
                uploadErrors.style.display = 'block';
                uploadErrors.setAttribute('role', 'alert');
            } else if (uploadErrors) {
                uploadErrors.style.display = 'none';
            }

            // Mostrar preview dos válidos
            if (validFiles.length && fileList) {
                fileList.innerHTML = validFiles.map(f => 
                    `<div class="nc-file-item">📄 ${escapeHtml(f.name)} <small>(${formatFileSize(f.size)})</small></div>`
                ).join('');
                fileList.style.display = 'block';
            } else if (fileList) {
                fileList.style.display = 'none';
            }

            // Atualizar input com apenas arquivos válidos
            if (validFiles.length !== files.length) {
                const dt = new DataTransfer();
                validFiles.forEach(f => dt.items.add(f));
                fileInput.files = dt.files;
            }
        }

        // ================= UPLOAD COM PROGRESSO =================
        uploadForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const files = fileInput.files;
            
            // Validar seleção
            if (!files || !files.length) {
                mostrarResultado('error', 'Nenhum arquivo selecionado.');
                return;
            }

            // Validar novamente antes de enviar
            const allErrors = [];
            Array.from(files).forEach(f => {
                allErrors.push(...validarArquivo(f));
            });
            if (allErrors.length) {
                mostrarResultado('error', allErrors[0]);
                return;
            }

            // UI: Loading state
            mostrarLoading();

            const formData = new FormData();
            for (const f of files) formData.append("files", f);

            let xhr = null;

            try {
                // Usar XMLHttpRequest para progresso real
                xhr = new XMLHttpRequest();
                
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable && uploadProgress) {
                        const percent = Math.round((e.loaded / e.total) * 100);
                        updateProgress(percent);
                    }
                });

                xhr.onload = () => {
                    if (xhr.status === 200) {
                        try {
                            const data = JSON.parse(xhr.responseText);
                            handleUploadResponse(data);
                        } catch (err) {
                            throw new Error('Resposta inválida do servidor');
                        }
                    } else {
                        throw new Error(`Erro HTTP: ${xhr.status}`);
                    }
                };

                xhr.onerror = () => {
                    throw new Error('Erro de rede ao enviar arquivos');
                };

                xhr.open('POST', '/operacoes/upload');
                
                // Adicionar CSRF token
                const csrfToken = getCsrfToken();
                if (csrfToken) {
                    xhr.setRequestHeader('X-CSRF-Token', csrfToken);
                }

                xhr.send(formData);

            } catch (err) {
                console.error("Erro ao enviar arquivos:", err);
                mostrarResultado('error', 'Erro ao enviar arquivos. Tente novamente.');
            } finally {
                // Restaurar UI
                resetUploadUI();
            }
        });

        // Cancelar upload
        if (btnCancel) {
            btnCancel.addEventListener('click', () => {
                if (xhr && xhr.readyState !== 4) {
                    xhr.abort();
                    mostrarResultado('warning', 'Upload cancelado pelo usuário.');
                    resetUploadUI();
                }
            });
        }

        // Helpers de UI
        function mostrarLoading() {
            if (uploadResult) {
                uploadResult.innerHTML = `
                    <div class="nc-loading" role="status" aria-live="polite">
                        <span class="spinner" aria-hidden="true"></span>
                        <span>Processando arquivos...</span>
                    </div>
                `;
            }
            if (uploadProgress) {
                uploadProgress.style.display = 'block';
                updateProgress(0);
            }
            if (btnUpload) btnUpload.disabled = true;
            if (btnCancel) btnCancel.style.display = 'inline-block';
        }

        function updateProgress(percent) {
            if (!uploadProgress) return;
            const bar = uploadProgress.querySelector('.nc-progress-bar');
            const text = uploadProgress.querySelector('.nc-progress-text');
            if (bar) bar.style.width = percent + '%';
            if (text) text.textContent = percent + '%';
            uploadProgress.setAttribute('aria-valuenow', percent);
        }

        function resetUploadUI() {
            if (btnUpload) btnUpload.disabled = false;
            if (btnCancel) btnCancel.style.display = 'none';
            if (uploadProgress) uploadProgress.style.display = 'none';
        }

        function handleUploadResponse(data) {
            if (!data.ok) {
                mostrarResultado('error', data.message || 'Erro ao processar arquivos.');
                return;
            }

            // Construir resultado seguro
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
                    <div class="nc-actions">
                        <a href="/operacoes/conciliacao" class="nc-btn nc-btn-primary">✔️ Ir para conciliação</a>
                        <button type="button" class="nc-btn nc-btn-outline" onclick="location.reload()">Enviar mais</button>
                    </div>
                </div>
            `;
            mostrarResultado('success', resumo, true);
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
    
            if (!empresaId) {
                conciliacaoResult.innerHTML = `
                    <div class="nc-error" role="alert">
                        ⚠️ Empresa não identificada. Faça login novamente.
                    </div>
                `;
                return;
            }

            // UI: Loading
            conciliacaoResult.innerHTML = `
                <div class="nc-loading" role="status" aria-live="polite">
                    <span class="spinner" aria-hidden="true"></span>
                    <span>Executando conciliação...</span>
                </div>
            `;
            if (conciliacaoProgress) {
                conciliacaoProgress.style.display = 'block';
            }
            btnConciliar.disabled = true;

            try {
                const response = await fetch("/api/v1/conciliacao/processar", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "X-CSRF-Token": getCsrfToken()
                    },
                    body: JSON.stringify({}), // empresa_id vem da sessão no backend
                    signal: AbortSignal.timeout(60000) // 60s timeout
                });

                const data = await response.json();

                if (!data.ok && !data.status === "success") {
                    throw new Error(data.message || data.error || "Erro ao processar conciliação");
                }

                const r = data.resultado || {};

                // Resultado seguro
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
                        <div class="nc-actions">
                            <a href="/operacoes/detalhado" class="nc-btn nc-btn-primary">📊 Ver detalhamento</a>
                        </div>
                    </div>
                `;

            } catch (err) {
                console.error("Erro conciliação:", err);
                
                const msg = err.name === 'TimeoutError' 
                    ? 'Processamento demorou muito. Tente com menos dados.' 
                    : 'Erro ao processar conciliação. Tente novamente.';
                
                conciliacaoResult.innerHTML = `
                    <div class="nc-error" role="alert">
                        ❌ ${escapeHtml(msg)}
                    </div>
                `;
            } finally {
                // Restaurar UI
                btnConciliar.disabled = false;
                if (conciliacaoProgress) {
                    conciliacaoProgress.style.display = 'none';
                }
            }
        });
    }

});
