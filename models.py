from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------------------- Modelo de Usuário ---------------------- #
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # 🔹 Define se o usuário é admin

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


# ---------------------- Modelo de Produto ---------------------- #
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False, default=0.0)
    estoque = db.Column(db.Integer, nullable=False, default=0)


# ---------------------- Modelo de Cliente ---------------------- #
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    pedidos = db.relationship("Pedido", backref="cliente", lazy="dynamic")  # 🔹 Melhor performance


# ---------------------- Modelo de Pedido ---------------------- #
class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produtos = db.Column(db.Text, nullable=False)  # 🔹 Armazena produtos em JSON string
    total = db.Column(db.Float, nullable=False, default=0.0)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="pendente")
    data = db.Column(db.DateTime, default=datetime.utcnow)  # 🔹 Registra a data da venda automaticamente
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))  # 🔹 Relaciona pedido ao cliente


# ---------------------- Modelo de Caixa ---------------------- #
class Caixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    saldo_inicial = db.Column(db.Float, nullable=False, default=0.0)
    saldo_atual = db.Column(db.Float, nullable=False, default=0.0)
    saldo_final = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="aberto")  # 🔹 "aberto" ou "fechado"
    data_fechamento = db.Column(db.DateTime)
