from django.shortcuts import render
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from datetime import date, timedelta, datetime
from .models import Produto, Venda
from django.contrib.auth.decorators import login_required 
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect


@login_required
def dashboard(request):
    hoje = date.today()

    # Últimos 3 dias (hoje, ontem, anteontem)
    dias = [hoje - timedelta(days=i) for i in range(5)]

    # Quantidade total vendida por dia (unidades)
    vendas_dias = {
        dia: Venda.objects.filter(data_venda__date=dia).aggregate(total=Sum('itens__quantidade'))['total'] or 0
        for dia in dias
    }

    # Valor total vendido hoje (soma dos itens de todas as vendas do dia)
    total_hoje = Venda.objects.filter(data_venda__date=hoje).annotate(
        total=Sum(ExpressionWrapper(F('itens__quantidade') * F('itens__produto__preco'), output_field=DecimalField()))
    ).aggregate(soma=Sum('total'))['soma'] or 0

    # Total vendido hoje por forma de pagamento
    vendas_por_forma = Venda.objects.filter(data_venda__date=hoje) \
        .values('forma_pagamento') \
        .annotate(total=Sum(ExpressionWrapper(F('itens__quantidade') * F('itens__produto__preco'), output_field=DecimalField())))

    # Buscar produtos
    produtos = Produto.objects.all().order_by('nome')

    # Passar tudo para o template
    return render(request, 'dashboard.html', {
        'produtos': produtos,
        'vendas_dias': vendas_dias,
        'total_hoje': total_hoje,
        'vendas_por_forma': vendas_por_forma,
        'data_hoje': hoje,
    })

@login_required
def vendas_por_data(request, data):
    try:
        data_formatada = datetime.strptime(data, '%Y-%m-%d').date()
    except ValueError:
        return render(request, 'erro.html', {'mensagem': 'Data inválida.'})
    
    vendas = Venda.objects.filter(data_venda__date=data_formatada)
    
    # Valor total vendido no dia (somando itens)
    valor_total_dia = vendas.annotate(
        total=Sum(ExpressionWrapper(F('itens__quantidade') * F('itens__produto__preco'), output_field=DecimalField()))
    ).aggregate(soma=Sum('total'))['soma'] or 0
    
    # Quantidade de vendas confirmadas e pendentes
    vendas_confirmadas = vendas.filter(pago=True).count()
    vendas_pendentes = vendas.filter(pago=False).count()
    
    # Soma total do saldo devedor das vendas pendentes
    saldo_total_devedor = vendas.filter(pago=False).aggregate(total=Sum('saldo_devedor'))['total'] or 0

    return render(request, 'vendas_por_data.html', {
        'vendas': vendas,
        'data': data_formatada,
        'data_hoje': date.today(),
        'valor_total_dia': valor_total_dia,
        'vendas_confirmadas': vendas_confirmadas,
        'vendas_pendentes': vendas_pendentes,
        'saldo_total_devedor': saldo_total_devedor,
        'data_relatorio': data_formatada.strftime('%d/%m/%Y'),
    })

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

    return render(request, 'login.html', {'error': error, 'next': request.GET.get('next', '')})

def logout_view(request):
    logout(request)
    return redirect('login')


