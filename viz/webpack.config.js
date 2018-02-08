const webpack = require('webpack');
const path = require('path');
const hotMiddlewareScript = 'webpack-hot-middleware/client?path=/__webpack_hmr&timeout=20000&reload=true';


module.exports = {
  context: __dirname,
  // Include the hot middleware with each entry point
  entry: {
		bundle: ['./main.js', hotMiddlewareScript]
	},
  output: {
    path: __dirname,
    publicPath: '/',
    filename: '[name].js'
  },
  devtool: 'cheap-module-source-map',
  module: {
    rules: [
      {
        test: /\.js$/i,
        exclude: [/node_modules/],
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env', '@babel/preset-react'],
            plugins: ['@babel/plugin-proposal-object-rest-spread']
          }
        }
      }
    ]
  },
  resolve: {
    extensions: ['.js', '.sass'],
    modules: ['node_modules'],
    alias: {
      '~' : __dirname
    }

  },
  devServer: {
    historyApiFallback: true
  },
	plugins: [
		 new webpack.HotModuleReplacementPlugin()
	]
};
