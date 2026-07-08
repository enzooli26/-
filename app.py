"""
社脉通 - 社会关系网络穿透分析系统
主程序入口
运行方式：python app.py
"""
import os
import sys
from datetime import date, datetime
from functools import wraps
from collections import deque

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, flash
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash



# ── 应用初始化 ──────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'social_network.db')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['SECRET_KEY'] = 'social-network-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'


# ── 数据库模型 ──────────────────────────────────────────────

class User(db.Model, UserMixin):
    """系统用户"""
    __tablename__ = 'users'
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    permission_level = db.Column(db.Integer, nullable=False)  # 1=大众 2=民警 3=管理员
    display_name = db.Column(db.String(50))

    def get_id(self):
        return str(self.uid)


class Person(db.Model):
    """人员"""
    __tablename__ = 'persons'
    pid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    gender = db.Column(db.String(10), nullable=False)
    birthday = db.Column(db.Date)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    id_card = db.Column(db.String(18), unique=True)

    # 关联
    duties = db.relationship('SocialDuty', backref='person', lazy='dynamic',
                             cascade='all, delete-orphan')
    relations_out = db.relationship('SocialRelation', foreign_keys='SocialRelation.person1_id',
                                    backref='person1', lazy='dynamic', cascade='all, delete-orphan')
    relations_in = db.relationship('SocialRelation', foreign_keys='SocialRelation.person2_id',
                                   backref='person2', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'pid': self.pid, 'name': self.name, 'gender': self.gender,
            'birthday': str(self.birthday) if self.birthday else '',
            'phone': self.phone or '', 'email': self.email or '',
            'address': self.address or '', 'id_card': self.id_card or ''
        }


class Organization(db.Model):
    """组织"""
    __tablename__ = 'organizations'
    oid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    type = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200))
    description = db.Column(db.Text)

    duties = db.relationship('SocialDuty', backref='organization', lazy='dynamic',
                             cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'oid': self.oid, 'name': self.name, 'type': self.type,
            'address': self.address or '', 'description': self.description or ''
        }


class SocialRelation(db.Model):
    """社会关系（人员--人员）"""
    __tablename__ = 'social_relations'
    rid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    person1_id = db.Column(db.Integer, db.ForeignKey('persons.pid'), nullable=False, index=True)
    person2_id = db.Column(db.Integer, db.ForeignKey('persons.pid'), nullable=False, index=True)
    relation_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date)
    description = db.Column(db.Text)

    __table_args__ = (
        db.Index('idx_p1_p2', 'person1_id', 'person2_id'),
        db.Index('idx_rel_type', 'relation_type'),
    )

    def to_dict(self):
        p1 = Person.query.get(self.person1_id)
        p2 = Person.query.get(self.person2_id)
        return {
            'rid': self.rid,
            'person1_id': self.person1_id,
            'person1_name': p1.name if p1 else '',
            'person2_id': self.person2_id,
            'person2_name': p2.name if p2 else '',
            'relation_type': self.relation_type,
            'start_date': str(self.start_date) if self.start_date else '',
            'description': self.description or ''
        }


