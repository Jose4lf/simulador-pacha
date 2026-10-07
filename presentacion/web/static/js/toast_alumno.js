/**
 * Sistema de Notificaciones Toast para PACHA - Alumno
 * Convierte automáticamente las alertas de Flask en toasts elegantes.
 */

(function() {
    // Paleta PACHA
    const COLORES = {
        exito:   { bg: '#BFE8D1', border: '#4caf50', text: '#2c5f3d', icono: '✅' },
        error:   { bg: '#F6C6D0', border: '#e74c3c', text: '#8b2234', icono: '❌' },
        info:    { bg: '#B9DDF4', border: '#3498db', text: '#2c5f7d', icono: 'ℹ️' },
        warning: { bg: '#FFF1C7', border: '#f39c12', text: '#8b6914', icono: '⚠️' },
    };

    function crearContenedor() {
        let contenedor = document.getElementById('toast-container');
        if (!contenedor) {
            contenedor = document.createElement('div');
            contenedor.id = 'toast-container';
            contenedor.style.cssText = `
                position: fixed;
                top: 90px;
                right: 25px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 12px;
                pointer-events: none;
                max-width: 420px;
            `;
            document.body.appendChild(contenedor);
        }
        return contenedor;
    }

    window.mostrarToast = function(mensaje, tipo = 'info', duracion = 4500) {
        const contenedor = crearContenedor();
        const estilo = COLORES[tipo] || COLORES.info;

        const toast = document.createElement('div');
        toast.style.cssText = `
            background: ${estilo.bg};
            color: ${estilo.text};
            padding: 16px 22px;
            border-radius: 14px;
            box-shadow: 0 12px 35px rgba(81, 70, 83, 0.18);
            display: flex;
            align-items: center;
            gap: 14px;
            font-family: 'Patrick Hand', cursive;
            font-size: 15px;
            min-width: 280px;
            max-width: 420px;
            animation: slideInRight 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            pointer-events: auto;
            border-left: 5px solid ${estilo.border};
            line-height: 1.4;
        `;

        toast.innerHTML = `
            <span style="font-size:22px; flex-shrink:0;">${estilo.icono}</span>
            <span style="flex:1;">${mensaje}</span>
            <button onclick="cerrarToast(this)" style="
                background:none; border:none; color:${estilo.text}; 
                font-size:22px; cursor:pointer; padding:0; width:24px; height:24px;
                display:flex; align-items:center; justify-content:center;
                border-radius:50%; transition:0.2s; opacity:0.6;
            " onmouseover="this.style.opacity='1'; this.style.background='rgba(0,0,0,0.05)'"
               onmouseout="this.style.opacity='0.6'; this.style.background='none'">×</button>
        `;

        contenedor.appendChild(toast);

        // Barra de progreso
        const progress = document.createElement('div');
        progress.style.cssText = `
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            background: ${estilo.border};
            opacity: 0.4;
            border-radius: 0 0 14px 14px;
            animation: shrinkProgress ${duracion}ms linear forwards;
        `;
        toast.style.position = 'relative';
        toast.style.overflow = 'hidden';
        toast.appendChild(progress);

        if (duracion > 0) {
            setTimeout(() => cerrarToast(toast.querySelector('button')), duracion);
        }
    };

    window.cerrarToast = function(boton) {
        const toast = boton.parentElement;
        toast.style.animation = 'slideOutRight 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    };

    // Auto-convertir alertas de Flask a toasts
    document.addEventListener('DOMContentLoaded', function() {
        const alertas = document.querySelectorAll('.alert');
        alertas.forEach((alerta, index) => {
            const texto = alerta.textContent.trim();
            let tipo = 'info';
            if (alerta.classList.contains('alert-exito')) tipo = 'exito';
            else if (alerta.classList.contains('alert-error')) tipo = 'error';
            else if (alerta.classList.contains('alert-info')) tipo = 'info';

            // Limpiar iconos duplicados del texto
            const mensajeLimpio = texto.replace(/^[✅❌ℹ️⚠️🔒✍️]\s*/, '');

            // Delay escalonado para múltiples toasts
            setTimeout(() => {
                mostrarToast(mensajeLimpio, tipo);
            }, index * 200);

            alerta.remove();
        });
    });
})();

// Agregar animaciones CSS al head
(function() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(450px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            to { transform: translateX(450px); opacity: 0; }
        }
        @keyframes shrinkProgress {
            from { width: 100%; }
            to { width: 0%; }
        }
    `;
    document.head.appendChild(style);
})();