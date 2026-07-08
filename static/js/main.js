
const API = {
    async get(url) {
        const res = await fetch(url, { credentials: 'same-origin' });
        return res.json();
    },
    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin', body: JSON.stringify(data)
        });
        return res.json();
    },
    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin', body: JSON.stringify(data)
        });
        return res.json();
    },
    async del(url) {
        const res = await fetch(url, { method: 'DELETE', credentials: 'same-origin' });
        return res.json();
    }
};

// ── 全局状态 ──
const state = {
    user: null,
    persons: [], orgs: [], relations: [], duties: []
};

// ── 工具函数 ──
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function toast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = `toast ${type}`; t.textContent = msg; document.body.appendChild(t);
    setTimeout(() => t.classList.add('show'), 10);
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 2500);
}

// ── 登录 ──
async function handleLogin() {
    const username = $('#login-username').value.trim();
    const password = $('#login-password').value;
    if (!username || !password) { toast('请输入用户名和密码', 'error'); return; }
    const res = await API.post('/api/login', { username, password });
    if (res.error) { toast(res.error, 'error'); return; }
    state.user = res.user;
    $('#login-overlay').style.display = 'none';
    $('#app-layout').style.display = 'flex';
    initApp();
}

// ── 主框架初始化 ──
function initApp() {
    updateUserDisplay();
    switchPanel('dashboard');
    loadDashboard();
}

function updateUserDisplay() {
    if (!state.user) return;
    const badges = { 3: 'badge-admin', 2: 'badge-officer', 1: 'badge-public' };
    const labels = { 3: '管理员', 2: '民警', 1: '普通用户' };
    $('#user-name').textContent = state.user.display_name;
    const badge = $('#user-badge');
    badge.textContent = labels[state.user.permission_level];
    badge.className = 'badge ' + (badges[state.user.permission_level] || 'badge-public');

    const isAdmin = state.user.permission_level >= 3;
    // 控制导航显示
    $$('.nav-item').forEach(el => {
        const minPerm = parseInt(el.dataset.permission || '1');
        el.style.display = state.user.permission_level >= minPerm ? 'flex' : 'none';
    });
    // 控制操作按钮显隐
    const adminBtns = ['btn-add-person', 'btn-add-org', 'btn-add-relation', 'btn-add-duty'];
    adminBtns.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.style.display = isAdmin ? 'inline-flex' : 'none';
    });
}

// ── 导航切换 ──
function switchPanel(name) {
    $$('.panel').forEach(p => p.classList.remove('active'));
    $$('.nav-item').forEach(a => a.classList.remove('active'));
    $(`#panel-${name}`).classList.add('active');
    $(`#nav-${name}`).classList.add('active');

    const titles = {
        dashboard: '系统仪表板', persons: '人员管理', organizations: '组织管理',
        relations: '社会关系管理', duties: '社会职责管理',
        network: '关系网络可视化', analyze: '关系穿透分析',
        users: '用户管理'
    };
    $('#page-title').textContent = titles[name] || name;

    // 自动加载数据
    const loaders = {
        dashboard: loadDashboard, persons: loadPersons,
        organizations: loadOrgs, relations: loadRelations,
        duties: loadDuties, network: loadNetwork,
        analyze: initAnalyze, users: loadUsers
    };
    if (loaders[name]) loaders[name]();
}

// ── 仪表板 ──
async function loadDashboard() {
    const [pRes, oRes, rRes, dRes] = await Promise.all([
        API.get('/api/persons?per_page=1'), API.get('/api/organizations'),
        API.get('/api/relations'), API.get('/api/duties')
    ]);
    $('#stat-persons').textContent = pRes.total || 0;
    $('#stat-orgs').textContent = (oRes && oRes.length) || 0;
    $('#stat-relations').textContent = (rRes && rRes.length) || 0;
    $('#stat-duties').textContent = (dRes && dRes.length) || 0;
}

// ── 人员管理 ──
let personPage = 1, personTotalPages = 1;

