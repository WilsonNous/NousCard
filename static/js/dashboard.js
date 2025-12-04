// ============================================================
//  DASHBOARD • NousCard Premium
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    const kpiVendas = document.querySelector(".kpi-value-vendas");
    const kpiRecebido = document.querySelector(".kpi-value-recebido");
    const kpiDiferenca = document.querySelector(".kpi-value-diferenca");
    const kpiAlertas = document.querySelector(".kpi-value-alertas");

    const ctxGrafico = document.getElementById("graficoVendasRecebidos");
    const ctxBandeiras = document.getElementById("graficoBandeiras");

    const acqContainer = document.getElementById("acqContainer");

    let graficoVendas = null;
    let graficoBandeiras = null;

    // ============================================================
    async function carregarKPIs() {
        try {
            const res = await fetch("/api/dashboard/kpis");
            const data = await res.json();

            if (!data.ok) return;

            atualizarKPIs(data.kpis);
            atualizarGraficoVendas(data.kpis);
            atualizarGraficoBandeiras(data.kpis.bandeiras);
            atualizarAdquirentes(data.kpis.adquirentes);

        } catch (err) {
            console.log("Erro ao carregar KPIs:", err);
        }
    }

    // ============================================================
    function atualizarKPIs(kpis) {

        kpiVendas.textContent = "R$ " + kpis.total_vendas.toFixed(2);
        kpiRecebido.textContent = "R$ " + kpis.total_recebido.toFixed(2);
        kpiDiferenca.textContent = kpis.diferenca.toFixed(2);
        kpiAlertas.textContent = kpis.alertas;
    }

    // ============================================================
    function atualizarAdquirentes(adquirentes) {
        acqContainer.innerHTML = "";

        if (!adquirentes || Object.keys(adquirentes).length === 0) {
            acqContainer.innerHTML = "<p>Nenhuma venda encontrada</p>";
            return;
        }

        for (const [nome, valor] of Object.entries(adquirentes)) {

            const icons = {
                "Cielo": "💳",
                "Rede": "🟧",
                "Getnet": "🟥",
                "Stone": "🟩",
                "PagSeguro": "🟢",
                "Outros": "⚪"
            };

            const colorClass = {
                "Cielo": "acq-cielo",
                "Rede": "acq-rede",
                "Getnet": "acq-getnet",
                "Stone": "acq-stone",
                "PagSeguro": "acq-pagseguro",
                "Outros": "acq-outros",
            };

            acqContainer.insertAdjacentHTML(
                "beforeend",
                `
                <div class="nc-acq-card ${colorClass[nome] || 'acq-outros'}">
                    <div class="nc-acq-icon">${icons[nome] || "💳"}</div>
                    <div class="nc-acq-label">${nome}</div>
                    <div class="nc-acq-value">R$ ${valor.toFixed(2)}</div>
                </div>
                `
            );
        }
    }

    // ============================================================
    function atualizarGraficoVendas(kpis) {
        if (!ctxGrafico) return;

        if (graficoVendas) graficoVendas.destroy();

        graficoVendas = new Chart(ctxGrafico, {
            type: "bar",
            data: {
                labels: ["Vendas", "Recebido"],
                datasets: [{
                    data: [kpis.total_vendas, kpis.total_recebido],
                    backgroundColor: ["#1877f2", "#3cb371"],
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    // ============================================================
    function atualizarGraficoBandeiras(bandeiras) {
        if (!ctxBandeiras) return;
        if (!bandeiras) return;

        if (graficoBandeiras) graficoBandeiras.destroy();

        graficoBandeiras = new Chart(ctxBandeiras, {
            type: "pie",
            data: {
                labels: Object.keys(bandeiras),
                datasets: [{
                    data: Object.values(bandeiras),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: "bottom" } }
            }
        });
    }

    carregarKPIs();
    setInterval(carregarKPIs, 10000);
});
