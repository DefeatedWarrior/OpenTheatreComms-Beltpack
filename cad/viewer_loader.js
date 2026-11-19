// The model is glTF JSON with its geometry as base64. Rebuild a GLB in memory and parse it, so nothing has to
// fetch a data: URL (some hosts' security policies block that).
const loadModel = (onLoad, onErr) => fetch('beltpack.json').then((r) => {
  if (!r.ok) throw new Error('beltpack.json: HTTP ' + r.status);
  return r.json();
}).then((j) => {
  const uri = j.buffers[0].uri; const b64 = uri.slice(uri.indexOf(',') + 1);
  const raw = atob(b64); const bin = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bin[i] = raw.charCodeAt(i);
  delete j.buffers[0].uri; j.buffers[0].byteLength = bin.length;
  const js = new TextEncoder().encode(JSON.stringify(j));
  const jl = js.length + ((4 - js.length % 4) % 4), bl = bin.length + ((4 - bin.length % 4) % 4);
  const total = 12 + 8 + jl + 8 + bl; const buf = new ArrayBuffer(total); const dv = new DataView(buf); const u8 = new Uint8Array(buf);
  dv.setUint32(0, 0x46546C67, true); dv.setUint32(4, 2, true); dv.setUint32(8, total, true);
  dv.setUint32(12, jl, true); dv.setUint32(16, 0x4E4F534A, true); u8.fill(0x20, 20, 20 + jl); u8.set(js, 20);
  const o = 20 + jl; dv.setUint32(o, bl, true); dv.setUint32(o + 4, 0x004E4942, true); u8.set(bin, o + 8);
  new GLTFLoader().parse(buf, '', onLoad, onErr);
}).catch(onErr);
loadModel((gltf) => {
