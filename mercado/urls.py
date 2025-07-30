from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # raiz do app mercado (que é raiz do site)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('vendas/<str:data>/', views.vendas_por_data, name='vendas_por_data'),
    path('logout/', views.logout_view, name='logout'),
]



