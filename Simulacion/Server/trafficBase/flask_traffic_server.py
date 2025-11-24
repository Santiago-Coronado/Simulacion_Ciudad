# TC2008B. Sistemas Multiagentes y Gráficas Computacionales
# Python flask server to interact with webGL.

from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from traffic_base.model import CityModel
from traffic_base.agent import Car, Obstacle, Traffic_Light, Destination, Road

# Size of the board:
number_agents = 10
width = 28
height = 28 
cityModel = None
currentStep = 0

# This application will be used to interact with WebGL
app = Flask("Traffic example")
cors = CORS(app, origins=['http://localhost'])

# This route will be used to send the parameters of the simulation to the server.
@app.route('/init', methods=['GET', 'POST'])
@cross_origin()
def initModel():
    global currentStep, cityModel, number_agents, width, height

    if request.method == 'POST':
        try:
            number_agents = int(request.json.get('NAgents'))
            currentStep = 0

        except Exception as e:
            print(e)
            return jsonify({"message": "Error initializing the model"}), 500

    print(f"Model parameters:{number_agents}")

    # Create the model using the parameters sent by the application
    cityModel = CityModel(number_agents)

    width = cityModel.width
    height = cityModel.height

    # Return a message to saying that the model was created successfully
    return jsonify({"message": f"Parameters recieved, model initiated.\nSize: {width}x{height}"})


# This route will be used to get the positions of the agents
@app.route('/getAgents', methods=['GET'])
@cross_origin()
def getAgents():
    global cityModel

    if request.method == 'GET':
        try:
            agentCells = cityModel.grid.all_cells.select(
                lambda cell: any(isinstance(obj, Car) for obj in cell.agents)
            ).cells

            agents = [
                (cell.coordinate, agent)
                for cell in agentCells
                for agent in cell.agents
                if isinstance(agent, Car)
            ]

            agentPositions = [
                {"id": str(a.unique_id), "x": coordinate[0], "y":1, "z":coordinate[1]}
                for (coordinate, a) in agents
            ]

            return jsonify({'positions': agentPositions})
        except Exception as e:
            print(e)
            return jsonify({"message": "Error with the agent positions"}), 500

# This route will be used to get the positions of the obstacles
@app.route('/getObstacles', methods=['GET'])
@cross_origin()
def getObstacles():
    global cityModel

    if request.method == 'GET':
        try:
            obstacleCells = cityModel.grid.all_cells.select(
                lambda cell: any(isinstance(obj, Obstacle) for obj in cell.agents)
            )

            agents = [
                (cell.coordinate, agent)
                for cell in obstacleCells
                for agent in cell.agents
                if isinstance(agent, Obstacle)
            ]

            obstaclePositions = [
                {"id": str(a.unique_id), "x": coordinate[0], "y":1, "z":coordinate[1]}
                for (coordinate, a) in agents
            ]

            return jsonify({'positions': obstaclePositions})
        except Exception as e:
            print(e)
            return jsonify({"message": "Error with obstacle positions"}), 500

# This route will be used to get the positions and states of traffic lights
@app.route('/getTrafficLights', methods=['GET'])
@cross_origin()
def getTrafficLights():
    global cityModel

    if request.method == 'GET':
        try:
            trafficLightCells = cityModel.grid.all_cells.select(
                lambda cell: any(isinstance(obj, Traffic_Light) for obj in cell.agents)
            )

            trafficLights = [
                (cell.coordinate, agent)
                for cell in trafficLightCells
                for agent in cell.agents
                if isinstance(agent, Traffic_Light)
            ]

            trafficLightPositions = [
                {
                    "id": str(a.unique_id), 
                    "x": coordinate[0], 
                    "y": 1, 
                    "z": coordinate[1],
                    "state": a.state,
                    "timeToChange": a.timeToChange
                }
                for (coordinate, a) in trafficLights
            ]

            return jsonify({'positions': trafficLightPositions})
        except Exception as e:
            print(e)
            return jsonify({"message": "Error with traffic light positions"}), 500

# This route will be used to get the positions of destinations
@app.route('/getDestinations', methods=['GET'])
@cross_origin()
def getDestinations():
    global cityModel

    if request.method == 'GET':
        try:
            destinationCells = cityModel.grid.all_cells.select(
                lambda cell: any(isinstance(obj, Destination) for obj in cell.agents)
            )

            destinations = [
                (cell.coordinate, agent)
                for cell in destinationCells
                for agent in cell.agents
                if isinstance(agent, Destination)
            ]

            destinationPositions = [
                {"id": str(a.unique_id), "x": coordinate[0], "y": 1, "z": coordinate[1]}
                for (coordinate, a) in destinations
            ]

            return jsonify({'positions': destinationPositions})
        except Exception as e:
            print(e)
            return jsonify({"message": "Error with destination positions"}), 500

# This route will be used to get the positions and directions of roads
@app.route('/getRoads', methods=['GET'])
@cross_origin()
def getRoads():
    global cityModel

    if request.method == 'GET':
        try:
            roadCells = cityModel.grid.all_cells.select(
                lambda cell: any(isinstance(obj, Road) for obj in cell.agents)
            )

            roads = [
                (cell.coordinate, agent)
                for cell in roadCells
                for agent in cell.agents
                if isinstance(agent, Road)
            ]

            roadPositions = [
                {
                    "id": str(a.unique_id), 
                    "x": coordinate[0], 
                    "y": 0, 
                    "z": coordinate[1],
                    "direction": a.direction
                }
                for (coordinate, a) in roads
            ]

            return jsonify({'positions': roadPositions})
        except Exception as e:
            print(e)
            return jsonify({"message": "Error with road positions"}), 500

# This route will be used to update the model
@app.route('/update', methods=['GET'])
@cross_origin()
def updateModel():
    global currentStep, cityModel
    if request.method == 'GET':
        try:
            if cityModel is None:
                return jsonify({"message": "Model not initialized."}), 400
            cityModel.step()
            currentStep += 1
            return jsonify({'message': f'Model updated to step {currentStep}.', 'currentStep':currentStep})
        except Exception as e:
            print(e)
            return jsonify({"message": "Error during step."}), 500


if __name__=='__main__':
    # Run the flask server in port 8585
    app.run(host="localhost", port=8585, debug=True)