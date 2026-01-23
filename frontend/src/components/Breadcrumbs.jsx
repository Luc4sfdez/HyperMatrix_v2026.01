export default function Breadcrumbs({ items, onNavigate, projectName, scanInfo }) {
  if (!items || items.length === 0) return null

  return (
    <nav className="flex items-center justify-between text-sm mb-4">
      {/* Breadcrumb trail */}
      <div className="flex items-center gap-2">
        {items.map((item, idx) => (
          <div key={idx} className="flex items-center gap-2">
            {idx > 0 && (
              <svg className="w-4 h-4 text-[var(--color-fg-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            )}
            {idx === items.length - 1 ? (
              // Current page - no link
              <span className="text-[var(--color-fg-primary)] font-medium flex items-center">
                {item.icon && <span className="mr-1.5">{item.icon}</span>}
                {item.label}
              </span>
            ) : (
              // Clickable link
              <button
                onClick={() => onNavigate(item.page, item.data)}
                className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] hover:underline flex items-center transition-colors"
              >
                {item.icon && <span className="mr-1.5">{item.icon}</span>}
                {item.label}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Project/Scan context indicator */}
      {(projectName || scanInfo) && (
        <div className="flex items-center gap-3 text-xs text-[var(--color-fg-secondary)]">
          {projectName && (
            <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--color-bg-secondary)] border border-[var(--color-border)]">
              <span>📁</span>
              <span className="font-medium text-[var(--color-fg-primary)]">{projectName}</span>
            </span>
          )}
          {scanInfo && (
            <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--color-bg-secondary)] border border-[var(--color-border)]">
              <span className={`w-2 h-2 rounded-full ${
                scanInfo.status === 'completed' ? 'bg-[var(--color-success)]' :
                scanInfo.status === 'running' ? 'bg-[var(--color-warning)] animate-pulse' :
                'bg-[var(--color-fg-tertiary)]'
              }`}></span>
              <span>{scanInfo.total_files || 0} archivos</span>
            </span>
          )}
        </div>
      )}
    </nav>
  )
}

// Helper para generar breadcrumbs comunes
export function generateBreadcrumbs(currentPage, context = {}) {
  const crumbs = [
    { page: 'dashboard', label: 'Inicio', icon: '🏠' }
  ]

  const pageConfig = {
    dashboard: { label: 'Dashboard', icon: '📊' },
    results: { label: 'Resultados', icon: '📈' },
    analysis: { label: 'Análisis', icon: '🔬' },
    explorer: { label: 'Explorador', icon: '🗄️' },
    deadcode: { label: 'Código Muerto', icon: '💀' },
    compare: { label: 'Comparador', icon: '🔀' },
    merge: { label: 'Merge', icon: '🔗' },
    batch: { label: 'Acciones Lote', icon: '⚡' },
    projectcompare: { label: 'Comparar Proyectos', icon: '🔄' },
    refactoring: { label: 'Refactoring', icon: '🔧' },
    lineage: { label: 'Linaje', icon: '🔗' },
    impact: { label: 'Impacto', icon: '💥' },
    webhooks: { label: 'Webhooks', icon: '🔔' },
    ml: { label: 'ML', icon: '🧠' },
    rules: { label: 'Reglas', icon: '📋' },
    settings: { label: 'Configuración', icon: '⚙️' },
  }

  // Agregar contexto intermedio si existe
  if (context.fromPage && context.fromPage !== 'dashboard' && context.fromPage !== currentPage) {
    const fromConfig = pageConfig[context.fromPage]
    if (fromConfig) {
      crumbs.push({
        page: context.fromPage,
        label: fromConfig.label,
        icon: fromConfig.icon,
        data: context.fromData
      })
    }
  }

  // Agregar página actual
  if (currentPage !== 'dashboard') {
    const config = pageConfig[currentPage] || { label: currentPage, icon: '📄' }
    crumbs.push({
      page: currentPage,
      label: context.customLabel || config.label,
      icon: config.icon
    })
  }

  return crumbs
}
