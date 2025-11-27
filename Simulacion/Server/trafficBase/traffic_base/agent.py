from mesa.discrete_space import CellAgent, FixedAgent
import heapq
from collections import deque

class Car(CellAgent):
    """
    Agent that moves randomly.
    """
    def __init__(self, unique_id, model, cell, destination = None):
        """
        Creates a new random agent.
        Args:
            unique_id: Unique identifier for the car
            model: Model reference for the agent
            cell: The initial position of the agent
            destination: The destination cell for the car
        """
        super().__init__(model)
        self.unique_id = unique_id
        self.cell = cell
        self.dying = False
        self.moving = False
        self.waiting = True
        self.calculating = False 
        self.destination = destination
        self.path = []
        self.current_step_in_path = 0
        self.facing_direction = None  
        self.stuck_steps = 0  
        self.max_stuck_time = 20

        self.update_facing_direction()

        if self.destination:
            self.calculate_route()

    def update_facing_direction(self):
        """Updates the car's facing direction based on the current road"""
        for agent in self.cell.agents:
            if isinstance(agent, Road):
                # Use the first available direction
                self.facing_direction = agent.directions[0] if agent.directions else None
                break

    def die(self):
        """ 
        Makes the car disappear
        """
        self.dying = True
        self.remove()
    
    def move(self):
        if not self.path or self.current_step_in_path >= len(self.path):
            self.stop()
            return
        
        next_cell = self.path[self.current_step_in_path]
        
        if self.can_move_to_cell(next_cell):
            self.moving = True
            self.waiting = False
            
            # Calculate new facing direction before moving
            dx = next_cell.coordinate[0] - self.cell.coordinate[0]
            dy = next_cell.coordinate[1] - self.cell.coordinate[1]
            
            direction_map = {
                (0, 1): "Up",
                (0, -1): "Down",
                (1, 0): "Right",
                (-1, 0): "Left"
            }
            self.facing_direction = direction_map.get((dx, dy), self.facing_direction)
            
            self.cell = next_cell
            self.current_step_in_path += 1
            self.stuck_steps = 0
        else:
            self.stop()
            self.update_facing_direction()

    def stop(self):
        """ 
        Makes the car stop
        """
        self.moving = False
        self.waiting = True

    def calculate_route(self):
        """ 
        Calculates the route to the destination using A* algorithm
        Considers traffic lights, traffic density, and road directions
        """
        self.calculating = True
        
        if not self.destination:
            self.calculating = False
            return
        
        # Use the destination directly
        goal = self.destination
        
        # A* pathfinding
        start = self.cell
        
        # Priority queue: (f_score, counter, current_cell, path)
        counter = 0
        open_set = []
        heapq.heappush(open_set, (0, counter, start, [start]))
        
        # Track visited cells and their costs
        g_scores = {start: 0}
        visited = set()
        
        max_iterations = 2000  # Increase max iterations for larger paths
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            current_f, _, current_cell, path = heapq.heappop(open_set)
            
            # Skip if already visited
            if current_cell in visited:
                continue
            
            visited.add(current_cell)
            
            # Check if reached destination
            if current_cell == goal:
                self.path = path[1:]  # Exclude starting position
                self.current_step_in_path = 0
                self.calculating = False
                print(f"Car {self.unique_id}: Path found with {len(self.path)} steps")
                return
            
            # Get valid neighbors based on road direction
            neighbors = self.get_valid_neighbors(current_cell)
            
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                
                # Calculate cost
                tentative_g = g_scores[current_cell] + self.calculate_edge_cost(current_cell, neighbor)
                
                # If this path to neighbor is better
                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    h_score = self.heuristic(neighbor, goal)
                    f_score = tentative_g + h_score
                    
                    counter += 1
                    new_path = path + [neighbor]
                    heapq.heappush(open_set, (f_score, counter, neighbor, new_path))
        """
        # No path found - this destination is unreachable from this spawn point
        #print(f"Car {self.unique_id}: No path to destination (explored {len(visited)} cells)")
        if visited:
            closest = min(visited, key=lambda c: self.heuristic(c, goal))
            print(f"Car {self.unique_id}: Closest: ({closest.coordinate[0]}, {closest.coordinate[1]}) - distance: {self.heuristic(closest, goal)}")
        
        # Assign a new reachable destination or remove the car
        print(f"Car {self.unique_id}: Destination unreachable, finding alternative...")
        """
        self.find_reachable_destination()
        self.calculating = False

    def step(self):
        """ 
        Determines what action each car will take next step
        """
        # Priority 1: Check if at destination
        if self.is_at_destination():
            self.die()
            return
        
        # Priority 2: Calculate route if not done yet
        if not self.path and not self.calculating:
            self.calculate_route()
            # If no path found, stop
            if not self.path:
                #print(f"Car {self.unique_id}: No path found, stopping")
                self.stop()
                return
        
        # Check if stuck for too long
        if self.waiting:
            self.stuck_steps += 1
            if self.stuck_steps >= self.max_stuck_time:
                #print(f"Car {self.unique_id}: Stuck for {self.stuck_steps} steps, recalculating")
                # Recalculate path
                self.path = []
                self.current_step_in_path = 0
                self.stuck_steps = 0
                return  # Will recalculate next step
        else:
            self.stuck_steps = 0
        
        # Priority 3: Move along the path
        if self.path and self.current_step_in_path < len(self.path):
            self.move()
        else:
            #print(f"Car {self.unique_id}: Path completed or empty")
            self.stop()

    """
    =====================================================================================================================0
    Helper Functions
    =====================================================================================================================0
    """

    def heuristic(self, cell, goal):
        """Manhattan distance heuristic"""
        return abs(cell.coordinate[0] - goal.coordinate[0]) + abs(cell.coordinate[1] - goal.coordinate[1])

    def find_reachable_destination(self):
        """Finds a reachable destination for the car"""
        # Get all destinations from model
        all_destinations = []
        for x in range(self.model.grid.width):
            for y in range(self.model.grid.height):
                cell = self.model.grid[(x, y)]
                for agent in cell.agents:
                    if isinstance(agent, Destination):
                        all_destinations.append(agent)
        
        # Try each destination
        for dest in all_destinations:
            if self.can_reach_destination(dest.cell):
                print(f"Car {self.unique_id}: Found reachable destination at ({dest.cell.coordinate[0]}, {dest.cell.coordinate[1]})")
                self.destination = dest.cell
                self.calculate_route()
                return
        
        # No reachable destination found
        print(f"Car {self.unique_id}: No reachable destination found, removing car")
        self.die()
    
    def can_reach_destination(self, goal):
        """Quick BFS check if destination is reachable"""
        start = self.cell
        visited = set()
        queue = deque([start])
        visited.add(start)
        max_checks = 500
        checks = 0
        
        while queue and checks < max_checks:
            checks += 1
            current = queue.popleft()
            
            if current == goal:
                return True
            
            neighbors = self.get_valid_neighbors(current)
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return False
    
    def get_valid_neighbors(self, cell):
        """Gets valid neighboring cells based on road directions"""
        neighbors = []
        
        # Find the road and traffic light at current cell
        road = None
        traffic_light = None
        for agent in cell.agents:
            if isinstance(agent, Road):
                road = agent
            if isinstance(agent, Traffic_Light):
                traffic_light = agent
        
        # If at destination, can move in any direction
        is_destination = any(isinstance(agent, Destination) for agent in cell.agents)
        if is_destination:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                new_x = cell.coordinate[0] + dx
                new_y = cell.coordinate[1] + dy
                if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                    next_cell = self.model.grid[(new_x, new_y)]
                    if self.is_traversable(next_cell):
                        neighbors.append(next_cell)
            return neighbors
        
        # If cell has a traffic light (with or without road), allow ALL 4 directions
        if traffic_light:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                new_x = cell.coordinate[0] + dx
                new_y = cell.coordinate[1] + dy
                
                if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                    next_cell = self.model.grid[(new_x, new_y)]
                    if self.is_traversable(next_cell):
                        neighbors.append(next_cell)
            return neighbors
        
        # If no road and no traffic light, allow movement to adjacent traffic lights/destinations
        if not road:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                new_x = cell.coordinate[0] + dx
                new_y = cell.coordinate[1] + dy
                
                if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                    next_cell = self.model.grid[(new_x, new_y)]
                    # Can move to traffic lights or destinations from non-road cells
                    has_tl = any(isinstance(agent, Traffic_Light) for agent in next_cell.agents)
                    has_dest = any(isinstance(agent, Destination) for agent in next_cell.agents)
                    if (has_tl or has_dest) and self.is_traversable(next_cell):
                        neighbors.append(next_cell)
            return neighbors
        
        # Extended direction map
        direction_map = {
            "Up": (0, 1),
            "Down": (0, -1),
            "Left": (-1, 0),
            "Right": (1, 0),
            "Up_and_Left": [(0, 1), (-1, 0)],
            "Up_and_Right": [(0, 1), (1, 0)],
            "Down_and_Left": [(0, -1), (-1, 0)],
            "Down_and_Right": [(0, -1), (1, 0)]
        }
        
        # Check all allowed directions for this road
        for direction in road.directions:
            moves = direction_map.get(direction, None)
            
            if moves is None:
                continue
            
            if isinstance(moves, list):
                for dx, dy in moves:
                    new_x = cell.coordinate[0] + dx
                    new_y = cell.coordinate[1] + dy
                    
                    if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                        next_cell = self.model.grid[(new_x, new_y)]
                        if self.is_traversable(next_cell):
                            neighbors.append(next_cell)
            else:
                dx, dy = moves
                new_x = cell.coordinate[0] + dx
                new_y = cell.coordinate[1] + dy
                
                if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                    next_cell = self.model.grid[(new_x, new_y)]
                    if self.is_traversable(next_cell):
                        neighbors.append(next_cell)
        
        # Allow entry to adjacent traffic lights from any road
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x = cell.coordinate[0] + dx
            new_y = cell.coordinate[1] + dy
            
            if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                next_cell = self.model.grid[(new_x, new_y)]
                has_traffic_light = any(isinstance(agent, Traffic_Light) for agent in next_cell.agents)
                if has_traffic_light and self.is_traversable(next_cell) and next_cell not in neighbors:
                    neighbors.append(next_cell)
        
        # Also check if ANY neighbor is a destination
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x = cell.coordinate[0] + dx
            new_y = cell.coordinate[1] + dy
            
            if 0 <= new_x < self.model.grid.width and 0 <= new_y < self.model.grid.height:
                next_cell = self.model.grid[(new_x, new_y)]
                is_dest = any(isinstance(agent, Destination) for agent in next_cell.agents)
                if is_dest and next_cell not in neighbors:
                    neighbors.append(next_cell)
        
        return neighbors
    
    def calculate_edge_cost(self, from_cell, to_cell):
        """Calculates the cost to move from one cell to another"""
        base_cost = 1.0
        
        # Penalize cells with traffic lights (especially red ones)
        for agent in to_cell.agents:
            if isinstance(agent, Traffic_Light):
                if not agent.state:  # Red light
                    base_cost += 5.0
                else:  # Green light
                    base_cost += 1.0
        
        # Penalize cells with other cars (traffic density)
        car_count = sum(1 for agent in to_cell.agents if isinstance(agent, Car))
        base_cost += car_count * 3.0
        
        # Check cars in neighboring cells (surrounding traffic)
        surrounding_cars = 0
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx = to_cell.coordinate[0] + dx
            ny = to_cell.coordinate[1] + dy
            if 0 <= nx < self.model.grid.width and 0 <= ny < self.model.grid.height:
                neighbor_cell = self.model.grid[(nx, ny)]
                surrounding_cars += sum(1 for agent in neighbor_cell.agents if isinstance(agent, Car))
        
        base_cost += surrounding_cars * 0.5
        
        return base_cost

    def get_next_cell_in_direction(self):
        """Gets the next cell based on the current road direction"""
        road = None
        for agent in self.cell.agents:
            if isinstance(agent, Road):
                road = agent
                break
        
        if not road:
            return None
            
        direction_map = {
            "Up": (0, 1),
            "Down": (0, -1),
            "Left": (-1, 0),
            "Right": (1, 0)
        }
        
        # For multi-directional roads, use the first direction
        # (or implement logic to choose based on path)
        primary_direction = road.directions[0] if road.directions else None
        
        if not primary_direction:
            return None
        
        dx, dy = direction_map.get(primary_direction, (0, 0))
        next_x = self.cell.coordinate[0] + dx
        next_y = self.cell.coordinate[1] + dy
        
        if 0 <= next_x < self.model.grid.width and 0 <= next_y < self.model.grid.height:
            return self.model.grid[(next_x, next_y)]
        return None

    def is_traversable(self, cell):
        """Checks if a cell can be used in pathfinding (ignores temporary obstacles like cars)"""
        if not cell:
            return False
        
        # Destinations are always traversable
        is_destination = any(isinstance(agent, Destination) for agent in cell.agents)
        if is_destination:
            return True
        
        # CRITICAL FIX: Traffic light cells are ALWAYS traversable
        has_traffic_light = any(isinstance(agent, Traffic_Light) for agent in cell.agents)
        if has_traffic_light:
            return True
        
        has_road = False
        has_permanent_obstacle = False
        
        for agent in cell.agents:
            if isinstance(agent, Road):
                has_road = True
            if isinstance(agent, Obstacle):
                has_permanent_obstacle = True
                
        return has_road and not has_permanent_obstacle
    
    def can_move_to_cell(self, cell):
        """Checks if the car can move to a cell in the current step (includes traffic lights and other cars)"""
        # Check traffic light state
        for agent in cell.agents:
            if isinstance(agent, Traffic_Light):
                if not agent.state:  # Red
                    return False
        
        if not self.is_traversable(cell):
            return False
        
        # Check for temporary obstacles (other cars)
        for agent in cell.agents:
            if isinstance(agent, Car):
                return False
                    
        return True
    
    def is_at_destination(self):
        """Checks if the car has reached its destination"""
        for agent in self.cell.agents:
            if isinstance(agent, Destination):
                return True
        return False

