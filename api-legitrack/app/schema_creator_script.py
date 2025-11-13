from sqlalchemy import create_engine, text

engine = create_engine('postgresql://user:password@db:5432/legitrack_db')

with engine.connect() as conn:
    with conn.begin():
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS camara"))
        print('Schema camara criado!')
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS senado"))
        print('Schema senado criado!')
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS usuarios"))
        print('Schema usuarios criado!')
