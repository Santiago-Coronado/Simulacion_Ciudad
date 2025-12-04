from random import random, choice
from mesa import Model
from mesa.discrete_space import OrthogonalMooreGrid
from mesa.datacollection import DataCollector
from .agent import *
import os
import json
import requests

class CityModel(Model):
    """
    Creates a model based on a city map.

    Args:
        N: Number of agents in the simulation
        seed: Random seed for the model
    """

    def __init__(self, N, spawn_frequency=10, seed=42):
        super().__init__(seed=seed)
    

        # Load the map dictionary. The dictionary maps the characters in the map file to the corresponding agent.
        dataDictionary = json.load(open("city_files/mapDictionary.json"))

        self.num_agents = N
        self.traffic_lights = []  
        self.destinations = []   
        self.spawn_points = []    
        self.cars_spawned = 0   # Total number of cars spawned
        self.cars_reached_destination = 0  # Total number of cars that have reached their destination
        self.max_cars = N         # Maximum number of cars simultaneously
        self.cars = []            # List of active cars in the simulation
        self.spawn_frequency = spawn_frequency  # Steps between spawns

        self.edge_costs = {}
        self.cell_neighbors = {}

        self.datacollector = DataCollector(
            model_reporters={
                "Active Cars": lambda m: len(m.cars),
                "Cars Spawned": lambda m: m.cars_spawned,
                "Cars Reached Destination": lambda m: m.cars_reached_destination,
            }
        )

        # Load the map file. The map file is a text file where each character represents an agent.
        with open("city_files/2025_base.txt") as baseFile:
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

        self.initialize_pathfinding_graph()
        self.datacollector.collect(self)
        self.running = True

    # ===========================================================
    # PATHFINDING GRAPH INITIALIZATION
    # DESCRIPTION: Pre-computes the graph structure and costs
    # ===========================================================
    def initialize_pathfinding_graph(self):
        """Pre-compute the graph structure and costs"""
        for x in range(self.width):
            for y in range(self.height):
                cell = self.grid[(x, y)]
                
                if not self.is_traversable_cell(cell):
                    continue
                
                # Compute valid neighbors
                neighbors = self.compute_valid_neighbors(cell)
                self.cell_neighbors[cell] = neighbors
                
                # Pre-compute base edge costs (without dynamic traffic)
                for neighbor in neighbors:
                    edge_key = (cell, neighbor)
                    self.edge_costs[edge_key] = 1.0  # Base cost

    # ===========================================================
    # PATHFINDING UTILITIES
    # DESCRIPTION: Functions to support pathfinding and cost updates
    # ===========================================================
    def is_traversable_cell(self, cell):
        """Check if cell can be used in pathfinding"""
        if not cell:
            return False
        
        if any(isinstance(agent, (Destination, Traffic_Light)) for agent in cell.agents):
            return True
        
        has_road = any(isinstance(agent, Road) for agent in cell.agents)
        has_obstacle = any(isinstance(agent, Obstacle) for agent in cell.agents)
        
        return has_road and not has_obstacle

    def compute_valid_neighbors(self, cell):
        """Compute valid neighbors for a cell based on road directions"""
        x, y = cell.coordinate
        neighbors = []
        
        DIRECTION_OFFSETS = {
            "Up": (0, 1),
            "Down": (0, -1),
            "Right": (1, 0),
            "Left": (-1, 0)
        }
        
        # Get allowed directions from current cell
        if any(isinstance(a, Traffic_Light) for a in cell.agents):
            # Traffic lights allow all directions
            allowed_dirs = list(DIRECTION_OFFSETS.keys())
        else:
            allowed_dirs = [d for agent in cell.agents if isinstance(agent, Road) for d in agent.directions]
        
        for direction in allowed_dirs:
            if direction in DIRECTION_OFFSETS:
                dx, dy = DIRECTION_OFFSETS[direction]
                nx, ny = x + dx, y + dy
                
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    neighbor = self.grid[(nx, ny)]
                    if self.is_traversable_cell(neighbor) and neighbor != cell:
                        neighbors.append(neighbor)
        
        return neighbors

    def update_dynamic_costs(self):
        """Update edge costs based on current traffic conditions (called once per step)"""
        # Reset all costs to base
        for edge_key in self.edge_costs:
            self.edge_costs[edge_key] = 1.0
        
        # Update costs based on current conditions
        for cell in self.cell_neighbors.keys():
            neighbors = self.cell_neighbors[cell]
            
            for neighbor in neighbors:
                edge_key = (cell, neighbor)
                cost = self.calculate_dynamic_edge_cost(cell, neighbor)
                self.edge_costs[edge_key] = cost

    def calculate_dynamic_edge_cost(self, from_cell, to_cell):
        """Calculate edge cost based on current traffic and lights"""
        base_cost = 1.0
        
        # Car density penalty
        car_count = sum(1 for agent in to_cell.agents if isinstance(agent, Car) and not agent.dying)
        base_cost += car_count * 5.0

        #Penalty for waiting cars in target direction
        waiting_cars = sum(1 for agent in to_cell.agents 
                        if isinstance(agent, Car) and agent.waiting and not agent.dying)
        base_cost += waiting_cars * 10.0  # Heavy penalty for waiting cars
        
        # Traffic light penalties
        for agent in to_cell.agents:
            if isinstance(agent, Traffic_Light):
                current_time = self.steps % agent.timeToChange
                time_until_change = agent.timeToChange - current_time
                
                if not agent.state:  # Red light
                    base_cost += min(time_until_change * 0.5, 5)
                else:  # Green light
                    remaining_green = agent.timeToChange - time_until_change
                    base_cost += remaining_green * 0.3 if remaining_green < 3 else 0.1
        
        # Surrounding traffic density
        x, y = to_cell.coordinate
        surrounding_cars = 0
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    neighbor = self.grid[(nx, ny)]
                    distance = max(abs(dx), abs(dy))
                    cars = sum(1 for a in neighbor.agents if isinstance(a, Car) and not a.dying)
                    surrounding_cars += cars / (distance ** 2)
        
        base_cost += surrounding_cars * 0.5
        
        return base_cost

    def find_path(self, start_cell, goal_cell, car=None):
        """Centralized A* pathfinding using pre-computed graph"""
        if start_cell not in self.cell_neighbors or goal_cell not in self.cell_neighbors:
            return []
        
        counter = 0
        open_set = []
        heapq.heappush(open_set, (0, counter, start_cell, [start_cell]))
        
        g_scores = {start_cell: 0}
        visited = set()
        
        max_iterations = 10000
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            current_f, _, current_cell, path = heapq.heappop(open_set)
            
            if current_cell in visited:
                continue
            
            visited.add(current_cell)
            
            # Found goal
            if current_cell == goal_cell:
                return path[1:]  # Exclude start cell
            
            # Get pre-computed neighbors
            neighbors = self.cell_neighbors.get(current_cell, [])
            
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                
                # Get pre-computed edge cost
                edge_key = (current_cell, neighbor)
                edge_cost = self.edge_costs.get(edge_key, 1.0)
                
                # Add penalty for backtracking (if car provided)
                if car and car.position_history and neighbor in car.position_history:
                    edge_cost += 20
                
                tentative_g = g_scores[current_cell] + edge_cost
                
                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    h_score = abs(neighbor.coordinate[0] - goal_cell.coordinate[0]) + \
                             abs(neighbor.coordinate[1] - goal_cell.coordinate[1])
                    f_score = tentative_g + h_score
                    
                    counter += 1
                    new_path = path + [neighbor]
                    heapq.heappush(open_set, (f_score, counter, neighbor, new_path))
        
        return []  # No path found
    
    # ============================================================
    # CAR GENERATION
    # DESCRIPTION: Creates new cars at spawn points
    # ============================================================
    def spawn_cars(self):
        """Generates cars at spawn points every n steps"""
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
    # Generates cars every n steps, executes step for all agents,
    # and cleans up removed cars
    # ============================================================
    def step(self):     
        # EXECUTION: Execute step for all agents in random order
        self.agents.shuffle_do("step")

        # Check if all spawn points are blocked
        if self.all_spawn_points_blocked():
            self.running = False

         # GENERATION: Spawn new cars every n steps
        if self.steps % self.spawn_frequency == 0:
            self.spawn_cars()   

        # Update dynamic costs once per step
        self.update_dynamic_costs()
        
        # CLEANUP: Remove cars that reached their destination (were removed from the model)
        # Only keep cars that are still in self.agents
        self.cars = [c for c in self.cars if c in self.agents]

        # Collect data for this step
        self.datacollector.collect(self)

        # Api connection to send simulation data
        url = "http://10.49.12.39:5000/api/"
        endpoint = "validate_attempt"

        data = {
            "year" : 2025,
            "classroom" : 302,
            "name" : "Equipo Los Troneadores",
            "current_cars": len(self.cars),
            "total_arrived": self.cars_reached_destination,
            "attempt_number": 5
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url+endpoint, data=json.dumps(data), headers=headers)
        print("Data: ",data)

        print("Request " + "successful" if response.status_code == 200 else "failed", "Status code:", response.status_code)
        print("Response:", response.json())

    # ============================================================
    # SPAWN POINT CHECK 
    # DESCRIPTION: Checks if all spawn points are blocked
    # ============================================================
    def all_spawn_points_blocked(self):
        """Check if all spawn points with roads are blocked by cars"""
        valid_spawn_points = 0
        blocked_spawn_points = 0
        
        for pos in self.spawn_points:
            cell = self.grid[pos]
            
            # Check if there's a road at this spawn point
            has_road = any(isinstance(a, Road) for a in cell.agents)
            if not has_road:
                continue  # Skip invalid spawn points
            
            valid_spawn_points += 1
            
            # Check if there's already a car at this spawn point
            has_car = any(isinstance(a, Car) for a in cell.agents)
            if has_car:
                blocked_spawn_points += 1
        
        # Only end simulation if we have valid spawn points and all are blocked
        return valid_spawn_points > 0 and blocked_spawn_points == valid_spawn_points    