/**
 * Misura locale (Node, NON Cloudflare) del costo di un alarm con fauna: ripristino + N passi + snapshot + hash.
 * Uso: node genesis/fauna01/adapter/tests/bench.mjs   — habitat sintetici; serve solo a stimare l'ordine di grandezza.
 */
import { importaHabitat } from '../habitat.mjs';
import { creaZona, passoZona, snapshotZona, ripristinaZona } from '../zona.mjs';
import { habitatSintetico } from './genera_fixture.mjs';

function misura(lato, passiPerAllarme, giri = 300) {
  const h = importaHabitat(habitatSintetico({ w: lato, h: lato, zone_id: `bench-${lato}`, spawn: [[Math.round(lato * 0.3), Math.round(lato * 0.3)], [Math.round(lato * 0.3) + 1, Math.round(lato * 0.3)]] }), { consentiSintetico: true });
  let z = creaZona(h, { seed: 13 });
  for (let i = 0; i < 300; i++) passoZona(z);          // popolazione a regime
  let s = snapshotZona(z);
  const tempi = [];
  for (let g = 0; g < giri; g++) {
    const a = process.hrtime.bigint();
    z = ripristinaZona(h, s.testo, s.sha256);
    for (let i = 0; i < passiPerAllarme; i++) passoZona(z);
    s = snapshotZona(z);
    tempi.push(Number(process.hrtime.bigint() - a) / 1e6);
  }
  tempi.sort((a, b) => a - b);
  return { celle: lato * lato, adatte: h.suitable_cells, vivi: z.world.organisms.length, passi_per_allarme: passiPerAllarme,
    snapshot_caratteri: s.testo.length, ms_mediana: +tempi[giri >> 1].toFixed(3), ms_p99: +tempi[Math.floor(giri * 0.99)].toFixed(3) };
}
for (const lato of [24, 48, 64]) for (const n of [1, 20]) console.log(JSON.stringify(misura(lato, n)));
