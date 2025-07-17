from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from decimal import Decimal
from collections import defaultdict
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

app = Flask(__name__)

# 🔧 Configuração geral
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://db_grupovixloja1_user:lZAJz61gp1qBngzMzQO5WVOsUjQzNenA@dpg-d1so45fdiees738h258g-a/db_grupovixloja1'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "sua_chave_super_secreta"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=5)
SENHA_MASTER = os.getenv("SENHA_MASTER", "123")

# 🗃️ Banco e modelos
from models import db, Usuario, Produto, Cliente, Pedido, Caixa
db.init_app(app)

# ---------------------- ROTA PRINCIPAL ---------------------- #
@app.route("/")
def home():
    # Verificação de autenticação
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar a frente de caixa", "warning")
        return redirect(url_for("login"))

    # Coleta de dados para exibir
    produtos = Produto.query.all()
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()
    ultimo_pedido = Pedido.query.order_by(Pedido.id.desc()).first()

    # Processamento seguro dos produtos do último pedido
    if ultimo_pedido:
        try:
            ultimo_pedido.produtos = json.loads(ultimo_pedido.produtos)
        except Exception:
            ultimo_pedido.produtos = []

    # Recupera dados do usuário para exibir na navbar ou tela
    usuario = Usuario.query.get(session["usuario_id"])

    return render_template("home.html",
        produtos=produtos,
        clientes=clientes,
        ultimo_pedido=ultimo_pedido,
        usuario=usuario
    )

#       CADASTRO DE USUARIOS        #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha_hash, senha):
            session["usuario_id"] = usuario.id
            session["usuario_tipo"] = usuario.tipo
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("home"))
        else:
            flash("Credenciais inválidas", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema com sucesso", "info")
    return redirect(url_for("login"))

@app.route("/cadastrar_usuario", methods=["GET", "POST"])
def cadastrar_usuario():

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        tipo = request.form.get("tipo")

        if not nome or not email or not senha or tipo not in ["admin", "atendimento"]:
            flash("Preencha todos os campos corretamente", "warning")
            return redirect(url_for("cadastrar_usuario"))

        senha_hash = generate_password_hash(senha)
        novo_usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash, tipo=tipo)
        db.session.add(novo_usuario)
        db.session.commit()
        flash(f"Usuário '{nome}' cadastrado com sucesso!", "success")
        return redirect(url_for("cadastrar_usuario"))

    return render_template("cadastrar_usuario.html")

@app.route("/usuarios")
def listar_usuarios():
    if session.get("usuario_tipo") != "admin":
        flash("Acesso negado", "danger")
        return redirect(url_for("home"))

    usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    return render_template("usuarios.html", usuarios=usuarios)

@app.route("/excluir_usuario/<int:id>", methods=["POST"])
def excluir_usuario(id):
    if session.get("usuario_tipo") != "admin":
        flash("Acesso negado", "danger")
        return redirect(url_for("home"))

    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("listar_usuarios"))



# ---------------------- FINALIZAR VENDA ---------------------- #
@app.route("/processar_venda", methods=["POST"])
def processar_venda():
    pedido_json = request.form.get("pedido")
    forma_pagamento = request.form.get("forma_pagamento", "Dinheiro")
    cliente_id = request.form.get("cliente_id")
    venda_fiado = request.form.get("fiado") == "on"

    if not pedido_json or pedido_json == "[]":
        return jsonify({"success": False, "message": "Erro: Nenhum produto selecionado."}), 400

    if venda_fiado and not cliente_id:
        return jsonify({"success": False, "message": "Venda fiado exige um cliente selecionado."}), 400

    try:
        produtos_selecionados = json.loads(pedido_json)
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Erro ao processar os produtos."}), 400

    total = 0
    itens = []
    for item in produtos_selecionados:
        produto = Produto.query.get(item["id"])
        if not produto or produto.estoque < item["quantidade"]:
            return jsonify({"success": False, "message": f"Estoque insuficiente para {item['nome']}"}), 400
        produto.estoque -= item["quantidade"]
        total += produto.preco * item["quantidade"]
        itens.append({
            "id": produto.id,
            "nome": produto.nome,
            "quantidade": item["quantidade"],
            "preco": produto.preco
        })

    nova_venda = Pedido(
        produtos=json.dumps(itens, ensure_ascii=False),
        total=total,
        status="finalizado",
        forma_pagamento=forma_pagamento,
        fiado=venda_fiado,
        cliente_id=cliente_id if venda_fiado else None
    )
    db.session.add(nova_venda)
    db.session.commit()
    return redirect(url_for("cupom", id=nova_venda.id))

