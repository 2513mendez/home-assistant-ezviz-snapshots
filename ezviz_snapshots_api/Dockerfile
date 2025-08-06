FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /config

# Copiar los archivos del addon al contenedor
COPY . .

# Asegurar permisos de ejecución para el script
RUN chmod +x /config/run.sh

# Convertir el script a formato UNIX (evita errores CRLF si se edita en Windows)
RUN apt-get update && apt-get install -y dos2unix && dos2unix /config/run.sh && apt-get purge -y dos2unix && apt-get autoremove -y

# Instalar dependencias necesarias
RUN pip install requests

# Ejecutar el script al iniciar el contenedor
CMD ["/bin/sh", "/config/run.sh"]
