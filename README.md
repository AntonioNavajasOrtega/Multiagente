# Sistema Multiagente para la Logística (AutoGen v0.4)

**Máster Universitario en Ingeniería del Software e Inteligencia Artificial — Curso 2025/26**  
*Sistemas Multiagente — Antonio Navajas Ortega*

Simulación multiagente avanzada basada en el **Modelo de Actores** utilizando **Microsoft AutoGen v0.4**. El sistema modela la logística de un centro mediante agentes asíncronos desacoplados que se comunican exclusivamente por paso de mensajes fuertemente tipados.

---

## Arquitectura Moderna (Actor Model)

Esta implementación utiliza la arquitectura **v0.4** de AutoGen:

1.  **Agentes como Actores (`RoutedAgent`)**: Cada entidad (Vehículo, Depósito, Cliente, Coordinador) es un actor independiente con su propio buzón de mensajes.
2.  **Mensajería Asíncrona**: La comunicación se realiza mediante objetos `@dataclass` (definidos en `agents/messages.py`) procesados asíncronamente por manejadores `@message_handler`.
3.  **Runtime Distribuible**: El sistema utiliza un `AgentRuntime` que orquesta la entrega de mensajes, permitiendo una separación total entre la lógica del agente y la infraestructura.

---

## Estructura del Proyecto

```
logistics_mas/
│
├── agents/                        ← Agentes v0.4 (Modelo de Actores)
│   ├── messages.py                #   Protocolo formal (Dataclasses de mensajes)
│   ├── depot_agent.py             #   DepotAgent (RoutedAgent reactivo)
│   ├── client_agent.py            #   ClientAgent (RoutedAgent reactivo)
│   ├── vehicle_agent.py           #   VehicleAgent (Actor proactivo)
│   ├── coordinator_agent.py       #   CoordinatorAgent (Coordinador asíncrono)
│   └── rl_vehicle_agent.py        #   RLVehicleAgent (Q-Learning asíncrono)
│
├── core/                          ← Lógica de dominio (Grid, A*, Métricas)
│   ├── entities.py                #   Definición de Depot, Client, Vehicle y Cargo
│   ├── environment.py             #   Gestión del Grid y costes de tráfico
│   ├── metrics.py                 #   Recolección de estadísticas de simulación
│   └── pathfinding.py             #   Algoritmo A* adaptado a 8 direcciones
│
├── scenarios/                     ← Motores de simulación asíncronos
│   ├── base_scenario.py           #   Orquestador del AgentRuntime v0.4 (Padre)
│   ├── simple_scenario.py         #   Escenario 1: Independiente
│   ├── coordinated_scenario.py    #   Escenario 2: Coordinación via Actores
│   └── rl_scenario.py             #   Escenario 3: Aprendizaje asíncrono
│
├── simulation/                    ← Visualización (Opcional)
│   └── visualizer.py              #   Renderizado ASCII del entorno y estados
│
├── config/                        ← Configuraciones de escenario (JSON)
│   ├── small_simple.json          #   6x6 - Test rápido
│   ├── large_sparse.json          #   20x20 - Mapa extenso
│   └── congested.json             #   12x12 - Alta penalización de tráfico
│
├── results/                       ← Reportes de salida de experimentos
│
├── tools/                         ← Utilidades de soporte
│   ├── env_generator.py           #   Generador de configuraciones
│   └── run_all_experiments.py     #   Automatización de las 9 pruebas
│
├── main.py                        ← Punto de entrada CLI (Asyncio loop)
└── requirements.txt               ← Dependencias de AutoGen v0.4
```

---

## Protocolo de Mensajes (`agents/messages.py`)

Los agentes interactúan mediante los siguientes mensajes tipados:

| Mensaje | Origen | Destino | Propósito |
|---|---|---|---|
| `PickupRequest` | Vehículo | Depósito | Solicitar carga de unidades |
| `PickupResponse` | Depósito | Vehículo | Confirmar/Denegar carga autorizada |
| `DeliveryMessage` | Vehículo | Cliente | Notificar entrega en destino |
| `DeliveryAck` | Cliente | Vehículo | Confirmar recepción de pedido |
| `StatusReport` | Vehículo | Coordinador | Informar posición y estado (idle/en ruta) |
| `Assignment` | Coordinador | Vehículo | Asignar nuevo par Depósito-Cliente |
| `DemandAnnouncement` | Cliente | Todos | Anunciar demanda inicial |

---

## Instalación y Uso

### Requisitos
- Python 3.10+
- `autogen-core==0.4.*`

```bash
pip install -r requirements.txt
```

### Ejecución de Experimentos

