document.addEventListener("DOMContentLoaded", function () {
    const codigoInput = document.getElementById("id_codigo_barras");
    if (!codigoInput) return;

    codigoInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = codigoInput.value.trim();
            if (!codigo) return;

            fetch(`/admin/scan/?codigo=${codigo}`)
                .then(r => r.json())
                .then(data => {
                    if (!data.ok) {
                        alert(data.erro);
                        return;
                    }

                    adicionarItemVenda(data);
                    atualizarTotal();
                    codigoInput.value = "";
                });
        }
    });

    function adicionarItemVenda(data) {
        const totalForms = document.getElementById("id_itemvenda_set-TOTAL_FORMS");
        let index = parseInt(totalForms.value);

        // ADICIONA NOVA LINHA SE NECESSÁRIO
        const tabela = document.querySelector("#itemvenda_set-group table tbody");
        const novaLinha = tabela.querySelector("tr.empty-form").cloneNode(true);
        novaLinha.classList.remove("empty-form");

        novaLinha.innerHTML = novaLinha.innerHTML.replace(/__prefix__/g, index);

        tabela.appendChild(novaLinha);

        // Preenche os campos
        document.querySelector(`#id_itemvenda_set-${index}-produto`).value = data.id;
        document.querySelector(`#id_itemvenda_set-${index}-quantidade`).value = 1;
        document.querySelector(`#id_itemvenda_set-${index}-subtotal`).value = data.preco;

        totalForms.value = index + 1;
    }

    // SUBTOTAL AO MUDAR QUANTIDADE
    document.body.addEventListener("input", function (e) {
        if (e.target.name.includes("quantidade")) {
            const index = e.target.name.match(/\d+/)[0];
            const preco = parseFloat(
                document.querySelector(`#id_itemvenda_set-${index}-produto option:checked`).dataset.preco || 0
            );
            const qtd = parseInt(e.target.value || 0);
            document.querySelector(`#id_itemvenda_set-${index}-subtotal`).value = (qtd * preco).toFixed(2);
            atualizarTotal();
        }
    });

    function atualizarTotal() {
        let total = 0;
        document.querySelectorAll("[id$='-subtotal']").forEach(el => {
            const v = parseFloat(el.value || 0);
            total += v;
        });

        // Atualiza label do total
        const totalField = document.querySelector("p:contains('Valor Total:')");
        if (totalField) totalField.innerHTML = `<strong>Total: R$ ${total.toFixed(2)}</strong>`;

        // Atualiza troco se for dinheiro
        const valorPago = parseFloat(document.getElementById("id_valor_pago").value || 0);
        const trocoEl = document.getElementById("id_troco");
        if (trocoEl && !isNaN(valorPago)) {
            let troco = valorPago - total;
            trocoEl.value = troco >= 0 ? troco.toFixed(2) : "0.00";
        }
    }

    // TROCO AO MUDAR "valor pago"
    document.body.addEventListener("input", function (e) {
        if (e.target.id === "id_valor_pago") {
            atualizarTotal();
        }
    });
});
