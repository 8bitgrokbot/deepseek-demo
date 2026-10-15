# ブロックブラスト・豪華版

`../block_blast/` を元に、OpenCode V2 + 無料DeepSeek V4.1 Flash が演出を大幅追加した版（単一の `index.html` + `audio/`）。

## 演出
canvasパーティクル爆発 / 衝撃波リング / フラッシュ / 画面シェイク / コンボ5段階(GOOD〜UNBELIEVABLE)とCOMBOカウントアップ / 背景アニメグラデ+光の粒(コンボで加速・色変化) / 設置バウンス / ドラッグ中グロー / スコアポップアップとカウントアップ / 全消し(花火+紙吹雪+ALL CLEAR!) / ハイスコア更新演出 / ゲームオーバー演出 / バイブ(対応端末)。

## サウンド仕様
- すべて `playSfx(name, opts)` に集約。Web Audio API、`audio/` 配下を fetch → decodeAudioData。ファイルが無い・デコード失敗の場合は黙ってスキップし、合成音にフォールバック。
- ファイル名: `pickup, place, invalid, clear1-4, combo1-5, allclear, highscore, gameover` (.wav) / `bgm.mp3` / `bgm_intense.mp3`（任意）。
- 呼び出し: つかむ→pickup、置けない→invalid、設置→place、ライン消し→clearN(1〜4)+comboN(ティア1〜5)、全消し→allclear、ハイスコア更新→highscore、ゲームオーバー→gameover。
- BGMは AudioBufferSourceNode の loop。コンボ中は bgm_intense にクロスフェード。
- iOS: 最初のタッチで AudioContext を resume。右上に 🔊/🔇 と 🎵 の切替（状態は localStorage 保存）。
- テスト用: `window.__audio` (`loaded`, `muted`, `bgmOn`, `played`)、`window.__game.fxState`。

音声素材の詳細は `audio/MANIFEST.md`。
