from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db import transaction
from django.utils.html import format_html
from django.urls import path
from django.template.response import TemplateResponse
from datetime import date, timedelta
from decimal import Decimal
from simple_history.admin import SimpleHistoryAdmin
from django.contrib.admin.models import LogEntry
from django.forms.models import BaseInlineFormSet
from .models import Produto, Venda, Cliente, ClienteResumo, Caixa, ItemVenda
import logging

logger = logging.getLogger(__name__)

admin.site.site_header = "Administração do Mini Mercado"
admin.site.site_title = "Administração do Mini Mercado"
admin.site.index_title = "Painel Administrativo"


# -------------------------
# Inline para ItemVenda com formset padrão (removido método delete_existing que não era usado)
# -------------------------
class ItemVendaInlineFormSet(BaseInlineFormSet):
    pass  # Sem alteração, você pode customizar se precisar no futuro


class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    formset = ItemVendaInlineFormSet
    extra = 0
    autocomplete_fields = ['produto']
    readonly_fields = ['mostrar_produto', 'subtotal_display']
    fields = ['mostrar_produto', 'produto', 'quantidade', 'subtotal_display']
    can_delete = True

    def mostrar_produto(self, obj):
        return obj.produto.nome if obj.produto else "-"
    mostrar_produto.short_description = "Produto"

    def subtotal_display(self, obj):
        return obj.subtotal
    subtotal_display.short_description = "Subtotal (R$)"


# -------------------------
# Produto
# -------------------------
@admin.register(Produto)
class ProdutoAdmin(SimpleHistoryAdmin):
    list_display = ['nome', 'preco', 'estoque', 'status_estoque']
    list_filter = ['categoria']
    search_fields = ['nome']
    ordering = ['nome']

    def status_estoque(self, obj):
        if obj.estoque == 0:
            return format_html('<span style="color: red;">❌ Sem Estoque</span>')
        elif obj.estoque < 10:
            return format_html('<span style="color: orange;">⚠️ Estoque Baixo ({})</span>', obj.estoque)
        else:
            return format_html('<span style="color: green;">✅ OK ({})</span>', obj.estoque)
    status_estoque.short_description = 'Status'


# -------------------------
# Formulário customizado para Venda com validação
# -------------------------
class VendaAdminForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        valor_pago = cleaned_data.get('valor_pago')
        forma_pagamento = cleaned_data.get('forma_pagamento')

        if forma_pagamento == 'dinheiro':
            total = Decimal('0.00')

            if self.instance.pk:
                itens = self.instance.itens.all()
                itens_a_excluir = getattr(self, 'deleted_itens', [])

                for item in itens:
                    if item not in itens_a_excluir:
                        total += item.subtotal
            else:
                # Se for criação, ainda não há itens para somar
                return cleaned_data

            if valor_pago is None:
                raise ValidationError({'valor_pago': 'Informe o valor pago para pagamento em dinheiro.'})

            if valor_pago < total:
                raise ValidationError({'valor_pago': f'Valor pago ({valor_pago}) insuficiente para o total dos produtos ({total}).'})

        return cleaned_data


# -------------------------
# VendaAdmin com correção no save_formset para pegar itens deletados corretamente
# -------------------------
@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    form = VendaAdminForm
    inlines = [ItemVendaInline]
    list_display = [
        'id', 'cliente', 'mostrar_valor_total','status_pago', 'forma_pagamento',
        'data_venda', 'produtos', 'saldo_devedor']
    readonly_fields = ['mostrar_valor_total', 'troco', 'data_venda', 'saldo_devedor','pago']
    list_filter = ['forma_pagamento', 'data_venda', 'pago']
    search_fields = ['cliente__nome']
    actions = ['marcar_como_pago']
    autocomplete_fields = ['cliente']

    def mostrar_valor_total(self, obj):
        return f"R$ {obj.calcular_total():.2f}"
    mostrar_valor_total.short_description = 'Valor Total'

    def produtos(self, obj):
        return ", ".join(item.produto.nome for item in obj.itens.all())
    produtos.short_description = 'Produtos'

    def marcar_como_pago(self, request, queryset):
        atualizadas = queryset.update(pago=True)
        self.message_user(request, f"{atualizadas} venda(s) marcadas como pagas com sucesso.")
    marcar_como_pago.short_description = "Confirmar pagamento das vendas selecionadas"

    def save_formset(self, request, form, formset, change):
        deleted_itens = []
        if formset.can_delete:
            for form_ in formset.deleted_forms:
                if hasattr(form_, 'instance'):
                    deleted_itens.append(form_.instance)

        form.deleted_itens = deleted_itens

        for obj in deleted_itens:
            produto = obj.produto
            produto.estoque += obj.quantidade
            produto.save()
            obj.delete()

        instances = formset.save(commit=False)
        for instance in instances:
            instance.save()
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        total_calc = Decimal('0.00')
        for formset in formsets:
            if isinstance(formset, ItemVendaInlineFormSet):
                for item_form in formset.forms:
                    if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                        produto = item_form.cleaned_data.get('produto')
                        quantidade = item_form.cleaned_data.get('quantidade')
                        if produto and quantidade:
                            total_calc += produto.preco * quantidade

        obj = form.instance

        if obj.forma_pagamento == 'dinheiro':
            if obj.valor_pago is None:
                form.add_error('valor_pago', 'Informe o valor pago para pagamento em dinheiro.')
                raise ValidationError('Valor pago não informado.')
            if obj.valor_pago < total_calc:
                form.add_error('valor_pago', f'Valor pago ({obj.valor_pago}) insuficiente para o total dos produtos ({total_calc}).')
                raise ValidationError('Valor pago insuficiente.')

        super().save_related(request, form, formsets, change)

        if obj.forma_pagamento == 'dinheiro' and obj.valor_pago is not None:
            troco = max(obj.valor_pago - total_calc, Decimal('0.00'))
            obj.troco = troco
            obj.save(update_fields=['troco'])

    @transaction.atomic
    def delete_model(self, request, obj):
        for item in obj.itens.all():
            Produto.objects.filter(pk=item.produto.pk).update(estoque=F('estoque') + item.quantidade)
        super().delete_model(request, obj)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        for obj in queryset:
            for item in obj.itens.all():
                Produto.objects.filter(pk=item.produto.pk).update(estoque=F('estoque') + item.quantidade)
        super().delete_queryset(request, queryset)

    def status_pago(self, obj):
        if obj.pago:
            return format_html('<span style="color: green;">&#9989;</span>')  # ✅
        else:
            return format_html('<span style="color: red;">&#10060;</span>')   # ❌
    status_pago.short_description = 'Pago'
    status_pago.admin_order_field = 'pago'


