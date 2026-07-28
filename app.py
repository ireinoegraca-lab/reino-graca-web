import os, base64, io
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Perfil, Config, Usuario, Membro, Ministerio, Evento, Musica, Setlist, SetlistItem, Financeiro, Campanha, CampanhaCotista, MuralPost
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'rg-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///reino.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'

@login_manager.user_loader
def load_user(uid): return Usuario.query.get(int(uid))

def has_perm(p):
    if not current_user.is_authenticated: return False
    if current_user.status != 'ativo': return False
    perms = current_user.get_perms()
    return bool(perms.get(p, False))

def is_admin(): return has_perm('p_usuarios')
def can_manage(mid): return is_admin() or (current_user.is_authenticated and current_user.ministerio_id==mid and has_perm('p_ministerios'))

def serialize_usuario(u):
    return {'id':u.id,'nome':u.nome,'usuario':u.usuario,'role':u.role,'status':u.status or 'ativo',
            'perfil_id':u.perfil_id,'perfil_nome':u.perfil.nome if u.perfil else u.role,
            'ministerio_id':u.ministerio_id,'perms':u.get_perms()}
def serialize_membro(m):
    return {'id':m.id,'nome':m.nome,'nasc':m.nasc or '','tel':m.tel or '','email':m.email or '',
            'profissao':m.profissao or '','status':m.status or 'Ativo','bairro':m.bairro or '',
            'obs':m.obs or '','foto':m.foto or '','ministerio_id':m.ministerio_id}
def serialize_ministerio(c):
    return {'id':c.id,'nome':c.nome,'descricao':c.descricao or '','cor':c.cor or '#e11d2a',
            'membros':[{'id':mb.id,'nome':mb.nome,'status':mb.status} for mb in c.membros]}
def serialize_evento(e):
    return {'id':e.id,'titulo':e.titulo,'data':e.data,'hora':e.hora or '','local':e.local or '','tipo':e.tipo or 'culto','descricao':e.descricao or ''}
def serialize_musica(m):
    return {'id':m.id,'titulo':m.titulo,'artista':m.artista or '','tom':m.tom or '','cifra':m.cifra or ''}
def serialize_setlist(s):
    itens = sorted(s.itens, key=lambda x: x.ordem)
    return {'id':s.id,'titulo':s.titulo,'data':s.data or '','hora':s.hora or '',
            'musicas':[{'id':i.musica_id,'titulo':i.musica.titulo,'artista':i.musica.artista or '','tom':i.tom or i.musica.tom or ''} for i in itens]}
def serialize_fin(f):
    return {'id':f.id,'tipo':f.tipo,'categoria':f.categoria or '','valor':f.valor,'data':f.data,
            'descricao':f.descricao or '','membro_id':f.membro_id,'forma':f.forma or '',
            'campanha_id':f.campanha_id,'campanha_nome':f.campanha.nome if f.campanha else '',
            'membro_nome':f.membro.nome if f.membro else ''}

def serialize_campanha(c):
    arrecadado = db.session.query(db.func.sum(Financeiro.valor)).filter_by(campanha_id=c.id, tipo='entrada').scalar() or 0
    mensal = sum(co.valor_mensal for co in c.cotistas)
    return {'id':c.id,'nome':c.nome,'descricao':c.descricao or '','meta':c.meta or 0,
            'data_inicio':c.data_inicio or '','data_fim':c.data_fim or '','status':c.status or 'ativa',
            'dia_vencimento':c.dia_vencimento,'arrecadado':float(arrecadado),'total_mensal':mensal,
            'cotistas':[{'id':co.id,'membro_id':co.membro_id,'nome':co.membro.nome,
                         'tel':co.membro.tel or '','valor_mensal':co.valor_mensal} for co in c.cotistas]}
def serialize_post(p):
    return {'id':p.id,'titulo':p.titulo,'texto':p.texto or '','imagem':p.imagem or '',
            'ministerio_id':p.ministerio_id,'ministerio_nome':p.ministerio.nome if p.ministerio else 'Geral',
            'autor_nome':p.autor.nome,'criado_em':p.criado_em.isoformat()}

# ── MAIN ──────────────────────────────────────────────────────────
@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html')
    return render_template('index.html')

