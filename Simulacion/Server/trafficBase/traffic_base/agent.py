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

    def die(self):
        """ 
        Makes the car disappear
        """
        self.dying = True

        if self.is_at_destination():
            self.model.cars_reached_destination += 1
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
        Calculates the route to the destination using centralized pathfinding
        """
        self.calculating = True

        if not self.destination:
            self.calculating = False
            return
        
        # Use model centralized pathfinding
        self.path = self.model.find_path(self.cell, self.destination, car=self)
        
        if self.path:
            self.current_step_in_path = 0
            self.calculating = False
            self.failed_pathfinding_attempts = 0

            if self.facing_direction is None and len(self.path) > 0:
                next_cell = self.path[0]
                dx = next_cell.coordinate[0] - self.cell.coordinate[0]
                dy = next_cell.coordinate[1] - self.cell.coordinate[1]
                direction_map = {v: k for k, v in self.DIRECTION_OFFSETS.items()}
                self.facing_direction = direction_map.get((dx, dy))
        else:
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
        
         # Emergency exit if stuck too long on traffic light
        if self.stuck_steps >= 10 and self.has_traffic_light(self.cell):
            print(f"Car {self.unique_id} emergency exit from traffic light after {self.stuck_steps} stuck steps")
            x, y = self.cell.coordinate
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                    next_cell = self.model.grid[(nx, ny)]
                    if self.can_move_to_cell(next_cell) and self.is_traversable(next_cell):
                        self.cell = next_cell
                        self.stuck_steps = 0
                        self.path = []
                        self.position_history.clear()
                        self.current_step_in_path = 0
                        self.calculate_route()
                        return
            # If no valid exit found, try recalculating
            self.path = []
            self.current_step_in_path = 0
            self.calculate_route()
            return
        
        # Priority 2: Calculate route if not done yet
        if not self.path and not self.calculating:
            self.calculate_route()

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
                self.stop()
                self.stuck_steps += 1

            is_blocked_by_car = any(isinstance(agent, Car) for agent in next_cell.agents)
            has_traffic_light = any(isinstance(agent, Traffic_Light) for agent in next_cell.agents)

            if is_blocked_by_car and not has_traffic_light and not self.is_near_traffic_light(1):
                    blocking_car_waiting = any(isinstance(agent, Car) and agent.waiting for agent in next_cell.agents)
                    if blocking_car_waiting:
                        # Recalculate immediately to find alternative route
                        self.path = []
                        self.current_step_in_path = 0
                        self.position_history.clear()
                        self.calculate_route()
                        self.stuck_steps = 0
                        return
                    
                    # Try lane change second
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
        
        # Priority 5: Try lane change if stuck (not at traffic lights)
        if self.waiting and self.stuck_steps >= 2 and not self.is_near_traffic_light(1):
            lane_change_cell = self.can_change_lane()
            if lane_change_cell:
                self.cell = lane_change_cell
                self.stuck_steps = 0
                self.path = []
                self.position_history.clear()
                self.current_step_in_path = 0
                self.calculate_route()
                return
        
        # Priority 6: Recalculate if stuck too long
        if self.stuck_steps >= 5 and not self.is_near_traffic_light(2):
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
    def has_traffic_light(self, cell):
        """Check if cell has a traffic light"""
        return any(isinstance(agent, Traffic_Light) for agent in cell.agents)
    
    def has_road(self, cell):
        """Check if cell has a road"""
        return any(isinstance(agent, Road) for agent in cell.agents)
    
    def _get_neighbor_cell(self, x, y):
        """Get cell at coordinates if valid"""
        if 0 <= x < self.model.grid.width and 0 <= y < self.model.grid.height:
            return self.model.grid[(x, y)]
        return None

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
        
        # Check if target cell is traversable and has no other cars
        if not self.is_traversable(cell) or any(isinstance(agent, Car) for agent in cell.agents):
            return False
        
        # If on top of a traffic light, can always move off it
        if self.has_traffic_light(self.cell):
            return True
        
        # Only block movement if ENTERING a red light (not when leaving one)
        if self.has_traffic_light(cell):
            for agent in cell.agents:
                if isinstance(agent, Traffic_Light) and not agent.state:
                    # Only block if we're NOT already on a traffic light
                    if not self.has_traffic_light(self.cell):
                        return False
        
        return True
    
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
                # Check if it is a valid road in the same direction
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
