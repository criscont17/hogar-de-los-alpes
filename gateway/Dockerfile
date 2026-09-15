FROM nginx:1.28-alpine

# La configuración viaja dentro de la imagen: en la VM basta con clonar y construir,
# sin depender de montar archivos del host.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1/salud || exit 1
