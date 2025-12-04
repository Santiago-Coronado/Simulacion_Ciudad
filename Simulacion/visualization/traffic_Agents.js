/*
 * Program for a 3D scene that connects to an API to get the movement
 * of agents with Phong lighting.
 * The scene shows some tron-inspired lightcycles, buildings, traffic 
 * lights and even bits from the 1980s film.
 *
 * Luis Emilio Velediaz & Santiago Coronado
 * 2025-11
 */

'use strict';

import * as twgl from 'twgl-base.js';
import GUI from 'lil-gui';
import { M4 } from '../libs/3d-lib.js';
import { Scene3D } from '../libs/scene3d.js';
import { Object3D } from '../libs/object3d.js';
import { Light3D } from '../libs/light3d.js';
import { Camera3D } from '../libs/camera3d.js';

// Functions and arrays for the communication with the API
import { loadObj, loadMtl } from '../libs/obj_loader.js';
import {
  agents, obstacles, trafficLights, destinations, roads,
  initAgentsModel, update, 
  getAgents, getObstacles, getTrafficLights, getDestinations, getRoads,
  updateTrafficLights
} from '../libs/api_connection.js';

// Define the shader code with Phong lighting
import vsGLSL from '../assets/shaders/vs_phong_302.glsl?raw';
import fsGLSL from '../assets/shaders/fs_phong_302.glsl?raw';

const scene = new Scene3D();

// Global variables
let phongProgramInfo = undefined; 
let gl = undefined;
const duration = 1000; // ms
let elapsed = 0;
let then = 0;
let baseCubeRef = null;
let cycleTemplate = null;

// Bit object orbiting the cycles
let bitTemplate = null;
let bitSpeed = 0.005; // Bit rotation speed
let startTimeGlobal = Date.now(); // Global time for rotation

let sphereTemplate = null;
let mapDirections = {};

// ============================================================
// BUILDING MODELS CONFIGURATION
// Dictionary defining paths, scales and offsets for buildings
// ============================================================
const BUILDING_MODELS = {
  untitled: {
    path: '../assets/models/Untitled.obj',
    mtl: '../assets/models/Untitled.mtl',
    scale: 0.04,
    offset: -1
  },
  building2: {
    path: '../assets/models/building2.obj',
    mtl: '../assets/models/building2.mtl',
    scale: 0.03,
    offset: -1
  },
  building3: {
    path: '../assets/models/building3.obj',
    mtl: '../assets/models/building3.mtl',
    scale: 0.05,
    offset: -1
  },
  building4: {
    path: '../assets/models/building4.obj',
    mtl: '../assets/models/building4.mtl',
    scale: 0.04,
    offset: -1
  },
  building5: {
    path: '../assets/models/building5.obj',
    mtl: '../assets/models/building5.mtl',
    scale: 0.04,
    offset: -1
  }
};

// ============================================================
// CYCLE MODEL CONFIGURATION
// Parameters for the TRON 3D model representing agents
// ============================================================
const CYCLE_MODEL = {
  path: '../assets/models/tron (1).obj',
  mtl: '../assets/models/tron (1).mtl',
  scale: 0.15,
  offset: { x: 0, y: -1, z: 0 } 
};

// ============================================================
// BIT MODEL CONFIGURATION
// Parameters for the bit model orbiting the cycles
// ============================================================
const BIT_MODEL = {
  path: '../assets/models/bit.obj',
  mtl: '../assets/models/bit.mtl',
  scale: 0.06,
  radius: 0.4,
  heightOffset: -0.5
};

