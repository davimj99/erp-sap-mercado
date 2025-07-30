document.addEventListener('DOMContentLoaded', function () {
    const formaPagamento = document.querySelector('#id_forma_pagamento');
    const valorPagoInput = document.querySelector('#id_valor_pago');
    const valorTotalInput = document.querySelector('#id_valor_total');
    const trocoInput = document.querySelector('#id_troco');
    const produtoSelect = document.querySelector('#id_produto');
    const quantidadeInput = document.querySelector('#id_quantidade');

    // Função para buscar o preço do produto selecionado
    function getPrecoProduto() {
        const option = produtoSelect.options[produtoSelect.selectedIndex];
        // Supondo que o preço esteja armazenado num atributo data-preco do option
        return option ? parseFloat(option.getAttribute('data-preco')) || 0 : 0;
    }

    function calcularValorTotal() {
        const preco = getPrecoProduto();
        const qtd = parseInt(quantidadeInput.value) || 0;
        const total = preco * qtd;
        valorTotalInput.value = total.toFixed(2).replace('.', ',');
        return total;
    }

    function calcularTroco() {
        if (formaPagamento.value !== 'dinheiro') {
            trocoInput.value = '';
            return;
        }

        const pago = parseFloat(valorPagoInput.value.replace(',', '.')) || 0;
        const total = calcularValorTotal();

        if (pago >= total) {
            const troco = (pago - total).toFixed(2).replace('.', ',');
            trocoInput.value = troco;
        } else {
            trocoInput.value = '';
        }
    }

    if (formaPagamento) formaPagamento.addEventListener('change', calcularTroco);
    if (valorPagoInput) valorPagoInput.addEventListener('input', calcularTroco);
    if (produtoSelect) produtoSelect.addEventListener('change', calcularTroco);
    if (quantidadeInput) quantidadeInput.addEventListener('input', calcularTroco);
});
