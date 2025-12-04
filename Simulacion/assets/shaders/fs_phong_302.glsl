#version 300 es
precision highp float;

// ============================================================
// INPUT VARIABLES
// Interpolated data passed from the vertex shader
// ============================================================
in vec3 v_normal;
in vec3 v_surfaceToLight;
in vec3 v_surfaceToView;
in vec4 v_color;
in vec3 v_worldPosition; // Required for point light distance calculation 

// ============================================================
// SCENE UNIFORMS
// Global lighting settings
// ============================================================
uniform vec4 u_ambientLight;
uniform vec4 u_diffuseLight;
uniform vec4 u_specularLight;

// ============================================================
// MULTI-LIGHT UNIFORMS (TRAFFIC & CYCLES)
// Arrays holding data for up to 100 dynamic point lights simultaneously
// ============================================================
// u_trafficLightPositions: XYZ position of each light source 
// u_trafficLightColors: RGB color of the light 
// u_trafficLightRange: Maximum effective distance of the light 
// u_numTrafficLights: Actual number of active lights in the scene 
uniform vec3 u_trafficLightPositions[100]; 
uniform vec3 u_trafficLightColors[100]; 
uniform float u_trafficLightRange[100]; 
uniform int u_numTrafficLights;

// ============================================================
// EMISSIVE OBJECT UNIFORMS
// Parameters for objects that glow (ignore shadows)
// ============================================================
// u_isEmissive: > 0.5 if the object glows, 0.0 otherwise
// u_emissiveColor: RGB color of the emitted light
uniform float u_isEmissive; 
uniform vec3 u_emissiveColor; 

out vec4 outColor;

// ============================================================
// ATTENUATION FUNCTION
// LITTLE DESCRIPTION: Calculates light intensity falloff based on distance
// using a smooth quadratic formula: 1 - (distance/range)^2
// ============================================================
float calculateAttenuation(float distance, float range) {
    // If distance exceeds range, light does not reach (attenuation = 0)
    if (distance > range) {
        return 0.0; 
    }
    
    // Smooth quadratic attenuation
    // The greater the distance, the lower the brightness
    float normalized = distance / range;
    // Formula: 1 - x^2 provides a natural falloff
    float attenuation = 1.0 - (normalized * normalized);
    
    return max(0.0, attenuation);
}

void main() {
    // ============================================================
    // EMISSIVE CHECK
    // If this object emits light (like traffic light spheres),
    // render pure emissive color and skip standard lighting calculations
    // ============================================================
    if (u_isEmissive > 0.5) { 
        outColor = vec4(u_emissiveColor, 1.0);
        return;
    }
    
    // ============================================================
    // VECTOR NORMALIZATION
    // Normalize interpolated vectors for accurate lighting math
    // ============================================================
    vec3 normal = normalize(v_normal);
    vec3 surfToLigthDirection = normalize(v_surfaceToLight); 
    vec3 surfToViewDirection = normalize(v_surfaceToView);

    // ============================================================
    // PHONG REFLECTION MODEL (BASE LIGHTING)
    // Calculates Ambient, Diffuse and Specular components using vertex color
    // ============================================================
    
    // Diffuse component (Lambert)
    float diffuse = max(dot(normal, surfToLigthDirection), 0.0);
    float specular = 0.0; 

    // Specular component (Phong)
    if (diffuse > 0.0){
        vec3 r = 2.0 * diffuse * normal - surfToLigthDirection;
        specular = pow(max(dot(surfToViewDirection, r), 0.0), 32.0);
    }

    // Combine components using the model's vertex color (v_color)
    vec4 ambientColor = v_color * u_ambientLight;
    vec4 diffuseColor = u_diffuseLight * v_color * diffuse;
    vec4 specularColor = u_specularLight * vec4(1.0) * specular;

    vec4 finalColor = ambientColor + diffuseColor + specularColor;

    // ============================================================
    // DYNAMIC POINT LIGHTS LOOP
    // Accumulates lighting from traffic lights and agents (max 100)
    // based on distance, range, and surface orientation
    // ============================================================
   for (int i = 0; i < 100; i++) {
        if (i >= u_numTrafficLights) break;

        // 1. Calculate vector and distance from pixel to light source
        vec3 trafficLightDir = u_trafficLightPositions[i] - v_worldPosition;
        float distToLight = length(trafficLightDir);
        
        // 2. Calculate attenuation factor (0.0 to 1.0)
        float attenuation = calculateAttenuation(distToLight, u_trafficLightRange[i]);

        // Only process if light reaches this pixel
        if (attenuation > 0.0) {
            // Normalize direction to light
            trafficLightDir = normalize(trafficLightDir);

            // 3. Calculate Diffuse component for this point light
            // Dot product determines if surface faces the light
            float trafficDiffuse = max(dot(normal, trafficLightDir), 0.0);

            // 4. Combine: Light Color * Attenuation * Diffuse Factor
           vec3 trafficColor = u_trafficLightColors[i] * attenuation * trafficDiffuse;

            // Add contribution to final pixel color
            finalColor.rgb += trafficColor;
        }
    }
    
   outColor = finalColor;
}