from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('produtos/', views.produtos, name='produtos'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # rota sem data → redireciona para hoje
    path('vendas/', views.vendas_por_data, name='vendas'),

    # rota com data
    path('vendas/<str:data>/', views.vendas_por_data, name='vendas_por_data'),
]

