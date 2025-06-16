from flask import Flask, redirect, render_template, request, url_for, session, jsonify
from models import Caixa, Cliente, Pedido, Produto, Usuario, db
import json
from datetime import datetime
from flask import render_template, request, redirect, url_for, jsonify
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask import request, jsonify, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv # type: ignore
from flask import session
from datetime import timedelta



app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///lanchonete.db"
app.config["SECRET_KEY"] = "sua_chave_super_secreta"
db.init_app(app)



# ---------------------- ROTA PRINCIPAL ---------------------- #
@app.route("/")
def home():
    produtos = Produto.query.all()
    ultimo_pedido = Pedido.query.order_by(Pedido.id.desc()).first()  # 🔹 Pega o último pedido

    if ultimo_pedido:
        try:
            ultimo_pedido.produtos = json.loads(ultimo_pedido.produtos)
        except json.JSONDecodeError:
            ultimo_pedido.produtos = []

    return render_template("home.html", produtos=produtos, ultimo_pedido=ultimo_pedido)

@app.route("/caixa")
def caixa():
    produtos = Produto.query.all()
    return render_template("caixa.html", produtos=produtos)

# ---------------------- FINALIZAR VENDA ---------------------- #
@app.route("/finalizar_venda", methods=["POST"])
def finalizar_venda():
    produtos_consumidos = []  # 🔹 Inicializa corretamente a variável
    total = 0

    for produto in Produto.query.all():
        quantidade = request.form.get(f"quantidade_{produto.id}", type=int)
        if quantidade and quantidade > 0:
            produtos_consumidos.append({
                "id": produto.id,
                "nome": produto.nome,
                "quantidade": quantidade,
                "preco": produto.preco
            })
            total += produto.preco * quantidade
            produto.estoque -= quantidade

    forma_pagamento = request.form.get("forma_pagamento", "Dinheiro")

    if not produtos_consumidos:
        return "Nenhum produto selecionado", 400

    nova_venda = Pedido(
        produtos=json.dumps(produtos_consumidos, ensure_ascii=False),  # 🔹 Salva corretamente como JSON
        total=total,
        status="finalizado",
        forma_pagamento=forma_pagamento
    )
    db.session.add(nova_venda)
    db.session.commit()

    return redirect(url_for("vendas"))

# ---------------------- PROCESSAR VENDA ---------------------- #
@app.route("/processar_venda", methods=["POST"])
def processar_venda():
    pedido_json = request.form.get("pedido")
    forma_pagamento = request.form.get("forma_pagamento", "Dinheiro")  # 🔹 Definir padrão caso vazio

    if not pedido_json or pedido_json == "[]":
        return jsonify({"success": False, "message": "Erro: Nenhum produto selecionado."}), 400

    try:
        produtos_consumidos = json.loads(pedido_json)
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro ao processar os produtos."}), 400

    total = 0
    produtos_processados = []

    for item in produtos_consumidos:
        produto = Produto.query.get(item["id"])
        if produto:
            if produto.estoque >= item["quantidade"]:
                produto.estoque -= item["quantidade"]  # 🔹 Corrigindo atualização do estoque
                total += produto.preco * item["quantidade"]
                produtos_processados.append({"id": produto.id, "nome": produto.nome, "preco": produto.preco, "quantidade": item["quantidade"]})
            else:
                return jsonify({"success": False, "message": f"Erro: Estoque insuficiente para {item['nome']}."}), 400
        else:
            return jsonify({"success": False, "message": f"Erro: Produto ID {item['id']} não encontrado."}), 404
    db.session.commit()

    nova_venda = Pedido(
        produtos=json.dumps(produtos_processados, ensure_ascii=False),
        total=total,
        status="finalizado",
        forma_pagamento=forma_pagamento
    )

    db.session.add(nova_venda)  # ✅ Certo! Está passando uma instância corretamente
    db.session.commit()
    return redirect(url_for("cupom", id=nova_venda.id))

@app.route("/cupom/<int:id>")
def cupom(id):
        with db.session.no_autoflush:
            pedido = Pedido.query.get_or_404(id)

        try:
            pedido.produtos = json.loads(pedido.produtos)  # 🔹 Converte string JSON para lista
        except (json.JSONDecodeError, TypeError):
            pedido.produtos = []

        return render_template("cupom.html", pedido=pedido)