# -------------------------
# Inline de Venda no Cliente
# -------------------------
class VendaInline(admin.TabularInline):
    model = Venda
    extra = 0
    readonly_fields = ['listar_produtos', 'valor_total', 'forma_pagamento']
    fields = ['forma_pagamento', 'listar_produtos', 'valor_total']
    show_change_link = True
    can_delete = True

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# -------------------------
# Cliente
# -------------------------
@admin.register(Cliente)
class ClienteAdmin(SimpleHistoryAdmin):
    list_display = ['nome', 'telefone', 'tipo', 'equipe', 'cor']
    list_filter = ['tipo']
    search_fields = ['nome', 'equipe', 'cor']
    inlines = [VendaInline]
    ordering = ['nome']


# -------------------------
# ClienteResumo (proxy)
# -------------------------
@admin.register(ClienteResumo)
class ClienteResumoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo', 'total_quantidade', 'total_valor']
    search_fields = ['nome']
    list_filter = ['tipo']
    ordering = ['nome']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        valor_total_expr = ExpressionWrapper(
            F('vendas__itens__quantidade') * F('vendas__itens__produto__preco'),
            output_field=DecimalField()
        )
        return qs.annotate(
            total_qtd=Sum('vendas__itens__quantidade'),
            total_valor=Sum(valor_total_expr)
        )

    def total_quantidade(self, obj):
        return obj.total_qtd or 0
    total_quantidade.short_description = 'Qtd. Total'

    def total_valor(self, obj):
        valor_raw = obj.total_valor or 0
        try:
            valor = float(valor_raw)
        except (TypeError, ValueError):
            valor = 0.0
        valor_formatado = f"R$ {valor:.2f}"
        return format_html('<strong>{}</strong>', valor_formatado)
    total_valor.short_description = 'Total Comprado'


# -------------------------
# Relatório de Vendas por Dia
# -------------------------
class RelatorioVendaAdmin(admin.ModelAdmin):
    change_list_template = 'admin/relatorio_vendas_change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('totais-por-dia/', self.admin_site.admin_view(self.totais_por_dia_view), name='totais-por-dia'),
        ]
        return custom_urls + urls

    def totais_por_dia_view(self, request):
        hoje = date.today()
        dias = [hoje - timedelta(days=i) for i in range(7)]

        totais_por_dia = []
        for dia in dias:
            vendas_do_dia = Venda.objects.filter(data_venda__date=dia)
            total_valor = sum([v.calcular_total() for v in vendas_do_dia])
            totais_por_forma = [
                {
                    'forma_pagamento': forma['forma_pagamento'],
                    'total': sum([
                        v.calcular_total() for v in vendas_do_dia if v.forma_pagamento == forma['forma_pagamento']
                    ])
                }
                for forma in vendas_do_dia.values('forma_pagamento').distinct()
            ]

            totais_por_dia.append({
                'data': dia,
                'total_valor': total_valor,
                'totais_por_forma': totais_por_forma,
            })

        context = dict(
            self.admin_site.each_context(request),
            totais_por_dia=totais_por_dia,
            title='Relatório de Vendas por Dia',
        )
        return TemplateResponse(request, 'admin/relatorio_vendas.html', context)


# -------------------------
# Caixa
# -------------------------
@admin.register(Caixa)
class CaixaAdmin(admin.ModelAdmin):
    list_display = ['data_abertura', 'valor_inicial', 'valor_fechamento', 'data_fechamento', 'status']
    readonly_fields = ['status']
    ordering = ['-data_abertura']

    def status(self, obj):
        return "Aberto" if not obj.data_fechamento else "Fechado"
    status.short_description = "Status"


# -------------------------
# Histórico
# -------------------------
class LogEntryProxy(LogEntry):
    class Meta:
        proxy = True
        verbose_name = "Histórico"
        verbose_name_plural = "Histórico"


@admin.register(LogEntryProxy)
class LogEntryProxyAdmin(admin.ModelAdmin):
    list_display = ['action_time', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message']
    list_filter = ['user', 'content_type', 'action_flag']
    search_fields = ['object_repr', 'change_message']

    def has_delete_permission(self, request, obj=None):
        return True
