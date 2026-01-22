import { useState, useCallback, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'
import { Button } from '../components/Button'

// Badge de estado
function StatusBadge({ enabled }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
      enabled
        ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
        : 'bg-[var(--color-fg-tertiary)] bg-opacity-20 text-[var(--color-fg-tertiary)]'
    }`}>
      {enabled ? 'Activo' : 'Inactivo'}
    </span>
  )
}

// Badge de delivery
function DeliveryBadge({ success }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
      success
        ? 'bg-[var(--color-success)] bg-opacity-20 text-[var(--color-success)]'
        : 'bg-[var(--color-error)] bg-opacity-20 text-[var(--color-error)]'
    }`}>
      {success ? '✓ OK' : '✕ Error'}
    </span>
  )
}

// Tarjeta de webhook
function WebhookCard({ webhook, onDelete, onViewHistory, expanded, onToggle }) {
  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
      <div
        className="p-4 bg-[var(--color-bg-secondary)] cursor-pointer flex items-center gap-4"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-[var(--color-fg-primary)]">{webhook.id}</span>
            <StatusBadge enabled={webhook.enabled} />
          </div>
          <p className="text-sm text-[var(--color-fg-tertiary)] font-mono truncate">
            {webhook.url}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--color-fg-secondary)]">
            {webhook.events?.length || 0} eventos
          </span>
          <span className="text-[var(--color-fg-tertiary)]">
            {expanded ? '▼' : '▶'}
          </span>
        </div>
      </div>

      {expanded && (
        <div className="p-4 bg-[var(--color-bg-primary)] border-t border-[var(--color-border)] space-y-4">
          {/* URL */}
          <div>
            <label className="text-xs text-[var(--color-fg-tertiary)]">URL</label>
            <p className="font-mono text-sm text-[var(--color-fg-primary)] break-all">{webhook.url}</p>
          </div>

          {/* Eventos */}
          <div>
            <label className="text-xs text-[var(--color-fg-tertiary)]">Eventos Suscritos</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {(webhook.events || []).map((event, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-[var(--color-primary)] bg-opacity-10 rounded text-xs font-mono text-[var(--color-primary)]"
                >
                  {event}
                </span>
              ))}
            </div>
          </div>

          {/* Secret */}
          {webhook.secret && (
            <div>
              <label className="text-xs text-[var(--color-fg-tertiary)]">Secret</label>
              <p className="font-mono text-sm text-[var(--color-fg-secondary)]">••••••••</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
            <Button variant="secondary" onClick={onViewHistory}>
              📋 Ver Historial
            </Button>
            <Button variant="danger" onClick={onDelete}>
              🗑️ Eliminar
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// Modal para agregar webhook
function AddWebhookModal({ isOpen, onClose, onAdd, availableEvents }) {
  const [id, setId] = useState('')
  const [url, setUrl] = useState('')
  const [secret, setSecret] = useState('')
  const [selectedEvents, setSelectedEvents] = useState([])
  const [enabled, setEnabled] = useState(true)

  const handleAdd = () => {
    if (!id.trim() || !url.trim() || selectedEvents.length === 0) return
    onAdd({ id, url, secret: secret || null, events: selectedEvents, enabled })
    // Reset
    setId('')
    setUrl('')
    setSecret('')
    setSelectedEvents([])
    setEnabled(true)
    onClose()
  }

  const toggleEvent = (eventName) => {
    setSelectedEvents(prev =>
      prev.includes(eventName)
        ? prev.filter(e => e !== eventName)
        : [...prev, eventName]
    )
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-auto">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="font-bold text-[var(--color-fg-primary)]">Registrar Webhook</h3>
          <button onClick={onClose} className="p-2 hover:bg-[var(--color-bg-secondary)] rounded">
            ✕
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* ID */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-1">
              ID (único)
            </label>
            <input
              type="text"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="mi-webhook-1"
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>

          {/* URL */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-1">
              URL del Endpoint
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://mi-servidor.com/webhook"
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>

          {/* Secret */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-1">
              Secret (opcional)
            </label>
            <input
              type="text"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder="mi-secret-key"
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg-primary)] text-[var(--color-fg-primary)] focus:outline-none focus:border-[var(--color-primary)]"
            />
            <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
              Se usará para firmar las peticiones (HMAC-SHA256)
            </p>
          </div>

          {/* Eventos */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-fg-primary)] mb-2">
              Eventos
            </label>
            <div className="grid grid-cols-1 gap-2 max-h-48 overflow-auto">
              {availableEvents.map(event => (
                <label
                  key={event.name}
                  className="flex items-start gap-2 p-2 rounded hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(event.name)}
                    onChange={() => toggleEvent(event.name)}
                    className="mt-1"
                  />
                  <div>
                    <span className="font-mono text-sm text-[var(--color-fg-primary)]">{event.name}</span>
                    <p className="text-xs text-[var(--color-fg-tertiary)]">{event.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Enabled */}
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <span className="text-sm text-[var(--color-fg-primary)]">Activar inmediatamente</span>
          </label>
        </div>

        <div className="p-4 border-t border-[var(--color-border)] flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            onClick={handleAdd}
            disabled={!id.trim() || !url.trim() || selectedEvents.length === 0}
          >
            Registrar
          </Button>
        </div>
      </div>
    </div>
  )
}

// Modal de historial
function HistoryModal({ isOpen, onClose, webhookId, history }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-bg-primary)] rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="font-bold text-[var(--color-fg-primary)]">
            Historial: {webhookId}
          </h3>
          <button onClick={onClose} className="p-2 hover:bg-[var(--color-bg-secondary)] rounded">
            ✕
          </button>
        </div>

        <div className="p-4">
          {history.length === 0 ? (
            <p className="text-center text-[var(--color-fg-tertiary)] py-8">
              No hay entregas registradas
            </p>
          ) : (
            <div className="space-y-2">
              {history.map((delivery, idx) => (
                <div
                  key={idx}
                  className="p-3 border border-[var(--color-border)] rounded-lg flex items-center gap-4"
                >
                  <DeliveryBadge success={delivery.success} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm text-[var(--color-primary)]">
                        {delivery.event}
                      </span>
                      {delivery.status_code && (
                        <span className="text-xs text-[var(--color-fg-tertiary)]">
                          HTTP {delivery.status_code}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-[var(--color-fg-tertiary)]">
                      {new Date(delivery.timestamp).toLocaleString()}
                      {delivery.duration_ms && ` • ${delivery.duration_ms}ms`}
                      {delivery.attempts > 1 && ` • ${delivery.attempts} intentos`}
                    </div>
                    {delivery.error && (
                      <p className="text-xs text-[var(--color-error)] mt-1">{delivery.error}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Webhooks({ hypermatrixUrl }) {
  const [webhooks, setWebhooks] = useState([])
  const [availableEvents, setAvailableEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedWebhook, setExpandedWebhook] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [historyModal, setHistoryModal] = useState({ isOpen: false, webhookId: null, history: [] })

  // Cargar webhooks y eventos
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [webhooksRes, eventsRes] = await Promise.all([
        fetch(`${hypermatrixUrl}/api/advanced/webhooks`),
        fetch(`${hypermatrixUrl}/api/advanced/webhooks/events`),
      ])

      if (webhooksRes.ok) {
        const data = await webhooksRes.json()
        setWebhooks(data.webhooks || [])
      }

      if (eventsRes.ok) {
        const data = await eventsRes.json()
        setAvailableEvents(data.events || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [hypermatrixUrl])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Registrar webhook
  const addWebhook = async (webhookData) => {
    try {
      const response = await fetch(`${hypermatrixUrl}/api/advanced/webhooks/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(webhookData),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  // Eliminar webhook
  const deleteWebhook = async (webhookId) => {
    if (!confirm(`¿Eliminar webhook "${webhookId}"?`)) return

    try {
      const response = await fetch(`${hypermatrixUrl}/api/advanced/webhooks/${webhookId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Error ${response.status}`)
      }

      setWebhooks(prev => prev.filter(w => w.id !== webhookId))
    } catch (err) {
      setError(err.message)
    }
  }

  // Ver historial
  const viewHistory = async (webhookId) => {
    try {
      const response = await fetch(`${hypermatrixUrl}/api/advanced/webhooks/${webhookId}/history`)

      if (response.ok) {
        const data = await response.json()
        setHistoryModal({
          isOpen: true,
          webhookId,
          history: data.deliveries || [],
        })
      }
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[var(--color-fg-primary)] mb-2">
            🔔 Webhooks
          </h2>
          <p className="text-[var(--color-fg-secondary)]">
            Configura notificaciones automáticas a endpoints externos
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowAddModal(true)}>
          + Agregar Webhook
        </Button>
      </div>

      {error && (
        <div className="p-4 bg-[var(--color-error)] bg-opacity-10 border border-[var(--color-error)] border-opacity-30 rounded-lg text-[var(--color-error)]">
          {error}
        </div>
      )}

      {/* Lista de eventos disponibles */}
      <Card>
        <CardHeader>
          <CardTitle>📋 Eventos Disponibles</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {availableEvents.map(event => (
              <div
                key={event.name}
                className="px-3 py-2 bg-[var(--color-bg-secondary)] rounded-lg"
                title={event.description}
              >
                <span className="font-mono text-sm text-[var(--color-primary)]">{event.name}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Lista de webhooks */}
      <Card>
        <CardHeader>
          <CardTitle>🔗 Webhooks Registrados ({webhooks.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full"></div>
            </div>
          ) : webhooks.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">🔔</div>
              <h3 className="text-lg font-medium text-[var(--color-fg-primary)] mb-2">
                No hay webhooks configurados
              </h3>
              <p className="text-[var(--color-fg-secondary)] mb-4">
                Registra un webhook para recibir notificaciones de eventos
              </p>
              <Button variant="primary" onClick={() => setShowAddModal(true)}>
                + Agregar Primer Webhook
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {webhooks.map(webhook => (
                <WebhookCard
                  key={webhook.id}
                  webhook={webhook}
                  expanded={expandedWebhook === webhook.id}
                  onToggle={() => setExpandedWebhook(
                    expandedWebhook === webhook.id ? null : webhook.id
                  )}
                  onDelete={() => deleteWebhook(webhook.id)}
                  onViewHistory={() => viewHistory(webhook.id)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Estadísticas */}
      {webhooks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>📊 Resumen</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-fg-primary)]">
                  {webhooks.length}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Total</div>
              </div>
              <div className="text-center p-4 bg-[var(--color-success)] bg-opacity-10 rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-success)]">
                  {webhooks.filter(w => w.enabled).length}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Activos</div>
              </div>
              <div className="text-center p-4 bg-[var(--color-bg-secondary)] rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-fg-tertiary)]">
                  {webhooks.filter(w => !w.enabled).length}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Inactivos</div>
              </div>
              <div className="text-center p-4 bg-[var(--color-primary)] bg-opacity-10 rounded-lg">
                <div className="text-3xl font-bold text-[var(--color-primary)]">
                  {availableEvents.length}
                </div>
                <div className="text-sm text-[var(--color-fg-secondary)]">Eventos</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Modal agregar */}
      <AddWebhookModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={addWebhook}
        availableEvents={availableEvents}
      />

      {/* Modal historial */}
      <HistoryModal
        isOpen={historyModal.isOpen}
        onClose={() => setHistoryModal({ isOpen: false, webhookId: null, history: [] })}
        webhookId={historyModal.webhookId}
        history={historyModal.history}
      />
    </div>
  )
}
