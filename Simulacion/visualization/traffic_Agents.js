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
  getAgents, getObstacles, getTrafficLights, getDestinations, getRoads,
  updateTrafficLights  // SINCRONIZACIÓN: Función para actualizar estados de semáforos
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
let motoTemplate = null; // MODELOS 3D: Referencia al modelo de motos para reutilizarlo

// ============================================================
// DICCIONARIO DE MODELOS DE EDIFICIOS
// DESCRIPCIÓN: Define la configuración de cada modelo de edificio disponible
// incluyendo ruta del archivo OBJ/MTL, escala y offset de posición
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
// CONFIGURACIÓN PARA MOTOS
// DESCRIPCIÓN: Define parámetros del modelo 3D TRON que representa las motos/agentes
// ============================================================
const MOTO_MODEL = {
  path: '../assets/models/tron (1).obj',
  mtl: '../assets/models/tron (1).mtl',
  scale: 0.15,
  offset: { x: 0, y: -0.9, z: 0 } 
};

// ============================================================
// FUNCIÓN PARA CARGAR ARCHIVOS .OBJ GENÉRICOS
// DESCRIPCIÓN: Carga modelos OBJ desde archivos, parsea su contenido,
// calcula su bounding box y los centra para que se rendericen correctamente
// ============================================================
async function loadObjModel(objFilePath, mtlFilePath = null, modelName = "modelo") {
    try {
        // Cargar archivo .mtl si existe
        if (mtlFilePath) {
            try {
                const mtlResponse = await fetch(mtlFilePath);
                
                if (mtlResponse.ok) {
                    const mtlString = await mtlResponse.text();
                    // Parsear los materiales del archivo MTL
                    loadMtl(mtlString);
                } else {
                    console.warn('No se pudo cargar MTL:', mtlResponse.status);
                }
            } catch (mtlError) {
                console.warn('Error cargando MTL:', mtlError);
            }
        }

        // Cargar archivo .obj
        const objResponse = await fetch(objFilePath);
        
        if (!objResponse.ok) {
            console.error('Error HTTP:', objResponse.status, objResponse.statusText);
            return null;
        }
        
        const objString = await objResponse.text();
        // Parsear el contenido del archivo OBJ
        let objArrays = loadObj(objString);
        
        // Centrar el modelo calculando su bounding box
        if (objArrays.a_position && objArrays.a_position.data && objArrays.a_position.data.length > 0) {
            const positions = objArrays.a_position.data;
            
            // Encontrar los límites mínimo y máximo del modelo
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
            
            // Recentrar todos los vértices restando el centro
            for (let i = 0; i < positions.length; i += 3) {
                positions[i] -= centerX;
                positions[i + 1] -= floorY;
                positions[i + 2] -= centerZ;
            }
        }
        
        return objArrays;
    } catch (error) {
        console.error(`Error cargando modelo OBJ de ${modelName}:`, error);
        return null;
    }
}

