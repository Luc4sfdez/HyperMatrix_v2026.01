import { useState, useCallback } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Barra de ratio
function RatioBar({ label, value, total }) {
  const percent = total > 0 ? (value / total) * 100 : 0

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-[var(--color-fg-secondary)]">{label}</span>
        <span className="font-medium text-[var(--color-fg-primary)]">
          {percent.toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
        <div
          className="h-full bg-[var(--color-primary)] transition-all duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}

// Tabla de archivos
function FileMatchTable({ title, matches, columns, emptyMessage }) {
  const [showAll, setShowAll] = useState(false)
  const displayItems = showAll ? matches : matches.slice(0, 10)

  if (matches.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-[var(--color-fg-secondary)] py-4">
            {emptyMessage || 'No hay coincidencias'}
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {title}
          <span className="ml-2 text-sm font-normal text-[var(--color-fg-secondary)]">
            ({matches.length})
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-bg-secondary)]">
              <tr>
                {columns.map((col, idx) => (
                  <th key={idx} className="px-3 py-2 text-left text-[var(--color-fg-secondary)]">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {displayItems.map((item, idx) => (
                <tr key={idx} className="hover:bg-[var(--color-bg-secondary)]">
                  {columns.map((col, cidx) => (
                    <td key={cidx} className="px-3 py-2 text-[var(--color-fg-primary)]">
                      {col.render ? col.render(item) : item[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {matches.length > 10 && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="w-full py-2 text-center text-sm text-[var(--color-primary)] hover:underline mt-2"
          >
            {showAll ? 'Mostrar menos' : `Ver ${matches.length - 10} más`}
          </button>
        )}
      </CardContent>
    </Card>
  )
}

export default function ProjectCompare({ hypermatrixUrl }) {
  const [project1, setProject1] = useState({ path: '', name: '' })
  const [project2, setProject2] = useState({ path: '', name: '' })
  const [deepCompare, setDeepCompare] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [results, setResults] = useState(null)

  // Comparar proyectos
  const compare = useCallback(async () => {
    if (!project1.path || !project1.name || !project2.path || !project2.name) {
      setError('Completa todos los campos')
      return
    }

    setLoading(true)
    setError(null)
    setResults(null)

    try {
      const params = new URLSearchParams({
        project1_path: project1.path,
        project1_name: project1.name,
        project2_path: project2.path,
        project2_name: project2.name,
        deep_compare: deepCompare.toString(),
      })

      const response = await fetch(`${hypermatrixUrl}/api/advanced/compare/projects?${params}`, {
        method: 'POST',
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, project1, project2, deepCompare])

  // Auto-generar nombre desde path
  const autoName = (path) => {
    if (!path) return ''
    const parts = path.replace(/\\/g, '/').split('/')
    return parts[parts.length - 1] || parts[parts.length - 2] || 'proyecto'
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
          🔄 Comparación entre Proyectos
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Encuentra código compartido, duplicado y similitudes entre dos proyectos
        </p>
      </div>

      {error && (
        <div className="p-3 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] rounded-lg text-[var(--color-error)]">
          {error}
        </div>
      )}

      {/* Inputs de proyectos */}
      <Card>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Proyecto 1 */}
            <div className="space-y-3 p-4 bg-[var(--color-bg-secondary)] rounded-lg">
              <h4 className="font-medium text-[var(--color-primary)]">📁 Proyecto 1</h4>
              <div>
                <label className="block text-sm text-[var(--color-fg-secondary)] mb-1">Ruta</label>
                <input
                  type="text"
                  value={project1.path}
                  onChange={(e) => {
                    setProject1({ path: e.target.value, name: project1.name || autoName(e.target.value) })
                  }}
                  placeholder="C:/proyectos/proyecto-a"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="block text-sm text-[var(--color-fg-secondary)] mb-1">Nombre</label>
                <input
                  type="text"
                  value={project1.name}
                  onChange={(e) => setProject1({ ...project1, name: e.target.value })}
                  placeholder="proyecto-a"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
            </div>

            {/* Proyecto 2 */}
            <div className="space-y-3 p-4 bg-[var(--color-bg-secondary)] rounded-lg">
              <h4 className="font-medium text-[var(--color-warning)]">📁 Proyecto 2</h4>
              <div>
                <label className="block text-sm text-[var(--color-fg-secondary)] mb-1">Ruta</label>
                <input
                  type="text"
                  value={project2.path}
                  onChange={(e) => {
                    setProject2({ path: e.target.value, name: project2.name || autoName(e.target.value) })
                  }}
                  placeholder="C:/proyectos/proyecto-b"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="block text-sm text-[var(--color-fg-secondary)] mb-1">Nombre</label>
                <input
                  type="text"
                  value={project2.name}
                  onChange={(e) => setProject2({ ...project2, name: e.target.value })}
                  placeholder="proyecto-b"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
            </div>
          </div>

          {/* Opciones */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-[var(--color-fg-secondary)]">
              <input
                type="checkbox"
                checked={deepCompare}
                onChange={(e) => setDeepCompare(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              Comparación profunda (más precisa pero más lenta)
            </label>
          </div>

          <Button
            variant="primary"
            onClick={compare}
            disabled={loading || !project1.path || !project1.name || !project2.path || !project2.name}
          >
            {loading ? '⏳ Comparando...' : '🔍 Comparar Proyectos'}
          </Button>
        </CardContent>
      </Card>

      {/* Resultados */}
      {results && (
        <>
          {/* Resumen */}
          <Card>
            <CardHeader>
              <CardTitle>📊 Resumen de Comparación</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-center gap-4 text-lg">
                <span className="font-bold text-[var(--color-primary)]">{results.projects?.[0]}</span>
                <span className="text-[var(--color-fg-tertiary)]">vs</span>
                <span className="font-bold text-[var(--color-warning)]">{results.projects?.[1]}</span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                    {results.total_files?.project1 || 0}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Archivos P1</div>
                </div>
                <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-fg-primary)]">
                    {results.total_files?.project2 || 0}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Archivos P2</div>
                </div>
                <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-success)]">
                    {results.exact_matches?.length || 0}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Exactos</div>
                </div>
                <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                  <div className="text-2xl font-bold text-[var(--color-warning)]">
                    {results.similar_matches?.length || 0}
                  </div>
                  <div className="text-xs text-[var(--color-fg-secondary)]">Similares</div>
                </div>
              </div>

              {results.summary && (
                <p className="text-[var(--color-fg-secondary)] text-sm bg-[var(--color-bg-secondary)] p-3 rounded">
                  {results.summary}
                </p>
              )}

              {/* Ratios de código compartido */}
              {results.shared_code_ratio && (
                <div className="space-y-3 pt-4 border-t border-[var(--color-border)]">
                  <h4 className="font-medium text-[var(--color-fg-primary)]">Código Compartido</h4>
                  {Object.entries(results.shared_code_ratio).map(([key, value]) => (
                    <RatioBar
                      key={key}
                      label={key.replace(/_/g, ' ')}
                      value={value * 100}
                      total={100}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Archivos exactos */}
          <FileMatchTable
            title="📋 Archivos Idénticos"
            matches={results.exact_matches || []}
            columns={[
              {
                key: 'project1_file',
                label: `${results.projects?.[0] || 'P1'}`,
                render: (item) => <code className="text-xs truncate block max-w-xs">{item.project1_file}</code>
              },
              {
                key: 'project2_file',
                label: `${results.projects?.[1] || 'P2'}`,
                render: (item) => <code className="text-xs truncate block max-w-xs">{item.project2_file}</code>
              },
              {
                key: 'common_lines',
                label: 'Líneas',
                render: (item) => <span className="font-mono">{item.common_lines}</span>
              },
            ]}
            emptyMessage="No hay archivos idénticos"
          />

          {/* Archivos similares */}
          <FileMatchTable
            title="🔗 Archivos Similares"
            matches={results.similar_matches || []}
            columns={[
              {
                key: 'project1_file',
                label: `${results.projects?.[0] || 'P1'}`,
                render: (item) => <code className="text-xs truncate block max-w-xs">{item.project1_file}</code>
              },
              {
                key: 'project2_file',
                label: `${results.projects?.[1] || 'P2'}`,
                render: (item) => <code className="text-xs truncate block max-w-xs">{item.project2_file}</code>
              },
              {
                key: 'similarity',
                label: 'Similitud',
                render: (item) => (
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    item.similarity >= 0.8
                      ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
                      : 'bg-[var(--color-warning)] bg-opacity-20 text-[var(--color-warning)]'
                  }`}>
                    {(item.similarity * 100).toFixed(0)}%
                  </span>
                )
              },
              {
                key: 'match_type',
                label: 'Tipo',
                render: (item) => <span className="text-xs text-[var(--color-fg-tertiary)]">{item.match_type}</span>
              },
            ]}
            emptyMessage="No hay archivos similares"
          />

          {/* Archivos únicos */}
          {results.unique_files && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(results.unique_files).map(([project, files]) => (
                <Card key={project}>
                  <CardHeader>
                    <CardTitle className="text-base">
                      📄 Únicos en {project}
                      <span className="ml-2 text-sm font-normal text-[var(--color-fg-secondary)]">
                        ({files.length})
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {files.length > 0 ? (
                      <ul className="space-y-1 max-h-48 overflow-y-auto">
                        {files.map((file, idx) => (
                          <li key={idx} className="text-xs font-mono text-[var(--color-fg-secondary)] truncate">
                            {file}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-center text-[var(--color-fg-tertiary)] text-sm py-2">
                        No hay archivos únicos
                      </p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Patrones comunes */}
          {results.common_patterns?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>🎯 Patrones Comunes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {results.common_patterns.map((pattern, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] rounded-full text-sm"
                    >
                      {pattern}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
