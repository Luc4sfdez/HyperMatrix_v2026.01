import { useState, useCallback, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../components/Card'
import { Button } from '../components/Button'

// Pasos del wizard
const STEPS = [
  { id: 1, title: 'Seleccionar Archivos', icon: '📁' },
  { id: 2, title: 'Revisar Análisis', icon: '🔍' },
  { id: 3, title: 'Resolver Conflictos', icon: '⚡' },
  { id: 4, title: 'Preview y Ejecutar', icon: '✅' },
]

// Indicador de paso
function StepIndicator({ steps, currentStep }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {steps.map((step, idx) => (
        <div key={step.id} className="flex items-center">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
            currentStep === step.id
              ? 'bg-[var(--color-primary)] text-white'
              : currentStep > step.id
                ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
                : 'bg-[var(--color-bg-secondary)] text-[var(--color-fg-tertiary)]'
          }`}>
            <span>{step.icon}</span>
            <span className="hidden md:inline">{step.title}</span>
          </div>
          {idx < steps.length - 1 && (
            <div className={`w-8 h-0.5 mx-1 ${
              currentStep > step.id
                ? 'bg-[var(--color-success)]'
                : 'bg-[var(--color-border)]'
            }`} />
          )}
        </div>
      ))}
    </div>
  )
}

// Selector de grupos de hermanos detectados
function SiblingGroupSelector({ groups, loading, onSelect, selectedGroup }) {
  if (loading) {
    return (
      <div className="text-center py-4">
        <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--color-primary)]"></div>
        <p className="text-sm text-[var(--color-fg-secondary)] mt-2">Cargando grupos detectados...</p>
      </div>
    )
  }

  if (!groups || groups.length === 0) {
    return (
      <p className="text-sm text-[var(--color-fg-tertiary)] text-center py-4">
        No hay grupos de hermanos detectados. Ejecuta un escaneo primero.
      </p>
    )
  }

  return (
    <div className="space-y-2 max-h-64 overflow-y-auto">
      {groups.map((group, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(group)}
          className={`w-full text-left p-3 rounded-lg border transition-all ${
            selectedGroup?.filename === group.filename
              ? 'border-[var(--color-primary)] bg-[var(--color-primary)] bg-opacity-10'
              : 'border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-secondary)]'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-lg">📄</span>
              <div>
                <span className="font-medium text-[var(--color-fg-primary)]">{group.filename}</span>
                <span className="text-xs text-[var(--color-fg-tertiary)] ml-2">
                  ({group.file_count} versiones)
                </span>
              </div>
            </div>
            {group.average_affinity >= 0.8 && (
              <span className="px-2 py-0.5 bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)] text-xs rounded">
                Alta similitud
              </span>
            )}
          </div>
          {group.proposed_master && (
            <p className="text-xs text-[var(--color-fg-tertiary)] mt-1 truncate">
              Maestro: {group.proposed_master.split('/').pop()}
            </p>
          )}
        </button>
      ))}
    </div>
  )
}

