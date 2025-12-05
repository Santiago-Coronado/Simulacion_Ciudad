# Simulación_Ciudad
## Proyecto de Modelación de sistemas multiagentes con gráficas computacionales (Gpo 302)
### Miembros del Equipo
- Santiago Coronado Hernández A01785558
- Luis Emilio Veledíaz Flores A01029829
### Profesores
- Octavio Navarro Hinojosa
- Gilberto Echeverría Furió

## Contexto del Proyecto
La movilidad urbana, se define como la habilidad de transportarse de un lugar a otro1 y es fundamental para el desarrollo económico y social y la calidad de vida de los habitantes de una ciudad. Desde hace un tiempo, asociar la movilidad con el uso del automóvil ha sido un signo distintivo de progreso. Sin embargo, esta asociación ya no es posible hoy. El crecimiento y uso indiscriminado del automóvil —que fomenta políticas públicas erróneamente asociadas con la movilidad sostenible—genera efectos negativos enormes en los niveles económico, ambiental y social en México.

Durante las últimas décadas, ha existido una tendencia alarmante de un incremento en el uso de automóviles en México. Los Kilómetros-Auto Recorridos (VKT por sus siglas en Inglés) se han triplicado, de 106 millones en 1990, a 339 millones en 2010. Ésto se correlaciona simultáneamente con un incremento en los impactos negativos asociados a los autos, como el smog, accidentes, enfermedades y congestión vehicular2.

Para que México pueda estar entre las economías más grandes del mundo, es necesario mejorar la movilidad en sus ciudades, lo que es crítico para las actividades económicas y la calidad de vida de millones de personas.

Este reto te permitirá contribuir a la solución del problema de movilidad urbana en México, mediante un enfoque que reduzca la congestión vehicular al simular de manera gráfica el tráfico, representando la salida de un sistema multi agentes.

## Descripción del Proyecto
El reto consiste en proponer una solución al problema de movilidad urbana en México, mediante un enfoque que reduzca la congestión vehicular al simular de manera gráfica el tráfico, representando la salida de un sistema multi agentes.

Imagina una solución que implemente una de las siguientes estrategias de ejemplo:

- Controlar y asignar los espacios de estacionamiento disponible en una zona de la ciudad, evitando así que los autos estén dando vueltas para encontrar estacionamiento.
- Compartir tu vehículo con otras personas. Aumentando la ocupación de los vehículos, reduciría el número de vehículos en las calles.
- Tomar las rutas menos congestionadas. Quizás no más las cortas, pero las rutas con menos tráfico. Más movilidad, menos consumo, menos contaminación.
- Que permita a los semáforos coordinar sus tiempos y, así, reducir la congestión de un cruce. O, quizás, indicar en qué momento un vehículo va a cruzar una intersección y que de esta forma, el semáforo puede determinar el momento y duración de la luz verde.

## Etapas
### Etapa 1.1: Modelación de agentes
¿Cómo se modela la circulación de un automóvil en un ambiente urbano?
¿Cómo se modela la circulación de un grupo de automóviles en un ambiente urbano?

### Etapa 1.2: Modelación gráfica en tres dimensiones
¿Cómo se diseña un sistema 3D para visualizar los datos de movimiento de los automóviles, resultado de la simulación?

### Etapa 2.1: Interacción entre agentes
¿Cómo negocian las personas en México el espacio que ocupa su automóvil, y cómo se puede modelar esta negociación?
¿Cómo se diseña e implementa un sistema que simule la ocurrencia de estos fenómenos para varios automovilistas?

### Etapa 2.2: Animación gráfica en tres dimensiones
¿Cómo se implementa un sistema 3D para visualizar los datos de movimiento de los automóviles, resultado de la simulación?

## Como correr el proyecto
### Clona el Repositorio
```bash
git clone git@github.com:Santiago-Coronado/Simulacion_Ciudad.git
```

### Instala dependencias de proyecto (Dentro de la carpeta Simulacion)
```bash
npm install
```

### Crea el entorno virtual (En la raíz del Repositorio)

```bash
python -m venv .agents
```
### Activa el entorno virtual

```bash
./.agents/Scripts/activate
```
### Instala dependencias para correr el proyecto

```bash
pip install -U "mesa[all]"
pip install flask flask_cors
```
### (Opción 1) Ejecuta la simulación de Solara (Dentro de la carpeta Server\trafficBase)

```bash
solara run server.py
```

### (Opción 2) Ejecuta la simulación de Flask 
(Dentro de la carpeta Server\trafficBase)
```bash
python .\flask_traffic_server.py
```

(Dentro de la carpeta Simulacion)
```bash
npx vite
```


