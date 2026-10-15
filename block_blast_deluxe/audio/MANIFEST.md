# Block Blast Deluxe — オーディオ素材

すべてコード生成（`gsound` / sfxr風シンセ + チップチューンBGM）のオリジナル音源。著作権フリー扱いで使用可。
- SFX: `.wav` 44.1kHz / 16bit PCM / モノラル / 2秒以内 / ピーク −3 dBFS / クリップなし
- BGM: `.mp3` 44.1kHz / ステレオ / 160kbps CBR / ピーク約 −11 dBFS（SFXより約8dB小さい）
- iPhone Safari で再生可能な形式（WAV PCM / MP3）のみ使用

## ファイル一覧

| ファイル | 長さ | トリガー案 |
|---|---|---|
| `pickup.wav` | 0.14s | ブロックをつかんだ（ドラッグ開始）。軽く上がるサイン波 |
| `place.wav` | 0.13s | ブロックをボードに置いた。ポンと弾む音 |
| `invalid.wav` | 0.39s | 置けない場所に離した／ブロックが戻る。低いブッブー |
| `clear1.wav` | 0.41s | 1ライン消し。4音の上昇アルペジオ |
| `clear2.wav` | 0.67s | 2ライン同時消し。6音＋キラキラ |
| `clear3.wav` | 1.13s | 3ライン同時消し。派手な上昇＋和音 |
| `clear4.wav` | 1.62s | 4ライン以上。花火風（打ち上げ→爆発→パチパチ） |
| `combo1.wav` 〜 `combo5.wav` | 0.21 / 0.31 / 0.42 / 0.53 / 0.78s | コンボ段階1〜5(以上は5)。段階ごとにルート音が C5→D5→E5→G5→A5 と上がり、音数も増える |
| `allclear.wav` | 1.72s | 盤面を全消し（オールクリア）。ファンファーレ |
| `highscore.wav` | 1.67s | ハイスコア更新（ゲームオーバー画面などで） |
| `gameover.wav` | 1.84s | ゲームオーバー。下降する4音 |
| `bgm.mp3` | 75.000s | 通常BGM（128BPM / 40小節 / ハ長調） |
| `bgm_intense.mp3` | 67.606s | 激しいBGM（142BPM / 同じ40小節構成・同じハ長調。コンボ中にクロスフェードして切替） |

## 実装メモ（推奨）
- 消去時の組み合わせ例: 消したライン数で `clear1〜4`、コンボ中なら `combo{n}` を **少し遅らせて(80〜120ms)重ねる**。全消しなら `allclear` を追加で鳴らす。
- 音量: SFXはそのままゲイン1.0、BGMは 1.0（すでに小さめ）。SFX多重再生時は master gain 0.8 程度でも可。
- `bgm.mp3` と `bgm_intense.mp3` は **同じ小節構成**なので、再生位置の比率で対応づけられる（`pos/75.0 * 67.606`）。
- BGMは一周がちょうど小節境界。波形はループ点で連続（残響も先頭に回り込み済み）。

## MP3ループの注意（重要）
- MP3はエンコーダ遅延（約1100サンプル）があるため、プレイヤー次第でループ継ぎ目に数十msの無音/ノイズが出ることがある。LAMEヘッダ(gapless情報)付きで書き出してあり、ffmpegのデコードでは長さ・位相ともに一致（bgm: 3,307,500サンプル、ずれ0）を確認済み。
- 最も安全なのは **Web Audio API の `AudioBufferSourceNode.loop = true`**（`<audio loop>` は iOS で隙間が出やすい）。
- それでも継ぎ目が気になる場合は下の「クロスフェードループ」を使う（20〜60msの重ねで目立たなくなる）。

