document.addEventListener("DOMContentLoaded", () => {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const form = document.getElementById("uploadForm");
  const resultDiv = document.getElementById("uploadResult");

  if (!dropZone || !fileInput || !form) return;

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    fileInput.files = e.dataTransfer.files;
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const files = fileInput.files;
    if (!files || files.length === 0) {
      resultDiv.textContent = "Nenhum arquivo selecionado.";
      return;
    }

    const formData = new FormData();
    for (const f of files) {
      formData.append("files[]", f);
    }

    resultDiv.textContent = "Processando arquivos...";

    const response = await fetch("/upload/files", {
      method: "POST",
      body: formData
    });

    const data = await response.json();
    if (!data.ok) {
      resultDiv.textContent = data.message || "Erro ao processar arquivos.";
      return;
    }

    const linhas = data.result
      .map(r => `${r.arquivo} → ${r.tipo} (${r.linhas} linhas)`)
      .join("\n");

    resultDiv.textContent = `Arquivos analisados:\n${linhas}`;
  });
});
