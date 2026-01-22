import { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../components/Card'
import { Button } from '../components/Button'

// Opciones de resolución de conflictos
const CONFLICT_RESOLUTIONS = [
  { value: 'manual', label: 'Manual', description: 'Requiere aprobación manual para cada conflicto' },
  { value: 'keep_largest', label: 'Mantener mayor', description: 'Conserva el archivo más grande' },
  { value: 'keep_complex', label: 'Mantener complejo', description: 'Conserva el archivo con más complejidad' },
  { value: 'keep_newest', label: 'Mantener reciente', description: 'Conserva el archivo más reciente' },
  { value: 'keep_all', label: 'Mantener todos', description: 'No fusiona automáticamente' },
]

// Componente para lista de patrones editable
function PatternList({ title, patterns, onAdd, onRemove, placeholder }) {
  const [newPattern, setNewPattern] = useState('')

  const handleAdd = () => {
    if (newPattern.trim()) {
      onAdd(newPattern.trim())
      setNewPattern('')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleAdd()
    }
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-[var(--color-fg-primary)]">
        {title}
      </label>
      <div className="flex gap-2">
        <input
          type="text"
          value={newPattern}
          onChange={(e) => setNewPattern(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          className="flex-1 px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
        />
        <Button variant="secondary" size="sm" onClick={handleAdd}>
          + Añadir
        </Button>
      </div>
      {patterns.length > 0 ? (
        <div className="flex flex-wrap gap-2 mt-2">
          {patterns.map((pattern, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 px-2 py-1 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-md text-sm font-mono"
            >
              {pattern}
              <button
                onClick={() => onRemove(pattern)}
                className="ml-1 text-[var(--color-fg-tertiary)] hover:text-[var(--color-error)]"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-[var(--color-fg-tertiary)] italic">Sin patrones configurados</p>
      )}
    </div>
  )
}

export default function Rules({ hypermatrixUrl }) {
  const [rules, setRules] = useState(null)
  const [presets, setPresets] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [validation, setValidation] = useState(null)

  // Cargar reglas y presets
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [rulesRes, presetsRes] = await Promise.all([
        fetch(`${hypermatrixUrl}/api/rules/`),
        fetch(`${hypermatrixUrl}/api/rules/presets`),
      ])

      if (rulesRes.ok) {
        const rulesData = await rulesRes.json()
        setRules(rulesData)
      }

      if (presetsRes.ok) {
        const presetsData = await presetsRes.json()
        setPresets(presetsData.presets || [])
      }
    } catch (err) {
      setError('Error cargando configuración: ' + err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Guardar reglas
  const saveRules = async () => {
    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/rules/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rules),
      })

      if (response.ok) {
        setSuccess('Reglas guardadas correctamente')
        setTimeout(() => setSuccess(null), 3000)
        validateRules()
      } else {
        throw new Error('Error al guardar')
      }
    } catch (err) {
      setError('Error guardando reglas: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // Aplicar preset
  const applyPreset = async (presetName) => {
    setSaving(true)
    setError(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/rules/apply-preset/${presetName}`, {
        method: 'POST',
      })

      if (response.ok) {
        const data = await response.json()
        setRules(data.config)
        setSuccess(`Preset "${presetName}" aplicado`)
        setTimeout(() => setSuccess(null), 3000)
      }
    } catch (err) {
      setError('Error aplicando preset: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // Reset a defaults
  const resetRules = async () => {
    if (!confirm('¿Restablecer todas las reglas a valores por defecto?')) return

    setSaving(true)
    setError(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/rules/reset`, {
        method: 'POST',
      })

      if (response.ok) {
        const data = await response.json()
        setRules(data.config)
        setSuccess('Reglas restablecidas')
        setTimeout(() => setSuccess(null), 3000)
      }
    } catch (err) {
      setError('Error restableciendo reglas: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // Validar reglas
  const validateRules = async () => {
    try {
      const response = await fetch(`${hypermatrixUrl}/api/rules/validate`)
      if (response.ok) {
        const data = await response.json()
        setValidation(data)
      }
    } catch (err) {
      console.error('Error validando:', err)
    }
  }

  // Actualizar campo simple
  const updateField = (field, value) => {
    setRules((prev) => ({ ...prev, [field]: value }))
  }

  // Añadir patrón
  const addPattern = (field, pattern) => {
    setRules((prev) => ({
      ...prev,
      [field]: [...(prev[field] || []), pattern],
    }))
  }

  // Eliminar patrón
  const removePattern = (field, pattern) => {
    setRules((prev) => ({
      ...prev,
      [field]: (prev[field] || []).filter((p) => p !== pattern),
    }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          📋 Reglas de Consolidación
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Configura cómo HyperMatrix determina archivos maestros y resuelve conflictos
        </p>
      </div>

      {/* Mensajes */}
      {error && (
        <div className="p-3 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] rounded-lg text-[var(--color-error)]">
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 bg-[var(--color-success)] bg-opacity-10 border border-[var(--color-success)] rounded-lg text-[var(--color-success)]">
          {success}
        </div>
      )}

      {/* Presets */}
      <Card>
        <CardHeader>
          <CardTitle>🎯 Presets Rápidos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {presets.map((preset) => (
              <button
                key={preset.name}
                onClick={() => applyPreset(preset.name)}
                disabled={saving}
                className="p-4 text-left border border-[var(--color-border)] rounded-lg hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-secondary)] transition-all disabled:opacity-50"
              >
                <h4 className="font-semibold text-[var(--color-fg-primary)] capitalize">
                  {preset.name}
                </h4>
                <p className="text-xs text-[var(--color-fg-secondary)] mt-1">
                  {preset.description}
                </p>
                <div className="mt-2 text-xs text-[var(--color-fg-tertiary)]">
                  Umbral: {preset.config.min_affinity_threshold}
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {rules && (
        <>
          {/* Configuración principal */}
          <Card>
            <CardHeader>
              <CardTitle>⚙️ Configuración Principal</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Umbral de afinidad */}
              <div>
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Umbral mínimo de afinidad
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={rules.min_affinity_threshold}
                    onChange={(e) => updateField('min_affinity_threshold', parseFloat(e.target.value))}
                    className="flex-1"
                  />
                  <span className="w-16 text-center font-mono text-lg font-bold text-[var(--color-primary)]">
                    {(rules.min_affinity_threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
                  Archivos con similitud menor a este umbral no serán considerados duplicados
                </p>
              </div>

              {/* Resolución de conflictos */}
              <div>
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Resolución de conflictos
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {CONFLICT_RESOLUTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => updateField('conflict_resolution', option.value)}
                      className={`p-3 text-left border rounded-lg transition-all ${
                        rules.conflict_resolution === option.value
                          ? 'border-[var(--color-primary)] bg-[var(--color-primary)] bg-opacity-10'
                          : 'border-[var(--color-border)] hover:border-[var(--color-fg-tertiary)]'
                      }`}
                    >
                      <div className="font-medium text-[var(--color-fg-primary)]">
                        {option.label}
                      </div>
                      <div className="text-xs text-[var(--color-fg-secondary)] mt-1">
                        {option.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto commit */}
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="auto_commit"
                  checked={rules.auto_commit || false}
                  onChange={(e) => updateField('auto_commit', e.target.checked)}
                  className="w-5 h-5 rounded border-[var(--color-border)]"
                />
                <label htmlFor="auto_commit" className="text-sm text-[var(--color-fg-primary)]">
                  Auto-commit después de merge (solo si hay control de versiones)
                </label>
              </div>
            </CardContent>
          </Card>

          {/* Patrones */}
          <Card>
            <CardHeader>
              <CardTitle>📁 Patrones de Archivos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <PatternList
                title="Rutas preferidas para maestro"
                patterns={rules.prefer_paths || []}
                onAdd={(p) => addPattern('prefer_paths', p)}
                onRemove={(p) => removePattern('prefer_paths', p)}
                placeholder="ej: src/*, lib/*, core/*"
              />

              <PatternList
                title="Nunca usar como maestro"
                patterns={rules.never_master_from || []}
                onAdd={(p) => addPattern('never_master_from', p)}
                onRemove={(p) => removePattern('never_master_from', p)}
                placeholder="ej: backup/*, temp/*, old/*"
              />

              <PatternList
                title="Patrones a ignorar"
                patterns={rules.ignore_patterns || []}
                onAdd={(p) => addPattern('ignore_patterns', p)}
                onRemove={(p) => removePattern('ignore_patterns', p)}
                placeholder="ej: *.pyc, __pycache__, node_modules/*"
              />
            </CardContent>
          </Card>

          {/* Validación */}
          {validation && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {validation.valid ? '✅' : '⚠️'}
                  Estado de validación
                </CardTitle>
              </CardHeader>
              <CardContent>
                {validation.valid ? (
                  <p className="text-[var(--color-success)]">La configuración es válida</p>
                ) : (
                  <ul className="space-y-1">
                    {validation.issues.map((issue, idx) => (
                      <li key={idx} className="text-[var(--color-error)] text-sm">
                        • {issue}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}

          {/* Acciones */}
          <Card>
            <CardFooter className="flex justify-between">
              <Button variant="ghost" onClick={resetRules} disabled={saving}>
                🔄 Restablecer
              </Button>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={validateRules} disabled={saving}>
                  ✓ Validar
                </Button>
                <Button variant="primary" onClick={saveRules} disabled={saving}>
                  {saving ? '⏳ Guardando...' : '💾 Guardar Reglas'}
                </Button>
              </div>
            </CardFooter>
          </Card>

          {/* Vista previa JSON */}
          <Card>
            <CardHeader>
              <CardTitle>📄 Vista Previa (YAML)</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="bg-[var(--color-bg-secondary)] p-4 rounded-lg text-xs font-mono overflow-x-auto">
{`prefer_paths:
${(rules.prefer_paths || []).map(p => `  - "${p}"`).join('\n') || '  []'}

never_master_from:
${(rules.never_master_from || []).map(p => `  - "${p}"`).join('\n') || '  []'}

ignore_patterns:
${(rules.ignore_patterns || []).map(p => `  - "${p}"`).join('\n') || '  []'}

min_affinity_threshold: ${rules.min_affinity_threshold}
conflict_resolution: "${rules.conflict_resolution}"
auto_commit: ${rules.auto_commit || false}`}
              </pre>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