# ── AUTH ──────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.json
    u = Usuario.query.filter_by(usuario=d.get('usuario','').lower()).first()
    if not u or not u.check_senha(d.get('senha','')):
        return jsonify({'ok':False,'msg':'Usuário ou senha incorretos'}), 401
    if u.status == 'bloqueado':
        return jsonify({'ok':False,'msg':'Conta bloqueada. Fale com o administrador.'}), 403
    if u.status == 'pendente':
        return jsonify({'ok':False,'msg':'Cadastro aguardando aprovação do administrador.'}), 403
    login_user(u, remember=True)
    return jsonify({'ok':True,'user':{'id':u.id,'nome':u.nome,'role':u.role,'status':u.status,
                                      'ministerio_id':u.ministerio_id,'perfil_id':u.perfil_id,'perms':u.get_perms()}})

@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.json or {}
    nome    = (d.get('nome') or '').strip()
    email   = (d.get('email') or '').strip().lower()
    tel     = (d.get('tel') or '').strip()
    nasc    = (d.get('nasc') or '').strip()
    usuario = (d.get('usuario') or '').strip().lower()
    senha   = d.get('senha') or ''
    if not nome or not usuario or not senha:
        return jsonify({'ok':False,'msg':'Nome, usuário e senha são obrigatórios'}), 400
    if Usuario.query.filter_by(usuario=usuario).first():
        return jsonify({'ok':False,'msg':'Usuário já existe. Escolha outro nome de usuário.'}), 409
    perfil_membro = Perfil.query.filter_by(nome='Membro').first()
    u = Usuario(nome=nome, usuario=usuario, role='membro', status='pendente',
                perfil_id=perfil_membro.id if perfil_membro else None)
    u.set_senha(senha)
    db.session.add(u)
    m = Membro(nome=nome, email=email, tel=tel, nasc=nasc or None, status='Ativo')
    db.session.add(m)
    db.session.commit()
    return jsonify({'ok':True,'pendente':True,'msg':'Cadastro enviado! Aguarde a aprovação do administrador.'})

@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'ok':True})

@app.route('/api/me')
def api_me():
    if not current_user.is_authenticated:
        return jsonify({'ok':False}), 401
    u = current_user
    return jsonify({'ok':True,'user':{'id':u.id,'nome':u.nome,'role':u.role,'status':u.status,
                                      'ministerio_id':u.ministerio_id,'perfil_id':u.perfil_id,'perms':u.get_perms()}})

# ── MEMBROS ───────────────────────────────────────────────────────
@app.route('/api/membros')
@login_required
def get_membros():
    return jsonify([serialize_membro(m) for m in Membro.query.order_by(Membro.nome).all()])

@app.route('/api/membros', methods=['POST'])
@login_required
def add_membro():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    m = Membro(nome=d['nome'],nasc=d.get('nasc'),tel=d.get('tel'),email=d.get('email'),
               profissao=d.get('profissao'),status=d.get('status','Ativo'),
               bairro=d.get('bairro'),obs=d.get('obs'),ministerio_id=d.get('ministerio_id'))
    db.session.add(m); db.session.commit()
    return jsonify({'ok':True,'membro':serialize_membro(m)})

@app.route('/api/membros/<int:mid>', methods=['PUT'])
@login_required
def update_membro(mid):
    if not is_admin(): return jsonify({'ok':False}), 403
    m = Membro.query.get_or_404(mid); d = request.json
    for k in ['nome','nasc','tel','email','profissao','status','bairro','obs','foto','ministerio_id']:
        if k in d: setattr(m, k, d[k])
    db.session.commit()
    return jsonify({'ok':True,'membro':serialize_membro(m)})

@app.route('/api/membros/<int:mid>', methods=['DELETE'])
@login_required
def del_membro(mid):
    if not is_admin(): return jsonify({'ok':False}), 403
    m = Membro.query.get_or_404(mid); db.session.delete(m); db.session.commit()
    return jsonify({'ok':True})

# ── MINISTÉRIOS ───────────────────────────────────────────────────
@app.route('/api/ministerios')
@login_required
def get_ministerios():
    return jsonify([serialize_ministerio(c) for c in Ministerio.query.order_by(Ministerio.nome).all()])

@app.route('/api/ministerios', methods=['POST'])
@login_required
def add_ministerio():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    c = Ministerio(nome=d['nome'],descricao=d.get('descricao',''),cor=d.get('cor','#e11d2a'))
    db.session.add(c); db.session.commit()
    return jsonify({'ok':True,'ministerio':serialize_ministerio(c)})

@app.route('/api/ministerios/<int:cid>', methods=['PUT'])
@login_required
def update_ministerio(cid):
    if not can_manage(cid): return jsonify({'ok':False}), 403
    c = Ministerio.query.get_or_404(cid); d = request.json
    for k in ['nome','descricao','cor']:
        if k in d: setattr(c, k, d[k])
    db.session.commit()
    return jsonify({'ok':True,'ministerio':serialize_ministerio(c)})

