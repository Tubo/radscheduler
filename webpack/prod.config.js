const { merge } = require('webpack-merge');
const commonConfig = require('./common.config');

// This variable should mirror the one from config/settings/production.py
const staticUrl = '/static/';

const config = merge(commonConfig, {
  mode: 'production',
  devtool: 'source-map',
  bail: true,
  output: {
    publicPath: `${staticUrl}webpack_bundles/`,
  },
});

// Compile Elm with --optimize for production.
const elmRule = config.module.rules.find(
  (rule) => String(rule.test) === String(/\.elm$/),
);
elmRule.use.options = { ...elmRule.use.options, optimize: true };

module.exports = config;
