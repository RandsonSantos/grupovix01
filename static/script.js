// 🔹 Inicializando variáveis globais
let pedido = [];
let total = 0;

// 🔹 Pegando os produtos do HTML via JSON para uso no JavaScript
let produtosDataElement = document.getElementById("produtos-data");
let produtosDisponiveis = produtosDataElement ? JSON.parse(produtosDataElement.textContent) : [];

function adicionarAoPedido(id, nome, preco, quantidade) {
    quantidade = parseInt(quantidade);

    if (isNaN(quantidade) || quantidade <= 0) {
        alert("Quantidade inválida! Informe um número maior que 0.");
        return;
    }

    let estoqueElement = document.getElementById(`estoque_${id}`);
    let estoqueAtual = parseInt(estoqueElement.textContent);

    if (quantidade > estoqueAtual) {
        alert("Erro: Estoque insuficiente!");
        return;
    }

    // Atualiza a quantidade no estoque na tela
    estoqueElement.textContent = estoqueAtual - quantidade;

    // Criar um objeto de produto com quantidade
    const item = { id, nome, preco, quantidade };

    // Adicionar ao array de pedido
    pedido.push(item);

    // Atualizar a exibição da lista de pedidos
    atualizarListaPedido();
}

function atualizarListaPedido() {
    let listaPedido = document.getElementById("lista-pedido");
    let totalElement = document.getElementById("total");

    // 🔹 Limpa a exibição anterior
    listaPedido.innerHTML = "";

    // 🔹 Calcula o total corretamente com quantidade
    total = pedido.reduce((acc, item) => acc + (item.preco * item.quantidade), 0);
    totalElement.textContent = total.toFixed(2);

    pedido.forEach((item, index) => {
        let li = document.createElement("li");
        li.className = "list-group-item";
        li.innerHTML = `${item.nome} (x${item.quantidade}) - R$ ${(item.preco * item.quantidade).toFixed(2)}
            <button class="btn btn-danger btn-sm float-end" onclick="removerItem(${index})">❌</button>`;
        
        listaPedido.appendChild(li);
    });

    // 🔹 Atualiza o input oculto para envio no formulário, convertendo a lista para JSON
    document.getElementById("pedido-input").value = JSON.stringify(pedido);
}

function removerItem(index) {
    pedido.splice(index, 1);
    atualizarListaPedido();
}

function adicionarPorNome(event) {
    if (event.key === "Enter") {
        event.preventDefault();

        let input = document.getElementById("produto-input").value.toLowerCase().trim();
        let produtoEncontrado = produtosDisponiveis.find(produto => produto.nome.toLowerCase().includes(input));

        if (produtoEncontrado) {
            adicionarAoPedido(produtoEncontrado.id, produtoEncontrado.nome, produtoEncontrado.preco, 1);
            document.getElementById("produto-input").value = "";  // 🔹 Limpa o campo após adicionar
            document.getElementById("produto-input").focus(); // 🔹 Retorna o foco
        } else {
            alert("Produto não encontrado!");
        }
    }
}

function selecionarPagamento(tipo, botao) {
    document.getElementById("forma-pagamento").value = tipo;

    // 🔹 Destacar o botão selecionado
    document.querySelectorAll(".btn-group button").forEach(btn => btn.classList.remove("active"));
    botao.classList.add("active");

    // 🔹 Esconder aviso de erro
    document.getElementById("erro-pagamento").style.display = "none";
}

function validarPagamento() {
    let formaPagamento = document.getElementById("forma-pagamento").value;

    if (!formaPagamento) {
        document.getElementById("erro-pagamento").style.display = "block";
        return false; // 🔹 Impede envio do formulário
    }

    return true;
}

function filtrarProdutos() {
    let input = document.getElementById("produto-input").value.toLowerCase();
    let tabela = document.getElementById("tabela-produtos");
    let produtos = document.querySelectorAll(".produto-item");

    tabela.style.display = input.length > 0 ? "block" : "none";

    produtos.forEach(produto => {
        let nomeProdutoCell = produto.getElementsByTagName("td")[0];
        if (nomeProdutoCell) {
            let nomeProduto = nomeProdutoCell.textContent.toLowerCase();
            produto.style.display = nomeProduto.includes(input) ? "" : "none";
        }
    });
}

function cancelarVenda(id) {
    if (confirm("Tem certeza que deseja cancelar esta venda?")) {
        fetch(`/cancelar_venda/${id}`, { method: "PUT" })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("Venda cancelada com sucesso!");
                    window.location.reload(); // 🔹 Atualiza a página
                } else {
                    alert("Erro ao cancelar a venda: " + data.message);
                }
            })
            .catch(error => {
                alert("Ocorreu um erro no cancelamento. Verifique o console.");
                console.error("Erro:", error);
            });
    }
}
