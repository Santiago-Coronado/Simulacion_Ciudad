/*
 * Base program for a 3D scene that connects to an API to get the movement
 * of agents with Phong lighting.
 * The scene shows colored cubes, buildings and traffic lights
 *
 * Gilberto Echeverria
 * 2025-11-08
 */

'use strict';

import * as twgl from 'twgl-base.js';
import GUI from 'lil-gui';
import { M4 } from '../libs/3d-lib.js';
import { Scene3D } from '../libs/scene3d.js';
import { Object3D } from '../libs/object3d.js';
import { Light3D } from '../libs/light3d.js';
import { Camera3D } from '../libs/camera3d.js';

// CARGADOR DE MODELOS OBJ/MTL
import { loadObj, loadMtl } from '../libs/obj_loader.js';
import {
  agents, obstacles, trafficLights, destinations, roads,
  initAgentsModel, update, 
  getAgents, getObstacles, getTrafficLights, getDestinations, getRoads
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

// DICCIONARIO DE MODELOS DE EDIFICIOS
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
  }
};

// ============================================================
// FUNCIÓN PARA CARGAR ARCHIVOS .OBJ GENÉRICOS
// ============================================================
async function loadObjModel(objFilePath, mtlFilePath = null, modelName = "modelo") {
    try {
        // PRIMERO: Cargar archivo .mtl si existe
        if (mtlFilePath) {
            console.log(`Intentando cargar MTL de ${modelName} desde:`, mtlFilePath);
            try {
                const mtlResponse = await fetch(mtlFilePath);
                
                if (mtlResponse.ok) {
                    const mtlString = await mtlResponse.text();
                    console.log(`MTL cargado, tamaño: ${mtlString.length} caracteres`);
                    loadMtl(mtlString);
                } else {
                    console.warn('No se pudo cargar MTL:', mtlResponse.status);
                }
            } catch (mtlError) {
                console.warn('Error cargando MTL:', mtlError);
            }
        }

        // DESPUÉS: Cargar archivo .obj
        console.log(`Intentando cargar OBJ de ${modelName} desde:`, objFilePath);
        const objResponse = await fetch(objFilePath);
        
        if (!objResponse.ok) {
            console.error('Error HTTP:', objResponse.status, objResponse.statusText);
            return null;
        }
        
        const objString = await objResponse.text();
        console.log(`OBJ cargado, tamaño: ${objString.length} caracteres`);
        
        let objArrays = loadObj(objString);
        
        console.log('OBJ parseado, propiedades:', Object.keys(objArrays));
        console.log('Posiciones disponibles:', objArrays.a_position ? objArrays.a_position.data.length : 'NO');
        
        // Centrar el modelo calculando su bounding box
        if (objArrays.a_position && objArrays.a_position.data && objArrays.a_position.data.length > 0) {
            const positions = objArrays.a_position.data;
            console.log('Total de coordenadas:', positions.length, '=', positions.length / 3, 'vértices');
            
            // Encontrar min y max
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
            
            // Centro en X y Z, pero piso en Y
            const centerX = (minX + maxX) / 2;
            const centerZ = (minZ + maxZ) / 2;
            const floorY = minY;
            
            console.log('Bounds:', { minX: minX.toFixed(2), maxX: maxX.toFixed(2), minY: minY.toFixed(2), maxY: maxY.toFixed(2), minZ: minZ.toFixed(2), maxZ: maxZ.toFixed(2) });
            console.log('Centro:', { centerX: centerX.toFixed(2), centerZ: centerZ.toFixed(2), floorY: floorY.toFixed(2) });
            
            // Recentrar todos los vértices
            for (let i = 0; i < positions.length; i += 3) {
                positions[i] -= centerX;
                positions[i + 1] -= floorY;
                positions[i + 2] -= centerZ;
            }
            console.log(`Modelo ${modelName} centrado y posicionado`);
        } else {
            console.warn('No hay datos de posición para centrar el modelo');
        }
        
        console.log(`OBJ de ${modelName} parseado y centrado:`, objArrays);
        return objArrays;
    } catch (error) {
        console.error(`Error cargando modelo OBJ de ${modelName}:`, error);
        return null;
    }
}