async function loadPersons(page = 1) {
    personPage = page;
    const search = $('#person-search')?.value || '';
    const res = await API.get(`/api/persons?page=${page}&per_page=15&search=${encodeURIComponent(search)}`);
    if (res.error) { toast(res.error, 'error'); return; }
    state.persons = res.persons;
    personTotalPages = res.pages;

    let html = '';
    res.persons.forEach(p => {
        html += `<tr>
            <td>${p.pid}</td><td>${escapeHtml(p.name)}</td><td>${p.gender}</td>
            <td>${p.phone}</td><td>${p.email}</td>
            <td class="actions">
                <button class="btn btn-outline btn-sm" onclick="editPerson(${p.pid})">编辑</button>
                ${state.user.permission_level >= 3 ? `<button class="btn btn-danger btn-sm" onclick="deletePerson(${p.pid}, '${escapeHtml(p.name)}')">删除</button>` : ''}
            </td></tr>`;
    });
    $('#person-table-body').innerHTML = html || '<tr><td colspan="6" class="empty-state">暂无数据</td></tr>';

    // 分页
    let pgHtml = `<button ${personPage <= 1 ? 'disabled' : ''} onclick="loadPersons(${personPage - 1})">上一页</button>`;
    for (let i = 1; i <= personTotalPages; i++) {
        pgHtml += `<button class="${i === personPage ? 'active' : ''}" onclick="loadPersons(${i})">${i}</button>`;
    }
    pgHtml += `<button ${personPage >= personTotalPages ? 'disabled' : ''} onclick="loadPersons(${personPage + 1})">下一页</button>`;
    $('#person-pagination').innerHTML = pgHtml;
}

async function deletePerson(pid, name) {
    if (!confirm(`确定删除 "${name}" 吗？其关联关系和职责也将一并删除。`)) return;
    const res = await API.del(`/api/persons/${pid}`);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('删除成功', 'success');
    loadPersons(personPage);
}

function showPersonModal() { $('#person-modal').classList.add('show'); $('#person-form').reset(); $('#person-pid').value = ''; }
function hidePersonModal() { $('#person-modal').classList.remove('show'); }

async function editPerson(pid) {
    const p = state.persons.find(x => x.pid === pid) || (await API.get(`/api/persons?page=1&per_page=100`)).persons.find(x => x.pid === pid);
    if (!p) return;
    $('#person-pid').value = p.pid;
    $('#person-name').value = p.name;
    $('#person-gender').value = p.gender;
    $('#person-birthday').value = p.birthday;
    $('#person-phone').value = p.phone;
    $('#person-email').value = p.email;
    $('#person-address').value = p.address;
    $('#person-idcard').value = p.id_card;
    $('#person-modal').classList.add('show');
}

async function savePerson() {
    const data = {
        name: $('#person-name').value.trim(),
        gender: $('#person-gender').value,
        birthday: $('#person-birthday').value,
        phone: $('#person-phone').value.trim(),
        email: $('#person-email').value.trim(),
        address: $('#person-address').value.trim(),
        id_card: $('#person-idcard').value.trim()
    };
    if (!data.name) { toast('请输入姓名', 'error'); return; }
    const pid = $('#person-pid').value;
    const res = pid
        ? await API.put(`/api/persons/${pid}`, data)
        : await API.post('/api/persons', data);
    if (res.error) { toast(res.error, 'error'); return; }
    toast(pid ? '更新成功' : '添加成功', 'success');
    hidePersonModal();
    loadPersons(personPage);
}

// ── 组织管理 ──
async function loadOrgs() {
    const res = await API.get('/api/organizations');
    state.orgs = Array.isArray(res) ? res : [];
    let html = '';
    state.orgs.forEach(o => {
        html += `<tr>
            <td>${o.oid}</td><td>${escapeHtml(o.name)}</td><td>${o.type}</td>
            <td>${o.address}</td><td>${(o.description || '').substring(0, 30)}</td>
            <td class="actions">
                <button class="btn btn-outline btn-sm" onclick="editOrg(${o.oid})">编辑</button>
                ${state.user.permission_level >= 3 ? `<button class="btn btn-danger btn-sm" onclick="deleteOrg(${o.oid}, '${escapeHtml(o.name)}')">删除</button>` : ''}
            </td></tr>`;
    });
    $('#org-table-body').innerHTML = html || '<tr><td colspan="6" class="empty-state">暂无数据</td></tr>';
}

