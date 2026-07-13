from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(120), nullable=False)
    usuario    = db.Column(db.String(60), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.String(20), default='lider')  # admin | lider
    ministerio_id = db.Column(db.Integer, db.ForeignKey('ministerios.id'), nullable=True)

    def set_senha(self, s): self.senha_hash = generate_password_hash(s)
    def check_senha(self, s): return check_password_hash(self.senha_hash, s)

class Membro(db.Model):
    __tablename__ = 'membros'
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(120), nullable=False)
    nasc       = db.Column(db.String(10))
    tel        = db.Column(db.String(30))
    email      = db.Column(db.String(120))
    profissao  = db.Column(db.String(80))
    status     = db.Column(db.String(30), default='Ativo')
    bairro     = db.Column(db.String(80))
    obs        = db.Column(db.Text)
    ministerio_id = db.Column(db.Integer, db.ForeignKey('ministerios.id'), nullable=True)

class Ministerio(db.Model):
    __tablename__ = 'ministerios'
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(100), nullable=False)
    descricao  = db.Column(db.Text)
    cor        = db.Column(db.String(20), default='#e11d2a')
    membros    = db.relationship('Membro', backref='ministerio', lazy=True)
    usuarios   = db.relationship('Usuario', backref='ministerio', lazy=True)

class Evento(db.Model):
    __tablename__ = 'eventos'
    id         = db.Column(db.Integer, primary_key=True)
    titulo     = db.Column(db.String(120), nullable=False)
    data       = db.Column(db.String(10), nullable=False)
    hora       = db.Column(db.String(5))
    local      = db.Column(db.String(120))
    tipo       = db.Column(db.String(30), default='culto')
    descricao  = db.Column(db.Text)

class Musica(db.Model):
    __tablename__ = 'musicas'
    id         = db.Column(db.Integer, primary_key=True)
    titulo     = db.Column(db.String(120), nullable=False)
    artista    = db.Column(db.String(100))
    tom        = db.Column(db.String(5))
    cifra      = db.Column(db.Text)

class Setlist(db.Model):
    __tablename__ = 'setlists'
    id         = db.Column(db.Integer, primary_key=True)
    titulo     = db.Column(db.String(120), nullable=False)
    data       = db.Column(db.String(10))
    hora       = db.Column(db.String(5))
    itens      = db.relationship('SetlistItem', backref='setlist', lazy=True, cascade='all,delete')

class SetlistItem(db.Model):
    __tablename__ = 'setlist_itens'
    id         = db.Column(db.Integer, primary_key=True)
    setlist_id = db.Column(db.Integer, db.ForeignKey('setlists.id'), nullable=False)
    musica_id  = db.Column(db.Integer, db.ForeignKey('musicas.id'), nullable=False)
    ordem      = db.Column(db.Integer, default=0)
    tom        = db.Column(db.String(5))
    musica     = db.relationship('Musica')

class Financeiro(db.Model):
    __tablename__ = 'financeiro'
    id         = db.Column(db.Integer, primary_key=True)
    tipo       = db.Column(db.String(20), nullable=False)  # entrada | saida
    categoria  = db.Column(db.String(60))
    valor      = db.Column(db.Float, nullable=False)
    data       = db.Column(db.String(10), nullable=False)
    descricao  = db.Column(db.Text)
    membro_id  = db.Column(db.Integer, db.ForeignKey('membros.id'), nullable=True)
    forma      = db.Column(db.String(30))
    membro     = db.relationship('Membro')

class MuralPost(db.Model):
    __tablename__ = 'mural'
    id           = db.Column(db.Integer, primary_key=True)
    titulo       = db.Column(db.String(200), nullable=False)
    texto        = db.Column(db.Text)
    imagem       = db.Column(db.Text)
    ministerio_id = db.Column(db.Integer, db.ForeignKey('ministerios.id'), nullable=True)
    autor_id     = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)
    autor        = db.relationship('Usuario')
    ministerio   = db.relationship('Ministerio')
