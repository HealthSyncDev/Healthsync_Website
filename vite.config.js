import { defineConfig } from 'vite';

/** Inline built CSS into index.html — kills the render-blocking stylesheet request. */
function inlineCss() {
  return {
    name: 'inline-css',
    enforce: 'post',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        if (!ctx.bundle) return html;
        let out = html;
        for (const asset of Object.values(ctx.bundle)) {
          if (asset.type !== 'asset' || !asset.fileName.endsWith('.css')) continue;
          const css = typeof asset.source === 'string' ? asset.source : Buffer.from(asset.source).toString('utf8');
          out = out.replace(
            new RegExp(`<link[^>]*href="/${asset.fileName}"[^>]*>`),
            `<style>${css}</style>`
          );
          // drop from emit so it isn't also requested
          delete ctx.bundle[asset.fileName];
        }
        return out;
      },
    },
    generateBundle(_opts, bundle) {
      for (const fileName of Object.keys(bundle)) {
        if (fileName.endsWith('.css')) delete bundle[fileName];
      }
    },
  };
}

export default defineConfig({
  plugins: [inlineCss()],
  server: {
    allowedHosts: ['healthsync.ae'],
  },
  build: {
    cssCodeSplit: false,
    assetsInlineLimit: 4096,
  },
});
