import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../components/Card'
import { Button } from '../components/Button'

export default function Settings({ hypermatrixUrl, setHypermatrixUrl }) {
  const [tempUrl, setTempUrl] = useState(hypermatrixUrl)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setHypermatrixUrl(tempUrl)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[#1E1E1E] mb-2">⚙️ Configuración</h2>
        <p className="text-[#616161]">Parámetros de HyperMatrix UI</p>
      </div>

      {/* API Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>🔌 Configuración de API</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#1E1E1E] mb-2">
              URL de HyperMatrix API
            </label>
            <input
              type="text"
              value={tempUrl}
              onChange={(e) => setTempUrl(e.target.value)}
              placeholder="http://127.0.0.1:26020"
              className="w-full px-4 py-2 border border-[#E0E0E0] rounded-md focus:outline-none focus:border-[#007ACC]"
            />
            <p className="text-xs text-[#616161] mt-2">
              La URL debe estar accesible desde tu navegador. Por defecto: http://127.0.0.1:26020
            </p>
          </div>

          {saved && (
            <div className="p-3 bg-[#D4EDDA] border border-[#C3E6CB] rounded-md text-[#155724]">
              ✅ Configuración guardada correctamente
            </div>
          )}
        </CardContent>

        <CardFooter>
          <Button variant="secondary" onClick={() => setTempUrl(hypermatrixUrl)}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={handleSave}>
            Guardar
          </Button>
        </CardFooter>
      </Card>

      {/* Acerca de */}
      <Card>
        <CardHeader>
          <CardTitle>ℹ️ Acerca de HyperMatrix</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-[#616161]">
          <div>
            <strong className="text-[#1E1E1E]">Versión</strong>
            <p>v2026.1.0 - MVP Completo</p>
          </div>

          <div>
            <strong className="text-[#1E1E1E]">Desarrollado por</strong>
            <p>Claude (Anthropic) + Tacolu Servicios</p>
          </div>

          <div>
            <strong className="text-[#1E1E1E]">UI Framework</strong>
            <p>React 18 + @tacolu/design-system + Tailwind CSS</p>
          </div>

          <div>
            <strong className="text-[#1E1E1E]">Backend</strong>
            <p>FastAPI + Python 3.9+</p>
          </div>

          <div>
            <strong className="text-[#1E1E1E]">Lenguajes Soportados</strong>
            <p>Python, JavaScript, TypeScript, SQL, JSON, YAML, Markdown</p>
          </div>
        </CardContent>
      </Card>

      {/* Documentación */}
      <Card>
        <CardHeader>
          <CardTitle>📚 Documentación</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <a
            href="http://127.0.0.1:26020/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="block p-3 border border-[#E0E0E0] rounded-lg hover:bg-[#F5F5F5] transition text-[#007ACC] font-medium"
          >
            → API Documentation (Swagger UI)
          </a>

          <a
            href="https://github.com/tu-repo/hypermatrix"
            target="_blank"
            rel="noopener noreferrer"
            className="block p-3 border border-[#E0E0E0] rounded-lg hover:bg-[#F5F5F5] transition text-[#007ACC] font-medium"
          >
            → GitHub Repository
          </a>
        </CardContent>
      </Card>

      {/* Información de sistema */}
      <Card>
        <CardHeader>
          <CardTitle>💻 Información del Sistema</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-[#616161]">
          <div className="flex justify-between py-2 border-b border-[#E0E0E0]">
            <span>User Agent:</span>
            <code className="text-xs">{navigator.userAgent.split(' ').slice(0, 2).join(' ')}</code>
          </div>
          <div className="flex justify-between py-2 border-b border-[#E0E0E0]">
            <span>Navegador:</span>
            <span>Chrome/Firefox/Safari</span>
          </div>
          <div className="flex justify-between py-2">
            <span>Resolución:</span>
            <span>{window.innerWidth}x{window.innerHeight}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
