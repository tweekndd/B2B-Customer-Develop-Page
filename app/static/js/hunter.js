/* ============================================
   AI Trade Customer Analyzer V3.2.3 - Hunter 邮箱查找页
   ============================================ */

// ── 检查配置状态 ──
async function checkHunterConfig() {
    try {
        const status = await _fetchWithTimeout('/api/hunter/status');
        const badge = document.getElementById('hunterConfigBadge');
        if (status.configured) {
            if (status.test_mode) {
                badge.className = 'badge rounded-pill bg-warning text-dark';
                badge.textContent = '测试模式 (test-api-key)';
            } else {
                badge.className = 'badge rounded-pill bg-success';
                badge.textContent = 'API Key 已配置';
            }
        } else {
            badge.className = 'badge rounded-pill bg-danger';
            badge.textContent = '未配置 API Key';
        }
    } catch (err) {
        console.error('检查 Hunter 配置失败:', err);
        document.getElementById('hunterConfigBadge').textContent = '配置检查失败';
    }
}

// ── 快速查找 ──
async function quickHunterSearch() {
    const domain = document.getElementById('hQuickDomain').value.trim();
    if (!domain) {
        showToast('请输入公司域名', 'warning');
        return;
    }

    const firstName = document.getElementById('hQuickFirstName').value.trim();
    const lastName = document.getElementById('hQuickLastName').value.trim();
    const dept = document.getElementById('hQuickDepartment').value;
    const seniority = document.getElementById('hQuickSeniority').value;

    document.getElementById('hQuickLoading').classList.remove('d-none');
    document.getElementById('hQuickResult').classList.add('d-none');
    const btn = document.getElementById('btnQuickSearch');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>查找中...';

    try {
        let url = `/api/hunter/find-emails?domain=${encodeURIComponent(domain)}`;
        if (firstName) url += `&first_name=${encodeURIComponent(firstName)}`;
        if (lastName) url += `&last_name=${encodeURIComponent(lastName)}`;
        if (dept) url += `&department=${encodeURIComponent(dept)}`;
        if (seniority) url += `&seniority=${encodeURIComponent(seniority)}`;

        const data = await _fetchWithTimeout(url, {}, 20000);
        renderQuickResult(data);
    } catch (err) {
        const resultEl = document.getElementById('hQuickResult');
        resultEl.classList.remove('d-none');
        resultEl.innerHTML = `<div class="alert alert-danger mb-0"><i class="bi bi-exclamation-triangle me-1"></i>查询失败: ${_esc(err.message)}</div>`;
    } finally {
        document.getElementById('hQuickLoading').classList.add('d-none');
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-search me-1"></i>查找';
    }
}

function renderQuickResult(data) {
    const resultEl = document.getElementById('hQuickResult');
    resultEl.classList.remove('d-none');

    if (data.total_available === 0) {
        resultEl.innerHTML = `
            <div class="card border-0">
                <div class="card-body">
                    <div class="alert alert-info mb-0">
                        <i class="bi bi-info-circle me-1"></i>
                        Hunter 数据库中未找到 <strong>${_esc(data.domain)}</strong> 的邮箱数据。
                    </div>
                </div>
            </div>`;
        return;
    }

    const emails = data.emails || [];
    const quotaInfo = data.quota_used || {};
    const searchUsed = (quotaInfo.domain_search || 0) + (quotaInfo.email_finder || 0);

    let html = `
        <div class="card border-0">
            <div class="card-header d-flex justify-content-between">
                <span><i class="bi bi-envelope-fill me-1"></i> ${_esc(data.domain)} 的邮箱</span>
                <span class="text-muted small">
                    共 ${data.total_available} 个可用 | 本次消耗 ${searchUsed} 次搜索
                </span>
            </div>
            <div class="card-body p-0">`;

    if (emails.length === 0) {
        html += `
            <div class="p-3">
                <div class="alert alert-warning mb-0">
                    <i class="bi bi-search me-1"></i>
                    该公司共有 ${data.total_available} 个邮箱，但未匹配到筛选条件。
                </div>
            </div>`;
    } else {
        html += `
            <div class="table-responsive">
                <table class="table table-hover mb-0 align-middle">
                    <thead>
                        <tr>
                            <th>邮箱</th>
                            <th>姓名</th>
                            <th>职位</th>
                            <th>置信度</th>
                            <th>验证</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>`;

        emails.forEach(e => {
            const email = e.value || e.email || '';
            const name = [e.first_name, e.last_name].filter(Boolean).join(' ') || '-';
            const position = e.position || '-';
            const confidence = e.confidence || 0;
            const verification = e.verification || {};
            const vStatus = verification.status || 'unknown';
            const vBadge = vStatus === 'valid' ? 'success' : vStatus === 'accept_all' ? 'warning text-dark' : 'secondary';
            const vLabel = vStatus === 'valid' ? '有效' : vStatus === 'accept_all' ? '待验证' : '未知';
            const confBadge = confidence >= 90 ? 'success' : confidence >= 70 ? 'warning text-dark' : 'secondary';

            html += `<tr>
                <td><code style="font-size:0.85rem">${_esc(email)}</code></td>
                <td>${_esc(name)}</td>
                <td><small>${_esc(position)}</small></td>
                <td><span class="badge bg-${confBadge}">${confidence}%</span></td>
                <td><span class="badge bg-${vBadge}" style="font-size:0.75rem">${vLabel}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-secondary" onclick="_copyText('${_esc(email)}')" title="复制邮箱">
                        <i class="bi bi-clipboard"></i>
                    </button>
                </td>
            </tr>`;
        });

        html += `</tbody></table></div>`;
    }

    html += `</div></div>`;
    resultEl.innerHTML = html;
}

// ── 配额统计 ──
async function refreshUsage() {
    try {
        const data = await _fetchWithTimeout('/api/hunter/usage');

        const usage = data.session_usage || {};
        const usageHtml = `
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted small">Email Count（免费）</span>
                <span class="fw-medium">${usage.email_count || 0}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted small">Domain Search</span>
                <span class="fw-medium">${usage.domain_search || 0}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted small">Email Finder</span>
                <span class="fw-medium">${usage.email_finder || 0}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted small">Email Verifier</span>
                <span class="fw-medium">${usage.email_verifier || 0}</span>
            </div>
            <hr class="my-2">
            <div class="d-flex justify-content-between mb-1">
                <span class="text-muted small">缓存命中</span>
                <span class="fw-medium text-success">${usage.cache_hits || 0}</span>
            </div>
            <div class="d-flex justify-content-between">
                <span class="text-muted small">实际搜索消耗</span>
                <span class="fw-medium text-warning">${usage.total_searches || 0}</span>
            </div>
        `;
        document.getElementById('usageStatsContainer').innerHTML = usageHtml;

        const cache = data.cache || {};
        if (cache.enabled) {
            const byTypeHtml = Object.entries(cache.by_type || {})
                .map(([k, v]) => `<span class="badge bg-secondary me-1">${k}: ${v}条</span>`)
                .join('');
            const cacheHtml = `
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted small">缓存条目总数</span>
                    <span class="fw-medium">${cache.total_entries || 0}</span>
                </div>
                <div class="mb-0">
                    <span class="text-muted small">类型分布</span>
                    <div class="mt-1">${byTypeHtml || '<span class="text-muted small">暂无</span>'}</div>
                </div>
            `;
            document.getElementById('cacheStatsContainer').innerHTML = cacheHtml;
        } else {
            document.getElementById('cacheStatsContainer').innerHTML = '<p class="text-muted small mb-0">缓存功能不可用（无数据库连接）</p>';
        }
    } catch (err) {
        document.getElementById('usageStatsContainer').innerHTML = `<p class="text-danger small mb-0">加载失败: ${_esc(err.message)}</p>`;
    }
}

// ── 清除缓存 ──
async function clearHunterCache() {
    if (!confirm('确定要清除所有 Hunter 缓存吗？下次查询将消耗真实 API 额度。')) return;
    try {
        const data = await _fetchWithTimeout('/api/hunter/clear-cache', { method: 'POST' });
        showToast(data.message, 'success');
        refreshUsage();
    } catch (err) {
        showToast('清除失败: ' + err.message, 'danger');
    }
}

// ── 按回车触发查找 ──
document.addEventListener('DOMContentLoaded', () => {
    checkHunterConfig();
    refreshUsage();

    const inputs = ['hQuickDomain', 'hQuickFirstName', 'hQuickLastName'];
    inputs.forEach(id => {
        document.getElementById(id).addEventListener('keydown', (e) => {
            if (e.key === 'Enter') quickHunterSearch();
        });
    });
});
