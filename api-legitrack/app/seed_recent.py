import time
import requests
from datetime import datetime
from . import create_app, db
from .models import TP_Situacao, TP_Tramitacao, TP_Temas, TB_Projeto, RL_Tramitacoes, rel_temas
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import text
from urllib.parse import urlparse, parse_qs

app = create_app()
app.app_context().push()

#Espero o DB iniciar
def wait_for_db():
    print("SEEDER: Aguardando o banco de dados ficar pronto...")
    retries = 0
    max_retries = 10
    while retries < max_retries:
        try:
            db.session.execute(text('SELECT 1'))
            print("SEEDER: Conexão com o banco de dados estabelecida!")
            return True
        except OperationalError:
            retries += 1
            wait_time = 5
            print(f"SEEDER: Banco ainda não está pronto. Tentando novamente em {wait_time}s... (Tentativa {retries}/{max_retries})")
            time.sleep(wait_time)
        except Exception as e:
            print(f"SEEDER: Erro inesperado ao esperar pelo banco: {e}")
            retries += 1
            time.sleep(5)
            
    print(f"SEEDER: ERRO CRÍTICO! Não foi possível conectar ao banco após {max_retries} tentativas. Encerrando.")
    return False

#Atualização e Adição de Metadados das Tabelas Tipo 
def sicronizar_tabelas_tp(url, model_class, id_field_name, ds_field_name, api_id_key, api_desc_key):
    tabela_nome = model_class.__tablename__
    print(f"SEEDER: Iniciando sicronização da tabela '{tabela_nome}'...")
    
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        dados_api = resposta.json().get('dados', {})

        if not dados_api:
            print(f"SEEDER: Nenhum dado recebido da API para '{tabela_nome}'. Pulando.")
            return
        
        itens_locais = db.session.scalars(db.select(model_class)).all()
        mapa_itens_locais = {getattr(item, id_field_name): item for item in itens_locais}
        print(f"SEEDER: {len(mapa_itens_locais)} itens existem localmente em '{tabela_nome}'.")

        itens_para_salvar = []
        itens_atualizados = 0
        itens_novos = 0

        #Comparação
        for item_api in dados_api:
            try:
                if not isinstance(item_api, dict):
                    continue

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
                else: #Se não está no banco, insere
                    novo_item_args = {id_field_name: id_api, ds_field_name: desc_api}
                    novo_item = model_class(**novo_item_args)
                    itens_para_salvar.append(novo_item)
                    itens_novos += 1
                
            except (AttributeError, ValueError, TypeError) as e:
                print(f"SEEDER: [AVISO] ERRO em item individual (API enviou lixo? {item_api}). Erro: {e}. Pulando item.")
                continue

        if itens_para_salvar:
            print(f"SEEDER: {itens_novos} itens novos, {itens_atualizados} itens atualizados para '{tabela_nome}'. Salvando...")
            try:
                db.session.add_all(itens_para_salvar)
                db.session.commit()
                print(f"SEEDER: Sincronização de '{tabela_nome}' completa.")
            except Exception as e:
                db.session.rollback()
                print(f"SEEDER: [ERRO] ERRO ao salvar no banco para '{tabela_nome}': {e}")
        else:
            print(f"SEEDER: Tabela '{tabela_nome}' já está atualizada.")

    except requests.exceptions.RequestException as e:
        print(f"SEEDER: [ERRO] ERRO DE REDE GERAL ao buscar '{tabela_nome}': {e}")
    except Exception as e:
        print(f"SEEDER: [ERRO] ERRO INESPERADO (fora do loop) ao sicronizar '{tabela_nome}': {e}")
        db.session.rollback()