// ============================================================
// OBJ LOADING UTILITY
// Loads and parses OBJ/MTL files, calculating bounding box
// to center the model geometry
// ============================================================
async function loadObjModel(objFilePath, mtlFilePath = null, modelName = "model") {
    try {
        // Load .mtl file if it exists
        if (mtlFilePath) {
            try {
                const mtlResponse = await fetch(mtlFilePath);
                
                if (mtlResponse.ok) {
                    const mtlString = await mtlResponse.text();
                    // Parse MTL file materials
                    loadMtl(mtlString);
                } else {
                    console.warn('Could not load MTL:', mtlResponse.status);
                }
            } catch (mtlError) {
                console.warn('Error loading MTL:', mtlError);
            }
        }

       // Load .obj file
        const objResponse = await fetch(objFilePath);
        
        if (!objResponse.ok) {
            console.error('HTTP Error:', objResponse.status, objResponse.statusText);
            return null;
        }
        
        const objString = await objResponse.text();
        // Parse OBJ file content
        let objArrays = loadObj(objString);
        
        // Center the model by calculating its bounding box (a concept pretty similar to last semester's videogame) (THE CURSED RETURN FOR THE WIN!!!!)
        if (objArrays.a_position && objArrays.a_position.data && objArrays.a_position.data.length > 0) {
            const positions = objArrays.a_position.data;
            
            // Find model min and max limits
            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;
            let minZ = Infinity, maxZ = -Infinity;
            
            for (let i = 0; i < positions.length; i += 3) {
                minX = Math.min(minX, positions[i]);
                maxX = Math.max(maxX, positions[i]);
                minY = Math.min(minY, positions[i + 1]);
                maxY = Math.max(maxY, positions[i + 1]);
                minZ = Math.min(minZ, positions[i + 2]);
                maxZ = Math.max(maxZ, positions[i + 2]);
            }
            
            // Center on X and Z, but floor on Y
            const centerX = (minX + maxX) / 2;
            const centerZ = (minZ + maxZ) / 2;
            const floorY = minY;
            
            // Re-center all vertices by subtracting the center
            for (let i = 0; i < positions.length; i += 3) {
                positions[i] -= centerX;
                positions[i + 1] -= floorY;
                positions[i + 2] -= centerZ;
            }
        }
        
        return objArrays;
    } catch (error) {
        console.error(`Error loading OBJ model for ${modelName}:`, error);
        return null;
    }
}

// ============================================================
// RANDOM BUILDING SELECTOR
// Selects a random building model from the loaded collection
// ============================================================
function getRandomBuilding(loadedBuildingModels) {
  const buildingKeys = Object.keys(loadedBuildingModels);
  
  if (buildingKeys.length === 0) {
    return null;
  }
  
  // Select random index
  const randomKey = buildingKeys[Math.floor(Math.random() * buildingKeys.length)];
  return loadedBuildingModels[randomKey];
}

// Main function is async to be able to make the requests
async function main() {
  // Setup the canvas area
  const canvas = document.querySelector('canvas');
  gl = canvas.getContext('webgl2');
  twgl.resizeCanvasToDisplaySize(gl.canvas);
  gl.viewport(0, 0, gl.canvas.width, gl.canvas.height);

  // Prepare the program with the shaders
  phongProgramInfo = twgl.createProgramInfo(gl, [vsGLSL, fsGLSL]);

  // Initialize the agents model
  await initAgentsModel();

  // Get all elements from the model
  await getAgents();
  await getObstacles();
  await getTrafficLights();
  await getDestinations();
  await getRoads();

  // Initialize the scene
  setupScene();

  // Position the objects in the scene
  await setupObjects(scene, gl, phongProgramInfo);

  // Fisrt call to the drawing loop
  drawScene();
}

function setupScene() {
  let camera = new Camera3D(0,
    40,             // Distance to target
    4,              // Azimut
    1.2,            // Elevation
    [14, 0, 14],    // Target (center of the grid)
    [0, 0, 0]);
  camera.panOffset = [0, 8, 0];
  scene.setCamera(camera);
  scene.camera.setupControls();

  // === MAIN SCENE LIGHT ===
  let mainLight = new Light3D(0, [20, 20, 20],       // Position
                             [0.6, 0.6, 0.6, 1.0],   // Ambient
                             [0.7, 0.7, 0.7, 1.0],   // Diffuse
                             [0.6, 0.6, 0.6, 1.0]);  // Specular
  scene.addLight(mainLight);
}