@app.route("/cupom/<int:id>")
def cupom(id):
    pedido = Pedido.query.get_or_404(id)
    try:
        pedido.produtos = json.loads(pedido.produtos)
    except (json.JSONDecodeError, TypeError):
        pedido.produtos = []
    return render_template("cupom.html", pedido=pedido)

# ---------------------- ROTA DE VENDAS ---------------------- #
@app.route("/vendas", methods=["GET", "POST"])
def vendas():
        # Verificação de autenticação
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar a frente de caixa", "warning")
        return redirect(url_for("login"))

    query = Pedido.query
    if request.method == "POST":
        status = request.form.get("status")
        forma = request.form.get("forma_pagamento")
        if status:
            query = query.filter_by(status=status)
        if forma:
            query = query.filter_by(forma_pagamento=forma)

    pedidos = query.order_by(Pedido.id.desc()).all()

    for pedido in pedidos:
        try:
            pedido.produtos = json.loads(pedido.produtos) if isinstance(pedido.produtos, str) else []
        except (json.JSONDecodeError, TypeError):
            pedido.produtos = []

    return render_template("vendas.html", pedidos=pedidos)

@app.route("/vendas_realizadas", methods=["GET", "POST"])
def vendas_realizadas():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar a frente de caixa", "warning")
        return redirect(url_for("login"))

    hoje = datetime.utcnow().date()
    status = request.form.get("status")
    forma_pagamento = request.form.get("forma_pagamento")
    fiado = request.form.get("fiado")

    query = Pedido.query.filter(db.func.date(Pedido.data) == hoje)

    if status:
        query = query.filter(Pedido.status == status)
    if forma_pagamento:
        query = query.filter(Pedido.forma_pagamento == forma_pagamento)
    if fiado == "true":
        query = query.filter(Pedido.fiado.is_(True))
    elif fiado == "false":
        query = query.filter(Pedido.fiado.is_(False))

    pedidos = query.order_by(Pedido.data.desc()).all()

    total_finalizadas = sum(1 for p in pedidos if p.status == "finalizado")
    total_canceladas = sum(1 for p in pedidos if p.status == "cancelado")
    faturamento_finalizadas = sum(p.total or 0 for p in pedidos if p.status == "finalizado")
    faturamento_canceladas = sum(p.total or 0 for p in pedidos if p.status == "cancelado")

    return render_template("vendas_realizadas.html",
        pedidos=pedidos,
        total_finalizadas=total_finalizadas,
        total_canceladas=total_canceladas,
        faturamento_finalizadas=faturamento_finalizadas,
        faturamento_canceladas=faturamento_canceladas
    )
    