#Atualização e Adição de Projetos
def sicronizar_projetos_por_ano(ano_selecionado):
    todos_projetos = []
    MAX_TENTATIVAS_POR_PAGINA = 3
    
    url = (
        f"https://dadosabertos.camara.leg.br/api/v2/proposicoes"
        f"?{ano_selecionado}"
        f"&pagina=1&itens=100&ordem=ASC&ordenarPor=id"
    )

    print(f"SEEDER (Projetos): Iniciando BUSCA COMPLETA (Ano: {ano_selecionado}) de projetos...")

    while url:
        print(f"SEEDER (Projetos): Buscando página: {url}")
        
        resposta = None
        for tentativa in range(MAX_TENTATIVAS_POR_PAGINA):
            try:
                resposta = requests.get(url, timeout=20)
                resposta.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                print(f"SEEDER (Projetos): [ERRO DE REDE] Tentativa {tentativa + 1}/{MAX_TENTATIVAS_POR_PAGINA} falhou: {e}.")
                if tentativa < MAX_TENTATIVAS_POR_PAGINA - 1:
                    time.sleep(5)
                else:
                    print(f"SEEDER (Projetos): [ERRO CRÍTICO] Falha ao buscar página: {e}. Abortando ciclo.")
                    url = None
        
        if not url or not resposta:
            break
            
        dados_api = resposta.json()
        projetos_desta_pagina = dados_api.get('dados', [])
        links_da_api = dados_api.get('links', [])

        if not projetos_desta_pagina:
            print("SEEDER (Projetos): Página sem dados. Concluindo busca.")
            break

        todos_projetos.extend(projetos_desta_pagina)

        novo_url = None
        for link in links_da_api:
            if link.get('rel') == 'next':
                novo_url = link.get('href')
                break

        url = novo_url
        time.sleep(1)
    
    if not todos_projetos:
        print("SEEDER (Projetos): Nenhum projeto encontrado para este período.")
        return

    print(f"SEEDER (Projetos): Paginação concluída. {len(todos_projetos)} projetos (do ano {ano_selecionado}) encontrados para checar/atualizar.")
    
    projetos_atualizados = 0
    projetos_novos = 0
    novas_tramitacoes_total = 0

    for i, projeto_resumido in enumerate(todos_projetos):
        id_api = None
        
        if (i + 1) % 100 == 0:
            print(f"SEEDER (Projetos): Processando... {i+1} / {len(todos_projetos)}")

        try:
            id_api_str = projeto_resumido.get('id')
            if not id_api_str:
                print(f"SEEDER (Projetos): [AVISO] Item de projeto resumido sem ID. Pulando item.")
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
            projeto_db.ano_inicio = int(projeto_resumido.get('ano'))

            sequencias_existentes = {t.sequencia for t in projeto_db.tramitacoes}
            url_tram = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_api}/tramitacoes"
            resposta_tram = requests.get(url_tram, timeout=10)
            resposta_tram.raise_for_status()
            tramitacoes_api = resposta_tram.json().get('dados', [])

            novas_tramitacoes_para_salvar = []
            
            if not tramitacoes_api:
                print(f"SEEDER (Projetos): [AVISO] Projeto {id_api} sem tramitações. Pulando.")
            else:
                for item_tram_api in tramitacoes_api:
                    try:
                        if not isinstance(item_tram_api, dict):
                            continue
                        
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
                        print(f"SEEDER (Projetos): [AVISO] Item de tramitação malformado para projeto {id_api}. Pulando item.")

                if novas_tramitacoes_para_salvar:
                    db.session.add_all(novas_tramitacoes_para_salvar)
                    novas_tramitacoes_total += len(novas_tramitacoes_para_salvar)

                ultimo_status = tramitacoes_api[-1]
                try:
                    projeto_db.data_hora = datetime.fromisoformat(ultimo_status.get("dataHora"))
                    projeto_db.sigla_orgao = ultimo_status.get("siglaOrgao")
                    projeto_db.despacho = ultimo_status.get("despacho")
                    projeto_db.id_ultima_situacao = int(ultimo_status.get("codSituacao"))
                    projeto_db.id_ultima_tramitacao = int(ultimo_status.get("codTipoTramitacao"))
                except (ValueError, TypeError):
                     print(f"SEEDER (Projetos): [AVISO] 'statusProposicao' (da tramitação) malformado para projeto {id_api}.")

            resposta_tema = requests.get(f'https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_api}/temas', timeout=10)
            resposta_tema.raise_for_status()
            projeto_temas_api = resposta_tema.json().get("dados", [])

            if projeto_temas_api:
                temas_existentes_ids = {tema.id_tema for tema in projeto_db.temas}
                
                for tema_api in projeto_temas_api:
                    try:
                        if not isinstance(tema_api, dict):
                           continue
                        
                        id_tema_api = int(tema_api.get('cod'))
                        if id_tema_api not in temas_existentes_ids:
                            tema_db = db.session.get(TP_Temas, id_tema_api)
                            if tema_db:
                                projeto_db.temas.append(tema_db)
                            else:
                                print(f"SEEDER (Projetos): [AVISO] Tema {id_tema_api} não encontrado no banco local. Pulei.")
                    except (ValueError, TypeError, KeyError, AttributeError):
                        print(f"SEEDER (Projetos): [AVISO] Item de tema malformado para projeto {id_api}. Pulando item.")

            db.session.commit()
            
        except Exception as e:
            print(f"SEEDER (Projetos): [ERRO CRÍTICO] Falha ao processar projeto {id_api}: {e}")
            db.session.rollback()

    print(f"\n" + "="*30 + " ESTATÍSTICAS FINAIS " + "="*30)
    print(f"Projetos Novos: {projetos_novos}")
    print(f"Projetos Atualizados: {projetos_atualizados}")
    print(f"Tramitações Adicionadas: {novas_tramitacoes_total}")

