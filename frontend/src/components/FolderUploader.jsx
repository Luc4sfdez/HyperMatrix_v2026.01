import { useState, useRef } from 'react'

/**
 * Uploader de carpetas al workspace del contenedor
 * Funciona como Dropbox/GDrive - seleccionas carpeta local, se sube al servidor
 */
export default function FolderUploader({ hypermatrixUrl, onUploadComplete, onClose }) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0, currentFile: '' })
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)

  const handleFolderSelect = async (e) => {
    const files = Array.from(e.target.files)
    if (files.length === 0) return

    setUploading(true)
    setError(null)
    setProgress({ current: 0, total: files.length, currentFile: '' })

    // Get folder name from first file path
    const firstPath = files[0].webkitRelativePath
    const folderName = firstPath.split('/')[0]

    try {
      // Create folder in workspace
      const formData = new FormData()
      formData.append('name', folderName)
      const createRes = await fetch(`${hypermatrixUrl}/api/workspace/create-folder`, {
        method: 'POST',
        body: formData
      })

      if (!createRes.ok) {
        let errMsg = 'Error creating folder'
        try {
          const err = await createRes.json()
          errMsg = err.detail || errMsg
        } catch (e) {}
        throw new Error(errMsg)
      }

      const { path: basePath } = await createRes.json()

      // Upload files one by one
      let uploaded = 0
      for (const file of files) {
        const relativePath = file.webkitRelativePath
        setProgress({ current: uploaded, total: files.length, currentFile: relativePath })

        const formData = new FormData()
        formData.append('file', file)
        formData.append('path', relativePath)

        const uploadRes = await fetch(`${hypermatrixUrl}/api/workspace/upload-file`, {
          method: 'POST',
          body: formData
        })

        if (!uploadRes.ok) {
          console.warn(`Failed to upload ${relativePath}`)
        }

        uploaded++
        setProgress({ current: uploaded, total: files.length, currentFile: relativePath })
      }

      setResult({
        success: true,
        folderName,
        path: basePath,
        filesUploaded: uploaded
      })

      if (onUploadComplete) {
        onUploadComplete({ folderName, path: basePath, filesUploaded: uploaded })
      }

    } catch (err) {
      setError(typeof err === 'string' ? err : (err.message || 'Error desconocido'))
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setError(null)
    setProgress({ current: 0, total: 0, currentFile: '' })
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-[var(--color-fg-primary)]">
            Subir Carpeta al Workspace
          </h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[var(--color-bg-secondary)] rounded text-[var(--color-fg-secondary)]"
          >
            ✕
          </button>
        </div>

        {!uploading && !result && (
          <div className="text-center py-8">
            <div className="mb-4">
              <span className="text-5xl">📁</span>
            </div>
            <p className="text-[var(--color-fg-secondary)] mb-4">
              Selecciona una carpeta de tu ordenador para subirla al workspace
            </p>
            <input
              ref={inputRef}
              type="file"
              webkitdirectory=""
              directory=""
              multiple
              onChange={handleFolderSelect}
              className="hidden"
              id="folder-input"
            />
            <label
              htmlFor="folder-input"
              className="inline-block px-6 py-3 bg-[var(--color-primary)] text-white rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
            >
              Seleccionar Carpeta
            </label>
            <p className="text-xs text-[var(--color-fg-tertiary)] mt-4">
              La carpeta se copiará al workspace del contenedor (límite 20GB)
            </p>
          </div>
        )}

        {uploading && (
          <div className="py-8">
            <div className="flex items-center justify-center mb-4">
              <div className="animate-spin w-10 h-10 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
            </div>
            <p className="text-center text-[var(--color-fg-primary)] font-medium mb-2">
              Subiendo archivos...
            </p>
            <div className="w-full bg-[var(--color-bg-tertiary)] rounded-full h-2 mb-2">
              <div
                className="bg-[var(--color-primary)] h-2 rounded-full transition-all"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              ></div>
            </div>
            <p className="text-center text-sm text-[var(--color-fg-tertiary)]">
              {progress.current} / {progress.total} archivos
            </p>
            <p className="text-center text-xs text-[var(--color-fg-tertiary)] truncate mt-1">
              {progress.currentFile}
            </p>
          </div>
        )}

        {error && (
          <div className="py-4">
            <div className="text-center text-[var(--color-error)] mb-4">
              <span className="text-3xl">⚠️</span>
              <p className="mt-2">{error}</p>
            </div>
            <button
              onClick={reset}
              className="w-full px-4 py-2 bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] rounded hover:bg-[var(--color-bg-tertiary)]"
            >
              Intentar de nuevo
            </button>
          </div>
        )}

        {result && (
          <div className="py-4">
            <div className="text-center text-[var(--color-success)] mb-4">
              <span className="text-5xl">✅</span>
              <p className="mt-2 font-medium">¡Carpeta subida!</p>
            </div>
            <div className="bg-[var(--color-bg-secondary)] rounded-lg p-4 mb-4">
              <p className="text-sm">
                <span className="text-[var(--color-fg-tertiary)]">Carpeta:</span>{' '}
                <span className="font-mono text-[var(--color-fg-primary)]">{result.folderName}</span>
              </p>
              <p className="text-sm">
                <span className="text-[var(--color-fg-tertiary)]">Archivos:</span>{' '}
                <span className="text-[var(--color-fg-primary)]">{result.filesUploaded}</span>
              </p>
              <p className="text-sm">
                <span className="text-[var(--color-fg-tertiary)]">Ubicación:</span>{' '}
                <span className="font-mono text-[var(--color-fg-primary)]">{result.path}</span>
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={reset}
                className="flex-1 px-4 py-2 bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] rounded hover:bg-[var(--color-bg-tertiary)]"
              >
                Subir otra
              </button>
              <button
                onClick={onClose}
                className="flex-1 px-4 py-2 bg-[var(--color-primary)] text-white rounded hover:opacity-90"
              >
                Cerrar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