class Traffic_Light(FixedAgent):
    """
    Traffic light. Where the traffic lights are in the grid.
    """
    def __init__(self, unique_id, model, cell, state = False, timeToChange = 10):
        """
        Creates a new Traffic light.
        Args:
            model: Model reference for the agent
            cell: The initial position of the agent
            state: Whether the traffic light is green or red
            timeToChange: After how many step should the traffic light change color 
        """
        super().__init__(model)
        self.cell = cell
        self.state = state
        self.timeToChange = timeToChange
        self.unique_id = unique_id

    def step(self):
        """ 
        To change the state (green or red) of the traffic light in case you consider the time to change of each traffic light.
        """
        if self.model.steps % self.timeToChange == 0:
            self.state = not self.state

class Destination(FixedAgent):
    """
    Destination agent. Where each car should go.
    """
    def __init__(self, unique_id, model, cell):
        """
        Creates a new destination agent
        Args:
            model: Model reference for the agent
            cell: The initial position of the agent
        """
        super().__init__(model)
        self.cell = cell
        self.unique_id = unique_id

class Obstacle(FixedAgent):
    """
    Obstacle agent. Just to add obstacles to the grid.
    """
    def __init__(self, unique_id, model, cell):
        """
        Creates a new obstacle.
        
        Args:
            model: Model reference for the agent
            cell: The initial position of the agent
        """
        super().__init__(model)
        self.cell = cell
        self.unique_id = unique_id

class Road(FixedAgent):
    """
    Road agent. Determines where the cars can move, and in which direction.
    """
    def __init__(self, unique_id, model, cell, direction= "Left"):
        """
        Creates a new road.
        Args:
            model: Model reference for the agent
            cell: The initial position of the agent
        """
        super().__init__(model)
        self.cell = cell
        self.unique_id = unique_id

        # Handle multi-directional roads properly
        if "Up_and_Left" in direction:
            self.directions = ["Up", "Left"]
        elif "Up_and_Right" in direction:
            self.directions = ["Up", "Right"]
        elif "Down_and_Left" in direction:
            self.directions = ["Down", "Left"]
        elif "Down_and_Right" in direction:
            self.directions = ["Down", "Right"]
        else:
            self.directions = [direction]