# ---------------------- ROTA DE VENDAS ---------------------- #
@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    query = db.session.query(Pedido)  # 🔹 Usa consulta modificável corretamente

    status_filtro = request.form.get("status")
    pagamento_filtro = request.form.get("forma_pagamento")

    if status_filtro:
        query = query.filter(Pedido.status == status_filtro)
    if pagamento_filtro:
        query = query.filter(Pedido.forma_pagamento == pagamento_filtro)

    pedidos = query.order_by(Pedido.id.desc()).all()

    for pedido in pedidos:
        try:
            if isinstance(pedido.produtos, str):  # 🔹 Certifica que produtos está em formato correto
                pedido.produtos = json.loads(pedido.produtos)
            else:
                pedido.produtos = []
        except (json.JSONDecodeError, TypeError):
            pedido.produtos = []

    return render_template("vendas.html", pedidos=pedidos)

@app.route("/vendas_realizadas")
def vendas_realizadas():
    hoje = datetime.utcnow().date()  # Obtém a data atual

    pedidos_finalizados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje, Pedido.status == "finalizado"
    ).all()

    pedidos_cancelados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje, Pedido.status == "cancelado"
    ).all()


    total_finalizadas = len(pedidos_finalizados)
    total_canceladas = len(pedidos_cancelados)

    faturamento_finalizadas = sum(p.total or 0 for p in pedidos_finalizados)
    faturamento_canceladas = sum(p.total or 0 for p in pedidos_cancelados)

    return render_template(
        "vendas_realizadas.html",
        pedidos=pedidos_finalizados + pedidos_cancelados,
        total_finalizadas=total_finalizadas,
        total_canceladas=total_canceladas,
        faturamento_finalizadas=faturamento_finalizadas,
        faturamento_canceladas=faturamento_canceladas,
    )
# ---------------------- CANCELAR VENDA ---------------------- #
@app.route("/cancelar_venda/<int:id>", methods=["PUT"])
def cancelar_venda(id):
    pedido = Pedido.query.get_or_404(id)

    if pedido.status == "cancelado":
        return {"success": False, "message": "Venda já está cancelada."}, 400

    produtos_vendidos = json.loads(pedido.produtos)  # 🔹 Certifique-se de converter para lista antes de usar

    for item in produtos_vendidos:
        produto = Produto.query.get(item["id"])
        if produto:
            produto.estoque += item["quantidade"]  # 🔹 Restaurando corretamente o estoque

    pedido.status = "cancelado"
    db.session.commit()
    return {"success": True}, 200

# ------
# from flask import session, render_template, request, redirect, url_for, jsonify
@app.route("/pedir_senha")
def pedir_senha():
    return render_template("pedir_senha.html")

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    senha_digitada = request.form.get("senha_master")

    if senha_digitada == SENHA_MASTER:
        session["autorizado_estoque"] = True  # 🔹 Define a sessão como autorizada
        return redirect(url_for("dashboard_admin"))
    
    return jsonify({"success": False, "message": "Acesso negado! Senha incorreta."}), 403


# ---------------- ROTA DE ESTOQUE ---------------------- #
@app.route("/estoque")
def estoque():
    if not session.get("autorizado_estoque"):  # 🔹 Usuário precisa estar autenticado
        return redirect(url_for("pedir_senha"))  

    produtos = Produto.query.all()
    return render_template("estoque.html", produtos=produtos)

@app.route("/logout")
def logout():
    session.pop("autorizado_estoque", None)  # 🔹 Remove acesso ao estoque
    return redirect(url_for("pedir_senha"))  # 🔹 Redireciona para a tela de login

# ---------------------- ADICIONAR PRODUTO ---------------------- #
load_dotenv()  # 🔹 Carregar variáveis de ambiente
SENHA_MASTER = os.getenv("SENHA_MASTER", "123")  # 🔹 Defina uma senha segura
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=5)  # 🔹 Usuário será desconectado após 5 minutos

@app.route("/adicionar_produto", methods=["POST"])
def adicionar_produto():
    nome = request.form["nome"]
    preco = float(request.form["preco"])
    estoque = int(request.form["estoque"])

    produto_existente = Produto.query.filter_by(nome=nome).first()
    if produto_existente:
        produto_existente.estoque += estoque
    else:
        novo_produto = Produto(nome=nome, preco=preco, estoque=estoque)
        db.session.add(novo_produto)

    db.session.commit()
    return redirect(url_for("estoque"))

