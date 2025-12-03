from mesa.discrete_space import CellAgent, FixedAgent
import heapq
from collections import deque

class Car(CellAgent):
    # Class constants for direction mappings
    DIRECTION_OFFSETS = {
        "Up": (0, 1),
        "Down": (0, -1),
        "Right": (1, 0),
        "Left": (-1, 0)
    }
    
    PERPENDICULAR = {
        "Up": ["Left", "Right"],
        "Down": ["Left", "Right"],
        "Left": ["Up", "Down"],
        "Right": ["Up", "Down"]
    }
    
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
        self.steps_since_last_recalc = 0
        self.position_history = deque(maxlen=5)
        self.failed_pathfinding_attempts = 0
        self.wait_before_retry = 0
        self.arrival_time_at_intersection = None  # Track when car arrived at intersection
        self.has_claimed_intersection = False  # C ar has right-of-way
        self.turn_direction = None  # "straight", "left", or "right"

    """
    ======================================================================================================================
    Main Functions
    ======================================================================================================================
    """


    def update_facing_direction(self):
        """Updates the car's facing direction based on the current road"""
        for agent in self.cell.agents:
            if isinstance(agent, Road):
                # Use the first available direction
                if agent.directions:
                    self.facing_direction = agent.directions[0]
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
            self.position_history.append(self.cell)
            
            # Reset intersection tracking when leaving traffic light
            if self.has_traffic_light(self.cell) and not self.has_traffic_light(next_cell):
                self.arrival_time_at_intersection = None
                self.has_claimed_intersection = False
            
            # Calculate new facing direction before moving
            dx = next_cell.coordinate[0] - self.cell.coordinate[0]
            dy = next_cell.coordinate[1] - self.cell.coordinate[1]
            direction_map = {v: k for k, v in self.DIRECTION_OFFSETS.items()}
            self.facing_direction = direction_map.get((dx, dy), self.facing_direction)
            
            self.cell = next_cell
            self.current_step_in_path += 1
            self.stuck_steps = 0
        else:
            self.stop()

    def stop(self):
        """ 
        Makes the car stop
        """
        self.moving = False
        self.waiting = True

    def calculate_route(self):
        """ 
        Calculates the route to the destination using A* algorithm
        """
        self.calculating = True

        if not self.destination:
            self.calculating = False
            return
        
        goal = self.destination
        start = self.cell

        if not self.is_traversable(start):
            self.calculating = False
            return
        
        initial_neighbors = self.get_valid_neighbors(start)
                
        counter = 0
        open_set = []
        heapq.heappush(open_set, (0, counter, start, [start]))
        
        g_scores = {start: 0}
        visited = set()
        
        # Increase iterations based on retry attempts
        max_iterations = 10000 * (1 + self.failed_pathfinding_attempts)
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            current_f, _, current_cell, path = heapq.heappop(open_set)
            
            if current_cell in visited:
                continue
            
            visited.add(current_cell)
            
            if current_cell == goal:
                self.path = path[1:]
                self.current_step_in_path = 0
                self.calculating = False
                self.failed_pathfinding_attempts = 0  # Reset on success
                return
            
            neighbors = self.get_valid_neighbors(current_cell)
            
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                
                tentative_g = g_scores[current_cell] + self.calculate_edge_cost(current_cell, neighbor)
                
                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    h_score = self.heuristic(neighbor, goal)
                    f_score = tentative_g + h_score
                    
                    counter += 1
                    new_path = path + [neighbor]
                    heapq.heappush(open_set, (f_score, counter, neighbor, new_path))

        # Pathfinding failed
        self.failed_pathfinding_attempts += 1
        self.wait_before_retry = min(20 * self.failed_pathfinding_attempts, 100) 
        
        self.calculating = False

    def step(self):
        """Determines what action each car will take next step"""

        # Handle wait before retrying pathfinding
        if self.wait_before_retry > 0:
            self.wait_before_retry -= 1
            self.stop()
            return
        
        # Priority 1: Check if at destination
        if self.is_at_destination():
            self.die()
            return
        
        # Priority 2: Calculate route if not done yet
        if not self.path and not self.calculating:
            self.calculate_route()
            if not self.path:
                self.stop()
                return
        
        # Priority 3: Check if path is exhausted but not at destination
        if self.path and self.current_step_in_path >= len(self.path):
            self.path = []
            self.current_step_in_path = 0
            self.position_history.clear()
            self.calculate_route()

        
        # Priority 4: Try to move
        if self.path and self.current_step_in_path < len(self.path):
            next_cell = self.path[self.current_step_in_path]
            
            if self.can_move_to_cell(next_cell):
                self.move()
                self.stuck_steps = 0
                return
            else:
                self.waiting = True
                self.stuck_steps += 1

            is_blocked_by_car = any(isinstance(agent, Car) for agent in next_cell.agents)
            has_traffic_light = any(isinstance(agent, Traffic_Light) for agent in next_cell.agents)

            if is_blocked_by_car and not has_traffic_light and not self.is_near_traffic_light(1):
                    # Try lane change first
                    lane_change_cell = self.can_change_lane()
                    if lane_change_cell:
                        self.cell = lane_change_cell
                        self.stuck_steps = 0
                        self.path = []
                        self.position_history.clear()
                        self.current_step_in_path = 0
                        self.calculate_route()
                        return
                    
                    # If no lane change possible and stuck for 2+ steps, recalculate immediately
                    if self.stuck_steps >= 2:
                        self.path = []
                        self.current_step_in_path = 0
                        self.position_history.clear()
                        self.calculate_route()
                        self.stuck_steps = 0
                        return
        
        # Priority 5: Try lane change if stuck (not at traffic lights)
        if self.waiting and self.stuck_steps >= 3 and not self.is_near_traffic_light(1):
            lane_change_cell = self.can_change_lane()
            if lane_change_cell:
                self.cell = lane_change_cell
                self.stuck_steps = 0
                self.path = []
                self.position_history.clear()
                self.current_step_in_path = 0
                self.calculate_route()
                return
        
        # Priority 6: Recalculate if stuck too long (not at traffic lights)
        if self.stuck_steps >= 10 and not self.is_near_traffic_light(2):
            self.path = []
            self.current_step_in_path = 0
            self.position_history.clear()
            self.calculate_route()
            self.stuck_steps = 0

    """
    =====================================================================================================================0
    Helper Functions
    =====================================================================================================================0
    """

    def heuristic(self, cell, goal):
        """Manhattan distance heuristic"""
        return abs(cell.coordinate[0] - goal.coordinate[0]) + abs(cell.coordinate[1] - goal.coordinate[1])
    
    def has_traffic_light(self, cell):
        """Check if cell has a traffic light"""
        return any(isinstance(agent, Traffic_Light) for agent in cell.agents)
    
    def has_road(self, cell):
        """Check if cell has a road"""
        return any(isinstance(agent, Road) for agent in cell.agents)
    
    def get_cars_in_cell(self, cell):
        """Count non-dying cars in cell"""
        return sum(1 for agent in cell.agents if isinstance(agent, Car) and not agent.dying)
    
    def _get_neighbor_cell(self, x, y):
        """Get cell at coordinates if valid"""
        if 0 <= x < self.model.grid.width and 0 <= y < self.model.grid.height:
            return self.model.grid[(x, y)]
        return None
    
    def get_valid_neighbors(self, cell):
        """Gets valid neighboring cells based on road directions, prioritizing less congested lanes"""
        x, y = cell.coordinate
        
        if self.has_traffic_light(cell):
            neighbors = self._get_traffic_light_neighbors(x, y)
        else:
            neighbors = self._get_road_neighbors(cell, x, y)
        
        return sorted(neighbors, key=self._get_congestion_score)
    
    def _get_traffic_light_neighbors(self, x, y):
        """Get neighbors when at traffic light - allow all valid directions for pathfinding"""
        neighbors = []
        
        # During pathfinding, explore all traversable directions
        for direction, (dx, dy) in self.DIRECTION_OFFSETS.items():
            neighbor = self._get_neighbor_cell(x + dx, y + dy)
            if neighbor and self.is_traversable(neighbor):
                # Verify the neighbor allows this approach direction
                if self.has_road(neighbor):
                    for agent in neighbor.agents:
                        if isinstance(agent, Road):
                            # Check if we can enter this road from current direction
                            opposite_dir = {"Up": "Down", "Down": "Up", "Left": "Right", "Right": "Left"}[direction]
                            if direction in agent.directions or opposite_dir in agent.directions:
                                neighbors.append(neighbor)
                                break
                elif self.has_traffic_light(neighbor) or any(isinstance(a, Destination) for a in neighbor.agents):
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _get_road_neighbors(self, cell, x, y):
        """Get neighbors when on regular road"""
        neighbors = []
        allowed_dirs = [d for agent in cell.agents if isinstance(agent, Road) for d in agent.directions]
        
        for direction in allowed_dirs:
            if direction in self.DIRECTION_OFFSETS:
                dx, dy = self.DIRECTION_OFFSETS[direction]
                neighbor = self._get_neighbor_cell(x + dx, y + dy)

                if neighbor and self.is_traversable(neighbor) and neighbor != cell:
                    neighbors.append(neighbor)
        return neighbors
    
    def _get_congestion_score(self, neighbor_cell):
        """Calculate congestion score for sorting"""
        score = 20 if neighbor_cell in self.position_history else 0
        score += self.get_cars_in_cell(neighbor_cell) * 8
        
        # Check surrounding area (2-cell radius)
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx == 0 and dy == 0:
                    continue
                neighbor = self._get_neighbor_cell(neighbor_cell.coordinate[0] + dx, neighbor_cell.coordinate[1] + dy)
                if neighbor:
                    distance = max(abs(dx), abs(dy))
                    score += self.get_cars_in_cell(neighbor) / (distance ** 2)
        
        # Red light penalty
        if any(isinstance(a, Traffic_Light) and not a.state for a in neighbor_cell.agents):
            score += 3
        
        return score
        
    def calculate_edge_cost(self, from_cell, to_cell):
        """Calculates the cost to move from one cell to another"""
        base_cost = 1.0

        # Recent path backtracking penalty
        if self.path and 0 < self.current_step_in_path <= len(self.path):
            lookback = min(3, self.current_step_in_path)
            if to_cell in self.path[max(0, self.current_step_in_path - lookback):self.current_step_in_path]:
                base_cost += 50
        
        # Traffic light timing penalties
        for agent in to_cell.agents:
            if isinstance(agent, Traffic_Light):
                current_time = self.model.steps % agent.timeToChange
                time_until_change = agent.timeToChange - current_time
                base_cost += min(time_until_change * 0.5, 5) if not agent.state else \
                            (agent.timeToChange - time_until_change) * 0.3 if self.heuristic(self.cell, to_cell) / 2 > time_until_change else 0.1
        
        # Car density and surrounding traffic penalties
        car_count = self.get_cars_in_cell(to_cell)
        base_cost += car_count * 2.0
        
        surrounding_cars = sum(
            self.get_cars_in_cell(neighbor) / (max(abs(dx), abs(dy)) ** 2)
            for dx in range(-2, 3) for dy in range(-2, 3)
            if (dx != 0 or dy != 0) and (neighbor := self._get_neighbor_cell(to_cell.coordinate[0] + dx, to_cell.coordinate[1] + dy))
        )
        base_cost += surrounding_cars * 0.5
        
        return base_cost

    def is_traversable(self, cell):
        """Checks if a cell can be used in pathfinding (ignores temporary obstacles like cars)"""
        if not cell:
            return False
        
        # Destinations and traffic lights are always traversable
        if any(isinstance(agent, (Destination, Traffic_Light)) for agent in cell.agents):
            return True
        
        has_road = any(isinstance(agent, Road) for agent in cell.agents)
        has_obstacle = any(isinstance(agent, Obstacle) for agent in cell.agents)
        
        return has_road and not has_obstacle
    
    def can_move_to_cell(self, cell):
        """Checks if the car can move to a cell in the current step (includes traffic lights and other cars)"""
        # Check traffic light state only if car is NOT already on a traffic light
        if not self.has_traffic_light(self.cell) and self.has_traffic_light(cell):
            for agent in cell.agents:
                if isinstance(agent, Traffic_Light) and not agent.state:
                    return False
    
        # Check if cell is traversable and has no other cars
        return self.is_traversable(cell) and not any(isinstance(agent, Car) for agent in cell.agents)
    
    def is_at_destination(self):
        """Checks if the car has reached its destination"""
        return any(isinstance(agent, Destination) for agent in self.cell.agents)

    def is_near_traffic_light(self, distance):
        """Checks if car is within 'distance' cells of a traffic light (ahead or just passed)"""
        if not self.path or self.current_step_in_path >= len(self.path):
            return False
        
        # Check current cell
        if self.has_traffic_light(self.cell):
            return True
        
        # Check previous cell (just passed)
        if self.current_step_in_path > 0 and self.has_traffic_light(self.path[self.current_step_in_path - 1]):
            return True
        
        # Check upcoming cells in path
        return any(self.has_traffic_light(self.path[i]) 
                   for i in range(self.current_step_in_path, min(self.current_step_in_path + distance, len(self.path))))
    
    def can_change_lane(self):
        """Check if car can change to a parallel lane"""
        if not self.waiting or self.stuck_steps < 3 or not self.facing_direction:
            return None
        
        # Check parallel lanes
        for perp_dir in self.PERPENDICULAR.get(self.facing_direction, []):
            dx, dy = self.DIRECTION_OFFSETS[perp_dir]
            neighbor_cell = self._get_neighbor_cell(self.cell.coordinate[0] + dx, self.cell.coordinate[1] + dy)
            
            if neighbor_cell:
                # Check if it's a valid road in the same direction
                for agent in neighbor_cell.agents:
                    if isinstance(agent, Road) and self.facing_direction in agent.directions:
                        if self.can_move_to_cell(neighbor_cell):
                            if self.heuristic(neighbor_cell, self.destination) <= self.heuristic(self.cell, self.destination):
                                return neighbor_cell
        
        return None

    def get_turn_direction(self, current_cell, next_cell):
        """Determine if car is going straight, left, or right"""
        if not self.facing_direction or not self.path or self.current_step_in_path >= len(self.path) - 1:
            return "straight"
        
        # Get next direction
        dx = next_cell.coordinate[0] - current_cell.coordinate[0]
        dy = next_cell.coordinate[1] - current_cell.coordinate[1]
        direction_map = {v: k for k, v in self.DIRECTION_OFFSETS.items()}
        next_direction = direction_map.get((dx, dy), self.facing_direction)
        
        # Determine turn type
        if next_direction == self.facing_direction:
            return "straight"
        elif next_direction in self.PERPENDICULAR.get(self.facing_direction, []):
            # Determine left vs right based on current direction
            if self.facing_direction == "Up":
                return "left" if next_direction == "Left" else "right"
            elif self.facing_direction == "Down":
                return "left" if next_direction == "Right" else "right"
            elif self.facing_direction == "Left":
                return "left" if next_direction == "Down" else "right"
            else:  # Right
                return "left" if next_direction == "Up" else "right"
        
        return "straight"

    def is_at_intersection(self):
        """Check if car is at a traffic light intersection"""
        return self.has_traffic_light(self.cell)

    def get_cars_at_same_intersection(self):
        """Get all cars at the same intersection (within traffic light radius)"""
        if not self.is_at_intersection():
            return []
        
        cars_at_intersection = []
        x, y = self.cell.coordinate
        
        # Check 2-cell radius for other cars at traffic lights
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                neighbor = self._get_neighbor_cell(x + dx, y + dy)
                if neighbor and self.has_traffic_light(neighbor):
                    for agent in neighbor.agents:
                        if isinstance(agent, Car) and agent != self and agent.waiting:
                            cars_at_intersection.append(agent)
        
        return cars_at_intersection

    def has_right_of_way(self):
        """Determine if this car has right-of-way at intersection"""
        if not self.is_at_intersection():
            return True  # Not at intersection, can move freely
        
        # Check traffic light state first
        traffic_light = next((a for a in self.cell.agents if isinstance(a, Traffic_Light)), None)
        if traffic_light and not traffic_light.state:
            return False
        
        # Set arrival time if just arrived
        if self.arrival_time_at_intersection is None:
            self.arrival_time_at_intersection = self.model.steps
        
        # Get other cars at intersection
        other_cars = self.get_cars_at_same_intersection()
        
        if not other_cars:
            return True
        
        # Update turn direction
        if self.path and self.current_step_in_path < len(self.path):
            next_cell = self.path[self.current_step_in_path]
            self.turn_direction = self.get_turn_direction(self.cell, next_cell)
        
        # Rule 1: First to arrive, first to go
        earliest_arrival = min((c.arrival_time_at_intersection for c in other_cars 
                               if c.arrival_time_at_intersection is not None), 
                              default=self.model.steps + 1)
        
        if self.arrival_time_at_intersection < earliest_arrival:
            return True
        
        # Rule 2: Tie goes to the right
        cars_arrived_same_time = [c for c in other_cars 
                                  if c.arrival_time_at_intersection == self.arrival_time_at_intersection]
        
        if cars_arrived_same_time:
            # Check if any car is to my right (based on facing direction)
            for other_car in cars_arrived_same_time:
                if self.is_car_to_my_right(other_car):
                    return False
            
            # Rule 3 & 4: Handle straight vs turns
            for other_car in cars_arrived_same_time:
                if self.is_across_from(other_car):
                    # Both going straight - both can go
                    if self.turn_direction == "straight" and other_car.turn_direction == "straight":
                        return True
                    
                    # One straight, one turning - straight goes first
                    if self.turn_direction != "straight" and other_car.turn_direction == "straight":
                        return False
                    
                    # Both turning - right turn has priority
                    if self.turn_direction == "left" and other_car.turn_direction == "right":
                        return False
        
        return True

    def is_car_to_my_right(self, other_car):
        """Check if another car is to the right of this car at intersection"""
        if not self.facing_direction or not other_car.facing_direction:
            return False
        
        dx = other_car.cell.coordinate[0] - self.cell.coordinate[0]
        dy = other_car.cell.coordinate[1] - self.cell.coordinate[1]
        
        # Determine relative position based on facing direction
        if self.facing_direction == "Up":
            return dx > 0  # Right is positive x
        elif self.facing_direction == "Down":
            return dx < 0  # Right is negative x
        elif self.facing_direction == "Left":
            return dy < 0  # Right is negative y
        elif self.facing_direction == "Right":
            return dy > 0  # Right is positive y
        
        return False

    def is_across_from(self, other_car):
        """Check if another car is directly across the intersection"""
        if not self.facing_direction or not other_car.facing_direction:
            return False
        
        # Cars are across if facing opposite directions
        opposite_dir = {"Up": "Down", "Down": "Up", "Left": "Right", "Right": "Left"}
        return other_car.facing_direction == opposite_dir.get(self.facing_direction)
    
"""
=======================================================================================================================
End of Car class
=======================================================================================================================
"""

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
    def __init__(self, unique_id, model, cell, direction="Left"):
        """
        Creates a new road.
        Args:
            model: Model reference for the agent
            cell: The initial position of the agent
        """
        super().__init__(model)
        self.cell = cell
        self.unique_id = unique_id
        
        # Parse multi-directional roads
        self.directions = direction.replace("_and_", " ").split() if "_and_" in direction else [direction]
