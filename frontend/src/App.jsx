import { useState, useEffect, useCallback } from 'react'
import { Layout, LayoutHeader } from './components/Layout'
import { Sidebar, SidebarNav, SidebarNavGroup, SidebarNavItem } from './components/Sidebar'
import { ThemeToggle } from './components/ThemeToggle'
import { SearchBar } from './components/SearchBar'
import Breadcrumbs, { generateBreadcrumbs } from './components/Breadcrumbs'
import Dashboard from './pages/Dashboard'
import ScanResults from './pages/ScanResults'
import Analysis from './pages/Analysis'
import Explorer from './pages/Explorer'
import DeadCode from './pages/DeadCode'
import Compare from './pages/Compare'
import MergeWizard from './pages/MergeWizard'
import BatchActions from './pages/BatchActions'
import ProjectCompare from './pages/ProjectCompare'
import Rules from './pages/Rules'
import Refactoring from './pages/Refactoring'
import Lineage from './pages/Lineage'
import ImpactAnalysis from './pages/ImpactAnalysis'
import Webhooks from './pages/Webhooks'
import MLDashboard from './pages/MLDashboard'
import Settings from './pages/Settings'
import './styles/variables.css'
import './styles/globals.css'

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [navContext, setNavContext] = useState({}) // Contexto de navegación (datos entre páginas)
  const [navHistory, setNavHistory] = useState([]) // Historial para breadcrumbs
  const [hypermatrixUrl, setHypermatrixUrl] = useState('http://127.0.0.1:26020')
  const [isConnected, setIsConnected] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Navegación con contexto
  const handleNavigate = useCallback((page, data = {}) => {
    setNavHistory(prev => [...prev.slice(-5), { page: currentPage, data: navContext }])
    setNavContext(data)
    setCurrentPage(page)
  }, [currentPage, navContext])

  // Verificar conexión a HyperMatrix
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/scan/list`)
        setIsConnected(response.ok)
      } catch {
        setIsConnected(false)
      }
    }
    checkConnection()
    const interval = setInterval(checkConnection, 5000)
    return () => clearInterval(interval)
  }, [hypermatrixUrl])

  // Props comunes para todas las páginas
  const commonProps = {
    hypermatrixUrl,
    onNavigate: handleNavigate,
    navContext,
  }

  // Renderizar solo la página actual (evita crear todas las páginas en cada render)
  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'dashboard': return <Dashboard {...commonProps} />
      case 'results': return <ScanResults {...commonProps} />
      case 'analysis': return <Analysis {...commonProps} />
      case 'explorer': return <Explorer {...commonProps} />
      case 'deadcode': return <DeadCode {...commonProps} />
      case 'compare': return <Compare {...commonProps} />
      case 'merge': return <MergeWizard {...commonProps} />
      case 'batch': return <BatchActions {...commonProps} />
      case 'projectcompare': return <ProjectCompare {...commonProps} />
      case 'refactoring': return <Refactoring {...commonProps} />
      case 'lineage': return <Lineage {...commonProps} />
      case 'impact': return <ImpactAnalysis {...commonProps} />
      case 'webhooks': return <Webhooks {...commonProps} />
      case 'ml': return <MLDashboard {...commonProps} />
      case 'rules': return <Rules {...commonProps} />
      case 'settings': return <Settings {...commonProps} setHypermatrixUrl={setHypermatrixUrl} />
      default: return <Dashboard {...commonProps} />
    }
  }

  const sidebarContent = (
    <Sidebar width="280px">
      <div className="p-6 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🔍</span>
          <div>
            <h1 className="font-bold text-[var(--color-fg-primary)]">HyperMatrix</h1>
            <p className="text-xs text-[var(--color-fg-secondary)]">Code Analysis</p>
          </div>
        </div>
      </div>

      <SidebarNav>
        <SidebarNavGroup title="Analisis" defaultOpen>
          <SidebarNavItem
            href="#"
            active={currentPage === 'dashboard'}
            onClick={() => setCurrentPage('dashboard')}
          >
            📊 Dashboard
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'results'}
            onClick={() => setCurrentPage('results')}
          >
            📈 Resultados
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'analysis'}
            onClick={() => setCurrentPage('analysis')}
          >
            🔬 Analisis Avanzado
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'explorer'}
            onClick={() => setCurrentPage('explorer')}
          >
            🗄️ Explorador BD
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'deadcode'}
            onClick={() => setCurrentPage('deadcode')}
          >
            💀 Código Muerto
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'compare'}
            onClick={() => setCurrentPage('compare')}
          >
            🔀 Comparador
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'merge'}
            onClick={() => setCurrentPage('merge')}
          >
            🔗 Merge Wizard
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'batch'}
            onClick={() => setCurrentPage('batch')}
          >
            ⚡ Acciones Lote
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'projectcompare'}
            onClick={() => setCurrentPage('projectcompare')}
          >
            🔄 Comparar Proyectos
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'refactoring'}
            onClick={() => setCurrentPage('refactoring')}
          >
            🔧 Refactoring
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'lineage'}
            onClick={() => setCurrentPage('lineage')}
          >
            🔗 Grafo Linaje
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'impact'}
            onClick={() => setCurrentPage('impact')}
          >
            💥 Análisis Impacto
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'webhooks'}
            onClick={() => setCurrentPage('webhooks')}
          >
            🔔 Webhooks
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'ml'}
            onClick={() => setCurrentPage('ml')}
          >
            🧠 Dashboard ML
          </SidebarNavItem>
        </SidebarNavGroup>

        <SidebarNavGroup title="Sistema">
          <SidebarNavItem
            href="#"
            active={currentPage === 'rules'}
            onClick={() => setCurrentPage('rules')}
          >
            📋 Reglas
          </SidebarNavItem>
          <SidebarNavItem
            href="#"
            active={currentPage === 'settings'}
            onClick={() => setCurrentPage('settings')}
          >
            ⚙️ Configuracion
          </SidebarNavItem>
        </SidebarNavGroup>
      </SidebarNav>

      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="flex items-center gap-2 text-xs">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'}`}></div>
          <span className="text-[var(--color-fg-secondary)]">
            {isConnected ? 'Conectado' : 'Desconectado'}
          </span>
        </div>
        <p className="text-xs text-[var(--color-fg-tertiary)] mt-1 break-words">{hypermatrixUrl}</p>
      </div>
    </Sidebar>
  )

  return (
    <Layout
      sidebar={sidebarOpen ? sidebarContent : null}
      header={
        <div className="flex items-center justify-between w-full gap-4">
          <div className="flex items-center gap-4 flex-shrink-0">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-md transition-colors hover:bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)]"
              title={sidebarOpen ? 'Cerrar sidebar' : 'Abrir sidebar'}
            >
              {sidebarOpen ? '✕' : '☰'}
            </button>
            <LayoutHeader
              title="HyperMatrix"
              subtitle={isConnected ? 'Conectado' : 'Desconectado'}
            />
          </div>
          <SearchBar
            hypermatrixUrl={hypermatrixUrl}
            onNavigate={handleNavigate}
          />
          <ThemeToggle />
        </div>
      }
    >
      <div className="bg-[var(--color-bg-primary)]">
        {/* Breadcrumbs */}
        {currentPage !== 'dashboard' && (
          <div className="px-6 pt-4">
            <Breadcrumbs
              items={generateBreadcrumbs(currentPage, navContext)}
              onNavigate={handleNavigate}
            />
          </div>
        )}
        {renderCurrentPage()}
      </div>
    </Layout>
  )
}
