from flask import Blueprint, jsonify, request, render_template
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

bp = Blueprint('routes', __name__)

@bp.route("/teste") 
def teste():
    return render_template("index.html")

'''
=================== Rotas para Login e Cadastro ===================
'''

@bp.route('/registrar', methods=['POST'])
def registrar():
    from .models import User
    data = request.get_json()

    # Verifica se todos os campos obrigatórios estão presentes
    if not data or not data.get("username") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Dados incompletos"}), 400
    
    # Consulta se já existe um usuário com o mesmo nome ou email
    user_exists = User.query.filter((User.username == data["username"]) | (User.email == data["email"])).first()
    if user_exists:
        return jsonify({"error": "Usuário já existente"}), 409
    
    # Cria novo usuário com os dados recebidos
    user = User(
        username=data["username"],
        email=data["email"]
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Cadastro realizado com sucesso"}), 201

@bp.route('/login', methods=['POST'])
def login():
    from .models import User
    data = request.get_json()

    # Verifica se e-mail e senha foram enviados
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Dados incompletos"}), 400
    
    # Busca o usuário pelo e-mail informado
    user = User.query.filter_by(email=data["email"]).first()

    # Verifica se o usuário existe e se a senha está correta
    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "Credenciais inválidas"}), 401
    return jsonify({"message": "Login realizado"}), 200

'''
=================== Rotas para interações com a API da Câmara ===================
'''

# Busca por tema de um projeto
@bp.route("/projetos", methods=["GET"])
def listar_projetos():

    pagina = request.args.get("pagina", 1)
    codigos_de_tema = request.args.getlist("tema")

    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?pagina={pagina}"

    for codigo in codigos_de_tema:
        url += f"&codTema={codigo}"

    resposta = requests.get(url)
    return jsonify(resposta.json())

# Buscar por ID de um projeto
@bp.route("/projetos/<int:id>", methods=["GET"])
def detalhes_do_projeto(id):
    url_base = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/"

    resposta = requests.get(f"{url_base}{id}")
    dados_projeto = resposta.json().get('dados', {})

    # Reune as informações do PL necessárias para formar a descrição
    descricao_PL = {
        "projeto": dados_projeto.get("siglaTipo"),
        "ano_do_projeto": dados_projeto.get("ano"),
        "numero_do_projeto": dados_projeto.get("numero")
    }

    # Formata as informações para que a descrição esteja no modelo correto
    descricao_PL_formatada = f"{descricao_PL['projeto']} {descricao_PL['ano_do_projeto']}/{descricao_PL['numero_do_projeto']}"

    resultado = {
        "id": dados_projeto.get("id"),
        "informacoes": {
            "titulo": dados_projeto.get("ementa"),
            "descricao": descricao_PL_formatada,
            "ano_inicio": dados_projeto.get("ano")
        },
        "status_tramitacao_atual": {
            "descricao_tramitacao": dados_projeto.get("statusProposicao", {}).get("descricaoTramitacao", ""),
            "descricao_situacao": dados_projeto.get("statusProposicao", {}).get("descricaoSituacao", ""),
            "sigla_orgao": dados_projeto.get("statusProposicao", {}).get("siglaOrgao", ""),
            "data_hora": dados_projeto.get("statusProposicao", {}).get("dataHora", ""),
            "despacho": dados_projeto.get("statusProposicao", {}).get("despacho", "")         
        } 
    }
    return jsonify(resultado)

# Buscar as tramitações de um projeto
@bp.route("/projetos/tramitacoes/<int:id>", methods=["GET"])
def tramitacoes(id):
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id}/tramitacoes"

    resposta = requests.get(url)
    dados_tramitacoes = resposta.json().get("dados", {})

    resultado = [{
        "data": tramitacao.get("dataHora")[:10],
        "hora": tramitacao.get("dataHora")[-5:],
        "situacao": tramitacao.get("descricaoSituacao"),
        "tramitacao": tramitacao.get("descricaoTramitacao")
    } for tramitacao in dados_tramitacoes
    ]

    return resultado

# Busca todos os temas existentes
@bp.route("/projetos/temas", methods=["GET"])
def listar_temas_projetos():
    url = "https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTema"

    resposta = requests.get(url)

    dados = resposta.json()
    lista_de_temas = dados.get('dados', [])

    temas_formatados = []

    for tema in lista_de_temas:
        nome = tema.get('nome', 'Sem nome')
        cod = tema.get('cod', 'Sem código')
        texto = f"Nome: {nome} - Cod: {cod}"
        temas_formatados.append(texto)

    contagem = len(lista_de_temas)

    resposta_final = {
        "total_de_temas": contagem,
        "temas": temas_formatados
    }
    return jsonify(resposta_final)

# Salva o tema escolhido
@bp.route("/projeto/interesses", methods=["POST"])
def salvar_interesses():
    dados = request.get_json()

    if not dados or 'codigos' not in dados:
        return jsonify({"ERRO": "Nenhum código de tema foi enviado"}), 400
    
    codigos_selecionados = dados['codigos']

    print(f"Interesses recebidos e salvos (simulação): {codigos_selecionados}")

    return jsonify({
        "mensagem": "Interesses salvos com sucesso",
        "temas_selecionados": codigos_selecionados
    }), 201