# mercado/views_api.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from .models import Produto, ItemVenda
from .services import get_or_create_pdv_session

@csrf_exempt
@login_required
def api_pdv_scan(request):
    data = json.loads(request.body)
    codigo = data.get("codigo")

    try:
        produto = Produto.objects.get(codigo_barras=codigo)
    except Produto.DoesNotExist:
        return JsonResponse({"error": "Produto não encontrado"}, status=404)

    session = get_or_create_pdv_session(request.user)
    venda = session.venda

    item, created = ItemVenda.objects.get_or_create(
        venda=venda,
        produto=produto,
        defaults={"quantidade": 1, "preco": produto.preco}
    )

    if not created:
        item.quantidade += 1
        item.save()

    itens = [{
        "nome": i.produto.nome,
        "quantidade": i.quantidade,
        "preco": float(i.preco),
    } for i in venda.itens.all()]

    return JsonResponse({
        "itens": itens,
        "total": float(venda.valor_total())
    })
