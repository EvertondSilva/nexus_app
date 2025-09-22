from django.db import models
from django.contrib.auth.models import User


class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=7, default="#007bff")
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"


class Produto(models.Model):
    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, blank=True, null=True)
    descricao = models.TextField(blank=True)
    # preco = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.CASCADE, null=True, blank=True
    )
    estoque = models.IntegerField(default=0)
    estoque_minimo = models.IntegerField(default=5)
    unidade = models.CharField(max_length=10, default="UN")
    observacoes = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome"]


class StatusProjeto(models.Model):
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=7, default="#6c757d")
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Status do Projeto"
        verbose_name_plural = "Status dos Projetos"
        ordering = ["ordem"]


class Projeto(models.Model):
    APROVACAO_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('rejeitado', 'Rejeitado'),
    ]
    
    nome = models.CharField(max_length=200)
    cliente = models.CharField(max_length=200)
    data_prazo_entrega = models.DateField()
    data_prazo_pagamento = models.DateField()
    status = models.ForeignKey(StatusProjeto, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    observacoes = models.TextField(blank=True, null=True)
    concluido = models.BooleanField(default=False)
    data_conclusao = models.DateTimeField(blank=True, null=True)
    
    # CAMPOS DE APROVAÇÃO
    aprovacao = models.CharField(max_length=10, choices=APROVACAO_CHOICES, default='pendente')
    data_aprovacao = models.DateTimeField(blank=True, null=True)
    motivo_rejeicao = models.TextField(blank=True, null=True)
    
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} - {self.cliente}"

    def marcar_como_concluido(self):
        """Marca o projeto como concluído"""
        from django.utils import timezone

        self.concluido = True
        self.data_conclusao = timezone.now()
        self.save()

    def reabrir_projeto(self):
        """Reabre um projeto concluído"""
        self.concluido = False
        self.data_conclusao = None
        self.save()
    
    def aprovar_projeto(self):
        """Aprova o projeto"""
        from django.utils import timezone
        self.aprovacao = 'aprovado'
        self.data_aprovacao = timezone.now()
        self.motivo_rejeicao = None
        self.save()
    
    def rejeitar_projeto(self, motivo=None):
        """Rejeita o projeto"""
        from django.utils import timezone
        self.aprovacao = 'rejeitado'
        self.data_aprovacao = timezone.now()
        self.motivo_rejeicao = motivo
        self.save()
    
    def resetar_aprovacao(self):
        """Reseta a aprovação para pendente"""
        self.aprovacao = 'pendente'
        self.data_aprovacao = None
        self.motivo_rejeicao = None
        self.save()

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["-data_criacao"]


class MaterialProjeto(models.Model):
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="materiais"
    )
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.projeto.nome} - {self.produto.nome} ({self.quantidade})"

    class Meta:
        verbose_name = "Material do Projeto"
        verbose_name_plural = "Materiais dos Projetos"
        unique_together = ["projeto", "produto"]