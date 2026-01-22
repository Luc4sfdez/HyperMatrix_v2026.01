export default function Breadcrumbs({ items, onNavigate }) {
  if (!items || items.length === 0) return null

  return (
    <nav className="flex items-center gap-2 text-sm mb-4">
      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2">
          {idx > 0 && (
            <span className="text-[var(--color-fg-tertiary)]">/</span>
          )}
          {idx === items.length - 1 ? (
            // Current page - no link
            <span className="text-[var(--color-fg-primary)] font-medium">
              {item.icon && <span className="mr-1">{item.icon}</span>}
              {item.label}
            </span>
          ) : (
            // Clickable link
            <button
              onClick={() => onNavigate(item.page, item.data)}
              className="text-[var(--color-primary)] hover:underline flex items-center"
            >
              {item.icon && <span className="mr-1">{item.icon}</span>}
              {item.label}
            </button>
          )}
        </div>
      ))}
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
