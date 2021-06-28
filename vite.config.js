import legacy from "@vitejs/plugin-legacy";
import copy from "rollup-plugin-copy";

/**
 * @type {import('vite').UserConfig}
 */
const config = {
  base: "/static/",
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        main: "./assets/src/scripts/main.js",
      },
    },
    outDir: "assets/dist",
    emptyOutDir: true,
  },
  plugins: [
    legacy({
      targets: ["ie >= 11"],
      additionalLegacyPolyfills: ["regenerator-runtime/runtime"],
      polyfills: ["es.promise", "es.array.iterator"],
    }),
    copy({
      targets: [
        {
          src: "./node_modules/bootstrap/dist/js/bootstrap.min.*",
          dest: "./assets/dist/vendor",
        },
        {
          src: "./node_modules/jquery/dist/jquery.slim.min.*",
          dest: "./assets/dist/vendor",
        },
        {
          src: "./node_modules/list.js/dist/list.min.*",
          dest: "./assets/dist/vendor",
        },
        {
          src: "./node_modules/select2/dist/css/select2.min.css",
          dest: "./assets/dist/vendor",
        },
        {
          src: "./node_modules/select2/dist/js/select2.min.js",
          dest: "./assets/dist/vendor",
        },
        {
          src: "./assets/src/js/*",
          dest: "./assets/dist/js",
        },
      ],
      hook: "writeBundle",
    }),
  ],
};

export default config;
