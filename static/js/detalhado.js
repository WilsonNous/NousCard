document.addEventListener("DOMContentLoaded", () => {
    carregarDetalhado();
});

async function carregarDetalhado() {

    const container = document.getElementById("detalhadoContainer");

    try {
        const res = await fetch("/operacoes/api/detalhado");
        const data = await res.json();

        if (!data.ok) {
            container.innerHTML = "<p style='color:red'>Erro ao carregar dados.</p>";
            return;
        }

        montarTabela(data.dados);

    } catch (err) {
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
                    <th>Descrição</th>
                    <th>Valor</th>
                    <th>Previsão</th>
                    <th>Recebido</th>
                    <th>Data</th>
                    <th>Banco</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    `;

    for (const row of linhas) {
        const stClass = row.status === "Recebido" ? "status-ok" : "status-pendente";

        html += `
            <tr>
                <td>${row.data_venda}</td>
                <td>${row.adquirente}</td>
                <td>${row.descricao}</td>
                <td>R$ ${row.valor_venda.toFixed(2)}</td>
                <td>${row.previsao}</td>
                <td>R$ ${row.recebido.toFixed(2)}</td>
                <td>${row.data_recebimento}</td>
                <td>${row.banco}</td>
                <td class="${stClass}">${row.status}</td>
            </tr>
        `;
    }

    html += "</tbody></table>";

    container.innerHTML = html;
}
