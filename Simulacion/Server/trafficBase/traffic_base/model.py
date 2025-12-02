from random import random, choice
from mesa import Model
from mesa.discrete_space import OrthogonalMooreGrid
from .agent import *
import os
import json


class CityModel(Model):
    """
    Creates a model based on a city map.

    Args:
        N: Number of agents in the simulation
        seed: Random seed for the model
    """

    def __init__(self, N, seed=42):
        super().__init__(seed=seed)
        
        # INICIALIZACIÓN: Resetear contador de pasos
        # Mesa lo inicializa automáticamente, pero lo forzamos a 0
        self.steps = 0

        # Load the map dictionary. The dictionary maps the characters in the map file to the corresponding agent.
        dataDictionary = json.load(open("city_files/mapDictionary.json"))

        self.num_agents = N
        # ALMACENAMIENTO: Listas para rastrear elementos específicos del modelo
        self.traffic_lights = []  # Semáforos
        self.destinations = []    # Destinos donde van los autos
        self.spawn_points = []    # Puntos donde aparecen nuevos autos
        self.cars_spawned = 0     # Contador total de autos creados
        self.max_cars = N         # Límite máximo de autos simultáneos
        self.cars = []            # Lista de autos activos en la simulación

        # Load the map file. The map file is a text file where each character represents an agent.
        with open("city_files/2024_base.txt") as baseFile:
            lines = baseFile.readlines()
            # Obtener ancho (caracteres por línea) y alto (número de líneas)
            self.width = len(lines[0].strip())
            self.height = len(lines)

            # Crear grid con capacidad para múltiples agentes por celda
            self.grid = OrthogonalMooreGrid(
                [self.width, self.height], capacity=100, torus=False
            )

            # PARSING DEL MAPA: Iterar cada carácter del archivo .txt
            # Las coordenadas se invierten en Y para que (0,0) sea esquina inferior izquierda
            for r, row in enumerate(lines):
                for c, col in enumerate(row.strip()):

                    cell = self.grid[(c, self.height - r - 1)]

                    # CARRETERAS: Caracteres v,^,>,<,%,&,_,= representan direcciones
                    if col in ["v", "^", ">", "<", "%", "&", "_", "="]:
                        agent = Road(f"road_{r}_{c}", self, cell, dataDictionary[col])

                    # SEMÁFOROS: S (rojo inicial) o s (verde inicial)
                    elif col in ["S", "s"]:
                        # Estado inicial: False=rojo (S), True=verde (s)
                        initial_state = False if col == "S" else True
                        # Tiempo de cambio viene del diccionario
                        change_time = int(dataDictionary[col])
                        agent = Traffic_Light(
                            f"traffic_{r}_{c}",
                            self,
                            cell,
                            initial_state,
                            change_time,
                        )
                        # Guardar referencia para acceso rápido
                        self.traffic_lights.append(agent)

                    # OBSTÁCULOS: # representa edificios/objetos fijos
                    elif col == "#":
                        agent = Obstacle(f"obstacle_{r}_{c}", self, cell)

                    # DESTINOS: D es donde deben llegar los autos
                    elif col == "D":
                        agent = Destination(f"dest_{r}_{c}", self, cell)
                        # Guardar referencia para asignar destinos a nuevos autos
                        self.destinations.append(agent)
        
        # PUNTOS DE SPAWN: Esquinas del mapa donde aparecen nuevos autos
        self.spawn_points = [
            (0, self.height - 1),                # Esquina superior izquierda
            (self.width - 1, self.height - 1),   # Esquina superior derecha
            (0, 0),                              # Esquina inferior izquierda
            (self.width - 1, 0),                 # Esquina inferior derecha
        ]

        self.running = True

    # ============================================================
    # GENERACIÓN DE AUTOS
    # DESCRIPCIÓN: Crea nuevos autos en los puntos de spawn
    # Se llama cada 20 pasos para generar tráfico gradualmente
    # ============================================================
    def spawn_cars(self):
        """Genera autos en los puntos de inicio cada 20 pasos"""
        spawned = 0
        # Iterar sobre cada punto de spawn
        for pos in self.spawn_points:
            cell = self.grid[pos]
            
            # VALIDACIÓN: Solo spawnear si hay una calle en este punto
            if not any(isinstance(a, Road) for a in cell.agents):
                continue
            
            # VALIDACIÓN: No spawnear si ya hay un auto en esta celda
            if any(isinstance(a, Car) for a in cell.agents):
                continue
            
            # DESTINO: Asignar destino aleatorio (rotativo) del banco de destinos
            destination_cell = None
            if self.destinations:
                # Usar módulo para ciclar entre destinos disponibles
                destination_cell = self.destinations[spawned % len(self.destinations)].cell
            
            # CREACIÓN: Instanciar nuevo auto con ID único
            car_id = f"car_{self.cars_spawned}"
            new_car = Car(car_id, self, cell, destination_cell)
            # Guardar referencia al auto
            self.cars.append(new_car)
            self.cars_spawned += 1
            spawned += 1

    # ============================================================
    # PASO DE SIMULACIÓN
    # DESCRIPCIÓN: Avanza un paso la simulación completa
    # Genera autos cada 20 pasos, ejecuta step de todos los agentes,
    # y limpia autos eliminados
    # ============================================================
    def step(self):
        """Paso del modelo"""
        # Incrementar contador de pasos
        self.steps += 1
        
        # GENERACIÓN: Spawnear nuevos autos cada 20 pasos
        if self.steps % 20 == 0:
            self.spawn_cars()
        
        # EJECUCIÓN: Ejecutar step de todos los agentes en orden aleatorio
        self.agents.shuffle_do("step")
        
        # LIMPIEZA: Remover autos que alcanzaron destino (fueron removidos del modelo)
        # Solo mantener autos que aún están en self.agents
        self.cars = [c for c in self.cars if c in self.agents]