class SocialDuty(db.Model):
    """社会职责（人员--组织）"""
    __tablename__ = 'social_duties'
    did = db.Column(db.Integer, primary_key=True, autoincrement=True)
    person_id = db.Column(db.Integer, db.ForeignKey('persons.pid'), nullable=False, index=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.oid'), nullable=False, index=True)
    position = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    description = db.Column(db.Text)

    def to_dict(self):
        p = Person.query.get(self.person_id)
        o = Organization.query.get(self.org_id)
        return {
            'did': self.did,
            'person_id': self.person_id,
            'person_name': p.name if p else '',
            'org_id': self.org_id,
            'org_name': o.name if o else '',
            'position': self.position,
            'start_date': str(self.start_date) if self.start_date else '',
            'end_date': str(self.end_date) if self.end_date else '',
            'description': self.description or ''
        }


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── 权限装饰器 ──────────────────────────────────────────────

def api_permission_required(level):
    """API权限装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': '请先登录'}), 401
            if current_user.permission_level < level:
                return jsonify({'error': '权限不足'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── 前端页面路由 ────────────────────────────────────────────

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """登录API"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': '用户名或密码错误'}), 401

    login_user(user)
    return jsonify({
        'ok': True,
        'user': {
            'uid': user.uid,
            'username': user.username,
            'display_name': user.display_name or user.username,
            'permission_level': user.permission_level
        }
    })


@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    """注销"""
    logout_user()
    return jsonify({'ok': True})


@app.route('/api/current_user')
def api_current_user():
    """获取当前登录用户信息"""
    if current_user.is_authenticated:
        return jsonify({
            'logged_in': True,
            'user': {
                'uid': current_user.uid,
                'username': current_user.username,
                'display_name': current_user.display_name or current_user.username,
                'permission_level': current_user.permission_level
            }
        })
    return jsonify({'logged_in': False})


# ── 人员管理 API ───────────────────────────────────────────

@app.route('/api/persons')
@login_required
def api_persons_list():
    """获取人员列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()

    q = Person.query
    if search:
        q = q.filter(Person.name.contains(search))
    q = q.order_by(Person.pid)

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'persons': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })


@app.route('/api/persons', methods=['POST'])
@login_required
@api_permission_required(3)
def api_persons_create():
    """添加人员"""
    data = request.get_json()
    try:
        person = Person(
            name=data['name'],
            gender=data.get('gender', ''),
            birthday=date.fromisoformat(data['birthday']) if data.get('birthday') else None,
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            address=data.get('address', ''),
            id_card=data.get('id_card', '')
        )
    except KeyError as e:
        return jsonify({'error': f'缺少必要字段: {e}'}), 400
    db.session.add(person)
    db.session.commit()
    return jsonify({'ok': True, 'person': person.to_dict()})


@app.route('/api/persons/<int:pid>', methods=['PUT'])
@login_required
@api_permission_required(3)
def api_persons_update(pid):
    """更新人员"""
    person = Person.query.get(pid)
    if not person:
        return jsonify({'error': '人员不存在'}), 404
    data = request.get_json()
    person.name = data.get('name', person.name)
    person.gender = data.get('gender', person.gender)
    if data.get('birthday'):
        person.birthday = date.fromisoformat(data['birthday'])
    elif 'birthday' in data and not data['birthday']:
        person.birthday = None
    person.phone = data.get('phone', person.phone)
    person.email = data.get('email', person.email)
    person.address = data.get('address', person.address)
    person.id_card = data.get('id_card', person.id_card)
    db.session.commit()
    return jsonify({'ok': True, 'person': person.to_dict()})


@app.route('/api/persons/<int:pid>', methods=['DELETE'])
@login_required
@api_permission_required(3)
def api_persons_delete(pid):
    """删除人员（级联删除关联关系和职责）"""
    person = Person.query.get(pid)
    if not person:
        return jsonify({'error': '人员不存在'}), 404
    db.session.delete(person)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/persons/all')
@login_required
def api_persons_all():
    """获取所有人员简化列表（用于下拉选择）"""
    persons = Person.query.order_by(Person.name).all()
    return jsonify([{'pid': p.pid, 'name': p.name} for p in persons])


# ── 组织管理 API ───────────────────────────────────────────

@app.route('/api/organizations')
@login_required
def api_orgs_list():
    """获取组织列表"""
    q = Organization.query.order_by(Organization.oid)
    orgs = q.all()
    return jsonify([o.to_dict() for o in orgs])


@app.route('/api/organizations', methods=['POST'])
@login_required
@api_permission_required(3)
def api_orgs_create():
    """添加组织"""
    data = request.get_json()
    org = Organization(
        name=data['name'],
        type=data.get('type', ''),
        address=data.get('address', ''),
        description=data.get('description', '')
    )
    db.session.add(org)
    db.session.commit()
    return jsonify({'ok': True, 'organization': org.to_dict()})


@app.route('/api/organizations/<int:oid>', methods=['PUT'])
@login_required
@api_permission_required(3)
def api_orgs_update(oid):
    """更新组织"""
    org = Organization.query.get(oid)
    if not org:
        return jsonify({'error': '组织不存在'}), 404
    data = request.get_json()
    org.name = data.get('name', org.name)
    org.type = data.get('type', org.type)
    org.address = data.get('address', org.address)
    org.description = data.get('description', org.description)
    db.session.commit()
    return jsonify({'ok': True, 'organization': org.to_dict()})


@app.route('/api/organizations/<int:oid>', methods=['DELETE'])
@login_required
@api_permission_required(3)
def api_orgs_delete(oid):
    """删除组织（级联删除关联职责）"""
    org = Organization.query.get(oid)
    if not org:
        return jsonify({'error': '组织不存在'}), 404
    db.session.delete(org)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/organizations/all')
@login_required
def api_orgs_all():
    """获取所有组织简化列表"""
    orgs = Organization.query.order_by(Organization.name).all()
    return jsonify([{'oid': o.oid, 'name': o.name} for o in orgs])


# ── 社会关系 API ──────────────────────────────────────────

@app.route('/api/relations')
@login_required
@api_permission_required(2)
def api_relations_list():
    """获取关系列表"""
    relations = SocialRelation.query.order_by(SocialRelation.rid.desc()).all()
    return jsonify([r.to_dict() for r in relations])


@app.route('/api/relations', methods=['POST'])
@login_required
@api_permission_required(3)
def api_relations_create():
    """添加关系"""
    data = request.get_json()
    person1_id = data['person1_id']
    person2_id = data['person2_id']
    if person1_id == person2_id:
        return jsonify({'error': '不能为自己添加关系'}), 400
    # 保证 person1_id < person2_id 规范化存储
    if person1_id > person2_id:
        person1_id, person2_id = person2_id, person1_id
    rel = SocialRelation(
        person1_id=person1_id,
        person2_id=person2_id,
        relation_type=data['relation_type'],
        start_date=date.fromisoformat(data['start_date']) if data.get('start_date') else None,
        description=data.get('description', '')
    )
    db.session.add(rel)
    db.session.commit()
    return jsonify({'ok': True, 'relation': rel.to_dict()})


@app.route('/api/relations/<int:rid>', methods=['DELETE'])
@login_required
@api_permission_required(3)
def api_relations_delete(rid):
    """删除关系"""
    rel = SocialRelation.query.get(rid)
    if not rel:
        return jsonify({'error': '关系不存在'}), 404
    db.session.delete(rel)
    db.session.commit()
    return jsonify({'ok': True})


# ── 社会职责 API ──────────────────────────────────────────

@app.route('/api/duties')
@login_required
@api_permission_required(2)
def api_duties_list():
    """获取职责列表"""
    duties = SocialDuty.query.order_by(SocialDuty.did.desc()).all()
    return jsonify([d.to_dict() for d in duties])


@app.route('/api/duties', methods=['POST'])
@login_required
@api_permission_required(3)
def api_duties_create():
    """添加职责"""
    data = request.get_json()
    duty = SocialDuty(
        person_id=data['person_id'],
        org_id=data['org_id'],
        position=data['position'],
        start_date=date.fromisoformat(data['start_date']) if data.get('start_date') else None,
        end_date=date.fromisoformat(data['end_date']) if data.get('end_date') else None,
        description=data.get('description', '')
    )
    db.session.add(duty)
    db.session.commit()
    return jsonify({'ok': True, 'duty': duty.to_dict()})


@app.route('/api/duties/<int:did>', methods=['DELETE'])
@login_required
@api_permission_required(3)
def api_duties_delete(did):
    """删除职责"""
    duty = SocialDuty.query.get(did)
    if not duty:
        return jsonify({'error': '职责不存在'}), 404
    db.session.delete(duty)
    db.session.commit()
    return jsonify({'ok': True})


# ── 网络可视化 API ────────────────────────────────────────

@app.route('/api/network')
def api_network():
    """获取网络图数据（公开接口，无需登录也可查看）"""
    # 节点
    persons = Person.query.all()
    nodes = [{'id': p.pid, 'name': p.name, 'gender': p.gender,
              'category': 0 if p.gender == '男' else 1} for p in persons]

    # 边
    relations = SocialRelation.query.all()
    links = []
    link_set = set()
    for r in relations:
        key = (min(r.person1_id, r.person2_id), max(r.person1_id, r.person2_id))
        if key in link_set:
            continue
        link_set.add(key)
        links.append({
            'source': r.person1_id,
            'target': r.person2_id,
            'label': r.relation_type
        })

    return jsonify({'nodes': nodes, 'links': links})


# ── 关系穿透分析 API ──────────────────────────────────────

@app.route('/api/analyze')
@login_required
@api_permission_required(2)
def api_analyze():
    """关系穿透分析——BFS搜索指定深度内的关系路径"""
    person_a_id = request.args.get('person_a', type=int)
    person_b_id = request.args.get('person_b', type=int)
    max_depth = request.args.get('max_depth', 3, type=int)

    if not person_a_id or not person_b_id:
        return jsonify({'error': '请指定两个人员'}), 400
    if person_a_id == person_b_id:
        return jsonify({'error': '不能分析同一个人'}), 400
    if max_depth < 1 or max_depth > 5:
        return jsonify({'error': '最大层数需在1~5之间'}), 400

    # 构建邻接表
    relations = SocialRelation.query.all()
    adjacency = {}
    name_map = {}
    for r in relations:
        adjacency.setdefault(r.person1_id, []).append((r.person2_id, r.relation_type))
        adjacency.setdefault(r.person2_id, []).append((r.person1_id, r.relation_type))
    for p in Person.query.all():
        name_map[p.pid] = p.name

    if person_a_id not in name_map or person_b_id not in name_map:
        return jsonify({'error': '人员不存在'}), 404

    # BFS
    # 队列元素: (当前节点, 已走路径[(from_id, to_id, relation_type), ...])
    queue = deque()
    queue.append((person_a_id, []))
    visited_at_depth = {}  # {node_id: 首次访问时的深度}
    visited_at_depth[person_a_id] = 0
    found_paths = []

    while queue:
        current, path = queue.popleft()
        current_depth = len(path)

        if current_depth >= max_depth:
            continue

        for neighbor, rel_type in adjacency.get(current, []):
            new_depth = current_depth + 1
            if neighbor in visited_at_depth and visited_at_depth[neighbor] <= new_depth:
                # 已通过更短或相同路径访问过，跳过
                continue

            visited_at_depth[neighbor] = new_depth
            new_path = path + [(current, neighbor, rel_type)]

            if neighbor == person_b_id:
                # 找到目标，构建可读路径
                readable_path = []
                for step in new_path:
                    readable_path.append({
                        'from_id': step[0],
                        'from_name': name_map.get(step[0], ''),
                        'to_id': step[1],
                        'to_name': name_map.get(step[1], ''),
                        'relation_type': step[2]
                    })
                found_paths.append(readable_path)
            elif new_depth < max_depth:
                queue.append((neighbor, new_path))

    person_a_name = name_map.get(person_a_id, '')
    person_b_name = name_map.get(person_b_id, '')

    return jsonify({
        'person_a_id': person_a_id,
        'person_a_name': person_a_name,
        'person_b_id': person_b_id,
        'person_b_name': person_b_name,
        'max_depth': max_depth,
        'path_count': len(found_paths),
        'paths': found_paths
    })


# ── 用户管理 API ──────────────────────────────────────────

@app.route('/api/users')
@login_required
@api_permission_required(3)
def api_users_list():
    """获取用户列表"""
    users = User.query.all()
    return jsonify([{
        'uid': u.uid, 'username': u.username,
        'display_name': u.display_name or u.username,
        'permission_level': u.permission_level
    } for u in users])


@app.route('/api/users', methods=['POST'])
@login_required
@api_permission_required(3)
def api_users_create():
    """创建用户"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 400
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        permission_level=data.get('permission_level', 1),
        display_name=data.get('display_name', username)
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/users/<int:uid>', methods=['DELETE'])
@login_required
@api_permission_required(3)
def api_users_delete(uid):
    """删除用户"""
    if current_user.uid == uid:
        return jsonify({'error': '不能删除自己'}), 400
    user = User.query.get(uid)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({'ok': True})


# ── 初始化数据库 ───────────────────────────────────────────

def init_sample_data():
    """插入示例数据"""
    # 插入用户
    if not User.query.first():
        users = [
            User(username='admin', password_hash=generate_password_hash('admin123'),
                 permission_level=3, display_name='高级管理员'),
            User(username='officer', password_hash=generate_password_hash('123456'),
                 permission_level=2, display_name='王警官'),
            User(username='public', password_hash=generate_password_hash('123456'),
                 permission_level=1, display_name='普通用户'),
        ]
        db.session.add_all(users)

    # 插入人员
    if not Person.query.first():
        persons = [
            Person(name='张三', gender='男', birthday=date(1990, 5, 15),
                   phone='13800001001', email='zhangsan@example.com',
                   address='北京市朝阳区望京SOHO', id_card='110101199005150010'),
            Person(name='李四', gender='男', birthday=date(1988, 8, 22),
                   phone='13800001002', email='lisi@example.com',
                   address='北京市海淀区中关村大街1号', id_card='110108198808220020'),
            Person(name='王五', gender='女', birthday=date(1992, 3, 10),
                   phone='13800001003', email='wangwu@example.com',
                   address='北京市朝阳区望京SOHO', id_card='110101199203100030'),
            Person(name='赵六', gender='男', birthday=date(1985, 11, 30),
                   phone='13800001004', email='zhaoliu@example.com',
                   address='北京市海淀区中关村大街2号', id_card='110108198511300040'),
            Person(name='孙七', gender='女', birthday=date(1995, 7, 18),
                   phone='13800001005', email='sunqi@example.com',
                   address='北京市西城区金融街15号', id_card='110102199507180050'),
            Person(name='周八', gender='男', birthday=date(1987, 1, 5),
                   phone='13800001006', email='zhouba@example.com',
                   address='北京市丰台区科技园A座', id_card='110106198701050060'),
            Person(name='吴九', gender='女', birthday=date(1993, 12, 25),
                   phone='13800001007', email='wujiu@example.com',
                   address='北京市朝阳区国贸大厦', id_card='110101199312250070'),
            Person(name='郑十', gender='男', birthday=date(1989, 9, 9),
                   phone='13800001008', email='zhengshi@example.com',
                   address='北京市海淀区五道口', id_card='110108198909090080'),
        ]
        db.session.add_all(persons)
        db.session.flush()

        # 组织
        orgs = [
            Organization(name='望京科技有限公司', type='企业',
                        address='北京市朝阳区望京SOHO T1', description='一家互联网科技公司'),
            Organization(name='中关村研究院', type='事业单位',
                        address='北京市海淀区中关村大街1号', description='科研机构'),
            Organization(name='金融街管理委员会', type='政府机构',
                        address='北京市西城区金融街15号', description='政府部门'),
        ]
        db.session.add_all(orgs)
        db.session.flush()

        # 社会关系
        p_dict = {p.name: p.pid for p in Person.query.all()}
        relations = [
            SocialRelation(person1_id=p_dict['张三'], person2_id=p_dict['李四'],
                          relation_type='同事', description='同在中关村研究院工作'),
            SocialRelation(person1_id=p_dict['张三'], person2_id=p_dict['王五'],
                          relation_type='配偶', description='夫妻关系'),
            SocialRelation(person1_id=p_dict['李四'], person2_id=p_dict['赵六'],
                          relation_type='大学同学', description='清华大学计算机系同学'),
            SocialRelation(person1_id=p_dict['王五'], person2_id=p_dict['吴九'],
                          relation_type='闺蜜', description='关系密切的朋友'),
            SocialRelation(person1_id=p_dict['赵六'], person2_id=p_dict['孙七'],
                          relation_type='同事', description='同在望京科技工作'),
            SocialRelation(person1_id=p_dict['赵六'], person2_id=p_dict['周八'],
                          relation_type='亲戚', description='表兄弟关系'),
            SocialRelation(person1_id=p_dict['孙七'], person2_id=p_dict['吴九'],
                          relation_type='大学同学', description='北京大学校友'),
            SocialRelation(person1_id=p_dict['周八'], person2_id=p_dict['郑十'],
                          relation_type='朋友', description='多年的好友'),
            SocialRelation(person1_id=p_dict['郑十'], person2_id=p_dict['李四'],
                          relation_type='前同事', description='曾一起在望京科技工作'),
        ]
        db.session.add_all(relations)
        db.session.flush()

        # 社会职责
        o_dict = {o.name: o.oid for o in Organization.query.all()}
        duties = [
            SocialDuty(person_id=p_dict['张三'], org_id=o_dict['中关村研究院'],
                      position='研究员', start_date=date(2018, 7, 1),
                      description='从事人工智能方向研究'),
            SocialDuty(person_id=p_dict['李四'], org_id=o_dict['中关村研究院'],
                      position='高级研究员', start_date=date(2016, 3, 1),
                      description='大数据分析方向'),
            SocialDuty(person_id=p_dict['王五'], org_id=o_dict['望京科技有限公司'],
                      position='产品经理', start_date=date(2020, 1, 1),
                      description='负责核心产品线'),
            SocialDuty(person_id=p_dict['赵六'], org_id=o_dict['望京科技有限公司'],
                      position='技术总监', start_date=date(2019, 6, 1),
                      description='管理技术团队'),
            SocialDuty(person_id=p_dict['孙七'], org_id=o_dict['金融街管理委员会'],
                      position='行政主管', start_date=date(2021, 4, 1),
                      description='负责行政审批工作'),
            SocialDuty(person_id=p_dict['周八'], org_id=o_dict['望京科技有限公司'],
                      position='高级工程师', start_date=date(2020, 8, 1),
                      description='后端开发'),
            SocialDuty(person_id=p_dict['吴九'], org_id=o_dict['中关村研究院'],
                      position='助理研究员', start_date=date(2022, 9, 1),
                      description='数据采集与分析'),
            SocialDuty(person_id=p_dict['郑十'], org_id=o_dict['金融街管理委员会'],
                      position='信息管理员', start_date=date(2019, 1, 1),
                      description='IT支持与系统维护'),
        ]
        db.session.add_all(duties)

    db.session.commit()


# ── 启动入口 ────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_sample_data()
        print('=' * 50)
        print('  社脉通 - 社会关系网络穿透分析系统')
        print('  默认账户:')
        print('    管理员: admin / admin123')
        print('    民警:   officer / 123456')
        print('    大众:   public / 123456')
        print('  访问地址: http://127.0.0.1:5000')
        print('=' * 50)
    app.run(host='127.0.0.1', port=5000, debug=True)
