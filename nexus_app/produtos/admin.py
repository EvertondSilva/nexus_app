from django.contrib import admin
from .models import Categoria, Produto, StatusProjeto, Projeto, MaterialProjeto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cor", "ativo", "data_criacao"]
    list_filter = ["ativo", "data_criacao"]
    search_fields = ["nome"]
    list_editable = ["ativo"]


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = [
        "nome",
        "codigo",
        "categoria",
        "estoque",
        "estoque_minimo",
        "ativo",
        "data_criacao",
    ]  # Removido 'preco'
    list_filter = ["categoria", "ativo", "data_criacao"]
    search_fields = ["nome", "codigo", "descricao"]
    list_editable = ["estoque", "ativo"]  # Removido 'preco'
    readonly_fields = ["data_criacao", "data_atualizacao"]


@admin.register(StatusProjeto)
class StatusProjetoAdmin(admin.ModelAdmin):
    list_display = ["nome", "cor", "ordem", "ativo", "data_criacao"]
    list_filter = ["ativo", "data_criacao"]
    search_fields = ["nome"]
    list_editable = ["ordem", "ativo"]
    ordering = ["ordem"]


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = [
        "nome",
        "cliente",
        "status",
        "data_prazo_entrega",
        "usuario",
        "data_criacao",
    ]  # Removido 'valor_orcamento'
    list_filter = ["status", "usuario", "data_criacao"]
    search_fields = ["nome", "cliente"]
    readonly_fields = ["data_criacao", "data_atualizacao"]
    date_hierarchy = "data_prazo_entrega"


@admin.register(MaterialProjeto)
class MaterialProjetoAdmin(admin.ModelAdmin):
    list_display = ["projeto", "produto", "quantidade", "data_criacao"]
    list_filter = ["projeto", "produto", "data_criacao"]
    search_fields = ["projeto__nome", "produto__nome"]
