/**
 * 数据同步页面 - 交互逻辑
 * 提供导出、导入、备份、恢复的一键操作
 * V3.5.0
 */

// ─── 页面初始化 ───
document.addEventListener('DOMContentLoaded', () => {
    refreshStatus();
    loadBackups();
});

// ─── 刷新状态 ───
async function refreshStatus() {
    const btn = document.querySelector('.top-bar-right .btn');
    if (btn) btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新中...';

    try {
        // 获取统计
        const statsResp = await fetch('/api/stats');
        if (statsResp.ok) {
            const stats = await statsResp.json();
            document.getElementById('statCustomers').textContent = stats.total ?? '-';
            document.getElementById('statAnalyzed').textContent = stats.analyzed ?? '-';
        }

        // 获取数据库大小
        const dbResp = await fetch('/api/sync/backups');
        if (dbResp.ok) {
            const data = await dbResp.json();
            document.getElementById('statBackups').textContent = data.backups.length;
        }

        // 获取 DB 文件大小（后台无直接接口时显示备份目录信息）
        document.getElementById('statDbSize').textContent = '运行中';

    } catch (e) {
        console.warn('状态刷新失败:', e);
    } finally {
        if (btn) btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新';
    }
}

// ─── 导出 ───
async function doExport() {
    const btn = document.getElementById('btnExport');
    const info = document.getElementById('exportInfo');
    const result = document.getElementById('exportResult');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 正在导出...';
    info.textContent = '';
    result.style.display = 'none';

    try {
        const resp = await fetch('/api/sync/export');
        if (!resp.ok) throw new Error(`服务器错误: ${resp.status}`);

        const data = await resp.json();
        const stats = data.stats || {};
        const blob = new Blob(
            [JSON.stringify(data, null, 2)],
            { type: 'application/json' }
        );

        // 触发下载
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trade_data_export_${formatDate()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // 显示成功
        result.className = 'results-box success';
        result.innerHTML = `
            <i class="bi bi-check-circle-fill me-1"></i>
            导出成功！
            共 <strong>${stats.customers ?? 0}</strong> 个客户，
            <strong>${stats.search_tasks ?? 0}</strong> 个搜索任务，
            缓存 ${(stats.search_cache ?? 0) + (stats.website_cache ?? 0) + (stats.analysis_cache ?? 0)} 条
        `;
        result.style.display = 'block';
        info.textContent = `${(blob.size / 1024).toFixed(1)} KB`;

    } catch (e) {
        result.className = 'results-box error';
        result.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i> 导出失败: ${e.message}`;
        result.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-download me-1"></i> 导出数据';
    }
}

// ─── 导入 ───
async function doImport(input) {
    const file = input.files[0];
    if (!file) return;

    const btn = document.getElementById('btnImport');
    const info = document.getElementById('importInfo');
    const result = document.getElementById('importResult');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 正在导入...';
    info.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    result.style.display = 'none';

    try {
        // 读取文件内容
        const text = await file.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch {
            throw new Error('文件不是有效的 JSON 格式');
        }

        // 验证数据格式
        if (!data.data || !data.data.customers) {
            throw new Error('文件格式不匹配，请确认是从本系统导出的 JSON 文件');
        }

        // 确认导入
        const stats = data.stats || {};
        const confirmMsg =
            `即将导入:\n` +
            `  · 客户: ${stats.customers ?? 0} 个\n` +
            `  · 搜索任务: ${stats.search_tasks ?? 0} 个\n` +
            `  · 缓存数据: ${(stats.search_cache ?? 0) + (stats.website_cache ?? 0) + (stats.analysis_cache ?? 0)} 条\n\n` +
            `已存在的客户会自动跳过，不会重复创建。\n确定继续吗？`;

        if (!confirm(confirmMsg)) {
            result.className = 'results-box';
            result.innerHTML = `<i class="bi bi-info-circle me-1"></i> 已取消导入`;
            result.style.display = 'block';
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-upload me-1"></i> 选择文件并导入';
            return;
        }

        // 发送导入请求
        const resp = await fetch('/api/sync/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误: ${resp.status}`);
        }

        const resultData = await resp.json();
        const imp = resultData.imported || {};

        result.className = 'results-box success';
        result.innerHTML = `
            <i class="bi bi-check-circle-fill me-1"></i>
            导入完成！新增客户 <strong>${imp.customers ?? 0}</strong> 个，
            跳过重复 <strong>${imp.customers_skipped ?? 0}</strong> 个，
            导入任务 <strong>${imp.search_tasks ?? 0}</strong> 个
        `;
        result.style.display = 'block';

        // 刷新状态
        refreshStatus();

    } catch (e) {
        result.className = 'results-box error';
        result.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i> 导入失败: ${e.message}`;
        result.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-upload me-1"></i> 选择文件并导入';
        input.value = ''; // 重置文件选择器
    }
}

// ─── 备份 ───
async function doBackup() {
    const btn = document.getElementById('btnBackup');
    const info = document.getElementById('backupInfo');
    const result = document.getElementById('backupResult');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 正在备份...';
    info.textContent = '';
    result.style.display = 'none';

    try {
        const resp = await fetch('/api/sync/backup', { method: 'POST' });
        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误: ${resp.status}`);
        }

        const data = await resp.json();

        result.className = 'results-box success';
        result.innerHTML = `
            <i class="bi bi-check-circle-fill me-1"></i>
            备份成功！文件: <code>${data.file}</code> (${data.size_str})
        `;
        result.style.display = 'block';
        info.textContent = data.size_str;

        // 刷新备份列表
        loadBackups();
        refreshStatus();

    } catch (e) {
        result.className = 'results-box error';
        result.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i> 备份失败: ${e.message}`;
        result.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-save2 me-1"></i> 立即备份';
    }
}

// ─── 加载备份列表 ───
async function loadBackups() {
    const select = document.getElementById('restoreSelect');
    const tbody = document.getElementById('backupsBody');
    const btn = document.getElementById('btnRefreshBackups');

    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    const prevSelected = select.value;

    try {
        const resp = await fetch('/api/sync/backups');
        if (!resp.ok) throw new Error(`服务器错误: ${resp.status}`);

        const data = await resp.json();
        const backups = data.backups || [];

        // 更新下拉框
        const currentSelection = select.value;
        select.innerHTML = '<option value="">-- 选择备份文件 --</option>';
        if (backups.length === 0) {
            select.innerHTML = '<option value="">-- 暂无备份 --</option>';
            document.getElementById('btnRestore').disabled = true;
        } else {
            backups.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b.name;
                opt.textContent = `${b.name} (${b.size_str}, ${b.modified})`;
                select.appendChild(opt);
            });
            // 恢复之前的选中
            if (currentSelection && [...select.options].some(o => o.value === currentSelection)) {
                select.value = currentSelection;
            }
            document.getElementById('btnRestore').disabled = !select.value;
        }

        // 更新表格
        if (backups.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-secondary py-4">
                        <i class="bi bi-inbox me-2"></i>暂无备份，点击"立即备份"创建
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = backups.map(b => `
                <tr>
                    <td><code>${b.name}</code></td>
                    <td>${b.size_str}</td>
                    <td>${b.modified}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-danger" onclick="confirmRestore('${b.name}')">
                            <i class="bi bi-arrow-counterclockwise"></i> 恢复
                        </button>
                    </td>
                </tr>
            `).join('');
        }

    } catch (e) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="text-center text-danger py-4">
                    <i class="bi bi-exclamation-circle me-2"></i>加载失败: ${e.message}
                </td>
            </tr>
        `;
    } finally {
        btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
    }
}

