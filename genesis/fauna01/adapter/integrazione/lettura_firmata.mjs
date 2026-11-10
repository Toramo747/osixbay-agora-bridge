/**
 * Chiave di firma locale e letture firmate (solo GET) del World Engine. Nessuna dipendenza, Node >= 20.
 *
 *   node lettura_firmata.mjs genera <file_chiave>
 *       crea una chiave Ed25519 nel file (non sovrascrive) e stampa SOLO la chiave pubblica,
 *       da aggiungere a CHIAVI_PUBBLICHE del Worker. Il file resta sul PC: non va in git ne' in chat.
 *   node lettura_firmata.mjs leggi <url_base> <agente> <file_chiave> [percorso]
 *       percorso predefinito /v1/stato; per la fauna: /v1/fauna oppure "/v1/fauna?area=0,0,8,8"
 * La chiave privata non viene mai stampata.
 */
import { generateKeyPairSync, createPrivateKey, createPublicKey, createHash, sign, randomBytes } from 'node:crypto';
import { writeFileSync, readFileSync } from 'node:fs';

const pubB64 = (k) => createPublicKey(k).export({ format: 'der', type: 'spki' }).subarray(-32).toString('base64');
const [comando, ...a] = process.argv.slice(2);

if (comando === 'genera' && a[0]) {
  const { privateKey } = generateKeyPairSync('ed25519');
  writeFileSync(a[0], privateKey.export({ format: 'pem', type: 'pkcs8' }), { flag: 'wx', mode: 0o600 });
  console.log('chiave privata scritta in', a[0], '(tienila fuori da git)');
  console.log('chiave pubblica da mettere in CHIAVI_PUBBLICHE:', pubB64(privateKey));
} else if (comando === 'leggi' && a.length >= 3) {
  const [base, agente, file, percorso = '/v1/stato'] = a;
  const chiave = createPrivateKey(readFileSync(file, 'utf8'));
  const ts = String(Math.floor(Date.now() / 1000)), nonce = randomBytes(16).toString('hex');
  const msg = `GET\n${percorso}\n${ts}\n${nonce}\n${createHash('sha256').update('').digest('hex')}`;
  const r = await fetch(base.replace(/\/$/, '') + percorso, { headers: {
    'X-Genesis-Agente': agente, 'X-Genesis-Timestamp': ts, 'X-Genesis-Nonce': nonce,
    'X-Genesis-Firma': sign(null, Buffer.from(msg), chiave).toString('base64') } });
  console.log(`HTTP ${r.status} alle ${new Date().toISOString()} (chiave pubblica usata: ${pubB64(chiave)})`);
  const testo = await r.text();
  try { console.log(JSON.stringify(JSON.parse(testo), null, 1)); } catch { console.log(testo.slice(0, 2000)); }
  process.exitCode = r.ok ? 0 : 1;
} else {
  console.error('uso: genera <file_chiave> | leggi <url_base> <agente> <file_chiave> [percorso]');
  process.exitCode = 2;
}
