import { createContext, useContext, useState, useCallback } from 'react'

const AIContext = createContext(null)

export function AIProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false)
  const [contextCode, setContextCode] = useState(null)
  const [contextFile, setContextFile] = useState(null)
  const [contextLanguage, setContextLanguage] = useState(null)
  const [lastResult, setLastResult] = useState(null)

  // Abrir panel con código específico
  const openWithCode = useCallback((code, file = null, language = null) => {
    setContextCode(code)
    setContextFile(file)
    setContextLanguage(language)
    setIsOpen(true)
  }, [])

  // Abrir panel para revisar resultados de análisis
  const openForReview = useCallback((results, title = 'Resultados') => {
    const resultsText = typeof results === 'string' ? results : JSON.stringify(results, null, 2)
    setContextCode(resultsText)
    setContextFile(title)
    setContextLanguage('json')
    setIsOpen(true)
  }, [])

  // Abrir panel vacío
  const open = useCallback(() => {
    setIsOpen(true)
  }, [])

  // Cerrar panel
  const close = useCallback(() => {
    setIsOpen(false)
  }, [])

  // Toggle panel
  const toggle = useCallback(() => {
    setIsOpen(prev => !prev)
  }, [])

  // Limpiar contexto
  const clearContext = useCallback(() => {
    setContextCode(null)
    setContextFile(null)
    setContextLanguage(null)
  }, [])

  // Manejar resultado de IA
  const handleAIResult = useCallback((result) => {
    setLastResult(result)
  }, [])

  const value = {
    // Estado
    isOpen,
    contextCode,
    contextFile,
    contextLanguage,
    lastResult,

    // Acciones
    open,
    close,
    toggle,
    openWithCode,
    openForReview,
    clearContext,
    handleAIResult,
    setIsOpen
  }

  return (
    <AIContext.Provider value={value}>
      {children}
    </AIContext.Provider>
  )
}

export function useAI() {
  const context = useContext(AIContext)
  if (!context) {
    throw new Error('useAI must be used within an AIProvider')
  }
  return context
}

export default AIContext