// ─── 恢复（从下拉框） ───
async function doRestore() {
    const select = document.getElementById('restoreSelect');
    const name = select.value;
    if (!name) return;
    confirmRestore(name);
}

// ─── 恢复（通用） ───
async function confirmRestore(name) {
    const result = document.getElementById('restoreResult');
    result.style.display = 'none';

    const msg =
        `⚠️ 恢复操作将覆盖当前数据库！\n\n` +
        `备份文件: ${name}\n\n` +
        `恢复前会自动备份当前数据。\n` +
        `但建议你也手动备份一次。\n\n` +
        `确定继续吗？`;

    if (!confirm(msg)) {
        result.className = 'results-box';
        result.innerHTML = `<i class="bi bi-info-circle me-1"></i> 已取消恢复`;
        result.style.display = 'block';
        return;
    }

    // 二次确认
    if (!confirm('最后确认：真的要恢复这个备份吗？当前数据将被替换。')) {
        return;
    }

    const btn = document.getElementById('btnRestore');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 正在恢复...';

    try {
        const resp = await fetch(`/api/sync/restore?name=${encodeURIComponent(name)}`, {
            method: 'POST',
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误: ${resp.status}`);
        }

        const data = await resp.json();

        result.className = 'results-box success';
        result.innerHTML = `
            <i class="bi bi-check-circle-fill me-1"></i>
            恢复成功！<br>
            ${data.backup_before ? `当前数据已备份到 <code>${data.backup_before}</code><br>` : ''}
            <strong>请重启程序使数据生效。</strong>
        `;
        result.style.display = 'block';

    } catch (e) {
        result.className = 'results-box error';
        result.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i> 恢复失败: ${e.message}`;
        result.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i> 恢复';
    }
}

// ─── 工具函数 ───
function formatDate() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}
