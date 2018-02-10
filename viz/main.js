/* global window,document */
import React, {Component} from 'react';
import {render} from 'react-dom';
import MapGL from 'react-map-gl';
import DeckGLOverlay from './deckgl-overlay.js';
import {json as requestJson} from 'd3-request';
import MAPBOX_TOKEN from './token';

// Source data CSV
const DATA_URL = {
  TRIPS:
    '/trips.json',
  COORD:
    '/coord.json',
  BUSES:
    '/buses.json'
};

class Root extends Component {
  constructor(props) {
    super(props);
    this.state = {
      viewport: {
        ...DeckGLOverlay.defaultViewport,
        width: 500,
        height: 500
      },
      trips: null,
      buses: null,
      time: 0
    };

    requestJson(DATA_URL.TRIPS, (error, response) => {
      if (!error) {
        this.setState({trips: response});
      }
    });
    requestJson(DATA_URL.BUSES, (error, response) => {
      if (!error) {
        this.setState({buses: response});
      }
    });
    requestJson(DATA_URL.COORD, (error, response) => {
      if (!error) {
        let viewport = this.state.viewport;
        viewport.latitude = response.lat;
        viewport.longitude = response.lng;
        this.setState({viewport: viewport})
      }
    });

  }

  componentDidMount() {
    window.addEventListener('resize', this._resize.bind(this));
    this._resize();
    this._animate();
  }

  componentWillUnmount() {
    if (this._animationFrame) {
      window.cancelAnimationFrame(this._animationFrame);
    }
  }

  _animate() {
    const timestamp = Date.now();
    const loopLength = 1800;
    const loopTime = 60000;

    this.setState({
      time: (timestamp % loopTime) / loopTime * loopLength
    });
    this._animationFrame = window.requestAnimationFrame(this._animate.bind(this));
  }

  _resize() {
    this._onViewportChange({
      width: window.innerWidth,
      height: window.innerHeight
    });
  }

  _onViewportChange(viewport) {
    this.setState({
      viewport: {...this.state.viewport, ...viewport}
    });
  }

  render() {
    const {viewport, trips, buses, time} = this.state;

    return (
      <MapGL
        {...viewport}
        mapStyle="mapbox://styles/mapbox/dark-v9"
        onViewportChange={this._onViewportChange.bind(this)}
        mapboxApiAccessToken={MAPBOX_TOKEN}
      >
        <DeckGLOverlay
          viewport={viewport}
          trips={trips}
          buses={buses}
          trailLength={180}
          time={time}
        />
      </MapGL>
    );
  }
}

render(<Root />, document.body.appendChild(document.createElement('div')));

