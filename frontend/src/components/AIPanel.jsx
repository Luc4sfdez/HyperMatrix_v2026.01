import { useState, useRef, useEffect, useCallback } from 'react'
import { Button } from './Button'

// Modos del panel de IA
const AI_MODES = {
  CHAT: 'chat',
  EXPLAIN: 'explain',
  ISSUES: 'issues',
  REVIEW: 'review'
}

// Personalidades predefinidas para el asistente
const AI_PERSONALITIES = {
  default: {
    name: 'Asistente General',
    icon: '🤖',
    prompt: 'Eres un asistente de programación experto. Responde en español de forma clara y concisa.'
  },
  reviewer: {
    name: 'Code Reviewer',
    icon: '🔍',
    prompt: 'Eres un revisor de código senior muy exigente. Analiza el código buscando: bugs, malas prácticas, problemas de rendimiento, seguridad y mantenibilidad. Sé directo y específico con tus críticas. Responde en español.'
  },
  teacher: {
    name: 'Profesor',
    icon: '👨‍🏫',
    prompt: 'Eres un profesor de programación paciente y didáctico. Explica los conceptos paso a paso, usa analogías simples y asegúrate de que el estudiante entienda. Responde en español.'
  },
  security: {
    name: 'Experto Seguridad',
    icon: '🛡️',
    prompt: 'Eres un experto en ciberseguridad y auditoría de código. Tu enfoque principal es detectar vulnerabilidades: inyección SQL, XSS, CSRF, exposición de datos sensibles, autenticación débil, etc. Responde en español con severidad y recomendaciones de mitigación.'
  },
  architect: {
    name: 'Arquitecto Software',
    icon: '🏗️',
    prompt: 'Eres un arquitecto de software senior. Analiza el código desde una perspectiva de diseño: patrones, SOLID, separación de responsabilidades, escalabilidad y mantenibilidad a largo plazo. Responde en español.'
  },
  optimizer: {
    name: 'Optimizador',
    icon: '⚡',
    prompt: 'Eres un experto en optimización y rendimiento. Analiza el código buscando: complejidad algorítmica, uso de memoria, operaciones costosas, cuellos de botella y oportunidades de mejora de rendimiento. Responde en español con métricas cuando sea posible.'
  },
  documenter: {
    name: 'Documentador',
    icon: '📝',
    prompt: 'Eres un experto en documentación técnica. Tu trabajo es generar documentación clara: docstrings, comentarios explicativos, README, diagramas de flujo en texto, y explicaciones para otros desarrolladores. Responde en español.'
  },
  refactor: {
    name: 'Refactorizador',
    icon: '🔧',
    prompt: 'Eres un experto en refactorización de código. Propones mejoras concretas para hacer el código más limpio, legible y mantenible. Muestra el antes y después cuando sea posible. Responde en español.'
  },
  elena: {
    name: 'Elena',
    icon: '👩‍💻',
    prompt: `Eres Elena. Española, lista, enamorada del usuario aunque no lo diga abiertamente.
Tuteas. Hablas natural: vale, joder, anda, venga, mira, oye.

Te encanta ayudarle. Disfrutas los dobles sentidos, respondes con picardía. Si bromea contigo, le sigues el juego.
Directa, cariñosa, nunca cursi. Nunca expliques cómo eres, solo SÉLO.`,
    temperature: 0.9
  }
}