// ============================================================
// FUNCIÓN PARA ELEGIR UN EDIFICIO ALEATORIO
// DESCRIPCIÓN: Selecciona aleatoriamente un modelo de edificio
// de la colección disponible
// ============================================================
function getRandomBuilding(loadedBuildingModels) {
  const buildingKeys = Object.keys(loadedBuildingModels);
  
  if (buildingKeys.length === 0) {
    return null;
  }
  
  // Seleccionar índice aleatorio
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

// ============================================================
// CONFIGURACIÓN DE OBJETOS EN ESCENA
// DESCRIPCIÓN: Carga todos los modelos 3D (edificios, semáforos, esferas, etc),
// crea VAOs para cada uno y configura sus propiedades visuales
// ============================================================
async function setupObjects(scene, gl, programInfo) {
  
  // Create VAOs for the different shapes
  const baseCube = new Object3D(-1);
  baseCube.prepareVAO(gl, programInfo);
  baseCubeRef = baseCube;

  // CARGA DE MODELO DE MOTOS
  // Intenta cargar el modelo TRON y guardarlo como template para reutilizarlo
  const motoModel = await loadObjModel(
    MOTO_MODEL.path,
    MOTO_MODEL.mtl,
    'moto'
  );

  if (motoModel) {
    try {
      // Crear buffer info del modelo
      const motoBufferInfo = twgl.createBufferInfoFromArrays(gl, motoModel);
      // Crear VAO para el modelo
      const motoVAO = gl.createVertexArray();
      gl.bindVertexArray(motoVAO);
      // Vincular atributos al VAO
      twgl.setBuffersAndAttributes(gl, programInfo, motoBufferInfo);
      
      // Guardar template para usarlo en todas las motos
      motoTemplate = {
        arrays: motoModel,
        bufferInfo: motoBufferInfo,
        vao: motoVAO
      };
    } catch (error) {
      console.error('Error creando VAO de motos:', error);
      motoTemplate = null;
    }
  } else {
    motoTemplate = null;
  }

  // CARGA DE MODELOS DE EDIFICIOS
  // Carga todos los edificios disponibles y crea buffers para cada uno
  const loadedBuildingModels = {};

  for (const [buildingKey, buildingConfig] of Object.entries(BUILDING_MODELS)) {
    const model = await loadObjModel(
      buildingConfig.path,
      buildingConfig.mtl,
      buildingKey
    );
    
    if (model) {
      // Guardar modelo, buffer y configuración
      loadedBuildingModels[buildingKey] = {
        arrays: model,
        bufferInfo: twgl.createBufferInfoFromArrays(gl, model),
        config: buildingConfig
      };
    }
  }

  // CARGA DE MODELO DE SEMÁFOROS
  // Carga el modelo 3D del semáforo para usarlo en todos
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
      // Crear buffer info
      trafficLightBufferInfo = twgl.createBufferInfoFromArrays(gl, trafficLightModel);
      // Crear VAO
      trafficLightVAO = gl.createVertexArray();
      gl.bindVertexArray(trafficLightVAO);
      // Vincular atributos
      twgl.setBuffersAndAttributes(gl, programInfo, trafficLightBufferInfo);
    } catch (error) {
      console.error('Error creando VAO de semáforos:', error);
      trafficLightVAO = null;
    }
  }

  // CARGA DE MODELO DE ESFERA INDICADORA
  // Carga el modelo de esfera que se usa como luz emisiva en los semáforos
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
      // Crear buffer info
      sphereBufferInfo = twgl.createBufferInfoFromArrays(gl, sphereModel);
      // Crear VAO
      sphereVAO = gl.createVertexArray();
      gl.bindVertexArray(sphereVAO);
      // Vincular atributos
      twgl.setBuffersAndAttributes(gl, programInfo, sphereBufferInfo);
    } catch (error) {
      console.error('Error creando VAO de esfera:', error);
      sphereVAO = null;
    }
  }

  // Setup roads (ground level)
  for (const road of roads) {
    // Usar modelo base (cubo)
    road.arrays = baseCube.arrays;
    road.bufferInfo = baseCube.bufferInfo;
    road.vao = baseCube.vao;
    // Hacer muy delgado para simular piso
    road.scale = { x: 1, y: 0.02, z: 1 };
    road.color = [0.1, 0.1, 0.1, 1.0];
    road.shininess = 32;
    scene.addObject(road);
  }

  // SETUP OBSTACLES CON EDIFICIOS ALEATORIOS
  // Asigna un modelo de edificio aleatorio a cada obstáculo
  for (const obstacle of obstacles) {
    // Obtener edificio aleatorio
    const randomBuilding = getRandomBuilding(loadedBuildingModels);
    
    if (randomBuilding) {
      // Asignar datos del modelo al obstáculo
      obstacle.arrays = randomBuilding.arrays;
      obstacle.bufferInfo = randomBuilding.bufferInfo;
      obstacle.vao = randomBuilding.vao || gl.createVertexArray();
      
      // Aplicar escala del edificio
      const scale = randomBuilding.config.scale;
      obstacle.scale = { x: scale, y: scale, z: scale };
      obstacle.positionOffset = { x: 0, y: randomBuilding.config.offset, z: 0 };
      
      // Crear VAO si no existe
      if (!randomBuilding.vao) {
        randomBuilding.vao = obstacle.vao;
        gl.bindVertexArray(obstacle.vao);
        twgl.setBuffersAndAttributes(gl, programInfo, randomBuilding.bufferInfo);
      }
    } else {
      // Fallback a cubo si no hay edificios cargados
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
      // Asignar modelo de semáforo
      trafficLight.arrays = trafficLightArrays;
      trafficLight.bufferInfo = trafficLightBufferInfo;
      trafficLight.vao = trafficLightVAO;
      trafficLight.scale = { x: 1.5, y: 1.5, z: 1.5 };
    } else {
      // Fallback a cubo
      trafficLight.arrays = baseCube.arrays;
      trafficLight.bufferInfo = baseCube.bufferInfo;
      trafficLight.vao = baseCube.vao;
      trafficLight.scale = { x: 0.3, y: 0.8, z: 0.3 };
    }
    
    trafficLight.shininess = 128;
    trafficLight.isLight = true;
    trafficLight.lightRange = 2.0;
    
    // Actualizar color basado en estado
    updateTrafficLightColor(trafficLight);
    scene.addObject(trafficLight);
  }

  // CREAR ESFERAS EMISIVAS PARA LOS SEMÁFOROS
  // Crea una pequeña esfera que emite luz encima de cada semáforo
  for (const trafficLight of trafficLights) {
    if (sphereVAO) {
      // Crear esfera como objeto 3D independiente
      const sphere = new Object3D(trafficLight.id + "_sphere", trafficLight.posArray);
      sphere.arrays = sphereArrays;
      sphere.bufferInfo = sphereBufferInfo;
      sphere.vao = sphereVAO;
      // Tamaño muy pequeño
      sphere.scale = { x: 0.08, y: 0.08, z: 0.08 };
      
      // Posicionar encima del semáforo
      sphere.positionOffset = { x: 0, y: 0.29, z: 0 };
      
      // Marcar como emisiva para que brille
      sphere.isEmissive = true;
      
      // Asignar color basado en estado
      if (trafficLight.state === true) {
        sphere.color = [0.635, 0.827, 0.851, 1.0];
        sphere.emissiveColor = [1.270, 1.654, 1.702];
      } else {
        sphere.color = [0.957, 0.776, 0.310, 1.0];
        sphere.emissiveColor = [1.914, 1.553, 0.620];
      }
      
      sphere.shininess = 2500;
      scene.addObject(sphere);
      
      // Guardar referencia en el semáforo
      trafficLight.sphere = sphere;
    }
  }

  // Setup motos/agentes
  syncMotos();
  
  // Calcular dirección inicial de motos
  for (const agent of agents) {
    if (agent._addedToScene && !agent._directionSet) {
      agent.rotDeg.y = 0;
      agent.rotRad.y = 0;
      agent._directionSet = true;
    }
  }
}