// FUNCIÓN PARA ELEGIR UN EDIFICIO ALEATORIO
function getRandomBuilding(loadedBuildingModels) {
  const buildingKeys = Object.keys(loadedBuildingModels);
  
  if (buildingKeys.length === 0) {
    return null;
  }
  
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

  console.log('=== INICIANDO SIMULACIÓN ===');

  // Initialize the agents model
  console.log('Inicializando modelo...');
  await initAgentsModel();

  // Get all elements from the model
  console.log('Obteniendo agentes...');
  await getAgents();
  console.log('Agentes obtenidos:', agents.length);

  console.log('Obteniendo obstáculos...');
  await getObstacles();
  console.log('Obstáculos obtenidos:', obstacles.length);

  console.log('Obteniendo semáforos...');
  await getTrafficLights();
  console.log('Semáforos obtenidos:', trafficLights.length);

  console.log('Obteniendo destinos...');
  await getDestinations();
  console.log('Destinos obtenidos:', destinations.length);

  console.log('Obteniendo carreteras...');
  await getRoads();
  console.log('Carreteras obtenidas:', roads.length);

  // Initialize the scene
  setupScene();

  // Position the objects in the scene
  await setupObjects(scene, gl, phongProgramInfo);

  // First call to the drawing loop
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

  // LUZ PRINCIPAL DE LA ESCENA (PHONG)
  let mainLight = new Light3D(0, [20, 20, 20],           // Position
                             [0.6, 0.6, 0.6, 1.0],   // Ambient
                             [1.2, 1.2, 1.2, 1.0],   // Diffuse
                             [1.2, 1.2, 1.2, 1.0]);  // Specular
  scene.addLight(mainLight);
}

