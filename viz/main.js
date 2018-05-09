/* global window,document */
import React, {Component} from 'react';
import {render} from 'react-dom';
import MapGL from 'react-map-gl';
import DeckGLOverlay from './deckgl-overlay.js';
import {json as requestJson} from 'd3-request';
import MAPBOX_TOKEN from './token';

const SEC_PER_FRAME = 0.5;
const META = '/meta.json'; // center of place to start viewport
const DATA_URL = {
  trips: '/trips.json', // trips
  buses: '/stops.json', // bus stops (inferred)
};

class Info extends Component {
  render() {
    return (
      <ul>
        {Object.keys(this.props).map(k => {
          return <li key={k}>{k}: {this.props[k]}</li>
        })}
      </ul>
    );
  }
}

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

    Object.keys(DATA_URL).map(k => {
      requestJson(DATA_URL[k], (error, response) => {
        if (!error) {
          let update = {};
          update[k] = response;
          this.setState(update);
        }
      });
    });
    requestJson(META, (error, response) => {
      if (!error) {
        let viewport = this.state.viewport;
        viewport.latitude = response.lat;
        viewport.longitude = response.lng;
        this.setState({viewport: viewport, time: response.start_time});
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
    this.setState({
      time: this.state.time + SEC_PER_FRAME
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
      <div>
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
        <Info time={time.toFixed(2)} />
      </div>
    );
  }
}

render(<Root />, document.body.appendChild(document.createElement('div')));

