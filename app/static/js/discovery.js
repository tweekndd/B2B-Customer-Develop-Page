/* ============================================
   AI Trade Customer Analyzer V3.2.3 - 客户发现页
   ============================================ */

// ═══════════════════════════════════════════
// SSE 实时任务流
// ═══════════════════════════════════════════
let _eventSource = null;
let _activeTaskId = null;
let _fallbackTimer = null;
let _fallbackCount = 0;
let _discPage = 1;
let _discTotalPages = 1;
let _similarCompanies = [];

function _connectSSE(taskId) {
    _disconnectSSE();
    if (!taskId) return;
    _activeTaskId = taskId;
    const url = `/api/discovery/task-stream/${taskId}`;
    _eventSource = new EventSource(url);

    _eventSource.addEventListener('progress', function (e) {
        try {
            const data = JSON.parse(e.data);
            _activeTaskId = data.id;
            const kws = _arr(data.expanded_keywords);
            const totalKw = kws.length || 1;
            const currentIdx = _num(data.current_keyword_index);
            const progress = data.status === 'Pending' ? 0 : _calcProgress(currentIdx, totalKw);
            const currentKw = kws[currentIdx] || data.keyword;

            updateSearchStatus(
                `任务 #${data.id}: ${_esc(data.country)} / ${_esc(data.keyword)}`,
                `正在处理第 ${Math.min(currentIdx + 1, totalKw)}/${totalKw} 个关键词: 「${_esc(currentKw)}」 | 发现 ${_num(data.found_websites)} 个网站, 新增 ${_num(data.new_companies)} 个公司`,
                progress, kws, currentIdx
            );
        } catch (err) {
            console.error('SSE progress 解析失败:', err);
        }
    });

    _eventSource.addEventListener('done', function (e) {
        try {
            const data = JSON.parse(e.data);
            console.log(`任务 #${data.id} 结束: ${data.status}`);
        } catch (err) { /* ignore */ }
        _disconnectSSE();
        _refreshAll();
        hideSearchStatus();
    });

    _eventSource.addEventListener('error', function (e) {
        if (e.data) {
            try {
                const data = JSON.parse(e.data);
                console.warn('SSE 错误:', data.detail || '');
            } catch (err) { /* ignore */ }
            _disconnectSSE();
            _refreshAll();
            hideSearchStatus();
        } else if (_eventSource && _eventSource.readyState === EventSource.CLOSED) {
            _disconnectSSE();
            _refreshAll();
            if (_activeTaskId !== null) {
                _startFallbackCheck();
            }
        }
    });
}

function _disconnectSSE() {
    if (_eventSource) {
        _eventSource.close();
        _eventSource = null;
    }
    _activeTaskId = null;
    _stopFallbackCheck();
}

window.addEventListener('beforeunload', _disconnectSSE);

function _startFallbackCheck() {
    _stopFallbackCheck();
    _fallbackCount = 0;
    _fallbackTimer = setInterval(() => {
        _fallbackCount++;
        if (_fallbackCount > 3) {
            _stopFallbackCheck();
            return;
        }
        _refreshAll();
    }, 10000);
}

function _stopFallbackCheck() {
    if (_fallbackTimer) {
        clearInterval(_fallbackTimer);
        _fallbackTimer = null;
    }
    _fallbackCount = 0;
}

function _calcProgress(currentIdx, totalKw) {
    const idx = _num(currentIdx, 0);
    const total = _num(totalKw, 1);
    if (total <= 0) return 0;
    return Math.min(Math.max(Math.round((idx / total) * 100), 0), 100);
}

