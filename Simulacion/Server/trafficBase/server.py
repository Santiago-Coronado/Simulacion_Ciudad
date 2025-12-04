from traffic_base.agent import *
from traffic_base.model import CityModel

from mesa.visualization import Slider, SolaraViz, make_space_component, make_plot_component
from mesa.visualization.components import AgentPortrayalStyle


def agent_portrayal(agent):

    if agent is None:
        return
 
    portrayal = AgentPortrayalStyle(
        marker="s",
    )

    if isinstance(agent, Road):
        portrayal.color = "#aaa"

    if isinstance(agent, Destination):
        portrayal.color = "lightgreen"

    if isinstance(agent, Traffic_Light):
        portrayal.color = "red" if not agent.state else "green"

    if isinstance(agent, Obstacle):
        portrayal.color = "#555"
    
    if isinstance(agent, Car):
        if agent.dying:
            portrayal.color = "gray"
        elif agent.waiting:
            portrayal.color = "yellow"
        elif agent.moving:
            portrayal.color = "blue"
        else:
            portrayal.color = "black"

    return portrayal

def post_process_space(ax):
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def post_process_lines(ax):
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.9))


model = CityModel(N=10, spawn_frequency=10, seed=42)

# Define the colors for the line plot
COLORS = {
    "Active Cars": "blue",
    "Cars Spawned": "orange",
    "Cars Reached Destination": "green",
}

model_params = {
    "N": Slider("Maximum Cars", 10, 1, 100),
    "spawn_frequency": Slider("Spawn Every N Steps", 10, 1, 10),
    "seed": {
        "type": "InputText",
        "value": 42,
        "label": "Random Seed",
    },
    
}

# Create the space component
space_component = make_space_component(
    agent_portrayal,
    draw_grid=False,
    post_process=post_process_space,
)

# Create the line plot component
lineplot_component_1 = make_plot_component(
    COLORS,
    post_process=post_process_lines,
)

page = SolaraViz(
    model,
    components=[space_component, lineplot_component_1],
    model_params=model_params,
    name="Traffic Simulation",
)
