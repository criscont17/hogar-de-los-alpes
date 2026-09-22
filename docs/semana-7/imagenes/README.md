# Imágenes de las vistas

PNG exportados de los diagramas Mermaid de
[`../arquitectura-to-be-refinada.md`](../arquitectura-to-be-refinada.md). El `.mmd` de cada
uno queda junto al PNG para poder regenerarlo.

| Imagen | Vista |
|---|---|
| `cambios-antes-despues.png` | Resaltado de cambios frente al TO-BE de la Entrega 1 |
| `mapa-contextos-to-be-refinado.png` | Mapa de contextos TO-BE refinado: implementado vs. planeado |
| `saga-happy-path.png` | Vista dinámica: flujo exitoso de la saga, desde el cliente externo |
| `saga-compensacion.png` | Vista dinámica: compensación en orden inverso |
| `topologia-despliegue.png` | Vista de despliegue: contenedores, bases y puertos |

## Regenerar

Requiere Node y un Chrome o Edge instalado (no hace falta Graphviz):

```bash
# Desde docs/semana-7, con la ruta de su navegador
echo '{"executablePath": "C:/Program Files/Google/Chrome/Application/chrome.exe", "args": ["--no-sandbox"]}' > imagenes/puppeteer.json

for d in cambios-antes-despues mapa-contextos-to-be-refinado saga-happy-path saga-compensacion topologia-despliegue; do
  PUPPETEER_SKIP_DOWNLOAD=true npx -y @mermaid-js/mermaid-cli@11 \
    -i "imagenes/$d.mmd" -o "imagenes/$d.png" -b white -s 2 -p imagenes/puppeteer.json
done
rm imagenes/puppeteer.json
```

> El mapa de contextos en ContextMapper DSL
> ([`../hda-context-map-to-be-refinado.cml`](../hda-context-map-to-be-refinado.cml)) genera su
> propio diagrama desde el plugin de VS Code, pero eso requiere **Graphviz** instalado. El PNG
> de esta carpeta es la versión Mermaid del mismo mapa.
