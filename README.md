# VMN's Custom Add-ons (Home Assistant)

Repositorio de add-ons para Home Assistant.

[![Añadir repositorio a mi Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2F2513Mendez%2Fhome-assistant-ezviz-snapshots)

## Add-ons

### [EZVIZ Snapshots API/MQTT (Multi-account)](./ezviz_snapshots_api)

Para cámaras EZVIZ **sin RTSP**: pide snapshots a la API cloud de EZVIZ y los
publica por MQTT. Con MQTT Discovery crea automáticamente entidades
`image.ezviz_<slug>` en Home Assistant. Multi-cuenta, modo servicio con
intervalo configurable, o una pasada para lanzarlo por automatización.

Documentación completa en el [README del add-on](./ezviz_snapshots_api/README.md)
y cambios en el [CHANGELOG](./ezviz_snapshots_api/CHANGELOG.md).
