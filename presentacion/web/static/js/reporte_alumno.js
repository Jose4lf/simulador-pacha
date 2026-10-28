// Configuración global de Chart.js
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Patrick Hand', cursive";
  Chart.defaults.color = "#514653";
}

// Variables globales para no duplicar gráficos al cambiar de pestaña
let chart1, chart2, chart3, chart4;

// 1. Obtener datos del HTML
function obtenerDatos() {
  try {
    const script = document.getElementById("datos-reporte");
    return JSON.parse(script.textContent);
  } catch (e) {
    console.error("Error cargando datos:", e);
    return { marcas: [], anio: 0 };
  }
}

// 2. Navegación de Pestañas Principales
window.cambiarTabReporte = function (tabId, boton) {
  document.querySelectorAll(".tab-reporte").forEach((btn) => btn.classList.remove("activo"));
  boton.classList.add("activo");

  document.querySelectorAll(".tab-reporte-contenido").forEach((div) => div.classList.remove("activo"));
  const contenido = document.getElementById("tab-" + tabId);
  if (contenido) contenido.classList.add("activo");
};

// 3. Navegación de Sub-Pestañas (Gráficos)
window.cambiarSubTab = function (subTabId, boton) {
  document.querySelectorAll(".sub-tab-reporte").forEach((btn) => btn.classList.remove("activo"));
  boton.classList.add("activo");

  document.querySelectorAll(".sub-tab-contenido").forEach((div) => div.classList.remove("activo"));
  const subtab = document.getElementById("subtab-" + subTabId);
  if (subtab) subtab.classList.add("activo");

  // Dibujar el gráfico correspondiente al abrir la pestaña
  if (subTabId === "grafico1") dibujarGrafico1();
  if (subTabId === "grafico2") dibujarGrafico2();
  if (subTabId === "grafico3") dibujarGrafico3();
  if (subTabId === "grafico4") dibujarGrafico4();
};

// 4. Función para pestañas en proceso
window.enProceso = function (event) {
  if (event) event.preventDefault();
  if (typeof mostrarToast === "function") {
    mostrarToast("🚧 Función en proceso. Disponible próximamente.", "info");
  } else {
    alert("🚧 Función en proceso.");
  }
};

// ============================================================
// FUNCIONES DE LOS GRÁFICOS (Dinámicos)
// ============================================================
function dibujarGrafico1() {
  const ctx = document.getElementById("grafico-1");
  if (!ctx || chart1) return;
  
  const datos = obtenerDatos();
  const marcas = datos.marcas || [];

  chart1 = new Chart(ctx, {
    type: "bar",
    data: {
      labels: marcas.map((m) => m.marca),
      datasets: [
        { label: "Ventas", data: marcas.map((m) => m.unidades_vendidas || 0), backgroundColor: "#B9DDF4", borderRadius: 6 },
        { label: "Inventarios", data: marcas.map((m) => m.inventario || 0), backgroundColor: "#514653", borderRadius: 6 },
      ],
    },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false },
  });
}

function dibujarGrafico2() {
  const ctx = document.getElementById("grafico-2");
  if (!ctx || chart2) return;

  const datos = obtenerDatos();
  const marcas = datos.marcas || [];

  chart2 = new Chart(ctx, {
    type: "bar",
    data: {
      labels: marcas.map((m) => m.marca),
      datasets: [
        { label: "Precio Final", data: marcas.map((m) => m.precio_final || 0), backgroundColor: "#B9DDF4", borderRadius: 6 },
        { label: "Contribución Bruta", data: marcas.map((m) => m.contribucion_bruta_marketing || 0), backgroundColor: "#BFE8D1", borderRadius: 6 },
      ],
    },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false },
  });
}

function dibujarGrafico3() {
  const ctx = document.getElementById("grafico-3");
  if (!ctx || chart3) return;

  const datos = obtenerDatos();
  const marcas = datos.marcas || [];

  chart3 = new Chart(ctx, {
    type: "bar",
    data: {
      labels: marcas.map((m) => m.marca),
      datasets: [
        { label: "Publicidad", data: marcas.map((m) => m.publicidad || 0), backgroundColor: "#BFE8D1", borderRadius: 6 },
        { label: "Costo Productos", data: marcas.map((m) => m.costo_productos_vendidos || 0), backgroundColor: "#B9DDF4", borderRadius: 6 },
        { label: "Costo Inventario", data: marcas.map((m) => m.costo_inventario || 0), backgroundColor: "#F6C6D0", borderRadius: 6 },
      ],
    },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false },
  });
}

function dibujarGrafico4() {
  const ctx = document.getElementById("grafico-4");
  if (!ctx || chart4) return;

  const datos = obtenerDatos();
  const marcas = datos.marcas || [];

  chart4 = new Chart(ctx, {
    type: "bar",
    data: {
      labels: marcas.map((m) => m.marca),
      datasets: [
        { label: "Porción de Mercado (%)", data: marcas.map((m) => m.porcion_mercado || 0), backgroundColor: "#C9B6E4", borderRadius: 6 },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}
window.cambiarTabReporte = function (tabId, boton) {
  // 1. Quitar el estado activo de todos los botones
  document.querySelectorAll(".tab-reporte").forEach((btn) => {
    btn.classList.remove("activo");
    btn.style.background = "#8b1c4e"; 
    btn.style.color = "white"; 
    btn.style.border = "none";
  });
  
  // 2. Poner el botón actual como activo
  boton.classList.add("activo");
  boton.style.background = "#fff"; 
  boton.style.color = "#514653"; 
  boton.style.border = "1px solid #ddd"; 
  boton.style.borderBottom = "none";

  // 3. Ocultar todos los contenidos
  document.querySelectorAll(".tab-reporte-contenido").forEach((div) => div.classList.remove("activo"));
  
  // 4. Mostrar el contenido de la pestaña seleccionada
  const contenido = document.getElementById("tab-" + tabId);
  if (contenido) contenido.classList.add("activo");
};