// ============================================================
// SCENE OBJECTS SETUP
// Loads models, creates VAOs and configures visual properties
// for all entities (Agents, Buildings, Traffic Lights, etc.)
// ============================================================
async function setupObjects(scene, gl, programInfo) {
  
  // Create VAOs for the different shapes
  const baseCube = new Object3D(-1);
  baseCube.prepareVAO(gl, programInfo);
  baseCubeRef = baseCube;

  // === LOAD CYCLE MODEL ===
  const cycleModel = await loadObjModel(
    CYCLE_MODEL.path,
    CYCLE_MODEL.mtl,
    'cycle'
  );

  if (cycleModel) {
    try {
      // Create model buffer info
      const cycleBufferInfo = twgl.createBufferInfoFromArrays(gl, cycleModel);
      // Create VAO for the model
      const cycleVAO = gl.createVertexArray();
      gl.bindVertexArray(cycleVAO);
      // Bind attributes to VAO
      twgl.setBuffersAndAttributes(gl, programInfo, cycleBufferInfo);
      
      // Save template for reuse
      cycleTemplate = {
        arrays: cycleModel,
        bufferInfo: cycleBufferInfo,
        vao: cycleVAO
      };
    } catch (error) {
      console.error('Error creating Cycle VAO:', error);
      cycleTemplate = null;
    }
  } else {
    cycleTemplate = null;
  }

  // === LOAD BIT MODEL ===
  const bitModel = await loadObjModel(
    BIT_MODEL.path,
    BIT_MODEL.mtl,
    'bit'
  );

  if (bitModel) {
    try {
      // Create model buffer info
      const bitBufferInfo = twgl.createBufferInfoFromArrays(gl, bitModel);
      // Create VAO for the model
      const bitVAO = gl.createVertexArray();
      gl.bindVertexArray(bitVAO);
      // Bind attributes to VAO
      twgl.setBuffersAndAttributes(gl, programInfo, bitBufferInfo);
      
      // Save template for reuse
      bitTemplate = {
        arrays: bitModel,
        bufferInfo: bitBufferInfo,
        vao: bitVAO
      };
    } catch (error) {
      console.error('Error creating Bit VAO:', error);
      bitTemplate = null;
    }
  } else {
    bitTemplate = null;
  }

  // === LOAD BUILDING MODELS ===
  const loadedBuildingModels = {};

  for (const [buildingKey, buildingConfig] of Object.entries(BUILDING_MODELS)) {
    const model = await loadObjModel(
      buildingConfig.path,
      buildingConfig.mtl,
      buildingKey
    );
    
    if (model) {
      // Store model and config
      loadedBuildingModels[buildingKey] = {
        arrays: model,
        bufferInfo: twgl.createBufferInfoFromArrays(gl, model),
        config: buildingConfig
      };
    }
  }

  // === LOAD TRAFFIC LIGHT MODEL ===
  const trafficLightModel = await loadObjModel(
    '../assets/models/tl.obj',
    '../assets/models/tl.mtl',
    'semáforos'
  );

  let trafficLightVAO = null;
  let trafficLightBufferInfo = null;
  let trafficLightArrays = null;

  if (trafficLightModel) {
    trafficLightArrays = trafficLightModel;
    
    try {
       // Create model buffer info
      trafficLightBufferInfo = twgl.createBufferInfoFromArrays(gl, trafficLightModel);
      // Create VAO for the model
      trafficLightVAO = gl.createVertexArray();
      gl.bindVertexArray(trafficLightVAO);
      // Bind attributes to VAO
      twgl.setBuffersAndAttributes(gl, programInfo, trafficLightBufferInfo);
    } catch (error) {
      console.error('Error creating Traffic Light VAO:', error);
      trafficLightVAO = null;
    }
  }

  // === LOAD SPHERE MODEL ===
  const sphereModel = await loadObjModel(
    '../assets/models/sphere.obj',
    '../assets/models/sphere.mtl',
    'esfera'
  );

  let sphereVAO = null;
  let sphereBufferInfo = null;
  let sphereArrays = null;

  if (sphereModel) {
    sphereArrays = sphereModel;
    
    try {
      // Create model buffer info
      sphereBufferInfo = twgl.createBufferInfoFromArrays(gl, sphereModel);
      // Create VAO for the model
      sphereVAO = gl.createVertexArray();
      gl.bindVertexArray(sphereVAO);
     // Bind attributes to VAO
      twgl.setBuffersAndAttributes(gl, programInfo, sphereBufferInfo);
      sphereTemplate = {
              arrays: sphereModel,
              bufferInfo: sphereBufferInfo,
              vao: sphereVAO
            };
          } catch (error) {
            console.error('Error creating Sphere VAO:', error);
            sphereVAO = null;
          }
        }

  // === SETUP ROADS ===
  mapDirections = {}; // Clear map dictionary

  for (const road of roads) {
    // Generate key for map dictionary using grid coordinates
    const key = `${Math.floor(road.posArray[0])},${Math.floor(road.posArray[2])}`;
    
    // Store direction or default value
    mapDirections[key] = road.direction || "Down"; 

    // Visual setup
    road.arrays = baseCube.arrays;
    road.bufferInfo = baseCube.bufferInfo;
    road.vao = baseCube.vao;
    road.scale = { x: 1, y: 0.02, z: 1 };
    road.color = [0.1, 0.1, 0.1, 1.0];
    road.shininess = 32;
    scene.addObject(road);
  }

  // === SETUP OBSTACLES ===
  for (const obstacle of obstacles) {
    // Assign random building model
    const randomBuilding = getRandomBuilding(loadedBuildingModels);
    
    if (randomBuilding) {
      // Copy model data
      obstacle.arrays = randomBuilding.arrays;
      obstacle.bufferInfo = randomBuilding.bufferInfo;
      obstacle.vao = randomBuilding.vao || gl.createVertexArray();
      
      // Apply configuration
      const scale = randomBuilding.config.scale;
      obstacle.scale = { x: scale, y: scale, z: scale };
      obstacle.positionOffset = { x: 0, y: randomBuilding.config.offset, z: 0 };
      
      // Initialize VAO if needed
      if (!randomBuilding.vao) {
        randomBuilding.vao = obstacle.vao;
        gl.bindVertexArray(obstacle.vao);
        twgl.setBuffersAndAttributes(gl, programInfo, randomBuilding.bufferInfo);
      }
    } else {
      // Fallback to simple cube
      obstacle.arrays = baseCube.arrays;
      obstacle.bufferInfo = baseCube.bufferInfo;
      obstacle.vao = baseCube.vao;
      obstacle.scale = { x: 1, y: 3, z: 1 };
      obstacle.positionOffset = { x: 0, y: 0, z: 0 };
    }
    
    obstacle.color = [0.5, 0.5, 0.5, 1.0];
    obstacle.shininess = 16;
    scene.addObject(obstacle);
  }

  // Setup destinations
  for (const destination of destinations) {
    destination.arrays = baseCube.arrays;
    destination.bufferInfo = baseCube.bufferInfo;
    destination.vao = baseCube.vao;
    destination.scale = { x: 1, y: 0.1, z: 1 };
    destination.color = [0.0, 1.0, 0.0, 1.0];
    destination.shininess = 16;
    scene.addObject(destination);
  }

  // Setup traffic lights
  for (const trafficLight of trafficLights) {
    if (trafficLightVAO) {
      // Use imported model
      trafficLight.arrays = trafficLightArrays;
      trafficLight.bufferInfo = trafficLightBufferInfo;
      trafficLight.vao = trafficLightVAO;
      trafficLight.scale = { x: 1.5, y: 1.5, z: 1.5 };
    } else {
      // Fallback
      trafficLight.arrays = baseCube.arrays;
      trafficLight.bufferInfo = baseCube.bufferInfo;
      trafficLight.vao = baseCube.vao;
      trafficLight.scale = { x: 0.3, y: 0.8, z: 0.3 };
    }
    
    trafficLight.shininess = 128;
    trafficLight.isLight = true;
    trafficLight.lightRange = 2.0;
    
    updateTrafficLightColor(trafficLight);
    scene.addObject(trafficLight);
  }

  // === SETUP EMISSIVE SPHERES ===
  // Attach emissive sphere to traffic lights
  for (const trafficLight of trafficLights) {
    if (sphereVAO) {
      const sphere = new Object3D(trafficLight.id + "_sphere", trafficLight.posArray);
      sphere.arrays = sphereArrays;
      sphere.bufferInfo = sphereBufferInfo;
      sphere.vao = sphereVAO;
      sphere.scale = { x: 0.08, y: 0.08, z: 0.08 };
      
      // Position on top
      sphere.positionOffset = { x: 0, y: 0.29, z: 0 };
      
      // Set emissive properties
      sphere.isEmissive = true;
      
      if (trafficLight.state === true) {
        sphere.color = [0.635, 0.827, 0.851, 1.0];
        sphere.emissiveColor = [0.254, 0.331, 0.341];
      } else {
        sphere.color = [0.957, 0.776, 0.310, 1.0];
        sphere.emissiveColor = [0.254, 0.331, 0.341];
      }
      
      sphere.shininess = 2500;
      scene.addObject(sphere);
      
      trafficLight.sphere = sphere;
    }
  }

  // Setup cycles/agents
  syncCycles();
  
  // Initialize direction flags
  for (const agent of agents) {
    if (agent._addedToScene && !agent._directionSet) {
      agent.rotDeg.y = 0;
      agent.rotRad.y = 0;
      agent._directionSet = true;
    }
  }
}

