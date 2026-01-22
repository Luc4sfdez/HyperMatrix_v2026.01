import { useState, useEffect, useRef } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../components/Card'
import { Button } from '../components/Button'
import ProjectSelector, { addRecentProject } from '../components/ProjectSelector'
import FileBrowser from '../components/FileBrowser'

// Fases del escaneo
const SCAN_PHASES = [
  { id: 'discovery', label: 'Descubrimiento', icon: '🔍' },
  { id: 'hashing', label: 'Hashing', icon: '🔐' },
  { id: 'deduplication', label: 'Deduplicación', icon: '📋' },
  { id: 'analysis', label: 'Análisis', icon: '🧠' },
  { id: 'consolidation', label: 'Consolidación', icon: '🔗' },
]

// Componente de barra de progreso
function ProgressBar({ progress, animated = true }) {
  return (
    <div className="w-full h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
      <div
        className={`h-full bg-[var(--color-primary)] rounded-full transition-all duration-500 ${
          animated ? 'animate-pulse' : ''
        }`}
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      />
    </div>
  )
}

// Componente de fase de escaneo
function ScanPhase({ phase, isActive, isCompleted, progress }) {
  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
      isActive
        ? 'bg-[var(--color-primary)] bg-opacity-10 border border-[var(--color-primary)]'
        : isCompleted
          ? 'bg-[var(--color-success)] bg-opacity-10'
          : 'bg-[var(--color-bg-secondary)]'
    }`}>
      <span className="text-xl">
        {isCompleted ? '✅' : isActive ? phase.icon : '⏳'}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className={`text-sm font-medium ${
            isActive ? 'text-[var(--color-primary)]' :
            isCompleted ? 'text-[var(--color-success)]' :
            'text-[var(--color-fg-secondary)]'
          }`}>
            {phase.label}
          </span>
          {isActive && progress !== undefined && (
            <span className="text-xs text-[var(--color-fg-secondary)]">
              {progress.toFixed(0)}%
            </span>
          )}
        </div>
        {isActive && (
          <ProgressBar progress={progress || 0} animated={true} />
        )}
      </div>
    </div>
  )
}

export default function Dashboard({ hypermatrixUrl, onNavigate }) {
  const [projectPath, setProjectPath] = useState('')
  const [projectName, setProjectName] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [currentScanId, setCurrentScanId] = useState(null)
  const [scanProgress, setScanProgress] = useState(null)
  const [showFileBrowser, setShowFileBrowser] = useState(false)
  const [existingScans, setExistingScans] = useState([])
  const pollingRef = useRef(null)

  // Cargar scans existentes al montar
  useEffect(() => {
    const loadExistingScans = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        if (response.ok) {
          const data = await response.json()
          setExistingScans(data.scans || [])
        }
      } catch (err) {
        console.error('Error loading scans:', err)
      }
    }
    if (hypermatrixUrl) {
      loadExistingScans()
    }
  }, [hypermatrixUrl])

  // Polling para obtener estado del scan
  useEffect(() => {
    if (currentScanId && isScanning) {
      const pollStatus = async () => {
        try {
          const response = await fetch(`${hypermatrixUrl}/api/scan/status/${currentScanId}`)
          const data = await response.json()

          setScanProgress(data)

          // Si el scan terminó, detener polling
          if (data.status === 'completed' || data.status === 'failed') {
            setIsScanning(false)
            setCurrentScanId(null)

            if (data.status === 'completed') {
              // Obtener resultado completo
              const resultRes = await fetch(`${hypermatrixUrl}/api/scan/result/${currentScanId}`)
              const result = await resultRes.json()
              setScanResult({
                scan_id: currentScanId,
                project_name: projectName || 'Mi Proyecto',
                ...result
              })
            }
          }
        } catch (error) {
          console.error('Error polling status:', error)
        }
      }

      // Poll inmediatamente y luego cada 1.5 segundos
      pollStatus()
      pollingRef.current = setInterval(pollStatus, 1500)

      return () => {
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
        }
      }
    }
  }, [currentScanId, isScanning, hypermatrixUrl, projectName])

  // Limpiar polling al desmontar
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])

  const handleScan = async () => {
    if (!projectPath) {
      alert('Por favor ingresa una ruta de proyecto')
      return
    }

    setIsScanning(true)
    setScanProgress(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/scan/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: projectPath,
          project_name: projectName || 'Mi Proyecto',
        }),
      })

      const data = await response.json()

      if (data.scan_id) {
        setCurrentScanId(data.scan_id)
        // El polling se encargará del resto
      } else {
        // Respuesta inmediata (sin async scan)
        setScanResult(data)
        setIsScanning(false)
      }

      setProjectPath('')
      setProjectName('')
    } catch (error) {
      alert(`Error: ${error.message}`)
      setIsScanning(false)
    }
  }

  // Determinar fase actual y progreso
  const getCurrentPhaseIndex = () => {
    if (!scanProgress?.phase) return -1
    const phaseMap = {
      'discovery': 0, 'discovering': 0,
      'hashing': 1,
      'deduplication': 2, 'dedup': 2,
      'analysis': 3, 'analyzing': 3,
      'consolidation': 4, 'consolidating': 4,
      'completed': 5
    }
    return phaseMap[scanProgress.phase.toLowerCase()] ?? -1
  }

  const currentPhaseIndex = getCurrentPhaseIndex()

  return (
    <div className="space-y-6 p-6">
      {/* Hero Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">🔍 Nuevo Análisis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <ProjectSelector
                  value={projectPath}
                  onChange={(path, name) => {
                    setProjectPath(path)
                    if (name && !projectName) setProjectName(name)
                  }}
                  label="Ruta del Proyecto"
                  placeholder="Selecciona o ingresa la ruta del proyecto"
                  hypermatrixUrl={hypermatrixUrl}
                />
              </div>
              <Button
                variant="secondary"
                onClick={() => setShowFileBrowser(true)}
                disabled={isScanning}
                className="mb-0"
              >
                📁 Explorar
              </Button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
              Nombre del Proyecto (opcional)
            </label>
            <input
              type="text"
              placeholder="ej: Mi Proyecto Importante"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              disabled={isScanning}
              className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-opacity-20 disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          <p className="text-sm text-[var(--color-fg-secondary)] bg-[var(--color-bg-secondary)] p-3 rounded-md">
            💡 HyperMatrix analizará la estructura, detectará duplicados, clones y código muerto. El proceso puede tardar unos minutos en proyectos grandes.
          </p>
        </CardContent>

        <CardFooter>
          <Button
            variant="primary"
            size="lg"
            onClick={handleScan}
            disabled={isScanning || !projectPath}
          >
            {isScanning ? '⏳ Analizando...' : '🚀 Iniciar Análisis'}
          </Button>
        </CardFooter>
      </Card>

      {/* Panel de Progreso en Tiempo Real */}
      {isScanning && scanProgress && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="animate-pulse">🔄</span>
              Análisis en Progreso
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Progreso general */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-[var(--color-fg-primary)]">
                  Progreso General
                </span>
                <span className="text-sm text-[var(--color-fg-secondary)]">
                  {scanProgress.progress?.overall_percent?.toFixed(0) ||
                   ((currentPhaseIndex + 1) / SCAN_PHASES.length * 100).toFixed(0)}%
                </span>
              </div>
              <ProgressBar
                progress={scanProgress.progress?.overall_percent ||
                          ((currentPhaseIndex + 1) / SCAN_PHASES.length * 100)}
                animated={true}
              />
            </div>

            {/* Archivo actual */}
            {scanProgress.current_file && (
              <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
                <div className="text-xs text-[var(--color-fg-secondary)] mb-1">
                  Procesando archivo:
                </div>
                <div className="text-sm font-mono text-[var(--color-fg-primary)] truncate">
                  📄 {scanProgress.current_file}
                </div>
              </div>
            )}

            {/* Estadísticas en tiempo real */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-2 bg-[var(--color-bg-secondary)] rounded text-center">
                <div className="text-lg font-bold text-[var(--color-primary)]">
                  {scanProgress.progress?.files_processed || scanProgress.files_discovered || 0}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Archivos</div>
              </div>
              <div className="p-2 bg-[var(--color-bg-secondary)] rounded text-center">
                <div className="text-lg font-bold text-[var(--color-warning)]">
                  {scanProgress.duplicates_found || 0}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Duplicados</div>
              </div>
              <div className="p-2 bg-[var(--color-bg-secondary)] rounded text-center">
                <div className="text-lg font-bold text-[var(--color-success)]">
                  {scanProgress.siblings_found || 0}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Hermanos</div>
              </div>
              <div className="p-2 bg-[var(--color-bg-secondary)] rounded text-center">
                <div className="text-lg font-bold text-[var(--color-fg-primary)]">
                  {scanProgress.progress?.elapsed_time
                    ? `${Math.floor(scanProgress.progress.elapsed_time)}s`
                    : '-'}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Tiempo</div>
              </div>
            </div>

            {/* Fases de escaneo */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Fases del análisis
              </div>
              {SCAN_PHASES.map((phase, index) => (
                <ScanPhase
                  key={phase.id}
                  phase={phase}
                  isActive={index === currentPhaseIndex}
                  isCompleted={index < currentPhaseIndex}
                  progress={index === currentPhaseIndex ? (scanProgress.progress?.phase_percent || 50) : undefined}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Scans */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Últimos Análisis</CardTitle>
            {existingScans.length > 0 && (
              <button
                onClick={() => onNavigate('results')}
                className="text-sm text-[var(--color-primary)] hover:underline"
              >
                Ver todos →
              </button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {/* Scan recién completado en esta sesión */}
            {scanResult && (
              <div
                onClick={() => onNavigate('results', { scanId: scanResult.scan_id })}
                className="p-4 bg-[var(--color-bg-secondary)] rounded-lg border-l-4 border-[var(--color-primary)] cursor-pointer hover:bg-[var(--color-bg-tertiary)] transition-colors"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-[var(--color-fg-primary)]">
                      {scanResult.project_name}
                    </h3>
                    <p className="text-sm text-[var(--color-fg-secondary)]">
                      ID: {scanResult.scan_id}
                    </p>
                    <div className="mt-2 flex gap-4 text-xs">
                      <span className="text-[var(--color-fg-secondary)]">
                        📁 {scanResult.total_files || 0} archivos
                      </span>
                      {(scanResult.duplicates || scanResult.duplicate_groups) > 0 && (
                        <span className="text-[var(--color-error)]">
                          🔴 {scanResult.duplicates || scanResult.duplicate_groups} duplicados
                        </span>
                      )}
                      {scanResult.sibling_groups > 0 && (
                        <span className="text-[var(--color-warning)]">
                          🟡 {scanResult.sibling_groups} hermanos
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]">
                    ✓ Nuevo
                  </span>
                </div>
              </div>
            )}

            {/* Scans existentes del backend */}
            {existingScans.filter(s => s.status === 'completed' && s.scan_id !== scanResult?.scan_id).slice(0, 3).map((scan) => (
              <div
                key={scan.scan_id}
                onClick={() => onNavigate('results', { scanId: scan.scan_id })}
                className="p-4 bg-[var(--color-bg-secondary)] rounded-lg border-l-4 border-[var(--color-border)] cursor-pointer hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-tertiary)] transition-all"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-[var(--color-fg-primary)]">
                      {scan.project || `Scan ${scan.scan_id}`}
                    </h3>
                    <p className="text-sm text-[var(--color-fg-tertiary)]">
                      ID: {scan.scan_id}
                    </p>
                    <div className="mt-2 flex gap-4 text-xs">
                      <span className="text-[var(--color-fg-secondary)]">
                        📁 {scan.files || 0} archivos
                      </span>
                      {scan.duplicates > 0 && (
                        <span className="text-[var(--color-error)]">
                          🔴 {scan.duplicates} duplicados
                        </span>
                      )}
                      {scan.siblings > 0 && (
                        <span className="text-[var(--color-warning)]">
                          🟡 {scan.siblings} hermanos
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="text-[var(--color-primary)] text-sm">→</span>
                </div>
              </div>
            ))}

            {/* Empty state */}
            {!scanResult && existingScans.filter(s => s.status === 'completed').length === 0 && !isScanning && (
              <p className="text-[var(--color-fg-secondary)] text-center py-8">
                No hay análisis recientes. ¡Comienza con uno nuevo!
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Métricas globales */}
      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">Lenguajes Soportados</div>
          <div className="metric-value">7</div>
          <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
            Python, JS, TS, SQL, JSON, YAML, Markdown
          </p>
        </div>

        <div className="metric-card">
          <div className="metric-label">Capacidades</div>
          <div className="metric-value">12+</div>
          <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
            Clones, Dedup, Semántica, Calidad
          </p>
        </div>

        <div className="metric-card">
          <div className="metric-label">API Endpoints</div>
          <div className="metric-value">20+</div>
          <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
            Scan, Analysis, Export, Batch, Advanced
          </p>
        </div>

        <div className="metric-card">
          <div className="metric-label">Estado</div>
          <div className="metric-value">✅</div>
          <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
            Backend Completo
          </p>
        </div>
      </div>

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle>ℹ️ Cómo funciona</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-[var(--color-fg-secondary)]">
          <div>
            <strong className="text-[var(--color-fg-primary)]">1. Ingresa una ruta</strong>
            <p>Proporciona la ruta completa a tu proyecto (local o red)</p>
          </div>
          <div>
            <strong className="text-[var(--color-fg-primary)]">2. HyperMatrix analiza</strong>
            <p>Escanea archivos, detecta duplicados, calcula similitud</p>
          </div>
          <div>
            <strong className="text-[var(--color-fg-primary)]">3. Revisa resultados</strong>
            <p>Ve métricas, clones, código muerto, sugerencias</p>
          </div>
          <div>
            <strong className="text-[var(--color-fg-primary)]">4. Consolida</strong>
            <p>Ejecuta acciones en lote para fusionar o eliminar</p>
          </div>
        </CardContent>
      </Card>

      {/* File Browser Modal */}
      <FileBrowser
        isOpen={showFileBrowser}
        onClose={() => setShowFileBrowser(false)}
        onSelect={(path) => {
          setProjectPath(path)
          const name = path.split(/[/\\]/).pop() || path
          if (!projectName) setProjectName(name)
          addRecentProject(hypermatrixUrl, path, name)
        }}
        initialPath={projectPath || 'C:/'}
        mode="directory"
        title="Seleccionar Directorio del Proyecto"
        hypermatrixUrl={hypermatrixUrl}
      />
    </div>
  )
}
