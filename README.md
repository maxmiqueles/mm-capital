# MM Capital · Portafolios a medida

Página web para que un ejecutivo de inversiones la use junto a su cliente. Guía la reunión de principio a cierre:

1. **Inicio**: explica en simple qué va a pasar.
2. **Diagnóstico**: datos del cliente (en pesos) y 9 preguntas simples. Define un perfil de riesgo entre cinco niveles.
3. **Propuesta**: un portafolio a medida que combina fondos de acciones, renta fija y oro. Incluye argumentos, objeciones con respuesta, cuánto cuesta esperar y prueba de crisis.
4. **Respaldo**: 10 años de datos frente a fondos de referencia.
5. **Cierre**: propuesta personalizada de una hoja, lista para copiar al correo o guardar como PDF.

**Ver la página:** https://maxmiqueles.github.io/mm-capital/

> Proyecto demostrativo de portafolio profesional. MM Capital no es una administradora real, los resultados son simulaciones históricas (backtest) y nada de esto es una recomendación de inversión.

## Universo

- Acciones del S&P 500 (cada una elegible solo desde la fecha en que entró al índice).
- Acciones chilenas del IPSA.
- ETF globales de los más grandes (VTI, VEA, VWO, QQQ, VTV).
- Bonos del Tesoro de EE.UU. a tres plazos (SHY, IEF, TLT) y oro (GLD).

## Los fondos que se combinan

| Fondo | Regla |
|---|---|
| MM Tendencia | 25 acciones del S&P 500 con mayor momentum 12-1, máximo 5 por sector |
| MM Dividendos Crecientes | Dividend yield + crecimiento del dividendo a 5 años, 25 acciones |
| MM Defensivo | 25 acciones menos volátiles, ponderadas por volatilidad inversa |
| MM Global | Cinco ETF ponderados por volatilidad inversa |
| MM Chile | 10 acciones del IPSA por momentum y baja volatilidad |
| MM Tesoro | 50% SHY, 35% IEF, 15% TLT |

El portafolio de cada cliente reparte el capital entre acciones, renta fija y oro según su perfil (de 20% a 95% en acciones) y ajusta la parte de acciones según sus respuestas.

## Cómo funciona

- `build.py` descarga precios y dividendos (Yahoo Finance), corre el backtest, calcula métricas y escribe `index.html` a partir de `template.html`.
- `sp500.csv` es la lista de acciones del S&P 500 con su sector y fecha de ingreso al índice.
- `.github/workflows/actualizar.yml` corre el script cada día hábil y publica la página actualizada.

```bash
pip install -r requirements.txt
python build.py
```

## Limitaciones

- Backtest, no rentabilidad real.
- Sesgo de supervivencia: no están las empresas que salieron de los índices.
- La lista del IPSA es fija y puede diferir de la composición oficial vigente.
- Proyecciones en pesos con tipo de cambio constante; tasa de depósito a plazo e inflación son supuestos editables.
