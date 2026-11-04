shader_type spatial;
render_mode blend_mix, cull_back, specular_schlick_ggx;
// Acqua: la profondità arriva dal fondale del generatore (COLOR.r: 0 = riva, 1 = largo),
// così colore e schiuma sono gli stessi con ogni renderer.
uniform vec4 bassa : source_color = vec4(0.278, 0.722, 0.788, 1.0); // #47B8C9 acqua chiara
uniform vec4 profonda : source_color = vec4(0.114, 0.435, 0.549, 1.0); // #1D6F8C acqua profonda
uniform float ampiezza = 0.012;
varying float prof;
varying vec3 mondo;

float onda(vec2 p, float t) {
	return sin(p.x * 1.3 + t * 1.2) * 0.5 + sin(p.y * 1.6 - t * 0.9) * 0.35 + sin((p.x + p.y) * 2.7 + t * 1.8) * 0.15;
}

void vertex() {
	prof = COLOR.r;
	mondo = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.y += onda(mondo.xz, TIME) * ampiezza;
}

void fragment() {
	NORMAL = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	float riva = 1.0 - smoothstep(0.0, 0.07, prof);
	float onde = smoothstep(0.6, 0.9, sin(prof * 60.0 - TIME * 1.5) * 0.5 + 0.5) * (1.0 - smoothstep(0.04, 0.16, prof));
	vec3 col = mix(bassa.rgb, profonda.rgb, smoothstep(0.0, 0.7, prof));
	col = mix(col, vec3(0.97, 0.99, 1.0), clamp(riva * 0.9 + onde * 0.45, 0.0, 1.0));
	ALBEDO = col;
	ALPHA = clamp(mix(0.6, 0.94, smoothstep(0.0, 0.5, prof)) + riva * 0.3, 0.0, 1.0);
	ROUGHNESS = 0.12;
	SPECULAR = 0.5;
}
