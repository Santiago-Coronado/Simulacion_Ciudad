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
        
        self.steps = 0

        # Load the map dictionary. The dictionary maps the characters in the map file to the corresponding agent.
        dataDictionary = json.load(open("city_files/mapDictionary.json"))

        self.num_agents = N
        self.traffic_lights = []  
        self.destinations = []   
        self.spawn_points = []    
        self.cars_spawned = 0     # How many cars are spawned so far
        self.max_cars = N         # Maximum number of cars simultaneously
        self.cars = []            # List of active cars in the simulation

        # Load the map file. The map file is a text file where each character represents an agent.
        with open("city_files/2024_base.txt") as baseFile:
            lines = baseFile.readlines()
            # Get width (characters per line) and height (number of lines)
            self.width = len(lines[0].strip())
            self.height = len(lines)

            # Create grid with capacity for multiple agents per cell
            self.grid = OrthogonalMooreGrid(
                [self.width, self.height], capacity=100, torus=False
            )

            # MAP PARSING: Iterate over each character in the .txt file
            # Coordinates are inverted in Y so that (0,0) is the bottom left corner
            for r, row in enumerate(lines):
                for c, col in enumerate(row.strip()):

                    cell = self.grid[(c, self.height - r - 1)]

                    # ROADS: Characters v,^,>,<,%,&,_,= represent directions
                    if col in ["v", "^", ">", "<", "%", "&", "_", "="]:
                        agent = Road(f"road_{r}_{c}", self, cell, dataDictionary[col])

                    # TRAFFIC LIGHTS: S (initial red) or s (initial green)
                    elif col in ["S", "s"]:
                        # Initial state: False=red (S), True=green (s)
                        initial_state = False if col == "S" else True
                        # Change time comes from the dictionary
                        change_time = int(dataDictionary[col])
                        agent = Traffic_Light(
                            f"traffic_{r}_{c}",
                            self,
                            cell,
                            initial_state,
                            change_time,
                        )
                        # Save reference for quick access
                        self.traffic_lights.append(agent)

                    # OBSTACLES: # represents buildings/fixed objects
                    elif col == "#":
                        agent = Obstacle(f"obstacle_{r}_{c}", self, cell)

                    # DESTINATIONS: D is where cars should arrive
                    elif col == "D":
                        agent = Destination(f"dest_{r}_{c}", self, cell)
                        # Save reference to assign destinations to new cars
                        self.destinations.append(agent)
        
        # SPAWN POINTS: Corners of the map where new cars appear

        self.spawn_points = [
            (0, self.height - 1),                # Top left corner
            (self.width - 1, self.height - 1),   # Top right corner
            (0, 0),                              # Bottom left corner
            (self.width - 1, 0),                 # Bottom right corner
        ]

        self.running = True

    # ============================================================
    # CAR GENERATION
    # DESCRIPTION: Creates new cars at spawn points
    # Called every 20 steps to gradually generate traffic
    # ============================================================
    def spawn_cars(self):
        """Generates cars at spawn points every 20 steps"""
        spawned = 0
        # Iterate over each spawn point
        for pos in self.spawn_points:
            cell = self.grid[pos]
            
            # VALIDATION: Only spawn if there is a road at this point
            if not any(isinstance(a, Road) for a in cell.agents):
                continue
            
            # VALIDATION: Do not spawn if there is already a car in this cell
            if any(isinstance(a, Car) for a in cell.agents):
                continue
            
            # DESTINATION: Assign random (rotating) destination from the destination pool
            destination_cell = None
            if self.destinations:
                # Use modulo to cycle through available destinations
                destination_cell = self.destinations[spawned % len(self.destinations)].cell
            
            # CREATION: Instantiate new car with unique ID
            car_id = f"car_{self.cars_spawned}"
            new_car = Car(car_id, self, cell, destination_cell)
            # Save reference to the car
            self.cars.append(new_car)
            self.cars_spawned += 1
            spawned += 1

    # ============================================================
    # SIMULATION STEP
    # DESCRIPTION: Advances the entire simulation by one step
    # Generates cars every 20 steps, executes step for all agents,
    # and cleans up removed cars
    # ============================================================
    def step(self):
        """Model step"""
        # Increment step counter
        self.steps += 1
        
        # GENERATION: Spawn new cars every 20 steps
        if self.steps % 20 == 0:
            self.spawn_cars()
        
        # EXECUTION: Execute step for all agents in random order
        self.agents.shuffle_do("step")
        
        # CLEANUP: Remove cars that reached their destination (were removed from the model)
        # Only keep cars that are still in self.agents
        self.cars = [c for c in self.cars if c in self.agents]