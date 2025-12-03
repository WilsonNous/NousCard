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

    let grafico = null;

    // ============================================================
    //  Função: Buscar KPIs da API
    // ============================================================
    async function carregarKPIs() {
        try {
            const res = await fetch("/api/dashboard/kpis");
            const data = await res.json();

            if (!data.ok) return;

            atualizarKPIs(data.kpis);
            atualizarGrafico(data.kpis);

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
    //  Montar ou atualizar gráfico
    // ============================================================
    function atualizarGrafico(kpis) {

        if (!ctxGrafico) return;

        if (grafico) grafico.destroy(); // limpa gráfico anterior

        grafico = new Chart(ctxGrafico, {
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
    //  Atualização automática a cada 10 segundos
    // ============================================================
    setInterval(carregarKPIs, 10000);

    // Carrega ao iniciar
    carregarKPIs();
});
