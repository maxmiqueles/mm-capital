# MM Capital · Fondos

Página web para ejecutivos de venta de inversiones. Guía la reunión con el cliente de principio a cierre:

1. **Diagnóstico**: datos del cliente (en pesos) y perfil del inversionista. Sugiere un fondo.
2. **Propuesta**: ficha del fondo, argumentos, objeciones con respuesta, cuánto cuesta esperar y prueba de crisis.
3. **Respaldo**: 10 años de datos frente a fondos de referencia (QQQ, SCHD, Fidelity Contrafund, Vanguard Wellington y otros).
4. **Cierre**: propuesta personalizada de una hoja, lista para copiar al correo o guardar como PDF.

**Ver la página:** https://maxmiqueles.github.io/mm-capital/

> Proyecto demostrativo de portafolio profesional. MM Capital no es una administradora real, los resultados de los fondos son simulaciones históricas (backtest) y nada de esto es una recomendación de inversión.

## Los cuatro fondos

Se arman con reglas fijas sobre 64 acciones grandes de EE.UU., usando solo información disponible en cada fecha de rebalanceo:

| Fondo | Regla |
|---|---|
| MM Tendencia | 12 acciones con mayor momentum 12-1, máximo 4 por sector |
| MM Dividendos Crecientes | Dividend yield + crecimiento del dividendo a 5 años, 12 acciones |
| MM Defensivo | 12 acciones menos volátiles, ponderadas por volatilidad inversa |
| MM Balanceado | 60% acciones (momentum + baja volatilidad), 25% bonos del Tesoro, 15% oro |

Comisión de 0,75% anual y costos de transacción de 0,10% ya descontados.

## Cómo funciona

- `build.py` descarga precios y dividendos (Yahoo Finance), corre el backtest, calcula métricas y escribe `index.html` a partir de `template.html`.
- `.github/workflows/actualizar.yml` corre ese script cada día hábil y publica la página actualizada.

```bash
pip install -r requirements.txt
python build.py
```

## Limitaciones

- Backtest, no rentabilidad real.
- Sesgo de supervivencia: el universo son empresas grandes de hoy.
- Proyecciones en pesos con tipo de cambio constante; tasa de depósito a plazo e inflación son supuestos editables.
