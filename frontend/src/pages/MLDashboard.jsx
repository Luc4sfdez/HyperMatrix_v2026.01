import { useState, useCallback, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Barra de progreso para accuracy
function AccuracyBar({ value, label }) {
  const getColor = (v) => {
    if (v >= 0.8) return 'bg-[var(--color-success)]'
    if (v >= 0.5) return 'bg-[var(--color-warning)]'
    return 'bg-[var(--color-error)]'
  }

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-[var(--color-fg-secondary)]">{label}</span>
        <span className="font-bold text-[var(--color-fg-primary)]">
          {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-3 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor(value)} transition-all duration-500`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  )
}

// Tarjeta de patrón
function PatternCard({ pattern, rank }) {
  return (
    <div className="p-4 border border-[var(--color-border)] rounded-lg bg-[var(--color-bg-secondary)]">
      <div className="flex items-center gap-3 mb-2">
        <span className={`w-8 h-8 flex items-center justify-center rounded-full font-bold text-sm ${
          rank === 1 ? 'bg-yellow-500 text-black' :
          rank === 2 ? 'bg-gray-400 text-black' :
          rank === 3 ? 'bg-orange-600 text-white' :
          'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-secondary)]'
        }`}>
          #{rank}
        </span>
        <div className="flex-1">
          <span className="font-medium text-[var(--color-fg-primary)]">{pattern.pattern}</span>
          <div className="text-xs text-[var(--color-fg-tertiary)]">
            {pattern.count} ocurrencias
          </div>
        </div>
      </div>
      {pattern.preferred_action && (
        <div className="mt-2 px-3 py-1 bg-[var(--color-primary)] bg-opacity-10 rounded inline-block">
          <span className="text-xs font-medium text-[var(--color-primary)]">
            Acción preferida: {pattern.preferred_action}
          </span>
        </div>
      )}
    </div>
  )
}

// Gráfico de decisiones por tipo (simplificado)
function DecisionTypeChart({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="text-center py-8 text-[var(--color-fg-tertiary)]">
        No hay datos de decisiones
      </div>
    )
  }

  const total = Object.values(data).reduce((a, b) => a + b, 0)
  const colors = [
    'bg-[var(--color-primary)]',
    'bg-[var(--color-success)]',
    'bg-[var(--color-warning)]',
    'bg-[var(--color-error)]',
    'bg-[var(--color-info)]',
  ]

  return (
    <div className="space-y-4">
      {/* Barra apilada */}
      <div className="h-8 rounded-full overflow-hidden flex">
        {Object.entries(data).map(([type, count], idx) => (
          <div
            key={type}
            className={`${colors[idx % colors.length]} transition-all`}
            style={{ width: `${(count / total) * 100}%` }}
            title={`${type}: ${count}`}
          />
        ))}
      </div>

      {/* Leyenda */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {Object.entries(data).map(([type, count], idx) => (
          <div key={type} className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded ${colors[idx % colors.length]}`}></div>
            <span className="text-sm text-[var(--color-fg-secondary)]">
              {type}: <span className="font-bold">{count}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function MLDashboard({ hypermatrixUrl }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [exportPath, setExportPath] = useState('')
  const [importPath, setImportPath] = useState('')
  const [operationStatus, setOperationStatus] = useState(null)

  // Cargar estadísticas
  const loadStats = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/advanced/ml/stats`)

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setStats(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  // Exportar datos
  const exportData = async () => {
    if (!exportPath.trim()) return

    setOperationStatus({ type: 'export', status: 'loading' })

    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/advanced/ml/export?filepath=${encodeURIComponent(exportPath)}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      setOperationStatus({ type: 'export', status: 'success', message: `Exportado a ${exportPath}` })
    } catch (err) {
      setOperationStatus({ type: 'export', status: 'error', message: err.message })
    }
  }

  // Importar datos
  const importData = async () => {
    if (!importPath.trim()) return

    setOperationStatus({ type: 'import', status: 'loading' })

    try {
      const response = await fetch(
        `${hypermatrixUrl}/api/advanced/ml/import?filepath=${encodeURIComponent(importPath)}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setOperationStatus({
        type: 'import',
        status: 'success',
        message: `Importadas ${data.decisions_imported} decisiones`
      })
      loadStats() // Recargar stats
    } catch (err) {
      setOperationStatus({ type: 'import', status: 'error', message: err.message })
    }
  }

  // Limpiar datos
  const clearData = async () => {
    if (!confirm('¿Estás seguro de limpiar TODOS los datos de aprendizaje? Esta acción no se puede deshacer.')) {
      return
    }

    setOperationStatus({ type: 'clear', status: 'loading' })

    try {
      const response = await fetch(`${hypermatrixUrl}/api/advanced/ml/clear`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      setOperationStatus({ type: 'clear', status: 'success', message: 'Datos limpiados' })
      loadStats() // Recargar stats
    } catch (err) {
      setOperationStatus({ type: 'clear', status: 'error', message: err.message })
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
            🧠 Dashboard ML
          </h2>
          <p className="text-[var(--color-fg-secondary)]">
            Sistema de aprendizaje automático basado en tus decisiones
          </p>
        </div>
        <Button variant="secondary" onClick={loadStats} disabled={loading}>
          🔄 Actualizar
        </Button>
      </div>

      {error && (
        <div className="p-4 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] border-opacity-30 rounded-lg text-[var(--color-error)]">
          {error}
        </div>
      )}

      {loading && !stats ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-12 h-12 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
        </div>
      ) : stats ? (
        <>
          {/* Métricas principales */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="text-center py-6">
                <div className="text-4xl font-bold text-[var(--color-primary)]">
                  {stats.total_decisions || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)] mt-1">
                  Decisiones Totales
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="text-center py-6">
                <div className={`text-4xl font-bold ${
                  stats.accuracy_estimate >= 0.7 ? 'text-[var(--color-success)]' :
                  stats.accuracy_estimate >= 0.4 ? 'text-[var(--color-warning)]' :
                  'text-[var(--color-error)]'
                }`}>
                  {((stats.accuracy_estimate || 0) * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)] mt-1">
                  Precisión Estimada
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="text-center py-6">
                <div className="text-4xl font-bold text-[var(--color-fg-primary)]">
                  {Object.keys(stats.decisions_by_type || {}).length}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)] mt-1">
                  Tipos de Decisión
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="text-center py-6">
                <div className="text-4xl font-bold text-[var(--color-info)]">
                  {(stats.most_common_patterns || []).length}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)] mt-1">
                  Patrones Detectados
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Accuracy y decisiones */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Precisión */}
            <Card>
              <CardHeader>
                <CardTitle>📊 Precisión del Modelo</CardTitle>
              </CardHeader>
              <CardContent>
                <AccuracyBar
                  value={stats.accuracy_estimate || 0}
                  label="Accuracy Estimada"
                />
                <p className="text-xs text-[var(--color-fg-tertiary)] mt-4">
                  La precisión mejora con más datos de entrenamiento.
                  Se necesitan mínimo 100 decisiones para estimaciones confiables.
                </p>
                {stats.total_decisions < 100 && (
                  <div className="mt-3 p-3 bg-[var(--color-warning)] bg-opacity-10 rounded border border-[var(--color-warning)] border-opacity-30">
                    <p className="text-sm text-[var(--color-warning)]">
                      ⚠️ Pocas decisiones registradas ({stats.total_decisions}/100).
                      Continúa usando HyperMatrix para mejorar las recomendaciones.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Decisiones por tipo */}
            <Card>
              <CardHeader>
                <CardTitle>📈 Decisiones por Tipo</CardTitle>
              </CardHeader>
              <CardContent>
                <DecisionTypeChart data={stats.decisions_by_type} />
              </CardContent>
            </Card>
          </div>

          {/* Patrones más comunes */}
          {stats.most_common_patterns && stats.most_common_patterns.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>🔍 Patrones Más Comunes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {stats.most_common_patterns.slice(0, 6).map((pattern, idx) => (
                    <PatternCard key={idx} pattern={pattern} rank={idx + 1} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Última actualización */}
          {stats.last_updated && (
            <div className="text-center text-sm text-[var(--color-fg-tertiary)]">
              Última actualización: {new Date(stats.last_updated).toLocaleString()}
            </div>
          )}
        </>
      ) : null}

      {/* Gestión de datos */}
      <Card>
        <CardHeader>
          <CardTitle>💾 Gestión de Datos</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Export */}
          <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg space-y-3">
            <h4 className="font-medium text-[var(--color-fg-primary)]">📤 Exportar Datos</h4>
            <p className="text-sm text-[var(--color-fg-secondary)]">
              Guarda los datos de aprendizaje en un archivo JSON
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={exportPath}
                onChange={(e) => setExportPath(e.target.value)}
                placeholder="C:/ruta/ml_data.json"
                className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              />
              <Button
                variant="secondary"
                onClick={exportData}
                disabled={!exportPath.trim() || operationStatus?.status === 'loading'}
              >
                Exportar
              </Button>
            </div>
          </div>

          {/* Import */}
          <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg space-y-3">
            <h4 className="font-medium text-[var(--color-fg-primary)]">📥 Importar Datos</h4>
            <p className="text-sm text-[var(--color-fg-secondary)]">
              Carga datos de aprendizaje desde un archivo JSON
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={importPath}
                onChange={(e) => setImportPath(e.target.value)}
                placeholder="C:/ruta/ml_data.json"
                className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              />
              <Button
                variant="secondary"
                onClick={importData}
                disabled={!importPath.trim() || operationStatus?.status === 'loading'}
              >
                Importar
              </Button>
            </div>
          </div>

          {/* Clear */}
          <div className="p-4 bg-[var(--color-error)] bg-opacity-5 rounded-lg border border-[var(--color-error)] border-opacity-30 space-y-3">
            <h4 className="font-medium text-[var(--color-error)]">🗑️ Limpiar Datos</h4>
            <p className="text-sm text-[var(--color-fg-secondary)]">
              Elimina todos los datos de aprendizaje. Esta acción no se puede deshacer.
            </p>
            <Button
              variant="danger"
              onClick={clearData}
              disabled={operationStatus?.status === 'loading'}
            >
              Limpiar Todos los Datos
            </Button>
          </div>

          {/* Operation status */}
          {operationStatus && operationStatus.status !== 'loading' && (
            <div className={`p-3 rounded ${
              operationStatus.status === 'success'
                ? 'bg-[var(--color-success)] bg-opacity-10 text-[var(--color-success)]'
                : 'bg-[var(--color-error)] bg-opacity-10 text-[var(--color-error)]'
            }`}>
              {operationStatus.status === 'success' ? '✓' : '✕'} {operationStatus.message}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cómo funciona */}
      <Card>
        <CardHeader>
          <CardTitle>💡 ¿Cómo Funciona?</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-4xl mb-3">📊</div>
              <h4 className="font-medium text-[var(--color-fg-primary)] mb-2">1. Recopilación</h4>
              <p className="text-sm text-[var(--color-fg-secondary)]">
                Cada decisión que tomas (merge, conservar, eliminar) se registra automáticamente
              </p>
            </div>
            <div className="text-center">
              <div className="text-4xl mb-3">🧠</div>
              <h4 className="font-medium text-[var(--color-fg-primary)] mb-2">2. Aprendizaje</h4>
              <p className="text-sm text-[var(--color-fg-secondary)]">
                El sistema aprende patrones de tus decisiones basándose en características de archivos
              </p>
            </div>
            <div className="text-center">
              <div className="text-4xl mb-3">🎯</div>
              <h4 className="font-medium text-[var(--color-fg-primary)] mb-2">3. Recomendación</h4>
              <p className="text-sm text-[var(--color-fg-secondary)]">
                Cuando encuentres archivos similares, recibirás recomendaciones personalizadas
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Empty state si no hay datos */}
      {stats && stats.total_decisions === 0 && (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🧠</div>
              <h3 className="text-xl font-medium text-[var(--color-fg-primary)] mb-2">
                El Sistema Está Listo para Aprender
              </h3>
              <p className="text-[var(--color-fg-secondary)] max-w-md mx-auto">
                Comienza a usar HyperMatrix para escanear y consolidar archivos.
                Cada decisión que tomes ayudará a mejorar las recomendaciones futuras.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