@app.route("/cancelar_venda/<int:id>", methods=["POST"])
def cancelar_venda(id):
    pedido = Pedido.query.get_or_404(id)

    if pedido.status == "cancelado":
        return jsonify({"success": False, "message": "Venda já está cancelada"}), 400

    try:
        # Fallback seguro
        itens = pedido.produtos
        if isinstance(itens, str):
            itens = json.loads(itens)

        for item in itens:
            produto = Produto.query.get(item["id"])
            if produto:
                produto.estoque += item["quantidade"]

        pedido.status = "cancelado"
        db.session.commit()
        return jsonify({"success": True, "message": "Venda cancelada com sucesso"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Erro ao cancelar venda: {str(e)}"}), 500
    
from datetime import datetime
from flask import request

@app.route("/relatorio_vendas", methods=["GET", "POST"])
def relatorio_vendas():
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar o relatório", "warning")
        return redirect(url_for("login"))

    # 🗓️ Definir datas padrão
    hoje = datetime.utcnow().date()
    data_inicio = data_fim = hoje

    if request.method == "POST":
        data_inicio_str = request.form.get("data_inicio")
        data_fim_str = request.form.get("data_fim")

        try:
            if data_inicio_str:
                data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            if data_fim_str:
                data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Formato de data inválido", "danger")
            return redirect(url_for("relatorio_vendas"))

    # 🔎 Buscar pedidos no intervalo
    pedidos = Pedido.query.filter(
        db.func.date(Pedido.data) >= data_inicio,
        db.func.date(Pedido.data) <= data_fim
    ).all()

    # 📊 Resumo financeiro
    resumo = {
        "Dinheiro": 0,
        "Cartão": 0,
        "PIX": 0,
        "Fiado": 0,
        "Cancelado": 0,
        "Total geral": 0
    }

    for p in pedidos:
        if p.status == "cancelado":
            resumo["Cancelado"] += p.total or 0
        else:
            if p.fiado:
                resumo["Fiado"] += p.total or 0

            if p.forma_pagamento in resumo:
                resumo[p.forma_pagamento] += p.total or 0

            resumo["Total geral"] += p.total or 0

    return render_template("relatorio_vendas.html",
        resumo=resumo,
        pedidos=pedidos,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


# ---------------------- PRODUTOS ---------------------- #
@app.route("/adicionar_produto", methods=["POST"])
def adicionar_produto():
        # Verificação de autenticação
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar a frente de caixa", "warning")
        return redirect(url_for("login"))

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

@app.route("/ver_produto/<int:id>")
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
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for("estoque"))

# ---------------------- CONTROLE DE CAIXA ---------------------- #
@app.route("/controle_caixa")
def controle_caixa():
        # Verificação de autenticação
    if not session.get("usuario_id"):
        flash("Você precisa estar logado para acessar a frente de caixa", "warning")
        return redirect(url_for("login"))

    hoje = datetime.utcnow().date()
    caixa_aberto = Caixa.query.filter_by(status="aberto").first()
    pedidos_do_dia = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje, Pedido.status == "finalizado"
    ).all()
    saldo_vendas = sum(p.total or 0 for p in pedidos_do_dia)
    saldo_total = (caixa_aberto.saldo_inicial if caixa_aberto else 0) + saldo_vendas

    return render_template("caixa.html",
        caixas=Caixa.query.order_by(Caixa.data_abertura.desc()).all(),
        caixa_aberto=caixa_aberto,
        saldo_vendas=saldo_vendas,
        saldo_total_caixa=saldo_total)

@app.route("/abrir_caixa", methods=["POST"])
def abrir_caixa():
    saldo_inicial = request.form.get("saldo_inicial", type=float)
    if saldo_inicial is None or saldo_inicial < 0:
        flash("Valor inválido", "danger")
        return redirect(url_for("controle_caixa"))

    if Caixa.query.filter_by(status="aberto").first():
        flash("Já existe um caixa aberto. Feche primeiro.", "warning")
        return redirect(url_for("controle_caixa"))

    caixa = Caixa(saldo_inicial=saldo_inicial, saldo_atual=saldo_inicial, status="aberto")
    db.session.add(caixa)
    db.session.commit()
    flash("Caixa aberto com sucesso", "success")
    return redirect(url_for("controle_caixa"))

@app.route("/fechar_caixa/<int:id>", methods=["POST"])
def fechar_caixa(id):
    caixa = Caixa.query.get_or_404(id)
    valor_gaveta = request.form.get("valor_gaveta", type=float)

    if valor_gaveta is None or valor_gaveta < 0:
        flash("Valor inválido", "danger")
        return redirect(url_for("controle_caixa"))

    caixa.saldo_final = valor_gaveta
    caixa.status = "fechado"
    caixa.data_fechamento = datetime.utcnow()
    db.session.commit()
    flash("Caixa fechado com sucesso", "success")
    return redirect(url_for("controle_caixa"))

@app.route("/excluir_caixas", methods=["POST"])
def excluir_todos_caixas():
    try:
        caixas = Caixa.query.all()
        for c in caixas:
            db.session.delete(c)
        db.session.commit()
        flash("Todos os registros de caixa foram excluídos!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {e}", "danger")

    return redirect(url_for("controle_caixa"))

# ---------------------- DASHBOARD ADMIN ---------------------- #
@app.route("/dashboard_admin")
def dashboard_admin():
    if session.get("usuario_tipo") != "admin":
        flash("Acesso negado", "danger")
        return redirect(url_for("home"))  # ← corrigido

    hoje = datetime.utcnow().date()

    usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    total_produtos = Produto.query.count()
    total_pedidos = Pedido.query.count()

    pedidos_finalizados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje,
        Pedido.status == "finalizado"
    ).count()

    pedidos_cancelados = Pedido.query.filter(
        db.func.date(Pedido.data) == hoje,
        Pedido.status == "cancelado"
    ).count()

    faturamento_total = db.session.query(db.func.sum(Pedido.total)).filter(
        db.func.date(Pedido.data) == hoje,
        Pedido.status == "finalizado"
    ).scalar() or 0

    return render_template("dashboard_admin.html",
        usuarios=usuarios,
        total_produtos=total_produtos,
        total_pedidos=total_pedidos,
        pedidos_finalizados=pedidos_finalizados,
        pedidos_cancelados=pedidos_cancelados,
        faturamento_total=faturamento_total
    )