async function deleteOrg(oid, name) {
    if (!confirm(`确定删除组织 "${name}" 吗？`)) return;
    const res = await API.del(`/api/organizations/${oid}`);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('删除成功', 'success');
    loadOrgs();
}

function showOrgModal() { $('#org-modal').classList.add('show'); $('#org-form').reset(); $('#org-oid').value = ''; }
function hideOrgModal() { $('#org-modal').classList.remove('show'); }

async function editOrg(oid) {
    const o = state.orgs.find(x => x.oid === oid);
    if (!o) return;
    $('#org-oid').value = o.oid;
    $('#org-name').value = o.name;
    $('#org-type').value = o.type;
    $('#org-address').value = o.address;
    $('#org-description').value = o.description;
    $('#org-modal').classList.add('show');
}

async function saveOrg() {
    const data = {
        name: $('#org-name').value.trim(),
        type: $('#org-type').value.trim(),
        address: $('#org-address').value.trim(),
        description: $('#org-description').value.trim()
    };
    if (!data.name) { toast('请输入组织名称', 'error'); return; }
    const oid = $('#org-oid').value;
    const res = oid
        ? await API.put(`/api/organizations/${oid}`, data)
        : await API.post('/api/organizations', data);
    if (res.error) { toast(res.error, 'error'); return; }
    toast(oid ? '更新成功' : '添加成功', 'success');
    hideOrgModal();
    loadOrgs();
}

// ── 社会关系管理 ──
async function loadRelations() {
    if (state.user.permission_level < 2) {
        $('#relation-table-body').innerHTML = '<tr><td colspan="6" class="empty-state">需要民警及以上权限</td></tr>';
        return;
    }
    const res = await API.get('/api/relations');
    state.relations = Array.isArray(res) ? res : [];
    let html = '';
    state.relations.forEach(r => {
        html += `<tr>
            <td>${r.rid}</td><td>${escapeHtml(r.person1_name)}</td><td>${escapeHtml(r.person2_name)}</td>
            <td>${r.relation_type}</td><td>${r.description || ''}</td>
            <td class="actions">
                ${state.user.permission_level >= 3 ? `<button class="btn btn-danger btn-sm" onclick="deleteRelation(${r.rid})">删除</button>` : ''}
            </td></tr>`;
    });
    $('#relation-table-body').innerHTML = html || '<tr><td colspan="6" class="empty-state">暂无数据</td></tr>';
}

async function deleteRelation(rid) {
    if (!confirm('确定删除此关系？')) return;
    const res = await API.del(`/api/relations/${rid}`);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('删除成功', 'success');
    loadRelations();
}

async function showRelationModal() {
    $('#relation-modal').classList.add('show');
    $('#relation-form').reset();
    const res = await API.get('/api/persons/all');
    const persons = Array.isArray(res) ? res : [];
    let opts = '';
    persons.forEach(p => opts += `<option value="${p.pid}">${escapeHtml(p.name)}</option>`);
    $('#rel-person1').innerHTML = opts;
    $('#rel-person2').innerHTML = opts;
}
function hideRelationModal() { $('#relation-modal').classList.remove('show'); }

async function saveRelation() {
    const p1 = parseInt($('#rel-person1').value);
    const p2 = parseInt($('#rel-person2').value);
    const data = {
        person1_id: p1, person2_id: p2,
        relation_type: $('#rel-type').value.trim(),
        start_date: $('#rel-start').value,
        description: $('#rel-desc').value.trim()
    };
    if (!data.relation_type) { toast('请输入关系类型', 'error'); return; }
    if (p1 === p2) { toast('不能为自己添加关系', 'error'); return; }
    const res = await API.post('/api/relations', data);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('添加成功', 'success');
    hideRelationModal();
    loadRelations();
}