// ============================================================
// CYCLE SYNCRONIZATION
// Handles cycle instantiation, spawn orientation based on map,
// movement interpolation and child objects (bit, light)
// ============================================================
function syncCycles() {
  
  // Rotation offset to align model with Z-axis
  const ROTATION_OFFSET = 180; 

  for (const agent of agents) {
    // === AGENT SPAWN ===
    if (!agent._addedToScene) {
      if (cycleTemplate !== null) {
        agent.arrays = cycleTemplate.arrays;
        agent.bufferInfo = cycleTemplate.bufferInfo;
        agent.vao = cycleTemplate.vao;
        agent.scale = { x: CYCLE_MODEL.scale, y: CYCLE_MODEL.scale, z: CYCLE_MODEL.scale };
        agent.positionOffset = CYCLE_MODEL.offset;
        agent.color = [0.2, 0.9, 1.0, 1.0];
        agent.shininess = 32;
      } else {
        // Fallback
        agent.arrays = baseCubeRef.arrays;
        agent.bufferInfo = baseCubeRef.bufferInfo;
        agent.vao = baseCubeRef.vao;
        agent.scale = { x: 0.5, y: 0.5, z: 0.5 };
        agent.color = [1.0, 0.0, 0.0, 1.0];
        agent.shininess = 32;
      }
      
      agent._addedToScene = true;
      agent._spawnPos = [...agent.posArray];
      agent._startPos = [...agent.posArray];
      agent._targetPos = [...agent.posArray]; 
      agent._moveStartTime = Date.now();
      
      // === DETERMINE SPAWN DIRECTION ===
      const key = `${Math.floor(agent.posArray[0])},${Math.floor(agent.posArray[2])}`;
      const dir = mapDirections[key]; 

      // Map direction string to rotation angle
      // Inverted logic to correct some failed orientations
      let angleY = 0; 
      
      if (dir === "Right" || dir === ">") angleY = -90;  
      if (dir === "Left"  || dir === "<") angleY = 90;   
      if (dir === "Up"    || dir === "^") angleY = 0;    
      if (dir === "Down"  || dir === "v") angleY = 180;  

      agent.rotDeg = { x: 0, y: angleY, z: 0 };
      agent.rotRad = { x: 0, y: angleY * Math.PI / 180, z: 0 };

      // Set visibility immediately
      agent._visible = true;

      scene.addObject(agent);

      // === CREATE CHILD OBJECTS ===
      if (bitTemplate !== null) {
          const bit = new Object3D(agent.id + "_bit", agent.posArray);
          bit.arrays = bitTemplate.arrays;
          bit.bufferInfo = bitTemplate.bufferInfo;
          bit.vao = bitTemplate.vao;
          bit.scale = { x: BIT_MODEL.scale, y: BIT_MODEL.scale, z: BIT_MODEL.scale };
          bit.color = [1.0, 0.5, 0.0, 1.0];
          bit.shininess = 64;
          bit._visible = true; 
          scene.addObject(bit);
          agent._bit = bit;
      }
      if (sphereTemplate !== null) {
        const lightSphere = new Object3D(agent.id + "_light", agent.posArray);
        lightSphere.arrays = sphereTemplate.arrays;
        lightSphere.bufferInfo = sphereTemplate.bufferInfo;
        lightSphere.vao = sphereTemplate.vao;
        lightSphere.scale = { x: 0.02, y: 0.02, z: 0.02 }; 
        lightSphere.color = [0.0, 0.5, 0.5, 1.0]; 
        lightSphere.isEmissive = true;
        lightSphere.emissiveColor = [0.0, 0.5, 0.5]; 
        lightSphere.shininess = 100;
        lightSphere._visible = true;
        scene.addObject(lightSphere);
        agent._lightSphere = lightSphere;
      }

    } else {
      // === AGENT UPDATE ===
      const nextTile = agent.posArray;
      const currentTile = agent._targetPos || [...nextTile]; 

      const dx = nextTile[0] - currentTile[0];
      const dz = nextTile[2] - currentTile[2];
      
      // === UPDATE ROTATION ===
      // Only update if movement detected to prevent jitter
      if (Math.abs(dx) > 0.01 || Math.abs(dz) > 0.01) {
        
        const angleRad = Math.atan2(dx, dz); 
        
        // Apply offset to match spawn orientation
        agent.rotDeg.y = (angleRad * 180 / Math.PI) + ROTATION_OFFSET;
        agent.rotRad.y = angleRad + (ROTATION_OFFSET * Math.PI / 180);
        
        agent._visible = true;
      }
      
      agent._startPos = currentTile;
      agent._targetPos = nextTile;
      agent._moveStartTime = Date.now();
    }
  }
}