# ---------------------- ESTOQUE COM SENHA ---------------------- #
@app.route("/estoque")
def estoque():
    # Verificação de permissão de administrador
    if session.get("usuario_tipo") != "admin":
        flash("Acesso negado", "danger")
        return redirect(url_for("dashboard_admin"))

    produtos = Produto.query.all()
    return render_template("estoque.html", produtos=produtos)

@app.route("/pedir_senha")
def pedir_senha():
    return render_template("pedir_senha.html")

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    senha_digitada = request.form.get("senha_master")
    if senha_digitada == SENHA_MASTER:
        session["autorizado_estoque"] = True
        return redirect(url_for("dashboard_admin"))
    flash("Senha incorreta", "danger")
    return redirect(url_for("pedir_senha"))

# ---------------------- CLIENTES ---------------------- #
@app.route("/cadastrar_cliente", methods=["GET", "POST"])
def cadastrar_cliente():
    if request.method == "POST":
        nome = request.form.get("nome")
        if not nome:
            flash("Nome é obrigatório", "warning")
        else:
            novo_cliente = Cliente(nome=nome)
            db.session.add(novo_cliente)
            db.session.commit()
            flash(f"Cliente '{nome}' cadastrado com sucesso!", "success")
            return redirect(url_for("cadastrar_cliente"))

    return render_template("clientes/cadastrar.html")

@app.route("/editar_cliente/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        novo_nome = request.form.get("nome")
        if not novo_nome:
            flash("Nome não pode ficar vazio", "warning")
            return redirect(url_for("editar_cliente", id=id))

        cliente.nome = novo_nome
        db.session.commit()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("listar_clientes"))

    return render_template("clientes/editar.html", cliente=cliente)

@app.route("/excluir_cliente/<int:id>", methods=["POST"])
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    # Se quiser impedir exclusão com pedidos vinculados:
    if cliente.pedidos.count() > 0:
        flash("Não é possível excluir cliente com pedidos vinculados.", "danger")
        return redirect(url_for("listar_clientes"))

    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for("listar_clientes"))

@app.route("/clientes")
def listar_clientes():
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()
    return render_template("clientes/listar.html", clientes=clientes)

