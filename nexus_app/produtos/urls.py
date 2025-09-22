from django.urls import path
from . import views

urlpatterns = [
    # Autenticação
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    
    # Página principal
    path("", views.home, name="home"),
    
    # Produtos
    path("produtos/", views.produto_list, name="produto_list"),
    path("produtos/<int:pk>/", views.produto_detail, name="produto_detail"),
    
    # APIs de criação
    path("api/criar-status/", views.criar_status, name="criar_status"),
    path("api/criar-projeto/", views.criar_projeto, name="criar_projeto"),
    path("api/criar-categoria/", views.criar_categoria, name="criar_categoria"),
    path("api/criar-produto/", views.criar_produto, name="criar_produto"),
    
    # APIs de projeto
    path("api/mover-projeto/", views.mover_projeto, name="mover_projeto"),
    path("api/excluir-projeto/", views.excluir_projeto, name="excluir_projeto"),
    path("api/editar-projeto/", views.editar_projeto, name="editar_projeto"),
    path("api/projeto/<int:projeto_id>/", views.projeto_detail_api, name="projeto_detail_api"),
    
    # APIs de conclusão
    path("api/concluir-projeto/", views.concluir_projeto, name="concluir_projeto"),
    path("api/reabrir-projeto/", views.reabrir_projeto, name="reabrir_projeto"),
    path("api/projetos-concluidos/", views.projetos_concluidos_api, name="projetos_concluidos_api"),
    
    # APIs de aprovação (usando as views que você já tem)
    path("projetos/<int:projeto_id>/aprovar/", views.aprovar_projeto, name="aprovar_projeto"),
    path("projetos/<int:projeto_id>/rejeitar/", views.rejeitar_projeto, name="rejeitar_projeto"),
    path("projetos/<int:projeto_id>/resetar-aprovacao/", views.resetar_aprovacao_projeto, name="resetar_aprovacao_projeto"),
    
    # APIs para AJAX
    path("api/projetos-rejeitados/", views.api_projetos_rejeitados, name="api_projetos_rejeitados"),
    
    # Páginas especiais
    path("projetos-rejeitados/", views.projetos_rejeitados, name="projetos_rejeitados"),

    #filtros
    path('api/metricas-filtradas/', views.api_metricas_filtradas, name='api_metricas_filtradas'),
]