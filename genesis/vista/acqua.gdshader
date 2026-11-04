shader_type spatial;
render_mode blend_mix, cull_back, specular_schlick_ggx;
// Acqua low-poly: onde sfaccettate, colore che schiarisce verso la riva, riflessi del cielo.
uniform vec4 profonda : source_color = vec4(0.05, 0.22, 0.42, 1.0);
uniform vec4 chiara : source_color = vec4(0.22, 0.62, 0.72, 1.0);
uniform float ampiezza = 0.12;
varying vec3 mondo;

float onda(vec2 p, float t) {
	return sin(p.x * 0.35 + t * 1.1) * 0.5 + sin(p.y * 0.42 - t * 0.9) * 0.35 + sin((p.x + p.y) * 0.8 + t * 1.7) * 0.15;
}

void vertex() {
	mondo = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.y += onda(mondo.xz, TIME) * ampiezza;
}

void fragment() {
	vec3 n = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));   // facce piatte: aspetto low-poly
	NORMAL = n;
	float fres = pow(1.0 - clamp(dot(n, VIEW), 0.0, 1.0), 3.0);
	float luce = onda(mondo.xz * 1.7, TIME * 1.3) * 0.5 + 0.5;
	ALBEDO = mix(profonda.rgb, chiara.rgb, 0.35 + 0.35 * luce);
	ALPHA = mix(0.72, 0.95, fres);
	ROUGHNESS = 0.08;
	METALLIC = 0.0;
	SPECULAR = 0.6;
}
