/* ============================================
   AI Trade Customer Analyzer V3.2.5 - 地理分布地图页
   修复: !lat 排除赤道、主题切换瓦片不变、标记叠加 jitter
   ============================================ */

// ── 工具函数 ──
function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ── 全局变量 ──
let map = null;
let markerCluster = null;
let tileLayer = null;
let themeObserver = null;
let currentAbortController = null;
let resizeObserver = null;

// ── 获取瓦片 URL（根据主题） ──
function getTileUrl() {
    const theme = document.documentElement.getAttribute('data-theme') || 'light';
    if (theme === 'dark') {
        return 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
    }
    return 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
}

function getTileAttribution() {
    const theme = document.documentElement.getAttribute('data-theme') || 'light';
    if (theme === 'dark') {
        return '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>';
    }
    return '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
}

// ── 替换瓦片层（主题切换时调用） ──
function replaceTileLayer() {
    if (!tileLayer || !map) return;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(getTileUrl(), {
        attribution: getTileAttribution(),
        maxZoom: 19,
        minZoom: 2,
    }).addTo(map);
}

// ── 监听主题切换 ──
function watchThemeChange() {
    if (themeObserver) themeObserver.disconnect();
    themeObserver = new MutationObserver(function() {
        replaceTileLayer();
    });
    themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme'],
    });
}

// ── 初始化地图 ──
function initMap() {
    map = L.map('mapContainer', {
        center: [20, 0],
        zoom: 2,
        zoomControl: true,
        attributionControl: true,
    });

    tileLayer = L.tileLayer(getTileUrl(), {
        attribution: getTileAttribution(),
        maxZoom: 19,
        minZoom: 2,
    }).addTo(map);

    markerCluster = L.markerClusterGroup({
        chunkedLoading: true,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: true,
        zoomToBoundsOnClick: true,
        maxClusterRadius: 80,
        disableClusteringAtZoom: 15,
    });

    map.addLayer(markerCluster);
    watchThemeChange();

    // ResizeObserver 替代硬编码 setTimeout
    resizeObserver = new ResizeObserver(function() {
        if (map) map.invalidateSize();
    });
    resizeObserver.observe(document.getElementById('mapContainer'));
}

// ── 前端标记抖动：相同坐标分散开 ──
function _addJitter(lat, lng, jitterDeg) {
    jitterDeg = jitterDeg || 0.3;
    return [
        lat + (Math.random() - 0.5) * jitterDeg,
        lng + (Math.random() - 0.5) * jitterDeg,
    ];
}

// ── 更新统计卡片 ──
function updateStats(stats) {
    stats = stats || {};
    _animateNumber(document.getElementById('totalCount'), stats.total || 0);
    _animateNumber(document.getElementById('geocodedCount'), stats.geocoded || 0);
    _animateNumber(document.getElementById('pendingCount'), stats.pending || 0);
    _animateNumber(document.getElementById('countryCount'), stats.countries || 0);
}

// ── 加载地图数据 ──
async function loadMapData() {
    // 取消前一个未完成请求
    if (currentAbortController) currentAbortController.abort();
    currentAbortController = new AbortController();

    const country = document.getElementById('countryFilter').value;
    const url = country
        ? '/api/customers/map?country=' + encodeURIComponent(country)
        : '/api/customers/map';

    document.getElementById('mapStatus').textContent = '加载中...';

    // 在地图容器上添加 loading 状态
    const container = document.getElementById('mapContainer');
    container.classList.add('map-loading');

    try {
        const data = await _fetchWithTimeout(url, { signal: currentAbortController.signal });
        const customers = Array.isArray(data) ? data : (data.customers || []);
        updateMap(customers);
        updateCountryFilter(customers);
        updateStats(data.stats);
        document.getElementById('mapStatus').textContent = '';
    } catch (err) {
        if (err.name === 'AbortError') return; // 被新请求取消，忽略
        console.error('加载地图数据失败:', err);
        document.getElementById('mapStatus').textContent = '加载失败';
        showToast('加载地图数据失败: ' + err.message, 'danger');
    } finally {
        container.classList.remove('map-loading');
    }
}

