/**
 * HyperMatrix Web - Main Application
 */

const API_BASE = '/api';
let currentScanId = null;
let selectedGroups = new Set();
let pollInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initScanForm();
    initFilters();
    initCompare();
    initRules();
    initModals();
    initBatchActions();
    initExport();
    checkStoredScan();
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            switchView(view);
        });
    });
}

function switchView(viewId) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewId);
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('active', view.id === `view-${viewId}`);
    });

    // Load data if needed
    if (viewId === 'results' && currentScanId) {
        loadResults();
    } else if (viewId === 'rules') {
        loadRules();
    }
}

// Scan Form
function initScanForm() {
    const form = document.getElementById('scan-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await startScan();
    });
}

async function startScan() {
    const path = document.getElementById('scan-path').value;
    const projectName = document.getElementById('project-name').value;
    const includeArchives = document.getElementById('include-archives').checked;
    const detectDuplicates = document.getElementById('detect-duplicates').checked;
    const calcSimilarities = document.getElementById('calc-similarities').checked;

    try {
        setStatus('running', 'Iniciando escaneo...');

        const response = await fetch(`${API_BASE}/scan/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                path,
                project_name: projectName || null,
                include_archives: includeArchives,
                detect_duplicates: detectDuplicates,
                calculate_similarities: calcSimilarities
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al iniciar escaneo');
        }

        const data = await response.json();
        currentScanId = data.scan_id;
        localStorage.setItem('lastScanId', currentScanId);

        // Show progress
        document.getElementById('scan-progress').classList.remove('hidden');

        // Start polling
        startPolling();

    } catch (error) {
        setStatus('error', error.message);
        alert('Error: ' + error.message);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/scan/status/${currentScanId}`);
            const data = await response.json();

            updateProgress(data);

            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(pollInterval);
                pollInterval = null;

                if (data.status === 'completed') {
                    setStatus('ready', 'Escaneo completado');
                    switchView('results');
                } else {
                    setStatus('error', 'Escaneo fallido');
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 1000);
}

function updateProgress(data) {
    const phaseNames = {
        'initializing': 'Inicializando...',
        'discovery': 'Descubrimiento',
        'deduplication': 'Deduplicacion',
        'analysis': 'Analisis',
        'consolidation': 'Consolidacion',
        'completed': 'Completado'
    };

    document.getElementById('phase-name').textContent = phaseNames[data.phase] || data.phase;
    document.getElementById('phase-files').textContent = `${data.processed_files} / ${data.total_files} archivos`;
    document.getElementById('progress-fill').style.width = `${data.phase_progress * 100}%`;
    document.getElementById('current-file').textContent = data.current_file || '-';

    if (data.errors && data.errors.length > 0) {
        const errorsDiv = document.getElementById('scan-errors');
        errorsDiv.classList.remove('hidden');
        errorsDiv.innerHTML = data.errors.map(e => `<div>${e}</div>`).join('');
    }
}

function checkStoredScan() {
    const lastScanId = localStorage.getItem('lastScanId');
    if (lastScanId) {
        currentScanId = lastScanId;
        // Check if scan exists and is completed
        fetch(`${API_BASE}/scan/status/${lastScanId}`)
            .then(r => r.json())
            .then(data => {
                if (data.status === 'completed') {
                    setStatus('ready', 'Listo');
                }
            })
            .catch(() => {
                localStorage.removeItem('lastScanId');
                currentScanId = null;
            });
    }
}

// Results
async function loadResults() {
    if (!currentScanId) {
        document.getElementById('groups-container').innerHTML = `
            <div class="empty-state">
                <p>No hay resultados de escaneo.</p>
            </div>
        `;
        return;
    }

    try {
        // Get filters
        const minAffinity = document.getElementById('filter-affinity').value;
        const search = document.getElementById('filter-search').value;
        const sortBy = document.getElementById('filter-sort').value;

        const params = new URLSearchParams({
            min_affinity: minAffinity,
            sort_by: sortBy,
            limit: 50
        });
        if (search) params.append('search', search);

        const response = await fetch(`${API_BASE}/consolidation/siblings/${currentScanId}?${params}`);
        const data = await response.json();

        // Update stats
        updateStats(data);

        // Render groups
        renderGroups(data.groups);

    } catch (error) {
        console.error('Error loading results:', error);
    }
}

function updateStats(data) {
    document.getElementById('stat-siblings').textContent = data.total || 0;

    // Count high affinity groups
    const highAffinity = data.groups ? data.groups.filter(g => g.average_affinity >= 0.7).length : 0;
    document.getElementById('stat-high-affinity').textContent = highAffinity;
}

function renderGroups(groups) {
    const container = document.getElementById('groups-container');

    if (!groups || groups.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No se encontraron grupos de hermanos.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = groups.map(group => {
        const affinityClass = group.average_affinity >= 0.7 ? 'high' :
                             group.average_affinity >= 0.5 ? 'medium' : 'low';

        const masterFile = group.files.find(f => f.is_master);

        return `
            <div class="group-card" data-filename="${group.filename}" onclick="showGroupDetail('${group.filename}')">
                <div class="group-header">
                    <div class="group-filename">
                        <input type="checkbox" class="group-checkbox" data-filename="${group.filename}" onclick="event.stopPropagation(); toggleGroupSelection('${group.filename}')">
                        ${group.filename}
                        <span class="group-count">${group.file_count} archivos</span>
                    </div>
                    <div class="group-affinity">
                        <span class="affinity-badge ${affinityClass}">
                            ${Math.round(group.average_affinity * 100)}%
                        </span>
                    </div>
                </div>
                <div class="group-files">
                    ${group.files.slice(0, 5).map(f => `
                        <span class="file-tag ${f.is_master ? 'master' : ''}">${getShortPath(f.directory)}</span>
                    `).join('')}
                    ${group.files.length > 5 ? `<span class="file-tag">+${group.files.length - 5} mas</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function getShortPath(path) {
    const parts = path.split(/[/\\]/);
    return parts.slice(-2).join('/');
}

function toggleGroupSelection(filename) {
    if (selectedGroups.has(filename)) {
        selectedGroups.delete(filename);
    } else {
        selectedGroups.add(filename);
    }
}

async function showGroupDetail(filename) {
    try {
        const response = await fetch(`${API_BASE}/consolidation/siblings/${currentScanId}/${encodeURIComponent(filename)}`);
        const data = await response.json();

        document.getElementById('detail-filename').textContent = filename;

        const body = document.getElementById('detail-body');
        body.innerHTML = `
            <div class="file-list">
                <h4>Archivos (${data.files.length})</h4>
                ${data.files.map(f => `
                    <div class="file-item ${f.is_master ? 'is-master' : ''}">
                        <span>${f.is_master ? '⭐' : '📄'}</span>
                        <div>
                            <div class="file-path">${f.filepath}</div>
                            <div class="file-stats">
                                <span>${formatBytes(f.size)}</span>
                                <span>${f.function_count} funciones</span>
                                <span>${f.class_count} clases</span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>

            ${data.affinity_matrix.length > 0 ? `
                <div class="affinity-matrix">
                    <h4>Matriz de Afinidad</h4>
                    <table class="matrix-table">
                        <thead>
                            <tr>
                                <th>Archivos</th>
                                <th>Overall</th>
                                <th>Contenido</th>
                                <th>Estructura</th>
                                <th>DNA</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.affinity_matrix.map(a => {
                                const affinityClass = a.overall >= 0.7 ? 'high' : a.overall >= 0.5 ? 'medium' : 'low';
                                return `
                                    <tr>
                                        <td>${a.file1} vs ${a.file2}</td>
                                        <td class="matrix-cell ${affinityClass}">${Math.round(a.overall * 100)}%</td>
                                        <td>${Math.round(a.content * 100)}%</td>
                                        <td>${Math.round(a.structure * 100)}%</td>
                                        <td>${Math.round(a.dna * 100)}%</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            ` : ''}

            <div style="margin-top: 1rem;">
                <strong>Maestro propuesto:</strong> ${data.master.filepath}<br>
                <strong>Confianza:</strong> ${Math.round(data.master.confidence * 100)}%<br>
                <strong>Razones:</strong> ${data.master.reasons.join(', ')}
            </div>
        `;

        // Store for merge preview
        body.dataset.files = JSON.stringify(data.files.map(f => f.filepath));

        openModal('detail-modal');

    } catch (error) {
        console.error('Error loading group detail:', error);
    }
}

// Filters
function initFilters() {
    document.getElementById('filter-affinity').addEventListener('change', loadResults);
    document.getElementById('filter-search').addEventListener('input', debounce(loadResults, 300));
    document.getElementById('filter-sort').addEventListener('change', loadResults);

    document.getElementById('btn-select-all').addEventListener('click', () => {
        const checkboxes = document.querySelectorAll('.group-checkbox');
        const allSelected = checkboxes.length === selectedGroups.size;

        checkboxes.forEach(cb => {
            cb.checked = !allSelected;
            if (!allSelected) {
                selectedGroups.add(cb.dataset.filename);
            }
        });

        if (allSelected) {
            selectedGroups.clear();
        }
    });
}

// Compare
function initCompare() {
    document.getElementById('btn-compare').addEventListener('click', async () => {
        const file1 = document.getElementById('compare-file1').value;
        const file2 = document.getElementById('compare-file2').value;

        if (!file1 || !file2) {
            alert('Por favor ingresa ambas rutas de archivo');
            return;
        }

        try {
            const params = new URLSearchParams({ file1, file2 });
            const response = await fetch(`${API_BASE}/consolidation/compare?${params}`);
            const data = await response.json();

            document.getElementById('compare-result').classList.remove('hidden');

            document.getElementById('compare-score').textContent = Math.round(data.affinity.overall * 100) + '%';
            document.getElementById('compare-level').textContent = data.affinity.level.toUpperCase();

            updateBreakdown('content', data.affinity.content);
            updateBreakdown('structure', data.affinity.structure);
            updateBreakdown('dna', data.affinity.dna);

        } catch (error) {
            alert('Error: ' + error.message);
        }
    });
}

function updateBreakdown(type, value) {
    document.getElementById(`compare-${type}`).style.width = `${value * 100}%`;
    document.getElementById(`compare-${type}-val`).textContent = Math.round(value * 100) + '%';
}

// Rules
function initRules() {
    // Preset buttons
    document.querySelectorAll('[data-preset]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const preset = btn.dataset.preset;
            try {
                await fetch(`${API_BASE}/rules/apply-preset/${preset}`, { method: 'POST' });
                loadRules();
            } catch (error) {
                console.error('Error applying preset:', error);
            }
        });
    });

    // Threshold slider
    const threshold = document.getElementById('rule-threshold');
    threshold.addEventListener('input', () => {
        document.getElementById('threshold-value').textContent = Math.round(threshold.value * 100) + '%';
    });

    // Form submit
    document.getElementById('rules-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveRules();
    });
}

async function loadRules() {
    try {
        const response = await fetch(`${API_BASE}/rules/`);
        const data = await response.json();

        document.getElementById('rule-threshold').value = data.min_affinity_threshold;
        document.getElementById('threshold-value').textContent = Math.round(data.min_affinity_threshold * 100) + '%';
        document.getElementById('rule-conflict').value = data.conflict_resolution;
        document.getElementById('rule-prefer-paths').value = data.prefer_paths.join('\n');
        document.getElementById('rule-never-master').value = data.never_master_from.join('\n');
        document.getElementById('rule-ignore').value = data.ignore_patterns.join('\n');

    } catch (error) {
        console.error('Error loading rules:', error);
    }
}

async function saveRules() {
    const config = {
        min_affinity_threshold: parseFloat(document.getElementById('rule-threshold').value),
        conflict_resolution: document.getElementById('rule-conflict').value,
        prefer_paths: document.getElementById('rule-prefer-paths').value.split('\n').filter(x => x.trim()),
        never_master_from: document.getElementById('rule-never-master').value.split('\n').filter(x => x.trim()),
        ignore_patterns: document.getElementById('rule-ignore').value.split('\n').filter(x => x.trim()),
        auto_commit: false
    };

    try {
        await fetch(`${API_BASE}/rules/`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        alert('Reglas guardadas');
    } catch (error) {
        alert('Error guardando reglas: ' + error.message);
    }
}

// Modals
function initModals() {
    // Close buttons
    document.querySelectorAll('[data-close]').forEach(btn => {
        btn.addEventListener('click', () => {
            closeModal(btn.dataset.close);
        });
    });

    // Click outside to close
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.add('hidden');
            }
        });
    });

    // Merge preview button
    document.getElementById('btn-merge-preview').addEventListener('click', async () => {
        const body = document.getElementById('detail-body');
        const files = JSON.parse(body.dataset.files || '[]');

        if (files.length < 2) {
            alert('Se necesitan al menos 2 archivos para merge');
            return;
        }

        try {
            const params = files.map(f => `files=${encodeURIComponent(f)}`).join('&');
            const response = await fetch(`${API_BASE}/consolidation/merge/preview?${params}`, {
                method: 'POST'
            });
            const data = await response.json();

            alert(`Preview generado:\n- Base: ${data.base_file}\n- Funciones a agregar: ${data.stats.functions_added}\n- Clases a agregar: ${data.stats.classes_added}\n- Conflictos: ${data.conflicts.length}`);

        } catch (error) {
            alert('Error: ' + error.message);
        }
    });
}

