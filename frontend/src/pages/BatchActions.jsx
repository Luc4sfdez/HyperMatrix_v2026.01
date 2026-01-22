import { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../components/Card'
import { Button } from '../components/Button'

// Acciones disponibles
const ACTIONS = [
  { value: 'merge', label: 'Fusionar', icon: '🔗', description: 'Combinar todos los archivos en uno' },
  { value: 'keep_master', label: 'Mantener maestro', icon: '👑', description: 'Eliminar duplicados, mantener el mejor' },
  { value: 'delete_duplicates', label: 'Eliminar duplicados', icon: '🗑️', description: 'Eliminar archivos no-maestro' },
  { value: 'ignore', label: 'Ignorar', icon: '⏸️', description: 'No hacer nada con este grupo' },
]

// Componente de grupo seleccionable
function GroupItem({ group, selected, action, onSelect, onActionChange }) {
  const actionInfo = ACTIONS.find(a => a.value === action) || ACTIONS[3]

  return (
    <div className={`p-4 border rounded-lg transition-all ${
      selected
        ? 'border-[var(--color-primary)] bg-[var(--color-primary)] bg-opacity-5'
        : 'border-[var(--color-border)] hover:border-[var(--color-fg-tertiary)]'
    }`}>
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => onSelect(group.filename, e.target.checked)}
          className="mt-1 w-5 h-5 rounded"
        />

        {/* Info del grupo */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h4 className="font-semibold text-[var(--color-fg-primary)] truncate">
              {group.filename}
            </h4>
            <span className={`px-2 py-0.5 text-xs rounded-full ${
              group.average_affinity >= 0.8
                ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
                : group.average_affinity >= 0.5
                  ? 'bg-[var(--color-warning)] bg-opacity-20 text-[var(--color-warning)]'
                  : 'bg-[var(--color-fg-tertiary)] bg-opacity-20 text-[var(--color-fg-tertiary)]'
            }`}>
              {(group.average_affinity * 100).toFixed(0)}% similitud
            </span>
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-fg-secondary)]">
            <span>{group.file_count} archivos</span>
            <span>Confianza: {(group.master_confidence * 100).toFixed(0)}%</span>
          </div>

          <div className="mt-1 text-xs text-[var(--color-fg-tertiary)]">
            <span className="text-[var(--color-success)]">👑</span> {group.proposed_master}
          </div>

          {/* Selector de acción */}
          {selected && (
            <div className="mt-3 flex flex-wrap gap-2">
              {ACTIONS.map((a) => (
                <button
                  key={a.value}
                  onClick={() => onActionChange(group.filename, a.value)}
                  title={a.description}
                  className={`px-3 py-1 text-xs rounded-md border transition-all ${
                    action === a.value
                      ? 'bg-[var(--color-primary)] text-white border-[var(--color-primary)]'
                      : 'bg-[var(--color-bg-primary)] text-[var(--color-fg-secondary)] border-[var(--color-border)] hover:border-[var(--color-primary)]'
                  }`}
                >
                  {a.icon} {a.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Modal de impacto
function ImpactModal({ impact, onClose, onExecute, executing }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
          <h3 className="font-semibold text-[var(--color-fg-primary)]">
            📊 Impacto de las Acciones
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-[var(--color-bg-secondary)] rounded">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Resumen */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
              <div className="text-2xl font-bold text-[var(--color-primary)]">
                {impact.total_groups}
              </div>
              <div className="text-xs text-[var(--color-fg-secondary)]">Grupos</div>
            </div>
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
              <div className="text-2xl font-bold text-[var(--color-warning)]">
                {impact.files_to_merge}
              </div>
              <div className="text-xs text-[var(--color-fg-secondary)]">A fusionar</div>
            </div>
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
              <div className="text-2xl font-bold text-[var(--color-error)]">
                {impact.files_to_delete}
              </div>
              <div className="text-xs text-[var(--color-fg-secondary)]">A eliminar</div>
            </div>
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
              <div className="text-2xl font-bold text-[var(--color-success)]">
                {impact.space_to_recover_kb?.toFixed(1) || 0} KB
              </div>
              <div className="text-xs text-[var(--color-fg-secondary)]">Espacio liberado</div>
            </div>
          </div>

          {/* Archivos afectados */}
          {impact.affected_files?.length > 0 && (
            <div>
              <h4 className="font-medium text-[var(--color-fg-primary)] mb-2">
                Archivos afectados ({impact.affected_files.length}):
              </h4>
              <div className="max-h-40 overflow-y-auto bg-[var(--color-bg-secondary)] rounded p-2">
                {impact.affected_files.map((file, idx) => (
                  <div key={idx} className="text-xs font-mono text-[var(--color-fg-secondary)] py-0.5 truncate">
                    {file}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {impact.warnings?.length > 0 && (
            <div className="p-3 bg-[var(--color-warning)] bg-opacity-10 border border-[var(--color-warning)] rounded">
              <h4 className="font-medium text-[var(--color-warning)] mb-1">Advertencias:</h4>
              <ul className="text-sm">
                {impact.warnings.map((w, idx) => (
                  <li key={idx} className="text-[var(--color-fg-secondary)]">• {w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Info backup */}
          <p className="text-sm text-[var(--color-fg-secondary)] bg-[var(--color-bg-secondary)] p-3 rounded">
            💡 Todos los archivos modificados o eliminados se respaldarán en <code>hypermatrix_backup/</code>
          </p>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t border-[var(--color-border)]">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            onClick={onExecute}
            disabled={executing}
          >
            {executing ? '⏳ Ejecutando...' : '🚀 Ejecutar Acciones'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function BatchActions({ hypermatrixUrl }) {
  const [scans, setScans] = useState([])
  const [selectedScan, setSelectedScan] = useState('')
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingScans, setLoadingScans] = useState(true)
  const [error, setError] = useState(null)
  const [selections, setSelections] = useState({}) // {filename: boolean}
  const [actions, setActions] = useState({}) // {filename: action}
  const [suggestions, setSuggestions] = useState([])
  const [showImpact, setShowImpact] = useState(false)
  const [impact, setImpact] = useState(null)
  const [executing, setExecuting] = useState(false)
  const [result, setResult] = useState(null)

  // Cargar lista de scans
  useEffect(() => {
    const loadScans = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        if (response.ok) {
          const data = await response.json()
          setScans(data.scans || [])
        }
      } catch (err) {
        console.error('Error cargando scans:', err)
      } finally {
        setLoadingScans(false)
      }
    }
    loadScans()
  }, [hypermatrixUrl])

  // Cargar grupos cuando se selecciona un scan
  const loadGroups = useCallback(async () => {
    if (!selectedScan) return

    setLoading(true)
    setError(null)
    setGroups([])
    setSelections({})
    setActions({})

    try {
      // Intentar cargar grupos del endpoint consolidation
      let groupsData = { groups: [] }
      try {
        const groupsRes = await fetch(`${hypermatrixUrl}/api/consolidation/siblings/${selectedScan}?limit=100`)
        if (groupsRes.ok) {
          groupsData = await groupsRes.json()
        }
      } catch (e) {
        console.log('Consolidation endpoint not available')
      }

      // Fallback: cargar desde DB siblings endpoint
      if (!groupsData.groups || groupsData.groups.length === 0) {
        const dbRes = await fetch(`${hypermatrixUrl}/api/db/siblings/${selectedScan}?limit=100`)
        if (dbRes.ok) {
          groupsData = await dbRes.json()
        }
      }

      setGroups(groupsData.groups || [])

      // Cargar sugerencias (opcional, puede fallar)
      let suggestionsRes = null
      try {
        suggestionsRes = await fetch(`${hypermatrixUrl}/api/batch/suggestions/${selectedScan}?min_confidence=0.5`)
      } catch (e) {
        console.log('Suggestions endpoint not available')
      }

      if (suggestionsRes && suggestionsRes.ok) {
        const suggestionsData = await suggestionsRes.json()
        setSuggestions(suggestionsData.suggestions || [])

        // Pre-seleccionar y pre-configurar acciones según sugerencias
        const newSelections = {}
        const newActions = {}
        suggestionsData.suggestions?.forEach((s) => {
          if (s.suggested_action !== 'ignore') {
            newSelections[s.filename] = true
            newActions[s.filename] = s.suggested_action
          }
        })
        setSelections(newSelections)
        setActions(newActions)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, selectedScan])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  // Seleccionar/deseleccionar grupo
  const handleSelect = (filename, selected) => {
    setSelections((prev) => ({ ...prev, [filename]: selected }))
    if (selected && !actions[filename]) {
      // Buscar sugerencia o default
      const suggestion = suggestions.find(s => s.filename === filename)
      setActions((prev) => ({
        ...prev,
        [filename]: suggestion?.suggested_action || 'ignore',
      }))
    }
  }

  // Cambiar acción de un grupo
  const handleActionChange = (filename, action) => {
    setActions((prev) => ({ ...prev, [filename]: action }))
  }

  // Seleccionar/deseleccionar todos
  const selectAll = (selected) => {
    const newSelections = {}
    const newActions = { ...actions }
    groups.forEach((g) => {
      newSelections[g.filename] = selected
      if (selected && !newActions[g.filename]) {
        const suggestion = suggestions.find(s => s.filename === g.filename)
        newActions[g.filename] = suggestion?.suggested_action || 'ignore'
      }
    })
    setSelections(newSelections)
    setActions(newActions)
  }

  // Aplicar sugerencias
  const applySuggestions = () => {
    const newSelections = {}
    const newActions = {}
    suggestions.forEach((s) => {
      if (s.suggested_action !== 'ignore' && s.confidence >= 0.7) {
        newSelections[s.filename] = true
        newActions[s.filename] = s.suggested_action
      }
    })
    setSelections(newSelections)
    setActions(newActions)
  }

  // Simular (dry-run)
  const simulate = async () => {
    const selectedActions = Object.entries(selections)
      .filter(([_, selected]) => selected)
      .map(([filename]) => ({
        filename,
        action: actions[filename] || 'ignore',
      }))

    if (selectedActions.length === 0) {
      setError('Selecciona al menos un grupo')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/batch/dry-run/${selectedScan}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions: selectedActions, dry_run: true }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setImpact(data.impact)
      setShowImpact(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Ejecutar
  const execute = async () => {
    const selectedActions = Object.entries(selections)
      .filter(([_, selected]) => selected)
      .map(([filename]) => ({
        filename,
        action: actions[filename] || 'ignore',
      }))

    setExecuting(true)
    setError(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/batch/execute/${selectedScan}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions: selectedActions, dry_run: false }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setResult(data)
      setShowImpact(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setExecuting(false)
    }
  }

  // Contar seleccionados
  const selectedCount = Object.values(selections).filter(Boolean).length

  // Resultado exitoso
  if (result) {
    return (
      <div className="space-y-6 p-6">
        <Card>
          <CardContent className="py-8">
            <div className="text-center mb-6">
              <div className="text-6xl mb-4">
                {result.failed > 0 ? '⚠️' : '✅'}
              </div>
              <h2 className="text-2xl font-bold text-[var(--color-fg-primary)]">
                Acciones Ejecutadas
              </h2>
              <p className="text-[var(--color-fg-secondary)]">
                {result.successful} exitosas, {result.failed} fallidas
              </p>
            </div>

            {/* Resultados detallados */}
            <div className="max-h-64 overflow-y-auto space-y-2">
              {result.results?.map((r, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border ${
                    r.success
                      ? 'border-[var(--color-success)] bg-[var(--color-success)] bg-opacity-5'
                      : 'border-[var(--color-error)] bg-[var(--color-error)] bg-opacity-5'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span>{r.success ? '✅' : '❌'}</span>
                    <code className="font-medium">{r.filename}</code>
                    <span className="text-xs text-[var(--color-fg-tertiary)]">({r.action})</span>
                  </div>
                  <p className="text-sm text-[var(--color-fg-secondary)] mt-1">{r.message}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 text-center">
              <Button variant="primary" onClick={() => {
                setResult(null)
                loadGroups()
              }}>
                Nueva Operación
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          ⚡ Acciones en Lote
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Ejecuta operaciones masivas en grupos de archivos hermanos
        </p>
      </div>

      {error && (
        <div className="p-3 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] rounded-lg text-[var(--color-error)]">
          {error}
        </div>
      )}

      {/* Selector de scan */}
      <Card>
        <CardContent>
          <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
            Seleccionar análisis
          </label>
          {loadingScans ? (
            <p className="text-[var(--color-fg-secondary)]">Cargando...</p>
          ) : (
            <select
              value={selectedScan}
              onChange={(e) => setSelectedScan(e.target.value)}
              className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
            >
              <option value="">Seleccionar...</option>
              {scans.filter(s => s.files > 0).map((scan) => (
                <option key={scan.scan_id} value={scan.scan_id}>
                  {scan.project || scan.project_name || scan.scan_id} ({scan.files || 0} archivos)
                </option>
              ))}
            </select>
          )}
        </CardContent>
      </Card>

      {/* Lista de grupos */}
      {selectedScan && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>📁 Grupos de Hermanos ({groups.length})</CardTitle>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={applySuggestions}>
                  💡 Aplicar sugerencias
                </Button>
                <Button variant="ghost" size="sm" onClick={() => selectAll(selectedCount < groups.length)}>
                  {selectedCount < groups.length ? '☑️ Seleccionar todos' : '☐ Deseleccionar'}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
              </div>
            ) : groups.length === 0 ? (
              <p className="text-center text-[var(--color-fg-secondary)] py-8">
                No hay grupos de hermanos en este análisis
              </p>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {groups.map((group) => (
                  <GroupItem
                    key={group.filename}
                    group={group}
                    selected={selections[group.filename] || false}
                    action={actions[group.filename] || 'ignore'}
                    onSelect={handleSelect}
                    onActionChange={handleActionChange}
                  />
                ))}
              </div>
            )}
          </CardContent>
          <CardFooter className="justify-between">
            <span className="text-sm text-[var(--color-fg-secondary)]">
              {selectedCount} grupo(s) seleccionado(s)
            </span>
            <Button
              variant="primary"
              onClick={simulate}
              disabled={selectedCount === 0 || loading}
            >
              {loading ? '⏳' : '🔍'} Simular Acciones
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Modal de impacto */}
      {showImpact && impact && (
        <ImpactModal
          impact={impact}
          onClose={() => setShowImpact(false)}
          onExecute={execute}
          executing={executing}
        />
      )}
    </div>
  )
}
