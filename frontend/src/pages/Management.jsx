import { useState, useEffect } from 'react'

/**
 * Management Page - Gestión separada de Workspace vs Análisis
 * Permite eliminar workspace, análisis o ambos independientemente
 */
export default function Management({ hypermatrixUrl }) {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionInProgress, setActionInProgress] = useState(null)
  const [confirmDialog, setConfirmDialog] = useState(null)
  const [previewData, setPreviewData] = useState(null)

  // Cargar proyectos
  const loadProjects = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${hypermatrixUrl}/api/management/projects/status`)
      if (!res.ok) throw new Error('Error cargando proyectos')
      const data = await res.json()
      setProjects(data.projects || [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProjects()
  }, [hypermatrixUrl])

  // Preview antes de eliminar
  const showPreview = async (projectId, type) => {
    setActionInProgress(`preview-${projectId}`)
    try {
      let endpoint
      if (type === 'workspace') {
        endpoint = `/api/management/workspace/${projectId}/preview`
      } else if (type === 'analysis') {
        endpoint = `/api/management/analysis/${projectId}/preview`
      } else {
        endpoint = `/api/management/project/${projectId}/preview`
      }

      const res = await fetch(`${hypermatrixUrl}${endpoint}`)
      const data = await res.json()

      setPreviewData({ type, projectId, data })
      setConfirmDialog({ type, projectId })
    } catch (err) {
      setError(err.message)
    } finally {
      setActionInProgress(null)
    }
  }

  // Ejecutar eliminación
  const executeDelete = async () => {
    if (!confirmDialog) return

    const { type, projectId } = confirmDialog
    setActionInProgress(`delete-${projectId}`)

    try {
      let endpoint
      if (type === 'workspace') {
        endpoint = `/api/management/workspace/${projectId}?confirm=true`
      } else if (type === 'analysis') {
        endpoint = `/api/management/analysis/${projectId}?confirm=true`
      } else {
        endpoint = `/api/management/project/${projectId}/all?confirm=true`
      }

      const res = await fetch(`${hypermatrixUrl}${endpoint}`, { method: 'DELETE' })
      const data = await res.json()

      if (data.success) {
        // Recargar lista
        await loadProjects()
        setConfirmDialog(null)
        setPreviewData(null)
      } else {
        throw new Error(data.detail || 'Error en eliminación')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setActionInProgress(null)
    }
  }

  const formatSize = (bytes) => {
    if (!bytes) return '0 B'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse flex items-center gap-2">
          <div className="w-6 h-6 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin"></div>
          <span>Cargando proyectos...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[var(--color-fg-primary)] flex items-center gap-2">
          🗂️ Gestión de Proyectos
        </h1>
        <p className="text-[var(--color-fg-secondary)] mt-1">
          Elimina workspace, análisis o ambos de forma independiente
        </p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-[var(--color-error-bg)] border border-[var(--color-error)] rounded-lg text-[var(--color-error)]">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Cerrar</button>
        </div>
      )}

      {/* Tabla de proyectos */}
      <div className="bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)] overflow-hidden">
        <table className="w-full">
          <thead className="bg-[var(--color-bg-tertiary)]">
            <tr>
              <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Proyecto</th>
              <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Workspace</th>
              <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Análisis (SQLite)</th>
              <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">ChromaDB</th>
              <th className="text-right p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => (
              <tr key={project.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                <td className="p-3">
                  <div className="font-medium text-[var(--color-fg-primary)]">{project.name}</div>
                  <div className="text-xs text-[var(--color-fg-tertiary)] truncate max-w-xs" title={project.root_path}>
                    {project.root_path}
                  </div>
                </td>
                <td className="p-3">
                  {project.workspace.exists ? (
                    <div>
                      <span className="text-[var(--color-success)]">✓</span>
                      <span className="ml-2 text-sm">{project.workspace.size_human}</span>
                    </div>
                  ) : (
                    <span className="text-[var(--color-fg-tertiary)]">—</span>
                  )}
                </td>
                <td className="p-3">
                  {project.analysis.exists ? (
                    <div className="text-sm">
                      <span className="text-[var(--color-success)]">✓</span>
                      <span className="ml-2">{project.analysis.files} archivos</span>
                      {project.analysis.functions > 0 && (
                        <span className="ml-1 text-[var(--color-fg-tertiary)]">
                          ({project.analysis.functions} func)
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-[var(--color-fg-tertiary)]">—</span>
                  )}
                </td>
                <td className="p-3">
                  {project.analysis.chromadb_docs > 0 ? (
                    <span className="text-sm">{project.analysis.chromadb_docs} docs</span>
                  ) : (
                    <span className="text-[var(--color-fg-tertiary)]">—</span>
                  )}
                </td>
                <td className="p-3 text-right">
                  <div className="flex gap-2 justify-end">
                    {project.workspace.exists && (
                      <button
                        onClick={() => showPreview(project.id, 'workspace')}
                        disabled={actionInProgress}
                        className="px-2 py-1 text-xs bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded hover:opacity-80 disabled:opacity-50"
                        title="Eliminar solo workspace"
                      >
                        🗑️ Workspace
                      </button>
                    )}
                    {project.analysis.exists && (
                      <button
                        onClick={() => showPreview(project.id, 'analysis')}
                        disabled={actionInProgress}
                        className="px-2 py-1 text-xs bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded hover:opacity-80 disabled:opacity-50"
                        title="Eliminar solo análisis"
                      >
                        🗑️ Análisis
                      </button>
                    )}
                    {(project.workspace.exists || project.analysis.exists) && (
                      <button
                        onClick={() => showPreview(project.id, 'all')}
                        disabled={actionInProgress}
                        className="px-2 py-1 text-xs bg-[var(--color-error-bg)] text-[var(--color-error)] rounded hover:opacity-80 disabled:opacity-50"
                        title="Eliminar TODO"
                      >
                        🗑️ Todo
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {projects.length === 0 && (
          <div className="p-8 text-center text-[var(--color-fg-tertiary)]">
            No hay proyectos
          </div>
        )}
      </div>

      {/* Leyenda */}
      <div className="mt-4 p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
        <h3 className="text-sm font-medium text-[var(--color-fg-primary)] mb-2">Leyenda:</h3>
        <div className="grid grid-cols-3 gap-4 text-xs text-[var(--color-fg-secondary)]">
          <div>
            <span className="font-medium">🗑️ Workspace:</span> Elimina archivos físicos, mantiene análisis
          </div>
          <div>
            <span className="font-medium">🗑️ Análisis:</span> Elimina SQLite + ChromaDB, mantiene archivos
          </div>
          <div>
            <span className="font-medium">🗑️ Todo:</span> Elimina workspace y análisis completamente
          </div>
        </div>
      </div>

      {/* Modal de confirmación */}
      {confirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-lg p-6 m-4">
            <h3 className="text-lg font-bold text-[var(--color-fg-primary)] mb-4">
              ⚠️ Confirmar eliminación
            </h3>

            {previewData && (
              <div className="mb-4 p-4 bg-[var(--color-bg-secondary)] rounded-lg text-sm">
                {confirmDialog.type === 'workspace' && previewData.data && (
                  <div>
                    <p className="font-medium mb-2">Se eliminarán los siguientes archivos:</p>
                    <div className="max-h-40 overflow-auto">
                      {previewData.data.files_to_delete?.slice(0, 10).map((f, i) => (
                        <div key={i} className="text-[var(--color-fg-tertiary)]">
                          {f.path} ({formatSize(f.size)})
                        </div>
                      ))}
                      {previewData.data.total_files > 10 && (
                        <div className="text-[var(--color-fg-tertiary)]">
                          ... y {previewData.data.total_files - 10} más
                        </div>
                      )}
                    </div>
                    <p className="mt-2 font-medium">
                      Total: {previewData.data.total_files} archivos ({previewData.data.total_size_human})
                    </p>
                    <p className="text-[var(--color-success)] mt-2">✓ El análisis se conservará</p>
                  </div>
                )}

                {confirmDialog.type === 'analysis' && previewData.data && (
                  <div>
                    <p className="font-medium mb-2">Se eliminarán los siguientes registros:</p>
                    <ul className="text-[var(--color-fg-tertiary)]">
                      <li>Archivos: {previewData.data.sqlite_records?.files || 0}</li>
                      <li>Funciones: {previewData.data.sqlite_records?.functions || 0}</li>
                      <li>Clases: {previewData.data.sqlite_records?.classes || 0}</li>
                      <li>Variables: {previewData.data.sqlite_records?.variables || 0}</li>
                      <li>Imports: {previewData.data.sqlite_records?.imports || 0}</li>
                      <li>ChromaDB docs: {previewData.data.chromadb_docs || 0}</li>
                    </ul>
                    <p className="mt-2 font-medium">
                      Total: {previewData.data.sqlite_total} registros SQLite
                    </p>
                    <p className="text-[var(--color-success)] mt-2">✓ Los archivos del workspace se conservarán</p>
                  </div>
                )}

                {confirmDialog.type === 'all' && previewData.data && (
                  <div>
                    <p className="font-medium text-[var(--color-error)] mb-2">
                      Se eliminará TODO el proyecto:
                    </p>
                    <ul className="text-[var(--color-fg-tertiary)]">
                      <li>Archivos: {previewData.data.workspace?.total_files || 0} ({previewData.data.workspace?.total_size_human})</li>
                      <li>Registros SQLite: {previewData.data.analysis?.sqlite_total || 0}</li>
                      <li>ChromaDB docs: {previewData.data.analysis?.chromadb_docs || 0}</li>
                    </ul>
                    <p className="text-[var(--color-error)] mt-2 font-medium">
                      ⚠️ Esta acción es IRREVERSIBLE
                    </p>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setConfirmDialog(null)
                  setPreviewData(null)
                }}
                className="px-4 py-2 bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] rounded hover:bg-[var(--color-bg-tertiary)]"
              >
                Cancelar
              </button>
              <button
                onClick={executeDelete}
                disabled={actionInProgress}
                className="px-4 py-2 bg-[var(--color-error)] text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {actionInProgress ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Eliminando...
                  </>
                ) : (
                  'Confirmar eliminación'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
