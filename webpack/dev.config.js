const { merge } = require('webpack-merge');
const commonConfig = require('./common.config');

module.exports = merge(commonConfig, {
  mode: 'development',
  devtool: 'inline-source-map',
  devServer: {
    host: '0.0.0.0',
    port: 3000,
    // We need hot=false (Disable HMR) to set liveReload=true
    hot: false,
    liveReload: true,
  },
});
