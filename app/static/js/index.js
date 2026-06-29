/* ============================================
   AI Trade Customer Analyzer V3.2.3 - 客户列表页
   ============================================ */

let searchTimer = null, statusPollTimer = null;

window.addEventListener('beforeunload', () => {
    if (statusPollTimer) { clearInterval(statusPollTimer); statusPollTimer = null; }
});

// ── 加载客户列表 ──
async function loadCustomers() {
    const search = document.getElementById('searchInput').value;
    const country = document.getElementById('countryFilter').value;
    const priority = document.getElementById('priorityFilter').value;
    const status = document.getElementById('statusFilter').value;
    const sort = document.getElementById('sortFilter').value;
    let url = `/api/customers?sort_by_score=${sort}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (country) url += `&country=${encodeURIComponent(country)}`;
    if (priority) url += `&priority=${encodeURIComponent(priority)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    try {
        const data = await _fetchWithTimeout(url);
        renderTable(data);
        document.getElementById('totalCount').textContent = `${data.total} 个客户`;
        const countrySelect = document.getElementById('countryFilter');
        const currentCountry = countrySelect.value;
        countrySelect.innerHTML = '<option value="">所有国家</option>';
        data.countries.forEach(c => {
            countrySelect.innerHTML += `<option value="${_esc(c)}" ${c === currentCountry ? 'selected' : ''}>${_esc(c)}</option>`;
        });
    } catch (err) { console.error('加载客户列表失败:', err); }
}

// ── 渲染表格 ──
function renderTable(data) {
    const tbody = document.getElementById('customerTableBody');
    if (!data.customers || data.customers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10"><div class="table-empty-state"><i class="bi bi-inbox"></i>暂无匹配的客户数据</div></td></tr>`;
        return;
    }

    let html = '';
    data.customers.forEach(c => {
        const g = _gradeLabel(c.total_score);
        const displaySources = [];
        if (c.discovery_source === 'Google') displaySources.push('google');
        else if (c.discovery_source === 'Similar') displaySources.push('similar');
        else displaySources.push('excel');

        const statusMap = {
            '待联系': 'new', '已发邮件': 'contacted', '已回复': 'qualified',
            '无效线索': 'unqualified', '成单': 'negotiating'
        };
        const followDate = c.follow_up_date
            ? `<br><small class="text-muted" style="font-size:0.75rem"><i class="bi bi-calendar3"></i> ${_esc(c.follow_up_date)}</small>`
            : '';
        const starHtml = _stars(c.star_rating);

        html += `<tr>
            <td class="text-center"><input class="form-check-input customer-checkbox" type="checkbox" value="${c.id}" onchange="updateBatchDeleteBtn()"></td>
            <td><a href="/customer/${c.id}" target="_blank" class="text-decoration-none fw-medium">${_esc(c.company_name)}</a></td>
            <td>
                <span class="followup-dot ${statusMap[c.status] || 'new'}"></span>
                <span>${_esc(c.status || '待联系')}</span>
                ${followDate}
            </td>
            <td><span class="badge bg-light text-dark border">${_esc(c.country) || '-'}</span></td>
            <td class="star-rating">${starHtml}</td>
            <td class="small">
                ${displaySources.map(s => `<span class="badge badge-source ${s}">${s === 'google' ? 'Google' : s === 'excel' ? '导入' : '相似'}</span>`).join(' ')}
                ${c.scrape_status === 'success' ? '<span class="badge badge-status analyzed" style="font-size:0.7rem">已抓取</span>' : ''}
                ${c.scrape_status === 'failed' ? '<span class="badge badge-status error" style="font-size:0.7rem">失败</span>' : ''}
                ${c.ai_status === 'success' ? '<span class="badge badge-status analyzed" style="font-size:0.7rem">已分析</span>' : ''}
            </td>
            <td><span class="badge bg-secondary rounded-pill">${c.email_count}</span></td>
            <td class="fw-bold fs-6 ${g.cls}">${c.total_score ?? '-'}</td>
            <td><span class="badge rounded-pill ${g.cls === 'grade-A' ? 'bg-danger' : g.cls === 'grade-B' ? 'bg-warning text-dark' : g.cls === 'grade-C' ? 'bg-info text-dark' : 'bg-secondary'}">${c.priority || '-'}</span></td>
            <td>
                <div class="btn-group btn-group-sm" style="gap:2px">
                    <a href="/customer/${c.id}" target="_blank" class="btn btn-icon btn-outline-primary" title="查看详情"><i class="bi bi-eye"></i></a>
                    <button class="btn btn-icon btn-outline-success" onclick="analyzeSingle(${c.id})" title="分析"><i class="bi bi-lightning"></i></button>
                    <button class="btn btn-icon btn-outline-warning" onclick="rescrapeCustomer(${c.id})" title="重新抓取"><i class="bi bi-arrow-clockwise"></i></button>
                    <button class="btn btn-icon btn-outline-info" onclick="reanalyzeCustomer(${c.id})" title="重新AI分析"><i class="bi bi-robot"></i></button>
                    <button class="btn btn-icon btn-outline-danger" onclick="deleteCustomer(${c.id})" title="删除"><i class="bi bi-trash"></i></button>
                </div>
            </td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function _stars(rating) {
    const n = Number(rating) || 0;
    let s = '';
    for (let i = 1; i <= 5; i++) {
        s += i <= n
            ? '<i class="bi bi-star-fill text-warning"></i>'
            : '<i class="bi bi-star text-muted" style="opacity:0.3"></i>';
    }
    return s;
}

// ── 加载统计（带数字动画） ──
async function loadStats() {
    try {
        const s = await _fetchWithTimeout('/api/stats');
        _animateNumber(document.getElementById('statTotal'), s.total);
        _animateNumber(document.getElementById('statAnalyzed'), s.analyzed);
        _animateNumber(document.getElementById('statGoogle'), s.discovery_stats?.google || 0);
        _animateNumber(document.getElementById('statGradeA'), s.priority_distribution?.A || 0);
    } catch (err) { console.error('加载统计数据失败:', err); }
}

// ── 导入Excel ──
async function importExcel() {
    const file = document.getElementById('excelFile').files[0];
    if (!file) { showToast('请选择Excel文件', 'warning'); return; }
    const progress = document.getElementById('importProgress');
    const result = document.getElementById('importResult');
    progress.classList.remove('d-none');
    result.classList.add('d-none');
    try {
        const fd = new FormData();
        fd.append('file', file);
        const data = await _fetchWithTimeout('/api/import-excel', { method: 'POST', body: fd }, 30000);
        result.className = 'alert alert-success mt-3';
        result.innerHTML = `<i class="bi bi-check-circle me-1"></i> ${data.message}<br><small class="text-muted">文件中 ${data.total_in_file} 条，成功导入 ${data.imported} 条</small>`;
        result.classList.remove('d-none');
        showToast('导入成功', 'success');
        loadCustomers();
        loadStats();
    } catch (err) {
        result.className = 'alert alert-danger mt-3';
        result.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> ${_esc(err.message)}`;
        result.classList.remove('d-none');
        showToast('导入失败', 'danger');
    } finally {
        progress.classList.add('d-none');
    }
}

// ── 分析操作 ──
async function analyzeSingle(id) {
    if (!confirm('确定要分析该客户吗？')) return;
    try {
        await _fetchWithTimeout(`/api/analyze/${id}`, { method: 'POST' }, 120000);
        loadCustomers(); loadStats();
        showToast('分析完成', 'success');
    } catch (err) {
        showToast('分析失败: ' + err.message, 'danger');
    }
}

async function analyzeAll() {
    if (!confirm('确定要分析所有未分析的客户吗？')) return;
    const btn = document.getElementById('btnAnalyzeAll');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>分析中...';
    showAnalysisStatus('批量分析进行中...');
    try {
        const data = await _fetchWithTimeout('/api/analyze-all', { method: 'POST' }, 600000);
        loadCustomers(); loadStats();
        showToast(`批量分析完成！共分析 ${data.analyzed_count} 个客户`, 'success');
    } catch (err) {
        showToast('批量分析失败: ' + err.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-lightning-fill me-1"></i>批量分析';
        hideAnalysisStatus();
    }
}

async function stopAnalysis() {
    try {
        await _fetchWithTimeout('/api/stop-analysis', { method: 'POST' });
        document.getElementById('analysisStatusText').textContent = '正在停止...';
        setTimeout(() => { hideAnalysisStatus(); loadCustomers(); }, 2000);
        showToast('已发送停止信号', 'info');
    } catch (err) { console.error('停止分析失败:', err); }
}

function showAnalysisStatus(text) {
    document.getElementById('analysisStatusText').textContent = text;
    document.getElementById('analysisStatusBar').classList.remove('d-none');
    if (statusPollTimer) clearInterval(statusPollTimer);
    statusPollTimer = setInterval(pollStatus, 2000);
}

function hideAnalysisStatus() {
    document.getElementById('analysisStatusBar').classList.add('d-none');
    if (statusPollTimer) { clearInterval(statusPollTimer); statusPollTimer = null; }
}

async function pollStatus() {
    try {
        const s = await _fetchWithTimeout('/api/analysis-status');
        if (!s.is_analyzing) {
            hideAnalysisStatus();
            loadCustomers();
            loadStats();
        } else {
            document.getElementById('analysisStatusText').textContent = '正在分析中...';
        }
    } catch (err) { console.error('轮询状态失败:', err); }
}

// ── 批量选择 & 删除 ──
function toggleSelectAll() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.customer-checkbox').forEach(cb => cb.checked = checked);
    updateBatchDeleteBtn();
}

function updateBatchDeleteBtn() {
    const checked = document.querySelectorAll('.customer-checkbox:checked');
    const btn = document.getElementById('batchDeleteBtn');
    const count = document.getElementById('selectedCount');
    if (checked.length > 0) {
        btn.classList.remove('d-none');
        count.textContent = checked.length;
    } else {
        btn.classList.add('d-none');
    }
}

async function batchDeleteCustomers() {
    const checked = document.querySelectorAll('.customer-checkbox:checked');
    if (checked.length === 0) return;
    if (!confirm(`确定要删除所选 ${checked.length} 个客户吗？此操作不可撤销。`)) return;
    const ids = Array.from(checked).map(cb => parseInt(cb.value));
    try {
        const data = await _fetchWithTimeout(`/api/customers/batch-delete?ids=${encodeURIComponent(JSON.stringify(ids))}`, { method: 'POST' });
        document.getElementById('selectAll').checked = false;
        updateBatchDeleteBtn();
        loadCustomers(); loadStats();
        showToast(`已删除 ${data.deleted} 个客户`, 'success');
    } catch (err) {
        showToast('批量删除失败: ' + err.message, 'danger');
    }
}

async function deleteCustomer(id) {
    if (!confirm('确定要删除该客户吗？')) return;
    try {
        await _fetchWithTimeout(`/api/customers/${id}`, { method: 'DELETE' });
        loadCustomers(); loadStats();
        showToast('已删除', 'success');
    } catch (err) {
        showToast('删除失败: ' + err.message, 'danger');
    }
}

function debouncedSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { loadCustomers(); }, 400);
}

function refreshData() { loadCustomers(); loadStats(); }

// ── 重新抓取 / 重新分析 ──
async function rescrapeCustomer(id) {
    if (!confirm('确定要重新抓取该客户的官网吗？')) return;
    try {
        await _fetchWithTimeout(`/api/customers/${id}/re-scrape`, { method: 'POST' }, 60000);
        loadCustomers(); loadStats();
        showToast('重新抓取完成', 'success');
    } catch (err) {
        showToast('重新抓取失败: ' + err.message, 'danger');
    }
}

async function reanalyzeCustomer(id) {
    if (!confirm('确定要重新AI分析该客户吗？')) return;
    try {
        await _fetchWithTimeout(`/api/customers/${id}/re-analyze`, { method: 'POST' }, 120000);
        loadCustomers(); loadStats();
        showToast('重新分析完成', 'success');
    } catch (err) {
        showToast('重新分析失败: ' + err.message, 'danger');
    }
}

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => { loadCustomers(); loadStats(); });
