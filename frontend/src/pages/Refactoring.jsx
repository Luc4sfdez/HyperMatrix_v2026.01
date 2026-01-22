import { useState, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Badge de severidad
function SeverityBadge({ severity }) {
  const colors = {
    high: 'bg-[var(--color-error)] text-white',
    medium: 'bg-[var(--color-warning)] text-black',
    low: 'bg-[var(--color-info)] text-white',
  }

  const labels = {
    high: 'Alta',
    medium: 'Media',
    low: 'Baja',
  }

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || colors.low}`}>
      {labels[severity] || severity}
    </span>
  )
}

// Icono por tipo de sugerencia
function TypeIcon({ type }) {
  const icons = {
    long_function: '📏',
    high_complexity: '🔀',
    deep_nesting: '📐',
    duplicate_code: '📋',
    naming_issue: '🏷️',
    unused_variable: '🗑️',
    magic_number: '🔢',
    god_class: '👑',
    feature_envy: '👀',
  }
  return <span className="text-lg">{icons[type] || '💡'}</span>
}

// Tarjeta de sugerencia individual
function SuggestionCard({ suggestion, expanded, onToggle }) {
  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden hover:border-[var(--color-primary)] transition-colors">
      <div
        className="p-4 cursor-pointer flex items-start gap-3 bg-[var(--color-bg-secondary)]"
        onClick={onToggle}
      >
        <TypeIcon type={suggestion.type} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={suggestion.severity} />
            <span className="text-xs text-[var(--color-fg-tertiary)] font-mono">
              {suggestion.type}
            </span>
          </div>
          <h4 className="font-medium text-[var(--color-fg-primary)] truncate">
            {suggestion.title}
          </h4>
          <p className="text-xs text-[var(--color-fg-tertiary)] truncate mt-1">
            {suggestion.file}:{suggestion.line}
          </p>
        </div>
        <span className="text-[var(--color-fg-tertiary)]">
          {expanded ? '▼' : '▶'}
        </span>
      </div>

      {expanded && (
        <div className="p-4 bg-[var(--color-bg-primary)] border-t border-[var(--color-border)]">
          <p className="text-sm text-[var(--color-fg-secondary)] mb-3">
            {suggestion.description}
          </p>
          {suggestion.code_snippet && (
            <div className="bg-[var(--color-bg-tertiary)] rounded p-3 overflow-x-auto">
              <pre className="text-xs font-mono text-[var(--color-fg-primary)]">
                {suggestion.code_snippet}
              </pre>
            </div>
          )}
          {suggestion.suggestion && (
            <div className="mt-3 p-3 bg-[var(--color-success)] bg-opacity-10 rounded border border-[var(--color-success)] border-opacity-30">
              <p className="text-sm text-[var(--color-success)]">
                💡 {suggestion.suggestion}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Quick Win Card
function QuickWinCard({ win }) {
  return (
    <div className="p-4 border border-[var(--color-success)] border-opacity-50 rounded-lg bg-[var(--color-success)] bg-opacity-5">
      <div className="flex items-start gap-3">
        <span className="text-2xl">⚡</span>
        <div className="flex-1">
          <h4 className="font-medium text-[var(--color-fg-primary)]">{win.title}</h4>
          <p className="text-sm text-[var(--color-fg-secondary)] mt-1">{win.description}</p>
          <div className="flex items-center gap-4 mt-2 text-xs">
            <span className="text-[var(--color-fg-tertiary)] font-mono">
              {win.file}:{win.line}
            </span>
            {win.impact && (
              <span className="text-[var(--color-success)] font-medium">
                Impacto: {win.impact}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Refactoring({ hypermatrixUrl }) {
  const [inputMode, setInputMode] = useState('files') // 'files' or 'directory'
  const [filesInput, setFilesInput] = useState('')
  const [directoryInput, setDirectoryInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [results, setResults] = useState(null)
  const [quickWins, setQuickWins] = useState(null)
  const [expandedSuggestions, setExpandedSuggestions] = useState({})
  const [activeTab, setActiveTab] = useState('all') // 'all', 'high', 'medium', 'low', 'quickwins'

  // Obtener lista de archivos
  const getFiles = useCallback(() => {
    if (inputMode === 'files') {
      return filesInput
        .split('\n')
        .map(f => f.trim())
        .filter(f => f.length > 0)
    } else {
      // Para directorio, el backend buscará archivos .py
      return [directoryInput.trim()]
    }
  }, [inputMode, filesInput, directoryInput])

  // Analizar archivos
  const analyze = useCallback(async () => {
    const files = getFiles()
    if (files.length === 0) {
      setError('Ingresa al menos un archivo o directorio')
      return
    }

    setLoading(true)
    setError(null)
    setResults(null)
    setQuickWins(null)

    try {
      // Construir query string
      const params = new URLSearchParams()
      files.forEach(f => params.append('files', f))

      // Análisis completo
      const response = await fetch(
        `${hypermatrixUrl}/api/advanced/refactoring/analyze?${params.toString()}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setResults(data)

      // También obtener quick wins
      const qwResponse = await fetch(
        `${hypermatrixUrl}/api/advanced/refactoring/quick-wins?${params.toString()}`
      )

      if (qwResponse.ok) {
        const qwData = await qwResponse.json()
        setQuickWins(qwData)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, getFiles])

  // Toggle expansión de sugerencia
  const toggleSuggestion = (index) => {
    setExpandedSuggestions(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  // Obtener sugerencias filtradas
  const getFilteredSuggestions = () => {
    if (!results) return []

    if (activeTab === 'all') {
      return [
        ...(results.by_severity?.high || []),
        ...(results.by_severity?.medium || []),
        ...(results.by_severity?.low || []),
      ]
    }

    return results.by_severity?.[activeTab] || []
  }

  const filteredSuggestions = getFilteredSuggestions()

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          🔧 Sugerencias de Refactoring
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Analiza tu código y obtén sugerencias para mejorar su calidad
        </p>
      </div>

      {/* Input Section */}
      <Card>
        <CardContent className="space-y-4">
          {/* Mode Toggle */}
          <div className="flex gap-2">
            <button
              onClick={() => setInputMode('files')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                inputMode === 'files'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              📄 Archivos
            </button>
            <button
              onClick={() => setInputMode('directory')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                inputMode === 'directory'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
              }`}
            >
              📁 Directorio
            </button>
          </div>

          {inputMode === 'files' ? (
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Archivos Python (uno por línea)
              </label>
              <textarea
                value={filesInput}
                onChange={(e) => setFilesInput(e.target.value)}
                placeholder="C:/proyecto/src/main.py&#10;C:/proyecto/src/utils.py&#10;C:/proyecto/src/models.py"
                rows={5}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] font-mono text-sm focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Directorio a analizar
              </label>
              <input
                type="text"
                value={directoryInput}
                onChange={(e) => setDirectoryInput(e.target.value)}
                placeholder="C:/proyecto/src"
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          )}

          <Button
            variant="primary"
            onClick={analyze}
            disabled={loading}
          >
            {loading ? '⏳ Analizando...' : '🔍 Analizar Código'}
          </Button>

          {error && (
            <p className="text-[var(--color-error)] text-sm bg-[var(--color-error)] bg-opacity-10 p-3 rounded">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {results && (
        <>
          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle>📊 Resumen del Análisis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                  <div className="text-3xl font-bold text-[var(--color-fg-primary)]">
                    {results.total_suggestions || 0}
                  </div>
                  <div className="text-sm text-[var(--color-fg-secondary)]">Total</div>
                </div>
                <div className="text-center p-4 bg-[var(--color-error)] bg-opacity-10 rounded-lg">
                  <div className="text-3xl font-bold text-[var(--color-error)]">
                    {results.by_severity?.high?.length || 0}
                  </div>
                  <div className="text-sm text-[var(--color-fg-secondary)]">Alta Prioridad</div>
                </div>
                <div className="text-center p-4 bg-[var(--color-warning)] bg-opacity-10 rounded-lg">
                  <div className="text-3xl font-bold text-[var(--color-warning)]">
                    {results.by_severity?.medium?.length || 0}
                  </div>
                  <div className="text-sm text-[var(--color-fg-secondary)]">Media</div>
                </div>
                <div className="text-center p-4 bg-[var(--color-info)] bg-opacity-10 rounded-lg">
                  <div className="text-3xl font-bold text-[var(--color-info)]">
                    {results.by_severity?.low?.length || 0}
                  </div>
                  <div className="text-sm text-[var(--color-fg-secondary)]">Baja</div>
                </div>
              </div>

              {/* Files analyzed */}
              <div className="mt-4 text-sm text-[var(--color-fg-tertiary)]">
                Archivos analizados: {results.files_analyzed || 0}
              </div>
            </CardContent>
          </Card>

          {/* Quick Wins */}
          {quickWins && quickWins.quick_wins_count > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>⚡ Quick Wins ({quickWins.quick_wins_count})</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-[var(--color-fg-secondary)] mb-4">
                  Cambios de bajo esfuerzo con alto impacto
                </p>
                <div className="space-y-3">
                  {quickWins.quick_wins.slice(0, 10).map((win, idx) => (
                    <QuickWinCard key={idx} win={win} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Suggestions by Tab */}
          <Card>
            <CardHeader>
              <CardTitle>💡 Sugerencias de Refactoring</CardTitle>
            </CardHeader>
            <CardContent>
              {/* Tabs */}
              <div className="flex flex-wrap gap-2 mb-4 border-b border-[var(--color-border)] pb-4">
                <button
                  onClick={() => setActiveTab('all')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'all'
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                  }`}
                >
                  Todas ({results.total_suggestions || 0})
                </button>
                <button
                  onClick={() => setActiveTab('high')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'high'
                      ? 'bg-[var(--color-error)] text-white'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                  }`}
                >
                  Alta ({results.by_severity?.high?.length || 0})
                </button>
                <button
                  onClick={() => setActiveTab('medium')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'medium'
                      ? 'bg-[var(--color-warning)] text-black'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                  }`}
                >
                  Media ({results.by_severity?.medium?.length || 0})
                </button>
                <button
                  onClick={() => setActiveTab('low')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'low'
                      ? 'bg-[var(--color-info)] text-white'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                  }`}
                >
                  Baja ({results.by_severity?.low?.length || 0})
                </button>
              </div>

              {/* Suggestion List */}
              {filteredSuggestions.length > 0 ? (
                <div className="space-y-3">
                  {filteredSuggestions.map((suggestion, idx) => (
                    <SuggestionCard
                      key={`${activeTab}-${idx}`}
                      suggestion={suggestion}
                      expanded={expandedSuggestions[`${activeTab}-${idx}`]}
                      onToggle={() => toggleSuggestion(`${activeTab}-${idx}`)}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-[var(--color-fg-tertiary)]">
                  No hay sugerencias en esta categoría
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Empty State */}
      {!results && !loading && (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🔧</div>
              <h3 className="text-xl font-medium text-[var(--color-fg-primary)] mb-2">
                Mejora tu Código
              </h3>
              <p className="text-[var(--color-fg-secondary)] max-w-md mx-auto">
                Ingresa archivos Python para obtener sugerencias de refactoring.
                Detectamos funciones largas, código duplicado, complejidad alta,
                y más problemas comunes.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
