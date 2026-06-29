/* ============================================
   AI Trade Customer Analyzer V3.2.3 - 工具函数 & 全局行为
   ============================================ */

// ═══════════════════════════════════════════
// IntersectionObserver 滚动动画
// ═══════════════════════════════════════════
(function() {
    'use strict';

    if (typeof window !== 'undefined' && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('[data-animate]').forEach(el => observer.observe(el));
        });
    }
})();

// ═══════════════════════════════════════════
// 页面过渡动画
// ═══════════════════════════════════════════
const transitionEl = document.getElementById('pageTransition');

function navigate(event, url) {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.button === 1) return;
    if (window.location.pathname === url) return;
    event.preventDefault();
    transitionEl.style.opacity = '1';
    setTimeout(() => { window.location.href = url; }, 200);
}

(function() {
    document.addEventListener('DOMContentLoaded', () => {
        if (transitionEl) {
            transitionEl.style.opacity = '1';
            requestAnimationFrame(() => {
                transitionEl.style.transition = 'opacity 0.4s ease';
                transitionEl.style.opacity = '0';
                setTimeout(() => { transitionEl.style.transition = ''; }, 500);
            });
        }
        // 加载导航统计
        loadNavStats();
        // 恢复主题偏好
        const savedTheme = localStorage.getItem('theme') || 'light';
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            document.getElementById('themeIcon').className = 'bi bi-sun';
            document.getElementById('themeLabel').textContent = '亮色模式';
        }
    });
})();

// ═══════════════════════════════════════════
// Sidebar 切换（移动端）
// ═══════════════════════════════════════════
function toggleSidebar() {
    const sidebar = document.getElementById('appSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    if (sidebar.classList.contains('open')) {
        overlay.classList.remove('d-none');
        setTimeout(() => overlay.style.opacity = '1', 10);
    } else {
        overlay.style.opacity = '0';
        setTimeout(() => overlay.classList.add('d-none'), 300);
    }
}

// ═══════════════════════════════════════════
// 暗色模式切换
// ═══════════════════════════════════════════
function toggleTheme() {
    const html = document.documentElement;
    const icon = document.getElementById('themeIcon');
    const label = document.getElementById('themeLabel');
    const isDark = html.getAttribute('data-theme') === 'dark';

    if (isDark) {
        html.setAttribute('data-theme', 'light');
        icon.className = 'bi bi-moon-stars';
        label.textContent = '暗色模式';
        localStorage.setItem('theme', 'light');
    } else {
        html.setAttribute('data-theme', 'dark');
        icon.className = 'bi bi-sun';
        label.textContent = '亮色模式';
        localStorage.setItem('theme', 'dark');
    }
}

// ═══════════════════════════════════════════
// 导航统计
// ═══════════════════════════════════════════
async function loadNavStats() {
    try {
        const s = await _fetchWithTimeout('/api/stats');
        document.getElementById('navStatsText').textContent = `${s.total} 客户 | ${s.analyzed} 已分析`;
    } catch (err) {
        document.getElementById('navStatsText').textContent = '统计数据加载失败';
    }
}

// ═══════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════
function _esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function _num(val, fallback) {
    const n = parseInt(val);
    return isNaN(n) ? (fallback !== undefined ? fallback : 0) : n;
}

function _arr(val) {
    return Array.isArray(val) ? val : (val ? [val] : []);
}

function _fmtDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

function _gradeLabel(score) {
    const s = _num(score);
    if (s >= 80) return { label: 'A', cls: 'grade-A' };
    if (s >= 60) return { label: 'B', cls: 'grade-B' };
    if (s >= 40) return { label: 'C', cls: 'grade-C' };
    return { label: 'D', cls: 'grade-D' };
}

function _animateNumber(el, target) {
    if (!el) return;
    const start = parseInt(el.textContent) || 0;
    if (start === target) return;
    const duration = 600;
    const steps = 20;
    const increment = (target - start) / steps;
    let current = start;
    let step = 0;
    const timer = setInterval(() => {
        step++;
        current += increment;
        el.textContent = Math.round(current);
        if (step >= steps) {
            el.textContent = target;
            clearInterval(timer);
        }
    }, duration / steps);
}

function _copyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到剪贴板', 'success');
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('已复制到剪贴板', 'success');
    });
}

// ═══════════════════════════════════════════
// Toast 提示
// ═══════════════════════════════════════════
function showToast(message, type) {
    type = type || 'info';
    const container = document.getElementById('toastContainer');
    const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
    const icon = icons[type] || icons.info;
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `<div class="d-flex align-items-center"><i class="bi ${icon} me-2 fs-5"></i><div>${_esc(message)}</div></div>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.transition = 'all 0.3s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ═══════════════════════════════════════════
// 通用 fetch（带超时）
// ═══════════════════════════════════════════
async function _fetchWithTimeout(url, options, timeout) {
    timeout = timeout || 15000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(timer);
        if (!response.ok) {
            let detail = '';
            try {
                const errData = await response.json();
                detail = errData.detail || errData.message || '';
            } catch (e) { /* ignore */ }
            throw new Error(detail || `HTTP ${response.status}`);
        }
        return await response.json();
    } catch (err) {
        clearTimeout(timer);
        if (err.name === 'AbortError') throw new Error('请求超时');
        throw err;
    }
}
