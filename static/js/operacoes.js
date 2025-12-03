document.addEventListener("DOMContentLoaded", () => {

    // ====================================================================================
    //  DRAG & DROP (somente se existir)
    // ====================================================================================
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const uploadForm = document.getElementById("uploadForm");
    const uploadResult = document.getElementById("uploadResult");

    if (dropZone && fileInput && uploadForm) {

        dropZone.addEventListener("click", () => fileInput.click());

        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragging");
        });

        dropZone.addEventListener("dragleave", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragging");
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragging");
            fileInput.files = e.dataTransfer.files;
        });

        // ================= UPLOAD =================
        uploadForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            uploadResult.innerHTML = `<p>⏳ Processando arquivos...</p>`;

            const files = fileInput.files;
            if (!files.length) {
                uploadResult.innerHTML = `<p style="color:red">Nenhum arquivo selecionado.</p>`;
                return;
            }

            const formData = new FormData();
            for (const f of files) formData.append("files", f);

            try {
                const response = await fetch("/operacoes/upload", {
                    method: "POST",
                    body: formData,
                });

                const data = await response.json();

                if (!data.ok) {
                    uploadResult.innerHTML = `<p style="color:red">${data.message}</p>`;
                    return;
                }

                uploadResult.innerHTML = `
                    <div style="background:#eaf3ff;padding:15px;border-radius:8px;margin-top:12px;">
                        <h3>✔ Arquivos processados</h3>
                        <p><strong>Total de arquivos:</strong> ${data.total_arquivos}</p>
                        <p><strong>Vendas:</strong> ${data.qtde_vendas}</p>
                        <p><strong>Recebimentos:</strong> ${data.qtde_recebimentos}</p>
                        <p><strong>Total Vendas:</strong> R$ ${data.total_vendas.toFixed(2)}</p>
                        <p><strong>Total Recebido:</strong> R$ ${data.total_recebimentos.toFixed(2)}</p>
                        <p>${data.message}</p>
                    </div>
                `;
            } catch (err) {
                uploadResult.innerHTML = `<p style="color:red">Erro ao enviar arquivos.</p>`;
            }
        });

    }  // 🔥🔥🔥 FECHAMENTO DO IF FALTANDO — ESSA LINHA CORRIGE O ERRO!!!


    // ====================================================================================
    //  CONCILIAÇÃO (somente se existir)
    // ====================================================================================
    const btnConciliar = document.getElementById("btnConciliar");
    const conciliacaoResumo = document.getElementById("conciliacaoResumo");
    
    if (btnConciliar && conciliacaoResumo) {
    
        btnConciliar.addEventListener("click", async () => {
    
            conciliacaoResumo.innerHTML = `<p>⏳ Executando conciliação...</p>`;
    
            try {
    
                const response = await fetch("/operacoes/conciliar", {
                    method: "POST",
                });
    
                const data = await response.json();
    
                if (!data.ok) {
                    conciliacaoResumo.innerHTML = `
                        <p style="color:red">❌ ${data.message || "Erro ao processar conciliação."}</p>
                    `;
                    return;
                }
    
                const r = data.resultado;
    
                conciliacaoResumo.innerHTML = `
                    <div style="background:#eaf8ea;padding:15px;border-radius:8px;margin-top:12px;">
                        <h3>✔ Conciliação concluída</h3>
    
                        <p><strong>Total de Vendas:</strong> R$ ${r.total_vendas.toFixed(2)}</p>
                        <p><strong>Total Recebido:</strong> R$ ${r.total_recebimentos.toFixed(2)}</p>
                        <p><strong>Diferença:</strong> 
                            <span style="color:${r.diferenca === 0 ? "#0a0" : "#c00"};">
                                R$ ${r.diferenca.toFixed(2)}
                            </span>
                        </p>
    
                        <hr>
    
                        <p><strong>Arquivos analisados:</strong> ${r.arquivos_processados}</p>
                    </div>
                `;
    
            } catch (err) {
                console.error("Erro conciliação:", err);
                conciliacaoResumo.innerHTML = `<p style="color:red">Erro ao processar conciliação.</p>`;
            }
        });
    }

});
