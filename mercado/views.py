from django.shortcuts import render, redirect
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from datetime import date, timedelta, datetime
from .models import Produto, Venda
from django.contrib.auth.decorators import login_required 
from django.contrib.auth import authenticate, login, logout

# ==========================
# DASHBOARD
# ==========================
@login_required
def dashboard(request):
    hoje = date.today()

    # Últimos 30 dias
    dias_range = [hoje - timedelta(days=i) for i in range(29, -1, -1)]

    # Quantidade total vendida por dia
    vendas_dias = {
        dia: (
            Venda.objects
            .filter(data_venda__date=dia)
            .aggregate(total=Sum("itens__quantidade"))
            ['total'] or 0
        )
        for dia in dias_range
    }

    dias_labels = [d.strftime('%d/%m') for d in dias_range]
    dias_totais = list(vendas_dias.values())

    # -------------------------------
    # Total vendido HOJE (valor)
    # -------------------------------
    total_hoje = (
        Venda.objects
        .filter(data_venda__date=hoje)
        .annotate(
            total_produto=ExpressionWrapper(
                F('itens__quantidade') * F('itens__produto__preco'),
                output_field=DecimalField()
            )
        )
        .aggregate(soma=Sum('total_produto'))['soma'] or 0
    )

    # -------------------------------
    # Totais por forma de pagamento
    # -------------------------------
    vendas_por_forma = (
        Venda.objects
        .filter(data_venda__date=hoje)
        .annotate(
            total_produto=ExpressionWrapper(
                F('itens__quantidade') * F('itens__produto__preco'),
                output_field=DecimalField()
            )
        )
        .values('forma_pagamento')
        .annotate(total=Sum('total_produto'))
    )

    # -------------------------------
    # Totais por categoria
    # -------------------------------
    categorias = (
        Produto.objects
        .values('categoria')
        .annotate(total=Sum('itemvenda__quantidade'))
    )

    categorias_labels = [c['categoria'] for c in categorias]
    categorias_totais = [c['total'] or 0 for c in categorias]

    return render(request, 'dashboard.html', {
        'vendas_dias': vendas_dias,
        'dias_labels': dias_labels,
        'dias_totais': dias_totais,
        'categorias_labels': categorias_labels,
        'categorias_totais': categorias_totais,
        'total_hoje': total_hoje,
        'vendas_por_forma': vendas_por_forma,
    })

# ==========================
# VENDAS POR DATA
# ==========================
@login_required
def vendas_por_data(request, data=None):

    # Se acessou /vendas/ sem data → redireciona para hoje
    if data is None:
        hoje = date.today().strftime("%Y-%m-%d")
        return redirect("vendas_por_data", data=hoje)

    # Se veio data via GET (formulário)
    data_query = request.GET.get("data")
    if data_query:
        return redirect("vendas_por_data", data=data_query)

    # Converte a data enviada
    try:
        data_formatada = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        hoje = date.today().strftime("%Y-%m-%d")
        return redirect("vendas_por_data", data=hoje)

    # Vendas do dia
    vendas = Venda.objects.filter(data_venda__date=data_formatada)

    # Total do dia
    valor_total_dia = (
        vendas
        .annotate(
            total_produto=ExpressionWrapper(
                F('itens__quantidade') * F('itens__produto__preco'),
                output_field=DecimalField()
            )
        )
        .aggregate(soma=Sum('total_produto'))['soma'] or 0
    )

    # Confirmadas e pendentes
    vendas_confirmadas = vendas.filter(pago=True).count()
    vendas_pendentes = vendas.filter(pago=False).count()

    # Saldo devedor
    saldo_total_devedor = (
        vendas
        .filter(pago=False)
        .aggregate(total=Sum('saldo_devedor'))['total'] or 0
    )

    return render(request, "vendas_por_data.html", {
        "vendas": vendas,
        "data": data_formatada,
        "data_hoje": date.today(),
        "valor_total_dia": valor_total_dia,
        "vendas_confirmadas": vendas_confirmadas,
        "vendas_pendentes": vendas_pendentes,
        "saldo_total_devedor": saldo_total_devedor,
        "data_relatorio": data_formatada.strftime("%d/%m/%Y"),
    })

# ==========================
# LOGIN
# ==========================
def login_view(request):
    error = False
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            next_url = request.POST.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            error = True

    return render(request, 'login.html', {
        'error': error,
        'next': request.GET.get('next', '')
    })

# ==========================
# LOGOUT
# ==========================
def logout_view(request):
    logout(request)
    return redirect('login')

# ==========================
# PRODUTOS
# ==========================
@login_required
def produtos(request):
    produtos = Produto.objects.all().order_by('nome')
    return render(request, 'produtos.html', {"produtos": produtos})
