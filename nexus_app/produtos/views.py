import json
import duckdb
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone  # Adicionar este import
from datetime import timedelta  # Adicionar este import
from .models import Produto, Categoria, StatusProjeto, Projeto, MaterialProjeto
from django.db import models
from django.views.decorators.http import require_http_methods


# Views de autenticação
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Usuário ou senha inválidos.")

    return render(request, "produtos/login.html")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        password_confirm = request.POST["password_confirm"]

        if password != password_confirm:
            messages.error(request, "As senhas não coincidem.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Nome de usuário já existe.")
        elif len(password) < 4:
            messages.error(request, "A senha deve ter pelo menos 4 caracteres.")
        else:
            User.objects.create_user(username=username, password=password)
            messages.success(request, "Usuário criado com sucesso! Faça login.")
            return redirect("login")

    return render(request, "produtos/register.html")


def logout_view(request):
    logout(request)
    return redirect("login")


# Views principais
@login_required(login_url='/login/')
def home(request):
    """Página inicial com dashboard Kanban"""
    from django.utils import timezone
    from datetime import timedelta
    
    # IMPORTANTE: Buscar apenas projetos não concluídos E não rejeitados
    projetos = Projeto.objects.filter(
        #usuario=request.user, 
        concluido=False,
        aprovacao__in=['pendente', 'aprovado']  # EXCLUIR REJEITADOS
    ).order_by('-data_criacao')
    
    produtos = Produto.objects.filter(ativo=True).order_by('nome')
    categorias = Categoria.objects.filter(ativo=True).order_by('nome')
    status_list = StatusProjeto.objects.filter(ativo=True).order_by('ordem')
    
    # Organizar projetos por status
    projetos_por_status = {}
    for status in status_list:
        projetos_por_status[status.id] = projetos.filter(status=status)
    
    # ========== MÉTRICAS ==========
    hoje = timezone.now().date()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    
    # 1. Projetos por status (pegar o primeiro status como exemplo)
    primeiro_status = status_list.first()
    projetos_primeiro_status = projetos.filter(status=primeiro_status).count() if primeiro_status else 0
    
    # 2. Projetos em atraso (prazo de entrega passou)
    projetos_em_atraso = projetos.filter(data_prazo_entrega__lt=hoje).count()
    
    # 3. Projetos a entregar esta semana
    projetos_semana = projetos.filter(
        data_prazo_entrega__gte=inicio_semana,
        data_prazo_entrega__lte=fim_semana
    ).count()
    
    # 4. Total de projetos concluídos
    projetos_concluidos = Projeto.objects.filter(
        #usuario=request.user, 
        concluido=True).count()
    
    # 5. PROJETOS REJEITADOS - CONTAR SEPARADAMENTE
    projetos_rejeitados = Projeto.objects.filter(
        #usuario=request.user, 
        aprovacao='rejeitado'
    ).count()
    
    # 6. Projetos pendentes de aprovação
    projetos_pendentes = projetos.filter(aprovacao='pendente').count()
    
    # ========== NOVAS MÉTRICAS ==========
    
    # 7. Orçamentos aceitos (aprovados)
    orcamentos_aceitos = Projeto.objects.filter(
        #usuario=request.user,
        aprovacao='aprovado'
    ).count()
    
    # 8. Orçamentos rejeitados
    orcamentos_rejeitados = projetos_rejeitados  # Mesmo valor dos rejeitados
    
    # 9. Número de projetos concluídos (pode ser diferente se quiser outra lógica)
    numero_concluidos = projetos_concluidos  # Mesmo valor, mas pode ser customizado
    
    # Dados dos status para o dropdown
    status_metricas = []
    for status in status_list:
        count = projetos.filter(status=status).count()
        status_metricas.append({
            'id': status.id,
            'nome': status.nome,
            'cor': status.cor,
            'count': count
        })
    
    context = {
        'projetos': projetos,
        'produtos': produtos,
        'categorias': categorias,
        'status_list': status_list,
        'projetos_por_status': projetos_por_status,
        
        # Métricas existentes
        'primeiro_status': primeiro_status,
        'projetos_primeiro_status': projetos_primeiro_status,
        'projetos_em_atraso': projetos_em_atraso,
        'projetos_semana': projetos_semana,
        'projetos_concluidos': projetos_concluidos,
        'projetos_rejeitados': projetos_rejeitados,
        'projetos_pendentes': projetos_pendentes,
        'status_metricas': status_metricas,
        
        # NOVAS MÉTRICAS
        'orcamentos_aceitos': orcamentos_aceitos,
        'orcamentos_rejeitados': orcamentos_rejeitados,
        'numero_concluidos': numero_concluidos,
        
        # Dados da semana
        'inicio_semana': inicio_semana,
        'fim_semana': fim_semana,
    }
    
    return render(request, 'produtos/home.html', context)


