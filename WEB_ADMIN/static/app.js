// JWT bilan ishlash
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login/';
        return null;
    }
    
    if (!options.headers) options.headers = {};
    options.headers['Authorization'] = `Bearer ${token}`;
    
    let res = await fetch(url, options);
    
    if (res.status === 401) {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
            const refreshRes = await fetch('/api/token/refresh/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({refresh: refreshToken})
            });
            
            if (refreshRes.ok) {
                const data = await refreshRes.json();
                localStorage.setItem('access_token', data.access);
                options.headers['Authorization'] = `Bearer ${data.access}`;
                res = await fetch(url, options);
                return res;
            }
        }
        
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login/';
        return null;
    } else if (res.status === 403) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login/';
        return null;
    }
    
    return res;
}

// API orqali statlarni olish
async function fetchStats() {
    try {
        const res = await fetchWithAuth('/api/stats/');
        if (!res) return;

        const data = await res.json();

        document.getElementById('revenue-today').innerText = data.revenue_today.toLocaleString() + " so'm";
        document.getElementById('revenue-total').innerText = data.revenue_total.toLocaleString() + " so'm";
        document.getElementById('passengers-count').innerText = data.passengers;
        document.getElementById('drivers-count').innerText = data.drivers;

        renderChart(data.chart.labels, data.chart.data);
    } catch (error) {
        console.error("Stats fetching error:", error);
    }
}

// Chart.js orqali grafik chizish
function renderChart(labels, dataPoints) {
    const ctx = document.getElementById('ridesChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: "Buyurtmalar soni",
                data: dataPoints,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#94a3b8', stepSize: 1 }
                },
                x: {
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                legend: { labels: { color: '#f8fafc' } }
            }
        }
    });
}

// Leaflet.js orqali xaritani yurgizish
let map;
let markers = [];

function initMap() {
    // Toshkent markazini boshlang'ich nuqta qilamiz
    map = L.map('live-map').setView([41.311081, 69.240562], 12);

    // Qorong'u (Dark) kartani ulash
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://carto.com/">CARTO</a>'
    }).addTo(map);

    fetchLiveLocations();
    // Har 5 soniyada yangilab turish
    setInterval(fetchLiveLocations, 5000);
}

// Jonli manzillarni olish
async function fetchLiveLocations() {
    try {
        const res = await fetchWithAuth('/api/live/');
        if (!res) return;
        const drivers = await res.json();

        // Eski markerlarni o'chirish
        markers.forEach(m => map.removeLayer(m));
        markers = [];

        // Yangi markerlarni qo'yish
        drivers.forEach(d => {
            const marker = L.marker([d.latitude, d.longitude])
                .bindPopup(`<b>${d.full_name}</b><br>${d.car_model} (${d.car_number})`)
                .addTo(map);
            markers.push(marker);
        });

    } catch (error) {
        console.error("Live map error:", error);
    }
}


window.onload = () => {
    fetchStats();
    initMap();
};
