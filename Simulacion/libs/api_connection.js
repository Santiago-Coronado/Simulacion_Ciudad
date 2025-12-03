/*
 * Functions to connect to an external API to get the coordinates of agents
 *
 * Gilberto Echeverria
 * 2025-11-08
 */

'use strict';

import { Object3D } from '../libs/object3d';

// Define the agent server URI
const agent_server_uri = "http://localhost:8585/";

// Initialize arrays to store agents and obstacles
const agents = [];
const obstacles = [];
// Arrays para elementos adicionales del mapa
const trafficLights = [];
const destinations = [];
const roads = [];

// Define the data object
// Parameters equal to randommodel class in other examples
const initData = {
    NAgents: 200
};

/* FUNCTIONS FOR THE INTERACTION WITH THE MESA SERVER */

/*
 * Initializes the agents model by sending a POST request to the agent server.
 */
async function initAgentsModel() {
    try {
        // Send a POST request to the agent server to initialize the model
        let response = await fetch(agent_server_uri + "init", {
            method: 'POST',
            headers: { 'Content-Type':'application/json' },
            body: JSON.stringify(initData)
        });

        // Check if the response was successful
        if (response.ok) {
            // Parse the response as JSON and log the message
            let result = await response.json();
            console.log(result.message);
        }

    } catch (error) {
        // Log any errors that occur during the request
        console.log(error);
    }
}

/*
 * Retrieves the current positions of all agents from the agent server.
 */
async function getAgents() {
    try {
        // Send a GET request to the agent server to retrieve the agent positions
        let response = await fetch(agent_server_uri + "getAgents");

        // Check if the response was successful
        if (response.ok) {
            // Parse the response as JSON
            let result = await response.json();

            // Sincronización inteligente: detectar agentes eliminados en el servidor
            const serverAgentIds = new Set(result.positions.map(a => a.id));
            
            // Remover agentes que ya no existen
            for (let i = agents.length - 1; i >= 0; i--) {
                if (!serverAgentIds.has(agents[i].id)) {
                    agents.splice(i, 1);
                }
            }

            // Create new agents or update existing ones
            for (const agent of result.positions) {
                const current_agent = agents.find((object3d) => object3d.id == agent.id);

                if (current_agent === undefined) {
                    // Crear agente nuevo
                    const newAgent = new Object3D(agent.id, [agent.x, agent.y, agent.z]);
                    // Store the initial position
                    newAgent['oldPosArray'] = [...newAgent.posArray];
                    agents.push(newAgent);
                } else {
                    // Usar setPosition() en lugar de acceso directo a .position
                    // Update the agent's position
                    current_agent.oldPosArray = [...current_agent.posArray];
                    current_agent.setPosition([agent.x, agent.y, agent.z]);
                }
            }
        }

    } catch (error) {
        // Log any errors that occur during the request
        console.log(error);
    }
}

/*
 * Retrieves the current positions of all obstacles from the agent server.
 */
async function getObstacles() {
    try {
        // Send a GET request to the agent server to retrieve the obstacle positions
        let response = await fetch(agent_server_uri + "getObstacles");

        // Check if the response was successful
        if (response.ok) {
            // Parse the response as JSON
            let result = await response.json();

            // Create new obstacles and add them to the obstacles array
            for (const obstacle of result.positions) {
                const newObstacle = new Object3D(obstacle.id, [obstacle.x, obstacle.y, obstacle.z]);
                obstacles.push(newObstacle);
            }
        }

    } catch (error) {
        // Log any errors that occur during the request
        console.log(error);
    }
}

// ============================================================
// OBTENCIÓN INICIAL DE SEMÁFOROS
// DESCRIPCIÓN: Solicita al servidor los semáforos y sus estados
// Se llama una sola vez durante la inicialización
// ============================================================
async function getTrafficLights() {
    try {
        let response = await fetch(agent_server_uri + "getTrafficLights");

        if (response.ok) {
            let result = await response.json();

            // Crear objeto 3D para cada semáforo
            for (const light of result.positions) {
                const newLight = new Object3D(light.id, [light.x, light.y, light.z]);
                // Guardar estado (true=verde, false=rojo)
                newLight.state = light.state;
                // Guardar intervalo de cambio
                newLight.timeToChange = light.timeToChange;
                trafficLights.push(newLight);
            }
        }
    } catch (error) {
        console.log(error);
    }
}

// ============================================================
// ACTUALIZACIÓN DE ESTADOS DE SEMÁFOROS
// DESCRIPCIÓN: Sincroniza los estados de los semáforos con el servidor
// Se llama cada ciclo de simulación para actualizar colores dinámicamente
// ============================================================
async function updateTrafficLights() {
    try {
        let response = await fetch(agent_server_uri + "getTrafficLights");

        if (response.ok) {
            let result = await response.json();
            // Crear mapa para búsqueda rápida
            const serverTrafficLights = new Map(result.positions.map(tl => [tl.id, tl]));

            // Actualizar estados locales con datos del servidor
            for (const trafficLight of trafficLights) {
                const serverData = serverTrafficLights.get(trafficLight.id);
                if (serverData) {
                    // Actualizar estado del semáforo
                    trafficLight.state = serverData.state;
                    // Actualizar intervalo de cambio
                    trafficLight.timeToChange = serverData.timeToChange;
                }
            }
        }
    } catch (error) {
        console.log(error);
    }
}

// ============================================================
// OBTENCIÓN DE DESTINOS
// DESCRIPCIÓN: Solicita al servidor la ubicación de todos los destinos
// Se llama una sola vez durante la inicialización
// ============================================================
async function getDestinations() {
    try {
        let response = await fetch(agent_server_uri + "getDestinations");

        if (response.ok) {
            let result = await response.json();

            // Crear objeto 3D para cada destino
            for (const dest of result.positions) {
                const newDest = new Object3D(dest.id, [dest.x, dest.y, dest.z]);
                destinations.push(newDest);
            }
        }
    } catch (error) {
        console.log(error);
    }
}

// ============================================================
// OBTENCIÓN DE CARRETERAS
// DESCRIPCIÓN: Solicita al servidor las carreteras y sus direcciones
// Se llama una sola vez durante la inicialización
// ============================================================
async function getRoads() {
    try {
        let response = await fetch(agent_server_uri + "getRoads");

        if (response.ok) {
            let result = await response.json();

            // Crear objeto 3D para cada carretera
            for (const road of result.positions) {
                const newRoad = new Object3D(road.id, [road.x, road.y, road.z]);
                // Guardar dirección permitida en esa carretera
                newRoad.direction = road.direction;
                roads.push(newRoad);
            }
        }
    } catch (error) {
        console.log(error);
    }
}

/*
 * Updates the agent positions by sending a request to the agent server.
 */
async function update() {
    try {
        // Send a request to the agent server to update the agent positions
        let response = await fetch(agent_server_uri + "update");

        // Check if the response was successful
        if (response.ok) {
            // Retrieve the updated agent positions
            await getAgents();
            // Sincronizar estados de semáforos en cada actualización
            await updateTrafficLights();
        }

    } catch (error) {
        // Log any errors that occur during the request
        console.log(error);
    }
}

export { agents, obstacles, roads, trafficLights, destinations, 
    initAgentsModel, update, getAgents, getObstacles, getTrafficLights, 
    getDestinations, getRoads, updateTrafficLights };