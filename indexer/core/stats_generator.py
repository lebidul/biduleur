"""
Générateur de dashboard HTML pour les statistiques Bidul.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def get_stats_data(db_path: str) -> List[Dict[str, Any]]:
    """
    Récupère les statistiques d'événements et contenus par Bidul.

    Returns:
        Liste de dicts avec: bidul, events, content, missing
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Récupérer les numéros existants dans la table bidul
    cur.execute("SELECT numero FROM bidul ORDER BY numero")
    existing_biduls = set(row[0] for row in cur.fetchall())

    # Récupérer les stats avec CTE récursive
    cur.execute("""
        WITH RECURSIVE all_numeros(numero) AS (
            SELECT 1
            UNION ALL
            SELECT numero + 1 FROM all_numeros WHERE numero < 308
        )
        SELECT
            a.numero as bidul_numero,
            COUNT(DISTINCT e.id) as nb_evenements,
            COALESCE(COUNT(CASE WHEN ce.artiste IS NOT NULL OR ce.nom_spectacle IS NOT NULL THEN 1 END), 0) as nb_contenus
        FROM all_numeros a
        LEFT JOIN evenement e ON e.bidul_numero = a.numero
        LEFT JOIN contenu_evenement ce ON ce.evenement_id = e.id
        GROUP BY a.numero
        ORDER BY a.numero
    """)

    data = []
    for row in cur.fetchall():
        data.append({
            "bidul": row[0],
            "events": row[1],
            "content": row[2],
            "missing": row[0] not in existing_biduls
        })

    conn.close()
    return data


