from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from simple_history.models import HistoricalRecords

# Sinais
from django.db.models.signals import pre_delete
from django.dispatch import receiver

# -------------------------------
# PRODUTO
# -------------------------------
class Produto(models.Model):
    CATEGORIAS = [
        ('comida', 'Comida'),
        ('bebida_nao_alcoolica', 'Bebida Não Alcoólica'),
        ('bebida_alcoolica', 'Bebida Alcoólica'),
        ('doces', 'Doces'),
        ('acessorios', 'Acessórios'),
        ('cigarros', 'Cigarros')
    ]

    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=6, decimal_places=2)
    estoque = models.PositiveIntegerField()
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    codigo_barras = models.CharField(max_length=50, unique=True, blank=True, null=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.nome

    def verificar_estoque(self, quantidade):
        if quantidade is None:
            return False
        return self.estoque >= quantidade

    def diminuir_estoque(self, quantidade):
        if self.verificar_estoque(quantidade):
            self.estoque -= quantidade
            self.save()
            return True
        return False

    def aumentar_estoque(self, quantidade):
        self.estoque += quantidade
        self.save()


# -------------------------------
# CLIENTE
# -------------------------------
class Cliente(models.Model):
    TIPOS = [
        ('cliente', 'Cliente'),
        ('conta', 'Conta'),
    ]

    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    equipe = models.CharField(max_length=100, blank=True, null=True)
    cor = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    def get_total_quantidade_comprada(self):
        total = self.vendas.aggregate(total=Sum('quantidade'))['total']
        return total or 0

    def get_total_valor_comprado(self):
        total = self.vendas.aggregate(total=Sum('valor_pago'))['total']
        return total or Decimal('0.00')


class ClienteResumo(Cliente):
    class Meta:
        proxy = True
        verbose_name = 'Resumo de Vendas'
        verbose_name_plural = 'Resumo de Vendas'
        ordering = ['nome']


# -------------------------------
# VENDA
# -------------------------------
class Venda(models.Model):
    FORMAS_PAGAMENTO = [
        ('pix', 'Pix'),
        ('credito', 'Cartão de Crédito'),
        ('debito', 'Cartão de Débito'),
        ('dinheiro', 'Dinheiro'),
        ('em aberto', 'Em aberto')
    ]

    data_venda = models.DateTimeField(auto_now_add=True)
    cliente = models.ForeignKey('Cliente', on_delete=models.SET_NULL, null=True, blank=True, related_name='vendas')
    forma_pagamento = models.CharField(max_length=10, choices=FORMAS_PAGAMENTO, default='dinheiro')
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    troco = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)
    saldo_devedor = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)
    pago = models.BooleanField(default=False)

    def calcular_total(self):
        total = self.itens.aggregate(total=Sum('subtotal'))['total']
        return total or Decimal('0.00')

    def clean(self):
        super().clean()

        if not self.cliente:
            raise ValidationError("Você deve selecionar um cliente.")

        # Não calcular total aqui (venda ainda pode não ter pk)

        if self.forma_pagamento == 'dinheiro':
            if self.valor_pago is None:
                raise ValidationError("Informe o valor pago para pagamento em dinheiro.")
        else:
            if self.valor_pago:
                raise ValidationError("Valor pago só deve ser informado para pagamento em dinheiro.")
            if self.troco:
                raise ValidationError("Troco só para pagamento em dinheiro.")

    def save(self, *args, validate=True, **kwargs):
        if validate:
            self.full_clean()

        creating = self.pk is None

        # Primeiro salva a venda caso não exista
        if creating:
            super().save(*args, **kwargs)

        # Agora pode calcular total
        total = self.calcular_total()
        self.valor_total = total

        # Regras de pagamento
        if self.forma_pagamento == 'dinheiro':
            if self.valor_pago:
                self.troco = max(self.valor_pago - total, Decimal('0.00'))
                self.saldo_devedor = max(total - self.valor_pago, Decimal('0.00'))
                self.pago = self.valor_pago >= total
        else:
            self.troco = None
            self.valor_pago = None
            self.pago = False
            self.saldo_devedor = Decimal('0.00')

        # Agora salva apenas os campos que mudaram
        super().save(update_fields=[
            'valor_total', 'troco', 'valor_pago', 'saldo_devedor', 'pago'
        ])

    def __str__(self):
        return f"Venda #{self.pk} - Cliente: {self.cliente.nome if self.cliente else 'Desconhecido'}"

    def listar_produtos(self):
        return ", ".join([f"{item.produto.nome} (x{item.quantidade})" for item in self.itens.all()])


# -------------------------------
# ITEM DE VENDA
# -------------------------------
class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, blank=True)

    def clean(self):
        super().clean()
        if self.quantidade is None:
            raise ValidationError("Informe a quantidade.")
        if not self.produto.verificar_estoque(self.quantidade):
            raise ValidationError(f'Estoque insuficiente para {self.produto.nome}. Disponível: {self.produto.estoque}')

    def save(self, *args, **kwargs):
        novo = not self.pk

        if novo:
            self.clean()
            self.produto.diminuir_estoque(self.quantidade)

        self.subtotal = self.produto.preco * self.quantidade
        super().save(*args, **kwargs)

        # Recalcular a venda após salvar o item
        self.venda.save(validate=False)

    def delete(self, *args, **kwargs):
        self.produto.aumentar_estoque(self.quantidade)
        super().delete(*args, **kwargs)

        # Atualiza venda após excluir item
        self.venda.save(validate=False)

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} (Venda #{self.venda.pk})"


# -------------------------------
# SINAL — garante que o estoque volta SEMPRE
# -------------------------------
@receiver(pre_delete, sender=ItemVenda)
def devolver_estoque_ao_excluir(sender, instance, **kwargs):
    instance.produto.aumentar_estoque(instance.quantidade)


# -------------------------------
# CAIXA
# -------------------------------
class Caixa(models.Model):
    data_abertura = models.DateTimeField(default=timezone.now)
    valor_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_fechamento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True)

    def fechar_caixa(self, valor_fechamento=None):
        self.valor_fechamento = valor_fechamento or self.valor_fechamento
        self.data_fechamento = timezone.now()
        self.save()

    def get_total_vendas(self):
        vendas = Venda.objects.filter(
            data_venda__gte=self.data_abertura,
            data_venda__lte=self.data_fechamento or timezone.now()
        )
        total = vendas.aggregate(total=Sum('valor_pago'))['total']
        return total or Decimal('0.00')

    def get_total_saidas(self):
        total = self.saidas.aggregate(total=Sum('valor'))['total']
        return total or Decimal('0.00')

    def __str__(self):
        status = "Aberto" if not self.data_fechamento else "Fechado"
        return f"Caixa {self.data_abertura.strftime('%d/%m/%Y %H:%M')} - {status}"
