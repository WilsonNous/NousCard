// ============================================================
//  DASHBOARD • NousCard Premium
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // Elementos HTML
    const kpiVendas = document.querySelector(".kpi-value-vendas");
    const kpiRecebido = document.querySelector(".kpi-value-recebido");
    const kpiDiferenca = document.querySelector(".kpi-value-diferenca");
    const kpiAlertas = document.querySelector(".kpi-value-alertas");

    const ctxGrafico = document.getElementById("graficoVendasRecebidos");
    const ctxBandeiras = document.getElementById("graficoBandeiras");

    let graficoVendas = null;
    let graficoBandeiras = null;

    // ============================================================
    //  Função: Buscar KPIs da API
    // ============================================================
    async function carregarKPIs() {
        try {
            const res = await fetch("/api/dashboard/kpis");
            const data = await res.json();

            if (!data.ok) return;

            atualizarKPIs(data.kpis);
            atualizarGraficoVendas(data.kpis);
            atualizarGraficoBandeiras(data.kpis.bandeiras || {});

        } catch (err) {
            console.log("Erro ao carregar KPIs:", err);
        }
    }

    // ============================================================
    //  Atualização dos valores dos KPIs
    // ============================================================
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

    // ============================================================
    //  Gráfico: Vendas x Recebido
    // ============================================================
    function atualizarGraficoVendas(kpis) {

        if (!ctxGrafico) return;

        if (graficoVendas) graficoVendas.destroy(); // limpa gráfico anterior

        graficoVendas = new Chart(ctxGrafico, {
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

    // ============================================================
    //  Gráfico: Bandeiras (Pizza)
    // ============================================================
    function atualizarGraficoBandeiras(bandeiras) {

        if (!ctxBandeiras) return;
        if (!bandeiras || Object.keys(bandeiras).length === 0) return;

        if (graficoBandeiras) graficoBandeiras.destroy();

        graficoBandeiras = new Chart(ctxBandeiras, {
            type: "pie",
            data: {
                labels: Object.keys(bandeiras),
                datasets: [{
                    label: "Vendas por Bandeira",
                    data: Object.values(bandeiras),
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

    // ============================================================
    //  Atualização automática a cada 10 segundos
    // ============================================================
    setInterval(carregarKPIs, 10000);

    // Carrega ao iniciar
    carregarKPIs();
});