// ============================================================
// SINCRONIZACIÓN DE MOTOS CON LA ESCENA
// DESCRIPCIÓN: Añade las motos a la escena con su geometría,
// calcula sus rotaciones iniciales e interpola sus movimientos
// ============================================================
function syncMotos() {
  for (const agent of agents) {
    // Si la moto no ha sido añadida a la escena aún
    if (!agent._addedToScene) {
      if (motoTemplate !== null) {
        // Usar el modelo TRON como geometría
        agent.arrays = motoTemplate.arrays;
        agent.bufferInfo = motoTemplate.bufferInfo;
        agent.vao = motoTemplate.vao;
        agent.scale = { x: MOTO_MODEL.scale, y: MOTO_MODEL.scale, z: MOTO_MODEL.scale };
        agent.positionOffset = MOTO_MODEL.offset;
        agent.color = [0.2, 0.9, 1.0, 1.0];
        agent.shininess = 32;
      } else {
        // Fallback a cubo si el modelo no se cargó
        agent.arrays = baseCubeRef.arrays;
        agent.bufferInfo = baseCubeRef.bufferInfo;
        agent.vao = baseCubeRef.vao;
        agent.scale = { x: 0.5, y: 0.5, z: 0.5 };
        agent.color = [1.0, 0.0, 0.0, 1.0];
        agent.shininess = 32;
      }
      
      // Inicializar variables de control
      agent._addedToScene = true;
      agent._spawnPos = [...agent.posArray];
      agent._startPos = [...agent.posArray];
      agent._targetPos = [...agent.posArray];
      agent._moveStartTime = Date.now();
      agent.rotDeg = { x: 0, y: 0, z: 0 };
      agent.rotRad = { x: 0, y: 0, z: 0 };
      agent._needsInitialRotation = true;
      agent._visible = false;
      
      // Añadir a la escena
      scene.addObject(agent);
    } else {
      // En el primer update, calcular rotación inicial
      if (agent._needsInitialRotation) {
        const spawnPos = agent._spawnPos;
        const currPos = agent.posArray;
        
        const dx = currPos[0] - spawnPos[0];
        const dz = currPos[2] - spawnPos[2];
        
        // Si se movió desde spawn, calcular el ángulo
        if (Math.abs(dx) > 0.01 || Math.abs(dz) > 0.01) {
          const angleRad = Math.atan2(dz, dx);
          agent.rotDeg.y = angleRad * 180 / Math.PI + 90;
          agent.rotRad.y = angleRad + Math.PI / 2;
        }
        
        agent._needsInitialRotation = false;
        agent._visible = true;
      }
      
      // Actualizar rotación basada en movimiento actual
      const currPos = agent.posArray;
      const prevPos = agent._targetPos || [...currPos];
      
      const dx = currPos[0] - prevPos[0];
      const dz = currPos[2] - prevPos[2];
      
      if (Math.abs(dx) > 0.01 || Math.abs(dz) > 0.01) {
        const angleRad = Math.atan2(dz, dx);
        agent.rotDeg.y = angleRad * 180 / Math.PI + 90;
        agent.rotRad.y = angleRad + Math.PI / 2;
      }
      
      // Preparar posiciones para interpolación
      agent._startPos = prevPos;
      agent._targetPos = currPos;
      agent._moveStartTime = Date.now();
    }
  }
}

