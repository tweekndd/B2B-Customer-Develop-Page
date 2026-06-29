/* ============================================
   AI Trade Customer Analyzer V3.2.4 - 地理分布地图页
   ============================================ */

// ── 全局变量 ──
let map = null;
let markerCluster = null;
let tileLayer = null;

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
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        maxClusterRadius: 50,
        disableClusteringAtZoom: 15,
    });

    map.addLayer(markerCluster);
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
    const country = document.getElementById('countryFilter').value;
    const url = country
        ? '/api/customers/map?country=' + encodeURIComponent(country)
        : '/api/customers/map';

    document.getElementById('mapStatus').textContent = '加载中...';

    try {
        const data = await _fetchWithTimeout(url);
        const customers = Array.isArray(data) ? data : (data.customers || []);
        updateMap(customers);
        updateCountryFilter(customers);
        updateStats(data.stats);
    } catch (err) {
        console.error('加载地图数据失败:', err);
        document.getElementById('mapStatus').textContent = '加载失败';
        showToast('加载地图数据失败: ' + err.message, 'danger');
    }
}

// ── 更新地图标记 ──
function updateMap(customers) {
    markerCluster.clearLayers();

    if (!customers || customers.length === 0) {
        document.getElementById('mapStatus').textContent = '暂无客户数据';
        return;
    }

    let markerCount = 0;

    customers.forEach(function(c) {
        const lat = parseFloat(c.latitude);
        const lng = parseFloat(c.longitude);
        if (!lat || !lng || isNaN(lat) || isNaN(lng)) return;

        const score = c.total_score != null ? c.total_score : '-';
        const status = c.status || '未知';
        const priority = c.priority || '-';
        const city = c.city || '';
        const location = city
            ? _esc(c.country || '未知') + ' / ' + _esc(city)
            : _esc(c.country || '未知');

        const popupContent = '<strong>' + _esc(c.name) + '</strong><br>'
            + '📍 ' + location + '<br>'
            + '⭐ 评分：' + score + '<br>'
            + '📌 状态：' + _esc(status) + '<br>'
            + '🏷 优先级：' + _esc(priority);

        const marker = L.marker([lat, lng]);
        marker.bindPopup(popupContent);
        markerCluster.addLayer(marker);
        markerCount++;
    });

    document.getElementById('mapStatus').textContent = '显示 ' + markerCount + ' / ' + customers.length + ' 个客户';

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

// ── 批量地理编码 ──
async function runGeocode() {
    const btn = document.getElementById('btnGeocode');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>编码中...';

    try {
        const result = await _fetchWithTimeout('/api/customers/geocode/batch', { method: 'POST' }, 300000);
        showToast(result.message || '批量地理编码完成', 'success');
        loadMapData();
    } catch (err) {
        showToast('地理编码失败: ' + err.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-globe2 me-1"></i>批量地理编码';
    }
}

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    loadMapData();

    // 延迟触发 invalidateSize 确保地图正确渲染
    setTimeout(function() { if (map) map.invalidateSize(); }, 300);
});