// Lista de archivos editable
function FileList({ files, onRemove, onAdd }) {
  const [newFile, setNewFile] = useState('')

  const handleAdd = () => {
    if (newFile.trim() && !files.includes(newFile.trim())) {
      onAdd(newFile.trim())
      setNewFile('')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          value={newFile}
          onChange={(e) => setNewFile(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Ruta del archivo Python..."
          className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
        />
        <Button variant="secondary" onClick={handleAdd}>
          + Añadir
        </Button>
      </div>
      {files.length > 0 ? (
        <ul className="space-y-2">
          {files.map((file, idx) => (
            <li
              key={idx}
              className="flex items-center justify-between p-3 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]"
            >
              <code className="text-sm text-[var(--color-fg-primary)] truncate">{file}</code>
              <button
                onClick={() => onRemove(file)}
                className="ml-2 p-1 text-[var(--color-fg-tertiary)] hover:text-[var(--color-error)]"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-center text-[var(--color-fg-tertiary)] py-4">
          Añade al menos 2 archivos Python para fusionar
        </p>
      )}
    </div>
  )
}

// Selector de resolución de conflicto
function ConflictResolver({ conflict, resolution, onResolve }) {
  return (
    <div className="p-4 border border-[var(--color-warning)] border-opacity-50 rounded-lg bg-[var(--color-warning)] bg-opacity-5">
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="text-sm font-medium text-[var(--color-fg-primary)]">
            {conflict.type}: <code className="font-mono">{conflict.name}</code>
          </span>
          <p className="text-xs text-[var(--color-fg-secondary)] mt-1">
            {conflict.versions.length} versiones diferentes
          </p>
        </div>
        <span className="px-2 py-0.5 bg-[var(--color-warning)] text-[var(--color-warning-text)] text-xs rounded font-medium">
          Conflicto
        </span>
      </div>

      {conflict.differences && (
        <ul className="text-xs text-[var(--color-fg-tertiary)] mb-3 space-y-1">
          {conflict.differences.slice(0, 3).map((diff, i) => (
            <li key={i}>• {diff}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-2">
        {conflict.versions.map((version, idx) => (
          <button
            key={idx}
            onClick={() => onResolve(conflict.name, version)}
            className={`px-3 py-1.5 text-xs rounded border transition-all ${
              resolution === version
                ? 'bg-[var(--color-primary)] text-white border-[var(--color-primary)]'
                : 'bg-[var(--color-bg-primary)] text-[var(--color-fg-secondary)] border-[var(--color-border)] hover:border-[var(--color-primary)]'
            }`}
          >
            Usar versión de {version.split('/').pop()}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function MergeWizard({ hypermatrixUrl, navContext }) {
  const [step, setStep] = useState(1)
  const [files, setFiles] = useState([])
  const [baseFile, setBaseFile] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)
  const [resolutions, setResolutions] = useState({})
  const [outputPath, setOutputPath] = useState('')
  const [executing, setExecuting] = useState(false)
  const [result, setResult] = useState(null)

  // Sibling groups state
  const [siblingGroups, setSiblingGroups] = useState([])
  const [loadingSiblings, setLoadingSiblings] = useState(true)
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [currentScanId, setCurrentScanId] = useState(null)

  // AI-assisted merge state
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [loadingAI, setLoadingAI] = useState(false)
  const [aiError, setAiError] = useState(null)

  // Load sibling groups on mount
  useEffect(() => {
    const loadSiblingGroups = async () => {
      setLoadingSiblings(true)
      try {
        // First get the latest scan
        const scanRes = await fetch(`${hypermatrixUrl}/api/scan/list`)
        const scanData = await scanRes.json()
        const completedScan = scanData.scans?.find(s => s.status === 'completed')

        if (completedScan) {
          setCurrentScanId(completedScan.scan_id)

          // Load sibling groups (only those with 2+ files, sorted by file count)
          const siblingsRes = await fetch(
            `${hypermatrixUrl}/api/consolidation/siblings/${completedScan.scan_id}?limit=50&sort_by=files`
          )
          if (siblingsRes.ok) {
            const siblingsData = await siblingsRes.json()
            // Filter to only show groups with 2+ files
            const validGroups = (siblingsData.groups || []).filter(g => g.file_count >= 2)
            setSiblingGroups(validGroups)
          }
        }
      } catch (err) {
        console.error('Error loading sibling groups:', err)
      } finally {
        setLoadingSiblings(false)
      }
    }

    loadSiblingGroups()

    // If coming from Results page with pre-selected files
    if (navContext?.files) {
      setFiles(navContext.files)
      if (navContext.masterProposal) {
        setBaseFile(navContext.masterProposal)
      }
    }
  }, [hypermatrixUrl, navContext])

  // Select a sibling group
  const selectSiblingGroup = (group) => {
    setSelectedGroup(group)
    const filePaths = group.files?.map(f => f.filepath) || []
    setFiles(filePaths)
    if (group.proposed_master) {
      setBaseFile(group.proposed_master)
    }
  }

  // Añadir archivo
  const addFile = (file) => {
    setFiles([...files, file])
  }

  // Eliminar archivo
  const removeFile = (file) => {
    setFiles(files.filter((f) => f !== file))
    if (baseFile === file) setBaseFile('')
  }

  // Generar preview
  const generatePreview = useCallback(async () => {
    if (files.length < 2) {
      setError('Necesitas al menos 2 archivos')
      return
    }

    setLoading(true)
    setError(null)
    setAiAnalysis(null)
    setAiError(null)

    try {
      const params = new URLSearchParams()
      files.forEach((f) => params.append('files', f))
      if (baseFile) params.append('base_file', baseFile)

      const response = await fetch(`${hypermatrixUrl}/api/consolidation/merge/preview?${params}`, {
        method: 'POST',
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setPreview(data)
      setBaseFile(data.base_file)
      setStep(2)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl, files, baseFile])

  // Resolver conflicto
  const resolveConflict = (name, version) => {
    setResolutions({ ...resolutions, [name]: version })
  }

  // Solicitar análisis de IA
  const requestAIAnalysis = useCallback(async () => {
    if (files.length < 2 || !preview) return

    setLoadingAI(true)
    setAiError(null)
    setAiAnalysis(null)

    try {
      // Build a summary of the merge preview for AI analysis
      const summaryData = {
        base_file: preview.base_file,
        files_count: files.length,
        common_functions: preview.common_functions?.length || 0,
        common_classes: preview.common_classes?.length || 0,
        unique_functions: Object.keys(preview.unique_functions || {}).length,
        unique_classes: Object.keys(preview.unique_classes || {}).length,
        conflicts: preview.conflicts?.length || 0,
        conflict_details: preview.conflicts?.slice(0, 5).map(c => ({
          name: c.name,
          type: c.type,
          versions: c.versions?.length || 0
        }))
      }

      // Use AI chat with a summary (not full file contents) to avoid timeout
      const response = await fetch(`${hypermatrixUrl}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `Analiza este merge de ${files.length} archivos main.py y dame recomendaciones:
- Archivo base: ${preview.base_file?.split('/').pop()}
- Funciones comunes: ${summaryData.common_functions}
- Clases comunes: ${summaryData.common_classes}
- Funciones únicas a agregar: ${summaryData.unique_functions}
- Clases únicas a agregar: ${summaryData.unique_classes}
- Conflictos detectados: ${summaryData.conflicts}
${summaryData.conflict_details?.length > 0 ? `Conflictos: ${summaryData.conflict_details.map(c => c.name).join(', ')}` : ''}

¿Qué recomiendas para este merge? ¿Hay riesgos o consideraciones especiales?`,
          scan_id: currentScanId
        })
      })

      if (!response.ok) {
        throw new Error(`Error ${response.status}`)
      }

      const data = await response.json()
      setAiAnalysis({
        response: data.response,
        summary: summaryData
      })
    } catch (err) {
      setAiError(err.message)
    } finally {
      setLoadingAI(false)
    }
  }, [hypermatrixUrl, files, currentScanId, preview])

  // Ejecutar merge
  const executeMerge = useCallback(async () => {
    if (!outputPath.trim()) {
      setError('Especifica la ruta de salida')
      return
    }

    setExecuting(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      files.forEach((f) => params.append('files', f))
      params.append('output_path', outputPath)
      if (baseFile) params.append('base_file', baseFile)
      params.append('conflict_resolution', 'keep_largest')

      const response = await fetch(`${hypermatrixUrl}/api/consolidation/merge/execute?${params}`, {
        method: 'POST',
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setExecuting(false)
    }
  }, [hypermatrixUrl, files, baseFile, outputPath])

  // Navegación
  const canProceed = () => {
    switch (step) {
      case 1: return files.length >= 2
      case 2: return preview !== null
      case 3: return preview?.conflicts?.length === 0 || Object.keys(resolutions).length === preview?.conflicts?.length
      case 4: return outputPath.trim().length > 0
      default: return false
    }
  }

  const nextStep = () => {
    if (step === 1) {
      generatePreview()
    } else if (step < 4) {
      setStep(step + 1)
    }
  }

  const prevStep = () => {
    if (step > 1) setStep(step - 1)
  }

  // Resultado exitoso
  if (result) {
    return (
      <div className="space-y-6 p-6">
        <Card>
          <CardContent className="text-center py-12">
            <div className="text-6xl mb-4">✅</div>
            <h2 className="text-2xl font-bold text-[var(--color-success)] mb-2">
              ¡Merge Completado!
            </h2>
            <p className="text-[var(--color-fg-secondary)] mb-4">
              El archivo fusionado se ha creado correctamente
            </p>
            <code className="block p-3 bg-[var(--color-bg-secondary)] rounded-lg text-sm">
              {result.output_file || outputPath}
            </code>
            <div className="mt-6">
              <Button variant="primary" onClick={() => {
                setStep(1)
                setFiles([])
                setPreview(null)
                setResult(null)
                setOutputPath('')
                setResolutions({})
              }}>
                Nuevo Merge
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
          🔗 Asistente de Merge
        </h2>
        <p className="text-[var(--color-fg-secondary)]">
          Fusiona múltiples versiones de un archivo Python de forma inteligente
        </p>
      </div>

      <StepIndicator steps={STEPS} currentStep={step} />

      {error && (
        <div className="p-3 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] rounded-lg text-[var(--color-error)]">
          {error}
        </div>
      )}

      {/* Paso 1: Seleccionar archivos */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>📁 Selecciona los archivos a fusionar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Grupos de hermanos detectados */}
            <div>
              <h4 className="text-sm font-medium text-[var(--color-fg-primary)] mb-3 flex items-center gap-2">
                <span>🔍</span> Grupos de hermanos detectados
                {siblingGroups.length > 0 && (
                  <span className="text-xs px-2 py-0.5 bg-[var(--color-primary)] bg-opacity-20 text-[var(--color-primary)] rounded-full">
                    {siblingGroups.length} disponibles
                  </span>
                )}
              </h4>
              <SiblingGroupSelector
                groups={siblingGroups}
                loading={loadingSiblings}
                onSelect={selectSiblingGroup}
                selectedGroup={selectedGroup}
              />
            </div>

            {/* Separador */}
            <div className="flex items-center gap-4">
              <div className="flex-1 h-px bg-[var(--color-border)]"></div>
              <span className="text-xs text-[var(--color-fg-tertiary)]">o añade manualmente</span>
              <div className="flex-1 h-px bg-[var(--color-border)]"></div>
            </div>

            {/* Lista manual */}
            <FileList files={files} onAdd={addFile} onRemove={removeFile} />

            {files.length >= 2 && (
              <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
                <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                  Archivo base (opcional)
                </label>
                <select
                  value={baseFile}
                  onChange={(e) => setBaseFile(e.target.value)}
                  className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)]"
                >
                  <option value="">Auto-seleccionar</option>
                  {files.map((f, i) => (
                    <option key={i} value={f}>{f.split('/').pop()}</option>
                  ))}
                </select>
                <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
                  El archivo base será el punto de partida. Si no lo especificas, HyperMatrix elegirá el más completo.
                </p>
              </div>
            )}
          </CardContent>
          <CardFooter className="justify-end">
            <Button
              variant="primary"
              onClick={nextStep}
              disabled={!canProceed() || loading}
            >
              {loading ? '⏳ Analizando...' : 'Siguiente →'}
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Paso 2: Revisar análisis */}
      {step === 2 && preview && (
        <Card>
          <CardHeader>
            <CardTitle>🔍 Análisis de Versiones</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3 bg-[var(--color-success)] bg-opacity-10 border border-[var(--color-success)] rounded-lg">
              <strong className="text-[var(--color-success)]">Archivo base:</strong>
              <code className="ml-2">{preview.base_file}</code>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-2xl font-bold text-[var(--color-primary)]">
                  {preview.common_functions?.length || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Funciones comunes</div>
              </div>
              <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-2xl font-bold text-[var(--color-primary)]">
                  {preview.common_classes?.length || 0}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Clases comunes</div>
              </div>
            </div>

            {/* Elementos únicos */}
            {(Object.keys(preview.unique_functions || {}).length > 0 || Object.keys(preview.unique_classes || {}).length > 0) && (
              <div>
                <h4 className="font-medium text-[var(--color-fg-primary)] mb-2">
                  Elementos únicos que se agregarán:
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {Object.entries(preview.unique_functions || {}).map(([name, source]) => (
                    <div key={name} className="flex items-center gap-2 text-sm">
                      <span className="text-[var(--color-primary)]">⚡</span>
                      <code>{name}</code>
                      <span className="text-[var(--color-fg-tertiary)]">de {source}</span>
                    </div>
                  ))}
                  {Object.entries(preview.unique_classes || {}).map(([name, source]) => (
                    <div key={name} className="flex items-center gap-2 text-sm">
                      <span className="text-[var(--color-warning)]">📦</span>
                      <code>{name}</code>
                      <span className="text-[var(--color-fg-tertiary)]">de {source}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Conflictos */}
            {preview.conflicts?.length > 0 && (
              <div className="p-3 bg-[var(--color-warning)] bg-opacity-10 border border-[var(--color-warning)] rounded-lg">
                <strong className="text-[var(--color-warning)]">
                  ⚠️ {preview.conflicts.length} conflicto(s) detectado(s)
                </strong>
                <p className="text-sm text-[var(--color-fg-secondary)] mt-1">
                  Necesitarás resolverlos en el siguiente paso
                </p>
              </div>
            )}

            {/* AI Analysis Section */}
            <div className="border-t border-[var(--color-border)] pt-4 mt-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-[var(--color-fg-primary)] flex items-center gap-2">
                  <span>🤖</span> Análisis con IA
                </h4>
                <Button
                  variant="secondary"
                  onClick={requestAIAnalysis}
                  disabled={loadingAI || files.length < 2}
                >
                  {loadingAI ? '⏳ Analizando...' : '🔍 Pedir Sugerencias'}
                </Button>
              </div>

              {aiError && (
                <div className="p-3 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] rounded-lg text-sm text-[var(--color-error)]">
                  {aiError}
                </div>
              )}

              {aiAnalysis && (
                <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                  <div className="text-xs text-[var(--color-fg-tertiary)] mb-2 flex items-center gap-2">
                    <span className="text-green-500">✓</span> Análisis completado
                  </div>
                  <div className="prose prose-sm max-w-none text-[var(--color-fg-primary)]">
                    <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                      {aiAnalysis.response}
                    </pre>
                  </div>
                </div>
              )}

              {!aiAnalysis && !loadingAI && !aiError && (
                <p className="text-sm text-[var(--color-fg-tertiary)] text-center py-2">
                  La IA puede analizar las diferencias y sugerir cómo hacer el merge
                </p>
              )}
            </div>
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="ghost" onClick={prevStep}>← Anterior</Button>
            <Button variant="primary" onClick={nextStep}>Siguiente →</Button>
          </CardFooter>
        </Card>
      )}

      {/* Paso 3: Resolver conflictos */}
      {step === 3 && preview && (
        <Card>
          <CardHeader>
            <CardTitle>⚡ Resolver Conflictos</CardTitle>
          </CardHeader>
          <CardContent>
            {preview.conflicts?.length > 0 ? (
              <div className="space-y-4">
                {preview.conflicts.map((conflict, idx) => (
                  <ConflictResolver
                    key={idx}
                    conflict={conflict}
                    resolution={resolutions[conflict.name]}
                    onResolve={resolveConflict}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-4xl mb-2">✅</div>
                <p className="text-[var(--color-success)] font-medium">No hay conflictos</p>
                <p className="text-[var(--color-fg-secondary)] text-sm">
                  Los archivos se pueden fusionar automáticamente
                </p>
              </div>
            )}
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="ghost" onClick={prevStep}>← Anterior</Button>
            <Button
              variant="primary"
              onClick={nextStep}
              disabled={!canProceed()}
            >
              Siguiente →
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Paso 4: Preview y ejecutar */}
      {step === 4 && preview && (
        <Card>
          <CardHeader>
            <CardTitle>✅ Preview y Ejecutar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                <div className="text-lg font-bold text-[var(--color-fg-primary)]">
                  {preview.stats?.total_functions || 0}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Funciones</div>
              </div>
              <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                <div className="text-lg font-bold text-[var(--color-fg-primary)]">
                  {preview.stats?.total_classes || 0}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Clases</div>
              </div>
              <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                <div className="text-lg font-bold text-[var(--color-fg-primary)]">
                  {preview.preview_lines || 0}
                </div>
                <div className="text-xs text-[var(--color-fg-secondary)]">Líneas</div>
              </div>
            </div>

            {/* Preview de código */}
            {preview.preview_code && (
              <div>
                <h4 className="font-medium text-[var(--color-fg-primary)] mb-2">
                  Preview del código fusionado:
                  {preview.truncated && <span className="text-xs text-[var(--color-fg-tertiary)] ml-2">(truncado)</span>}
                </h4>
                <pre className="max-h-64 overflow-auto p-4 bg-[var(--color-bg-secondary)] rounded-lg text-xs font-mono">
                  {preview.preview_code}
                </pre>
              </div>
            )}

            {/* Output path */}
            <div>
              <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
                Ruta del archivo de salida
              </label>
              <input
                type="text"
                value={outputPath}
                onChange={(e) => setOutputPath(e.target.value)}
                placeholder="ej: C:/proyecto/merged_utils.py"
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="ghost" onClick={prevStep}>← Anterior</Button>
            <Button
              variant="primary"
              onClick={executeMerge}
              disabled={!outputPath.trim() || executing}
            >
              {executing ? '⏳ Ejecutando...' : '🚀 Ejecutar Merge'}
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  )
}
