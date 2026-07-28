from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Perfil(db.Model):
    __tablename__ = 'perfis'
    id            = db.Column(db.Integer, primary_key=True)
    nome          = db.Column(db.String(60), nullable=False)
    cor           = db.Column(db.String(7), default='#e11d2a')
    builtin       = db.Column(db.Boolean, default=False)
    p_membros     = db.Column(db.Boolean, default=False)
    p_ministerios = db.Column(db.Boolean, default=False)
    p_agenda      = db.Column(db.Boolean, default=True)
    p_louvor      = db.Column(db.Boolean, default=False)
    p_mural       = db.Column(db.Boolean, default=True)
    p_financeiro  = db.Column(db.Boolean, default=False)
    p_usuarios    = db.Column(db.Boolean, default=False)
    p_perfis      = db.Column(db.Boolean, default=False)
    pode_aprovar  = db.Column(db.Boolean, default=False)
    usuarios      = db.relationship('Usuario', backref='perfil', lazy=True)

    def to_dict(self):
        return {'id':self.id,'nome':self.nome,'cor':self.cor,'builtin':self.builtin,
                'p_membros':self.p_membros,'p_ministerios':self.p_ministerios,
                'p_agenda':self.p_agenda,'p_louvor':self.p_louvor,'p_mural':self.p_mural,
                'p_financeiro':self.p_financeiro,'p_usuarios':self.p_usuarios,
                'p_perfis':self.p_perfis,'pode_aprovar':self.pode_aprovar}

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id            = db.Column(db.Integer, primary_key=True)
    nome          = db.Column(db.String(120), nullable=False)
    usuario       = db.Column(db.String(60), unique=True, nullable=False)
    senha_hash    = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default='membro')
    status        = db.Column(db.String(20), default='ativo')   # ativo | pendente | bloqueado
    perfil_id     = db.Column(db.Integer, db.ForeignKey('perfis.id'), nullable=True)
    ministerio_id       = db.Column(db.Integer, db.ForeignKey('ministerios.id'), nullable=True)
    ultima_confirmacao  = db.Column(db.String(10))   # YYYY-MM-DD

    def set_senha(self, s): self.senha_hash = generate_password_hash(s)
    def check_senha(self, s): return check_password_hash(self.senha_hash, s)

    def get_perms(self):
        if self.perfil:
            return self.perfil.to_dict()
        # fallback para role legado
        full = dict(p_membros=True,p_ministerios=True,p_agenda=True,p_louvor=True,
                    p_mural=True,p_financeiro=True,p_usuarios=True,p_perfis=True,pode_aprovar=True)
        membro = dict(p_membros=False,p_ministerios=False,p_agenda=True,p_louvor=True,
                      p_mural=True,p_financeiro=False,p_usuarios=False,p_perfis=False,pode_aprovar=False)
        return full if self.role in ('admin','pastor') else membro

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
    foto       = db.Column(db.Text)
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

class Campanha(db.Model):
    __tablename__ = 'campanhas'
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(120), nullable=False)
    descricao   = db.Column(db.Text)
    meta        = db.Column(db.Float, default=0)
    data_inicio = db.Column(db.String(10))
    data_fim    = db.Column(db.String(10))
    status          = db.Column(db.String(20), default='ativa')
    dia_vencimento  = db.Column(db.Integer)   # dia do mês (1-28)
    cotistas        = db.relationship('CampanhaCotista', backref='campanha', lazy=True, cascade='all,delete')

class CampanhaCotista(db.Model):
    __tablename__ = 'campanha_cotistas'
    id           = db.Column(db.Integer, primary_key=True)
    campanha_id  = db.Column(db.Integer, db.ForeignKey('campanhas.id'), nullable=False)
    membro_id    = db.Column(db.Integer, db.ForeignKey('membros.id'), nullable=False)
    valor_mensal = db.Column(db.Float, nullable=False)
    membro       = db.relationship('Membro')

class Financeiro(db.Model):
    __tablename__ = 'financeiro'
    id          = db.Column(db.Integer, primary_key=True)
    tipo        = db.Column(db.String(20), nullable=False)
    categoria   = db.Column(db.String(60))
    valor       = db.Column(db.Float, nullable=False)
    data        = db.Column(db.String(10), nullable=False)
    descricao   = db.Column(db.Text)
    membro_id   = db.Column(db.Integer, db.ForeignKey('membros.id'), nullable=True)
    forma       = db.Column(db.String(30))
    campanha_id = db.Column(db.Integer, db.ForeignKey('campanhas.id'), nullable=True)
    membro      = db.relationship('Membro')
    campanha    = db.relationship('Campanha', foreign_keys=[campanha_id])

class Config(db.Model):
    __tablename__ = 'config'
    id    = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(60), unique=True, nullable=False)
    valor = db.Column(db.Text)

class PedidoOracao(db.Model):
    __tablename__ = 'pedidos_oracao'
    id               = db.Column(db.Integer, primary_key=True)
    texto            = db.Column(db.Text, nullable=False)
    nome_solicitante = db.Column(db.String(120))   # null = anônimo
    membro_id        = db.Column(db.Integer, db.ForeignKey('membros.id'), nullable=True)
    privado          = db.Column(db.Boolean, default=False)
    status           = db.Column(db.String(20), default='aberto')  # aberto | orado | encerrado
    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)
    membro           = db.relationship('Membro')

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
