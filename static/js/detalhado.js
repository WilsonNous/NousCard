document.addEventListener("DOMContentLoaded", async () => {

    const container = document.getElementById("detalhadoContainer");
    container.innerHTML = "<p>⏳ Carregando detalhamento...</p>";

    try {
        const res = await fetch("/operacoes/api/detalhado");
        const data = await res.json();

        if (!data.ok) {
            container.innerHTML = `<p style='color:red'>Erro ao carregar dados.</p>`;
            return;
        }

        const vendas = data.dados.vendas || [];
        const creditos = data.dados.creditos_sem_origem || [];

        let html = "";

        // =========================================================
        // 🎯 LISTA DE VENDAS DETALHADAS
        // =========================================================
        html += `
        <h3>📌 Vendas e Conciliações</h3>
        <table class="detalhado-table">
            <thead>
                <tr>
                    <th>Data Venda</th>
                    <th>Adquirente</th>
                    <th>Bandeira</th>
                    <th>Produto</th>
                    <th>Valor Líquido</th>
                    <th>Conciliado</th>
                    <th>Faltante</th>
                    <th>Previsão</th>
                    <th>Recebimentos</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
        `;

        vendas.forEach(v => {

            const statusClass =
                v.status === "conciliado" ? "status-ok" :
                v.status === "parcial" ? "status-parcial" :
                "status-pendente";

            let recebHtml = "-";

            if (v.recebimentos.length > 0) {
                recebHtml = v.recebimentos
                    .map(r => `${r.data} — R$ ${r.valor.toFixed(2)} (${r.banco})`)
                    .join("<br>");
            }

            html += `
                <tr>
                    <td>${v.data_venda}</td>
                    <td>${v.adquirente}</td>
                    <td>${v.bandeira}</td>
                    <td>${v.produto}</td>
                    <td>R$ ${v.valor_liquido.toFixed(2)}</td>
                    <td>R$ ${v.valor_conciliado.toFixed(2)}</td>
                    <td>R$ ${v.faltante.toFixed(2)}</td>
                    <td>${v.previsao_pagamento}</td>
                    <td>${recebHtml}</td>
                    <td class="${statusClass}">${v.status.toUpperCase()}</td>
                </tr>
            `;
        });

        html += "</tbody></table>";

        // =========================================================
        // 🎯 RECEBIMENTOS SEM ORIGEM
        // =========================================================
        html += `
            <h3 style="margin-top:40px;">⚠️ Créditos sem Origem</h3>
            <table class="detalhado-table">
                <thead>
                    <tr>
                        <th>Data</th>
                        <th>Descrição</th>
                        <th>Valor</th>
                    </tr>
                </thead>
                <tbody>
        `;

        if (creditos.length === 0) {
            html += `
                <tr>
                    <td colspan="3" style="text-align:center; color:#777">
                        Nenhum crédito pendente
                    </td>
                </tr>`;
        } else {
            creditos.forEach(c => {
                html += `
                    <tr>
                        <td>${c.data_movimento}</td>
                        <td>${c.descricao}</td>
                        <td>R$ ${c.valor.toFixed(2)}</td>
                    </tr>
                `;
            });
        }

        html += "</tbody></table>";

        // =========================================================
        // FINAL: renderiza tudo
        // =========================================================
        container.innerHTML = html;


    } catch (err) {
        console.error(err);
        container.innerHTML = "<p style='color:red'>Erro ao carregar detalhamento.</p>";
    }

});
