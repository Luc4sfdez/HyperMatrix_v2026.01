import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Formatos de export disponibles
const EXPORT_FORMATS = [
  { id: 'json', label: 'JSON', icon: '📋', description: 'Datos completos en formato JSON' },
  { id: 'csv', label: 'CSV', icon: '📊', description: 'Tabla para Excel/Sheets' },
  { id: 'markdown', label: 'Markdown', icon: '📝', description: 'Reporte legible' },
]

// Componente de botones de export
function ExportButtons({ hypermatrixUrl, scanId, onPreview }) {
  const [exporting, setExporting] = useState(null)
  const [showPreview, setShowPreview] = useState(false)
  const [previewContent, setPreviewContent] = useState(null)
  const [previewFormat, setPreviewFormat] = useState(null)

  const handleExport = async (format) => {
    setExporting(format)
    try {
      // Abrir en nueva ventana para descargar
      window.open(`${hypermatrixUrl}/api/export/${scanId}?format=${format}`, '_blank')
    } finally {
      setExporting(null)
    }
  }

  const handlePreview = async (format) => {
    setExporting(format)
    try {
      const response = await fetch(`${hypermatrixUrl}/api/export/${scanId}?format=${format}`)
      if (response.ok) {
        const text = await response.text()
        setPreviewContent(text)
        setPreviewFormat(format)
        setShowPreview(true)
      }
    } catch (err) {
      console.error('Error preview:', err)
    } finally {
      setExporting(null)
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-[var(--color-fg-secondary)]">Exportar:</span>
        {EXPORT_FORMATS.map((format) => (
          <div key={format.id} className="relative group">
            <button
              onClick={() => handleExport(format.id)}
              disabled={exporting === format.id}
              className="px-3 py-1.5 text-sm bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-md hover:bg-[var(--color-bg-tertiary)] hover:border-[var(--color-primary)] transition-all disabled:opacity-50"
              title={format.description}
            >
              {exporting === format.id ? '⏳' : format.icon} {format.label}
            </button>
            {/* Botón preview pequeño */}
            <button
              onClick={() => handlePreview(format.id)}
              className="absolute -right-1 -top-1 w-5 h-5 text-xs bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-full opacity-0 group-hover:opacity-100 hover:bg-[var(--color-primary)] hover:text-white transition-all"
              title="Vista previa"
            >
              👁
            </button>
          </div>
        ))}
      </div>

      {/* Modal de preview */}
      {showPreview && previewContent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowPreview(false)}>
          <div
            className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
              <h3 className="font-semibold text-[var(--color-fg-primary)]">
                Vista previa - {previewFormat?.toUpperCase()}
              </h3>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(previewContent)
                  }}
                >
                  📋 Copiar
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleExport(previewFormat)}
                >
                  ⬇️ Descargar
                </Button>
                <button
                  onClick={() => setShowPreview(false)}
                  className="p-1 hover:bg-[var(--color-bg-secondary)] rounded"
                >
                  ✕
                </button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto p-4 text-xs font-mono bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)]">
              {previewFormat === 'json'
                ? JSON.stringify(JSON.parse(previewContent), null, 2)
                : previewContent}
            </pre>
          </div>
        </div>
      )}
    </>
  )
}

