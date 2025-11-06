from . import db
from datetime import datetime

#TP
class TP_Situacao(db.Model):
    __tablename__ = 'tp_situacao'
    __table_args__ = {'schema': 'camara'}
    id_situacao = db.Column(db.Integer, primary_key=True, autoincrement=False)
    ds_situacao = db.Column(db.String(255), unique=True, nullable=False)

class TP_Tramitacao(db.Model):
    __tablename__ = 'tp_tramitacao'
    __table_args__ = {'schema': 'camara'}
    id_tramitacao = db.Column(db.Integer, primary_key=True, autoincrement=False)
    ds_tramitacao = db.Column(db.String(255), unique=True, nullable=False)

class TP_Temas(db.Model):
    __tablename__ = 'tp_temas'
    __table_args__ = {'schema': 'camara'}
    id_tema = db.Column(db.Integer, primary_key=True, autoincrement=False)
    ds_tema = db.Column(db.String(255), unique=True, nullable=False)

#TB
class TB_Projeto(db.Model):
    __tablename__ = 'tb_projeto'
    __table_args__ = {'schema': 'camara'}
    
    id_projeto = db.Column(db.Integer, primary_key=True, autoincrement=False)
    titulo_projeto = db.Column(db.String(500))
    descricao = db.Column(db.Text)
    ano_inicio = db.Column(db.Integer)
    data_hora = db.Column(db.DateTime)
    sigla_orgao = db.Column(db.String(100))
    despacho = db.Column(db.Text)
    id_ultima_situacao = db.Column(db.Integer, db.ForeignKey('camara.tp_situacao.id_situacao'))
    id_ultima_tramitacao = db.Column(db.Integer, db.ForeignKey('camara.tp_tramitacao.id_tramitacao'))

    tramitacoes = db.relationship('RL_Tramitacoes', backref='projeto', lazy='dynamic')
    temas = db.relationship('TP_Temas', secondary='camara.rl_temas', lazy='subquery',
                            backref=db.backref('projetos', lazy=True))
    ultima_situacao = db.relationship('TP_Situacao', foreign_keys=[id_ultima_situacao])
    ultima_tramitacao = db.relationship('TP_Tramitacao', foreign_keys=[id_ultima_tramitacao])

class RL_Tramitacoes(db.Model):
    __tablename__ = 'rl_tramitacoes'
    __table_args__ = {'schema': 'camara'}
    
    id_rl_tramitacao = db.Column(db.Integer, primary_key=True)
    id_projeto = db.Column(db.Integer, db.ForeignKey('camara.tb_projeto.id_projeto'), nullable=False)
    sequencia = db.Column(db.Integer, nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)
    id_situacao = db.Column(db.Integer, db.ForeignKey('camara.tp_situacao.id_situacao'), nullable=False)
    id_tramitacao = db.Column(db.Integer, db.ForeignKey('camara.tp_tramitacao.id_tramitacao'), nullable=False)
    
    situacao = db.relationship('TP_Situacao')
    tipo_tramitacao = db.relationship('TP_Tramitacao')

#RL
rel_temas = db.Table('rl_temas',
    db.Column('id_rl_temas', db.Integer, primary_key=True),
    db.Column('id_projeto', db.Integer, db.ForeignKey('camara.tb_projeto.id_projeto')),
    db.Column('id_tema', db.Integer, db.ForeignKey('camara.tp_temas.id_tema')),
    schema='camara'
)