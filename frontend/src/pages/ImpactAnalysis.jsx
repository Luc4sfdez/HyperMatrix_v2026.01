import { useState, useCallback, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Badge de estado
function StatusBadge({ safe }) {
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
      safe
        ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
        : 'bg-[var(--color-error)] bg-opacity-20 text-[var(--color-error)]'
    }`}>
      {safe ? '✓ Seguro' : '⚠️ Riesgoso'}
    </span>
  )
}

// Lista de archivos afectados
function AffectedFilesList({ title, files, icon, color }) {
  if (!files || files.length === 0) return null

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-[var(--color-fg-secondary)] flex items-center gap-2">
        <span>{icon}</span>
        {title} ({files.length})
      </h4>
      <div className="max-h-48 overflow-auto space-y-1">
        {files.map((file, idx) => (
          <div
            key={idx}
            className={`p-2 rounded bg-[var(--color-bg-secondary)] border-l-4 ${color}`}
          >
            <span className="font-mono text-sm text-[var(--color-fg-primary)]">
              {file}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Alerta de warning o breaking change
function Alert({ type, message }) {
  const isWarning = type === 'warning'
  return (
    <div className={`p-3 rounded flex items-start gap-2 ${
      isWarning
        ? 'bg-[var(--color-warning)] bg-opacity-10 border border-[var(--color-warning)] border-opacity-30'
        : 'bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] border-opacity-30'
    }`}>
      <span>{isWarning ? '⚠️' : '❌'}</span>
      <span className={`text-sm ${
        isWarning ? 'text-[var(--color-warning)]' : 'text-[var(--color-error)]'
      }`}>
        {message}
      </span>
    </div>
  )
}

// Panel de resultados de impacto
function ImpactResults({ impact }) {
  if (!impact) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>📊 Resultado del Análisis</span>
          <StatusBadge safe={impact.safe_to_proceed} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Info del target */}
        <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg">
          <div className="text-sm text-[var(--color-fg-tertiary)] mb-1">Archivo objetivo</div>
          <div className="font-mono text-[var(--color-fg-primary)]">{impact.target_file}</div>
          {impact.action && (
            <div className="mt-2 text-sm">
              <span className="text-[var(--color-fg-tertiary)]">Acción: </span>
              <span className="font-medium text-[var(--color-fg-primary)]">{impact.action}</span>
            </div>
          )}
        </div>

        {/* Breaking changes */}
        {impact.breaking_changes?.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-[var(--color-error)]">
              ❌ Breaking Changes ({impact.breaking_changes.length})
            </h4>
            {impact.breaking_changes.map((change, idx) => (
              <Alert key={idx} type="error" message={change} />
            ))}
          </div>
        )}

        {/* Warnings */}
        {impact.warnings?.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-[var(--color-warning)]">
              ⚠️ Advertencias ({impact.warnings.length})
            </h4>
            {impact.warnings.map((warning, idx) => (
              <Alert key={idx} type="warning" message={warning} />
            ))}
          </div>
        )}

        {/* Archivos afectados */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <AffectedFilesList
            title="Afectados Directamente"
            files={impact.directly_affected}
            icon="🎯"
            color="border-[var(--color-error)]"
          />
          <AffectedFilesList
            title="Afectados Transitivamente"
            files={impact.transitively_affected}
            icon="🔄"
            color="border-[var(--color-warning)]"
          />
        </div>

        {/* Import updates */}
        {impact.import_updates_required?.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-[var(--color-fg-secondary)]">
              📝 Actualizaciones de Import Requeridas
            </h4>
            <div className="bg-[var(--color-bg-tertiary)] rounded p-3 overflow-x-auto">
              <pre className="text-xs font-mono text-[var(--color-fg-primary)]">
                {impact.import_updates_required.map((update, idx) => (
                  <div key={idx} className="py-1">{update}</div>
                ))}
              </pre>
            </div>
          </div>
        )}

        {/* Resumen */}
        <div className="p-4 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)]">
          <h4 className="text-sm font-medium text-[var(--color-fg-primary)] mb-3">Resumen</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-[var(--color-error)]">
                {impact.directly_affected?.length || 0}
              </div>
              <div className="text-xs text-[var(--color-fg-tertiary)]">Directos</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[var(--color-warning)]">
                {impact.transitively_affected?.length || 0}
              </div>
              <div className="text-xs text-[var(--color-fg-tertiary)]">Transitivos</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[var(--color-info)]">
                {impact.import_updates_required?.length || 0}
              </div>
              <div className="text-xs text-[var(--color-fg-tertiary)]">Imports</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                {impact.breaking_changes?.length || 0}
              </div>
              <div className="text-xs text-[var(--color-fg-tertiary)]">Breaking</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function ImpactAnalysis({ hypermatrixUrl }) {
  const [analysisType, setAnalysisType] = useState('deletion') // 'deletion', 'merge', 'group'
  const [filepath, setFilepath] = useState('')
  const [mergeFiles, setMergeFiles] = useState('')
  const [mergeTarget, setMergeTarget] = useState('')
  const [scanId, setScanId] = useState('')
  const [groupFile, setGroupFile] = useState('')
  const [availableScans, setAvailableScans] = useState([])
  const [availableGroups, setAvailableGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [impact, setImpact] = useState(null)

  // Cargar scans disponibles
  useEffect(() => {
    const loadScans = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        if (response.ok) {
          const data = await response.json()
          setAvailableScans(data.scans || [])
        }
      } catch (err) {
        console.error('Error loading scans:', err)
      }
    }
    loadScans()
  }, [hypermatrixUrl])

  // Cargar grupos cuando se selecciona un scan
  useEffect(() => {
    if (!scanId || analysisType !== 'group') return

    const loadGroups = async () => {
      try {
        // Intentar cargar del endpoint de scan primero
        let groups = []
        try {
          const response = await fetch(`${hypermatrixUrl}/api/scan/result/${scanId}/summary`)
          if (response.ok) {
            const data = await response.json()
            groups = data.sibling_groups || []
          }
        } catch (e) {
          console.log('Scan summary not available')
        }

        // Fallback: cargar desde DB siblings endpoint
        if (groups.length === 0) {
          const dbRes = await fetch(`${hypermatrixUrl}/api/db/siblings/${scanId}?limit=100`)
          if (dbRes.ok) {
            const dbData = await dbRes.json()
            groups = dbData.groups || []
          }
        }

        setAvailableGroups(groups)
      } catch (err) {
        console.error('Error loading groups:', err)
      }
    }
    loadGroups()
  }, [hypermatrixUrl, scanId, analysisType])

  // Analizar impacto de eliminación
  const analyzeDeletion = useCallback(async () => {
    if (!filepath.trim()) {
      setError('Ingresa la ruta del archivo')
      return
    }

    setLoading(true)
    setError(null)
    setImpact(null)

    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/analysis/impact/deletion?filepath=${encodeURIComponent(filepath)}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setImpact(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, filepath])

  // Analizar impacto de merge
  const analyzeMerge = useCallback(async () => {
    const files = mergeFiles.split('\n').map(f => f.trim()).filter(f => f)
    if (files.length < 2) {
      setError('Ingresa al menos 2 archivos para merge')
      return
    }
    if (!mergeTarget.trim()) {
      setError('Ingresa el archivo destino')
      return
    }

    setLoading(true)
    setError(null)
    setImpact(null)

    try {
      const params = new URLSearchParams()
      files.forEach(f => params.append('files', f))
      params.append('target', mergeTarget)

      const response = await fetch(
        `${hypermatrixUrl}/api/analysis/impact/merge?${params.toString()}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setImpact(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, mergeFiles, mergeTarget])

  // Analizar impacto de grupo
  const analyzeGroup = useCallback(async () => {
    if (!scanId || !groupFile) {
      setError('Selecciona un scan y un grupo')
      return
    }

    setLoading(true)
    setError(null)
    setImpact(null)

    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/analysis/impact/group/${scanId}/${encodeURIComponent(groupFile)}`
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setImpact(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, scanId, groupFile])

  // Handler principal
  const analyze = () => {
    switch (analysisType) {
      case 'deletion':
        analyzeDeletion()
        break
      case 'merge':
        analyzeMerge()
        break
      case 'group':
        analyzeGroup()
        break
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          💥 Análisis de Impacto
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Evalúa las consecuencias de eliminar o consolidar archivos
        </p>
      </div>

      {/* Selector de tipo de análisis */}
      <Card>
        <CardContent className="space-y-4">
          {/* Tabs de tipo */}
          <div className="flex gap-2 border-b border-[var(--color-border)] pb-4">
            <button
              onClick={() => {
                setAnalysisType('deletion')
                setImpact(null)
                setError(null)
              }}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                analysisType === 'deletion'
                  ? 'bg-[var(--color-error)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              🗑️ Eliminación
            </button>
            <button
              onClick={() => {
                setAnalysisType('merge')
                setImpact(null)
                setError(null)
              }}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                analysisType === 'merge'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              🔗 Merge
            </button>
            <button
              onClick={() => {
                setAnalysisType('group')
                setImpact(null)
                setError(null)
              }}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                analysisType === 'group'
                  ? 'bg-[var(--color-success)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              👥 Grupo (Scan)
            </button>
          </div>

          {/* Formulario según tipo */}
          {analysisType === 'deletion' && (
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Archivo a Eliminar
              </label>
              <input
                type="text"
                value={filepath}
                onChange={(e) => setFilepath(e.target.value)}
                placeholder="C:/proyecto/src/file.py"
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              />
              <p className="text-xs text-[var(--color-fg-tertiary)] mt-2">
                Analiza qué otros archivos se romperían si eliminas este archivo
              </p>
            </div>
          )}

          {analysisType === 'merge' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Archivos a Mergear (uno por línea)
                </label>
                <textarea
                  value={mergeFiles}
                  onChange={(e) => setMergeFiles(e.target.value)}
                  placeholder="C:/proyecto/src/utils.py&#10;C:/proyecto/backup/utils.py&#10;C:/proyecto/old/utils.py"
                  rows={4}
                  className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] font-mono text-sm focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Archivo Destino
                </label>
                <input
                  type="text"
                  value={mergeTarget}
                  onChange={(e) => setMergeTarget(e.target.value)}
                  placeholder="C:/proyecto/src/utils.py"
                  className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <p className="text-xs text-[var(--color-fg-tertiary)]">
                Analiza el impacto de consolidar múltiples archivos en uno
              </p>
            </div>
          )}

          {analysisType === 'group' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Scan
                </label>
                <select
                  value={scanId}
                  onChange={(e) => {
                    setScanId(e.target.value)
                    setGroupFile('')
                  }}
                  className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Seleccionar scan...</option>
                  {availableScans.filter(s => s.files > 0).map(scan => (
                    <option key={scan.scan_id} value={scan.scan_id}>
                      {scan.project || scan.project_name || scan.scan_id} ({scan.files || 0} archivos)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Grupo de Siblings
                </label>
                <select
                  value={groupFile}
                  onChange={(e) => setGroupFile(e.target.value)}
                  disabled={!scanId}
                  className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
                >
                  <option value="">Seleccionar grupo...</option>
                  {availableGroups.map(group => (
                    <option key={group.filename} value={group.filename}>
                      {group.filename} ({group.file_count} archivos)
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-[var(--color-fg-tertiary)] col-span-full">
                Analiza el impacto de consolidar un grupo de archivos detectado en el scan
              </p>
            </div>
          )}

          <Button
            variant="primary"
            onClick={analyze}
            disabled={loading}
          >
            {loading ? '⏳ Analizando...' : '🔍 Analizar Impacto'}
          </Button>

          {error && (
            <p className="text-[var(--color-error)] text-sm bg-[var(--color-error)] bg-opacity-10 p-3 rounded">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Resultados */}
      <ImpactResults impact={impact} />

      {/* Empty State */}
      {!impact && !loading && (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="text-6xl mb-4">💥</div>
              <h3 className="text-xl font-medium text-[var(--color-fg-primary)] mb-2">
                Prevé Problemas Antes de Actuar
              </h3>
              <p className="text-[var(--color-fg-secondary)] max-w-md mx-auto">
                Analiza el impacto de eliminar o mergear archivos antes de hacerlo.
                Identifica dependencias rotas y archivos que necesitarán actualización.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