// ── 社会职责管理 ──
async function loadDuties() {
    if (state.user.permission_level < 2) {
        $('#duty-table-body').innerHTML = '<tr><td colspan="7" class="empty-state">需要民警及以上权限</td></tr>';
        return;
    }
    const res = await API.get('/api/duties');
    state.duties = Array.isArray(res) ? res : [];
    let html = '';
    state.duties.forEach(d => {
        html += `<tr>
            <td>${d.did}</td><td>${escapeHtml(d.person_name)}</td><td>${escapeHtml(d.org_name)}</td>
            <td>${d.position}</td><td>${d.start_date}</td><td>${d.end_date || '至今'}</td>
            <td class="actions">
                ${state.user.permission_level >= 3 ? `<button class="btn btn-danger btn-sm" onclick="deleteDuty(${d.did})">删除</button>` : ''}
            </td></tr>`;
    });
    $('#duty-table-body').innerHTML = html || '<tr><td colspan="7" class="empty-state">暂无数据</td></tr>';
}

async function deleteDuty(did) {
    if (!confirm('确定删除此职责？')) return;
    const res = await API.del(`/api/duties/${did}`);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('删除成功', 'success');
    loadDuties();
}

async function showDutyModal() {
    $('#duty-modal').classList.add('show');
    $('#duty-form').reset();
    const [pRes, oRes] = await Promise.all([API.get('/api/persons/all'), API.get('/api/organizations/all')]);
    const persons = Array.isArray(pRes) ? pRes : [];
    const orgs = Array.isArray(oRes) ? oRes : [];
    let pOpts = '', oOpts = '';
    persons.forEach(p => pOpts += `<option value="${p.pid}">${escapeHtml(p.name)}</option>`);
    orgs.forEach(o => oOpts += `<option value="${o.oid}">${escapeHtml(o.name)}</option>`);
    $('#duty-person').innerHTML = pOpts;
    $('#duty-org').innerHTML = oOpts;
}
function hideDutyModal() { $('#duty-modal').classList.remove('show'); }

async function saveDuty() {
    const data = {
        person_id: parseInt($('#duty-person').value),
        org_id: parseInt($('#duty-org').value),
        position: $('#duty-position').value.trim(),
        start_date: $('#duty-start').value,
        end_date: $('#duty-end').value,
        description: $('#duty-desc').value.trim()
    };
    if (!data.position) { toast('请输入职位', 'error'); return; }
    const res = await API.post('/api/duties', data);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('添加成功', 'success');
    hideDutyModal();
    loadDuties();
}

// ── 网络可视化 ──
let networkChart = null;
let allNetworkData = null;  // 缓存完整数据

async function loadNetwork() {
    const container = $('#network-container');
    if (!window.echarts) {
        container.innerHTML = '<div class="empty-state">正在加载 ECharts...</div>';
        return;
    }

    // 加载完整数据
    const res = await API.get('/api/network');
    allNetworkData = res;

    // ✅ 填充核心人员下拉列表
    populateCorePersonSelect(res.nodes);

    // 应用筛选
    applyNetworkFilter();
}

// ✅ 填充核心人员下拉框
function populateCorePersonSelect(nodes) {
    const select = $('#core-person-select');
    select.innerHTML = '<option value="">-- 请选择 --</option>';
    nodes.forEach(n => {
        select.innerHTML += `<option value="${n.id}">${n.name}</option>`;
    });
}

// ✅ 应用网络筛选
async function applyNetworkFilter() {
    if (!allNetworkData || !window.echarts) return;

    const filterType = $('#network-filter-type').value;
    const corePersonId = $('#core-person-select').value;
    const maxDepth = parseInt($('#core-depth').value) || 2;

    // 显示/隐藏核心人员控制组
    $('#core-person-group').style.display = 
        (filterType === 'selected' || filterType === 'core') ? 'flex' : 'none';

    let filteredNodes = [];
    let filteredLinks = [];

    switch (filterType) {
        case 'all':
            filteredNodes = allNetworkData.nodes;
            filteredLinks = allNetworkData.links;
            break;

        case 'selected':
            // 只显示选中的核心人员（无关系）
            if (corePersonId) {
                const node = allNetworkData.nodes.find(n => n.id === parseInt(corePersonId));
                if (node) filteredNodes = [node];
            }
            filteredLinks = [];
            break;

        case 'core':
            // 显示核心人员及其指定层数的关系
            if (corePersonId) {
                const result = filterNetworkByCore(
                    parseInt(corePersonId), 
                    maxDepth,
                    allNetworkData.nodes,
                    allNetworkData.links
                );
                filteredNodes = result.nodes;
                filteredLinks = result.links;
            } else {
                // 未选择时显示全部
                filteredNodes = allNetworkData.nodes;
                filteredLinks = allNetworkData.links;
            }
            break;
    }

    renderNetwork(filteredNodes, filteredLinks);
}

