#version 300 es
in vec4 a_position;
in vec3 a_normal;
in vec4 a_color;

// Scene uniforms
uniform vec3 u_lightWorldPosition;
uniform vec3 u_viewWorldPosition;

// Model uniforms
uniform mat4 u_world;
uniform mat4 u_worldInverseTransform;
uniform mat4 u_worldViewProjection;

// Transformed normals
out vec3 v_normal;
out vec3 v_surfaceToLight;
out vec3 v_surfaceToView;
out vec4 v_color;
// NUEVA VARIABLE: POSICIÓN MUNDIAL DEL FRAGMENTO
// Se envía al fragment shader para calcular distancias a las luces de los semáforos.
// Esto permite saber qué tan lejos está cada píxel de una fuente de luz.
out vec3 v_worldPosition;

void main() {
    // Transform the position of the vertices
    gl_Position = u_worldViewProjection * a_position;

    // Transform the normal vector along with the object
    v_normal = mat3(u_worldInverseTransform) * a_normal;

    // Get world position of the surface
    vec3 surfaceWorldPosition = (u_world * a_position).xyz;
    // ASIGNAR POSICIÓN MUNDIAL
    // Guardamos la posición del vértice en coordenadas mundiales (del mundo, no de la cámara).
    // El fragment shader la usará para calcular distancias a las luces de semáforos.
    v_worldPosition = surfaceWorldPosition;

    // Direction from the surface to the light
    v_surfaceToLight = u_lightWorldPosition - surfaceWorldPosition;

    // Direction from the surface to the view
    v_surfaceToView = u_viewWorldPosition - surfaceWorldPosition;
    
    // Pass the color to the fragment shader
    v_color = a_color;
}