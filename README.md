# NestBlocks_Wren

## LP の公開（GitHub Pages）

`landing/` を GitHub Pages の公開ルートとして配信します。
公開 URL: https://mecanam.github.io/NestBlocks_Wren/

1. GitHub のリポジトリで **Settings → Pages** を開きます。
2. **Build and deployment → Source** を **GitHub Actions** に設定します。
3. `.github/workflows/pages.yml` を含めて `main` にコミット・プッシュします。
4. **Actions → Deploy landing page** が成功すると公開されます。
   設定前にプッシュした場合は、同じ画面の **Run workflow** から再実行できます。

以後、`main` の `landing/` を更新すると自動で再公開されます。
LP の画像・スクリプトは相対パスのため、この URL からそのまま利用できます。

公開時には、コミット済みの `landing/firmware.js` をそのまま配信します。
GitHub Actions ではファームウェアをビルドしないため、隣接する NestBlocks のソースは不要です。
ファームウェア更新時は、ローカルでビルドして更新した `landing/firmware.js` と
`landing/index.html` もコミットしてください。