# ---------------------- PEDIDOS DO CLIENTE ---------------------- #
from collections import defaultdict
from decimal import Decimal
from datetime import datetime

@app.route("/clientes/<int:cliente_id>/pedidos", methods=["GET", "POST"])
def pedidos_do_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    # POST: excluir todos os pedidos desse cliente
    if request.method == "POST":
        senha = request.form.get("senha_master")
        if senha != SENHA_MASTER:
            flash("Senha incorreta!", "danger")
            return redirect(url_for("pedidos_do_cliente", cliente_id=cliente_id))

        pedidos = Pedido.query.filter_by(cliente_id=cliente_id).all()
        for pedido in pedidos:
            db.session.delete(pedido)
        db.session.commit()
        flash(f"{len(pedidos)} pedidos excluídos do cliente!", "success")
        return redirect(url_for("pedidos_do_cliente", cliente_id=cliente_id))

    # 🔍 Filtros GET
    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    imprimir = request.args.get("imprimir") == "1"

    query = Pedido.query.filter_by(cliente_id=cliente_id)

    if status:
        query = query.filter(Pedido.status == status)

    try:
        if data_inicio:
            data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
            query = query.filter(Pedido.data >= data_inicio_dt)
        if data_fim:
            data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")
            query = query.filter(Pedido.data <= data_fim_dt)
    except ValueError:
        flash("Formato de data inválido", "danger")

    pedidos = query.order_by(Pedido.data.desc()).all()

    if imprimir:
        resumo = {
            "total_geral": Decimal("0.00"),
            "total_fiado": Decimal("0.00"),
            "por_status": defaultdict(Decimal),
            "por_forma_pagamento": defaultdict(Decimal)
        }

        for pedido in pedidos:
            valor = Decimal(str(pedido.total))
            resumo["por_status"][pedido.status] += valor
            resumo["por_forma_pagamento"][pedido.forma_pagamento] += valor
            if pedido.status != "cancelado":
                resumo["total_geral"] += valor
                if pedido.fiado:
                    resumo["total_fiado"] += valor

        return render_template("clientes/imprimir_pedidos.html",
            cliente=cliente,
            pedidos=pedidos,
            status=status,
            data_inicio=data_inicio,
            data_fim=data_fim,
            agora=datetime.now(),
            resumo=resumo
        )

    return render_template("clientes/pedidos_cliente.html",
        cliente=cliente,
        pedidos=pedidos,
        status=status,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


@app.route("/marcar_pago/<int:pedido_id>", methods=["POST"])
def marcar_pago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if not pedido.fiado:
        return jsonify({"success": False, "message": "Pedido já está pago."}), 400
    pedido.fiado = False
    db.session.commit()
    return jsonify({"success": True, "message": "Pedido marcado como pago."})

@app.route("/reverter_pago/<int:pedido_id>", methods=["POST"])
def reverter_pago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.fiado:
        return jsonify({"success": False, "message": "Pedido já está fiado."}), 400
    pedido.fiado = True
    db.session.commit()
    return jsonify({"success": True, "message": "Pedido revertido para fiado."})

# ---------------------- EXCLUSÃO GLOBAL DE FIADOS ---------------------- #
@app.route("/excluir_vendas", methods=["POST"])
def excluir_vendas():
    senha = request.form.get("senha_master")
    if senha != SENHA_MASTER:
        flash("Senha incorreta!", "danger")
        return redirect(url_for("dashboard_admin"))

    fiados = Pedido.query.filter_by(fiado=True).all()
    for pedido in fiados:
        db.session.delete(pedido)

    db.session.commit()
    flash(f"{len(fiados)} pedidos fiado foram excluídos!", "success")
    return redirect(url_for("dashboard_admin"))

# ---------------------- OUTRAS ROTAS ---------------------- #
@app.route("/lojas")
def lojas():
    return render_template("lojas.html")

# ---------------------- INICIAR APP ---------------------- #
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
