# EZVIZ Snapshots

Este add-on de Home Assistant permite obtener snapshots de cámaras EZVIZ usando la API oficial. Los snapshots se guardan automáticamente en `/config/www/snapshots`.

## Configuración

Desde la interfaz de Home Assistant podrás configurar:

- `app_key`: tu App Key oficial de EZVIZ
- `app_secret`: tu App Secret de EZVIZ
- `token`: opcional; si no lo defines, se genera automáticamente con `app_key` y `app_secret`
- `camaras`: lista de cámaras con nombre y número de serie (deviceSerial)

### Ejemplo de configuración en la interfaz:

```yaml
app_key: "tu_app_key"
app_secret: "tu_app_secret"
token: ""
camaras:
  - nombre: "salon"
    serial: "BF2XXXXXXX"
  - nombre: "entrada"
    serial: "BF3XXXXXXX"