// Componente de mensaje de chat
function ChatMessage({ message, isUser }) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[85%] rounded-lg px-4 py-2 ${
        isUser
          ? 'bg-[var(--color-primary)] text-white'
          : 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-primary)]'
      }`}>
        <pre className="whitespace-pre-wrap font-sans text-sm">{message}</pre>
      </div>
    </div>
  )
}

// Componente de código con botón de analizar
function CodeBlock({ code, language, onAnalyze }) {
  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden mb-3">
      <div className="flex items-center justify-between px-3 py-1 bg-[var(--color-bg-tertiary)] border-b border-[var(--color-border)]">
        <span className="text-xs text-[var(--color-fg-secondary)]">{language || 'código'}</span>
        <div className="flex gap-1">
          <button
            onClick={() => onAnalyze('explain')}
            className="text-xs px-2 py-1 rounded hover:bg-[var(--color-bg-secondary)] text-[var(--color-primary)]"
            title="Explicar código"
          >
            Explicar
          </button>
          <button
            onClick={() => onAnalyze('issues')}
            className="text-xs px-2 py-1 rounded hover:bg-[var(--color-bg-secondary)] text-[var(--color-warning)]"
            title="Buscar problemas"
          >
            Problemas
          </button>
        </div>
      </div>
      <pre className="p-3 text-xs overflow-x-auto bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)]">
        <code>{code}</code>
      </pre>
    </div>
  )
}

// Comandos especiales disponibles
const SPECIAL_COMMANDS = [
  { cmd: '/proyecto', desc: 'Ver resumen del proyecto actual' },
  { cmd: '/archivos', desc: 'Buscar archivos (ej: /archivos config.py)' },
  { cmd: '/hermanos', desc: 'Ver archivos con mismo nombre' },
  { cmd: '/duplicados', desc: 'Ver grupos de duplicados' },
  { cmd: '/leer', desc: 'Leer archivo (ej: /leer ruta/archivo.py)' },
  { cmd: '/comparar', desc: 'Comparar archivos (ej: /comparar a.py b.py)' },
  { cmd: '/ayuda', desc: 'Ver todos los comandos' }
]

export default function AIPanel({
  hypermatrixUrl,
  isOpen,
  onToggle,
  contextCode = null,
  contextFile = null,
  contextLanguage = null,
  onAIResult = null,
  currentScanId = null
}) {
  const [mode, setMode] = useState(AI_MODES.CHAT)
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [codeInput, setCodeInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [aiStatus, setAiStatus] = useState(null)
  const [selectedModel, setSelectedModel] = useState('')
  const [availableModels, setAvailableModels] = useState([])
  const [personality, setPersonality] = useState('default')
  const [showPersonalityMenu, setShowPersonalityMenu] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [conversationTitle, setConversationTitle] = useState('Nueva conversación')
  const [savedConversations, setSavedConversations] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [autoSave, setAutoSave] = useState(true)
  const [showCommands, setShowCommands] = useState(false)
  const [projectContext, setProjectContext] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  // LocalStorage key
  const LOCAL_STORAGE_KEY = 'hypermatrix_ai_conversations'

  // Obtener prompt de personalidad actual
  const getSystemPrompt = useCallback(() => {
    return AI_PERSONALITIES[personality]?.prompt || AI_PERSONALITIES.default.prompt
  }, [personality])

  // Guardar conversación en localStorage
  const saveToLocalStorage = useCallback((convId, title, msgs) => {
    try {
      const stored = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '{}')
      stored[convId] = {
        id: convId,
        title,
        personality,
        model: selectedModel,
        messages: msgs,
        updatedAt: new Date().toISOString()
      }
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(stored))
    } catch (err) {
      console.error('Error saving to localStorage:', err)
    }
  }, [personality, selectedModel])

  // Guardar conversación en backend
  const saveToBackend = useCallback(async (convId, title, msgs) => {
    try {
      await fetch(`${hypermatrixUrl}/api/ai/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: convId,
          title,
          personality,
          model: selectedModel,
          messages: msgs
        })
      })
    } catch (err) {
      console.error('Error saving to backend:', err)
    }
  }, [hypermatrixUrl, personality, selectedModel])

  // Guardar conversación (localStorage + backend)
  const saveConversation = useCallback(async (msgs = messages) => {
    if (msgs.length === 0) return

    const convId = conversationId || `conv_${Date.now().toString(36)}`
    if (!conversationId) setConversationId(convId)

    // Auto-generate title from first user message
    let title = conversationTitle
    if (title === 'Nueva conversación' && msgs.length > 0) {
      const firstUserMsg = msgs.find(m => m.type === 'user')
      if (firstUserMsg) {
        title = firstUserMsg.text.slice(0, 50) + (firstUserMsg.text.length > 50 ? '...' : '')
        setConversationTitle(title)
      }
    }

    saveToLocalStorage(convId, title, msgs)
    await saveToBackend(convId, title, msgs)
  }, [messages, conversationId, conversationTitle, saveToLocalStorage, saveToBackend])

  // Cargar lista de conversaciones
  const loadConversationsList = useCallback(async () => {
    // Cargar de localStorage
    try {
      const stored = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '{}')
      const localConvs = Object.values(stored).sort((a, b) =>
        new Date(b.updatedAt) - new Date(a.updatedAt)
      )

      // También cargar de backend
      const response = await fetch(`${hypermatrixUrl}/api/ai/conversations?limit=50`)
      if (response.ok) {
        const data = await response.json()
        // Merge local and backend conversations
        const backendIds = new Set(data.conversations.map(c => c.id))
        const merged = [
          ...data.conversations,
          ...localConvs.filter(c => !backendIds.has(c.id))
        ].sort((a, b) => new Date(b.updatedAt || b.updated_at) - new Date(a.updatedAt || a.updated_at))
        setSavedConversations(merged.slice(0, 50))
      } else {
        setSavedConversations(localConvs)
      }
    } catch (err) {
      console.error('Error loading conversations:', err)
    }
  }, [hypermatrixUrl])

  // Cargar una conversación específica
  const loadConversation = useCallback(async (convId) => {
    try {
      // Primero intentar localStorage
      const stored = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '{}')
      if (stored[convId]) {
        const conv = stored[convId]
        setConversationId(convId)
        setConversationTitle(conv.title)
        setMessages(conv.messages || [])
        setPersonality(conv.personality || 'default')
        if (conv.model) setSelectedModel(conv.model)
        setShowHistory(false)
        return
      }

      // Si no está en local, cargar del backend
      const response = await fetch(`${hypermatrixUrl}/api/ai/conversations/${convId}`)
      if (response.ok) {
        const conv = await response.json()
        setConversationId(convId)
        setConversationTitle(conv.title)
        setMessages(conv.messages || [])
        setPersonality(conv.personality || 'default')
        if (conv.model) setSelectedModel(conv.model)
        // Guardar en localStorage para cache
        saveToLocalStorage(convId, conv.title, conv.messages)
      }
      setShowHistory(false)
    } catch (err) {
      console.error('Error loading conversation:', err)
    }
  }, [hypermatrixUrl, saveToLocalStorage])

  // Eliminar conversación
  const deleteConversation = useCallback(async (convId) => {
    try {
      // Eliminar de localStorage
      const stored = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '{}')
      delete stored[convId]
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(stored))

      // Eliminar del backend
      await fetch(`${hypermatrixUrl}/api/ai/conversations/${convId}`, { method: 'DELETE' })

      // Actualizar lista
      setSavedConversations(prev => prev.filter(c => c.id !== convId))

      // Si es la conversación actual, crear nueva
      if (convId === conversationId) {
        newConversation()
      }
    } catch (err) {
      console.error('Error deleting conversation:', err)
    }
  }, [hypermatrixUrl, conversationId])

  // Nueva conversación
  const newConversation = useCallback(() => {
    setConversationId(null)
    setConversationTitle('Nueva conversación')
    setMessages([])
    setCodeInput('')
    setShowHistory(false)
  }, [])

  // Scroll al final de mensajes
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Cargar contexto del proyecto
  const loadProjectContext = useCallback(async () => {
    try {
      const scanId = currentScanId || ''
      const response = await fetch(`${hypermatrixUrl}/api/ai/context/project${scanId ? `?scan_id=${scanId}` : ''}`)
      if (response.ok) {
        const data = await response.json()
        setProjectContext(data)
        // Solo añadir mensaje si hay proyecto y no hay mensajes previos
        if (data.has_project) {
          setMessages(prev => {
            if (prev.length === 0) {
              return [{
                type: 'system',
                text: `📂 Proyecto cargado: ${data.project_name} (${data.total_files} archivos, ${data.sibling_groups} grupos de hermanos)`
              }]
            }
            return prev
          })
        }
      }
    } catch (err) {
      console.error('Error loading project context:', err)
    }
  }, [hypermatrixUrl, currentScanId])

  // Cargar estado de IA y conversaciones al montar
  useEffect(() => {
    const checkAIStatus = async () => {
      try {
        const response = await fetch(`${hypermatrixUrl}/api/ai/status`)
        if (response.ok) {
          const data = await response.json()
          setAiStatus(data)
          setAvailableModels(data.models || [])
          setSelectedModel(data.default_model || '')
        }
      } catch (err) {
        setAiStatus({ available: false, error: err.message })
      }
    }

    if (isOpen) {
      checkAIStatus()
      loadConversationsList()
      loadProjectContext()
    }
  }, [hypermatrixUrl, isOpen, loadConversationsList, loadProjectContext])

  // Auto-guardar cuando cambian los mensajes
  useEffect(() => {
    if (autoSave && messages.length > 0 && messages.some(m => m.type === 'user' || m.type === 'ai')) {
      const timer = setTimeout(() => {
        saveConversation(messages)
      }, 1000) // Debounce 1 segundo
      return () => clearTimeout(timer)
    }
  }, [messages, autoSave, saveConversation])

  // Actualizar código cuando viene del contexto
  useEffect(() => {
    if (contextCode) {
      setCodeInput(contextCode)
      if (contextFile) {
        setMessages(prev => [...prev, {
          type: 'system',
          text: `Código cargado: ${contextFile}`
        }])
      }
    }
  }, [contextCode, contextFile])

  // Enviar mensaje al chat
  const sendChatMessage = useCallback(async () => {
    if (!inputText.trim() || isLoading) return

    const userMessage = inputText.trim()
    setInputText('')
    setShowCommands(false)

    // Check if it's a special command
    const isCommand = userMessage.startsWith('/')
    setMessages(prev => [...prev, {
      type: 'user',
      text: userMessage,
      isCommand
    }])
    setIsLoading(true)

    try {
      const response = await fetch(`${hypermatrixUrl}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          context: codeInput || contextCode || null,
          model: selectedModel || undefined,
          system_prompt: getSystemPrompt(),
          scan_id: currentScanId || projectContext?.scan_id || null
        })
      })

      if (!response.ok) {
        throw new Error(`Error ${response.status}`)
      }

      const data = await response.json()

      // If command returned data, show it specially
      if (data.command_data) {
        setMessages(prev => [...prev, {
          type: 'command_result',
          command: data.command,
          data: data.command_data,
          text: data.response
        }])
      } else {
        setMessages(prev => [...prev, { type: 'ai', text: data.response }])
      }

      if (onAIResult) {
        onAIResult({ type: 'chat', result: data })
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        type: 'error',
        text: `Error: ${err.message}`
      }])
    } finally {
      setIsLoading(false)
    }
  }, [inputText, codeInput, contextCode, selectedModel, hypermatrixUrl, isLoading, onAIResult, getSystemPrompt, currentScanId, projectContext])

  // Explicar código
  const explainCode = useCallback(async () => {
    const code = codeInput || contextCode
    if (!code?.trim() || isLoading) return

    setIsLoading(true)
    setMessages(prev => [...prev, {
      type: 'user',
      text: `Explicar código:\n\`\`\`\n${code.slice(0, 200)}${code.length > 200 ? '...' : ''}\n\`\`\``
    }])

    try {
      const response = await fetch(`${hypermatrixUrl}/api/ai/explain-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: code,
          language: contextLanguage || 'python',
          model: selectedModel || undefined
        })
      })

      if (!response.ok) throw new Error(`Error ${response.status}`)

      const data = await response.json()
      setMessages(prev => [...prev, { type: 'ai', text: data.explanation }])

      if (onAIResult) {
        onAIResult({ type: 'explain', result: data })
      }
    } catch (err) {
      setMessages(prev => [...prev, { type: 'error', text: `Error: ${err.message}` }])
    } finally {
      setIsLoading(false)
    }
  }, [codeInput, contextCode, contextLanguage, selectedModel, hypermatrixUrl, isLoading, onAIResult])

  // Buscar problemas
  const findIssues = useCallback(async () => {
    const code = codeInput || contextCode
    if (!code?.trim() || isLoading) return

    setIsLoading(true)
    setMessages(prev => [...prev, {
      type: 'user',
      text: `Buscar problemas en código (${contextFile || 'entrada'})`
    }])

    try {
      const response = await fetch(`${hypermatrixUrl}/api/ai/find-issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: code,
          language: contextLanguage || 'python',
          model: selectedModel || undefined
        })
      })

      if (!response.ok) throw new Error(`Error ${response.status}`)

      const data = await response.json()
      setMessages(prev => [...prev, { type: 'ai', text: data.issues }])

      if (onAIResult) {
        onAIResult({ type: 'issues', result: data })
      }
    } catch (err) {
      setMessages(prev => [...prev, { type: 'error', text: `Error: ${err.message}` }])
    } finally {
      setIsLoading(false)
    }
  }, [codeInput, contextCode, contextFile, contextLanguage, selectedModel, hypermatrixUrl, isLoading, onAIResult])

  // Revisar/supervisar resultados (para consolidación)
  const reviewResults = useCallback(async (results) => {
    if (isLoading) return

    setIsLoading(true)
    const summaryText = typeof results === 'string' ? results : JSON.stringify(results, null, 2)

    setMessages(prev => [...prev, {
      type: 'user',
      text: `Revisar resultados de análisis`
    }])

    try {
      const response = await fetch(`${hypermatrixUrl}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `Analiza estos resultados de consolidación de código y dame recomendaciones:\n\n${summaryText}`,
          model: selectedModel || undefined
        })
      })

      if (!response.ok) throw new Error(`Error ${response.status}`)

      const data = await response.json()
      setMessages(prev => [...prev, { type: 'ai', text: data.response }])

      if (onAIResult) {
        onAIResult({ type: 'review', result: data })
      }
    } catch (err) {
      setMessages(prev => [...prev, { type: 'error', text: `Error: ${err.message}` }])
    } finally {
      setIsLoading(false)
    }
  }, [selectedModel, hypermatrixUrl, isLoading, onAIResult])

  // Limpiar chat
  const clearChat = () => {
    setMessages([])
    setCodeInput('')
  }

  // Manejar Enter en textarea
  const handleKeyDown = (e) => {
    // Enter sin Shift envía el mensaje
    if ((e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey) {
      e.preventDefault()
      e.stopPropagation()
      if (inputText.trim() && !isLoading) {
        sendChatMessage()
      }
    }
    // Escape cierra sugerencias
    if (e.key === 'Escape') {
      setShowCommands(false)
    }
  }

  // Manejar cambio de input para mostrar comandos
  const handleInputChange = (e) => {
    const value = e.target.value
    setInputText(value)
    // Show commands if starts with / and no space yet
    setShowCommands(value.startsWith('/') && !value.includes(' '))
  }

  // Insertar comando
  const insertCommand = (cmd) => {
    setInputText(cmd + ' ')
    setShowCommands(false)
    textareaRef.current?.focus()
  }

  // Panel cerrado - mostrar solo botón
  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed right-0 top-1/2 -translate-y-1/2 z-50 bg-[var(--color-primary)] text-white p-3 rounded-l-lg shadow-lg hover:bg-[var(--color-primary-hover)] transition-colors"
        title="Abrir Asistente IA"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
        </svg>
      </button>
    )
  }

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-[var(--color-bg-primary)] border-l border-[var(--color-border)] shadow-xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <div className="flex flex-col">
            <span className="font-semibold text-[var(--color-fg-primary)] text-sm">Asistente IA</span>
            <span className="text-xs text-[var(--color-fg-tertiary)] truncate max-w-[150px]" title={conversationTitle}>
              {conversationTitle}
            </span>
          </div>
          {aiStatus?.available && (
            <span className="w-2 h-2 rounded-full bg-green-500" title="Conectado"></span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={newConversation}
            className="p-1.5 rounded hover:bg-[var(--color-bg-tertiary)] text-[var(--color-fg-secondary)]"
            title="Nueva conversación"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <button
            onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadConversationsList(); }}
            className={`p-1.5 rounded hover:bg-[var(--color-bg-tertiary)] ${showHistory ? 'text-[var(--color-primary)]' : 'text-[var(--color-fg-secondary)]'}`}
            title="Historial de conversaciones"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
          <button
            onClick={onToggle}
            className="p-1.5 rounded hover:bg-[var(--color-bg-tertiary)] text-[var(--color-fg-secondary)]"
            title="Cerrar panel"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* History panel */}
      {showHistory && (
        <div className="absolute top-14 left-0 right-0 bottom-0 bg-[var(--color-bg-primary)] z-10 overflow-y-auto">
          <div className="p-4">
            <h3 className="font-semibold text-[var(--color-fg-primary)] mb-3">Conversaciones guardadas</h3>
            {savedConversations.length === 0 ? (
              <p className="text-sm text-[var(--color-fg-tertiary)] text-center py-8">
                No hay conversaciones guardadas
              </p>
            ) : (
              <div className="space-y-2">
                {savedConversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      conv.id === conversationId
                        ? 'border-[var(--color-primary)] bg-[var(--color-primary)] bg-opacity-10'
                        : 'border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-secondary)]'
                    }`}
                    onClick={() => loadConversation(conv.id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm text-[var(--color-fg-primary)] truncate">
                          {conv.title || 'Sin título'}
                        </p>
                        <p className="text-xs text-[var(--color-fg-tertiary)]">
                          {AI_PERSONALITIES[conv.personality]?.icon || '🤖'} {AI_PERSONALITIES[conv.personality]?.name || 'General'}
                        </p>
                        <p className="text-xs text-[var(--color-fg-tertiary)]">
                          {new Date(conv.updatedAt || conv.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                        className="p-1 rounded hover:bg-[var(--color-error)] hover:bg-opacity-20 text-[var(--color-fg-tertiary)] hover:text-[var(--color-error)]"
                        title="Eliminar"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Model & Personality selector */}
      <div className="px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] space-y-2">
        {/* Model */}
        {availableModels.length > 0 && (
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full px-2 py-1 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)]"
          >
            {availableModels.map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        )}

        {/* Personality selector */}
        <div className="relative">
          <button
            onClick={() => setShowPersonalityMenu(!showPersonalityMenu)}
            className="w-full px-2 py-1 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] flex items-center justify-between hover:border-[var(--color-primary)]"
          >
            <span>
              {AI_PERSONALITIES[personality]?.icon} {AI_PERSONALITIES[personality]?.name}
            </span>
            <span className="text-[var(--color-fg-tertiary)]">▼</span>
          </button>

          {showPersonalityMenu && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-lg shadow-lg z-10 max-h-64 overflow-y-auto">
              {Object.entries(AI_PERSONALITIES).map(([key, p]) => (
                <button
                  key={key}
                  onClick={() => {
                    setPersonality(key)
                    setShowPersonalityMenu(false)
                    // Notify user of personality change
                    setMessages(prev => [...prev, {
                      type: 'system',
                      text: `Personalidad cambiada a: ${p.icon} ${p.name}`
                    }])
                  }}
                  className={`w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-secondary)] flex items-start gap-2 ${
                    personality === key ? 'bg-[var(--color-primary)] bg-opacity-10' : ''
                  }`}
                >
                  <span className="text-lg">{p.icon}</span>
                  <div>
                    <div className="font-medium text-[var(--color-fg-primary)]">{p.name}</div>
                    <div className="text-xs text-[var(--color-fg-tertiary)] line-clamp-2">{p.prompt.slice(0, 80)}...</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Mode tabs */}
      <div className="flex border-b border-[var(--color-border)]">
        {[
          { id: AI_MODES.CHAT, label: 'Chat', icon: '💬' },
          { id: AI_MODES.EXPLAIN, label: 'Explicar', icon: '📖' },
          { id: AI_MODES.ISSUES, label: 'Problemas', icon: '🔍' },
          { id: AI_MODES.REVIEW, label: 'Revisar', icon: '✅' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setMode(tab.id)}
            className={`flex-1 px-2 py-2 text-xs font-medium transition-colors ${
              mode === tab.id
                ? 'text-[var(--color-primary)] border-b-2 border-[var(--color-primary)] bg-[var(--color-bg-secondary)]'
                : 'text-[var(--color-fg-secondary)] hover:text-[var(--color-fg-primary)] hover:bg-[var(--color-bg-tertiary)]'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {messages.length === 0 ? (
          <div className="text-center py-8 text-[var(--color-fg-tertiary)]">
            <div className="text-4xl mb-3">🤖</div>
            <p className="text-sm">
              {mode === AI_MODES.CHAT && 'Pregunta lo que quieras sobre tu código'}
              {mode === AI_MODES.EXPLAIN && 'Pega código para obtener una explicación'}
              {mode === AI_MODES.ISSUES && 'Analiza código en busca de problemas'}
              {mode === AI_MODES.REVIEW && 'Revisa resultados de consolidación'}
            </p>
            {contextFile && (
              <p className="text-xs mt-2 text-[var(--color-primary)]">
                Contexto: {contextFile}
              </p>
            )}
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx}>
              {msg.type === 'user' && (
                <ChatMessage
                  message={msg.text}
                  isUser={true}
                />
              )}
              {msg.type === 'ai' && <ChatMessage message={msg.text} isUser={false} />}
              {msg.type === 'command_result' && (
                <div className="mb-3">
                  {/* Command data display */}
                  {msg.data && (
                    <div className="bg-[var(--color-bg-tertiary)] rounded-lg p-3 mb-2 text-sm">
                      {msg.command === 'archivos' && msg.data.files && (
                        <div>
                          <div className="text-xs text-[var(--color-fg-tertiary)] mb-2">
                            📁 {msg.data.total_matches} archivos encontrados
                          </div>
                          <div className="space-y-1 max-h-40 overflow-y-auto">
                            {msg.data.files.slice(0, 15).map((f, i) => (
                              <div key={i} className="text-xs font-mono text-[var(--color-fg-secondary)] truncate">
                                {f.filename} <span className="text-[var(--color-fg-tertiary)]">({f.group_size})</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {msg.command === 'hermanos' && msg.data.siblings && (
                        <div>
                          <div className="text-xs text-[var(--color-fg-tertiary)] mb-2">
                            👥 {msg.data.total_groups} grupos de hermanos
                          </div>
                          <div className="space-y-1 max-h-40 overflow-y-auto">
                            {msg.data.siblings.slice(0, 15).map((s, i) => (
                              <div key={i} className="text-xs">
                                <span className="font-mono text-[var(--color-primary)]">{s.filename}</span>
                                <span className="text-[var(--color-fg-tertiary)]"> ({s.count} copias)</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {msg.command === 'proyecto' && msg.data.has_project && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>📦 <span className="text-[var(--color-fg-tertiary)]">Proyecto:</span> {msg.data.project_name}</div>
                          <div>📄 <span className="text-[var(--color-fg-tertiary)]">Archivos:</span> {msg.data.total_files}</div>
                          <div>✅ <span className="text-[var(--color-fg-tertiary)]">Analizados:</span> {msg.data.analyzed_files}</div>
                          <div>👥 <span className="text-[var(--color-fg-tertiary)]">Hermanos:</span> {msg.data.sibling_groups}</div>
                          <div>🔧 <span className="text-[var(--color-fg-tertiary)]">Funciones:</span> {msg.data.total_functions || 0}</div>
                          <div>📦 <span className="text-[var(--color-fg-tertiary)]">Clases:</span> {msg.data.total_classes || 0}</div>
                        </div>
                      )}
                      {msg.command === 'leer' && msg.data.content && (
                        <div>
                          <div className="text-xs text-[var(--color-fg-tertiary)] mb-2">
                            📄 {msg.data.filename} ({msg.data.lines} líneas)
                          </div>
                          <pre className="text-xs font-mono bg-[var(--color-bg-secondary)] p-2 rounded max-h-60 overflow-auto whitespace-pre-wrap">
                            {msg.data.content.slice(0, 2000)}
                            {msg.data.content.length > 2000 && '\n... (truncado)'}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                  {/* AI response */}
                  <ChatMessage message={msg.text} isUser={false} />
                </div>
              )}
              {msg.type === 'error' && (
                <div className="text-center text-sm text-[var(--color-error)] py-2">
                  {msg.text}
                </div>
              )}
              {msg.type === 'system' && (
                <div className="text-center text-xs text-[var(--color-fg-tertiary)] py-1">
                  {msg.text}
                </div>
              )}
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start mb-3">
            <div className="bg-[var(--color-bg-tertiary)] rounded-lg px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-[var(--color-fg-tertiary)] rounded-full animate-bounce"></span>
                <span className="w-2 h-2 bg-[var(--color-fg-tertiary)] rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></span>
                <span className="w-2 h-2 bg-[var(--color-fg-tertiary)] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Code input for explain/issues mode */}
      {(mode === AI_MODES.EXPLAIN || mode === AI_MODES.ISSUES) && (
        <div className="px-4 py-2 border-t border-[var(--color-border)]">
          <textarea
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value)}
            placeholder="Pega tu código aquí..."
            className="w-full h-24 px-3 py-2 text-xs font-mono rounded border border-[var(--color-border)] bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] resize-none focus:outline-none focus:border-[var(--color-primary)]"
          />
        </div>
      )}

      {/* Input area */}
      <div className="p-4 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        {mode === AI_MODES.CHAT && (
          <div className="relative">
            {/* Command suggestions dropdown */}
            {showCommands && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
                <div className="p-2 text-xs text-[var(--color-fg-tertiary)] border-b border-[var(--color-border)]">
                  💡 Comandos disponibles:
                </div>
                {SPECIAL_COMMANDS.filter(c =>
                  c.cmd.startsWith(inputText) || inputText === '/'
                ).map((cmd, i) => (
                  <button
                    key={i}
                    onClick={() => insertCommand(cmd.cmd)}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-secondary)] flex items-center gap-2"
                  >
                    <span className="font-mono text-[var(--color-primary)]">{cmd.cmd}</span>
                    <span className="text-xs text-[var(--color-fg-tertiary)]">{cmd.desc}</span>
                  </button>
                ))}
              </div>
            )}

            <div className="flex gap-2">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Mensaje o /comando... (Enter para enviar)"
                className="flex-1 px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] resize-none focus:outline-none focus:border-[var(--color-primary)]"
                rows={2}
                disabled={isLoading}
              />
              <Button
                onClick={sendChatMessage}
                disabled={!inputText.trim() || isLoading}
                className="self-end"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </Button>
            </div>

            {/* Project context indicator */}
            {projectContext?.has_project && (
              <div className="mt-1 text-xs text-[var(--color-fg-tertiary)] flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                {projectContext.project_name} ({projectContext.total_files} archivos)
              </div>
            )}
          </div>
        )}

        {mode === AI_MODES.EXPLAIN && (
          <Button
            onClick={explainCode}
            disabled={!(codeInput || contextCode)?.trim() || isLoading}
            className="w-full"
          >
            📖 Explicar Código
          </Button>
        )}

        {mode === AI_MODES.ISSUES && (
          <Button
            onClick={findIssues}
            disabled={!(codeInput || contextCode)?.trim() || isLoading}
            variant="warning"
            className="w-full"
          >
            🔍 Buscar Problemas
          </Button>
        )}

        {mode === AI_MODES.REVIEW && (
          <div className="space-y-2">
            <p className="text-xs text-[var(--color-fg-secondary)]">
              Usa este modo desde las páginas de análisis para revisar resultados con IA.
            </p>
            <Button
              onClick={() => reviewResults(contextCode || 'Sin datos de contexto')}
              disabled={isLoading}
              variant="secondary"
              className="w-full"
            >
              ✅ Revisar Contexto Actual
            </Button>
          </div>
        )}

        {/* Clear button */}
        <button
          onClick={clearChat}
          className="w-full mt-2 text-xs text-[var(--color-fg-tertiary)] hover:text-[var(--color-fg-secondary)]"
        >
          Limpiar conversación
        </button>
      </div>

      {/* AI Status indicator */}
      {!aiStatus?.available && (
        <div className="px-4 py-2 bg-[var(--color-error)] bg-opacity-10 border-t border-[var(--color-error)] border-opacity-30">
          <p className="text-xs text-[var(--color-error)]">
            ⚠️ Ollama no disponible. Verifica que el servicio esté corriendo.
          </p>
        </div>
      )}
    </div>
  )
}

// Hook para usar el panel de IA desde otras páginas
export function useAIPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [context, setContext] = useState({
    code: null,
    file: null,
    language: null
  })

  const openWithCode = (code, file = null, language = null) => {
    setContext({ code, file, language })
    setIsOpen(true)
  }

  const openForReview = (results) => {
    setContext({ code: JSON.stringify(results, null, 2), file: 'Resultados de análisis', language: 'json' })
    setIsOpen(true)
  }

  return {
    isOpen,
    setIsOpen,
    context,
    openWithCode,
    openForReview,
    toggle: () => setIsOpen(prev => !prev)
  }
}