## JS スニペット（iOS Safari対応）
```js
// ===== 初期化: iOSは最初のタッチでAudioContextをresumeする必要あり =====
const AC = window.AudioContext || window.webkitAudioContext;
const ctx = new AC();
const master = ctx.createGain(); master.connect(ctx.destination);
const sfxGain = ctx.createGain(); sfxGain.connect(master);
const bgmGain = ctx.createGain(); bgmGain.gain.value = 1.0; bgmGain.connect(master);
const bufs = {};

const SFX = ['pickup','place','invalid','clear1','clear2','clear3','clear4',
             'combo1','combo2','combo3','combo4','combo5','allclear','highscore','gameover'];

async function load(name, ext) {
  const res = await fetch(`audio/${name}.${ext}`);
  const arr = await res.arrayBuffer();
  // Safari古いバージョン対策: Promise版が無い場合はコールバック版
  bufs[name] = await new Promise((ok, ng) => ctx.decodeAudioData(arr, ok, ng));
}
async function loadAll() {
  await Promise.all([...SFX.map(n => load(n, 'wav')), load('bgm', 'mp3'), load('bgm_intense', 'mp3')]);
}

function unlockAudio() {           // 最初のタップ/クリックで呼ぶ
  if (ctx.state !== 'running') ctx.resume();
  window.removeEventListener('touchend', unlockAudio);
  window.removeEventListener('click', unlockAudio);
}
window.addEventListener('touchend', unlockAudio);
window.addEventListener('click', unlockAudio);

// ===== SFX =====
function sfx(name, { delay = 0, gain = 1, rate = 1 } = {}) {
  const b = bufs[name]; if (!b) return;
  const s = ctx.createBufferSource(); s.buffer = b; s.playbackRate.value = rate;
  const g = ctx.createGain(); g.gain.value = gain;
  s.connect(g); g.connect(sfxGain); s.start(ctx.currentTime + delay);
}
function onLinesCleared(lines, combo, allClear) {
  sfx('clear' + Math.min(Math.max(lines, 1), 4));
  if (combo >= 1) sfx('combo' + Math.min(combo, 5), { delay: 0.1 });
  if (allClear) sfx('allclear', { delay: 0.25 });
}

// ===== BGM（通常/激しい を2本同時に回してゲインでクロスフェード） =====
const BGM_LEN = { bgm: 75.0, bgm_intense: 67.606 };
const bgm = {};
function startBgm() {
  for (const name of ['bgm', 'bgm_intense']) {
    const s = ctx.createBufferSource(); s.buffer = bufs[name];
    s.loop = true; s.loopStart = 0; s.loopEnd = bufs[name].duration;   // 小節境界ちょうど
    const g = ctx.createGain(); g.gain.value = name === 'bgm' ? 1 : 0;
    s.connect(g); g.connect(bgmGain); s.start(ctx.currentTime);
    bgm[name] = { s, g };
  }
}
// intense=true でコンボ中の激しいBGMへ。小節構成が同じなので同時に回しておき、ゲインだけ切替
function setIntense(on, fade = 1.5) {
  const t = ctx.currentTime;
  const to = on ? ['bgm_intense', 'bgm'] : ['bgm', 'bgm_intense'];
  bgm[to[0]].g.gain.cancelScheduledValues(t); bgm[to[0]].g.gain.linearRampToValueAtTime(1, t + fade);
  bgm[to[1]].g.gain.cancelScheduledValues(t); bgm[to[1]].g.gain.linearRampToValueAtTime(0, t + fade);
}
// ※ テンポが違う(128/142BPM)ので、クロスフェード中は2曲が少しズレて聞こえる。1〜2秒の短いフェードがおすすめ。
//   気になるなら setIntense 時に bgm_intense を比率位置から頭出し(stop→start(offset = pos/75*67.606))して使う。

// ===== 継ぎ目が気になる場合のクロスフェードループ（loop=trueの代わり） =====
function loopWithCrossfade(name, xf = 0.04) {
  const buf = bufs[name], dur = buf.duration;
  function play(when) {
    const s = ctx.createBufferSource(); s.buffer = buf;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(1, when + xf);                    // フェードイン
    g.gain.setValueAtTime(1, when + dur - xf);
    g.gain.linearRampToValueAtTime(0, when + dur);                   // フェードアウト
    s.connect(g); g.connect(bgmGain); s.start(when);
    const next = when + dur - xf;                                    // xfぶん重ねて次を開始
    setTimeout(() => play(next), Math.max(0, (next - ctx.currentTime - 1) * 1000)); // 1秒前に予約
  }
  play(ctx.currentTime + 0.05);
}

// ===== ミュート/一時停止（タブ非表示時など） =====
document.addEventListener('visibilitychange', () => document.hidden ? ctx.suspend() : ctx.resume());
```

## 再生成
`/workspace/game-audio` のツールキットで再生成可能:
```
python examples/build_blockblast_sfx.py OUTDIR      # SFX 15個
python examples/build_blockblast_bgm.py OUTDIR      # bgm.mp3 / bgm_intense.mp3（MMLは examples/blockblast_bgm*.mml）
```