@app.route("/produto/<int:id>")
def ver_produto(id):
    produto = Produto.query.get_or_404(id)
    return render_template("ver_produto.html", produto=produto)

@app.route("/editar_produto/<int:id>", methods=["GET", "POST"])
def editar_produto(id):
    produto = Produto.query.get_or_404(id)

    if request.method == "POST":
        produto.nome = request.form["nome"]
        produto.preco = float(request.form["preco"])
        produto.estoque = int(request.form["estoque"])
        db.session.commit()
        return redirect(url_for("estoque"))

    return render_template("editar_produto.html", produto=produto)

@app.route("/excluir_produto/<int:id>", methods=["POST"])
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)

    if not produto:
        return jsonify({"success": False, "message": "Produto não encontrado."}), 404

    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for("estoque"))

@app.route("/abrir_caixa", methods=["POST"])
def abrir_caixa():
    saldo_inicial = request.form.get("saldo_inicial", type=float)

    if saldo_inicial is None or saldo_inicial < 0:
        return jsonify({"success": False, "message": "Saldo inicial inválido."}), 400

    caixa_aberto = Caixa.query.filter_by(status="aberto").first()
    if caixa_aberto:
        return jsonify({"success": False, "message": "Erro: Já existe um caixa aberto. Feche o caixa atual antes de abrir um novo."}), 400

    novo_caixa = Caixa(saldo_inicial=saldo_inicial, saldo_atual=saldo_inicial, status="aberto")
    db.session.add(novo_caixa)
    db.session.commit()
    return redirect(url_for("controle_caixa"))

@app.route("/fechar_caixa/<int:id>", methods=["POST"])
def fechar_caixa(id):
    caixa = Caixa.query.get_or_404(id)
    valor_gaveta = request.form.get("valor_gaveta", type=float)

    if valor_gaveta is None or valor_gaveta < 0:
        return jsonify({"success": False, "message": "Valor na gaveta inválido."}), 400
    saldo_esperado = caixa.saldo_inicial  # 🔹 Removemos vendas finalizadas
    diferenca = valor_gaveta - saldo_esperado
    caixa.saldo_final = valor_gaveta
    caixa.diferenca = diferenca
    caixa.status = "fechado"
    caixa.data_fechamento = datetime.utcnow()

    db.session.commit()
    return redirect(url_for("controle_caixa"))

@app.route("/controle_caixa")
def controle_caixa():
    hoje = datetime.utcnow().date()  # Obtém a data atual
    caixa_aberto = Caixa.query.filter_by(status="aberto").first()
    pedidos_finalizados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje, 
        Pedido.status == "finalizado"
    ).all()
    saldo_vendas = sum(p.total or 0 for p in pedidos_finalizados)
    saldo_total_caixa = (caixa_aberto.saldo_inicial if caixa_aberto else 0) + saldo_vendas

    return render_template("caixa.html", caixas=Caixa.query.order_by(Caixa.data_abertura.desc()).all(),
                           caixa_aberto=caixa_aberto, saldo_vendas=saldo_vendas, saldo_total_caixa=saldo_total_caixa)


@app.route("/dashboard_admin")
def dashboard_admin():
    if not session.get("autorizado_estoque"):  # 🔹 Usuário precisa estar autenticado
        return redirect(url_for("pedir_senha"))  

    hoje = datetime.utcnow().date()  # 🔹 Obtém a data de hoje

    # Estatísticas
    total_produtos = Produto.query.count()
    total_pedidos = Pedido.query.count()

    # Contagem de pedidos do dia
    pedidos_finalizados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje, Pedido.status == "finalizado"
    ).count()

    pedidos_cancelados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje, Pedido.status == "cancelado"
    ).count()

    # Faturamento total do dia (excluindo pedidos cancelados)
    faturamento_total = db.session.query(
        db.func.sum(Pedido.total)
    ).filter(
        db.func.date(Pedido.data) == hoje,
        Pedido.status == "finalizado"
    ).scalar() or 0

    return render_template("dashboard_admin.html",
                           total_produtos=total_produtos,
                           total_pedidos=total_pedidos,
                           pedidos_finalizados=pedidos_finalizados,
                           pedidos_cancelados=pedidos_cancelados,
                           faturamento_total=faturamento_total)

# ---------------------- INICIAR APLICACÃO ---------------------- #
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)





