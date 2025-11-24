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

        # Load the map file. The map file is a text file where each character represents an agent.
        with open("city_files/2024_base.txt") as baseFile:
            lines = baseFile.readlines()
            self.width = len(lines[0])
            self.height = len(lines)

            self.grid = OrthogonalMooreGrid(
                [self.width, self.height], capacity=100, torus=False
            )

            # Goes through each character in the map file and creates the corresponding agent.
            for r, row in enumerate(lines):
                for c, col in enumerate(row):

                    cell = self.grid[(c, self.height - r - 1)]

                    if col in ["v", "^", ">", "<"]:
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
                        
        self.running = True

    def step(self):
        """Advance the model by one step."""
        self.agents.shuffle_do("step")