@app.route('/api/ministerios/<int:cid>', methods=['DELETE'])
@login_required
def del_ministerio(cid):
    if not is_admin(): return jsonify({'ok':False}), 403
    c = Ministerio.query.get_or_404(cid); db.session.delete(c); db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/ministerios/<int:cid>/membros', methods=['POST'])
@login_required
def add_membro_ministerio(cid):
    if not can_manage(cid): return jsonify({'ok':False}), 403
    d = request.json
    m = Membro.query.get_or_404(d['membro_id'])
    m.ministerio_id = cid; db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/ministerios/<int:cid>/membros/<int:mid>', methods=['DELETE'])
@login_required
def rem_membro_ministerio(cid, mid):
    if not can_manage(cid): return jsonify({'ok':False}), 403
    m = Membro.query.get_or_404(mid)
    if m.ministerio_id == cid: m.ministerio_id = None; db.session.commit()
    return jsonify({'ok':True})

# ── AGENDA ────────────────────────────────────────────────────────
@app.route('/api/eventos')
@login_required
def get_eventos():
    return jsonify([serialize_evento(e) for e in Evento.query.order_by(Evento.data).all()])

@app.route('/api/eventos', methods=['POST'])
@login_required
def add_evento():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    e = Evento(titulo=d['titulo'],data=d['data'],hora=d.get('hora'),local=d.get('local'),tipo=d.get('tipo','culto'),descricao=d.get('descricao'))
    db.session.add(e); db.session.commit()
    return jsonify({'ok':True,'evento':serialize_evento(e)})

@app.route('/api/eventos/<int:eid>', methods=['PUT'])
@login_required
def update_evento(eid):
    if not is_admin(): return jsonify({'ok':False}), 403
    e = Evento.query.get_or_404(eid); d = request.json
    for k in ['titulo','data','hora','local','tipo','descricao']:
        if k in d: setattr(e, k, d[k])
    db.session.commit()
    return jsonify({'ok':True,'evento':serialize_evento(e)})

@app.route('/api/eventos/<int:eid>', methods=['DELETE'])
@login_required
def del_evento(eid):
    if not is_admin(): return jsonify({'ok':False}), 403
    e = Evento.query.get_or_404(eid); db.session.delete(e); db.session.commit()
    return jsonify({'ok':True})

# ── LOUVOR ────────────────────────────────────────────────────────
@app.route('/api/musicas')
@login_required
def get_musicas():
    return jsonify([serialize_musica(m) for m in Musica.query.order_by(Musica.titulo).all()])

@app.route('/api/musicas', methods=['POST'])
@login_required
def add_musica():
    d = request.json
    m = Musica(titulo=d['titulo'],artista=d.get('artista'),tom=d.get('tom'),cifra=d.get('cifra'))
    db.session.add(m); db.session.commit()
    return jsonify({'ok':True,'musica':serialize_musica(m)})

@app.route('/api/musicas/<int:mid>', methods=['PUT'])
@login_required
def update_musica(mid):
    m = Musica.query.get_or_404(mid); d = request.json
    for k in ['titulo','artista','tom','cifra']:
        if k in d: setattr(m, k, d[k])
    db.session.commit()
    return jsonify({'ok':True,'musica':serialize_musica(m)})

@app.route('/api/musicas/<int:mid>', methods=['DELETE'])
@login_required
def del_musica(mid):
    m = Musica.query.get_or_404(mid); db.session.delete(m); db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/setlists')
@login_required
def get_setlists():
    return jsonify([serialize_setlist(s) for s in Setlist.query.order_by(Setlist.data).all()])

@app.route('/api/setlists', methods=['POST'])
@login_required
def add_setlist():
    d = request.json
    s = Setlist(titulo=d['titulo'],data=d.get('data'),hora=d.get('hora'))
    db.session.add(s); db.session.flush()
    for i, item in enumerate(d.get('musicas',[])):
        si = SetlistItem(setlist_id=s.id,musica_id=item['id'],ordem=i,tom=item.get('tom',''))
        db.session.add(si)
    db.session.commit()
    return jsonify({'ok':True,'setlist':serialize_setlist(s)})

@app.route('/api/setlists/<int:sid>', methods=['DELETE'])
@login_required
def del_setlist(sid):
    s = Setlist.query.get_or_404(sid); db.session.delete(s); db.session.commit()
    return jsonify({'ok':True})

