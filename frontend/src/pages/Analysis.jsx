import { Card, CardHeader, CardTitle, CardContent } from '../components/Card'

export default function Analysis() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-[#1E1E1E] mb-2">🔬 Análisis Avanzado</h2>
        <p className="text-[#616161]">Funcionalidades avanzadas de HyperMatrix</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Busqueda Natural */}
        <Card hoverable>
          <CardHeader>
            <CardTitle>🔍 Búsqueda Natural</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#616161] mb-3">
              Encuentra funciones, clases o fragmentos de código con descripción natural.
            </p>
            <input
              type="text"
              placeholder="Ej: parsea archivos JSON"
              className="w-full px-3 py-2 text-sm border border-[#E0E0E0] rounded-md"
            />
            <button className="mt-3 w-full py-2 bg-[#007ACC] text-white rounded-md hover:bg-[#0E6BBF] transition">
              Buscar
            </button>
          </CardContent>
        </Card>

        {/* Código Muerto */}
        <Card hoverable>
          <CardHeader>
            <CardTitle>💀 Código Muerto</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#616161] mb-3">
              Detecta funciones, variables y clases no utilizadas.
            </p>
            <select className="w-full px-3 py-2 text-sm border border-[#E0E0E0] rounded-md">
              <option>Selecciona un proyecto...</option>
              <option>Mi Proyecto</option>
            </select>
            <button className="mt-3 w-full py-2 bg-[#007ACC] text-white rounded-md hover:bg-[#0E6BBF] transition">
              Analizar
            </button>
          </CardContent>
        </Card>

        {/* Impacto de cambios */}
        <Card hoverable>
          <CardHeader>
            <CardTitle>⚡ Análisis de Impacto</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#616161] mb-3">
              Calcula el impacto de modificar o eliminar un archivo.
            </p>
            <input
              type="text"
              placeholder="Ruta del archivo..."
              className="w-full px-3 py-2 text-sm border border-[#E0E0E0] rounded-md"
            />
            <button className="mt-3 w-full py-2 bg-[#007ACC] text-white rounded-md hover:bg-[#0E6BBF] transition">
              Calcular Impacto
            </button>
          </CardContent>
        </Card>

        {/* Similitud semántica */}
        <Card hoverable>
          <CardHeader>
            <CardTitle>🧠 Similitud Semántica</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#616161] mb-3">
              Encuentra funciones equivalentes con nombres diferentes.
            </p>
            <input
              type="text"
              placeholder="Función a comparar..."
              className="w-full px-3 py-2 text-sm border border-[#E0E0E0] rounded-md"
            />
            <button className="mt-3 w-full py-2 bg-[#007ACC] text-white rounded-md hover:bg-[#0E6BBF] transition">
              Comparar
            </button>
          </CardContent>
        </Card>
      </div>

      {/* Información */}
      <Card>
        <CardHeader>
          <CardTitle>📚 Funcionalidades Disponibles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="p-3 bg-[#F5F5F5] rounded-lg">
              <h4 className="font-semibold text-[#1E1E1E] mb-1">Natural Search</h4>
              <p className="text-[#616161]">Busca en lenguaje natural sin sintaxis especial</p>
            </div>

            <div className="p-3 bg-[#F5F5F5] rounded-lg">
              <h4 className="font-semibold text-[#1E1E1E] mb-1">Dead Code Detection</h4>
              <p className="text-[#616161]">Identifica código no utilizado automáticamente</p>
            </div>

            <div className="p-3 bg-[#F5F5F5] rounded-lg">
              <h4 className="font-semibold text-[#1E1E1E] mb-1">Impact Analysis</h4>
              <p className="text-[#616161]">Calcula dependencias cruzadas y riesgos</p>
            </div>

            <div className="p-3 bg-[#F5F5F5] rounded-lg">
              <h4 className="font-semibold text-[#1E1E1E] mb-1">Semantic Similarity</h4>
              <p className="text-[#616161]">Encuentra funciones equivalentes</p>
            </div>

            <div className="p-3 bg-[#F5F5F5] rounded-lg">
              <h4 className="font-semibold text-[#1E1E1E] mb-1">Clone Detection</h4>
              <p className="text-[#616161]">Detecta fragmentos duplicados exactos</p>
            </div>

            <div className="p-3 bg-[#F5F5F5] rounded-lg">
              <h4 className="font-semibold text-[#1E1E1E] mb-1">Quality Analysis</h4>
              <p className="text-[#616161]">Evalúa documentación y tipado</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
