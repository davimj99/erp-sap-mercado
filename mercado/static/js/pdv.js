document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("codigo_barras");

    input.addEventListener("keypress", async function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = input.value.trim();
            if (!codigo) return;

            try {
                const response = await fetch(`/api/pdv/scan/?codigo=${codigo}`);
                const data = await response.json();

                if (data.erro) {
                    alert(data.erro);
                    input.value = "";
                    return;
                }

                atualizarTabela(data);
                input.value = "";
            } catch (error) {
                console.error("Erro:", error);
            }
        }
    });
});

function atualizarTabela(data) {
    const tbody = document.getElementById("tabela-itens");
    const totalEl = document.getElementById("total-geral");

    const novaLinha = `
        <tr>
            <td>${data.produto}</td>
            <td>${data.quantidade}</td>
            <td>R$ ${data.subtotal.toFixed(2)}</td>
            <td>R$ ${data.total_venda.toFixed(2)}</td>
        </tr>
    `;

    tbody.innerHTML += novaLinha;

    totalEl.innerText = `Total: R$ ${data.total_venda.toFixed(2)}`;
}