# ── FINANCEIRO ────────────────────────────────────────────────────
@app.route('/api/financeiro')
@login_required
def get_financeiro():
    if not is_admin(): return jsonify({'ok':False}), 403
    return jsonify([serialize_fin(f) for f in Financeiro.query.order_by(Financeiro.data.desc()).all()])

@app.route('/api/financeiro', methods=['POST'])
@login_required
def add_financeiro():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    f = Financeiro(tipo=d['tipo'],categoria=d.get('categoria'),valor=float(d['valor']),
                   data=d['data'],descricao=d.get('descricao'),membro_id=d.get('membro_id'),
                   forma=d.get('forma'),campanha_id=d.get('campanha_id') or None)
    db.session.add(f); db.session.commit()
    return jsonify({'ok':True,'lancamento':serialize_fin(f)})

@app.route('/api/financeiro/importar', methods=['POST'])
@login_required
def importar_financeiro():
    if not is_admin(): return jsonify({'ok':False}), 403
    if 'arquivo' not in request.files:
        return jsonify({'ok':False,'msg':'Nenhum arquivo enviado'}), 400
    arquivo = request.files['arquivo']
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(arquivo.read()))
        ws = wb.active
        headers = [str(c.value).strip().lower() if c.value else '' for c in ws[1]]
        def col(row, names):
            for n in names:
                if n in headers:
                    v = row[headers.index(n)].value
                    return str(v).strip() if v is not None else ''
            return ''
        importados = 0
        for row in ws.iter_rows(min_row=2):
            valor_raw = col(row, ['valor','value','quantia'])
            data_raw  = col(row, ['data','date','data do lançamento'])
            if not valor_raw or not data_raw: continue
            try: valor = float(str(valor_raw).replace('R$','').replace('.','').replace(',','.').strip())
            except: continue
            tipo = col(row, ['tipo','type']) or 'entrada'
            if tipo.lower() not in ('entrada','saida','saída'): tipo='entrada'
            if tipo.lower() in ('saida','saída'): tipo='saida'
            f = Financeiro(
                tipo=tipo,
                categoria=col(row, ['categoria','category','tipo de entrada']),
                valor=valor,
                data=data_raw[:10],
                descricao=col(row, ['descrição','descricao','description','obs','observação']),
                forma=col(row, ['forma','forma de pagamento','payment','método']) or 'Dinheiro',
            )
            db.session.add(f)
            importados += 1
        db.session.commit()
        return jsonify({'ok':True,'importados':importados})
    except Exception as e:
        return jsonify({'ok':False,'msg':str(e)}), 500

@app.route('/api/financeiro/<int:fid>', methods=['PUT'])
@login_required
def update_financeiro(fid):
    if not is_admin(): return jsonify({'ok':False}), 403
    f = Financeiro.query.get_or_404(fid); d = request.json
    for k in ['tipo','categoria','valor','data','descricao','forma']:
        if k in d: setattr(f, k, float(d[k]) if k=='valor' else d[k])
    if 'campanha_id' in d: f.campanha_id = d['campanha_id'] or None
    db.session.commit()
    return jsonify({'ok':True,'lancamento':serialize_fin(f)})

@app.route('/api/financeiro/<int:fid>', methods=['DELETE'])
@login_required
def del_financeiro(fid):
    if not is_admin(): return jsonify({'ok':False}), 403
    f = Financeiro.query.get_or_404(fid); db.session.delete(f); db.session.commit()
    return jsonify({'ok':True})

# ── CAMPANHAS ────────────────────────────────────────────────────
@app.route('/api/campanhas')
@login_required
def get_campanhas():
    if not has_perm('p_financeiro'): return jsonify({'ok':False}), 403
    return jsonify([serialize_campanha(c) for c in Campanha.query.order_by(Campanha.id.desc()).all()])

@app.route('/api/campanhas', methods=['POST'])
@login_required
def add_campanha():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    dv = d.get('dia_vencimento')
    c = Campanha(nome=d['nome'],descricao=d.get('descricao'),meta=float(d.get('meta') or 0),
                 data_inicio=d.get('data_inicio'),data_fim=d.get('data_fim'),status='ativa',
                 dia_vencimento=int(dv) if dv else None)
    db.session.add(c); db.session.commit()
    return jsonify({'ok':True,'campanha':serialize_campanha(c)})