// ============================================================
// TRAFFIC LIGHT COLOR UPDATE
// Updates light color and emissive sphere based on state
// ============================================================
function updateTrafficLightColor(trafficLight) {
  if (trafficLight.state === true) {
    // Green State
    trafficLight.color = [0.635, 0.827, 0.851, 1.0];
    if (trafficLight.sphere) {
      trafficLight.sphere.color = [0.635, 0.827, 0.851, 1.0];
      trafficLight.sphere.emissiveColor = [1.270, 1.654, 1.702];
      trafficLight.sphere._changeTime = Date.now();
    }
  } else {
    // Red State
    trafficLight.color = [0.957, 0.776, 0.310, 1.0];
    if (trafficLight.sphere) {
      trafficLight.sphere.color = [0.957, 0.776, 0.310, 1.0];
      trafficLight.sphere.emissiveColor = [1.914, 1.553, 0.620];
      trafficLight.sphere._changeTime = Date.now();
    }
  }
}

// Draw an object with its corresponding transformations
function drawObject(gl, programInfo, object, viewProjectionMatrix, fract) {
  // Check visibility flag
  if (object._visible === false) {
    return;
  }

  let v3_tra = object.posArray;
  
  if (object.positionOffset) {
    v3_tra = [
      v3_tra[0] + object.positionOffset.x,
      v3_tra[1] + object.positionOffset.y,
      v3_tra[2] + object.positionOffset.z
    ];
  }
  
  let v3_sca = object.scaArray;

  const scaMat = M4.scale(v3_sca);
  const rotXMat = M4.rotationX(object.rotRad.x);
  const rotYMat = M4.rotationY(object.rotRad.y);
  const rotZMat = M4.rotationZ(object.rotRad.z);
  const traMat = M4.translation(v3_tra);

  let transforms = M4.identity();
  transforms = M4.multiply(scaMat, transforms);
  transforms = M4.multiply(rotXMat, transforms);
  transforms = M4.multiply(rotYMat, transforms);
  transforms = M4.multiply(rotZMat, transforms);
  transforms = M4.multiply(traMat, transforms);

  object.matrix = transforms;

  const wvpMat = M4.multiply(viewProjectionMatrix, transforms);

  const normalMat = M4.transpose(M4.inverse(object.matrix));

  let objectUniforms = {
    u_world: object.matrix,
    u_worldInverseTransform: normalMat,
    u_worldViewProjection: wvpMat,

    u_ambientColor: object.color,
    u_diffuseColor: object.color,
    u_specularColor: object.color,
    u_shininess: object.shininess,
    u_isEmissive: object.isEmissive ? 1.0 : 0.0,
    u_emissiveColor: object.emissiveColor || [0.0, 0.0, 0.0],
  }
  twgl.setUniforms(programInfo, objectUniforms);

  gl.bindVertexArray(object.vao);
  twgl.drawBufferInfo(gl, object.bufferInfo);
}