// ═══════════════════════════════════════════
// 预览扩展关键词
// ═══════════════════════════════════════════
async function previewKeywords() {
    const keyword = document.getElementById('discoveryKeyword').value.trim();
    const country = document.getElementById('discoveryCountry').value.trim();
    if (!keyword) { showToast('请输入关键词', 'warning'); return; }
    const btn = document.getElementById('btnPreview');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    document.getElementById('previewResult').textContent = '正在扩展...';
    try {
        let url = `/api/discovery/expand-keywords?keyword=${encodeURIComponent(keyword)}`;
        if (country) url += `&country=${encodeURIComponent(country)}`;
        const data = await _fetchWithTimeout(url);
        const kws = _arr(data.expanded_keywords);
        const langHint = data.country ? `（${_esc(data.country)}语言）` : '';
        document.getElementById('previewResult').textContent =
            kws.length > 0
                ? `扩展了 ${kws.length} 个关键词${langHint}: ${kws.join(', ')}`
                : '扩展失败，请重试';
    } catch (err) {
        document.getElementById('previewResult').textContent = '扩展失败: ' + err.message;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-magic me-1"></i>预览扩展关键词';
    }
}

// ═══════════════════════════════════════════
// 开始搜索
// ═══════════════════════════════════════════
async function startSearch() {
    const country = document.getElementById('discoveryCountry').value.trim();
    const keyword = document.getElementById('discoveryKeyword').value.trim();
    const depth = document.getElementById('discoveryDepth').value || 50;
    if (!country || !keyword) { showToast('请输入国家和关键词', 'warning'); return; }

    const btn = document.getElementById('btnStartSearch');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>启动中...';

    try {
        await _fetchWithTimeout(
            `/api/discovery/search-task?country=${encodeURIComponent(country)}&keyword=${encodeURIComponent(keyword)}&depth=${depth}`,
            { method: 'POST' }
        );
        const data = await _refreshAll();
        if (data && data.active_task_id) {
            _connectSSE(data.active_task_id);
        } else {
            _startFallbackCheck();
        }
        showToast('搜索任务已启动', 'success');
    } catch (err) {
        showToast('启动失败: ' + err.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>开始搜索';
    }
}

// ═══════════════════════════════════════════
// 停止搜索任务
// ═══════════════════════════════════════════
async function stopSearchTask() {
    const btn = document.querySelector('#searchRunningBar .btn-outline-danger');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>停止中...'; }
    try {
        await _fetchWithTimeout('/api/stop-analysis', { method: 'POST' });
        document.getElementById('searchStatusText').textContent = '正在停止...';
        document.getElementById('searchProgressDetail').textContent = '正在等待当前任务完成';
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="bi bi-stop-circle me-1"></i>停止中...'; }
        setTimeout(async () => {
            await _refreshAll();
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-stop-circle me-1"></i>停止任务'; }
        }, 3000);
        showToast('已发送停止信号', 'info');
    } catch (err) {
        console.error('停止失败:', err);
        showToast('发送停止信号失败: ' + err.message, 'danger');
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-stop-circle me-1"></i>停止任务'; }
    }
}

// ═══════════════════════════════════════════
// 更新搜索状态栏
// ═══════════════════════════════════════════
function updateSearchStatus(title, detail, progress, keywords, currentIdx) {
    document.getElementById('searchStatusText').textContent = title;
    document.getElementById('searchProgressDetail').textContent = detail;
    const bar = document.getElementById('searchProgressBar');
    const pct = Math.min(_num(progress), 100);
    bar.style.width = pct + '%';
    bar.textContent = pct + '%';
    document.getElementById('searchRunningBar').classList.remove('d-none');

    const container = document.getElementById('keywordListContainer');
    const newKey = JSON.stringify({ kws: keywords, idx: currentIdx });
    if (newKey === (container.dataset.lastKey || '')) return;
    container.dataset.lastKey = newKey;

    const kws = _arr(keywords);
    if (kws.length === 0) {
        container.innerHTML = '<span class="text-muted small">暂无关键词</span>';
        return;
    }

    let html = '';
    const idx = _num(currentIdx);
    kws.forEach((kw, i) => {
        let cls;
        if (i < idx)       { cls = 'badge bg-success'; }
        else if (i === idx) { cls = 'badge bg-warning text-dark'; }
        else               { cls = 'badge bg-light text-muted border'; }
        html += `<span class="${cls}" style="font-weight:400">${_esc(kw)}</span>`;
    });
    container.innerHTML = html;
}

function hideSearchStatus() {
    document.getElementById('searchRunningBar').classList.add('d-none');
}

// ═══════════════════════════════════════════
// 渲染任务表格
// ═══════════════════════════════════════════
function _renderTaskTable(data) {
    const tbody = document.getElementById('taskTableBody');
    const tasks = data.tasks || [];
    if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10"><div class="table-empty-state" style="padding:1.5rem"><i class="bi bi-inbox"></i>暂无搜索任务</div></td></tr>';
        return;
    }

    let html = '';
    tasks.forEach(t => {
        const kws = _arr(t.expanded_keywords);
        const totalKw = kws.length || 1;
        const progress = t.status === 'Completed' ? 100
            : t.status === 'Pending' ? 0
            : _calcProgress(_num(t.current_keyword_index), totalKw);

        let keywordLabel = _esc(t.keyword);
        if (t.status === 'Running' && kws.length > 0) {
            const idx = Math.min(_num(t.current_keyword_index), kws.length - 1);
            if (idx >= 0) keywordLabel += ` → ${_esc(kws[idx])}`;
        }

        const taskStatusCls = {
            'Pending': 'badge-status pending', 'Running': 'badge-status running',
            'Completed': 'badge-status completed', 'Failed': 'badge-status error',
            'Paused': 'badge-status stopped'
        };

        html += `<tr>
            <td>#${t.id}</td>
            <td>${_esc(t.country)}</td>
            <td class="small">${keywordLabel}</td>
            <td>${kws.length || '-'}</td>
            <td><span class="badge-status ${taskStatusCls[t.status] || 'bg-secondary'}">${_esc(t.status)}</span></td>
            <td>${_num(t.found_websites)}</td>
            <td class="fw-bold">${_num(t.new_companies)}</td>
            <td style="min-width:100px">
                <div class="d-flex align-items-center gap-2">
                    <div class="progress flex-grow-1" style="height:6px">
                        <div class="progress-bar ${t.status === 'Completed' ? 'bg-success' : t.status === 'Failed' ? 'bg-danger' : 'bg-warning'}" style="width:${progress}%"></div>
                    </div>
                    <small class="text-muted" style="font-size:0.75rem">${progress}%</small>
                </div>
            </td>
            <td class="small">${_fmtDate(t.created_at)}</td>
            <td>
                <button class="btn btn-icon btn-outline-secondary" onclick="showTaskLog(${t.id})" title="查看日志"><i class="bi bi-journal-text"></i></button>
                ${t.status === 'Paused' ? `<button class="btn btn-icon btn-outline-success ms-1" onclick="resumeTask(${t.id})" title="恢复"><i class="bi bi-play-fill"></i></button>` : ''}
                ${t.status === 'Completed' || t.status === 'Failed' ? `<button class="btn btn-icon btn-outline-danger ms-1" onclick="deleteTask(${t.id})" title="删除"><i class="bi bi-trash"></i></button>` : ''}
            </td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

async function loadTasks() {
    try {
        const data = await _fetchWithTimeout('/api/discovery/tasks');
        const activeId = data.active_task_id ?? null;
        _renderTaskTable(data);
        if (activeId && activeId !== _activeTaskId && (!_eventSource || _eventSource.readyState !== EventSource.OPEN)) {
            _connectSSE(activeId);
        }
        return data;
    } catch (err) { console.error('加载任务失败:', err); }
}

// ═══════════════════════════════════════════
// 恢复 / 删除
// ═══════════════════════════════════════════
async function resumeTask(id) {
    try {
        await _fetchWithTimeout(`/api/discovery/tasks/${id}/resume`, { method: 'POST' });
        await _refreshAll();
        _connectSSE(id);
        showToast('任务已恢复', 'success');
    } catch (err) {
        showToast('恢复失败: ' + err.message, 'danger');
    }
}

async function deleteTask(id) {
    if (!confirm('确定删除该任务？')) return;
    try {
        await _fetchWithTimeout(`/api/discovery/tasks/${id}`, { method: 'DELETE' });
        await _refreshAll();
        showToast('已删除', 'success');
    } catch (err) {
        showToast('删除失败: ' + err.message, 'danger');
    }
}

// ═══════════════════════════════════════════
// 发现结果列表（分页）
// ═══════════════════════════════════════════
async function loadDiscovered(resetPage) {
    if (resetPage) _discPage = 1;
    const search = document.getElementById('discSearch').value;
    const country = document.getElementById('discCountry').value;
    const priority = document.getElementById('discPriority').value;
    const keyword = document.getElementById('discKeyword').value;

    let url = `/api/discovery/discovered-customers?sort_by_score=desc&page=${_discPage}&page_size=50`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (country) url += `&country=${encodeURIComponent(country)}`;
    if (priority) url += `&priority=${encodeURIComponent(priority)}`;
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;

    try {
        const data = await _fetchWithTimeout(url);
        document.getElementById('discoveredCount').textContent = `${_num(data.total)} 个`;

        _discTotalPages = data.total_pages || 1;
        _renderDiscPagination();

        _updateSelectOptions('discCountry', data.countries || []);
        _updateSelectOptions('discKeyword', data.keywords || []);

        const tbody = document.getElementById('discoveredTableBody');
        const customers = data.customers || [];
        if (customers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8"><div class="table-empty-state" style="padding:1.5rem"><i class="bi bi-inbox"></i>暂无发现结果</div></td></tr>';
            return;
        }

        let html = '';
        customers.forEach(c => {
            const score = _num(c.total_score);
            const g = _gradeLabel(score);
            html += `<tr>
                <td><a href="/customer/${c.id}" class="text-decoration-none fw-medium">${_esc(c.company_name)}</a></td>
                <td><span class="badge bg-light text-dark border">${_esc(c.country) || '-'}</span></td>
                <td class="small text-muted">${_esc(c.website) || '-'}</td>
                <td><span class="badge bg-secondary rounded-pill">${_num(c.email_count)}</span></td>
                <td class="small text-muted">${_esc(c.discovery_keyword) || '-'}</td>
                <td class="fw-bold ${g.cls}">${score !== 0 || c.total_score !== null ? score : '-'}</td>
                <td><span class="badge rounded-pill ${g.cls === 'grade-A' ? 'bg-danger' : g.cls === 'grade-B' ? 'bg-warning text-dark' : g.cls === 'grade-C' ? 'bg-info text-dark' : 'bg-secondary'}">${_esc(c.priority) || '-'}</span></td>
                <td><a href="/customer/${c.id}" class="btn btn-sm btn-outline-primary"><i class="bi bi-eye me-1"></i>详情</a></td>
            </tr>`;
        });
        tbody.innerHTML = html;
    } catch (err) { console.error('加载发现结果失败:', err); }
}

function _renderDiscPagination() {
    const nav = document.getElementById('discPagination');
    if (_discTotalPages <= 1) { nav.style.display = 'none'; return; }
    nav.style.display = 'block';
    document.getElementById('discPageInfo').textContent = `${_discPage}/${_discTotalPages}`;
    document.getElementById('discPrevPage').className = `page-item${_discPage <= 1 ? ' disabled' : ''}`;
    document.getElementById('discNextPage').className = `page-item${_discPage >= _discTotalPages ? ' disabled' : ''}`;
}

function changeDiscPage(delta) {
    const newPage = _discPage + delta;
    if (newPage < 1 || newPage > _discTotalPages) return;
    _discPage = newPage;
    loadDiscovered(false);
}

function _updateSelectOptions(selectId, newOptions) {
    const sel = document.getElementById(selectId);
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">' + (selectId === 'discCountry' ? '所有国家' : '所有关键词') + '</option>';
    (newOptions || []).forEach(opt => {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        if (opt === currentVal) o.selected = true;
        sel.appendChild(o);
    });
}

// ═══════════════════════════════════════════
// 相似客户扩展
// ═══════════════════════════════════════════
async function findSimilarCompanies() {
    const url = document.getElementById('seedUrl').value.trim();
    const country = document.getElementById('seedCountry').value.trim();
    if (!url || !country) { showToast('请输入目标公司网址和目标国家', 'warning'); return; }

    const btn = document.getElementById('btnFindSimilar');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>分析中...';
    document.getElementById('similarProgress').classList.remove('d-none');
    document.getElementById('similarResultCard').classList.add('d-none');

    try {
        const data = await _fetchWithTimeout(
            `/api/discovery/similar-companies?company_url=${encodeURIComponent(url)}&target_country=${encodeURIComponent(country)}&top_n=50`,
            { method: 'POST' }, 120000
        );

        const seed = data.seed_company || {};
        document.getElementById('seedName').textContent = seed.name || url;
        document.getElementById('seedIndustry').textContent = seed.industry || seed.industry_category || '未知';
        document.getElementById('seedKeywords').textContent = (seed.keywords || []).slice(0, 5).join(', ') || '无';

        const companies = data.similar_companies || [];
        _similarCompanies = companies;
        document.getElementById('similarCount').textContent = `${companies.length} 个`;
        const tbody = document.getElementById('similarTableBody');

        if (companies.length === 0) {
            const errMsg = data.error ? ` (${data.error})` : '';
            tbody.innerHTML = `<tr><td colspan="6"><div class="table-empty-state" style="padding:1.5rem"><i class="bi bi-search"></i>未找到相似客户${_esc(errMsg)}</div></td></tr>`;
        } else {
            let html = '';
            companies.forEach((c, i) => {
                const sc = c.similarity_score || 0;
                const barColor = sc >= 70 ? 'bg-success' : sc >= 50 ? 'bg-warning' : 'bg-secondary';
                html += `<tr>
                    <td><input type="checkbox" class="form-check-input similar-checkbox" value="${i}" onchange="updateSimilarSelection()"></td>
                    <td>${i + 1}</td>
                    <td class="small">${_esc(c.name || c.website || '-')}</td>
                    <td class="small"><a href="https://${_esc(c.website)}" target="_blank" class="text-decoration-none">${_esc(c.website) || '-'}</a></td>
                    <td>${_esc(c.country) || '-'}</td>
                    <td style="min-width:120px">
                        <div class="d-flex align-items-center gap-2">
                            <div class="progress flex-grow-1" style="height:6px">
                                <div class="progress-bar ${barColor}" style="width:${sc}%"></div>
                            </div>
                            <small class="fw-bold">${sc}</small>
                        </div>
                    </td>
                </tr>`;
            });
            tbody.innerHTML = html;
        }
        document.getElementById('similarResultCard').classList.remove('d-none');
        showToast(`找到 ${companies.length} 个相似客户`, 'success');
    } catch (err) {
        document.getElementById('similarTableBody').innerHTML =
            `<tr><td colspan="6"><div class="table-empty-state" style="padding:1.5rem;color:var(--danger)"><i class="bi bi-exclamation-triangle"></i>请求失败: ${_esc(err.message)}</div></td></tr>`;
        document.getElementById('similarResultCard').classList.remove('d-none');
        showToast('请求失败: ' + err.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-diagram-3 me-1"></i>查找相似客户';
        document.getElementById('similarProgress').classList.add('d-none');
    }
}

// ═══════════════════════════════════════════
// 相似客户 — 批量选择 & 保存
// ═══════════════════════════════════════════
function toggleAllSimilar(checked) {
    document.querySelectorAll('.similar-checkbox').forEach(cb => cb.checked = checked);
    updateSimilarSelection();
}

function updateSimilarSelection() {
    const checked = document.querySelectorAll('.similar-checkbox:checked');
    document.getElementById('similarSelectedCount').textContent = `已选择 ${checked.length} 个`;
    document.getElementById('similarBatchBar').classList.toggle('d-none', checked.length === 0);
}

async function saveSelectedSimilar() {
    const checked = document.querySelectorAll('.similar-checkbox:checked');
    if (checked.length === 0) { showToast('请先选择公司', 'warning'); return; }

    const selected = [];
    checked.forEach(cb => {
        const idx = parseInt(cb.value);
        if (_similarCompanies[idx]) selected.push(_similarCompanies[idx]);
    });

    const btn = document.getElementById('btnSaveSimilar');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>保存中...';

    try {
        const result = await _fetchWithTimeout('/api/discovery/save-similar-companies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(selected),
        }, 30000);
        showToast(result.message, 'success');
        document.querySelectorAll('.similar-checkbox').forEach(cb => cb.checked = false);
        updateSimilarSelection();
    } catch (err) {
        showToast('保存失败: ' + err.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-save me-1"></i>保存到客户列表';
    }
}

// ═══════════════════════════════════════════
// 统一刷新
// ═══════════════════════════════════════════
async function _refreshAll() {
    const [taskData] = await Promise.all([loadTasks(), loadDiscovered()]);
    return taskData;
}

// ═══════════════════════════════════════════
// 查看任务日志
// ═══════════════════════════════════════════
async function showTaskLog(taskId) {
    document.getElementById('taskLogTitle').textContent = `#${taskId}`;
    document.getElementById('taskLogBody').innerHTML = '<p class="text-muted">加载中...</p>';
    const modal = new bootstrap.Modal(document.getElementById('taskLogModal'));
    modal.show();

    try {
        const data = await _fetchWithTimeout('/api/discovery/tasks');
        const task = (data.tasks || []).find(t => t.id === taskId);
        if (!task) {
            document.getElementById('taskLogBody').innerHTML = '<p class="text-muted">任务不存在</p>';
            return;
        }

        let logs = [];
        if (task.task_log) {
            try { logs = JSON.parse(task.task_log); } catch(e) { logs = []; }
        }

        if (logs.length === 0) {
            document.getElementById('taskLogBody').innerHTML = '<p class="text-muted">暂无日志记录</p>';
            return;
        }

        let html = '<table class="table table-sm table-borderless mb-0">';
        logs.forEach(log => {
            const icon = log.type === 'info' ? 'i' : log.type === 'success' ? '+' : log.type === 'warning' ? '!' : 'x';
            html += `<tr>
                <td class="text-muted" style="width:70px;white-space:nowrap;font-size:0.8rem">${_esc(log.time || '')}</td>
                <td style="width:30px">${icon}</td>
                <td style="font-size:0.85rem">${_esc(log.msg || '')}</td>
            </tr>`;
        });
        html += '</table>';
        document.getElementById('taskLogBody').innerHTML = html;
    } catch (err) {
        document.getElementById('taskLogBody').innerHTML = `<p class="text-danger">加载失败: ${_esc(err.message)}</p>`;
    }
}

// ═══════════════════════════════════════════
// 搜索引擎切换（V3.2 新增）
// ═══════════════════════════════════════════
async function loadSearchEngineConfig() {
    try {
        const data = await _fetchWithTimeout('/api/discovery/search-engine');
        const current = data.current || 'none';
        const available = data.available || {};

        document.querySelectorAll('.engine-btn').forEach(btn => {
            const eng = btn.dataset.engine;
            const isActive = eng === current;
            btn.classList.toggle('btn-outline-secondary', !isActive);
            btn.classList.toggle('btn-primary', isActive);
            btn.classList.toggle('active', isActive);
            btn.disabled = !available[eng];
            if (!available[eng]) {
                btn.title = eng + ' 未配置 API Key';
            } else {
                btn.title = '切换到 ' + eng;
            }
        });

        const indicator = document.getElementById('engineIndicator');
        if (current === 'tavily') {
            indicator.textContent = 'Tavily';
            indicator.className = 'badge rounded-pill bg-info';
        } else if (current === 'serpapi') {
            indicator.textContent = 'SerpAPI';
            indicator.className = 'badge rounded-pill bg-success';
        } else {
            indicator.textContent = '未配置';
            indicator.className = 'badge rounded-pill bg-secondary';
        }
    } catch (err) {
        console.error('加载搜索引擎配置失败:', err);
    }
}

async function switchSearchEngine(engine) {
    const btn = document.querySelector(`.engine-btn[data-engine="${engine}"]`);
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    try {
        const data = await _fetchWithTimeout(
            `/api/discovery/search-engine?engine=${encodeURIComponent(engine)}`,
            { method: 'POST' }
        );
        showToast(data.message || `已切换到 ${engine}`, 'success');
        await loadSearchEngineConfig();
    } catch (err) {
        showToast('切换失败: ' + err.message, 'danger');
        btn.disabled = false;
    }
}

// ═══════════════════════════════════════════
// 初始化
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
    const data = await _refreshAll();
    if (data && data.active_task_id) {
        _connectSSE(data.active_task_id);
    }
    await loadSearchEngineConfig();
});
