from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils.html import format_html
from datetime import date, timedelta
from decimal import Decimal
from simple_history.admin import SimpleHistoryAdmin
from django.contrib.admin.models import LogEntry
from django.forms.models import BaseInlineFormSet
from .models import Produto, Venda, Cliente, ClienteResumo, Caixa, ItemVenda

# Configurações do Admin
admin.site.site_header = "Administração do Mini Mercado"
admin.site.site_title = "Administração do Mini Mercado"
admin.site.index_title = "Painel Administrativo"

# -------------------------
# Inline de ItemVenda
# -------------------------
class ItemVendaInlineFormSet(BaseInlineFormSet):
    pass

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
        return f"R$ {obj.subtotal:.2f}" if obj.subtotal else "R$ 0.00"
    subtotal_display.short_description = "Subtotal"

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
        return format_html('<span style="color: green;">✅ OK ({})</span>', obj.estoque)
    status_estoque.short_description = 'Status'

# -------------------------
# Formulário customizado para Venda
# -------------------------
class VendaAdminForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        valor_pago = cleaned_data.get('valor_pago')
        forma_pagamento = cleaned_data.get('forma_pagamento')

        total = Decimal('0.00')
        if self.instance.pk:
            for item in self.instance.itens.all():
                total += item.subtotal

        if forma_pagamento and forma_pagamento.lower() == 'dinheiro':
            if valor_pago is None:
                raise ValidationError({'valor_pago': 'Informe o valor pago para pagamento em dinheiro.'})
            if valor_pago < total:
                raise ValidationError({'valor_pago': f'Valor pago ({valor_pago}) insuficiente para o total ({total}).'})
        return cleaned_data

# -------------------------
# Admin de Venda
# -------------------------
@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    form = VendaAdminForm
    inlines = [ItemVendaInline]
    list_display = [
        'id', 'cliente', 'mostrar_valor_total', 'status_pago', 
        'forma_pagamento', 'data_venda', 'produtos', 'saldo_devedor'
    ]
    readonly_fields = [
        'mostrar_valor_total', 'troco', 'data_venda', 
        'saldo_devedor', 'pago'
    ]
    list_filter = ['forma_pagamento', 'data_venda', 'pago']
    search_fields = ['cliente__nome']
    autocomplete_fields = ['cliente']
    actions = ['marcar_como_pago']

    # --- TUDO DO LEITOR FOI REMOVIDO ---

    def mostrar_valor_total(self, obj):
        return f"R$ {obj.calcular_total():.2f}"
    mostrar_valor_total.short_description = 'Valor Total'

    def produtos(self, obj):
        return ", ".join([item.produto.nome for item in obj.itens.all()])
    produtos.short_description = 'Produtos'

    def status_pago(self, obj):
        return format_html('<span style="color: green;">&#9989;</span>') if obj.pago else format_html('<span style="color: red;">&#10060;</span>')
    status_pago.short_description = 'Pago'
    status_pago.admin_order_field = 'pago'

    def marcar_como_pago(self, request, queryset):
        atualizadas = queryset.update(pago=True)
        self.message_user(request, f"{atualizadas} venda(s) marcadas como pagas com sucesso.")
    marcar_como_pago.short_description = "Confirmar pagamento das vendas selecionadas"

# -------------------------
# Cliente Inline
# -------------------------
class VendaInline(admin.TabularInline):
    model = Venda
    extra = 0
    readonly_fields = ['listar_produtos', 'valor_total', 'forma_pagamento']
    fields = ['forma_pagamento', 'listar_produtos', 'valor_total']
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj):
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
# ClienteResumo
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
        valor_formatado = f"R$ {float(valor_raw):.2f}"
        return format_html('<strong>{}</strong>', valor_formatado)
    total_valor.short_description = 'Total Comprado'

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