// ── 更新地图标记 ──
function updateMap(customers) {
    markerCluster.clearLayers();

    if (!customers || customers.length === 0) {
        document.getElementById('mapStatus').textContent = '暂无已定位的客户数据';
        showEmptyOverlay();
        return;
    }
    hideEmptyOverlay();

    let markerCount = 0;
    let hasJitter = false;

    customers.forEach(function(c) {
        const lat = parseFloat(c.latitude);
        const lng = parseFloat(c.longitude);

        // 【修复】使用 isNaN 替代 !lat，避免排除赤道（lat=0）客户
        if (isNaN(lat) || isNaN(lng)) return;

        const hasCity = c.city && c.city.trim();
        var markerLat = lat;
        var markerLng = lng;

        // 无城市数据时前端补 jitter（与后端双重保障）
        if (!hasCity) {
            var jittered = _addJitter(lat, lng, 0.3);
            markerLat = jittered[0];
            markerLng = jittered[1];
            hasJitter = true;
        }

        const score = c.total_score != null ? c.total_score : '-';
        const status = c.status || '未知';
        const priority = c.priority || '-';

        // 显示城市信息
        var locationText;
        if (hasCity) {
            locationText = _esc(c.country || '未知') + ' / ' + _esc(c.city);
        } else {
            locationText = _esc(c.country || '未知');
        }

        const popupContent = '<strong>' + _esc(c.name) + '</strong><br>'
            + '<i class="bi bi-geo-alt-fill"></i> ' + locationText + '<br>'
            + '<i class="bi bi-star-fill"></i> 评分：' + score + '<br>'
            + '<i class="bi bi-check-circle-fill"></i> 状态：' + _esc(status) + '<br>'
            + '<a href="/customer/' + c.id + '" target="_blank" class="btn btn-sm btn-outline-primary mt-2" style="text-decoration:none"><i class="bi bi-box-arrow-up-right me-1"></i>查看详情</a>';

        const marker = L.marker([markerLat, markerLng]);
        marker.bindPopup(popupContent);
        markerCluster.addLayer(marker);
        markerCount++;
    });

    var statusMsg = '显示 ' + markerCount + ' / ' + customers.length + ' 个客户';
    if (hasJitter) statusMsg += '（部分标记已自动分散）';
    document.getElementById('mapStatus').textContent = statusMsg;

    // 如果有标记，自适应视图
    if (markerCount > 0) {
        try {
            map.fitBounds(markerCluster.getBounds(), {
                padding: [30, 30],
                maxZoom: 12,
            });
        } catch (e) {
            // 单个标记时 getBounds 可能失败
        }
    }
}

// ── 空状态覆盖层 ──
function showEmptyOverlay() {
    if (document.getElementById('mapEmptyOverlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'mapEmptyOverlay';
    overlay.className = 'map-empty-overlay';
    overlay.innerHTML = '<div class="map-empty-icon"><i class="bi bi-globe2"></i></div>'
        + '<div class="map-empty-text">暂无已定位的客户数据</div>'
        + '<div class="map-empty-hint">请先执行「批量地理编码」操作，为已有客户生成地图坐标</div>';
    document.getElementById('mapContainer').appendChild(overlay);
}

function hideEmptyOverlay() {
    const overlay = document.getElementById('mapEmptyOverlay');
    if (overlay) overlay.remove();
}

// ── 更新国家筛选下拉框 ──
function updateCountryFilter(customers) {
    const select = document.getElementById('countryFilter');
    if (!customers || customers.length === 0) return;

    const currentValue = select.value;
    const countrySet = {};
    customers.forEach(function(c) {
        if (c.country) countrySet[c.country] = true;
    });
    const countries = Object.keys(countrySet).sort();

    let html = '<option value="">全部国家</option>';
    countries.forEach(function(c) {
        const selected = c === currentValue ? ' selected' : '';
        html += '<option value="' + _esc(c) + '"' + selected + '>' + _esc(c) + '</option>';
    });
    select.innerHTML = html;
}

// ── 批量地理编码（后台任务模式） ──
async function runGeocode() {
    const btn = document.getElementById('btnGeocode');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>提交中...';

    try {
        const result = await _fetchWithTimeout('/api/customers/geocode/batch', { method: 'POST' }, 10000);
        const taskId = result.task_id;

        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>编码中...';

        // 轮询任务状态
        while (true) {
            await new Promise(r => setTimeout(r, 2000));
            const statusRes = await _fetchWithTimeout('/api/customers/geocode/status/' + taskId);

            if (statusRes.status === 'completed') {
                showToast('批量地理编码完成', 'success');
                loadMapData();
                break;
            } else if (statusRes.status === 'failed') {
                showToast('地理编码失败: ' + (statusRes.error || '未知错误'), 'danger');
                break;
            }
            // 'pending' 或 'running' 继续轮询
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            showToast('地理编码失败: ' + err.message, 'danger');
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-globe2 me-1"></i>批量地理编码';
    }
}

// ── 销毁地图（页面切换时清理） ──
function destroyMap() {
    if (themeObserver) {
        themeObserver.disconnect();
        themeObserver = null;
    }
    if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
    }
    if (markerCluster) {
        map.removeLayer(markerCluster);
        markerCluster = null;
    }
    if (tileLayer) {
        map.removeLayer(tileLayer);
        tileLayer = null;
    }
    if (map) {
        map.remove();
        map = null;
    }
}

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    loadMapData();
});

// 页面切换时清理地图，防止 Leaflet 内存泄漏
window.addEventListener('beforeunload', function() {
    destroyMap();
});

// debounce 后的 loadMapData，供筛选器 onchange 调用避免频繁请求
const loadMapDataDebounced = debounce(loadMapData, 300);
window.loadMapDataDebounced = loadMapDataDebounced;
