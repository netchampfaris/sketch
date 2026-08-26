# Pick the in-browser SFC compiler and TypeScript stripper

Type: research
Status: claimed
Blocked by: 

## Question

Compare vue3-sfc-loader against a hand-rolled @vue/compiler-sfc + esbuild-wasm or sucrase pipeline for compiling `<script setup lang="ts">`, `<style scoped>`, and plain `.ts` modules in the browser. Report: browser bundle size of each option, support for scoped CSS and TS type stripping, error message quality (file, line, message), maintenance status. Recommend one.