@app.route('/api/campanhas/<int:cid>', methods=['PUT'])
@login_required
def update_campanha(cid):
    if not is_admin(): return jsonify({'ok':False}), 403
    c = Campanha.query.get_or_404(cid); d = request.json
    for k in ['nome','descricao','data_inicio','data_fim','status']:
        if k in d: setattr(c, k, d[k])
    if 'meta' in d: c.meta = float(d['meta'] or 0)
    if 'dia_vencimento' in d: c.dia_vencimento = int(d['dia_vencimento']) if d['dia_vencimento'] else None
    db.session.commit()
    return jsonify({'ok':True,'campanha':serialize_campanha(c)})

@app.route('/api/campanhas/<int:cid>', methods=['DELETE'])
@login_required
def del_campanha(cid):
    if not is_admin(): return jsonify({'ok':False}), 403
    c = Campanha.query.get_or_404(cid); db.session.delete(c); db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/campanhas/lembretes')
@login_required
def get_lembretes():
    """Retorna cotistas com vencimento nos próximos N dias ou atrasados."""
    if not has_perm('p_financeiro'): return jsonify({'ok':False}), 403
    from datetime import date as dt
    hoje = dt.today()
    dias_aviso = int(request.args.get('dias', 5))
    resultado = []
    for c in Campanha.query.filter_by(status='ativa').all():
        if not c.dia_vencimento: continue
        try:
            import calendar
            ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
            dia = min(c.dia_vencimento, ultimo_dia)
            venc = dt(hoje.year, hoje.month, dia)
        except: continue
        diff = (venc - hoje).days
        if -7 <= diff <= dias_aviso:
            for co in c.cotistas:
                resultado.append({
                    'campanha_id': c.id, 'campanha_nome': c.nome,
                    'membro_id': co.membro_id, 'membro_nome': co.membro.nome,
                    'tel': co.membro.tel or '', 'valor_mensal': co.valor_mensal,
                    'vencimento': venc.isoformat(), 'dias_para_vencer': diff,
                    'status': 'vencido' if diff < 0 else 'hoje' if diff == 0 else 'proximo'
                })
    return jsonify(resultado)

@app.route('/api/campanhas/<int:cid>/cotistas', methods=['POST'])
@login_required
def add_cotista(cid):
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    if CampanhaCotista.query.filter_by(campanha_id=cid, membro_id=d['membro_id']).first():
        return jsonify({'ok':False,'msg':'Membro já é cotista desta campanha'}), 400
    co = CampanhaCotista(campanha_id=cid, membro_id=d['membro_id'], valor_mensal=float(d['valor_mensal']))
    db.session.add(co); db.session.commit()
    c = Campanha.query.get(cid)
    return jsonify({'ok':True,'campanha':serialize_campanha(c)})

@app.route('/api/campanhas/<int:cid>/cotistas/<int:coid>', methods=['DELETE'])
@login_required
def del_cotista(cid, coid):
    if not is_admin(): return jsonify({'ok':False}), 403
    co = CampanhaCotista.query.get_or_404(coid)
    db.session.delete(co); db.session.commit()
    c = Campanha.query.get(cid)
    return jsonify({'ok':True,'campanha':serialize_campanha(c)})

# ── MURAL ─────────────────────────────────────────────────────────
@app.route('/api/mural')
@login_required
def get_mural():
    return jsonify([serialize_post(p) for p in MuralPost.query.order_by(MuralPost.criado_em.desc()).all()])

@app.route('/api/mural', methods=['POST'])
@login_required
def add_post():
    d = request.json
    mid = d.get('ministerio_id')
    if mid and not can_manage(int(mid)): return jsonify({'ok':False}), 403
    p = MuralPost(titulo=d['titulo'],texto=d.get('texto'),imagem=d.get('imagem'),
                  ministerio_id=mid,autor_id=current_user.id)
    db.session.add(p); db.session.commit()
    return jsonify({'ok':True,'post':serialize_post(p)})

@app.route('/api/mural/<int:pid>', methods=['PUT'])
@login_required
def update_post(pid):
    p = MuralPost.query.get_or_404(pid)
    if not is_admin() and p.autor_id != current_user.id: return jsonify({'ok':False}), 403
    d = request.json
    for k in ['titulo','texto','imagem','ministerio_id']:
        if k in d: setattr(p, k, d[k])
    db.session.commit()
    return jsonify({'ok':True,'post':serialize_post(p)})

@app.route('/api/mural/<int:pid>', methods=['DELETE'])
@login_required
def del_post(pid):
    p = MuralPost.query.get_or_404(pid)
    if not is_admin() and p.autor_id != current_user.id: return jsonify({'ok':False}), 403
    db.session.delete(p); db.session.commit()
    return jsonify({'ok':True})

