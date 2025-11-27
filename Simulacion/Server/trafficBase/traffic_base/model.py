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

        # Load the map dictionary. The dictionary maps the characters in the map file to the corresponding agent.
        #print(os.listdir())
        dataDictionary = json.load(open("city_files/mapDictionary.json"))

        self.num_agents = N
        self.traffic_lights = []
        self.destinations = []
        self.spawn_points = []
        self.cars_spawned = 0
        self.max_cars = N

        # Load the map file. The map file is a text file where each character represents an agent.
        with open("city_files/2024_base.txt") as baseFile:
            lines = baseFile.readlines()
            self.width = len(lines[0].strip())
            self.height = len(lines)

            self.grid = OrthogonalMooreGrid(
                [self.width, self.height], capacity=100, torus=False
            )

            # Goes through each character in the map file and creates the corresponding agent.
            for r, row in enumerate(lines):
                for c, col in enumerate(row.strip()):

                    cell = self.grid[(c, self.height - r - 1)]

                    if col in ["v", "^", ">", "<", "%", "&", "_", "="]:
                        agent = Road(f"road_{r}_{c}", self, cell, dataDictionary[col])

                    elif col in ["S", "s"]:
                        agent = Traffic_Light(
                            f"traffic_{r}_{c}",
                            self,
                            cell,
                            False if col == "S" else True,
                            int(dataDictionary[col]),
                        )
                        self.traffic_lights.append(agent)

                    elif col == "#":
                        agent = Obstacle(f"obstacle_{r}_{c}", self, cell)

                    elif col == "D":
                        agent = Destination(f"dest_{r}_{c}", self, cell)
                        self.destinations.append(agent)
        
        # Debug: Print traffic light locations
        print("\n=== Traffic Light Locations ===")
        for tl in self.traffic_lights:
            x, y = tl.cell.coordinate
            print(f"Traffic light at ({x}, {y})")
        print(f"Total traffic lights: {len(self.traffic_lights)}\n")
        
        # Debug: Print destination locations
        print("=== Destination Locations ===")
        for dest in self.destinations:
            x, y = dest.cell.coordinate
            print(f"Destination at ({x}, {y})")
        print(f"Total destinations: {len(self.destinations)}\n")
        
        self.spawn_points = [
            (0, self.height - 1), # Top-left
            (self.width - 1, self.height - 1), # Top-right
            (0, 0), # Bottom-left
            (self.width - 1, 0), # Bottom-right
        ]

        self.running = True

    def spawn_car(self):
        cars_spawned_this_step = 0  # Track how many cars are spawned in this step

        for spawn_point in self.spawn_points:
            cell = self.grid[spawn_point]
            
            # Check if there is space at the spawn point
            has_car = any(isinstance(agent, Car) for agent in cell.agents)
            if not has_car:
                destination = choice(self.destinations)
                Car(
                    f"car_{self.cars_spawned}",  # Unique ID for the car
                    self,
                    cell,
                    destination.cell
                )
                self.cars_spawned += 1  # Increment the total cars spawned
                cars_spawned_this_step += 1

        # Return True if at least one car was spawned
        return cars_spawned_this_step > 0

    def step(self):
        """Advance the model by one step."""
        if self.steps % 10 == 0:
            if not self.spawn_car():
                # Check if all four corners are occupied by cars
                corners_occupied = all(
                    any(isinstance(agent, Car) for agent in self.grid[corner].agents)
                    for corner in self.spawn_points
                )
                if corners_occupied:
                    self.running = False
                    return  # End the simulation

        self.agents.shuffle_do("step")
