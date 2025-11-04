from flask import Blueprint, jsonify, request, render_template
import requests

bp = Blueprint('routes', __name__)

@bp.route("/teste") 
def teste():
    return render_template("index.html")

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
    return ""

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