function filterNetworkByCore(coreId, maxDepth, allNodes, allLinks) {
    // 构建邻接表
    const adj = {};
    allLinks.forEach(link => {
        if (!adj[link.source]) adj[link.source] = [];
        if (!adj[link.target]) adj[link.target] = [];
        adj[link.source].push(link.target);
        adj[link.target].push(link.source);
    });

    // BFS 收集可达节点
    const visited = new Set();
    const queue = [{ id: coreId, depth: 0 }];
    visited.add(coreId);

    while (queue.length > 0) {
        const { id, depth } = queue.shift();
        if (depth >= maxDepth) continue;

        const neighbors = adj[id] || [];
        for (const neighbor of neighbors) {
            if (!visited.has(neighbor)) {
                visited.add(neighbor);
                queue.push({ id: neighbor, depth: depth + 1 });
            }
        }
    }

    // 筛选节点
    const filteredNodes = allNodes.filter(n => visited.has(n.id));

    // 筛选边（两端都在节点集中）
    const nodeSet = visited;
    const filteredLinks = allLinks.filter(link => 
        nodeSet.has(link.source) && nodeSet.has(link.target)
    );
    console.log(filteredLinks);
    console.log(filteredNodes);
    return { nodes: filteredNodes, links: filteredLinks };
}

// ✅ 渲染网络图
function renderNetwork(nodes, links) {
    console.log(' renderNetwork 开始执行');
    console.log('   nodes:', nodes);
    console.log('   links:', links);
    console.log('   typeof echarts:', typeof echarts);
    
    if (!networkChart) {
        networkChart = echarts.init($('#network-container'));
        window.addEventListener('resize', () => networkChart && networkChart.resize());
    }

    const categoriesMap = { '男': '男性', '女': '女性' };
    const categories = [
        { name: '男性', itemStyle: { color: '#1565C0' } },
        { name: '女性', itemStyle: { color: '#E91E63' } }
    ];

    // 如果没有数据，显示提示
    if (nodes.length === 0) {
        networkChart.setOption({
            title: { text: '请选择核心人员', left: 'center', top: 'center' }
        });
        return;
    }

    const option = {
        title: { 
            text: `关系网络图（${nodes.length} 个节点，${links.length} 条关系）`, 
            left: 'center', 
            top: 10,
            textStyle: { fontSize: 14 }
        },
        tooltip: {
            trigger: 'item',
            formatter: function(p) {
                if (p.dataType === 'edge') {
                    return `${p.data.label || '关系'}`;
                }
                return `${p.name}<br/>性别: ${categoriesMap[p.data.category === 0 ? '男' : '女']}`;
            }
        },
        legend: [{ data: categories.map(c => c.name), bottom: 10, left: 'center' }],
        series: [{
            type: 'graph',
            layout: 'force',
            nodesId: 'id',
            roam: true,
            draggable: true,
            force: {
                repulsion: 300,
                edgeLength: [120, 250],
                friction: 0.15
            },
            categories: categories,
            data: nodes.map(n => ({
                id: String(n.id),
                name: n.name,
                category: n.category,
                symbolSize: 40,
                label: { show: true, fontSize: 12 }
            })),
            edges: links.map(l => ({
                source: String(l.source),
                target: String(l.target),
                label: { show: true, formatter: l.label }
            })),
            lineStyle: {
                color: '#bbb',
                curveness: 0.15,
                width: 1.5
            },
            emphasis: {
                focus: 'adjacency',
                lineStyle: { width: 3 }
            }
        }]
    };

    networkChart.setOption(option, true);
}

// ── 关系穿透分析 ──
async function initAnalyze() {
    if (state.user.permission_level < 2) {
        $('#analyze-results').innerHTML = '<div class="empty-state">需要民警及以上权限</div>';
        return;
    }
    const res = await API.get('/api/persons/all');
    const persons = Array.isArray(res) ? res : [];
    let opts = '';
    persons.forEach(p => opts += `<option value="${p.pid}">${escapeHtml(p.name)}</option>`);
    $('#ana-person-a').innerHTML = opts;
    $('#ana-person-b').innerHTML = opts;
}

