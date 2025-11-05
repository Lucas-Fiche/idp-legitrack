import time
import requests
from datetime import datetime
from . import create_app, db
from .models import TP_Situacao, TP_Tramitacao, TP_Temas
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
def sicronizar_tabelas_tp(url, model_class, id_field_name, ds_field_name,):
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
            if not isinstance(item_api, dict):
                print("WORKER: Item da API malformado (não é um dicionário, talvez 'None'?). Pulando.")
                continue

            id_api_str = item_api.get('cod')
            desc_api = item_api.get('nome')

            if not id_api or not desc_api:
                continue

            try:
                id_api = int(id_api_str)
            except (ValueError, TypeError):
                print(f"WORKER: ID da API inválido ou não-numérico: {id_api_str}. Pulando.")
                continue

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

        if itens_para_salvar:
            print(f"WORKER: {itens_novos} itens novos, {itens_atualizados} itens atualizados para '{tabela_nome}'. Salvando...")
            try:
                db.session.add_all(itens_para_salvar)
                db.session.commit()
                print(f"WORKER: Sincronização de '{tabela_nome}' completa.")
            except Exception as e:
                db.session.rollback()
                print(f"WORKER: ERRO ao salvar no banco para '{tabela_nome}': {e}")
        else:
            print(f"WORKER: Tabela '{tabela_nome}' já está atualizada.")

    except requests.exceptions.RequestException as e:
        print(f"WORKER: ERRO DE REDE ao buscar '{tabela_nome}': {e}")
    except Exception as e:
        print(f"WORKER: ERRO INESPERADO ao sicronizar '{tabela_nome}': {e}")
        db.session.rollback()

#Loop do Worker
if __name__ == "__main__":
    TEMPO_DE_ESPERA = 60 * 15 #15 minutos

    if not wait_for_db():
        exit(1)

    while True:
        print(f"\nWORKER TP: {datetime.now()} - Iniciando novo ciclo de sincronização...")

        #TP_Situacao
        sicronizar_tabelas_tp(
            url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codSituacao",
            model_class=TP_Situacao,
            id_field_name="id_situacao",
            ds_field_name="ds_situacao"
        )
        print("-" * 20)

        #TP_Tramitacao
        sicronizar_tabelas_tp(
            url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTipoTramitacao",
            model_class=TP_Tramitacao,
            id_field_name="id_tramitacao",
            ds_field_name="ds_tramitacao"
        )
        print("-" * 20)

        #TP_Temas
        sicronizar_tabelas_tp(
            url="https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/codTema",
            model_class=TP_Temas,
            id_field_name="id_tema",
            ds_field_name="ds_tema"
        )

        #Espera
        print(f"\nWORKER (Metadata): Ciclo completo. Dormindo por {TEMPO_DE_ESPERA / 60} minutos...")
        time.sleep(TEMPO_DE_ESPERA)