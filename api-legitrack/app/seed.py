import time
import requests
from datetime import datetime
from . import create_app, db
from .models import TP_Situacao, TP_Tramitacao, TP_Temas, TB_Projeto, RL_Tramitacoes, rel_temas
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import text

app = create_app()
app.app_context().push()

#Espero o DB iniciar
def wait_for_db():
    print("WORKER: Aguardando o banco de dados ficar pronto...")
    retries = 0
    max_retries = 10
    while retries < max_retries:
        try:
            db.session.execute(text('SELECT 1'))
            print("WORKER: Conexão com o banco de dados estabelecida!")
            return True
        except OperationalError:
            retries += 1
            wait_time = 5
            print(f"WORKER: Banco ainda não está pronto. Tentando novamente em {wait_time}s... (Tentativa {retries}/{max_retries})")
            time.sleep(wait_time)
        except Exception as e:
            print(f"WORKER: Erro inesperado ao esperar pelo banco: {e}")
            retries += 1
            time.sleep(5)
            
    print(f"WORKER: ERRO CRÍTICO! Não foi possível conectar ao banco após {max_retries} tentativas. Encerrando.")
    return False

#Atualização e Adição de Metadados das Tabelas Tipo 
def sicronizar_tabelas_tp(url, model_class, id_field_name, ds_field_name, api_id_key, api_desc_key):
    tabela_nome = model_class.__tablename__
    print(f"WORKER: Iniciando sicronização da tabela '{tabela_nome}'...")
    
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        dados_api = resposta.json().get('dados', {})

        if not dados_api:
            print(f"WORKER: Nenhum dado recebido da API para '{tabela_nome}'. Pulando.")
            return
        
        itens_locais = model_class.query.all()
        mapa_itens_locais = {getattr(item, id_field_name): item for item in itens_locais}
        print(f"WORKER: {len(mapa_itens_locais)} itens existem localmente em '{tabela_nome}'.")

        itens_para_salvar = []
        itens_atualizados = 0
        itens_novos = 0

        #Comparação
        for item_api in dados_api:
            try:
                id_api_str = item_api.get(api_id_key)
                desc_api = item_api.get(api_desc_key)

                if not id_api_str or not desc_api:
                    continue

                id_api = int(id_api_str)
                item_local = mapa_itens_locais.get(id_api) 

                if item_local: #Se já está no banco, atualiza se necessário
                    if getattr(item_local, ds_field_name) != desc_api:
                        setattr(item_local, ds_field_name, desc_api)
                        itens_para_salvar.append(item_local)
                        itens_atualizados += 1

                else:  #Se não está no banco, insere
                    novo_item_args = {id_field_name: id_api, ds_field_name: desc_api}
                    novo_item = model_class(**novo_item_args)
                    itens_para_salvar.append(novo_item)
                    itens_novos += 1

            except (AttributeError, ValueError, TypeError) as e:
                print(f"WORKER: [AVISO] ERRO em item individual (API enviou lixo? {item_api}). Erro: {e}. Pulando item.")
                continue

        if itens_para_salvar:
            print(f"WORKER: {itens_novos} itens novos, {itens_atualizados} itens atualizados para '{tabela_nome}'. Salvando...")
            try:
                db.session.add_all(itens_para_salvar)
                db.session.commit()
                print(f"WORKER: Sincronização de '{tabela_nome}' completa.")
            except Exception as e:
                db.session.rollback()
                print(f"WORKER: [ERRO] ERRO ao salvar no banco para '{tabela_nome}': {e}")
        else:
            print(f"WORKER: Tabela '{tabela_nome}' já está atualizada.")

    except requests.exceptions.RequestException as e:
        print(f"WORKER: [ERRO] ERRO DE REDE GERAL ao buscar '{tabela_nome}': {e}")
    except Exception as e:
        print(f"WORKER: [ERRO] ERRO INESPERADO (fora do loop) ao sicronizar '{tabela_nome}': {e}")
        db.session.rollback()