// ============================================================
// BIT POSITION UPDATE
// Calculates bit orbit around the parent cycle
// ============================================================
function updateBitPosition(agent) {
  if (!agent._bit) {
    return;
  }

  // Calculate global rotation angle
  const elapsedTime = Date.now() - startTimeGlobal;
  const bitRotation = (elapsedTime * bitSpeed) % (2 * Math.PI);

  // Determine local position
  const bitX = agent.posArray[0] + BIT_MODEL.radius * Math.cos(bitRotation);
  const bitY = agent.posArray[1] + BIT_MODEL.heightOffset;
  const bitZ = agent.posArray[2] + BIT_MODEL.radius * Math.sin(bitRotation);

  // Apply position
  agent._bit.setPosition([bitX, bitY, bitZ]);
}

// ============================================================
// CYCLE LIGHT UPDATE
// Anchors the light sphere to the back of the cycle
// ============================================================
function updateCycleLightPosition(agent) {
  if (!agent._lightSphere) return;

  const heightOffset = -0.9; 
  const backOffset = 0.085;  

  // Calculate position relative to cycle rotation
  const offsetX = backOffset * Math.sin(agent.rotRad.y);
  const offsetZ = backOffset * Math.cos(agent.rotRad.y);

  const lightPos = [
    agent.posArray[0] + offsetX,
    agent.posArray[1] + heightOffset,
    agent.posArray[2] + offsetZ
  ];

  agent._lightSphere.setPosition(lightPos);
}

