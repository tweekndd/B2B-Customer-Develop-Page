/* ============================================
   AI Trade Customer Analyzer - 共享工具函数 & 动画
   ============================================ */

(function() {
    'use strict';

    // ═══════════════════════════════════════════
    // 初始化：IntersectionObserver 滚动动画
    // ═══════════════════════════════════════════
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

    // ═══════════════════════════════════════════
    // 数字计数动画
    // ═══════════════════════════════════════════
    window._animateNumber = function(el, target, duration = 800, suffix = '') {
        if (!el) return;
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // easeOutQuart
            const eased = 1 - Math.pow(1 - progress, 4);
            const current = Math.round(start + (target - start) * eased);
            el.textContent = current + suffix;
            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                el.textContent = target + suffix;
            }
        }
        requestAnimationFrame(update);
    };

    // ═══════════════════════════════════════════
    // 带超时的 fetch 请求
    // ═══════════════════════════════════════════
    window._fetchWithTimeout = async function(url, options = {}, timeout = 15000) {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
            });
            clearTimeout(id);
            if (!response.ok) {
                const text = await response.text();
                let msg;
                try {
                    msg = JSON.parse(text).detail || text;
                } catch {
                    msg = text;
                }
                throw new Error(`HTTP ${response.status}: ${msg}`);
            }
            return response.json();
        } catch (err) {
            clearTimeout(id);
            if (err.name === 'AbortError') {
                throw new Error('请求超时，请检查网络连接');
            }
            throw err;
        }
    };

    // ═══════════════════════════════════════════
    // HTML 转义
    // ═══════════════════════════════════════════
    window._esc = function(str) {
        if (!str && str !== 0 && str !== false) return '';
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(String(str)));
        return div.innerHTML;
    };

    // ═══════════════════════════════════════════
    // 安全解析数字 / 数组
    // ═══════════════════════════════════════════
    window._num = function(val, defaultVal = 0) {
        const n = parseInt(val);
        return isNaN(n) ? defaultVal : n;
    };

    window._arr = function(val) {
        if (Array.isArray(val)) return val;
        if (typeof val === 'string') {
            try { return JSON.parse(val); } catch { return []; }
        }
        return [];
    };

    // ═══════════════════════════════════════════
    // Toast 通知（带滑动进入动画）
    // ═══════════════════════════════════════════
    window.showToast = function(message, type = 'success', duration = 3000) {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const icons = {
            success: 'bi-check-circle-fill',
            danger: 'bi-exclamation-triangle-fill',
            warning: 'bi-exclamation-circle-fill',
            info: 'bi-info-circle-fill',
        };

        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${type} border-0 show`;
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${icons[type] || icons.info} me-2"></i>
                    ${window._esc(message)}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        container.appendChild(toastEl);

        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: duration });
            toast.show();
            toastEl.addEventListener('hidden.bs.toast', () => {
                toastEl.remove();
            });
        } else {
            setTimeout(() => {
                toastEl.style.transition = 'opacity 0.3s, transform 0.3s';
                toastEl.style.opacity = '0';
                toastEl.style.transform = 'translateX(40px)';
                setTimeout(() => toastEl.remove(), 300);
            }, duration);
        }
    };

    // ═══════════════════════════════════════════
    // 格式化日期
    // ═══════════════════════════════════════════
    window._fmtDate = function(dateStr) {
        if (!dateStr) return '-';
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            const pad = n => String(n).padStart(2, '0');
            return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
        } catch {
            return dateStr;
        }
    };

    // ═══════════════════════════════════════════
    // 格式化评分等级
    // ═══════════════════════════════════════════
    window._gradeLabel = function(score) {
        if (score >= 80) return { label: 'A', cls: 'grade-A' };
        if (score >= 60) return { label: 'B', cls: 'grade-B' };
        if (score >= 40) return { label: 'C', cls: 'grade-C' };
        return { label: 'D', cls: 'grade-D' };
    };

    // ═══════════════════════════════════════════
    // 复制文本到剪贴板
    // ═══════════════════════════════════════════
    window._copyText = function(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(() => {});
        } else {
            const ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
    };

})();