export default function ScanResults({ hypermatrixUrl, onNavigate }) {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [selectedScan, setSelectedScan] = useState(null)
  const [selectedScanId, setSelectedScanId] = useState(null)
  const [results, setResults] = useState(null)

  useEffect(() => {
    loadScans()
  }, [])

  const loadScans = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
      const data = await response.json()
      setScans(data.scans || [])
    } catch (error) {
      console.error('Error cargando scans:', error)
    } finally {
      setLoading(false)
    }
  }

  const viewResults = async (scanId) => {
    setLoadingDetails(true)
    try {
      // Cargar resumen (rapido) y grupos paginados - NO cargar el resultado completo (320MB+)
      const [summaryRes, siblingsRes] = await Promise.all([
        fetch(`${hypermatrixUrl}/api/scan/result/${scanId}/summary`),
        fetch(`${hypermatrixUrl}/api/consolidation/siblings/${scanId}?limit=50&sort_by=files`)
      ])
      const summary = await summaryRes.json()
      const siblingsData = await siblingsRes.json()

      // Convertir grupos al formato esperado
      const siblingDetails = {}
      if (siblingsData.groups) {
        siblingsData.groups.forEach(group => {
          siblingDetails[group.filename] = {
            files: group.files || [],
            master_proposal: {
              proposed_master: { filepath: group.proposed_master },
              confidence: group.master_confidence,
              reasons: group.reasons
            }
          }
        })
      }

      setSelectedScan(scanId)
      setSelectedScanId(scanId)
      setResults({
        ...summary,
        sibling_details: siblingDetails,
      })
    } catch (error) {
      alert(`Error: ${error.message}`)
    } finally {
      setLoadingDetails(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">📈 Resultados de Análisis</h2>
        <p className="text-[var(--color-fg-secondary)]">Visualiza todos los análisis completados</p>
      </div>

      {!selectedScan ? (
        <>
          {/* Lista de Scans */}
          <Card>
            <CardHeader>
              <CardTitle>Análisis Disponibles</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-[var(--color-fg-secondary)] text-center py-8">Cargando...</p>
              ) : loadingDetails ? (
                <div className="text-center py-12">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary)] mb-4"></div>
                  <p className="text-[var(--color-fg-secondary)]">Cargando detalles del analisis...</p>
                </div>
              ) : scans.length === 0 ? (
                <p className="text-[var(--color-fg-secondary)] text-center py-8">
                  No hay análisis disponibles. ¡Crea uno en el Dashboard!
                </p>
              ) : (
                <div className="space-y-3">
                  {scans.map((scan) => (
                    <button
                      key={scan.scan_id}
                      onClick={() => viewResults(scan.scan_id)}
                      disabled={loadingDetails}
                      className="w-full text-left p-4 rounded-lg border border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-secondary)] transition-all group disabled:opacity-50 disabled:cursor-wait"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-[var(--color-fg-primary)] truncate">
                            {scan.project || `Scan ${scan.scan_id}`}
                          </h3>
                          <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
                            ID: {scan.scan_id}
                          </p>
                          {/* Stats */}
                          <div className="flex flex-wrap gap-3 mt-2 text-xs">
                            <span className="text-[var(--color-fg-secondary)]">
                              📁 {scan.files || 0} archivos
                            </span>
                            {scan.analyzed > 0 && (
                              <span className="text-[var(--color-success)]">
                                ✓ {scan.analyzed} analizados
                              </span>
                            )}
                            {scan.duplicates > 0 && (
                              <span className="text-[var(--color-error)]">
                                🔴 {scan.duplicates} duplicados
                              </span>
                            )}
                            {scan.siblings > 0 && (
                              <span className="text-[var(--color-warning)]">
                                🟡 {scan.siblings} hermanos
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className={`px-2 py-0.5 text-xs rounded-full ${
                            scan.status === 'completed'
                              ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
                              : 'bg-[var(--color-warning)] bg-opacity-20 text-[var(--color-warning)]'
                          }`}>
                            {scan.status === 'completed' ? '✓ Completado' : scan.phase}
                          </span>
                          <span className="text-[var(--color-primary)] opacity-0 group-hover:opacity-100 transition-opacity">
                            Ver detalles →
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : (
        <>
          {/* Detalle de Scan */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <button
              onClick={() => {
                setSelectedScan(null)
                setSelectedScanId(null)
                setResults(null)
              }}
              className="text-[var(--color-primary)] hover:text-[var(--color-primary-hover)] font-medium text-sm"
            >
              ← Volver a lista
            </button>

            {/* Botones de Export */}
            <ExportButtons hypermatrixUrl={hypermatrixUrl} scanId={selectedScan} />
          </div>

          {results && (
            <div className="space-y-4">
              {/* Métricas principales */}
              <div className="metric-grid">
                <div className="metric-card">
                  <div className="metric-label">Archivos Totales</div>
                  <div className="metric-value">{results.total_files || 0}</div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Archivos Analizados</div>
                  <div className="metric-value">{results.analyzed_files || 0}</div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Grupos Duplicados</div>
                  <div className="metric-value text-[#E74C3C]">
                    {results.duplicate_groups || 0}
                  </div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Grupos Hermanos</div>
                  <div className="metric-value text-[#F39C12]">
                    {Array.isArray(results.sibling_groups) ? results.sibling_groups.length : (results.sibling_groups || 0)}
                  </div>
                </div>
              </div>

              {/* Resumen de Análisis */}
              <Card>
                <CardHeader>
                  <CardTitle>Resumen del Analisis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                      <div className="text-2xl font-bold text-[var(--color-primary)]">
                        {results.analysis_summary?.total_functions || 0}
                      </div>
                      <div className="text-xs text-[var(--color-fg-secondary)]">Funciones</div>
                    </div>
                    <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                      <div className="text-2xl font-bold text-[var(--color-primary)]">
                        {results.analysis_summary?.total_classes || 0}
                      </div>
                      <div className="text-xs text-[var(--color-fg-secondary)]">Clases</div>
                    </div>
                    <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                      <div className="text-2xl font-bold text-[var(--color-success)]">
                        {results.analysis_summary?.analyzed_files || 0}
                      </div>
                      <div className="text-xs text-[var(--color-fg-secondary)]">Analizados OK</div>
                    </div>
                    <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg text-center">
                      <div className="text-2xl font-bold text-[var(--color-error)]">
                        {results.analysis_summary?.failed_files || 0}
                      </div>
                      <div className="text-xs text-[var(--color-fg-secondary)]">Con Errores</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Errores de Sintaxis */}
              {results.analysis_summary?.errors && results.analysis_summary.errors.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Archivos con Errores de Sintaxis ({results.analysis_summary.errors.length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {results.analysis_summary.errors.map((error, idx) => (
                        <div
                          key={idx}
                          className="p-2 bg-[#FFEBEE] border-l-4 border-[#E74C3C] rounded text-xs font-mono text-[#C62828] break-all"
                        >
                          {error}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Grupos de Hermanos con Detalle */}
              {results.sibling_details && Object.keys(results.sibling_details).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Grupos de Hermanos ({Object.keys(results.sibling_details).length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3 max-h-96 overflow-y-auto">
                      {Object.entries(results.sibling_details).slice(0, 20).map(([filename, group]) => (
                        <div
                          key={filename}
                          className="p-4 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="font-semibold text-[var(--color-fg-primary)]">
                              {filename}
                            </h4>
                            <span className="text-xs px-2 py-1 bg-[var(--color-warning)] text-white rounded">
                              {group.files?.length || 0} versiones
                            </span>
                          </div>

                          {/* Archivo Maestro Propuesto */}
                          {group.master_proposal && (
                            <div className="mb-2 p-2 bg-[#E8F5E9] border-l-4 border-[var(--color-success)] rounded text-xs">
                              <strong className="text-[var(--color-success)]">Maestro propuesto:</strong>
                              <code className="ml-2 text-[var(--color-fg-secondary)] break-all">
                                {group.master_proposal.proposed_master?.filepath || 'N/A'}
                              </code>
                              {group.master_proposal.reasons && (
                                <p className="mt-1 text-[var(--color-fg-tertiary)]">
                                  {group.master_proposal.reasons.join(', ')}
                                </p>
                              )}
                            </div>
                          )}

                          {/* Lista de archivos */}
                          <div className="space-y-1">
                            {group.files?.slice(0, 5).map((file, idx) => (
                              <div
                                key={idx}
                                className={`text-xs p-1 rounded flex items-center gap-2 ${
                                  file.filepath === group.master_proposal?.proposed_master?.filepath
                                    ? 'bg-[#C8E6C9] text-[#2E7D32]'
                                    : 'text-[var(--color-fg-tertiary)]'
                                }`}
                              >
                                <span>{file.filepath === group.master_proposal?.proposed_master?.filepath ? '👑' : '📄'}</span>
                                <code className="break-all">{file.directory}</code>
                                <span className="ml-auto text-[var(--color-fg-tertiary)]">
                                  {file.size ? `${(file.size / 1024).toFixed(1)}KB` : ''}
                                </span>
                              </div>
                            ))}
                            {group.files?.length > 5 && (
                              <p className="text-xs text-[var(--color-fg-tertiary)] italic">
                                ... y {group.files.length - 5} mas
                              </p>
                            )}
                          </div>

                          {/* Botones de acción */}
                          {group.files?.length >= 2 && onNavigate && (
                            <div className="mt-3 pt-3 border-t border-[var(--color-border)] flex flex-wrap gap-2">
                              <button
                                onClick={() => onNavigate('compare', {
                                  file1: group.files[0]?.filepath,
                                  file2: group.files[1]?.filepath,
                                  fromPage: 'results',
                                })}
                                className="px-3 py-1 text-xs bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors"
                              >
                                🔀 Comparar
                              </button>
                              <button
                                onClick={() => onNavigate('merge', {
                                  files: group.files.map(f => f.filepath),
                                  masterProposal: group.master_proposal?.proposed_master?.filepath,
                                  fromPage: 'results',
                                })}
                                className="px-3 py-1 text-xs bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded hover:border-[var(--color-success)] hover:text-[var(--color-success)] transition-colors"
                              >
                                🔗 Merge
                              </button>
                              <button
                                onClick={() => onNavigate('impact', {
                                  scanId: selectedScanId,
                                  groupFile: filename,
                                  fromPage: 'results',
                                })}
                                className="px-3 py-1 text-xs bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded hover:border-[var(--color-warning)] hover:text-[var(--color-warning)] transition-colors"
                              >
                                💥 Impacto
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                      {Object.keys(results.sibling_details).length > 20 && (
                        <p className="text-center text-[var(--color-fg-tertiary)] text-sm">
                          Mostrando 20 de {Object.keys(results.sibling_details).length} grupos
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