# ── PERFIS ────────────────────────────────────────────────────────
@app.route('/api/perfis')
@login_required
def get_perfis():
    return jsonify([p.to_dict() for p in Perfil.query.order_by(Perfil.id).all()])

@app.route('/api/perfis', methods=['POST'])
@login_required
def add_perfil():
    if not has_perm('p_perfis'): return jsonify({'ok':False}), 403
    d = request.json
    p = Perfil(nome=d['nome'], cor=d.get('cor','#e11d2a'),
               p_membros=d.get('p_membros',False), p_ministerios=d.get('p_ministerios',False),
               p_agenda=d.get('p_agenda',True), p_louvor=d.get('p_louvor',False),
               p_mural=d.get('p_mural',True), p_financeiro=d.get('p_financeiro',False),
               p_usuarios=d.get('p_usuarios',False), p_perfis=d.get('p_perfis',False),
               pode_aprovar=d.get('pode_aprovar',False))
    db.session.add(p); db.session.commit()
    return jsonify({'ok':True,'perfil':p.to_dict()})

@app.route('/api/perfis/<int:pid>', methods=['PUT'])
@login_required
def update_perfil(pid):
    if not has_perm('p_perfis'): return jsonify({'ok':False}), 403
    p = Perfil.query.get_or_404(pid)
    if p.builtin: return jsonify({'ok':False,'msg':'Perfis padrão não podem ser editados'}), 400
    d = request.json
    for k in ['nome','cor','p_membros','p_ministerios','p_agenda','p_louvor','p_mural','p_financeiro','p_usuarios','p_perfis','pode_aprovar']:
        if k in d: setattr(p, k, d[k])
    db.session.commit()
    return jsonify({'ok':True,'perfil':p.to_dict()})

@app.route('/api/perfis/<int:pid>', methods=['DELETE'])
@login_required
def del_perfil(pid):
    if not has_perm('p_perfis'): return jsonify({'ok':False}), 403
    p = Perfil.query.get_or_404(pid)
    if p.builtin: return jsonify({'ok':False,'msg':'Perfis padrão não podem ser excluídos'}), 400
    db.session.delete(p); db.session.commit()
    return jsonify({'ok':True})

# ── USUÁRIOS ──────────────────────────────────────────────────────
@app.route('/api/usuarios')
@login_required
def get_usuarios():
    if not is_admin(): return jsonify({'ok':False}), 403
    return jsonify([serialize_usuario(u) for u in Usuario.query.order_by(Usuario.nome).all()])

@app.route('/api/usuarios/pendentes')
@login_required
def get_pendentes():
    if not (is_admin() or has_perm('pode_aprovar')): return jsonify({'ok':False}), 403
    return jsonify([serialize_usuario(u) for u in Usuario.query.filter_by(status='pendente').all()])

@app.route('/api/usuarios', methods=['POST'])
@login_required
def add_usuario():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json
    if Usuario.query.filter_by(usuario=d['usuario'].lower()).first():
        return jsonify({'ok':False,'msg':'Usuário já existe'}), 400
    u = Usuario(nome=d['nome'], usuario=d['usuario'].lower(), role=d.get('role','membro'),
                status='ativo', perfil_id=d.get('perfil_id'), ministerio_id=d.get('ministerio_id'))
    u.set_senha(d['senha'])
    db.session.add(u); db.session.commit()
    return jsonify({'ok':True,'usuario':serialize_usuario(u)})

@app.route('/api/usuarios/<int:uid>', methods=['PUT'])
@login_required
def update_usuario(uid):
    if not is_admin(): return jsonify({'ok':False}), 403
    u = Usuario.query.get_or_404(uid); d = request.json
    if 'nome' in d: u.nome = d['nome']
    if 'role' in d: u.role = d['role']
    if 'status' in d: u.status = d['status']
    if 'perfil_id' in d: u.perfil_id = d['perfil_id'] or None
    if 'ministerio_id' in d: u.ministerio_id = d['ministerio_id']
    if 'senha' in d and d['senha']: u.set_senha(d['senha'])
    db.session.commit()
    return jsonify({'ok':True,'usuario':serialize_usuario(u)})

@app.route('/api/usuarios/<int:uid>/aprovar', methods=['POST'])
@login_required
def aprovar_usuario(uid):
    if not (is_admin() or has_perm('pode_aprovar')): return jsonify({'ok':False}), 403
    u = Usuario.query.get_or_404(uid)
    u.status = 'ativo'
    if not u.perfil_id:
        perfil = Perfil.query.filter_by(nome='Membro').first()
        if perfil: u.perfil_id = perfil.id
    db.session.commit()
    return jsonify({'ok':True,'usuario':serialize_usuario(u)})

