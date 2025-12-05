from django.http import JsonResponse
from .models import Produto

def scan_codigo_admin(request):
    codigo = request.GET.get("codigo")

    try:
        produto = Produto.objects.get(codigo_barras=codigo)
        return JsonResponse({
            "ok": True,
            "id": produto.id,
            "nome": produto.nome,
            "preco": float(produto.preco),
        })
    except Produto.DoesNotExist:
        return JsonResponse({"ok": False, "erro": "Produto não encontrado"})
