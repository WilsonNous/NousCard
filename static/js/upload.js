document.addEventListener("DOMContentLoaded", () => {
    console.log("operacoes.js carregado...");

    // ============================================================================
    //  DRAG & DROP
    // ============================================================================
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const form = document.getElementById("uploadForm");
    const resultDiv = document.getElementById("uploadResult");

    if (dropZone && fileInput && form) {

        dropZone.addEventListener("click", () => fileInput.click());

        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragging");
        });

        dropZone.addEventListener("dragleave", () => {
            dropZone.classList.remove("dragging");
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragging");
            fileInput.files = e.dataTransfer.files;
        });


        // ============================================================================
        //  UPLOAD
        // ============================================================================
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const files = fileInput.files;

            if (!files || files.length === 0) {
                resultDiv.textContent = "Nenhum arquivo selecionado.";
                return;
            }

            const formData = new FormData();
            for (const f of files) {
                formData.append("files", f); // ✔ NOME CORRETO
            }

            resultDiv.innerHTML = `<p>⏳ Processando arquivos...</p>`;

            try {
                const response = await fetch("/operacoes/upload", {
                    method: "POST",
                    body: formData,
                });

                const data = await response.json();

                if (!data.ok) {
                    resultDiv.innerHTML = `<p style="color: red;">${data.message || "Erro ao processar arquivos."}</p>`;
                    return;
                }

                // Monta lista dos arquivos processados
                const linhas = data.result
                    .map(r => `
                        <div style="padding:4px 0;">
                            📄 <strong>${r.arquivo}</strong>  
                            — <em>${r.tipo}</em>  
                            — ${r.linhas} linha(s)
                        </div>
                    `)
                    .join("");

                resultDiv.innerHTML = `
                    <div style="background:#eaf3ff;padding:15px;border-radius:8px;margin-top:12px;">
                        <h3>✔ Arquivos processados</h3>
                        ${linhas}
                    </div>
                `;

            } catch (err) {
                console.error(err);
                resultDiv.innerHTML = `<p style="color:red;">Erro ao enviar arquivos.</p>`;
            }
        });
    }
});
