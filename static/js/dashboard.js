// ============================================================
//  DASHBOARD • NousCard Premium
// ============================================================

let ultimoKpis = null;
let graficoVendas = null;
let graficoBandeiras = null;

document.addEventListener("DOMContentLoaded", () => {
    const kpiVendas = document.querySelector(".kpi-value-vendas");
    const kpiRecebido = document.querySelector(".kpi-value-recebido");
    const kpiDiferenca = document.querySelector(".kpi-value-diferenca");
    const kpiAlertas = document.querySelector(".kpi-value-alertas");

    const ctxGrafico = document.getElementById("graficoVendasRecebidos");
    const ctxBandeiras = document.getElementById("graficoBandeiras");
    const acqContainer = document.getElementById("acqContainer");

    // ================== CARREGAR KPIs DA API ==================
    async function carregarKPIs() {
        try {
            const res = await fetch("/api/dashboard/kpis");
            const data = await res.json();
            if (!data.ok) return;

            ultimoKpis = data.kpis;

            atualizarKPIs(data.kpis);
            atualizarAcquirers(data.kpis.acquirers || {});
            atualizarGraficoVendas(data.kpis, ctxGrafico);
            atualizarGraficoBandeiras(data.kpis.acquirers || {}, ctxBandeiras);

        } catch (err) {
            console.log("Erro ao carregar KPIs:", err);
        }
    }

    // ================== ATUALIZAR VALORES ==================
    function atualizarKPIs(kpis) {
        if (kpiVendas)
            kpiVendas.textContent = "R$ " + kpis.total_vendas.toFixed(2);

        if (kpiRecebido)
            kpiRecebido.textContent = "R$ " + kpis.total_recebido.toFixed(2);

        if (kpiDiferenca)
            kpiDiferenca.textContent = kpis.diferenca.toFixed(2);

        if (kpiAlertas)
            kpiAlertas.textContent = kpis.alertas;
    }

    // ================== ACQUIRERS CARDS ==================
    function classFromAcquirer(nome) {
        const n = nome.toLowerCase();
        if (n.includes("cielo")) return "acq-cielo";
        if (n.includes("rede")) return "acq-rede";
        if (n.includes("getnet")) return "acq-getnet";
        if (n.includes("stone")) return "acq-stone";
        return "acq-outros";
    }

    function atualizarAcquirers(acquirers) {
        if (!acqContainer) return;

        acqContainer.innerHTML = "";

        const nomes = Object.keys(acquirers).sort();

        nomes.forEach(nome => {
            const acq = acquirers[nome];
            const card = document.createElement("div");
            card.className = `nc-acq-card acq-click ${classFromAcquirer(nome)}`;
            card.dataset.acq = nome;

            card.innerHTML = `
                <div class="nc-acq-header">
                    <div class="nc-acq-icon">💳</div>
                    <div class="nc-acq-label">${nome}</div>
                </div>
                <div class="nc-acq-values">
                    <strong>Vendas: R$ ${acq.vendas.toFixed(2)}</strong>
                    <span>Recebido: R$ ${acq.recebidos.toFixed(2)}</span><br>
                    <span>Diferença: R$ ${acq.diferenca.toFixed(2)}</span>
                </div>
            `;

            acqContainer.appendChild(card);
        });

        // Listeners para abrir modal por adquirente
        document.querySelectorAll(".acq-click").forEach(card => {
            card.addEventListener("click", () => {
                if (!ultimoKpis) return;
                const nome = card.dataset.acq;
                const linhas = (ultimoKpis.detalhamento?.vendas || [])
                    .filter(l => (l.adquirente || "Outros") === nome);

                abrirModal(
                    `Detalhamento de Vendas — ${nome}`,
                    linhas
                );
            });
        });
    }

    // ================== GRÁFICO VENDAS x RECEBIDO ==================
    function atualizarGraficoVendas(kpis, ctx) {
        if (!ctx) return;

        if (graficoVendas) graficoVendas.destroy();

        graficoVendas = new Chart(ctx, {
            type: "bar",
            data: {
                labels: ["Vendas", "Recebido"],
                datasets: [{
                    label: "Valores",
                    data: [kpis.total_vendas, kpis.total_recebido],
                    backgroundColor: ["#1877f2", "#3cb371"],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) =>
                                "R$ " + value.toLocaleString("pt-BR", { minimumFractionDigits: 2 })
                        }
                    }
                }
            }
        });
    }

    // ================== GRÁFICO BANDEIRAS (pizza simples) ==================
    function atualizarGraficoBandeiras(acquirers, ctx) {
        if (!ctx) return;

        const labels = Object.keys(acquirers);
        if (!labels.length) return;

        const valores = labels.map(l => acquirers[l].vendas || 0);

        if (graficoBandeiras) graficoBandeiras.destroy();

        graficoBandeiras = new Chart(ctx, {
            type: "pie",
            data: {
                labels,
                datasets: [{
                    label: "Vendas por Adquirente",
                    data: valores,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: "bottom" }
                }
            }
        });
    }

    // ================== MODAL ==================
    window.abrirModal = function (titulo, linhas) {
        const modal = document.getElementById("modalDetalhe");
        const tituloEl = document.getElementById("modalTitulo");
        const tabela = document.getElementById("modalTabela");

        if (!modal || !tituloEl || !tabela) return;

        tituloEl.textContent = titulo;

        if (!linhas || !linhas.length) {
            tabela.innerHTML = `<tr><td>Nenhum registro encontrado.</td></tr>`;
        } else {
            tabela.innerHTML = `
                <thead>
                    <tr>
                        <th>Data Venda</th>
                        <th>Adquirente</th>
                        <th>Descrição</th>
                        <th>Valor</th>
                        <th>Previsão</th>
                        <th>Banco</th>
                        <th>Data Receb.</th>
                        <th>Tipo</th>
                    </tr>
                </thead>
                <tbody>
                    ${linhas.map(l => `
                        <tr>
                            <td>${l.data || "-"}</td>
                            <td>${l.adquirente || "-"}</td>
                            <td>${l.descricao || "-"}</td>
                            <td>R$ ${Number(l.valor || 0).toFixed(2)}</td>
                            <td>${l.previsao || "-"}</td>
                            <td>${l.banco || "-"}</td>
                            <td>${l.data_recebimento || "-"}</td>
                            <td>${l.tipo || "-"}</td>
                        </tr>
                    `).join("")}
                </tbody>
            `;
        }

        modal.style.display = "block";
    };

    window.fecharModal = function () {
        const modal = document.getElementById("modalDetalhe");
        if (modal) modal.style.display = "none";
    };

    // ================== CLIQUES NOS KPIs ==================
    document.querySelectorAll(".kpi-click").forEach(card => {
        card.addEventListener("click", () => {
            if (!ultimoKpis) return;
            const acao = card.dataset.acao;

            if (acao === "vendas") {
                abrirModal("Detalhamento de Vendas", ultimoKpis.detalhamento?.vendas || []);
            } else if (acao === "recebidos") {
                abrirModal("Detalhamento de Recebimentos", ultimoKpis.detalhamento?.recebidos || []);
            } else if (acao === "diferencas") {
                // Por enquanto, usamos todas as vendas como "diferenças"
                // (amanhã a gente implementa a conciliação real)
                abrirModal("Diferenças (vendas ainda não conciliadas)", ultimoKpis.detalhamento?.vendas || []);
            }
        });
    });

    // ================== LOOP ==================
    carregarKPIs();
    setInterval(carregarKPIs, 10000);
});
