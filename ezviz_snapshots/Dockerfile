# Usa imagen base con Python 3
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /config

# Copia todos los archivos del add-on al contenedor
COPY . .

# Instala las dependencias necesarias
RUN pip install requests

# Da permisos de ejecución al script principal
RUN chmod +x /config/run.sh

# Comando de inicio
CMD ["/config/run.sh"]