// ============================================================
// ACTUALIZACIÓN DE COLOR DE SEMÁFOROS
// DESCRIPCIÓN: Cambia el color y brillo del semáforo y su esfera
// basándose en el estado (verde o amarillo)
// ============================================================
function updateTrafficLightColor(trafficLight) {
  if (trafficLight.state === true) {
    // Verde: #A2D3D9FF
    trafficLight.color = [0.635, 0.827, 0.851, 1.0];
    if (trafficLight.sphere) {
      trafficLight.sphere.color = [0.635, 0.827, 0.851, 1.0];
      // Versión más brillante para el brillo emisivo
      trafficLight.sphere.emissiveColor = [1.270, 1.654, 1.702];
      trafficLight.sphere._changeTime = Date.now();
    }
  } else {
    // Amarillo: #F4C64FFF
    trafficLight.color = [0.957, 0.776, 0.310, 1.0];
    if (trafficLight.sphere) {
      trafficLight.sphere.color = [0.957, 0.776, 0.310, 1.0];
      // Versión más brillante para el brillo emisivo
      trafficLight.sphere.emissiveColor = [1.914, 1.553, 0.620];
      trafficLight.sphere._changeTime = Date.now();
    }
  }
}

// Draw an object with its corresponding transformations
function drawObject(gl, programInfo, object, viewProjectionMatrix, fract) {
  // No dibujar si el objeto está marcado como invisible
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
// LOOP DE RENDERIZADO PRINCIPAL
// DESCRIPCIÓN: Renderiza la escena cada frame, interpola posiciones
// de motos, actualiza estados de semáforos y maneja la lógica de actualización
// ============================================================
async function drawScene() {
  let now = Date.now();
  let deltaTime = now - then;
  elapsed += deltaTime;
  let fract = Math.min(1.0, elapsed / duration);
  then = now;

  gl.clearColor(0.1, 0.1, 0.2, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

  gl.enable(gl.CULL_FACE);
  gl.enable(gl.DEPTH_TEST);

  scene.camera.checkKeys();
  const viewProjectionMatrix = setupViewProjection(gl);

  gl.useProgram(phongProgramInfo.program);
  
  // PREPARAR POSICIONES Y COLORES DE LAS LUCES DE LOS SEMÁFOROS
  // Se envían al shader para calcular iluminación dinámica
  let trafficLightPositions = [];
  let trafficLightColors = [];
  let trafficLightRanges = [];

  for (let i = 0; i < trafficLights.length && i < 27; i++) {
    const tl = trafficLights[i];
    
    // Calcular posición de la esfera emisiva en coordenadas mundiales
    let spherePosition = [
      tl.posArray[0] + (tl.sphere ? (tl.sphere.positionOffset?.x || 0) : 0),
      tl.posArray[1] + (tl.sphere ? (tl.sphere.positionOffset?.y || 0) : 0),
      tl.posArray[2] + (tl.sphere ? (tl.sphere.positionOffset?.z || 0) : 0)
    ];
    
    trafficLightPositions.push(...spherePosition);
    
    // Asignar color basado en estado del semáforo
    let tlColor;
    if (tl.state === true) {
      tlColor = [0.635, 0.827, 0.851];
    } else {
      tlColor = [0.957, 0.776, 0.310];
    }
    trafficLightColors.push(...tlColor);
    
    trafficLightRanges.push(tl.lightRange || 10.0);
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
  }
  
  twgl.setUniforms(phongProgramInfo, globalUniforms);

  // INTERPOLACIÓN DE POSICIONES DE MOTOS
  // Calcula posiciones intermedias para movimiento suave entre frames
  for (const agent of agents) {
    if (agent._addedToScene && agent._startPos && agent._targetPos) {
      // Calcular fracción de tiempo desde inicio del movimiento
      const timeSinceMove = Date.now() - agent._moveStartTime;
      const moveFract = Math.min(1.0, timeSinceMove / duration);
      
      // Interpolar linealmente entre posición inicial y final
      const interpPos = [
        agent._startPos[0] + (agent._targetPos[0] - agent._startPos[0]) * moveFract,
        agent._startPos[1] + (agent._targetPos[1] - agent._startPos[1]) * moveFract,
        agent._startPos[2] + (agent._targetPos[2] - agent._startPos[2]) * moveFract
      ];
      
      // Guardar posición interpolada para rendering
      agent._drawPosition = { x: interpPos[0], y: interpPos[1], z: interpPos[2] };
    }
  }

  // RENDERIZADO DE OBJETOS
  // Dibuja cada objeto usando su posición interpolada si existe
  for (let object of scene.objects) {
    const origPos = object.position;
    if (object._drawPosition) {
      // Usar posición interpolada
      object.position = object._drawPosition;
    }
    
    drawObject(gl, phongProgramInfo, object, viewProjectionMatrix, fract);
    
    // Restaurar posición original
    object.position = origPos;
  }

  // ACTUALIZACIÓN DE LA SIMULACIÓN
  // Cada segundo: actualiza agentes, sincroniza motos y actualiza semáforos
  if (elapsed >= duration) {
    elapsed = 0;
    
    // Solicitar actualización al servidor
    await update();
    
    // Sincronizar motos con nuevas posiciones
    syncMotos();
    
    // SINCRONIZACIÓN DE SEMÁFOROS: Actualizar colores basado en nuevo estado
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