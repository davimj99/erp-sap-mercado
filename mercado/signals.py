from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from django.db.models import Sum, F
from .models import ItemVenda, Venda

@receiver([post_save, post_delete], sender=ItemVenda)
def atualizar_valor_total_venda(sender, instance, **kwargs):
    venda = instance.venda
    total = venda.itens.aggregate(
        total=Sum(F('quantidade') * F('produto__preco'))
    )['total'] or Decimal('0.00')

    venda.valor_total = total

    if venda.forma_pagamento == 'dinheiro' and venda.valor_pago is not None:
        venda.troco = max(venda.valor_pago - total, Decimal('0.00'))
    else:
        venda.troco = None

    venda.save(update_fields=['valor_total', 'troco'], validate=False)