#Loop do Worker
if __name__ == "__main__":
    
    if not wait_for_db():
        exit(1)

    print(f"\n--- [SEED SCRIPT]: {datetime.now()} - INICIANDO CARGA INICIAL ---")
    
    print("\n" + "="*30 + " FASE 1: METADADOS (TP) " + "="*30)
    sicronizar_tabelas_tp(
        url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codSituacao",
        model_class=TP_Situacao, id_field_name="id_situacao", ds_field_name="ds_situacao",
        api_id_key="cod", api_desc_key="nome"
    )
    print("-" * 20)
    sicronizar_tabelas_tp(
        url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTipoTramitacao",
        model_class=TP_Tramitacao, id_field_name="id_tramitacao", ds_field_name="ds_tramitacao",
        api_id_key="cod", api_desc_key="nome"
    )
    print("-" * 20)
    sicronizar_tabelas_tp(
        url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTema",
        model_class=TP_Temas, id_field_name="id_tema", ds_field_name="ds_tema",
        api_id_key="cod", api_desc_key="nome"
    )
    
    print("\n" + "="*30 + " FASE 2: PROJETOS (POR ANO) " + "="*30)
    
    try:
        ano_atual = datetime.now().year
        ano_input = input(f"Digite o(s) ano(s) que deseja carregar (ex: 2023, ou 2023,2022,2021): ")
        
        if not ano_input:
            print("Nenhum ano fornecido. Encerrando.")
            exit(0)
            
        print(f"\nSEEDER: Ok! Processando ano(s): {ano_input}...")
        
        # Cria a string de query ?ano=2023&ano=2022
        anos_para_buscar = "&".join([f"ano={ano.strip()}" for ano in ano_input.split(',')])
        
        sicronizar_projetos_por_ano(anos_para_buscar)
        
    except ValueError:
        print("SEEDER: [ERRO] Entrada inválida.")
    except KeyboardInterrupt:
        print("\nSEEDER: Carga interrompida pelo usuário.")
            
    print(f"\n--- [SEED SCRIPT]: CARGA CONCLUÍDA ---")