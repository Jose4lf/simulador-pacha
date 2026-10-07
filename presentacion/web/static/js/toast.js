/**
 * Sistema de notificaciones Toast para PACHA
 */
(function() {
    // Crear contenedor de toasts si no existe
    function crearContenedor() {
        let contenedor = document.getElementById('toast-container');
        if (!contenedor) {
            contenedor = document.createElement('div');
            contenedor.id = 'toast-container';
            contenedor.className = 'toast-container';
            document.body.appendChild(contenedor);
        }
        return contenedor;
    }

    // Mostrar un toast
    window.mostrarToast = function(mensaje, tipo = 'info', duracion = 4000) {
        const contenedor = crearContenedor();

        const iconos = {
            'exito': '✅',
            'error': '❌',
            'info': 'ℹ️',
            'warning': '⚠️'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${tipo}`;
        toast.innerHTML = `
            <span class="toast-icono">${iconos[tipo] || 'ℹ️'}</span>
            <span class="toast-mensaje">${mensaje}</span>
            <button class="toast-cerrar" onclick="this.parentElement.remove()">×</button>
        `;

        contenedor.appendChild(toast);

        // Auto-cerrar
        if (duracion > 0) {
            setTimeout(() => {
                toast.classList.add('toast-saliendo');
                setTimeout(() => toast.remove(), 300);
            }, duracion);
        }
    };

    // Auto-convertir mensajes flash de Flask a toasts
    document.addEventListener('DOMContentLoaded', function() {
        const alertas = document.querySelectorAll('.alert');
        alertas.forEach(alerta => {
            const texto = alerta.textContent.trim();
            let tipo = 'info';

            if (alerta.classList.contains('alert-exito')) tipo = 'exito';
            else if (alerta.classList.contains('alert-error')) tipo = 'error';

            // Remover el texto del ícono si existe
            const mensajeLimpio = texto.replace(/^[✅❌ℹ️⚠️]\s*/, '');

            mostrarToast(mensajeLimpio, tipo);
            alerta.remove();
        });
    });
})();