async function doAnalyze() {
    const personA = $('#ana-person-a').value;
    const personB = $('#ana-person-b').value;
    const maxDepth = $('#ana-depth').value;
    if (!personA || !personB) { toast('请选择两个人员', 'error'); return; }
    const res = await API.get(`/api/analyze?person_a=${personA}&person_b=${personB}&max_depth=${maxDepth}`);
    if (res.error) { toast(res.error, 'error'); return; }

    let html = `<div class="card" style="margin-top:16px">
        <div class="card-header">分析结果：${escapeHtml(res.person_a_name)} → ${escapeHtml(res.person_b_name)}（最大${res.max_depth}层）</div>
        <div class="card-body">`;

    if (res.path_count === 0) {
        html += '<div class="empty-state"><div class="empty-icon">🔍</div>未找到关系路径</div>';
    } else {
        html += `<p style="margin-bottom:12px;color:var(--primary);font-weight:600;">共找到 ${res.path_count} 条路径</p>`;
        res.paths.forEach((path, i) => {
            html += `<div class="result-path"><strong>路径${i + 1}（${path.length}层）：</strong> `;
            path.forEach((step, j) => {
                html += `<span class="step">${escapeHtml(step.from_name)}</span>`;
                html += `<span class="arrow">—${step.relation_type}→</span>`;
                if (j === path.length - 1) {
                    html += `<span class="step">${escapeHtml(step.to_name)}</span>`;
                }
            });
            html += '</div>';
        });
    }
    html += '</div></div>';
    $('#analyze-results').innerHTML = html;
}

// ── 用户管理 ──
async function loadUsers() {
    if (state.user.permission_level < 3) {
        $('#user-table-body').innerHTML = '<tr><td colspan="5" class="empty-state">需要管理员权限</td></tr>';
        return;
    }
    const res = await API.get('/api/users');
    const perms = { 1: '普通大众', 2: '民警', 3: '管理员' };
    let html = '';
    (Array.isArray(res) ? res : []).forEach(u => {
        html += `<tr>
            <td>${u.uid}</td><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.display_name)}</td>
            <td>${perms[u.permission_level] || u.permission_level}</td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteUser(${u.uid}, '${escapeHtml(u.username)}')">删除</button></td></tr>`;
    });
    $('#user-table-body').innerHTML = html || '<tr><td colspan="5" class="empty-state">暂无数据</td></tr>';
}

async function deleteUser(uid, username) {
    if (!confirm(`确定删除用户 "${username}" 吗？`)) return;
    const res = await API.del(`/api/users/${uid}`);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('删除成功', 'success');
    loadUsers();
}

function showUserModal() {
    $('#user-modal').classList.add('show');
    $('#user-form').reset();
}
function hideUserModal() { $('#user-modal').classList.remove('show'); }

async function saveUser() {
    const data = {
        username: $('#user-username').value.trim(),
        password: $('#user-password').value,
        permission_level: parseInt($('#user-permission').value),
        display_name: $('#user-display').value.trim()
    };
    if (!data.username || !data.password) { toast('用户名和密码不能为空', 'error'); return; }
    const res = await API.post('/api/users', data);
    if (res.error) { toast(res.error, 'error'); return; }
    toast('创建成功', 'success');
    hideUserModal();
    loadUsers();
}

async function doLogout() {
    await API.post('/api/logout');
    state.user = null;
    $('#login-overlay').style.display = 'flex';
    $('#app-layout').style.display = 'none';
    $('#login-username').value = '';
    $('#login-password').value = '';
}

// ── 键盘事件 ──
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        $$('.modal-overlay.show').forEach(m => m.classList.remove('show'));
    }
    if (e.key === 'Enter' && $('#login-overlay').style.display !== 'none') {
        handleLogin();
    }
});

// ── 初始化 ──
(async function init() {
    const res = await API.get('/api/current_user');
    if (res.logged_in) {
        state.user = res.user;
        $('#login-overlay').style.display = 'none';
        $('#app-layout').style.display = 'flex';
        initApp();
    } else {
        $('#login-overlay').style.display = 'flex';
        $('#app-layout').style.display = 'none';
    }
})();
