document.addEventListener("DOMContentLoaded", () => {
    carregarDetalhado();
});

async function carregarDetalhado() {

    const container = document.getElementById("detalhadoContainer");
    const empresaId = window.EMPRESA_ID;

    container.innerHTML = "<p>⏳ Carregando dados...</p>";

    try {
        const res = await fetch(`/api/conciliacao/detalhes?empresa_id=${empresaId}`);
        const data = await res.json();

        if (data.status !== "success") {
            container.innerHTML = "<p style='color:red'>Erro ao carregar dados.</p>";
            return;
        }

        // Junta todas as listas em uma única tabela
        const linhas = [
            ...data.conciliadas,
            ...data.parciais,
            ...data.pendentes,
            ...data.nao_recebidas,
        ];

        montarTabela(linhas);

    } catch (err) {
        console.error(err);
        container.innerHTML = "<p style='color:red'>Falha ao comunicar com o servidor.</p>";
    }
}


function montarTabela(linhas) {
    const container = document.getElementById("detalhadoContainer");

    if (!linhas.length) {
        container.innerHTML = "<p>Nenhum dado encontrado.</p>";
        return;
    }

    let html = `
        <table class="detalhado-table">
            <thead>
                <tr>
                    <th>Data Venda</th>
                    <th>Adquirente</th>
                    <th>Bandeira</th>
                    <th>Valor</th>
                    <th>Previsto</th>
                    <th>Conciliado</th>
                    <th>Diferença</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    `;

    for (const row of linhas) {

        const liquido = row.valor_liquido ?? 0;
        const conciliado = row.valor_conciliado ?? 0;
        const diff = liquido - conciliado;

        let statusClass =
            row.status === "conciliado"
                ? "status-ok"
                : row.status === "parcial"
                ? "status-parcial"
                : "status-pendente";

        html += `
            <tr>
                <td>${row.data_venda || ""}</td>
                <td>${row.adquirente || ""}</td>
                <td>${row.bandeira || ""}</td>
                <td>R$ ${liquido.toFixed(2)}</td>
                <td>${row.data_prevista || ""}</td>
                <td>R$ ${conciliado.toFixed(2)}</td>
                <td style="color:${diff === 0 ? "#008000" : "#cc0000"};">
                    R$ ${diff.toFixed(2)}
                </td>
                <td class="${statusClass}">${row.status}</td>
            </tr>
        `;
    }

    html += "</tbody></table>";

    container.innerHTML = html;
}
