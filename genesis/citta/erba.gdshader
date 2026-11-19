shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, specular_disabled;
// Ciuffi d'erba mossi dal vento; più scuri alla base.
varying float alto;
void vertex() {
	alto = clamp(VERTEX.y / 0.2, 0.0, 1.0);
	vec3 w = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float vento = sin(TIME * 1.7 + w.x * 0.6 + w.z * 0.4) * 0.5 + sin(TIME * 2.9 + w.x * 1.3) * 0.25;
	VERTEX.x += vento * 0.05 * alto * alto;
	VERTEX.z += vento * 0.02 * alto * alto;
	NORMAL = vec3(0.0, 1.0, 0.0);
}
void fragment() {
	ALBEDO = COLOR.rgb * mix(0.55, 1.08, alto);
	ROUGHNESS = 1.0;
}
