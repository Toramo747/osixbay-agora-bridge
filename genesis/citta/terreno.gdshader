shader_type spatial;
render_mode diffuse_lambert_wrap, specular_disabled;
// Terreno morbido: colore dei biomi (COLOR), roccia sui pendii, macchie dell'erba e griglia vicino al cursore.
uniform float griglia = 0.0;
uniform vec2 cursore = vec2(0.0);
varying vec3 wpos;
varying vec3 wnorm;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnorm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float n = noise(wpos.xz * 2.3) * 0.6 + noise(wpos.xz * 9.0) * 0.4;
	vec3 c = COLOR.rgb * (0.9 + 0.2 * n);
	// pennellate larghe: zone più calde e più fredde, come un paesaggio dipinto
	float pen = noise(wpos.xz * 0.35) * 0.65 + noise(wpos.xz * 1.1) * 0.35;
	c = mix(c * vec3(0.92, 0.99, 1.04), c * vec3(1.07, 1.02, 0.90), pen);
	float roccia = smoothstep(0.86, 0.72, wnorm.y);
	c = mix(c, vec3(0.478, 0.455, 0.431) * (0.9 + 0.3 * n), roccia); // roccia #7A746E
	vec2 g = abs(fract(wpos.xz + 0.5) - 0.5);
	float linea = smoothstep(0.465, 0.5, max(g.x, g.y));
	float vicino = 1.0 - smoothstep(2.5, 6.0, length(wpos.xz - cursore));
	c = mix(c, vec3(1.0), linea * vicino * griglia * 0.55);
	ALBEDO = c;
	ROUGHNESS = 0.95;
}