#Atualização e Adição de Projetos
def sicronizar_projetos():
    todos_projetos = []
    url = 'https://dadosabertos.camara.leg.br/api/v2/proposicoes?pagina=1&itens=100&ordem=ASC&ordenarPor=id'
    print("WORKER (Projetos): Iniciando busca paginada de projetos alterados...")

    while url:
        print(f"WORKER (Projetos): Buscando página: {url}")
        try:
            resposta = requests.get(url, timeout=10)
            resposta.raise_for_status()

            dados_api = resposta.json()
            projetos_desta_pagina = dados_api.get('dados', [])
            links_da_api = dados_api.get('links', [])

            if not projetos_desta_pagina:
                print("WORKER (Projetos): Página sem dados. Concluindo busca.")
                break

            todos_projetos.extend(projetos_desta_pagina)

            novo_url = None
            for link in links_da_api:
                if link.get('rel') == 'next':
                    novo_url = link.get('href')
                    break

            url = novo_url
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"WORKER (Projetos): [ERRO DE REDE] Falha ao buscar página: {e}. Abortando ciclo.")
            url = None

    if not todos_projetos:
        print("WORKER (Projetos): Nenhum projeto para atualizar neste ciclo.")
        return
    
    print(f"WORKER (Projetos): Paginação concluída. {len(todos_projetos)} projetos encontrados para checar/atualizar.")
    
    projetos_atualizados = 0
    projetos_novos = 0
    novas_tramitacoes_total = 0

    for projeto_resumido in todos_projetos:
        id_api = None

        try:
            id_api_str = projeto_resumido.get('id')
            if not id_api_str:
                print(f"WORKER (Projetos): [AVISO] Item de projeto resumido sem ID. Pulando item.")
                continue
            
            id_api = int(id_api_str)
            projeto_db = db.session.get(TB_Projeto, id_api)

            if not projeto_db:
                projeto_db = TB_Projeto(id_projeto=id_api)
                db.session.add(projeto_db)
                projetos_novos += 1
            else:
                projetos_atualizados += 1

            projeto_db.titulo_projeto = projeto_resumido.get('ementa')
            projeto_db.descricao = f"{projeto_resumido.get('siglaTipo')} {projeto_resumido.get('numero')}/{projeto_resumido.get('ano')}"
            projeto_db.ano_inicio = projeto_resumido.get('ano')

            resposta = requests.get(f'https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_api}', timeout=10)
            resposta.raise_for_status()

            projeto_detalhado = resposta.json().get('dados', {})
            status_proposicao = projeto_detalhado.get('statusProposicao', {})

            if status_proposicao:
                try:
                    projeto_db.data_hora = datetime.fromisoformat(status_proposicao.get("dataHora"))
                    projeto_db.sigla_orgao = status_proposicao.get("siglaOrgao")
                    projeto_db.despacho = status_proposicao.get("despacho")
                    projeto_db.id_ultima_situacao = int(status_proposicao.get("codSituacao"))
                    projeto_db.id_ultima_tramitacao = int(status_proposicao.get("codTipoTramitacao"))
                except (ValueError, TypeError):
                     print(f"WORKER (Projetos): [AVISO] 'statusProposicao' malformado para projeto {id_api}.")
            else:
                print(f"WORKER (Projetos): [AVISO] 'statusProposicao' não encontrado para projeto {id_api}.")

            sequencias_existentes = {t.sequencia for t in projeto_db.tramitacoes}
            url_tram = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_api}/tramitacoes"
            resposta_tram = requests.get(url_tram, timeout=10)
            resposta_tram.raise_for_status()
            tramitacoes_api = resposta_tram.json().get('dados', [])

            novas_tramitacoes_para_salvar = []

            for item_tram_api in tramitacoes_api:
                try:
                    seq_api = int(item_tram_api['sequencia'])
                    
                    if seq_api not in sequencias_existentes:
                        nova_tram = RL_Tramitacoes(
                            id_projeto = id_api,
                            sequencia = seq_api,
                            data_hora = datetime.fromisoformat(item_tram_api['dataHora']),
                            id_situacao = int(item_tram_api['codSituacao']),
                            id_tramitacao = int(item_tram_api['codTipoTramitacao'])
                        )
                        novas_tramitacoes_para_salvar.append(nova_tram)
                        
                except (ValueError, TypeError, KeyError, AttributeError):
                    print(f"WORKER (Projetos): [AVISO] Item de tramitação malformado para projeto {id_api}. Pulando item.")

            if novas_tramitacoes_para_salvar:
                db.session.add_all(novas_tramitacoes_para_salvar)
                novas_tramitacoes_total += len(novas_tramitacoes_para_salvar)

            resposta_tema = requests.get(f'https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_api}/temas', timeout=10)
            resposta_tema.raise_for_status()
            projeto_temas_api = resposta_tema.json().get("dados", [])

            if projeto_temas_api:
                temas_existentes_ids = {tema.id_tema for tema in projeto_db.temas}
                
                for tema_api in projeto_temas_api:
                    try:
                        id_tema_api = int(tema_api.get('cod'))
                        if id_tema_api not in temas_existentes_ids:
                            tema_db = db.session.get(TP_Temas, id_tema_api)
                            if tema_db:
                                projeto_db.temas.append(tema_db)
                            else:
                                print(f"WORKER (Projetos): [AVISO] Tema {id_tema_api} não encontrado no banco local. Pulei.")
                    except (ValueError, TypeError, KeyError, AttributeError):
                        print(f"WORKER (Projetos): [AVISO] Item de tema malformado para projeto {id_api}. Pulando item.")

            db.session.commit()
            if novas_tramitacoes_para_salvar:
                 print(f"WORKER (Projetos): Projeto {id_api} processado. {len(novas_tramitacoes_para_salvar)} novas tramitações salvas.")

        except Exception as e:
            print(f"WORKER (Projetos): [ERRO CRÍTICO] Falha ao processar projeto {id_api}: {e}")
            db.session.rollback()

    print(f"WORKER (Projetos): Sincronização concluída. {projetos_novos} projetos novos, {projetos_atualizados} projetos atualizados, {novas_tramitacoes_total} tramitações novas.")

#Loop do Worker
if __name__ == "__main__":
    if not wait_for_db():
        exit(1)

    while True:
        print(f"\nWORKER (Metadata): {datetime.now()} - Iniciando novo ciclo de sincronização...")
        
        #TP_Situacao
        sicronizar_tabelas_tp(
            url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codSituacao",
            model_class=TP_Situacao,
            id_field_name="id_situacao",
            ds_field_name="ds_situacao",
            api_id_key="cod",
            api_desc_key="nome"
        )
        print("-" * 20)

        #TP_Tramitacao
        sicronizar_tabelas_tp(
            url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTipoTramitacao",
            model_class=TP_Tramitacao,
            id_field_name="id_tramitacao",
            ds_field_name="ds_tramitacao",
            api_id_key="cod",
            api_desc_key="nome"
        )
        print("-" * 20)

        #TP_Temas
        sicronizar_tabelas_tp(
            url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTema",
            model_class=TP_Temas,
            id_field_name="id_tema",
            ds_field_name="ds_tema",
            api_id_key="cod",
            api_desc_key="nome"
        )

        #Projetos
        sicronizar_projetos()

        print(f"\nWORKER: Ciclo completo.")