// ============================================================
// DRAW LOOP
// Main rendering cycle processing physics and graphics
// ============================================================
async function drawScene() {
  let now = Date.now();
  let deltaTime = now - then;
  elapsed += deltaTime;
  let fract = Math.min(1.0, elapsed / duration);
  then = now;

  // Clear the canvas
  gl.clearColor(0.1, 0.1, 0.2, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

  // tell webgl to cull faces
  gl.enable(gl.CULL_FACE);
  gl.enable(gl.DEPTH_TEST);

  scene.camera.checkKeys();
  const viewProjectionMatrix = setupViewProjection(gl);

  gl.useProgram(phongProgramInfo.program);
  
  // === TRAFFIC LIGHT UNIFORMS ===
  let trafficLightPositions = [];
  let trafficLightColors = [];
  let trafficLightRanges = [];

  for (let i = 0; i < trafficLights.length && i < 100; i++) {
    const tl = trafficLights[i];
    
    // Calculate world position for emissive sphere
    let spherePosition = [
      tl.posArray[0] + (tl.sphere ? (tl.sphere.positionOffset?.x || 0) : 0),
      tl.posArray[1] + (tl.sphere ? (tl.sphere.positionOffset?.y || 0) : 0),
      tl.posArray[2] + (tl.sphere ? (tl.sphere.positionOffset?.z || 0) : 0)
    ];
    
    trafficLightPositions.push(...spherePosition);
    
    // Set color based on state
    let tlColor;
    if (tl.state === true) {
      tlColor = [0.635, 0.827, 0.851];
    } else {
      tlColor = [0.957, 0.776, 0.310];
    }
    trafficLightColors.push(...tlColor);
    
    trafficLightRanges.push(tl.lightRange || 10.0);
  }

  // === CYCLE LIGHT UNIFORMS ===
  // Fill remaining shader light slots with cycle lights
  let currentLights = trafficLightPositions.length / 3;

  for (const agent of agents) {
    // Check shader limit
    if (currentLights >= 1200) break; // note this is greatly exaggerated so it won't break that easily

    if (agent._addedToScene && agent._lightSphere) {
      const pos = agent._lightSphere.posArray;
      trafficLightPositions.push(pos[0], pos[1], pos[2]);

      // Cyan light color
      trafficLightColors.push(0.0, 0.4, 0.4);

      // Light range
      trafficLightRanges.push(2.5); 

      currentLights++;
    }
  }

  let globalUniforms = {
    u_viewWorldPosition: scene.camera.posArray,
    u_lightWorldPosition: scene.lights[0].posArray,
    u_ambientLight: scene.lights[0].ambient,
    u_diffuseLight: scene.lights[0].diffuse,
    u_specularLight: scene.lights[0].specular,
    
    u_trafficLightPositions: trafficLightPositions,
    u_trafficLightColors: trafficLightColors,
    u_trafficLightRange: trafficLightRanges,
    u_numTrafficLights: trafficLights.length,
    u_numTrafficLights: trafficLightPositions.length / 3,    // Pass total light count to shader
  }
  
  twgl.setUniforms(phongProgramInfo, globalUniforms);

  // === INTERPOLATE POSITIONS ===
  for (const agent of agents) {
    if (agent._addedToScene && agent._startPos && agent._targetPos) {
      const timeSinceMove = Date.now() - agent._moveStartTime;
      const moveFract = Math.min(1.0, timeSinceMove / duration);
      
      // Linear interpolation
      const interPos = [
        agent._startPos[0] + (agent._targetPos[0] - agent._startPos[0]) * moveFract,
        agent._startPos[1] + (agent._targetPos[1] - agent._startPos[1]) * moveFract,
        agent._startPos[2] + (agent._targetPos[2] - agent._startPos[2]) * moveFract
      ];
      
      agent.setPosition(interPos);
    }
  }

  // === UPDATE CHILD OBJECTS ===
  for (const agent of agents) {
    if (agent._addedToScene && agent._bit) {
      updateBitPosition(agent);
      if (agent._lightSphere) updateCycleLightPosition(agent);
    }
  }

  // Draw the objects
  for (let object of scene.objects) {
    drawObject(gl, phongProgramInfo, object, viewProjectionMatrix, fract);
  }

  // === SIMULATION STEP ===
  // Update the scene after the elapsed duration
  if (elapsed >= duration) {
    elapsed = 0;
    
    // Request update from API
    await update();
    
    // Sync agents
    syncCycles();
    
    // Remove orphaned child objects
    const agentIds = new Set(agents.map(a => a.id));
    for (let i = scene.objects.length - 1; i >= 0; i--) {
      const obj = scene.objects[i];
      if (obj.id.includes("_bit") || obj.id.includes("_light")) {
        const parentAgentId = obj.id.replace("_bit", "").replace("_light", "");
        if (!agentIds.has(parentAgentId)) {
          scene.objects.splice(i, 1);
        }
      }
    }
    
    // Update traffic lights
    for (const trafficLight of trafficLights) {
      updateTrafficLightColor(trafficLight);
    }
  }

  requestAnimationFrame(drawScene);
}

function setupViewProjection(gl) {
  const fov = 60 * Math.PI / 180;
  const aspect = gl.canvas.clientWidth / gl.canvas.clientHeight;

  const projectionMatrix = M4.perspective(fov, aspect, 1, 200);

  const cameraPosition = scene.camera.posArray;
  const target = scene.camera.targetArray;
  const up = [0, 1, 0];

  const cameraMatrix = M4.lookAt(cameraPosition, target, up);
  const viewMatrix = M4.inverse(cameraMatrix);
  const viewProjectionMatrix = M4.multiply(projectionMatrix, viewMatrix);

  return viewProjectionMatrix;
}

main();