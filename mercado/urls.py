from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views
from .api_pdv import api_bipar
from .api_pdv import api_bipar


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('produtos/', views.produtos, name='produtos'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # rota sem data → redireciona para hoje
    path('vendas/', views.vendas_por_data, name='vendas'),

    # rota com data
    path('vendas/<str:data>/', views.vendas_por_data, name='vendas_por_data'),

    
    path('api/pdv/scan/', api_bipar, name='api_pdv_scan'),

    path("admin/scan/", api_bipar, name="api_bipar"),

]