# APIs para o Kanban
@csrf_exempt
@require_POST
@login_required
def criar_status(request):
    """API para criar novo status"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        nome = data.get("nome")
        cor = data.get("cor", "#007bff")

        if not nome:
            return JsonResponse({"success": False, "error": "Nome é obrigatório"})

        # Verificar se já existe um status com esse nome
        if StatusProjeto.objects.filter(nome=nome).exists():
            return JsonResponse(
                {"success": False, "error": "Já existe um status com esse nome"}
            )

        # Determinar a próxima ordem - COM models.Max
        ultima_ordem = (
            StatusProjeto.objects.aggregate(max_ordem=models.Max("ordem"))["max_ordem"]
            or 0
        )

        # Criar o status
        status = StatusProjeto.objects.create(
            nome=nome, cor=cor, ordem=ultima_ordem + 1, ativo=True
        )

        return JsonResponse(
            {
                "success": True,
                "status": {
                    "id": status.id,
                    "nome": status.nome,
                    "cor": status.cor,
                    "ordem": status.ordem,
                },
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
@login_required
def mover_projeto(request):
    """API para mover projeto entre status"""
    try:
        data = json.loads(request.body)
        projeto_id = data.get("projeto_id")
        novo_status_id = data.get("novo_status_id")

        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        novo_status = get_object_or_404(StatusProjeto, id=novo_status_id)

        projeto.status = novo_status
        projeto.save()

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
@login_required
def excluir_projeto(request):
    """API para excluir projeto"""
    try:
        data = json.loads(request.body)
        projeto_id = data.get("projeto_id")

        if not projeto_id:
            return JsonResponse(
                {"success": False, "error": "ID do projeto é obrigatório"}
            )

        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        nome_projeto = projeto.nome
        projeto.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f'Projeto "{nome_projeto}" excluído com sucesso!',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def projeto_detail_api(request, projeto_id):
    """API para buscar detalhes de um projeto"""
    try:
        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )

        # Buscar materiais
        materiais = []
        for material in projeto.materiais.all():
            materiais.append(
                {
                    "produto_nome": material.produto.nome,
                    "quantidade": material.quantidade,
                    "observacoes": material.observacoes or "",
                }
            )

        return JsonResponse(
            {
                "success": True,
                "projeto": {
                    "id": projeto.id,
                    "nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "data_prazo_entrega": projeto.data_prazo_entrega.strftime(
                        "%Y-%m-%d"
                    ),
                    "data_prazo_pagamento": projeto.data_prazo_pagamento.strftime(
                        "%Y-%m-%d"
                    ),
                    "status_id": projeto.status.id,
                    "status_nome": projeto.status.nome,
                    "observacoes": projeto.observacoes or "",
                    "data_criacao": projeto.data_criacao.isoformat(),
                    "materiais": materiais,
                },
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# Views de produtos
class ProdutoListView(LoginRequiredMixin, ListView):
    model = Produto
    template_name = "produtos/lista.html"
    context_object_name = "produtos"
    paginate_by = 10
    login_url = "/login/"

    def get_queryset(self):
        queryset = Produto.objects.filter(ativo=True).select_related("categoria")
        categoria_id = self.request.GET.get("categoria")
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categorias"] = Categoria.objects.filter(ativo=True)
        return context


class ProdutoDetailView(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = "produtos/detalhe.html"
    context_object_name = "produto"
    login_url = "/login/"


@login_required(login_url="/login/")
def analytics_api(request):
    """API para dados de analytics usando DuckDB"""
    try:
        conn = duckdb.connect(":memory:")

        conn.execute(
            """
            CREATE TABLE vendas AS SELECT * FROM VALUES
            ('2024-01-01', 'Produto A', 100.0, 5),
            ('2024-01-02', 'Produto B', 150.0, 3),
            ('2024-01-03', 'Produto A', 100.0, 2),
            ('2024-01-04', 'Produto C', 200.0, 4)
            AS t(data, produto, preco, quantidade)
        """
        )

        result = conn.execute(
            """
            SELECT 
                produto,
                SUM(preco * quantidade) as total_vendas,
                SUM(quantidade) as total_quantidade
            FROM vendas 
            GROUP BY produto
            ORDER BY total_vendas DESC
        """
        ).fetchall()

        data = []
        for row in result:
            data.append(
                {
                    "produto": row[0],
                    "total_vendas": float(row[1]),
                    "total_quantidade": int(row[2]),
                }
            )

        conn.close()
        return JsonResponse({"success": True, "data": data})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# No final do arquivo, adicione se não existirem:


@csrf_exempt
@require_POST
@login_required
def criar_categoria(request):
    """API para criar nova categoria"""
    try:
        data = json.loads(request.body)
        nome = data.get("nome")
        cor = data.get("cor", "#007bff")

        if not nome:
            return JsonResponse({"success": False, "error": "Nome é obrigatório"})

        categoria = Categoria.objects.create(nome=nome, cor=cor)

        return JsonResponse(
            {
                "success": True,
                "categoria": {
                    "id": categoria.id,
                    "nome": categoria.nome,
                    "cor": categoria.cor,
                },
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
@login_required
def criar_produto(request):
    """API para criar novo produto"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        nome = data.get("nome")
        # preco = data.get('preco')  # REMOVIDO

        if not nome:  # Removido: all([nome, preco])
            return JsonResponse({"success": False, "error": "Nome é obrigatório"})

        # Criar o produto
        categoria_id = data.get("categoria_id")
        categoria = None
        if categoria_id:
            categoria = get_object_or_404(Categoria, id=categoria_id)

        produto = Produto.objects.create(
            nome=nome,
            codigo=data.get("codigo", ""),
            descricao=data.get("descricao", ""),
            categoria=categoria,
            # preco=float(preco),  # REMOVIDO
            estoque=int(data.get("estoque", 0)),
            estoque_minimo=int(data.get("estoque_minimo", 5)),
            unidade=data.get("unidade", "UN"),
            observacoes=data.get("observacoes", ""),
            ativo=data.get("ativo", True),
        )

        return JsonResponse(
            {
                "success": True,
                "produto": {
                    "id": produto.id,
                    "nome": produto.nome,
                    # 'preco': str(produto.preco),  # REMOVIDO
                    "estoque": produto.estoque,
                },
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required(login_url="/login/")
def produto_list(request):
    """Lista de produtos"""
    produtos = Produto.objects.filter(ativo=True).order_by("nome")
    context = {"produtos": produtos}
    return render(request, "produtos/produto_list.html", context)


@login_required(login_url="/login/")
def produto_detail(request, pk):
    """Detalhes do produto"""
    produto = get_object_or_404(Produto, pk=pk, ativo=True)
    context = {"produto": produto}
    return render(request, "produtos/produto_detail.html", context)


@csrf_exempt
@require_POST
@login_required
def criar_projeto(request):
    """API para criar novo projeto"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        nome = data.get("nome")
        cliente = data.get("cliente")
        # valor_orcamento = data.get('valor_orcamento')  # REMOVIDO
        data_prazo_entrega = data.get("data_prazo_entrega")
        data_prazo_pagamento = data.get("data_prazo_pagamento")
        status_id = data.get("status_id")

        if not all(
            [nome, cliente, data_prazo_entrega, data_prazo_pagamento, status_id]
        ):  # Removido valor_orcamento
            return JsonResponse(
                {
                    "success": False,
                    "error": "Todos os campos obrigatórios devem ser preenchidos",
                }
            )

        # Buscar o status
        status = get_object_or_404(StatusProjeto, id=status_id)

        # Criar o projeto
        projeto = Projeto.objects.create(
            nome=nome,
            cliente=cliente,
            # valor_orcamento=float(valor_orcamento),  # REMOVIDO
            data_prazo_entrega=data_prazo_entrega,
            data_prazo_pagamento=data_prazo_pagamento,
            status=status,
            usuario=request.user,
            observacoes=data.get("observacoes", ""),
        )

        # Adicionar materiais se houver
        materiais = data.get("materiais", [])
        for material in materiais:
            produto = get_object_or_404(Produto, id=material["produto_id"])
            MaterialProjeto.objects.create(
                projeto=projeto, produto=produto, quantidade=int(material["quantidade"])
            )

        return JsonResponse(
            {
                "success": True,
                "projeto": {
                    "id": projeto.id,
                    "nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "status": projeto.status.nome,
                },
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required(login_url='/login/')
def projetos_rejeitados(request):
    """Lista projetos rejeitados"""
    projetos_rejeitados = Projeto.objects.filter(
        #usuario=request.user,
        aprovacao='rejeitado'
    ).order_by('-data_aprovacao')
    
    context = {
        'projetos_rejeitados': projetos_rejeitados,
        'total_rejeitados': projetos_rejeitados.count(),
    }
    
    return render(request, 'produtos/projetos_rejeitados.html', context)


@login_required
def projeto_detail_api(request, projeto_id):
    """API para buscar detalhes de um projeto"""
    try:
        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )

        # Buscar materiais
        materiais = []
        for material in projeto.materiais.all():
            materiais.append(
                {
                    "produto_nome": material.produto.nome,
                    "quantidade": material.quantidade,
                    "observacoes": material.observacoes,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "projeto": {
                    "id": projeto.id,
                    "nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "data_prazo_entrega": projeto.data_prazo_entrega.strftime(
                        "%Y-%m-%d"
                    ),
                    "data_prazo_pagamento": projeto.data_prazo_pagamento.strftime(
                        "%Y-%m-%d"
                    ),
                    "status_id": projeto.status.id,
                    "status_nome": projeto.status.nome,
                    "observacoes": projeto.observacoes,
                    "data_criacao": projeto.data_criacao.isoformat(),
                    "materiais": materiais,
                },
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
@login_required
def editar_projeto(request):
    """API para editar projeto"""
    try:
        data = json.loads(request.body)
        projeto_id = data.get("projeto_id")

        if not projeto_id:
            return JsonResponse(
                {"success": False, "error": "ID do projeto é obrigatório"}
            )

        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )

        # Validar campos obrigatórios
        nome = data.get("nome")
        cliente = data.get("cliente")
        data_prazo_entrega = data.get("data_prazo_entrega")
        data_prazo_pagamento = data.get("data_prazo_pagamento")
        status_id = data.get("status_id")

        if not all(
            [nome, cliente, data_prazo_entrega, data_prazo_pagamento, status_id]
        ):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Todos os campos obrigatórios devem ser preenchidos",
                }
            )

        # Atualizar campos
        projeto.nome = nome
        projeto.cliente = cliente
        projeto.data_prazo_entrega = data_prazo_entrega
        projeto.data_prazo_pagamento = data_prazo_pagamento
        projeto.observacoes = data.get("observacoes", "")

        # Atualizar status
        projeto.status = get_object_or_404(StatusProjeto, id=status_id)

        projeto.save()

        return JsonResponse(
            {
                "success": True,
                "message": f'Projeto "{projeto.nome}" atualizado com sucesso!',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
@login_required
def concluir_projeto(request):
    """API para marcar projeto como concluído"""
    try:
        data = json.loads(request.body)
        projeto_id = data.get("projeto_id")

        if not projeto_id:
            return JsonResponse(
                {"success": False, "error": "ID do projeto é obrigatório"}
            )

        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        projeto.marcar_como_concluido()

        return JsonResponse(
            {
                "success": True,
                "message": f'Projeto "{projeto.nome}" marcado como concluído!',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_POST
@login_required
def reabrir_projeto(request):
    """API para reabrir projeto concluído"""
    try:
        data = json.loads(request.body)
        projeto_id = data.get("projeto_id")

        if not projeto_id:
            return JsonResponse(
                {"success": False, "error": "ID do projeto é obrigatório"}
            )

        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        projeto.reabrir_projeto()

        return JsonResponse(
            {
                "success": True,
                "message": f'Projeto "{projeto.nome}" reaberto com sucesso!',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def projetos_concluidos_api(request):
    """API para listar projetos concluídos"""
    try:
        projetos = Projeto.objects.filter(
            #usuario=request.user, 
            concluido=True).order_by("-data_conclusao")

        projetos_data = []
        for projeto in projetos:
            projetos_data.append(
                {
                    "id": projeto.id,
                    "nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "status_nome": projeto.status.nome,
                    "data_conclusao": (
                        projeto.data_conclusao.isoformat()
                        if projeto.data_conclusao
                        else None
                    ),
                    "observacoes": projeto.observacoes or "",
                }
            )

        return JsonResponse({"success": True, "projetos": projetos_data})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required(login_url='/login/')
@require_http_methods(["POST"])
def aprovar_projeto(request, projeto_id):
    """Aprova um projeto"""
    try:
        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        projeto.aprovar_projeto()
        
        return JsonResponse({
            'success': True,
            'message': 'Projeto aprovado com sucesso!',
            'aprovacao': projeto.aprovacao,
            'data_aprovacao': projeto.data_aprovacao.strftime('%d/%m/%Y %H:%M') if projeto.data_aprovacao else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao aprovar projeto: {str(e)}'
        })

@login_required(login_url='/login/')
@require_http_methods(["POST"])
def rejeitar_projeto(request, projeto_id):
    """Rejeita um projeto"""
    try:
        import json
        
        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        
        # Pegar motivo do corpo da requisição
        data = json.loads(request.body) if request.body else {}
        motivo = data.get('motivo', 'Projeto rejeitado')
        
        projeto.rejeitar_projeto(motivo)
        
        return JsonResponse({
            'success': True,
            'message': 'Projeto rejeitado com sucesso!',
            'aprovacao': projeto.aprovacao,
            'motivo_rejeicao': projeto.motivo_rejeicao
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao rejeitar projeto: {str(e)}'
        })

@login_required(login_url='/login/')
@require_http_methods(["POST"])
def resetar_aprovacao_projeto(request, projeto_id):
    """Reseta aprovação de um projeto para pendente"""
    try:
        projeto = get_object_or_404(Projeto, id=projeto_id, 
        #usuario=request.user
        )
        projeto.resetar_aprovacao()
        
        return JsonResponse({
            'success': True,
            'message': 'Projeto reaberto com sucesso!',
            'aprovacao': projeto.aprovacao
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao reabrir projeto: {str(e)}'
        })

@login_required
def projetos_rejeitados_api(request):
    """API para listar projetos rejeitados"""
    try:
        projetos = Projeto.objects.filter(
            #usuario=request.user, 
            aprovacao='rejeitado'
        ).order_by('-data_aprovacao')
        
        projetos_data = []
        for projeto in projetos:
            projetos_data.append({
                'id': projeto.id,
                'nome': projeto.nome,
                'cliente': projeto.cliente,
                'status_nome': projeto.status.nome,
                'data_aprovacao': projeto.data_aprovacao.isoformat() if projeto.data_aprovacao else None,
                'motivo_rejeicao': projeto.motivo_rejeicao or 'Sem motivo especificado',
                'observacoes': projeto.observacoes or ''
            })
        
        return JsonResponse({
            'success': True,
            'projetos': projetos_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required(login_url='/login/')
@require_http_methods(["GET"])
def api_projetos_rejeitados(request):
    """API para carregar projetos rejeitados via AJAX"""
    try:
        projetos_rejeitados = Projeto.objects.filter(
            #usuario=request.user,
            aprovacao='rejeitado'
        ).order_by('-data_aprovacao')[:6]  # Limitar a 6 projetos
        
        projetos_data = []
        for projeto in projetos_rejeitados:
            projetos_data.append({
                'id': projeto.id,
                'nome': projeto.nome,
                'cliente': projeto.cliente,
                'data_aprovacao': projeto.data_aprovacao.strftime('%d/%m/%Y %H:%M') if projeto.data_aprovacao else 'Não informado',
                'motivo_rejeicao': projeto.motivo_rejeicao[:100] + '...' if projeto.motivo_rejeicao and len(projeto.motivo_rejeicao) > 100 else projeto.motivo_rejeicao or 'Sem motivo informado',
                'status_nome': projeto.status.nome,
                'status_cor': projeto.status.cor,
            })
        
        return JsonResponse({
            'success': True,
            'projetos': projetos_data,
            'total': len(projetos_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'projetos': [],
            'total': 0
        })
    

@login_required(login_url='/login/')
@require_http_methods(["GET"])
def api_metricas_filtradas(request):
    """API para calcular métricas com filtro de data"""
    try:
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        # Pegar parâmetros de data
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        
        # Converter strings para datas
        data_inicio = None
        data_fim = None
        
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        
        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        # Base query - projetos do usuário
        projetos_base = Projeto.objects.filter(
            #usuario=request.user
            )
        
        # Aplicar filtros de data se fornecidos
        if data_inicio:
            projetos_base = projetos_base.filter(data_criacao__date__gte=data_inicio)
        
        if data_fim:
            projetos_base = projetos_base.filter(data_criacao__date__lte=data_fim)
        
        # Projetos ativos (não concluídos e não rejeitados)
        projetos_ativos = projetos_base.filter(
            concluido=False,
            aprovacao__in=['pendente', 'aprovado']
        )
        
        # ========== CALCULAR MÉTRICAS ==========
        
        hoje = timezone.now().date()
        
        # Se há filtro de data, ajustar o "hoje" para o período
        if data_fim:
            hoje = min(hoje, data_fim)
        
        # 1. Projetos em atraso
        projetos_em_atraso = projetos_ativos.filter(data_prazo_entrega__lt=hoje).count()
        
        # 2. Projetos da semana (dentro do período filtrado)
        if data_inicio and data_fim:
            # Se há filtro, contar projetos com prazo dentro do período
            projetos_semana = projetos_ativos.filter(
                data_prazo_entrega__gte=data_inicio,
                data_prazo_entrega__lte=data_fim
            ).count()
            periodo_texto = f"{data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m')}"
        else:
            # Semana atual
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            fim_semana = inicio_semana + timedelta(days=6)
            projetos_semana = projetos_ativos.filter(
                data_prazo_entrega__gte=inicio_semana,
                data_prazo_entrega__lte=fim_semana
            ).count()
            periodo_texto = f"{inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}"
        
        # 3. Projetos concluídos
        projetos_concluidos = projetos_base.filter(concluido=True).count()
        
        # 4. Orçamentos aceitos
        orcamentos_aceitos = projetos_base.filter(aprovacao='aprovado').count()
        
        # 5. Orçamentos rejeitados
        orcamentos_rejeitados = projetos_base.filter(aprovacao='rejeitado').count()
        
        # 6. Projetos pendentes
        projetos_pendentes = projetos_ativos.filter(aprovacao='pendente').count()
        
        # 7. Status breakdown
        status_list = StatusProjeto.objects.filter(ativo=True).order_by('ordem')
        status_metricas = []
        
        for status in status_list:
            count = projetos_ativos.filter(status=status).count()
            status_metricas.append({
                'id': status.id,
                'nome': status.nome,
                'cor': status.cor,
                'count': count
            })
        
        # Calcular percentuais
        total_orcamentos = orcamentos_aceitos + orcamentos_rejeitados
        percentual_aceitos = round((orcamentos_aceitos / total_orcamentos * 100) if total_orcamentos > 0 else 0)
        percentual_rejeitados = round((orcamentos_rejeitados / total_orcamentos * 100) if total_orcamentos > 0 else 0)
        
        return JsonResponse({
            'success': True,
            'metricas': {
                'projetos_ativos': projetos_ativos.count(),
                'projetos_em_atraso': projetos_em_atraso,
                'projetos_semana': projetos_semana,
                'projetos_concluidos': projetos_concluidos,
                'orcamentos_aceitos': orcamentos_aceitos,
                'orcamentos_rejeitados': orcamentos_rejeitados,
                'projetos_pendentes': projetos_pendentes,
                'status_metricas': status_metricas,
                'percentual_aceitos': percentual_aceitos,
                'percentual_rejeitados': percentual_rejeitados,
                'total_orcamentos': total_orcamentos,
                'periodo_texto': periodo_texto,
            },
            'filtros': {
                'data_inicio': data_inicio_str,
                'data_fim': data_fim_str,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })