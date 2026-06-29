/* ============================================
   AI Trade Customer Analyzer V3.2.3 - 评分配置页
   ============================================ */

// ═══════════════════════════════════════════
// 数据状态
// ═══════════════════════════════════════════
let _config = null;
let _dirty = false;

// ═══════════════════════════════════════════
// 加载配置
// ═══════════════════════════════════════════
async function loadConfig() {
    try {
        const data = await _fetchWithTimeout('/api/config');
        _config = data;
        renderAll();
        _dirty = false;
    } catch (err) {
        console.error('加载配置失败:', err);
        showToast('加载配置失败: ' + err.message, 'danger');
    }
}

function markDirty() { _dirty = true; }

// ═══════════════════════════════════════════
// 渲染所有配置项
// ═══════════════════════════════════════════
function renderAll() {
    if (!_config) return;
    const ic = _config.industry_config || {};
    const cw = _config.country_weights || {};

    renderKeywordTags('positiveKeywordsContainer', ic.positive_keywords || [], 'removePositiveKeyword');
    renderKeywordTags('negativeKeywordsContainer', ic.negative_keywords || [], 'removeNegativeKeyword');

    const sc = ic.scoring || {};
    const im = sc.industry_match || {};
    document.getElementById('industryMaxScore').value = im.max_score ?? 30;
    renderIndustryWeights(im.keywords || {});

    const pm = sc.project_match || {};
    document.getElementById('projectMaxScore').value = pm.max_score ?? 25;
    renderKeywordTags('projectDetectionContainer', pm.detection_keywords || [], 'removeProjectDetectionKw');
    renderKeywordTags('projectContentContainer', pm.content_keywords || [], 'removeProjectContentKw');
    document.getElementById('projectHasProjectBase').value = pm.has_project_base ?? 10;
    document.getElementById('projectHasContentMatch').value = pm.has_content_match ?? 15;
    document.getElementById('projectHasProjectLabel').value = pm.has_project_label ?? '存在项目案例页面';
    document.getElementById('projectHasContentLabel').value = pm.has_content_label ?? '项目涉足目标行业';
    document.getElementById('projectLowRelevanceLabel').value = pm.low_relevance_label ?? '项目与目标行业相关度低';
    document.getElementById('projectLowRelevance').value = pm.low_relevance ?? 5;

    const ct = sc.company_type || {};
    document.getElementById('companyTypeMaxScore').value = ct.max_score ?? 20;
    renderCompanyTypes(ct.types || {});

    renderContactTiers((sc.contact || {}).tiers || []);

    document.getElementById('countryMaxScore').value = (sc.country || {}).max_score ?? 15;
    renderCountryWeights(cw);

    const pr = ic.priority_rules || {};
    document.getElementById('priorityAMin').value = (pr.A || {}).min ?? 80;
    document.getElementById('priorityBMin').value = (pr.B || {}).min ?? 60;
    document.getElementById('priorityCMin').value = (pr.C || {}).min ?? 40;
    document.getElementById('priorityDMin').value = (pr.D || {}).min ?? 0;
}

function renderKeywordTags(containerId, keywords, removeFn) {
    const container = document.getElementById(containerId);
    if (!keywords || keywords.length === 0) {
        container.innerHTML = '<span class="text-muted small">暂无关键词</span>';
        return;
    }
    let html = '';
    keywords.forEach(kw => {
        html += `<span class="keyword-tag">${_esc(kw)} <span class="remove-btn" onclick="${removeFn}('${_esc(kw).replace(/'/g, "\\'")}')">x</span></span>`;
    });
    container.innerHTML = html;
}

function renderIndustryWeights(kwMap) {
    const tbody = document.getElementById('industryWeightsBody');
    const entries = Object.entries(kwMap || {});
    if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-muted small py-2">暂无行业关键词</td></tr>';
        return;
    }
    let html = '';
    entries.forEach(([kw, weight]) => {
        html += `<tr>
            <td>${_esc(kw)}</td>
            <td><input type="number" class="form-control form-control-sm weight-input" value="${weight}" min="1" max="5" data-industry-kw="${_esc(kw).replace(/"/g, '&quot;')}" onchange="updateIndustryWeight(this)"></td>
            <td><span class="text-danger" style="cursor:pointer" onclick="removeIndustryWeight('${_esc(kw).replace(/'/g, "\\'")}')">x</span></td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function renderCompanyTypes(types) {
    const tbody = document.getElementById('companyTypeBody');
    const entries = Object.entries(types || {});
    if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-muted small py-2">暂无公司类型</td></tr>';
        return;
    }
    let html = '';
    entries.forEach(([name, score]) => {
        html += `<tr>
            <td>${_esc(name)}</td>
            <td><input type="number" class="form-control form-control-sm weight-input" value="${score}" min="0" max="20" data-ct-name="${_esc(name).replace(/"/g, '&quot;')}" onchange="updateCompanyTypeScore(this)"></td>
            <td><span class="text-danger" style="cursor:pointer" onclick="removeCompanyType('${_esc(name).replace(/'/g, "\\'")}')">x</span></td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function renderContactTiers(tiers) {
    const tbody = document.getElementById('contactTiersBody');
    if (!tiers || tiers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-muted small py-2">暂无阶梯配置</td></tr>';
        return;
    }
    let html = '';
    tiers.forEach((tier, idx) => {
        html += `<tr>
            <td><input type="number" class="form-control form-control-sm" value="${tier.min_emails}" min="0" data-tier-idx="${idx}" onchange="updateTier(${idx}, 'min_emails', this.value)"></td>
            <td><input type="number" class="form-control form-control-sm weight-input" value="${tier.score}" min="0" max="10" data-tier-idx="${idx}" onchange="updateTier(${idx}, 'score', this.value)"></td>
            <td><span class="text-danger" style="cursor:pointer" onclick="removeTier(${idx})">x</span></td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function renderCountryWeights(cw) {
    const tbody = document.getElementById('countryWeightsBody');
    const entries = Object.entries(cw || {});
    if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-muted small py-2">暂无国家权重</td></tr>';
        return;
    }
    let html = '';
    entries.forEach(([country, weight]) => {
        html += `<tr>
            <td>${_esc(country)}</td>
            <td><input type="number" class="form-control form-control-sm weight-input" value="${weight}" min="0" max="15" data-country="${_esc(country).replace(/"/g, '&quot;')}" onchange="updateCountryWeight(this)"></td>
            <td><span class="text-danger" style="cursor:pointer" onclick="removeCountryWeight('${_esc(country).replace(/'/g, "\\'")}')">x</span></td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

// ═══════════════════════════════════════════
// CRUD 操作
// ═══════════════════════════════════════════

function addPositiveKeyword() {
    const input = document.getElementById('newPositiveKeyword');
    const kw = input.value.trim();
    if (!kw) return;
    const list = _config.industry_config.positive_keywords || [];
    if (list.includes(kw)) { showToast('关键词已存在', 'warning'); return; }
    list.push(kw);
    renderKeywordTags('positiveKeywordsContainer', list, 'removePositiveKeyword');
    input.value = '';
    markDirty();
}
function removePositiveKeyword(kw) {
    const list = _config.industry_config.positive_keywords || [];
    const idx = list.indexOf(kw);
    if (idx > -1) list.splice(idx, 1);
    renderKeywordTags('positiveKeywordsContainer', list, 'removePositiveKeyword');
    markDirty();
}

function addNegativeKeyword() {
    const input = document.getElementById('newNegativeKeyword');
    const kw = input.value.trim();
    if (!kw) return;
    const list = _config.industry_config.negative_keywords || [];
    if (list.includes(kw)) { showToast('关键词已存在', 'warning'); return; }
    list.push(kw);
    renderKeywordTags('negativeKeywordsContainer', list, 'removeNegativeKeyword');
    input.value = '';
    markDirty();
}
function removeNegativeKeyword(kw) {
    const list = _config.industry_config.negative_keywords || [];
    const idx = list.indexOf(kw);
    if (idx > -1) list.splice(idx, 1);
    renderKeywordTags('negativeKeywordsContainer', list, 'removeNegativeKeyword');
    markDirty();
}

function addIndustryWeight() {
    const kw = document.getElementById('newIndustryKw').value.trim();
    const wt = parseInt(document.getElementById('newIndustryWt').value) || 3;
    if (!kw) return;
    const keywords = _config.industry_config.scoring.industry_match.keywords || {};
    if (keywords[kw] !== undefined) { showToast('关键词已存在', 'warning'); return; }
    keywords[kw] = wt;
    renderIndustryWeights(keywords);
    document.getElementById('newIndustryKw').value = '';
    markDirty();
}
function updateIndustryWeight(input) {
    const kw = input.dataset.industryKw;
    const val = parseInt(input.value) || 1;
    _config.industry_config.scoring.industry_match.keywords[kw] = Math.min(Math.max(val, 1), 5);
    markDirty();
}
function removeIndustryWeight(kw) {
    delete _config.industry_config.scoring.industry_match.keywords[kw];
    renderIndustryWeights(_config.industry_config.scoring.industry_match.keywords);
    markDirty();
}

function addProjectDetectionKw() {
    const input = document.getElementById('newProjectDetectKw');
    const kw = input.value.trim();
    if (!kw) return;
    const list = _config.industry_config.scoring.project_match.detection_keywords || [];
    if (list.includes(kw)) { showToast('关键词已存在', 'warning'); return; }
    list.push(kw);
    renderKeywordTags('projectDetectionContainer', list, 'removeProjectDetectionKw');
    input.value = '';
    markDirty();
}
function removeProjectDetectionKw(kw) {
    const list = _config.industry_config.scoring.project_match.detection_keywords || [];
    const idx = list.indexOf(kw);
    if (idx > -1) list.splice(idx, 1);
    renderKeywordTags('projectDetectionContainer', list, 'removeProjectDetectionKw');
    markDirty();
}

function addProjectContentKw() {
    const input = document.getElementById('newProjectContentKw');
    const kw = input.value.trim();
    if (!kw) return;
    const list = _config.industry_config.scoring.project_match.content_keywords || [];
    if (list.includes(kw)) { showToast('关键词已存在', 'warning'); return; }
    list.push(kw);
    renderKeywordTags('projectContentContainer', list, 'removeProjectContentKw');
    input.value = '';
    markDirty();
}
function removeProjectContentKw(kw) {
    const list = _config.industry_config.scoring.project_match.content_keywords || [];
    const idx = list.indexOf(kw);
    if (idx > -1) list.splice(idx, 1);
    renderKeywordTags('projectContentContainer', list, 'removeProjectContentKw');
    markDirty();
}

function addCompanyType() {
    const name = document.getElementById('newCompanyType').value.trim();
    const score = parseInt(document.getElementById('newCompanyTypeScore').value) || 0;
    if (!name) return;
    const types = _config.industry_config.scoring.company_type.types || {};
    if (types[name] !== undefined) { showToast('公司类型已存在', 'warning'); return; }
    types[name] = Math.min(Math.max(score, 0), 20);
    renderCompanyTypes(types);
    document.getElementById('newCompanyType').value = '';
    markDirty();
}
function updateCompanyTypeScore(input) {
    const name = input.dataset.ctName;
    const val = parseInt(input.value) || 0;
    _config.industry_config.scoring.company_type.types[name] = Math.min(Math.max(val, 0), 20);
    markDirty();
}
function removeCompanyType(name) {
    delete _config.industry_config.scoring.company_type.types[name];
    renderCompanyTypes(_config.industry_config.scoring.company_type.types);
    markDirty();
}

function updateTier(idx, field, val) {
    const tiers = _config.industry_config.scoring.contact.tiers || [];
    if (tiers[idx]) tiers[idx][field] = parseInt(val) || 0;
    markDirty();
}
function addTier() {
    const min = parseInt(document.getElementById('newTierMin').value) || 0;
    const score = parseInt(document.getElementById('newTierScore').value) || 0;
    const tiers = _config.industry_config.scoring.contact.tiers || [];
    tiers.push({ min_emails: min, score: score });
    renderContactTiers(tiers);
    document.getElementById('newTierMin').value = '0';
    document.getElementById('newTierScore').value = '0';
    markDirty();
}
function removeTier(idx) {
    const tiers = _config.industry_config.scoring.contact.tiers || [];
    tiers.splice(idx, 1);
    renderContactTiers(tiers);
    markDirty();
}

function addCountryWeight() {
    const country = document.getElementById('newCountry').value.trim();
    const weight = parseInt(document.getElementById('newCountryWeight').value) || 5;
    if (!country) return;
    if (_config.country_weights[country] !== undefined) { showToast('国家已存在', 'warning'); return; }
    _config.country_weights[country] = Math.min(Math.max(weight, 0), 15);
    renderCountryWeights(_config.country_weights);
    document.getElementById('newCountry').value = '';
    markDirty();
}
function updateCountryWeight(input) {
    const country = input.dataset.country;
    const val = parseInt(input.value) || 0;
    _config.country_weights[country] = Math.min(Math.max(val, 0), 15);
    markDirty();
}
function removeCountryWeight(country) {
    delete _config.country_weights[country];
    renderCountryWeights(_config.country_weights);
    markDirty();
}

// ═══════════════════════════════════════════
// 保存配置
// ═══════════════════════════════════════════
async function saveConfig() {
    if (!_config) return;

    const ic = _config.industry_config;
    const sc = ic.scoring;

    sc.industry_match.max_score = parseInt(document.getElementById('industryMaxScore').value) || 30;
    sc.project_match.max_score = parseInt(document.getElementById('projectMaxScore').value) || 25;
    sc.project_match.has_project_base = parseInt(document.getElementById('projectHasProjectBase').value) || 10;
    sc.project_match.has_content_match = parseInt(document.getElementById('projectHasContentMatch').value) || 15;
    sc.project_match.low_relevance = parseInt(document.getElementById('projectLowRelevance').value) || 5;
    sc.project_match.has_project_label = document.getElementById('projectHasProjectLabel').value.trim() || '存在项目案例页面';
    sc.project_match.has_content_label = document.getElementById('projectHasContentLabel').value.trim() || '项目涉足目标行业';
    sc.project_match.low_relevance_label = document.getElementById('projectLowRelevanceLabel').value.trim() || '项目与目标行业相关度低';

    sc.company_type.max_score = parseInt(document.getElementById('companyTypeMaxScore').value) || 20;
    sc.country.max_score = parseInt(document.getElementById('countryMaxScore').value) || 15;

    ic.priority_rules = {
        "A": { "min": parseInt(document.getElementById('priorityAMin').value) || 80, "max": 100 },
        "B": { "min": parseInt(document.getElementById('priorityBMin').value) || 60, "max": 79 },
        "C": { "min": parseInt(document.getElementById('priorityCMin').value) || 40, "max": 59 },
        "D": { "min": parseInt(document.getElementById('priorityDMin').value) || 0, "max": 39 },
    };

    try {
        await _fetchWithTimeout('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ic),
        }, 10000);

        await _fetchWithTimeout('/api/config/country-weights', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_config.country_weights),
        }, 10000);

        showToast('配置已保存，新评分规则已生效', 'success');
        _dirty = false;
    } catch (err) {
        showToast('保存失败: ' + err.message, 'danger');
    }
}

// ═══════════════════════════════════════════
// JSON 预览
// ═══════════════════════════════════════════
function toggleJsonPreview() {
    const body = document.getElementById('jsonPreviewBody');
    body.classList.toggle('d-none');
    if (!body.classList.contains('d-none')) {
        document.getElementById('jsonPreviewContent').textContent =
            JSON.stringify(_config.industry_config, null, 2);
    }
}

// ═══════════════════════════════════════════
// 离开时提示未保存
// ═══════════════════════════════════════════
window.addEventListener('beforeunload', (e) => {
    if (_dirty) {
        e.preventDefault();
        e.returnValue = '有未保存的配置修改，确定离开吗？';
    }
});

// ═══════════════════════════════════════════
// 初始化
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', loadConfig);