Para facilitar la evaluación de los tres escenarios en diferentes configuraciones, se ha incluido un script de automatización que ejecuta las 9 combinaciones posibles:

```bash
python tools/run_all_experiments.py
```

Este script:
1.  Utiliza los escenarios pre-configurados en `config/`.
2.  Ejecuta cada escenario en modo `simple`, `coordinated` y `rl`.
3.  Gestiona el pre-entrenamiento de RL (20 episodios) automáticamente.
4.  Genera reportes JSON detallados en `results/`.

### Generación de Escenarios (Subcomando `generate`)

El sistema permite generar entornos personalizados mediante una gran variedad de parámetros para probar diferentes condiciones logísticas.

```bash
# Ejemplo: Generar un mapa grande con mucha penalización de tráfico y alta demanda
python main.py generate \
  --output config/mi_escenario.json \
  --rows 15 --cols 15 \
  --depots 4 \
  --clients 10 \
  --vehicles 5 \
  --traffic 20 --traffic-penalty 3.5 \
  --depot-inventory 100 \
  --client-demand 25 \
  --seed 123
```

**Parámetros principales:**
- `--rows`, `--cols`: Dimensiones del grid.
- `--depots`, `--clients`, `--vehicles`: Cantidad de entidades de cada tipo.
- `--obstacles`, `--traffic`: Número de celdas de bloqueo y celdas con sobrecoste.
- `--traffic-penalty`: Multiplicador de coste para las celdas de tráfico (ej: `2.0` significa coste doble).
- `--depot-inventory`: Unidades disponibles en cada depósito al inicio.
- `--client-demand`: Unidades que cada cliente solicita de los depósitos.
- `--vehicle-capacity`: Carga máxima que puede transportar un vehículo simultáneamente.
- `--seed`: Semilla aleatoria para asegurar que los mapas sean reproducibles.

### Ejecución de Simulaciones (Subcomando `simulate`)

Una vez generado el escenario, se puede ejecutar en cualquiera de los tres modos disponibles (`simple`, `coordinated`, `rl`):

```bash
# Ejecutar Simulación con visualización ASCII en tiempo real
python main.py simulate --scenario config/mi_escenario.json --mode coordinated --verbose --output results/res_final.json
```

> **Nota**: El modo `--verbose` muestra una visualización ASCII en tiempo real del grid, permitiendo observar el comportamiento de los agentes y la resolución de rutas.

---

## Escenarios Detallados

1.  **Simple**: Sin coordinación central. Los vehículos buscan carga de forma independiente basándose en la disponibilidad local de los depósitos.
2.  **Coordinado**: Un `CoordinatorAgent` centraliza las peticiones, asignando tareas a los vehículos `IDLE` para optimizar la distribución.
3.  **Con Aprendizaje (RL)**: Los agentes utilizan **Q-Learning** para aprender rutas óptimas. El entrenamiento incluye recompensas ponderadas por la **prioridad del cliente** (Alta, Media, Baja), incentivando la entrega de pedidos críticos.

---

## Uso de Inteligencia Artificial Generativa

Para el desarrollo de este proyecto se ha utilizado **IA Generativa (Anthropic Claude / Google Gemini)** asistida por el entorno de desarrollo agentico **Antigravity**.

**Áreas de aplicación:**
- **Refactorización Arquitectónica**: Migración del código base de AutoGen v0.2 (basado en hilos/chats) a AutoGen v0.4 (basado en el Modelo de Actores asíncrono).
- **Lógica de Aprendizaje por Refuerzo**: Implementación de la tabla Q y la política epsilon-greedy dentro de la estructura de agentes asíncronos.
- **Automatización**: Generación del script de gestión de experimentos y diversificación de escenarios JSON.
- **Documentación y Calidad**: Estructuración del README y revisión de la consistencia en el protocolo de mensajes.

---

## Decisiones de Diseño Académico

1.  **Fidelidad al Modelo de Actores**: Se ha evitado el uso de variables globales o memoria compartida entre agentes. Toda solicitud de carga o entrega es una transacción asíncrona Request/Response.
2.  **Sincronización por Ticks**: Aunque AutoGen v0.4 es asíncrono por naturaleza, el motor de la simulación (`base_scenario.py`) actúa como un orquestador que envía señales de sincronización para mantener la coherencia del grid discreto.
3.  **Desacoplamiento**: Los agentes solo conocen los `AgentId` de sus interlocutores, cumpliendo con los principios de transparencia de localización de los sistemas multiagente modernos.

Sobre los resultados:
Muchas veces se llega a las iteraciones máximas porque alguna entrega es inaccesible.