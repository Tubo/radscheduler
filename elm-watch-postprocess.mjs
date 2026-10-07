// @ts-check
// Minifies optimized Elm builds (`elm-watch make --optimize`), with the terser settings the Elm guide
// recommends: Elm's output has no side effects in these helpers, so terser may drop and inline freely.
import { minify } from 'terser';

const pureFuncs = [
  'F2',
  'F3',
  'F4',
  'F5',
  'F6',
  'F7',
  'F8',
  'F9',
  'A2',
  'A3',
  'A4',
  'A5',
  'A6',
  'A7',
  'A8',
  'A9',
];

/** @type {import("elm-watch/elm-watch-node").Postprocess} */
export default async function postprocess({ code, compilationMode }) {
  if (compilationMode !== 'optimize') {
    return code;
  }
  const result = await minify(code, {
    compress: {
      pure_funcs: pureFuncs,
      pure_getters: true,
      keep_fargs: false,
      unsafe_comps: true,
      unsafe: true,
    },
    mangle: true,
  });
  if (result.code === undefined) {
    throw new Error('terser returned no code');
  }
  return result.code;
}