def generate_html(data: List[Dict[str, Any]], output_path: str) -> str:
    """
    Génère le fichier HTML avec le dashboard.

    Args:
        data: Données des stats par Bidul
        output_path: Chemin du fichier à créer

    Returns:
        Chemin absolu du fichier créé
    """
    data_json = json.dumps(data)
    html_content = HTML_TEMPLATE.replace('__DATA_PLACEHOLDER__', data_json)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content, encoding='utf-8')

    return str(output_file.absolute())


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bidul Indexer - Statistiques</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #111827;
            color: #f3f4f6;
            padding: 20px;
            min-height: 100vh;
        }
        h1 { text-align: center; margin-bottom: 10px; font-size: 1.5rem; }

        .stats {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .stat {
            background: #1f2937;
            padding: 10px 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat.missing { border: 1px solid #831843; }
        .stat.empty { border: 1px solid #991b1b; }
        .stat-label { color: #9ca3af; font-size: 0.8rem; }
        .stat-value { font-size: 1.3rem; font-weight: bold; }
        .stat-value.cyan { color: #06b6d4; }
        .stat-value.amber { color: #f59e0b; }
        .stat-value.green { color: #22c55e; }
        .stat-value.pink { color: #ec4899; }
        .stat-value.red { color: #ef4444; }
        .stat-sub { color: #6b7280; font-size: 0.7rem; }

        .controls {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        .btn {
            background: #374151;
            border: none;
            color: #f3f4f6;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .btn:hover { background: #4b5563; }
        .btn.active { background: #4f46e5; }

        .legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 10px;
            font-size: 0.8rem;
        }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-color { width: 12px; height: 12px; border-radius: 2px; }

        .chart-container {
            background: #1f2937;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            height: 400px;
        }

        .details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }
        .detail-box {
            background: #1f2937;
            padding: 15px;
            border-radius: 8px;
        }
        .detail-box.missing { border: 1px solid #831843; }
        .detail-box h3 { margin-bottom: 10px; font-size: 0.95rem; }
        .detail-box h3.pink { color: #ec4899; }
        .detail-box h3.red { color: #ef4444; }
        .detail-box h3.yellow { color: #eab308; }
        .detail-box h3.purple { color: #a855f7; }
        .detail-list { font-size: 0.85rem; max-height: 150px; overflow-y: auto; }
        .detail-row { display: flex; justify-content: space-between; padding: 2px 0; }
        .mono { font-family: monospace; }

        .footer { text-align: center; margin-top: 20px; color: #6b7280; font-size: 0.8rem; }
    </style>
</head>
<body>
    <h1>Bidul Indexer - Evenements & Contenus par Bidul</h1>

    <div class="stats">
        <div class="stat">
            <div class="stat-label">Evenements</div>
            <div class="stat-value cyan" id="totalEvents">-</div>
            <div class="stat-sub" id="avgEvents">-</div>
        </div>
        <div class="stat">
            <div class="stat-label">Contenus</div>
            <div class="stat-value amber" id="totalContent">-</div>
            <div class="stat-sub" id="avgContent">-</div>
        </div>
        <div class="stat">
            <div class="stat-label">Ratio</div>
            <div class="stat-value green" id="ratio">-</div>
            <div class="stat-sub">contenu/evenement</div>
        </div>
        <div class="stat missing">
            <div class="stat-label">PDFs manquants</div>
            <div class="stat-value pink" id="missingCount">-</div>
        </div>
        <div class="stat empty">
            <div class="stat-label">Biduls vides</div>
            <div class="stat-value red" id="emptyCount">-</div>
        </div>
    </div>

    <div class="controls">
        <button class="btn active" onclick="setView('both')">Les deux</button>
        <button class="btn" onclick="setView('events')">Evenements</button>
        <button class="btn" onclick="setView('content')">Contenus</button>
    </div>

    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background:#06b6d4"></div> Evenements</div>
        <div class="legend-item"><div class="legend-color" style="background:#f59e0b"></div> Artistes/Spectacles</div>
        <div class="legend-item"><div class="legend-color" style="background:#831843; border: 1px solid #be185d"></div> PDF manquant</div>
        <div class="legend-item"><div class="legend-color" style="background:#ef4444"></div> Vide (0)</div>
    </div>

    <div class="chart-container">
        <canvas id="mainChart"></canvas>
    </div>

    <div class="details">
        <div class="detail-box missing">
            <h3 class="pink">PDFs manquants</h3>
            <div class="mono" id="missingList">-</div>
        </div>
        <div class="detail-box">
            <h3 class="red">Biduls vides</h3>
            <div class="detail-list" id="emptyList">-</div>
        </div>
        <div class="detail-box">
            <h3 class="yellow">Ratios anormaux</h3>
            <div class="detail-list" id="anomaliesList">-</div>
        </div>
        <div class="detail-box">
            <h3 class="purple">Top 10 Biduls</h3>
            <div class="detail-list" id="topList">-</div>
        </div>
    </div>

    <div class="footer">
        Genere par Bidul Indexer - <span id="genDate"></span>
    </div>

    <script>
        const data = __DATA_PLACEHOLDER__;

        // Calculs
        const existing = data.filter(d => !d.missing);
        const eventsTotal = existing.reduce((s, d) => s + d.events, 0);
        const contentTotal = existing.reduce((s, d) => s + d.content, 0);
        const eventsAvg = eventsTotal / existing.length;
        const contentAvg = contentTotal / existing.length;
        const ratio = eventsTotal > 0 ? contentTotal / eventsTotal : 0;
        const missingBiduls = data.filter(d => d.missing).map(d => d.bidul);
        const emptyBiduls = data.filter(d => d.events === 0 && !d.missing).map(d => d.bidul);

        // Anomalies (ratio tres different)
        const anomalies = existing.filter(d => {
            if (d.events < 10) return false;
            const r = d.content / d.events;
            return r < 0.5 || r > 3;
        }).map(d => ({ ...d, ratio: (d.content / d.events).toFixed(2) }));

        // Top 10
        const top10 = [...existing].sort((a, b) => b.events - a.events).slice(0, 10);

        // Mise a jour stats
        document.getElementById('totalEvents').textContent = eventsTotal.toLocaleString();
        document.getElementById('avgEvents').textContent = `moy: ${eventsAvg.toFixed(0)}`;
        document.getElementById('totalContent').textContent = contentTotal.toLocaleString();
        document.getElementById('avgContent').textContent = `moy: ${contentAvg.toFixed(0)}`;
        document.getElementById('ratio').textContent = ratio.toFixed(2);
        document.getElementById('missingCount').textContent = missingBiduls.length;
        document.getElementById('emptyCount').textContent = emptyBiduls.length;
        document.getElementById('genDate').textContent = new Date().toLocaleString('fr-FR');

        // Details
        document.getElementById('missingList').textContent = missingBiduls.length > 0 ? missingBiduls.join(', ') : 'Aucun';
        document.getElementById('emptyList').innerHTML = emptyBiduls.length > 0
            ? emptyBiduls.map(b => `<div>Bidul ${b}</div>`).join('')
            : 'Aucun';
        document.getElementById('anomaliesList').innerHTML = anomalies.length > 0
            ? anomalies.slice(0, 10).map(d =>
                `<div class="detail-row"><span>B${d.bidul}</span><span>${d.events}->${d.content}</span><span style="color:${d.ratio < 1 ? '#ef4444' : '#22c55e'}">${d.ratio}</span></div>`
              ).join('')
            : 'Aucun';
        document.getElementById('topList').innerHTML = top10.map((d, i) =>
            `<div class="detail-row"><span>${i+1}. B${d.bidul}</span><span style="color:#06b6d4">${d.events}</span><span style="color:#f59e0b">${d.content}</span></div>`
        ).join('');

        // Couleurs pour les barres
        function getEventColors() {
            return data.map(d => {
                if (d.missing) return '#831843';
                if (d.events === 0) return '#ef4444';
                return '#06b6d4';
            });
        }

        function getContentColors() {
            return data.map(d => {
                if (d.missing) return '#831843';
                if (d.content === 0) return '#ef4444';
                return '#f59e0b';
            });
        }

        // Chart
        const ctx = document.getElementById('mainChart').getContext('2d');
        let chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.bidul),
                datasets: [
                    {
                        label: 'Evenements',
                        data: data.map(d => d.events),
                        backgroundColor: getEventColors(),
                        borderColor: data.map(d => d.missing ? '#be185d' : 'transparent'),
                        borderWidth: data.map(d => d.missing ? 2 : 0),
                    },
                    {
                        label: 'Contenus',
                        data: data.map(d => d.content),
                        backgroundColor: getContentColors(),
                        borderColor: data.map(d => d.missing ? '#be185d' : 'transparent'),
                        borderWidth: data.map(d => d.missing ? 2 : 0),
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1f2937',
                        titleColor: '#f3f4f6',
                        bodyColor: '#9ca3af',
                        callbacks: {
                            title: (items) => `Bidul ${items[0].label}`,
                            label: (item) => {
                                const d = data[item.dataIndex];
                                if (d.missing) return 'PDF MANQUANT';
                                return `${item.dataset.label}: ${item.raw}`;
                            },
                            afterBody: (items) => {
                                const d = data[items[0].dataIndex];
                                if (d.missing || d.events === 0) return '';
                                return `Ratio: ${(d.content / d.events).toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#9ca3af',
                            maxRotation: 90,
                            callback: (val, idx) => idx % 10 === 0 ? data[idx].bidul : ''
                        },
                        grid: { display: false }
                    },
                    y: {
                        ticks: { color: '#9ca3af' },
                        grid: { color: '#374151' }
                    }
                }
            }
        });

        // Boutons de vue
        function setView(view) {
            document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            chart.data.datasets[0].hidden = view === 'content';
            chart.data.datasets[1].hidden = view === 'events';
            chart.update();
        }
    </script>
</body>
</html>'''
