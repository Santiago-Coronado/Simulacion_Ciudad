#version 300 es
precision highp float;

in vec3 v_normal;
in vec3 v_surfaceToLight;
in vec3 v_surfaceToView;
in vec4 v_color;
in vec3 v_worldPosition;
 
// Scene uniforms
uniform vec4 u_ambientLight;
uniform vec4 u_diffuseLight;
uniform vec4 u_specularLight;

// UNIFORMS DE SEMÁFOROS
// Arrays que guardan información de hasta 27 semáforos simultáneamente.
// u_trafficLightPositions: posición XYZ de cada esfera de semáforo
// u_trafficLightColors: color RGB (verde o rojo) de cada luz
// u_trafficLightRange: alcance máximo de cada luz
// u_numTrafficLights: cuántos semáforos realmente hay en la escena
uniform vec3 u_trafficLightPositions[27];
uniform vec3 u_trafficLightColors[27];
uniform float u_trafficLightRange[27];
uniform int u_numTrafficLights;

// UNIFORMS PARA OBJETOS EMISIVOS
// u_isEmissive: 1.0 si el objeto emite luz, 0.0 si no
// u_emissiveColor: color RGB de la luz que emite (ej: [0, 2, 0] para verde intenso)
uniform float u_isEmissive;
uniform vec3 u_emissiveColor;

out vec4 outColor;

// FUNCIÓN DE ATENUACIÓN DE LUZ
// Calcula cuánto "brilla" la luz según la distancia.
// - Si distance > range: la luz no llega (atenuación = 0)
// - Si distance = 0: brilla al máximo (atenuación = 1)
// - Si distance = range: empieza a apagarse
// Usa una fórmula cuadrática suave: 1 - (distance/range)²
// Esto hace que la luz desaparezca de forma más natural que lineal.
float calculateAttenuation(float distance, float range) {
    // Si la distancia es mayor que el rango, atenuación = 0
    if (distance > range) {
        return 0.0;
    }
    
    // Atenuación cuadrática suave
    // A mayor distancia, menor brillo
    float normalized = distance / range;  // Normalizar a rango 0.0-1.0
    float attenuation = 1.0 - (normalized * normalized);  // Fórmula cuadrática: 1 - x²
    
    return max(0.0, attenuation);
}

void main() {
    // RAMA PARA OBJETOS EMISIVOS
    // Si este objeto emite luz (como las esferas de los semáforos),
    // simplemente mostramos su color emisivo sin aplicar iluminación normal.
    // Esto hace que brille con luz propia.
    if (u_isEmissive > 0.5) {
        outColor = vec4(u_emissiveColor, 1.0);
        return;
    }
    
    // v_normal must be normalized because the shader will interpolate
    // it for each fragment
    vec3 normal = normalize(v_normal);

    // Normalize the other incoming vectors
    vec3 surfToLigthDirection = normalize(v_surfaceToLight);
    vec3 surfToViewDirection = normalize(v_surfaceToView);

    // CALCULATIONS FOR THE AMBIENT, DIFFUSE and SPECULAR COMPONENTS
    float diffuse = max(dot(normal, surfToLigthDirection), 0.0);
    float specular = 0.0;

    if (diffuse > 0.0){
        vec3 r = 2.0 * diffuse * normal - surfToLigthDirection; 
        specular = pow(max(dot(surfToViewDirection, r), 0.0), 32.0);
    }

    // Use the color from the model (a_color / v_color)
    // Compute the three parts of the Phong lighting model
    vec4 ambientColor = v_color * u_ambientLight;
    vec4 diffuseColor = u_diffuseLight * v_color * diffuse;
    vec4 specularColor = u_specularLight * vec4(1.0) * specular;

    // Combine all lighting components
    vec4 finalColor = ambientColor + diffuseColor + specularColor;

    // LOOP DE ILUMINACIÓN DE SEMÁFOROS
    // Por cada semáforo (máximo 27), calcula cuánto ilumina a este píxel.
    // La iluminación depende de:
    // 1. La distancia entre el píxel y la esfera del semáforo (usando Pitágoras)
    // 2. La atenuación según esa distancia
    // 3. La orientación de la superficie (dot product con la normal)
    for (int i = 0; i < 27; i++) {
        if (i >= u_numTrafficLights) break;
        
        // CALCULAR DISTANCIA USANDO PITÁGORAS
        // trafficLightDir es el vector desde el píxel hasta la luz
        // length() calcula la magnitud: √(dx² + dy² + dz²)
        vec3 trafficLightDir = u_trafficLightPositions[i] - v_worldPosition;
        float distToLight = length(trafficLightDir);
        
        // CALCULAR ATENUACIÓN POR DISTANCIA
        // Obtiene un valor entre 0.0 (apagado) y 1.0 (al máximo brillo)
        float attenuation = calculateAttenuation(distToLight, u_trafficLightRange[i]);
        
        // SI HAY ATENUACIÓN (la luz llega a este píxel)
        if (attenuation > 0.0) {
            // Normalizar la dirección a la luz
            trafficLightDir = normalize(trafficLightDir);
            
            // CALCULAR COMPONENTE DIFUSA DEL SEMÁFORO
            // dot(normal, trafficLightDir) mide cuánto la luz apunta a esta superficie
            // Si el surface mira a la luz: valor alto (iluminado)
            // Si mira para otro lado: valor bajo (en sombra)
            float trafficDiffuse = max(dot(normal, trafficLightDir), 0.0);
            
            // COMBINAR: color del semáforo × atenuación × componente difusa
            // Esto genera el efecto final de iluminación de la luz del semáforo
            vec3 trafficColor = u_trafficLightColors[i] * attenuation * trafficDiffuse;
            
            // SUMAR la iluminación del semáforo al color final
            finalColor.rgb += trafficColor;
        }
    }
    
    outColor = finalColor;
}