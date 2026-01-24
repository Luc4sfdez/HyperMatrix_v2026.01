import { useState, useEffect, useRef } from 'react'

/**
 * Context Page - Agregador de documentos de contexto
 * Permite subir archivos sueltos (specs, requirements, notas) y vincularlos a proyectos
 */
export default function Context({ hypermatrixUrl }) {
  const [projects, setProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState(null)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [previewDoc, setPreviewDoc] = useState(null)
  const [previewContent, setPreviewContent] = useState(null)
  const fileInputRef = useRef(null)

  // Supported file types
  const SUPPORTED_TYPES = ['.txt', '.md', '.pdf', '.html', '.json', '.yaml', '.yml', '.zip']

  // Load projects
  const loadProjects = async () => {
    try {
      const res = await fetch(`${hypermatrixUrl}/api/context/projects`)
      if (!res.ok) throw new Error('Error loading projects')
      const data = await res.json()
      setProjects(data.projects || [])

      // Select first project if none selected
      if (!selectedProject && data.projects?.length > 0) {
        setSelectedProject(data.projects[0].id)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  // Load documents for selected project
  const loadDocuments = async (projectId) => {
    if (!projectId) return

    setLoading(true)
    try {
      const res = await fetch(`${hypermatrixUrl}/api/context/${projectId}`)
      if (!res.ok) throw new Error('Error loading documents')
      const data = await res.json()
      setDocuments(data.documents || [])
      setError(null)
    } catch (err) {
      setError(err.message)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProjects()
  }, [hypermatrixUrl])

  useEffect(() => {
    if (selectedProject) {
      loadDocuments(selectedProject)
    }
  }, [selectedProject])

  // Handle file upload
  const handleUpload = async (e) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    if (!selectedProject) {
      setError('Select a project first')
      return
    }

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('project_id', selectedProject)

        const res = await fetch(`${hypermatrixUrl}/api/context/upload`, {
          method: 'POST',
          body: formData
        })

        const data = await res.json()

        if (!res.ok) {
          throw new Error(data.detail || 'Upload failed')
        }

        setSuccess(`Uploaded: ${data.filename}`)
      }

      // Reload documents and projects
      await loadDocuments(selectedProject)
      await loadProjects()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  // Delete document
  const handleDelete = async (docId, filename) => {
    if (!confirm(`Delete "${filename}"?`)) return

    try {
      const res = await fetch(`${hypermatrixUrl}/api/context/${docId}?confirm=true`, {
        method: 'DELETE'
      })
      const data = await res.json()

      if (data.success) {
        setSuccess(`Deleted: ${filename}`)
        await loadDocuments(selectedProject)
        await loadProjects()
      } else {
        throw new Error(data.detail || 'Delete failed')
      }
    } catch (err) {
      setError(err.message)
    }
  }

  // Index document in ChromaDB
  const handleIndex = async (docId, filename) => {
    try {
      const res = await fetch(`${hypermatrixUrl}/api/context/${docId}/index`, {
        method: 'POST'
      })
      const data = await res.json()

      if (data.success) {
        setSuccess(`Indexed: ${filename} (${data.chunks_indexed} chunks)`)
        await loadDocuments(selectedProject)
      } else {
        setError(data.message || 'Indexing failed')
      }
    } catch (err) {
      setError(err.message)
    }
  }

  // Preview document content
  const handlePreview = async (doc) => {
    setPreviewDoc(doc)
    setPreviewContent(null)

    try {
      const res = await fetch(`${hypermatrixUrl}/api/context/document/${doc.id}/content`)
      const data = await res.json()
      setPreviewContent(data)
    } catch (err) {
      setPreviewContent({ error: err.message })
    }
  }

  const getFileIcon = (fileType) => {
    switch (fileType) {
      case '.md': return '📝'
      case '.txt': return '📄'
      case '.pdf': return '📕'
      case '.html': return '🌐'
      case '.json': return '📋'
      case '.yaml':
      case '.yml': return '⚙️'
      case '.zip': return '📦'
      default: return '📎'
    }
  }

  const selectedProjectData = projects.find(p => p.id === selectedProject)

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[var(--color-fg-primary)] flex items-center gap-2">
          📎 Documentos de Contexto
        </h1>
        <p className="text-[var(--color-fg-secondary)] mt-1">
          Sube specs, requirements, notas y vincúlalos a proyectos para búsqueda semántica
        </p>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 p-4 bg-[var(--color-error-bg)] border border-[var(--color-error)] rounded-lg text-[var(--color-error)]">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Cerrar</button>
        </div>
      )}
      {success && (
        <div className="mb-4 p-4 bg-[var(--color-success-bg)] border border-[var(--color-success)] rounded-lg text-[var(--color-success)]">
          {success}
          <button onClick={() => setSuccess(null)} className="ml-2 underline">Cerrar</button>
        </div>
      )}

      {/* Project selector and upload */}
      <div className="mb-6 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-[var(--color-fg-secondary)] mb-1">
            Proyecto
          </label>
          <select
            value={selectedProject || ''}
            onChange={(e) => setSelectedProject(Number(e.target.value))}
            className="w-full p-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-[var(--color-fg-primary)]"
          >
            <option value="">Selecciona un proyecto...</option>
            {projects.map(p => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.context_count} docs)
              </option>
            ))}
          </select>
        </div>

        <div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={SUPPORTED_TYPES.join(',')}
            onChange={handleUpload}
            disabled={!selectedProject || uploading}
            className="hidden"
            id="context-upload"
          />
          <label
            htmlFor="context-upload"
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg cursor-pointer transition-colors ${
              !selectedProject || uploading
                ? 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-tertiary)] cursor-not-allowed'
                : 'bg-[var(--color-primary)] text-white hover:opacity-90'
            }`}
          >
            {uploading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Subiendo...
              </>
            ) : (
              <>
                📤 Subir Documentos
              </>
            )}
          </label>
        </div>
      </div>

      {/* Supported types hint */}
      <div className="mb-4 text-xs text-[var(--color-fg-tertiary)]">
        Formatos soportados: {SUPPORTED_TYPES.join(', ')}
      </div>

      {/* Documents table */}
      {selectedProject && (
        <div className="bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)] overflow-hidden">
          <div className="p-4 border-b border-[var(--color-border)] flex justify-between items-center">
            <h2 className="font-medium text-[var(--color-fg-primary)]">
              Documentos de "{selectedProjectData?.name}"
            </h2>
            <span className="text-sm text-[var(--color-fg-tertiary)]">
              {documents.length} documentos
            </span>
          </div>

          {loading ? (
            <div className="p-8 text-center">
              <div className="animate-pulse flex items-center justify-center gap-2">
                <div className="w-6 h-6 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin"></div>
                <span>Cargando...</span>
              </div>
            </div>
          ) : documents.length === 0 ? (
            <div className="p-8 text-center text-[var(--color-fg-tertiary)]">
              No hay documentos. Sube archivos para empezar.
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-[var(--color-bg-tertiary)]">
                <tr>
                  <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Archivo</th>
                  <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Tipo</th>
                  <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Tamaño</th>
                  <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Fecha</th>
                  <th className="text-left p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Indexado</th>
                  <th className="text-right p-3 text-sm font-medium text-[var(--color-fg-secondary)]">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{getFileIcon(doc.file_type)}</span>
                        <span className="font-medium text-[var(--color-fg-primary)]">{doc.original_name}</span>
                      </div>
                      {doc.description && (
                        <div className="text-xs text-[var(--color-fg-tertiary)] mt-1">{doc.description}</div>
                      )}
                    </td>
                    <td className="p-3 text-sm text-[var(--color-fg-secondary)]">{doc.file_type}</td>
                    <td className="p-3 text-sm text-[var(--color-fg-secondary)]">{doc.size_human}</td>
                    <td className="p-3 text-sm text-[var(--color-fg-tertiary)]">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="p-3">
                      {doc.indexed ? (
                        <span className="text-[var(--color-success)]">✓ Sí</span>
                      ) : (
                        <span className="text-[var(--color-fg-tertiary)]">No</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <div className="flex gap-2 justify-end">
                        {['.txt', '.md', '.html', '.json', '.yaml', '.yml'].includes(doc.file_type) && (
                          <button
                            onClick={() => handlePreview(doc)}
                            className="px-2 py-1 text-xs bg-[var(--color-bg-tertiary)] text-[var(--color-fg-primary)] rounded hover:opacity-80"
                            title="Ver contenido"
                          >
                            👁️ Ver
                          </button>
                        )}
                        {!doc.indexed && ['.txt', '.md', '.html', '.json', '.yaml', '.yml'].includes(doc.file_type) && (
                          <button
                            onClick={() => handleIndex(doc.id, doc.original_name)}
                            className="px-2 py-1 text-xs bg-[var(--color-primary-bg)] text-[var(--color-primary)] rounded hover:opacity-80"
                            title="Indexar en ChromaDB"
                          >
                            🔍 Indexar
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(doc.id, doc.original_name)}
                          className="px-2 py-1 text-xs bg-[var(--color-error-bg)] text-[var(--color-error)] rounded hover:opacity-80"
                          title="Eliminar"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Preview modal */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] m-4 flex flex-col">
            <div className="p-4 border-b border-[var(--color-border)] flex justify-between items-center">
              <h3 className="font-bold text-[var(--color-fg-primary)] flex items-center gap-2">
                {getFileIcon(previewDoc.file_type)} {previewDoc.original_name}
              </h3>
              <button
                onClick={() => {
                  setPreviewDoc(null)
                  setPreviewContent(null)
                }}
                className="p-2 hover:bg-[var(--color-bg-secondary)] rounded"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {!previewContent ? (
                <div className="flex items-center justify-center h-32">
                  <div className="w-6 h-6 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : previewContent.error ? (
                <div className="text-[var(--color-error)]">{previewContent.error}</div>
              ) : previewContent.content ? (
                <pre className="whitespace-pre-wrap text-sm text-[var(--color-fg-secondary)] font-mono bg-[var(--color-bg-secondary)] p-4 rounded-lg overflow-auto">
                  {previewContent.content}
                </pre>
              ) : (
                <div className="text-[var(--color-fg-tertiary)]">{previewContent.message}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Info box */}
      <div className="mt-6 p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
        <h3 className="text-sm font-medium text-[var(--color-fg-primary)] mb-2">Cómo usar:</h3>
        <ul className="text-xs text-[var(--color-fg-secondary)] space-y-1">
          <li>1. Selecciona un proyecto existente</li>
          <li>2. Sube documentos de contexto (specs, requirements, notas)</li>
          <li>3. Haz clic en "Indexar" para añadirlos a la búsqueda semántica</li>
          <li>4. Los documentos indexados aparecerán en las búsquedas del AI</li>
        </ul>
      </div>
    </div>
  )
}