function openModal(modalId) {
    document.getElementById(modalId).classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

// Batch Actions
function initBatchActions() {
    document.getElementById('btn-batch-actions').addEventListener('click', () => {
        if (selectedGroups.size === 0) {
            alert('Selecciona al menos un grupo');
            return;
        }

        const list = document.getElementById('batch-groups-list');
        list.innerHTML = Array.from(selectedGroups).map(filename => `
            <div class="batch-item">
                <span>${filename}</span>
                <span></span>
                <select data-filename="${filename}">
                    <option value="ignore">Ignorar</option>
                    <option value="merge">Fusionar</option>
                    <option value="keep_master">Conservar maestro</option>
                    <option value="delete_duplicates">Eliminar duplicados</option>
                </select>
            </div>
        `).join('');

        openModal('batch-modal');
    });

    document.getElementById('btn-execute-batch').addEventListener('click', async () => {
        const dryRun = document.getElementById('batch-dry-run').checked;
        const actions = [];

        document.querySelectorAll('#batch-groups-list select').forEach(select => {
            actions.push({
                filename: select.dataset.filename,
                action: select.value
            });
        });

        try {
            const response = await fetch(`${API_BASE}/batch/${dryRun ? 'dry-run' : 'execute'}/${currentScanId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ actions, dry_run: dryRun })
            });
            const data = await response.json();

            if (dryRun) {
                const impact = data.impact;
                document.getElementById('batch-summary').innerHTML = `
                    <strong>Simulacion:</strong><br>
                    - Archivos a fusionar: ${impact.files_to_merge}<br>
                    - Archivos a eliminar: ${impact.files_to_delete}<br>
                    - Espacio a recuperar: ${impact.space_to_recover_kb.toFixed(2)} KB<br>
                    - Imports a actualizar: ${impact.imports_to_update}<br>
                    ${impact.warnings.length > 0 ? '<br><strong>Advertencias:</strong> ' + impact.warnings.join(', ') : ''}
                `;
            } else {
                alert(`Ejecutado: ${data.successful} exitosos, ${data.failed} fallidos`);
                closeModal('batch-modal');
                selectedGroups.clear();
                loadResults();
            }

        } catch (error) {
            alert('Error: ' + error.message);
        }
    });
}

// Export
function initExport() {
    document.getElementById('btn-export').addEventListener('click', () => {
        if (!currentScanId) {
            alert('No hay resultados para exportar');
            return;
        }
        openModal('export-modal');
    });

    document.querySelectorAll('.export-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const format = btn.dataset.format;
            window.open(`${API_BASE}/export/${currentScanId}/${format}`, '_blank');
            closeModal('export-modal');
        });
    });
}

// Utilities
function setStatus(status, text) {
    const dot = document.getElementById('status-indicator');
    const textEl = document.getElementById('status-text');

    dot.className = 'status-dot';
    if (status === 'running') dot.classList.add('running');
    if (status === 'error') dot.classList.add('error');

    textEl.textContent = text;
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