@app.route('/api/usuarios/<int:uid>/bloquear', methods=['POST'])
@login_required
def bloquear_usuario(uid):
    if not is_admin(): return jsonify({'ok':False}), 403
    if uid == current_user.id: return jsonify({'ok':False,'msg':'Não pode bloquear sua própria conta'}), 400
    u = Usuario.query.get_or_404(uid)
    u.status = 'bloqueado' if u.status == 'ativo' else 'ativo'
    db.session.commit()
    return jsonify({'ok':True,'status':u.status})

@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@login_required
def del_usuario(uid):
    if not is_admin(): return jsonify({'ok':False}), 403
    if uid == current_user.id: return jsonify({'ok':False,'msg':'Não pode excluir sua própria conta'}), 400
    u = Usuario.query.get_or_404(uid); db.session.delete(u); db.session.commit()
    return jsonify({'ok':True})

# ── CONFIGURAÇÕES ─────────────────────────────────────────────────
@app.route('/api/config')
@login_required
def get_config():
    rows = Config.query.all()
    return jsonify({r.chave: r.valor for r in rows})

@app.route('/api/config', methods=['PUT'])
@login_required
def save_config():
    if not is_admin(): return jsonify({'ok':False}), 403
    d = request.json or {}
    for chave, valor in d.items():
        c = Config.query.filter_by(chave=chave).first()
        if c: c.valor = valor
        else: db.session.add(Config(chave=chave, valor=valor))
    db.session.commit()
    return jsonify({'ok':True})

# ── IMPORTAR MEMBROS (Excel) ──────────────────────────────────────
@app.route('/api/membros/importar', methods=['POST'])
@login_required
def importar_membros():
    if not is_admin(): return jsonify({'ok':False}), 403
    if 'arquivo' not in request.files:
        return jsonify({'ok':False,'msg':'Nenhum arquivo enviado'}), 400
    arquivo = request.files['arquivo']
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(arquivo.read()))
        ws = wb.active
        headers = [str(c.value).strip().lower() if c.value else '' for c in ws[1]]
        def col(row, names):
            for n in names:
                if n in headers:
                    v = row[headers.index(n)].value
                    return str(v).strip() if v is not None else ''
            return ''
        importados = 0
        for row in ws.iter_rows(min_row=2):
            nome = col(row, ['nome','name'])
            if not nome: continue
            m = Membro(
                nome=nome,
                nasc=col(row, ['nascimento','data de nascimento','nasc','data_nasc','birthday']),
                tel=col(row, ['telefone','tel','phone','celular','whatsapp']),
                email=col(row, ['email','e-mail']),
                profissao=col(row, ['profissão','profissao','profession','ocupação','ocupacao']),
                bairro=col(row, ['bairro','neighborhood','endereco','endereço']),
                status=col(row, ['status']) or 'Ativo',
                obs=col(row, ['observações','observacoes','obs','notas','notes'])
            )
            db.session.add(m)
            importados += 1
        db.session.commit()
        return jsonify({'ok':True,'importados':importados})
    except Exception as e:
        return jsonify({'ok':False,'msg':str(e)}), 500

# ── PORTAL PÚBLICO ────────────────────────────────────────────────
@app.route('/portal')
def portal():
    hoje = date.today().isoformat()
    mes = hoje[5:7]
    membros = Membro.query.order_by(Membro.nome).all()
    musicas = Musica.query.order_by(Musica.titulo).all()
    posts = MuralPost.query.order_by(MuralPost.criado_em.desc()).limit(20).all()
    dados = {
        'codigoAcesso': os.environ.get('PORTAL_CODIGO', 'reino2026'),
        'pinLouvor': os.environ.get('PORTAL_PIN', 'louvor'),
        'onesignalAppId': 'e6cb61e9-ccfd-47a7-aa96-6eff5776b122',
        'mural': [{'id':p.id,'titulo':p.titulo,'texto':p.texto or '','imagem':p.imagem or '',
                   'ministerio':p.ministerio.nome if p.ministerio else 'Geral','autor':p.autor.nome} for p in posts],
        'eventos': [serialize_evento(e) for e in Evento.query.filter(Evento.data >= hoje).order_by(Evento.data).limit(20).all()],
        'membros': [{'nome':m.nome,'nasc':m.nasc or ''} for m in membros if m.nasc],
        'musicas': [{'titulo':m.titulo,'artista':m.artista or '','tom':m.tom or '','cifra':m.cifra or ''} for m in musicas],
        'guia': [],
    }
    return render_template('portal.html', dados=dados)

