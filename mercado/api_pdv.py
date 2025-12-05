from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Produto, PDVSession

@csrf_exempt
def api_bipar(request):
    codigo = request.GET.get("codigo")  # <-- USAR GET

    if not codigo:
        return JsonResponse({"erro": "Código não enviado"}, status=400)

    try:
        produto = Produto.objects.get(codigo_barras=codigo)
    except Produto.DoesNotExist:
        return JsonResponse({"erro": "Produto não encontrado"}, status=404)

    if not request.user.is_authenticated:
        return JsonResponse({"erro": "Usuário não autenticado"}, status=403)

    try:
        session = PDVSession.objects.get(usuario=request.user, ativa=True)
        venda = session.venda
    except PDVSession.DoesNotExist:
        return JsonResponse({"erro": "Sessão PDV não localizada"}, status=500)

    item, created = venda.itens.get_or_create(
        produto=produto,
        defaults={'quantidade': 1, 'subtotal': produto.preco}
    )

    if not created:
        item.quantidade += 1
        item.subtotal = produto.preco * item.quantidade
        item.save()

    return JsonResponse({
        "mensagem": "Item adicionado com sucesso",
        "produto": produto.nome,
        "quantidade": item.quantidade,
        "subtotal": float(item.subtotal),
        "total_venda": float(venda.calcular_total())
    })