async function setupObjects(scene, gl, programInfo) {
  console.log('=== SETUP OBJECTS INICIADO ===');
  
  // Create VAOs for the different shapes
  const baseCube = new Object3D(-1);
  baseCube.prepareVAO(gl, programInfo);

  // CARGAR TODOS LOS MODELOS DE EDIFICIOS DISPONIBLES
  const loadedBuildingModels = {};

  for (const [buildingKey, buildingConfig] of Object.entries(BUILDING_MODELS)) {
    console.log(`Cargando edificio: ${buildingKey}`);
    const model = await loadObjModel(
      buildingConfig.path,
      buildingConfig.mtl,
      buildingKey
    );
    
    if (model) {
      loadedBuildingModels[buildingKey] = {
        arrays: model,
        bufferInfo: twgl.createBufferInfoFromArrays(gl, model),
        config: buildingConfig
      };
      console.log(`Modelo de edificio ${buildingKey} cargado correctamente`);
    } else {
      console.warn(`No se pudo cargar modelo ${buildingKey}, será fallback`);
    }
  }

  // CARGAR MODELO DE SEMÁFOROS
  const trafficLightModel = await loadObjModel(
    '../assets/models/tl.obj',
    '../assets/models/tl.mtl',
    'semáforos'
  );

  let trafficLightVAO = null;
  let trafficLightBufferInfo = null;
  let trafficLightArrays = null;

  if (trafficLightModel) {
    console.log('Creando VAO para modelo de semáforos...');
    trafficLightArrays = trafficLightModel;
    
    try {
      trafficLightBufferInfo = twgl.createBufferInfoFromArrays(gl, trafficLightModel);
      trafficLightVAO = gl.createVertexArray();
      gl.bindVertexArray(trafficLightVAO);
      twgl.setBuffersAndAttributes(gl, programInfo, trafficLightBufferInfo);
      console.log('VAO de semáforos creado correctamente');
    } catch (error) {
      console.error('Error creando VAO de semáforos:', error);
      trafficLightVAO = null;
    }
  }

  // CARGAR MODELO DE ESFERA INDICADORA
  const sphereModel = await loadObjModel(
    '../assets/models/sphere.obj',
    '../assets/models/sphere.mtl',
    'esfera'
  );

  let sphereVAO = null;
  let sphereBufferInfo = null;
  let sphereArrays = null;

  if (sphereModel) {
    console.log('Creando VAO para modelo de esfera...');
    sphereArrays = sphereModel;
    
    try {
      sphereBufferInfo = twgl.createBufferInfoFromArrays(gl, sphereModel);
      sphereVAO = gl.createVertexArray();
      gl.bindVertexArray(sphereVAO);
      twgl.setBuffersAndAttributes(gl, programInfo, sphereBufferInfo);
      console.log('VAO de esfera creado correctamente');
    } catch (error) {
      console.error('Error creando VAO de esfera:', error);
      sphereVAO = null;
    }
  }

  // Setup roads (ground level)
  console.log('Configurando carreteras:', roads.length);
  for (const road of roads) {
    road.arrays = baseCube.arrays;
    road.bufferInfo = baseCube.bufferInfo;
    road.vao = baseCube.vao;
    road.scale = { x: 1, y: 0.05, z: 1 };
    road.color = [0.3, 0.3, 0.3, 1.0]; // Dark gray for roads
    road.shininess = 8;
    scene.addObject(road);
  }

  // SETUP OBSTACLES CON EDIFICIOS ALEATORIOS
  console.log('Configurando obstáculos:', obstacles.length);
  for (const obstacle of obstacles) {
    const randomBuilding = getRandomBuilding(loadedBuildingModels);
    
    if (randomBuilding) {
      obstacle.arrays = randomBuilding.arrays;
      obstacle.bufferInfo = randomBuilding.bufferInfo;
      obstacle.vao = randomBuilding.vao || gl.createVertexArray();
      
      const scale = randomBuilding.config.scale;
      obstacle.scale = { x: scale, y: scale, z: scale };
      obstacle.positionOffset = { x: 0, y: randomBuilding.config.offset, z: 0 };
      
      if (!randomBuilding.vao) {
        randomBuilding.vao = obstacle.vao;
        gl.bindVertexArray(obstacle.vao);
        twgl.setBuffersAndAttributes(gl, programInfo, randomBuilding.bufferInfo);
      }
    } else {
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
  console.log('Configurando destinos:', destinations.length);
  for (const destination of destinations) {
    destination.arrays = baseCube.arrays;
    destination.bufferInfo = baseCube.bufferInfo;
    destination.vao = baseCube.vao;
    destination.scale = { x: 1, y: 0.1, z: 1 };
    destination.color = [0.0, 1.0, 0.0, 1.0]; // Green for destinations
    destination.shininess = 16;
    scene.addObject(destination);
  }

  // Setup traffic lights
  console.log('Configurando semáforos:', trafficLights.length);
  for (const trafficLight of trafficLights) {
    if (trafficLightVAO) {
      trafficLight.arrays = trafficLightArrays;
      trafficLight.bufferInfo = trafficLightBufferInfo;
      trafficLight.vao = trafficLightVAO;
      trafficLight.scale = { x: 1.5, y: 1.5, z: 1.5 };
    } else {
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

  // CREAR ESFERAS EMISIVAS PARA LOS SEMÁFOROS
  console.log('Creando esferas para semáforos');
  for (const trafficLight of trafficLights) {
    if (sphereVAO) {
      const sphere = new Object3D(trafficLight.id + "_sphere", trafficLight.posArray);
      sphere.arrays = sphereArrays;
      sphere.bufferInfo = sphereBufferInfo;
      sphere.vao = sphereVAO;
      sphere.scale = { x: 0.08, y: 0.08, z: 0.08 };
      
      sphere.positionOffset = { x: 0, y: 0.29, z: 0 };
      
      sphere.isEmissive = true;
      
      if (trafficLight.state === true) {
        sphere.color = [0.0, 1.0, 0.0, 1.0];
        sphere.emissiveColor = [0.0, 1.0, 0.0];
      } else {
        sphere.color = [1.0, 0.0, 0.0, 1.0];
        sphere.emissiveColor = [1.0, 0.0, 0.0];
      }
      
      sphere.shininess = 2500;
      scene.addObject(sphere);
      
      trafficLight.sphere = sphere;
    }
  }

  // Setup cars/motos (agents) - CUBOS SIMPLES PARA DEBUG
  console.log('Configurando agentes:', agents.length);
  for (const agent of agents) {
    agent.arrays = baseCube.arrays;
    agent.bufferInfo = baseCube.bufferInfo;
    agent.vao = baseCube.vao;
    agent.scale = { x: 0.5, y: 0.5, z: 0.5 };
    agent.color = [1.0, 0.0, 0.0, 1.0]; // Red for agents
    agent.shininess = 32;
    scene.addObject(agent);
    console.log(`  Agente ${agent.id} en posición:`, agent.posArray);
  }
  console.log('Agentes configurados');

  console.log('=== SETUP OBJECTS COMPLETADO ===');
  console.log('Total objetos en escena:', scene.objects.length);
}

// Update traffic light color based on state
function updateTrafficLightColor(trafficLight) {
  if (trafficLight.state === true) {
    trafficLight.color = [0.0, 1.0, 0.0, 1.0]; // Green
  } else {
    trafficLight.color = [1.0, 0.0, 0.0, 1.0]; // Red
  }
  
  if (trafficLight.sphere) {
    if (trafficLight.state === true) {
      trafficLight.sphere.color = [0.0, 1.0, 0.0, 1.0];
      trafficLight.sphere.emissiveColor = [0.0, 1.0, 0.0];
    } else {
      trafficLight.sphere.color = [1.0, 0.0, 0.0, 1.0];
      trafficLight.sphere.emissiveColor = [1.0, 0.0, 0.0];
    }
  }
}

// Draw an object with its corresponding transformations
function drawObject(gl, programInfo, object, viewProjectionMatrix, fract) {
  let v3_tra = object.posArray;
  
  if (object.positionOffset) {
    v3_tra = [
      v3_tra[0] + object.positionOffset.x,
      v3_tra[1] + object.positionOffset.y,
      v3_tra[2] + object.positionOffset.z
    ];
  }
  
  let v3_sca = object.scaArray;

  // Create the individual transform matrices
  const scaMat = M4.scale(v3_sca);
  const rotXMat = M4.rotationX(object.rotRad.x);
  const rotYMat = M4.rotationY(object.rotRad.y);
  const rotZMat = M4.rotationZ(object.rotRad.z);
  const traMat = M4.translation(v3_tra);

  // Create the composite matrix with all transformations
  let transforms = M4.identity();
  transforms = M4.multiply(scaMat, transforms);
  transforms = M4.multiply(rotXMat, transforms);
  transforms = M4.multiply(rotYMat, transforms);
  transforms = M4.multiply(rotZMat, transforms);
  transforms = M4.multiply(traMat, transforms);

  object.matrix = transforms;

  // Apply the projection to the final matrix for the World-View-Projection
  const wvpMat = M4.multiply(viewProjectionMatrix, transforms);

  // The matrix to be used for normal transformations
  const normalMat = M4.transpose(M4.inverse(object.matrix));

  // Model uniforms
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

// Function to do the actual display of the objects
async function drawScene() {
  // Compute time elapsed since last frame
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

  // Draw the objects
  gl.useProgram(phongProgramInfo.program);
  
  // PREPARAR POSICIONES Y COLORES DE LAS LUCES DE LOS SEMÁFOROS
  let trafficLightPositions = [];
  let trafficLightColors = [];
  let trafficLightRanges = [];

  for (let i = 0; i < trafficLights.length && i < 27; i++) {
    const tl = trafficLights[i];
    
    let spherePosition = [
      tl.posArray[0] + (tl.sphere ? (tl.sphere.positionOffset?.x || 0) : 0),
      tl.posArray[1] + (tl.sphere ? (tl.sphere.positionOffset?.y || 0) : 0),
      tl.posArray[2] + (tl.sphere ? (tl.sphere.positionOffset?.z || 0) : 0)
    ];
    
    trafficLightPositions.push(...spherePosition);
    
    let tlColor;
    if (tl.state === true) {
      tlColor = [0.0, 1.0, 0.0];
    } else {
      tlColor = [1.0, 0.0, 0.0];
    }
    trafficLightColors.push(...tlColor);
    
    trafficLightRanges.push(tl.lightRange || 10.0);
  }

  // Usar la luz principal como base
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
  }
  
  twgl.setUniforms(phongProgramInfo, globalUniforms);

  for (let object of scene.objects) {
    drawObject(gl, phongProgramInfo, object, viewProjectionMatrix, fract);
  }

  // Update the scene after the elapsed duration
  if (elapsed >= duration) {
    elapsed = 0;
    console.log('Actualizando simulación...');
    await update();
    console.log('Agentes después de update:', agents.length);
    
    // Update traffic light colors based on their current state
    for (const trafficLight of trafficLights) {
      updateTrafficLightColor(trafficLight);
    }
  }

  requestAnimationFrame(drawScene);
}

function setupViewProjection(gl) {
  // Field of view of 60 degrees vertically, in radians
  const fov = 60 * Math.PI / 180;
  const aspect = gl.canvas.clientWidth / gl.canvas.clientHeight;

  // Matrices for the world view
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