# ── INIT DB ───────────────────────────────────────────────────────
PERFIS_PADRAO = [
    {'nome':'Pastor',     'cor':'#c9922a','builtin':True,
     'p_membros':True,'p_ministerios':True,'p_agenda':True,'p_louvor':True,'p_mural':True,
     'p_financeiro':True,'p_usuarios':True,'p_perfis':True,'pode_aprovar':True},
    {'nome':'Administrador','cor':'#e11d2a','builtin':True,
     'p_membros':True,'p_ministerios':True,'p_agenda':True,'p_louvor':True,'p_mural':True,
     'p_financeiro':True,'p_usuarios':True,'p_perfis':True,'pode_aprovar':True},
    {'nome':'Secretaria', 'cor':'#60a5fa','builtin':True,
     'p_membros':True,'p_ministerios':True,'p_agenda':True,'p_louvor':False,'p_mural':True,
     'p_financeiro':False,'p_usuarios':False,'p_perfis':False,'pode_aprovar':True},
    {'nome':'Líder',      'cor':'#a78bfa','builtin':True,
     'p_membros':True,'p_ministerios':True,'p_agenda':True,'p_louvor':True,'p_mural':True,
     'p_financeiro':False,'p_usuarios':False,'p_perfis':False,'pode_aprovar':False},
    {'nome':'Tesoureiro', 'cor':'#22c55e','builtin':True,
     'p_membros':False,'p_ministerios':False,'p_agenda':True,'p_louvor':False,'p_mural':True,
     'p_financeiro':True,'p_usuarios':False,'p_perfis':False,'pode_aprovar':False},
    {'nome':'Membro',     'cor':'#9b9296','builtin':True,
     'p_membros':False,'p_ministerios':False,'p_agenda':True,'p_louvor':True,'p_mural':True,
     'p_financeiro':False,'p_usuarios':False,'p_perfis':False,'pode_aprovar':False},
]

def migrate_columns():
    """Adiciona colunas novas em tabelas existentes sem destruir dados."""
    with app.app_context():
        conn = db.engine.connect()
        def add_col(table, col, definition):
            try:
                conn.execute(db.text(f'ALTER TABLE {table} ADD COLUMN {col} {definition}'))
                conn.commit()
                print(f'Coluna {table}.{col} adicionada.')
            except Exception:
                conn.rollback()
        add_col('usuarios',   'status',      "VARCHAR(20) DEFAULT 'ativo'")
        add_col('usuarios',   'perfil_id',   'INTEGER REFERENCES perfis(id)')
        add_col('membros',    'foto',        'TEXT')
        add_col('financeiro', 'campanha_id',      'INTEGER REFERENCES campanhas(id)')
        add_col('campanhas',  'dia_vencimento',   'INTEGER')
        conn.close()

def init_db():
    with app.app_context():
        db.create_all()
        # Migra colunas novas em tabelas existentes
        migrate_columns()
        # Seed perfis padrão
        for pd in PERFIS_PADRAO:
            if not Perfil.query.filter_by(nome=pd['nome']).first():
                db.session.add(Perfil(**pd))
        db.session.commit()
        # Seed config padrão
        configs_padrao = [
            ('whatsapp_secretaria', ''),
            ('nome_pastor', 'Pastor'),
            ('nome_igreja', 'Reino & Graça'),
        ]
        for chave, valor in configs_padrao:
            if not Config.query.filter_by(chave=chave).first():
                db.session.add(Config(chave=chave, valor=valor))
        db.session.commit()
        # Seed usuários iniciais
        if not Usuario.query.first():
            p_admin = Perfil.query.filter_by(nome='Administrador').first()
            admin = Usuario(nome='Administrador', usuario='admin', role='admin', status='ativo',
                            perfil_id=p_admin.id if p_admin else None)
            admin.set_senha('admin123')
            db.session.add(admin)
            dirceu = Usuario(nome='Dirceu Gonçalves', usuario='dirceu', role='admin', status='ativo',
                             perfil_id=p_admin.id if p_admin else None)
            dirceu.set_senha('dirceu123')
            db.session.add(dirceu)
            db.session.commit()
            print('Usuários iniciais criados: admin/admin123 e dirceu/dirceu123')

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5700)
